"""
AgentLoop: ReAct 风格的 Agent 主循环。

流程:
    用户问题 → Planner 规划 → MCP 工具执行 → Observer 评估
    → 不满足则 Replan（最多 3 轮）→ Generator 流式生成答案

使用方式:
    agent = AgentLoop(mcp_url="http://127.0.0.1:9390", chat_mdl=chat_mdl)
    for event in agent.run(question="...", history=[...], kb_ids=[...], ...):
        yield event
"""

import json
import logging
import time
from typing import Any, Generator

from rag.agent.client.mcp_client import MCPClient
from rag.agent.client.planner import Planner, Plan, IntentType, PlanStep
from rag.agent.client.observer import Observer, RetrievalObservation
from rag.agent.client.memory import MemoryManager, Observation

logger = logging.getLogger("ragflow.agent.loop")


class AgentLoop:
    """ReAct Agent 主循环"""

    def __init__(
        self,
        mcp_url: str,
        chat_mdl,
        redis_conn=None,
        conversation_id: str = "",
        user_id: str = "",
        max_retrieval_turns: int = 3,
    ):
        self.mcp_client = MCPClient(base_url=mcp_url)
        self.chat_mdl = chat_mdl
        self.planner = Planner(chat_mdl)
        self.observer = Observer()
        self.memory = MemoryManager(
            redis_conn=redis_conn,
            conversation_id=conversation_id,
            user_id=user_id,
        )
        self.max_retrieval_turns = max_retrieval_turns

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
        执行 Agent Loop，流式返回答案。

        Yields:
            dict: {"answer": str, "reference": dict, "id": str, "session_id": str}
        """
        start_time = time.time()

        # 1. 初始化 MCP 上下文
        self.mcp_client.initialize(
            tenant_ids=tenant_ids,
            kb_ids=kb_ids,
            embd_id=embd_id,
            rerank_id=rerank_id,
        )

        # 2. 获取可用工具列表
        mcp_tools = self.mcp_client.list_tools()
        openai_tools = self.mcp_client.get_openai_tools(mcp_tools)
        self.planner.set_tools(openai_tools)

        # 3. 初始化记忆
        self.memory.init_working_memory(question)
        context = self.memory.load_full_context(history)

        # 4. 规划
        plan = self.planner.plan(question, context)
        logger.info(f"规划结果: intent={plan.intent.value}, needs_retrieval={plan.needs_retrieval}, reasoning={plan.reasoning}")

        retrieved_pages: list[dict] = []

        # 5. ReAct 循环
        if plan.needs_retrieval:
            for turn in range(self.max_retrieval_turns):
                self.memory.working.agent_state = "executing"
                logger.info(f"Agent Turn {turn + 1}/{self.max_retrieval_turns}")

                # 5a. 执行检索
                for step in plan.steps:
                    logger.info(f"  执行工具: {step.tool}")
                    result = self.mcp_client.call_tool(step.tool, step.arguments)
                    self.memory.working.add_turn_result(result)
                    self.memory.working.executed_tools.append(step.tool)

                # 5b. 观察评估
                self.memory.working.agent_state = "observing"
                latest_result = self.memory.working.turn_results[-1] if self.memory.working.turn_results else {}
                observation = self.observer.evaluate(latest_result)
                self.memory.working.add_observation(Observation(
                    total_chunks=observation.total_chunks,
                    top_score=observation.top_score,
                    is_sufficient=observation.is_sufficient,
                    reason=observation.reason,
                ))

                if observation.is_sufficient:
                    logger.info(f"  检索满足要求: {observation.reason}")
                    retrieved_pages = list(self.memory.working.retrieved_pages)
                    break
                else:
                    logger.info(f"  检索不满足: {observation.reason} → {observation.suggestion}")

                # 5c. Replan
                self.memory.working.agent_state = "planning"
                previous_summary = self.memory.working.get_retrieved_summary()
                replan = self._replan(question, previous_summary, observation)
                plan = replan

            # 循环结束后仍不满足，使用已有的页面
            if not retrieved_pages and self.memory.working.has_retrieved_pages():
                retrieved_pages = list(self.memory.working.retrieved_pages)

        # 6. 生成答案
        self.memory.working.agent_state = "generating"
        answer = ""
        for chunk in self._generate(question, history, retrieved_pages):
            answer = chunk  # chunk 是累积的完整答案
            yield {
                "answer": answer,
                "reference": {},
            }

        # 7. 构建最终响应
        final_response = self._build_final_response(answer, retrieved_pages)
        yield {
            "answer": answer,
            "reference": final_response.get("reference", {}),
        }

        # 8. 保存短期记忆
        elapsed = time.time() - start_time
        logger.info(f"Agent Loop 完成，耗时 {elapsed:.2f}s，检索 {len(retrieved_pages)} 页")

    # ── 内部方法 ──────────────────────────────────────────────

    def _replan(self, question: str, context: str, observation: RetrievalObservation) -> Plan:
        """根据观察结果重新规划检索策略"""
        current_turn = self.memory.working.current_turn
        executed = self.memory.working.executed_tools

        # 策略回退：hybrid → keyword（更精确）→ text vector（更语义化）
        if current_turn == 1:
            # 第二轮：尝试 keyword search
            logger.info("  Replan → keyword_search")
            return Plan(
                intent=IntentType.RETRIEVE,
                steps=[PlanStep(tool="keyword_search", arguments={"query": question, "top_k": 80})],
                reasoning=f"hybrid_retrieve 结果不足（{observation.reason}），回退到关键词精确检索",
                needs_retrieval=True,
            )

        if current_turn == 2:
            # 第三轮：尝试纯 vector search（更宽松）
            logger.info("  Replan → vector_search_text")
            return Plan(
                intent=IntentType.RETRIEVE,
                steps=[PlanStep(tool="vector_search_text", arguments={"query": question, "top_k": 100})],
                reasoning="多轮检索均不满足，放宽搜索范围尝试向量语义检索",
                needs_retrieval=True,
            )

        # 超限，放弃
        return Plan(
            intent=IntentType.CHAT,
            reasoning="已达最大检索轮次，使用已有结果生成答案",
            needs_retrieval=False,
        )

    def _generate(
        self,
        question: str,
        history: list[dict],
        retrieved_pages: list[dict],
    ) -> Generator[str, None, None]:
        """使用 VLM 流式生成答案（支持多模态：文本 + 图片 base64）"""
        # 构建上下文消息
        if retrieved_pages:
            # 构建 RAG 上下文
            pages_text = self.memory.working.to_context_string(max_pages=5)
            system = (
                "你是 RAGFlow 智能助教。请根据以下从课件中检索到的页面内容回答用户问题。\n"
                "回答要求：\n"
                "1. 基于检索内容作答，如有引用请标注来源（文档名 + 页码）\n"
                "2. 如果检索内容不足以回答，请诚实说明\n"
                "3. 回答应清晰、有条理，适合学生学习\n\n"
                f"【检索到的课件内容】\n{pages_text}"
            )
        else:
            system = (
                "你是 RAGFlow 智能助教。当前没有从课件中检索到相关内容，"
                "请基于你的知识回答用户问题。如果是知识性问题，请说明检索结果不足。"
            )

        # 构建历史消息（只取最近几条）
        recent_history = history[-6:] if history else []
        # 如果消息超过一定数量，压缩早期消息
        history_msgs = []
        for msg in recent_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant"):
                history_msgs.append({"role": role, "content": content})

        # 流式生成
        answer = ""
        try:
            gen_conf = {"temperature": 0.3, "max_tokens": 2048}
            for chunk in self.chat_mdl.chat_streamly(system, history_msgs, gen_conf):
                answer = chunk
                yield chunk
        except Exception as e:
            logger.error(f"生成答案失败: {e}")
            yield answer + f"\n\n*[生成失败: {e}]*"

    def _build_final_response(self, answer: str, retrieved_pages: list[dict]) -> dict:
        """构建最终响应，包含引用信息"""
        # 构建 chunks 引用
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
                "content": page.get("content_with_weight", "")[:300],
                "doc_id": page.get("doc_id", ""),
                "docnm_kwd": page.get("docnm_kwd", ""),
                "img_url": page.get("img_url", ""),
                "page_num_int": page.get("page_num_int", 0),
                "score": round(float(score), 4),
            })

        # 构建 doc_aggs 引用
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
            "reference": {
                "chunks": chunks,
                "doc_aggs": doc_aggs,
            },
        }
