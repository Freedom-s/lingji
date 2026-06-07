"""
Planner: 基于 LLM function calling 的检索策略规划器。

分析用户问题，决定是否需要检索、使用哪些检索工具。
支持三种意图类型：CHAT（闲聊）、RETRIEVE（检索）、COMPARE（对比）。
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("ragflow.agent.planner")


class IntentType(str, Enum):
    CHAT = "chat"
    RETRIEVE = "retrieve"
    COMPARE = "compare"


@dataclass
class PlanStep:
    tool: str
    arguments: dict = field(default_factory=dict)


@dataclass
class Plan:
    intent: IntentType = IntentType.CHAT
    steps: list[PlanStep] = field(default_factory=list)
    reasoning: str = ""
    needs_retrieval: bool = False


PLANNER_SYSTEM_PROMPT = """
你是一个知识库检索规划助手。你的任务是分析用户的问题，决定是否需要从知识库中检索信息来回答。

你可以使用以下 MCP 工具：
- hybrid_retrieve: 一键混合检索（推荐优先使用），并行执行文本语义检索、图片语义检索和关键词检索，通过 RRF 融合后重排序返回最优结果。
- vector_search_text: 文本语义检索，基于自然语言描述的语义匹配。
- keyword_search: 关键词精确检索，基于 BM25 算法，适合专有名词、术语、数字等。
- get_adjacent_pages: 获取相邻页面，用于扩展上下文。
- rerank_pages: 对候选页面重排序。
- evaluate_page_relevance: 评估页面与问题的相关性。
- web_search: Tavily 联网搜索，获取互联网上的最新信息。适用于知识库未覆盖的时新话题、最新新闻等。

决策规则：
1. 如果用户只是打招呼、闲聊、询问你是谁、询问你的能力等通用对话 → INTENT: chat, needs_retrieval: false
2. 如果用户询问知识库中的具体内容、需要查找资料、询问课程相关内容 → INTENT: retrieve, needs_retrieval: true, 优先使用 hybrid_retrieve
3. 如果用户询问时新话题、最新新闻、知识库中明显没有的内容 → INTENT: retrieve, needs_retrieval: true, 使用 web_search
4. 如果用户要求对比多个概念、比较不同内容 → INTENT: compare, needs_retrieval: true, 可能多次检索

请以 JSON 格式回复：
{
  "intent": "chat|retrieve|compare",
  "reasoning": "你的判断理由",
  "needs_retrieval": true/false,
  "steps": [
    {"tool": "hybrid_retrieve", "arguments": {"query": "用户问题的精炼版本", "rerank_topk": 3}}
  ]
}
"""


class Planner:
    """检索策略规划器：使用 LLM function calling 决定是否及如何检索"""

    def __init__(self, chat_mdl):
        self.chat_mdl = chat_mdl
        self._tools: list[dict] = []

    def set_tools(self, tools: list[dict]):
        """设置可用的检索工具列表（OpenAI function calling 格式）"""
        self._tools = tools

    def plan(self, question: str, context: str = "") -> Plan:
        """
        分析用户问题，返回检索计划。

        Args:
            question: 用户当前问题
            context: 对话历史上下文

        Returns:
            Plan: 检索计划
        """
        if not self._tools:
            # 没有工具可用，默认进行一次 hybrid_retrieve
            return Plan(
                intent=IntentType.RETRIEVE,
                steps=[PlanStep(tool="hybrid_retrieve", arguments={"query": question, "rerank_topk": 3})],
                reasoning="无可用工具列表，默认检索",
                needs_retrieval=True,
            )

        context_message = self._build_context_message(question, context)

        try:
            result = self.chat_mdl.chat_with_tools(
                PLANNER_SYSTEM_PROMPT,
                [{"role": "user", "content": context_message}],
                {"tools": self._tools, "tool_choice": "auto", "temperature": 0.1},
            )
            return self._parse_plan(result, question)
        except Exception as e:
            logger.error(f"Planner LLM 调用失败: {e}")
            return self._default_plan(question)

    def _build_context_message(self, question: str, context: str) -> str:
        parts = ["请分析以下用户问题，制定合适的检索策略。\n"]
        if context:
            parts.append(f"对话历史摘要：\n{context}\n")
        parts.append(f"用户问题：{question}")
        return "\n".join(parts)

    def _parse_plan(self, result: dict | str, question: str) -> Plan:
        """解析 LLM function calling 的返回结果"""
        tool_calls = result.get("tool_calls") if isinstance(result, dict) else None

        if tool_calls:
            steps = []
            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "hybrid_retrieve")
                args = fn.get("arguments", "{}")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"query": question}
                if "query" not in args:
                    args["query"] = question
                steps.append(PlanStep(tool=name, arguments=args))

            return Plan(
                intent=IntentType.RETRIEVE,
                steps=steps,
                reasoning="LLM function calling 决策",
                needs_retrieval=True,
            )

        # 没有 tool_calls → 解读 content 判断意图
        content = result.get("content", "") if isinstance(result, dict) else str(result)
        content_lower = content.lower()

        # 尝试从 content 中提取 JSON
        try:
            # 可能 LLM 直接返回了 JSON 文本
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return self._from_json(parsed, question)
        except (json.JSONDecodeError, TypeError):
            pass

        if "needs_retrieval" in content_lower and "false" in content_lower:
            return Plan(intent=IntentType.CHAT, reasoning=content, needs_retrieval=False)
        if "chat" in content_lower and "retrieve" not in content_lower:
            return Plan(intent=IntentType.CHAT, reasoning=content, needs_retrieval=False)

        return self._default_plan(question)

    def _from_json(self, data: dict, question: str) -> Plan:
        intent_str = data.get("intent", "retrieve")
        try:
            intent = IntentType(intent_str)
        except ValueError:
            intent = IntentType.RETRIEVE

        steps = []
        for s in data.get("steps", []):
            args = s.get("arguments", {})
            if "query" not in args:
                args["query"] = question
            steps.append(PlanStep(tool=s.get("tool", "hybrid_retrieve"), arguments=args))

        return Plan(
            intent=intent,
            steps=steps,
            reasoning=data.get("reasoning", ""),
            needs_retrieval=data.get("needs_retrieval", True),
        )

    def _default_plan(self, question: str) -> Plan:
        """回退方案：始终使用混合检索"""
        return Plan(
            intent=IntentType.RETRIEVE,
            steps=[PlanStep(tool="hybrid_retrieve", arguments={"query": question, "rerank_topk": 3})],
            reasoning="默认检索（LLM 调用失败或未明确指定）",
            needs_retrieval=True,
        )
