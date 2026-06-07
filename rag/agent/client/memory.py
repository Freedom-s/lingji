"""
Memory System: 三层记忆架构

1. WorkingMemory  — 单次 Agent Loop 存活，存储检索页面和执行结果
2. ShortTermMemory — Redis 支持，会话级别（6 条最近消息，TTL 1 小时）
3. LongTermMemory  — MySQL 支持，永久存储用户偏好

MemoryManager 统一管理三个层级。
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("ragflow.agent.memory")

# ── 常量 ─────────────────────────────────────────────────────

MAX_RECENT_MESSAGES = 6
MAX_SHORT_TERM_TOKENS = 4096


# ── Observation ──────────────────────────────────────────────

@dataclass
class Observation:
    total_chunks: int = 0
    top_score: float = 0.0
    is_sufficient: bool = False
    reason: str = ""


# ── WorkingMemory ────────────────────────────────────────────

@dataclass
class WorkingMemory:
    """工作记忆：单次 Agent Loop 内有效"""

    user_question: str = ""
    retrieved_pages: list[dict] = field(default_factory=list)
    turn_results: list[dict] = field(default_factory=list)
    executed_tools: list[str] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)
    agent_state: str = "idle"  # idle | planning | executing | observing | generating
    current_turn: int = 0
    max_turns: int = 3
    _seen_page_ids: set = field(default_factory=set)

    def add_retrieved_pages(self, pages: list[dict]):
        for p in pages:
            pid = p.get("page_id", "")
            if pid and pid not in self._seen_page_ids:
                self._seen_page_ids.add(pid)
                self.retrieved_pages.append(p)

    def add_turn_result(self, result: dict):
        self.turn_results.append(result)
        pages = result.get("chunks", [])
        self.add_retrieved_pages(pages)

    def add_observation(self, obs: Observation):
        self.observations.append(obs)
        self.current_turn += 1

    def has_retrieved_pages(self) -> bool:
        return len(self.retrieved_pages) > 0

    def get_main_pages(self, top_k: int = 5) -> list[dict]:
        """获取排序后的主要页面"""
        sorted_pages = sorted(
            self.retrieved_pages,
            key=lambda p: p.get("rerank_score") or p.get("rrf_score") or p.get("similarity") or 0.0,
            reverse=True,
        )
        return sorted_pages[:top_k]

    def get_context_pages(self) -> list[dict]:
        return self.retrieved_pages

    def get_retrieved_summary(self) -> str:
        return (
            f"已检索 {len(self.retrieved_pages)} 个页面，"
            f"来自 {len(set(p.get('doc_id', '') for p in self.retrieved_pages))} 个文档"
        )

    def to_context_string(self, max_pages: int = 5) -> str:
        pages = self.get_main_pages(max_pages)
        parts = []
        for i, p in enumerate(pages, 1):
            doc_name = p.get("docnm_kwd", "未知文档")
            page_num = p.get("page_num_int", "?")
            content = p.get("content_with_weight", "")[:500]
            parts.append(
                f"[来源 {i}] {doc_name} 第 {page_num} 页\n{content}"
            )
        return "\n\n---\n\n".join(parts)

    def reset(self):
        self.user_question = ""
        self.retrieved_pages = []
        self.turn_results = []
        self.executed_tools = []
        self.observations = []
        self.agent_state = "idle"
        self.current_turn = 0
        self._seen_page_ids = set()


# ── ShortTermMemory ──────────────────────────────────────────

@dataclass
class ShortTermMemory:
    """短期记忆：Redis 支持，对话会话级别"""

    redis_conn: Any = None
    conversation_id: str = ""
    ttl: int = 3600

    def _key(self) -> str:
        return f"agent:short_term:{self.conversation_id}"

    def save_context(self, messages: list[dict]):
        """保存最近的对话消息"""
        if not self.redis_conn:
            return
        try:
            recent = messages[-MAX_RECENT_MESSAGES:]
            self.redis_conn.set(self._key(), json.dumps(recent, ensure_ascii=False), self.ttl)
        except Exception as e:
            logger.warning(f"ShortTermMemory save error: {e}")

    def load_context(self) -> list[dict]:
        """加载最近的对话消息"""
        if not self.redis_conn:
            return []
        try:
            data = self.redis_conn.get(self._key())
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"ShortTermMemory load error: {e}")
        return []

    def clear(self):
        if self.redis_conn:
            try:
                self.redis_conn.delete(self._key())
            except Exception:
                pass

    def get_token_estimate(self) -> int:
        """估算缓存消息的 token 数"""
        messages = self.load_context()
        total_chars = sum(len(m.get("content", "")) for m in messages)
        # 粗略估算：中文 1 char ≈ 1 token，英文 4 chars ≈ 1 token
        return total_chars


# ── LongTermMemory ───────────────────────────────────────────

@dataclass
class LongTermMemory:
    """长期记忆：MySQL 支持，永久存储"""

    user_id: str = ""

    def get_user_preferences(self) -> dict:
        """TODO: 从数据库读取用户偏好"""
        return {}

    def save_feedback(self, conversation_id: str, message_id: str, thumb_up: bool, feedback: str):
        """TODO: 保存用户反馈到数据库"""
        pass


# ── MemoryManager ────────────────────────────────────────────

@dataclass
class MemoryManager:
    """统一管理三层记忆"""

    working: WorkingMemory = field(default_factory=WorkingMemory)
    short_term: ShortTermMemory = field(default_factory=ShortTermMemory)
    long_term: LongTermMemory = field(default_factory=LongTermMemory)

    def __init__(self, redis_conn=None, conversation_id: str = "", user_id: str = ""):
        self.working = WorkingMemory()
        self.short_term = ShortTermMemory(redis_conn=redis_conn, conversation_id=conversation_id)
        self.long_term = LongTermMemory(user_id=user_id)

    def init_working_memory(self, question: str):
        self.working.reset()
        self.working.user_question = question
        self.working.agent_state = "planning"

    def load_full_context(self, history: list[dict]) -> str:
        """加载完整对话上下文（短期记忆 + 历史）"""
        short_term_context = self.short_term.load_context()
        all_history = short_term_context + history

        parts = []
        for msg in all_history[-MAX_RECENT_MESSAGES:]:
            role = msg.get("role", "")
            content = msg.get("content", "")
            role_label = "用户" if role == "user" else "助手"
            parts.append(f"{role_label}: {content[:200]}")

        return "\n".join(parts)

    def save_short_term(self, messages: list[dict]):
        self.short_term.save_context(messages)

    def clear(self):
        self.working.reset()
        self.short_term.clear()
