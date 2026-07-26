import json
import logging
import re
import time
from typing import Generator

from rag.agent.client.mcp_client import MCPClient

logger = logging.getLogger("ragflow.agent.loop")

EMPTY_REF = {"total": 0, "chunks": [], "doc_aggs": []}

REACT_SYSTEM_PROMPT = """你是一个名为"灵机"的智能教学助手。你的目标是耐心、专业、准确地解答学生关于课程的问题。

【你的工作流与决策机制】
1. **意图判断**：如果学生只是简单问候、表达情绪或闲聊（如"你好"、"谢谢"、"太难了"），请直接用亲切的语气回复，**绝对不要**调用检索工具。
2. **知识检索**：如果学生询问具体的课程概念、知识点、作业要求或相关拓展，你**必须**优先使用工具进行检索。
3. **信息评估**：仔细阅读每次检索返回的结果。hybrid_retrieve 已经提供了页面全文和截图，无需额外获取。如果信息足够，直接作答；覆盖不全则拆分关键词再查。
4. **空结果处理与联网回退**：如果 hybrid_retrieve 返回 `"total": 0` 或空 `"chunks": []`：
   - 先尝试将问题拆分成更小的子问题分别检索。
   - 拆分后仍无结果 → 调用 **web_search** 联网搜索。
   - web_search 也无结果 → 告知学生在课件和互联网中均未找到相关内容。

【终止条件 — 必须遵守】
- 检索结果覆盖了问题所有关键点 → 立即作答。
- 同一子问题检索 2 次仍返回空 → 课件中不存在，停止检索，告知学生。
- 基于通用知识回答时，必须明确标注"以下信息来自通用知识，课件中未找到相关内容"。

【回答规范】
- **客观准确**：严格基于检索到的内容作答，不要编造课件中不存在的细节。
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
        needs_es = tool_name in ("get_adjacent_pages",)
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
        openai_tools = self.mcp_client.get_openai_tools(mcp_tools)

        # 2. 构建消息列表
        messages: list[dict] = []

        # 历史消息：只保留 user 问题和 assistant 最终文本回答，清理 ReAct 中间产物
        for msg in history[-6:]:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                messages.append({"role": "user", "content": content})
            elif role == "assistant" and content:
                # 剥离 tool_call_log，只保留 LLM 真正输出的回答部分
                clean = re.sub(r"<tool_call[^>]*>.*?</tool_call>", "", content, flags=re.DOTALL).strip()
                if clean:
                    messages.append({"role": "assistant", "content": clean})

        # 加入当前用户问题
        messages.append({"role": "user", "content": question})

        retrieved_pages: dict[str, dict] = {}  # page_id → 页面完整信息，天然去重
        executed_tools: list[str] = []
        tool_call_log: str = ""

        # 3. ReAct 循环
        for turn in range(self.max_tool_calls):
            logger.info(f"========== ReAct Turn {turn + 1}/{self.max_tool_calls} ==========")

            # 构建系统 prompt（含检索上下文）
            if retrieved_pages:
                context = self._build_retrieval_context(retrieved_pages)
                system_prompt = REACT_SYSTEM_PROMPT + "\n\n" + context
            else:
                system_prompt = REACT_SYSTEM_PROMPT

            # ── 日志 ──
            logger.info(f"[AGENT_TRACE] Turn {turn+1} → LLM 输入:")
            logger.info(f"  tools: {[t['function']['name'] for t in openai_tools]}")
            logger.info(f"  messages: {json.dumps(self._log_messages(messages), indent=2, ensure_ascii=False)}")

            # 调用 LLM（带工具），system prompt 由 _build_messages 自动插入
            try:
                response = self.chat_mdl.chat_with_tools(
                    system_prompt,
                    messages,
                    {"tools": openai_tools, "tool_choice": "auto", "temperature": 0.0, "top_p": 1.0},
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

                    # 保存 LLM 原始参数（注入前），用于记录 assistant 消息
                    llm_args = dict(args)

                    # 注入系统上下文参数（LLM 不传的参数，AgentLoop 自动补上）
                    self._inject_context(tool_name, args, kb_ids, tenant_ids,
                                         _tenant_id, embd_id, rerank_id)

                    # 执行工具
                    result = self.mcp_client.call_tool(tool_name, args)

                    # ── 日志：工具返回结果 ──
                    logger.info(f"[AGENT_TRACE] Turn {turn+1} ← 工具结果: {tool_name}")
                    logger.info(f"  result: {json.dumps(result, ensure_ascii=False, default=str)[:2000]}")

                    # 记录检索结果 + 拉取新页面图片注入 user message
                    new_images: list[str] = []
                    for p in result.get("chunks", []):
                        pid = p.get("page_id", "")
                        if not pid:
                            continue
                        # 记录页面（dict 自动去重）
                        is_new = pid not in retrieved_pages
                        retrieved_pages[pid] = p
                        # 只对新页面拉取图片
                        if is_new and p.get("img_url"):
                            b64 = self._fetch_single_image(p["img_url"])
                            if b64:
                                new_images.append(b64)

                    executed_tools.append(tool_name)

                    # 向前端发送工具调用结果（可视化推理过程）
                    result_text = json.dumps(result, ensure_ascii=False, default=str)
                    tool_call_log += f"{result_text}\n</tool_call>\n"
                    yield {"answer": tool_call_log, "reference": EMPTY_REF}

                    # 把工具调用和结果加入消息
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": tc.get("id", f"call_{turn}"),
                            "type": "function",
                            "function": {"name": tool_name, "arguments": json.dumps(llm_args, ensure_ascii=False)},
                        }],
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", f"call_{turn}"),
                        "content": result_text,
                    })

                    # 工具结果之后，将新页面图片作为 user 消息注入
                    if new_images:
                        self._inject_images_into_messages(messages, new_images)
                        logger.info(f"注入 {len(new_images)} 张新图片到 user message，累计 {len(retrieved_pages)} 个页面")

                continue

            # LLM 返回了文本回答（无 tool_calls）→ 退出循环，生成答案
            logger.info(f"[AGENT_TRACE] Turn {turn+1} LLM 决定直接回答，退出 ReAct 循环")
            break

        # 6. 流式生成最终答案
        # 注意：_stream_answer 返回的是 chat_streamly 的全量累积文本（每次 yield 都是完整 ans），
        # 因此用 answer = chunk（替换），而非 answer += chunk（拼接）。
        answer = ""

        for chunk in self._stream_answer(messages, retrieved_pages):
            answer = chunk
            yield {"answer": answer, "reference": EMPTY_REF}

        # 7. 构建最终响应（规范化引用标记 + 转换 MinIO URL）
        answer = self._normalize_references(answer)
        final = self._build_final_response(answer, retrieved_pages)
        # 最终存储的答案拼接 tool_call_log，前端通过 replaceToolCallToSection
        # 将其渲染为可折叠的工具调用历史（<details> 元素）
        stored_answer = (tool_call_log + "\n" + answer) if tool_call_log else answer
        yield {"answer": stored_answer, "reference": final.get("reference", EMPTY_REF)}

        elapsed = time.time() - start_time
        logger.info(f"ReAct Agent 完成，耗时 {elapsed:.2f}s，共调用 {len(executed_tools)} 次工具，检索 {len(retrieved_pages)} 页")

    # ── 内部方法 ──────────────────────────────────────────────

    @staticmethod
    def _log_messages(msgs: list[dict]) -> list[dict]:
        """将 messages 复制一份用于日志打印，截断图片 base64 和长文本。"""
        import copy
        result = []
        for m in msgs:
            mc = copy.deepcopy(m)
            content = mc.get("content")
            if isinstance(content, list):
                for part in content:
                    if part.get("type") == "image_url":
                        url = part.get("image_url", {}).get("url", "")
                        if len(url) > 50:
                            part["image_url"]["url"] = url[:50] + f"...<{len(url)-50} chars>"
            elif isinstance(content, str) and len(content) > 500:
                mc["content"] = content[:500] + f"...<{len(content)-500} chars>"
            result.append(mc)
        return result

    def _build_retrieval_context(self, pages: dict[str, dict]) -> str:
        """将检索到的页面构建为上下文文本"""
        if not pages:
            return ""
        page_list = list(pages.values())
        parts = ["## 已检索到的课件内容\n"]
        for i, p in enumerate(page_list, 1):
            doc = p.get("docnm_kwd", "未知文档")
            page_num = p.get("page_num_int", "?")
            content = p.get("full_content", "")
            score = p.get("rerank_score") or p.get("rrf_score") or p.get("similarity") or 0.0
            parts.append(
                f"[来源{i}] {doc} 第{page_num}页 (相关度:{score:.2f})\n{content}\n"
            )
        parts.append(f"\n共检索到 {len(page_list)} 个相关页面。如果内容足够，请直接回答；如果不够，可以继续检索。")
        return "\n".join(parts)

    def _stream_answer(self, messages: list[dict], retrieved_pages: dict[str, dict]) -> Generator[str, None, None]:
        """流式生成最终答案"""
        if retrieved_pages:
            context = self._build_retrieval_context(retrieved_pages)
            system = REACT_SYSTEM_PROMPT + "\n\n" + context + "\n\n请根据以上检索内容回答用户问题。引用来源时使用 ~~0== ~~1== 格式（对应上述[来源N]）。"
        else:
            system = REACT_SYSTEM_PROMPT + "\n\n当前未检索到相关内容，请基于你的知识回答。如果是知识性问题，请说明信息不足。"

        try:
            gen_conf = {"temperature": 0.3, "max_tokens": 2048}
            for chunk in self.chat_mdl.chat_streamly(system, messages, gen_conf):
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

    def _build_final_response(self, answer: str, retrieved_pages: dict[str, dict]) -> dict:
        """构建最终响应，包含引用信息"""
        pages = list(retrieved_pages.values())
        chunks = []
        for page in pages:
            page_id = page.get("page_id", "")
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
        for page in pages:
            doc_id = page.get("doc_id", "")
            if doc_id and doc_id not in doc_ids_seen:
                doc_ids_seen.add(doc_id)
                doc_aggs.append({
                    "doc_id": doc_id,
                    "doc_name": page.get("docnm_kwd", ""),
                    "count": sum(1 for p in pages if p.get("doc_id") == doc_id),
                })

        return {
            "answer": answer,
            "reference": {"total": len(chunks), "chunks": chunks, "doc_aggs": doc_aggs},
        }

    def _fetch_single_image(self, img_url: str) -> str:
        """从 MinIO 拉取单张图片并转为 base64 data URL。失败返回空字符串。"""
        if not img_url:
            return ""
        try:
            from api.db.services.dialog_service import get_image_base64_from_minio
        except ImportError:
            logger.warning("无法导入 get_image_base64_from_minio")
            return ""
        try:
            return get_image_base64_from_minio(img_url) or ""
        except Exception as e:
            logger.warning(f"图片获取异常 {img_url}: {e}")
            return ""

    def _inject_images_into_messages(self, messages: list[dict], new_images: list[str]) -> None:
        """将图片作为新的 user 消息追加到 messages 末尾（原地修改）。

        放在 tool 结果之后，LLM 看到的时间顺序正确：
        user(问题) → assistant(tool_call) → tool(结果) → user(截图) → ...
        """
        if not new_images:
            return

        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": "以下是从上述工具调用中获取的文档页面截图："},
                *[{"type": "image_url", "image_url": {"url": b64, "detail": "auto"}} for b64 in new_images],
            ],
        })
