"""Retrieval evaluation metrics: Recall@K, MRR, NDCG@K."""
import numpy as np


def _hit_rank(ground_truth: str, retrieved: list[str]) -> int | None:
    """Return 1-indexed rank of ground_truth in retrieved, or None if missed."""
    try:
        return retrieved.index(ground_truth) + 1
    except ValueError:
        return None


def recall_at_k(results: list[dict], k: int) -> float:
    """Compute Recall@K over a list of result dicts.

    Each dict must have:
        ground_truth_page_id: str
        retrieved_page_ids: list[str]
    """
    if not results:
        return 0.0
    hits = sum(
        1 for r in results
        if r["ground_truth_page_id"] in r["retrieved_page_ids"][:k]
    )
    return hits / len(results)


def mrr(results: list[dict]) -> float:
    """Compute Mean Reciprocal Rank.

    MRR = 1/|Q| * sum(1 / rank_of_first_hit)
    """
    if not results:
        return 0.0
    scores: list[float] = []
    for r in results:
        rank = _hit_rank(r["ground_truth_page_id"], r["retrieved_page_ids"])
        scores.append(1.0 / rank if rank else 0.0)
    return float(np.mean(scores))


def ndcg_at_k(results: list[dict], k: int) -> float:
    """Compute NDCG@K.

    DCG@K = sum_{i=1}^K (rel_i / log2(i+1))
    IDCG@K = DCG of perfect ranking (ground truth at position 1)
    NDCG = DCG / IDCG

    Relevance is 1 if ground_truth is at position i, 0 otherwise.
    """
    if not results:
        return 0.0
    ndcg_scores: list[float] = []
    for r in results:
        retrieved = r["retrieved_page_ids"][:k]
        gt = r["ground_truth_page_id"]

        # DCG
        dcg = 0.0
        for i, pid in enumerate(retrieved, start=1):
            if pid == gt:
                dcg = 1.0 / np.log2(i + 1)
                break

        # IDCG (perfect: gt at position 1)
        idcg = 1.0 / np.log2(2)  # 1 / log2(1+1) = 1.0

        ndcg_scores.append(dcg / idcg if idcg > 0 else 0.0)

    return float(np.mean(ndcg_scores))


def compute_all_metrics(results: list[dict]) -> dict[str, float]:
    """Compute all standard retrieval metrics.

    Args:
        results: List of dicts, each with:
            ground_truth_page_id: str
            retrieved_page_ids: list[str]

    Returns:
        dict with recall_1, recall_3, recall_5, mrr, ndcg_5
    """
    return {
        "recall_1": recall_at_k(results, 1),
        "recall_3": recall_at_k(results, 3),
        "recall_5": recall_at_k(results, 5),
        "mrr": mrr(results),
        "ndcg_5": ndcg_at_k(results, 5),
        "n_queries": len(results),
    }
