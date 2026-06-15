"""
AgentLoop: True ReAct-style Agent.

LLM 看到 question + history + tool results → 自行决定:
    - 调用工具继续检索 → 拿到结果 → 再决策
    - 直接生成回答 → 流式输出

没有固定轮数限制（安全阀 max_turns=8），LLM 自主控制何时停止检索。
"""

import json
import logging
import time
from typing import Any, Generator

from rag.agent.client.mcp_client import MCPClient
from rag.agent.client.memory import MemoryManager

logger = logging.getLogger("ragflow.agent.loop")

REACT_SYSTEM_PROMPT = """你是 RAGFlow 智能助教。当学生问课程相关问题时，必须调用工具检索。简单问候闲聊可直接回答。工具列表中包含可用的检索工具。"""


class AgentLoop:
    """ReAct Agent: LLM 自主决策检索 vs. 回答"""

    def __init__(
        self,
        mcp_url: str,
        chat_mdl,
        redis_conn=None,
        conversation_id: str = "",
        user_id: str = "",
        max_retrieval_turns: int = 2,  # kept for backward compat, not used in ReAct
    ):
        self.mcp_client = MCPClient(base_url=mcp_url)
        self.chat_mdl = chat_mdl
        self.memory = MemoryManager(
            redis_conn=redis_conn,
            conversation_id=conversation_id,
            user_id=user_id,
        )
        # ReAct 安全阀：最多允许 LLM 调用工具多少次
        self.max_tool_calls = 8

    def run(
        self,
        question: str,
        history: list[dict],
        kb_ids: list[str],
        tenant_ids: list[str],
        dialog,
        embd_id: str | None = None,
        rerank_id: str | None = None,
    ) -> Generator[dict, None, None]:
        """
        ReAct Agent 主循环：LLM 自主决策检索或回答，流式返回。

        Yields:
            dict: {"answer": str, "reference": dict}
        """
        start_time = time.time()

        # 1. 初始化 MCP 上下文
        self.mcp_client.initialize(
            tenant_ids=tenant_ids,
            kb_ids=kb_ids,
            embd_id=embd_id,
            rerank_id=rerank_id,
        )

        # 2. 获取工具列表
        mcp_tools = self.mcp_client.list_tools()
        openai_tools = self.mcp_client.get_openai_tools(mcp_tools)

        # 3. 初始化记忆
        self.memory.init_working_memory(question)

        # 4. 构建消息列表
        messages: list[dict] = []

        # 历史消息
        for msg in history[-6:]:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": content})

        # 加入当前用户问题（之前漏掉了！）
        messages.append({"role": "user", "content": question})

        retrieved_pages: list[dict] = []
        tool_call_log: str = ""  # 累积工具调用日志，prepend 到最终答案

        # 5. ReAct 循环
        for turn in range(self.max_tool_calls):
            logger.info(f"ReAct Turn {turn + 1}")

            # 构建当前轮消息
            current_messages = list(messages)

            # 如果有检索结果，追加为 system 上下文
            if retrieved_pages:
                context = self._build_retrieval_context(retrieved_pages)
                # 替换或添加系统提示
                if current_messages and current_messages[0]["role"] == "system":
                    current_messages[0]["content"] = REACT_SYSTEM_PROMPT + "\n\n" + context
                else:
                    current_messages.insert(0, {"role": "system", "content": REACT_SYSTEM_PROMPT + "\n\n" + context})
            else:
                if current_messages and current_messages[0]["role"] == "system":
                    current_messages[0]["content"] = REACT_SYSTEM_PROMPT
                else:
                    current_messages.insert(0, {"role": "system", "content": REACT_SYSTEM_PROMPT})

            # 调用 LLM（带工具）
            try:
                response = self.chat_mdl.chat_with_tools(
                    "",  # system is already in messages
                    current_messages,
                    {"tools": openai_tools, "tool_choice": "auto", "temperature": 0.3},
                )
            except Exception as e:
                logger.error(f"LLM 调用失败: {e}")
                break

            tool_calls = response.get("tool_calls") if isinstance(response, dict) else None
            logger.info(f"  LLM response: content={str(response.get('content',''))[:100]}, tool_calls={bool(tool_calls)}, reasoning={str(response.get('reasoning_content',''))[:100]}")

            if tool_calls:
                # LLM 决定调用工具
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    tool_name = fn.get("name", "")
                    args = fn.get("arguments", "{}")
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {}

                    logger.info(f"  LLM 调用工具: {tool_name}({json.dumps(args, ensure_ascii=False)[:100]})")

                    # 向前端发送工具调用开始事件（可视化推理过程）
                    tool_call_log += f"\n<tool_call name=\"{tool_name}\">\n"
                    yield {"answer": tool_call_log, "reference": {}}

                    # 执行工具
                    result = self.mcp_client.call_tool(tool_name, args)
                    logger.info(f"  Tool result for {tool_name}: total={result.get('total', '?')}, documents={result.get('documents', 'N/A')}, chunks={len(result.get('chunks', []))}, error={result.get('error', 'N/A')}")

                    # 记录检索结果
                    chunks = result.get("chunks", [])
                    self.memory.working.add_retrieved_pages(chunks)
                    self.memory.working.executed_tools.append(tool_name)
                    self.memory.working.add_turn_result(result)

                    # 向前端发送工具调用结果（可视化推理过程）
                    formatted = self._format_tool_result(tool_name, result)
                    tool_call_log += f"{formatted}\n</tool_call>\n"
                    yield {"answer": tool_call_log, "reference": {}}

                    # 把工具调用和结果加入消息
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": tc.get("id", f"call_{turn}"),
                            "type": "function",
                            "function": {"name": tool_name, "arguments": json.dumps(args, ensure_ascii=False)},
                        }],
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", f"call_{turn}"),
                        "content": self._format_tool_result(tool_name, result),
                    })

                retrieved_pages = list(self.memory.working.retrieved_pages)
                continue

            # LLM 返回了文本回答（无 tool_calls）→ 退出循环，生成答案
            break

        # 6. 流式生成最终答案
        self.memory.working.agent_state = "generating"
        answer = ""
        retrieved_pages = list(self.memory.working.retrieved_pages)

        for chunk in self._stream_answer(messages, retrieved_pages):
            answer = tool_call_log + "\n" + chunk if tool_call_log else chunk
            yield {"answer": answer, "reference": {}}

        # 7. 构建最终响应（规范化引用标记 + 转换 MinIO URL）
        answer = self._normalize_references(answer)
        final = self._build_final_response(answer, retrieved_pages)
        yield {"answer": answer, "reference": final.get("reference", {})}

        elapsed = time.time() - start_time
        logger.info(f"ReAct Agent 完成，耗时 {elapsed:.2f}s，共调用 {len(self.memory.working.executed_tools)} 次工具，检索 {len(retrieved_pages)} 页")

    # ── 内部方法 ──────────────────────────────────────────────

    def _build_retrieval_context(self, pages: list[dict]) -> str:
        """将检索到的页面构建为上下文文本"""
        if not pages:
            return ""
        parts = ["## 已检索到的课件内容\n"]
        seen = set()
        for i, p in enumerate(pages, 1):
            pid = p.get("page_id", "")
            if pid in seen:
                continue
            seen.add(pid)
            doc = p.get("docnm_kwd", "未知文档")
            page_num = p.get("page_num_int", "?")
            content = p.get("content_with_weight", "")[:400]
            score = p.get("rerank_score") or p.get("rrf_score") or p.get("similarity") or 0.0
            parts.append(
                f"[来源{i}] {doc} 第{page_num}页 (相关度:{score:.2f})\n{content}\n"
            )
        parts.append(f"\n共检索到 {len(parts) - 1} 个相关页面。如果内容足够，请直接回答；如果不够，可以继续检索。")
        return "\n".join(parts)

    def _format_tool_result(self, tool_name: str, result: dict) -> str:
        """格式化工具返回结果，成为 LLM 可读的文本。

        解耦设计：如果 result 中有 'summary' 字段，直接使用（由 tool 自行格式化）。
        否则按已知格式解析。新增 tool 只需在返回结果中包含 'summary' 字段，无需改此函数。
        """
        # 优先使用 tool 自带的人类可读摘要（解耦）
        summary = result.get("summary")
        if summary:
            return f"[{tool_name}]\n{summary}"

        # 通用 chunks 格式（hybrid_retrieve / web_search / get_adjacent_pages）
        chunks = result.get("chunks", [])
        if chunks:
            lines = [f"[{tool_name}] 返回 {len(chunks)} 个结果："]
            for i, c in enumerate(chunks[:5], 1):
                title = c.get("title") or c.get("docnm_kwd", "")
                url = c.get("url", "")
                content = (c.get("content") or c.get("content_with_weight", ""))[:300]
                score = c.get("rerank_score") or c.get("rrf_score") or c.get("score") or c.get("similarity") or 0.0
                page_num = c.get("page_num_int", "")
                header = f"  [{i}] {title}"
                if page_num:
                    header += f" (第{page_num}页)"
                if url:
                    header += f"\n     {url}"
                header += f"\n     相关性: {score:.2f}"
                lines.append(header)
                if content:
                    lines.append(f"     {content[:200]}")
            return "\n".join(lines)

        # documents 格式（list_documents）
        documents = result.get("documents")
        if documents:
            lines = [f"[{tool_name}] 共 {len(documents)} 个文档："]
            for i, d in enumerate(documents, 1):
                doc_id = d.get("doc_id", "")
                doc_name = d.get("doc_name", "")
                page_count = d.get("page_count", 0)
                first = d.get("first_page", 1)
                last = d.get("last_page", page_count)
                lines.append(f"  [{i}] {doc_name} (doc_id={doc_id}, {page_count}页, p{first}-{last})")
            return "\n".join(lines)

        # mindmap 格式（get_knowledge_structure）
        if "mindmap" in result and result.get("found"):
            mindmap = result.get("mindmap", {})
            lines = [f"[{tool_name}] 知识结构："]
            if isinstance(mindmap, dict) and "root" in mindmap:
                lines.append(json.dumps(mindmap["root"], ensure_ascii=False)[:2000])
            lines.append(f"  闪卡: {result.get('flashcards_count', 0)} 测验: {result.get('quiz_count', 0)}")
            return "\n".join(lines)

        # full_content 格式（get_full_page）
        if "full_content" in result and result.get("found"):
            content = result.get("full_content", "")[:1000]
            return f"[{tool_name}] p{result.get('page_num_int', '?')} {result.get('docnm_kwd', '')}:\n{content}"

        # 完全未知格式：JSON 序列化前 500 字符，仍可工作
        return f"[{tool_name}]\n{json.dumps(result, ensure_ascii=False)[:500]}"

    def _stream_answer(self, messages: list[dict], retrieved_pages: list[dict]) -> Generator[str, None, None]:
        """流式生成最终答案"""
        if retrieved_pages:
            context = self._build_retrieval_context(retrieved_pages)
            system = REACT_SYSTEM_PROMPT + "\n\n" + context + "\n\n请根据以上检索内容回答用户问题。引用来源时使用 ~~0== ~~1== 格式（对应上述[来源N]）。"
        else:
            system = REACT_SYSTEM_PROMPT + "\n\n当前未检索到相关内容，请基于你的知识回答。如果是知识性问题，请说明信息不足。"

        # 替换 system message
        msgs = list(messages)
        if msgs and msgs[0]["role"] == "system":
            msgs[0] = {"role": "system", "content": system}
        else:
            msgs.insert(0, {"role": "system", "content": system})

        try:
            gen_conf = {"temperature": 0.3, "max_tokens": 2048}
            for chunk in self.chat_mdl.chat_streamly("", msgs, gen_conf):
                yield chunk
        except Exception as e:
            logger.error(f"生成答案失败: {e}")
            yield f"\n\n*[生成失败: {e}]*"

    @staticmethod
    def _normalize_references(text: str) -> str:
        """将 LLM 生成的 '来源N' / '[来源N]' 文本转为前端可识别的 ~~N== 标记"""
        import re
        # [来源N] → ~~N-1==
        text = re.sub(r'\[来源(\d+)\]', lambda m: f'~~{int(m.group(1))-1}==', text)
        # （来源N）→ (~~N-1==)
        text = re.sub(r'（来源(\d+)）', lambda m: f'(~~{int(m.group(1))-1}==)', text)
        return text

    @staticmethod
    def _convert_minio_url(img_url: str) -> str:
        """将 minio://bucket/path 转为 HTTP URL，使前端可直接渲染图片"""
        if not img_url or not img_url.startswith("minio://"):
            return img_url or ""
        try:
            import os
            path = img_url[8:]  # 移除 "minio://"
            parts = path.split("/", 1)
            if len(parts) != 2:
                return img_url
            bucket, obj_path = parts
            host = os.getenv("MINIO_VISIT_HOST", "localhost")
            if "://" not in host:
                host = "http://" + host
            port = os.getenv("MINIO_PORT", "9000")
            return f"{host}:{port}/{bucket}/{obj_path}"
        except Exception:
            return img_url

    def _build_final_response(self, answer: str, retrieved_pages: list[dict]) -> dict:
        """构建最终响应，包含引用信息"""
        chunks = []
        seen = set()
        for page in retrieved_pages:
            page_id = page.get("page_id", "")
            if page_id in seen:
                continue
            seen.add(page_id)
            score = page.get("rerank_score") or page.get("rrf_score") or page.get("similarity") or 0.0
            chunks.append({
                "chunk_id": page_id,
                "content_with_weight": page.get("content_with_weight", "")[:300],
                "doc_id": page.get("doc_id", ""),
                "docnm_kwd": page.get("docnm_kwd", ""),
                "img_url": self._convert_minio_url(page.get("img_url", "")),
                "page_num_int": page.get("page_num_int", 0),
                "similarity": round(float(score), 4),
            })

        doc_aggs = []
        doc_ids_seen = set()
        for page in retrieved_pages:
            doc_id = page.get("doc_id", "")
            if doc_id and doc_id not in doc_ids_seen:
                doc_ids_seen.add(doc_id)
                doc_aggs.append({
                    "doc_id": doc_id,
                    "doc_name": page.get("docnm_kwd", ""),
                    "count": sum(1 for p in retrieved_pages if p.get("doc_id") == doc_id),
                })

        return {
            "answer": answer,
            "reference": {"chunks": chunks, "doc_aggs": doc_aggs},
        }
