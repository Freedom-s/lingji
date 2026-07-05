"""Statistical tests for experiment analysis."""
from typing import Any

import numpy as np
from scipy import stats


def paired_ttest(scores_a: list[float], scores_b: list[float]) -> dict[str, Any]:
    """Paired t-test between two sets of per-query scores.

    Args:
        scores_a: Per-query metric values for method A.
        scores_b: Per-query metric values for method B.

    Returns:
        dict with t_stat, p_value, cohens_d, significant, mean_a, mean_b, delta
    """
    a = np.array(scores_a, dtype=np.float64)
    b = np.array(scores_b, dtype=np.float64)

    t_stat, p_value = stats.ttest_rel(a, b)

    # Cohen's d for paired samples
    diff = a - b
    d_denom = np.std(diff, ddof=1)
    cohens_d = float(np.mean(diff) / d_denom) if d_denom > 0 else 0.0

    return {
        "t_stat": float(t_stat),
        "p_value": float(p_value),
        "cohens_d": abs(cohens_d),
        "significant": p_value < 0.05,
        "mean_a": float(np.mean(a)),
        "mean_b": float(np.mean(b)),
        "delta": float(np.mean(diff)),
        "n": len(a),
    }


def bootstrap_ci(
    scores: list[float],
    alpha: float = 0.05,
    n_bootstrap: int = 10_000,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Bootstrap 95% confidence interval for a mean.

    Args:
        scores: The per-query metric values.
        alpha: Significance level (default 0.05 for 95% CI).
        n_bootstrap: Number of bootstrap resamples.
        seed: Random seed.

    Returns:
        (lower, mean, upper)
    """
    rng = np.random.default_rng(seed)
    arr = np.array(scores, dtype=np.float64)
    means: list[float] = []
    for _ in range(n_bootstrap):
        sample = rng.choice(arr, size=len(arr), replace=True)
        means.append(float(np.mean(sample)))

    lower = float(np.percentile(means, 100 * alpha / 2))
    upper = float(np.percentile(means, 100 * (1 - alpha / 2)))
    mean = float(np.mean(arr))
    return lower, mean, upper


def cohens_kappa(labels_a: list[str], labels_b: list[str]) -> float:
    """Cohen's Kappa for inter-rater agreement.

    Args:
        labels_a: First set of labels.
        labels_b: Second set of labels.

    Returns:
        Kappa value in [-1, 1].
    """
    if len(labels_a) != len(labels_b):
        raise ValueError("Label lists must have equal length")

    # Build confusion matrix
    categories = sorted(set(labels_a) | set(labels_b))
    n_cat = len(categories)
    cat_to_idx = {c: i for i, c in enumerate(categories)}

    matrix = np.zeros((n_cat, n_cat), dtype=np.int64)
    for a, b in zip(labels_a, labels_b):
        matrix[cat_to_idx[a], cat_to_idx[b]] += 1

    n = matrix.sum()
    if n == 0:
        return 0.0

    # Observed agreement
    p_o = np.trace(matrix) / n

    # Expected agreement
    row_sums = matrix.sum(axis=1)
    col_sums = matrix.sum(axis=0)
    p_e = float((row_sums @ col_sums) / (n * n))

    if p_e >= 1.0:
        return 1.0 if p_o >= 1.0 else 0.0

    return (p_o - p_e) / (1.0 - p_e)


def per_query_hit_scores(results: list[dict], k: int = 3) -> list[float]:
    """Extract per-query binary hit scores (1=hit, 0=miss) at rank k.

    Useful as input to paired_ttest for Recall@K comparison.
    """
    return [
        1.0 if r["ground_truth_page_id"] in r["retrieved_page_ids"][:k] else 0.0
        for r in results
    ]


def per_query_mrr_scores(results: list[dict]) -> list[float]:
    """Extract per-query reciprocal rank scores for t-test input."""
    scores: list[float] = []
    for r in results:
        try:
            rank = r["retrieved_page_ids"].index(r["ground_truth_page_id"]) + 1
            scores.append(1.0 / rank)
        except ValueError:
            scores.append(0.0)
    return scores
