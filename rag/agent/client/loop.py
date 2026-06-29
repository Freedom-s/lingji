import copy
import json
import logging
import time
from typing import Any, Generator

from rag.agent.client.mcp_client import MCPClient

logger = logging.getLogger("ragflow.agent.loop")

EMPTY_REF = {"total": 0, "chunks": [], "doc_aggs": []}

REACT_SYSTEM_PROMPT = """你是一个名为"灵机"的智能教学助手。你的目标是耐心、专业、准确地解答学生关于课程的问题。

【你的工作流与决策机制】
1. **意图判断**：如果学生只是简单问候、表达情绪或闲聊（如"你好"、"谢谢"、"太难了"），请直接用亲切的语气回复，**绝对不要**调用检索工具。
2. **知识检索**：如果学生询问具体的课程概念、知识点、作业要求或相关拓展，你**必须**优先使用工具进行检索。
3. **信息评估**：每次检索后，仔细阅读返回的结果。如果信息已经足够回答问题，请停止检索并开始生成答案；如果信息不足或只涵盖了部分问题，请提取新的关键词继续使用工具检索，直到获取完整信息。
4. **诚实原则**：如果你经过多次检索仍未找到相关内容，请坦诚地告诉学生"在当前课件/知识库中未能找到相关信息"，并根据你的通用知识给出合理的推测或建议，但必须明确区分"课件内容"和"通用知识"。

【回答规范】
- **客观准确**：严格基于检索到的内容作答，不要编造（幻觉）知识库中不存在的特定课程规定或数据。
- **结构清晰**：使用分段、列表等 Markdown 语法让回答易于阅读。
"""
# - **必须引用**：当你使用了检索结果中的信息时，**必须**在对应句子的末尾进行引用，引用格式必须严格为 `[来源N]`（例如：`机器学习是...[来源1]。` 或 `根据课件...[来源1][来源2]`）。N代表你参考的搜索结果编号。
class AgentLoop:
    """ReAct Agent: LLM 自主决策检索 vs. 回答"""

    def __init__(self, mcp_url: str, chat_mdl):
        self.mcp_client = MCPClient(base_url=mcp_url)
        self.chat_mdl = chat_mdl # 这个client是主要负责react范式的，所以他持有这个chat模型
        self.max_tool_calls = 10

    @staticmethod
    def _inject_context(tool_name: str, args: dict, kb_ids: list[str],
                        tenant_ids: list[str], tenant_id: str,
                        embd_id: str | None, rerank_id: str | None):
        """自动注入系统上下文参数。LLM 不传这些参数，AgentLoop 补上。"""
        needs_all = tool_name in ("hybrid_retrieve",)
        needs_es = tool_name in ("get_full_page", "get_adjacent_pages")
        needs_kb = tool_name in ("list_documents",)

        if needs_all:
            args.setdefault("tenant_ids", tenant_ids)
            args.setdefault("kb_ids", kb_ids)
            args.setdefault("tenant_id", tenant_id)
            args.setdefault("embd_id", embd_id or "")
            args.setdefault("rerank_id", rerank_id or "")
        elif needs_es:
            args.setdefault("tenant_ids", tenant_ids)
            args.setdefault("kb_ids", kb_ids)
        elif needs_kb:
            args.setdefault("kb_ids", kb_ids)

    def run(
        self,
        question: str,
        history: list[dict],
        kb_ids: list[str],
        tenant_ids: list[str],
        dialog,
        embd_id: str | None = None,
        rerank_id: str | None = None,
        max_images: int = 5,
    ) -> Generator[dict, None, None]:
        """
        ReAct Agent 主循环：LLM 自主决策检索或回答，流式返回。

        Yields:
            dict: {"answer": str, "reference": dict}
        """
        start_time = time.time()

        _tenant_id = tenant_ids[0] if tenant_ids else ""

        # 2. 获取工具列表
        mcp_tools = self.mcp_client.list_tools()
        mcp_tools = [t for t in mcp_tools if t.get("name") != "set_context"]
        openai_tools = self.mcp_client.get_openai_tools(mcp_tools)

        # 2. 构建消息列表
        messages: list[dict] = []

        # 历史消息
        for msg in history[-6:]:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": content})

        # 加入当前用户问题
        messages.append({"role": "user", "content": question})

        retrieved_pages: list[dict] = []
        seen_page_ids: set = set()
        executed_tools: list[str] = []
        tool_call_log: str = ""

        # 3. ReAct 循环
        for turn in range(self.max_tool_calls):
            logger.info(f"========== ReAct Turn {turn + 1}/{self.max_tool_calls} ==========")

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

            # ── 日志：发送给 LLM 的消息 ──
            logger.info(f"[AGENT_TRACE] Turn {turn+1} → LLM 输入:")
            logger.info(f"  tools: {[t['function']['name'] for t in openai_tools]}")
            for i, m in enumerate(current_messages):
                content_preview = str(m.get('content', ''))[:200]
                logger.info(f"  msg[{i}] role={m['role']} content_len={len(str(m.get('content','')))} preview={content_preview}")

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

            # ── 日志：LLM 返回结果 ──
            tool_calls = response.get("tool_calls") if isinstance(response, dict) else None
            logger.info(f"[AGENT_TRACE] Turn {turn+1} ← LLM 返回:")
            logger.info(f"  content: {str(response.get('content',''))[:300]}")
            logger.info(f"  reasoning_content: {str(response.get('reasoning_content',''))[:300]}")
            logger.info(f"  tool_calls: {json.dumps(tool_calls, ensure_ascii=False)[:500] if tool_calls else 'None'}")

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

                    # ── 日志：工具调用详情 ──
                    logger.info(f"[AGENT_TRACE] Turn {turn+1} → 调用工具: {tool_name}")
                    logger.info(f"  args: {json.dumps(args, ensure_ascii=False)}")

                    # 向前端发送工具调用开始事件（可视化推理过程）
                    tool_call_log += f"\n<tool_call name=\"{tool_name}\">\n"
                    yield {"answer": tool_call_log, "reference": EMPTY_REF}

                    # 注入系统上下文参数（LLM 不传的参数，AgentLoop 自动补上）
                    self._inject_context(tool_name, args, kb_ids, tenant_ids,
                                         _tenant_id, embd_id, rerank_id)

                    # 执行工具
                    result = self.mcp_client.call_tool(tool_name, args)

                    # ── 日志：工具返回结果 ──
                    logger.info(f"[AGENT_TRACE] Turn {turn+1} ← 工具结果: {tool_name}")
                    logger.info(f"  result: {json.dumps(result, ensure_ascii=False, default=str)[:2000]}")

                    # 记录检索结果
                    chunks = result.get("chunks", [])
                    for p in chunks:
                        pid = p.get("page_id", "")
                        if pid and pid not in seen_page_ids:
                            seen_page_ids.add(pid)
                            retrieved_pages.append(p)
                    executed_tools.append(tool_name)

                    # 向前端发送工具调用结果（可视化推理过程）
                    formatted = self._format_tool_result(tool_name, result)
                    tool_call_log += f"{formatted}\n</tool_call>\n"
                    yield {"answer": tool_call_log, "reference": EMPTY_REF}

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

                continue

            # LLM 返回了文本回答（无 tool_calls）→ 退出循环，生成答案
            logger.info(f"[AGENT_TRACE] Turn {turn+1} LLM 决定直接回答，退出 ReAct 循环")
            break

        # 5.5 循环结束后：注入图片到 user 消息（多模态 VLM 支持）
        images_base64 = self._fetch_images_from_minio(retrieved_pages, max_images)
        if images_base64:
            logger.info(f"注入 {len(images_base64)} 张图片到 user 消息")
            messages = self._inject_images_to_user_message(messages, images_base64)

        # 6. 流式生成最终答案
        answer = ""

        for chunk in self._stream_answer(messages, retrieved_pages):
            answer = tool_call_log + "\n" + chunk if tool_call_log else chunk
            yield {"answer": answer, "reference": EMPTY_REF}

        # 7. 构建最终响应（规范化引用标记 + 转换 MinIO URL）
        answer = self._normalize_references(answer)
        final = self._build_final_response(answer, retrieved_pages)
        yield {"answer": answer, "reference": final.get("reference", EMPTY_REF)}

        elapsed = time.time() - start_time
        logger.info(f"ReAct Agent 完成，耗时 {elapsed:.2f}s，共调用 {len(executed_tools)} 次工具，检索 {len(retrieved_pages)} 页")

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
            content = p.get("full_content", "")
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
                content = (c.get("content") or c.get("full_content", ""))
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
                    lines.append(f"     {content}")
            return "\n".join(lines)

        # documents 格式（list_documents）
        documents = result.get("documents")
        if documents:
            lines = [f"[{tool_name}] 共 {len(documents)} 个文档："]
            for i, d in enumerate(documents, 1):
                lines.append(
                    f"  [{i}] {d.get('doc_name', '')} ({d.get('page_count', 0)}页,"
                    f" doc_id={d.get('doc_id', '')}, kb={d.get('kb_name', '')})"
                )
            return "\n".join(lines)

        # mindmap 格式（get_knowledge_structure）
        if "mindmap" in result:
            mindmap = result.get("mindmap")
            if mindmap is None:
                return f"[{tool_name}] 未找到 {result.get('doc_id', '')} 的知识结构"
            lines = [f"[{tool_name}] 知识结构："]
            if isinstance(mindmap, dict) and "root" in mindmap:
                lines.append(json.dumps(mindmap["root"], ensure_ascii=False)[:2000])
            return "\n".join(lines)

        # full_content 格式（get_full_page）
        if "full_content" in result:
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
                "page_id": page_id,
                "content_with_weight": page.get("full_content", ""),
                "doc_id": page.get("doc_id", ""),
                "docnm_kwd": page.get("docnm_kwd", ""),
                "kb_id": page.get("kb_id", ""),
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
            "reference": {"total": len(chunks), "chunks": chunks, "doc_aggs": doc_aggs},
        }

    def _fetch_images_from_minio(self, retrieved_pages: list[dict], max_images: int = 5) -> list[str]:
        """从检索结果中提取最相关的页面截图并转为 base64 data URL。

        去重 → 按相关性分数降序 → 取前 max_images 张 → MinIO 拉取 → base64。
        单张获取失败跳过，不阻断流程。
        """
        if max_images <= 0 or not retrieved_pages:
            return []

        # 1. 按 page_id 去重
        seen: set[str] = set()
        unique_pages: list[dict] = []
        for p in retrieved_pages:
            pid = p.get("page_id", "")
            if pid and pid not in seen:
                seen.add(pid)
                unique_pages.append(p)

        # 2. 按相关性分数降序排列
        # Zero means "not scored" in this system, not "scored as irrelevant" -- falling through is intentional
        def _score(p: dict) -> float:
            return float(
                p.get("rerank_score")
                or p.get("rrf_score")
                or p.get("similarity")
                or 0.0
            )
        unique_pages.sort(key=_score, reverse=True)

        # 3. 取前 max_images 张，筛选有 img_url 的
        candidates = [p for p in unique_pages[:max_images] if p.get("img_url")]
        if not candidates:
            logger.info("没有可注入的图片（所有候选页面均无 img_url）")
            return []

        # 4. 从 MinIO 获取 base64
        try:
            from api.db.services.dialog_service import get_image_base64_from_minio
        except ImportError:
            logger.warning("无法导入 get_image_base64_from_minio，跳过图片注入")
            return []

        images: list[str] = []
        for p in candidates:
            img_url = p.get("img_url", "")
            page_num = p.get("page_num_int", "?")
            doc_name = p.get("docnm_kwd", "")
            try:
                b64 = get_image_base64_from_minio(img_url)
                if b64:
                    images.append(b64)
                    logger.debug(f"图片获取成功: {doc_name} p{page_num} ({len(b64)} chars)")
                else:
                    logger.warning(f"图片获取返回空: {doc_name} p{page_num} {img_url}")
            except Exception as e:
                logger.warning(f"图片获取异常 {doc_name} p{page_num} {img_url}: {e}")

        logger.info(f"图片注入准备: {len(images)}/{len(candidates)} 张成功")
        return images

    def _inject_images_to_user_message(self, messages: list[dict], images_base64: list[str]) -> list[dict]:
        """将 base64 图片注入第一个 user 消息，改写为 multimodal content 格式。

        找到第一个 role="user" 且 content 为纯文本的消息，
        将其 content 改写为 [{"type": "text", ...}, {"type": "image_url", ...}, ...]。

        如果 images_base64 为空，原样返回 messages（浅拷贝）。
        始终返回新列表，不修改传入的 messages。
        """
        if not images_base64:
            return list(messages)

        msgs = copy.deepcopy(messages)

        for msg in msgs:
            if msg.get("role") == "user" and isinstance(msg.get("content"), str):
                original_text = msg["content"]
                content_parts: list[dict] = [
                    {"type": "text", "text": original_text},
                ]
                for b64 in images_base64:
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": b64, "detail": "auto"},
                    })
                msg["content"] = content_parts
                logger.info(
                    f"user 消息已改写为 multimodal: "
                    f"text_len={len(original_text)}, images={len(images_base64)}"
                )
                break
        else:
            # 没有找到可改写的 user 消息（理论上不会发生）
            logger.warning("未找到 role=user 且 content 为 str 的消息，跳过图片注入")

        return msgs
