"""
Observer: 检索质量评估器。

评估检索结果的质量（数量、最高分、多样性），
决定是否需要调整策略重新检索。
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("ragflow.agent.observer")


@dataclass
class RetrievalObservation:
    total_chunks: int = 0
    top_score: float = 0.0
    is_sufficient: bool = False
    has_diversity: bool = False
    reason: str = ""
    suggestion: str = ""


class Observer:
    """检索质量评估器"""

    MIN_CHUNKS_THRESHOLD: int = 1
    GOOD_TOP_SCORE: float = 0.7
    ACCEPTABLE_TOP_SCORE: float = 0.3
    LOW_DIVERSITY_THRESHOLD: float = 0.3
    # 累积总页数达到此值即视为足够，不再继续检索
    ACCUMULATED_PAGES_TARGET: int = 4

    def evaluate(self, retrieval_results: dict) -> RetrievalObservation:
        """评估单轮检索结果"""
        chunks = retrieval_results.get("chunks", [])
        total = len(chunks)

        if total == 0:
            return RetrievalObservation(
                total_chunks=0,
                is_sufficient=False,
                reason="未检索到任何相关页面",
                suggestion="尝试更换检索关键词或放宽搜索范围",
            )

        top_score = self._get_top_score(chunks)
        diversity = self._compute_diversity(chunks)
        is_sufficient = self._judge_sufficiency(total, top_score, diversity)

        if not is_sufficient:
            if top_score < self.ACCEPTABLE_TOP_SCORE:
                suggestion = "检索结果相关性较低，建议更换检索词或使用 keyword_search"
            elif diversity < self.LOW_DIVERSITY_THRESHOLD:
                suggestion = "结果来源单一，建议扩大多样性"
            else:
                suggestion = "检索结果不足，建议调整策略"
        else:
            suggestion = ""

        return RetrievalObservation(
            total_chunks=total,
            top_score=top_score,
            is_sufficient=is_sufficient,
            has_diversity=diversity >= self.LOW_DIVERSITY_THRESHOLD,
            reason=(
                f"本轮 {total} 个结果，最高分 {top_score:.3f}，"
                f"多样性 {diversity:.3f}，"
                f"{'满足' if is_sufficient else '不满足'}要求"
            ),
            suggestion=suggestion,
        )

    def evaluate_accumulated(self, all_pages: list[dict], current_turn: int) -> RetrievalObservation:
        """
        评估所有轮次累积的页面总数，判断是否满足最低要求。

        逻辑：如果累积页面数 ≥ ACCUMULATED_PAGES_TARGET，或已进行到最后一轮，
        则视为足够，停止继续检索。
        """
        total = len(all_pages)
        top_score = self._get_top_score(all_pages)
        diversity = self._compute_diversity(all_pages)

        if total >= self.ACCUMULATED_PAGES_TARGET:
            return RetrievalObservation(
                total_chunks=total,
                top_score=top_score,
                is_sufficient=True,
                has_diversity=diversity >= self.LOW_DIVERSITY_THRESHOLD,
                reason=f"已累积 {total} 个页面（≥{self.ACCUMULATED_PAGES_TARGET}），检索充分",
            )

        return RetrievalObservation(
            total_chunks=total,
            top_score=top_score,
            is_sufficient=False,
            has_diversity=diversity >= self.LOW_DIVERSITY_THRESHOLD,
            reason=f"已累积 {total} 个页面，尚不足 {self.ACCUMULATED_PAGES_TARGET}",
            suggestion="继续检索" if total > 0 else "开始检索",
        )

    def _get_top_score(self, chunks: list[dict]) -> float:
        scores = []
        for c in chunks:
            s = c.get("rerank_score") or c.get("rrf_score") or c.get("similarity") or 0.0
            scores.append(float(s))
        return max(scores) if scores else 0.0

    def _compute_diversity(self, chunks: list[dict]) -> float:
        if not chunks:
            return 0.0
        unique_docs = len(set(c.get("doc_id", "") for c in chunks))
        return unique_docs / len(chunks)

    def _judge_sufficiency(self, total: int, top_score: float, diversity: float) -> bool:
        if total < self.MIN_CHUNKS_THRESHOLD:
            return False
        if top_score < self.ACCEPTABLE_TOP_SCORE:
            return False
        return True
