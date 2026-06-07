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

    # 阈值常量
    MIN_CHUNKS_THRESHOLD: int = 2          # 最少需要多少个 chunk
    GOOD_TOP_SCORE: float = 0.8            # 高相关度阈值
    ACCEPTABLE_TOP_SCORE: float = 0.5      # 可接受的最低相似度
    LOW_DIVERSITY_THRESHOLD: float = 0.3   # 多样性低阈值

    def evaluate(self, retrieval_results: dict) -> RetrievalObservation:
        """
        评估检索结果质量。

        Args:
            retrieval_results: {"total": int, "chunks": [{"similarity": float, "doc_id": str, ...}]}

        Returns:
            RetrievalObservation
        """
        chunks = retrieval_results.get("chunks", [])
        total = len(chunks)

        if total == 0:
            return RetrievalObservation(
                total_chunks=0,
                is_sufficient=False,
                reason="未检索到任何相关页面",
                suggestion="尝试更换检索关键词或放宽检索条件",
            )

        # 计算指标
        top_score = self._get_top_score(chunks)
        diversity = self._compute_diversity(chunks)
        is_sufficient = self._judge_sufficiency(total, top_score, diversity)

        if not is_sufficient:
            if top_score < self.ACCEPTABLE_TOP_SCORE:
                suggestion = "检索结果相关性较低，建议更换检索词或使用 keyword_search 精确匹配"
            elif total < self.MIN_CHUNKS_THRESHOLD:
                suggestion = "检索结果数量不足，建议增加 top_k 或使用 hybrid_retrieve"
            elif diversity < self.LOW_DIVERSITY_THRESHOLD:
                suggestion = "检索结果多样性不足（可能来自同一文档），建议扩大多样性"
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
                f"共 {total} 个结果，最高分 {top_score:.3f}，"
                f"多样性 {diversity:.3f}，"
                f"{'满足' if is_sufficient else '不满足'}最低要求"
            ),
            suggestion=suggestion,
        )

    def _get_top_score(self, chunks: list[dict]) -> float:
        scores = []
        for c in chunks:
            s = c.get("rerank_score") or c.get("rrf_score") or c.get("similarity") or 0.0
            scores.append(float(s))
        return max(scores) if scores else 0.0

    def _compute_diversity(self, chunks: list[dict]) -> float:
        """
        计算文档来源多样性。
        返回唯一文档数 / 总结果数，范围 [0, 1]。
        """
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
