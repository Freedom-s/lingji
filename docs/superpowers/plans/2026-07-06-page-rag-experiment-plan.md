# Page-Level Multimodal RAG Experiment Framework — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an `experiments/` module that runs retrieval ablation (G1-G9), Workflow vs Agentic comparison, and stratified analysis against a 500-query test set, producing LaTeX tables and matplotlib charts.

**Architecture:** Each experiment variant is a configurable `VariantRunner` that delegates to `MCPToolExecutor`'s existing retrieval methods. Workflow mode calls `Dealer.hybrid_page_retrieval()` directly. Agentic mode wraps `AgentLoop.run()` with data-collection hooks. Metrics and stats are pure functions operating on result dicts. A single `run_all_experiments.py` entry point orchestrates everything.

**Tech Stack:** Python 3.10+, scipy, numpy, matplotlib, the existing `rag.nlp.search.Dealer`, `rag.agent.server.tools.MCPToolExecutor`, `rag.agent.client.loop.AgentLoop`.

## Global Constraints

- All code lives under `experiments/` — zero modifications to existing production code
- `VariantRunner` reuses `MCPToolExecutor._tool_*` methods directly, not copy-pasting retrieval logic
- Result JSONL files are the canonical output; report generation reads them, never re-runs experiments
- All file paths are absolute or relative to the project root
- Python type hints on all public functions
- `scipy.stats` for t-tests, `numpy` for array ops, `matplotlib` for charts

---

### Task 1: Create `experiments/` package scaffold and `config.py`

**Files:**
- Create: `experiments/__init__.py`
- Create: `experiments/config.py`

**Interfaces:**
- Produces: `VariantConfig` dataclass, `VARIANTS` dict, `EXPERIMENT_DEFAULTS` dict

- [ ] **Step 1: Create `experiments/__init__.py`**

```python
"""Experiments module for page-level multimodal RAG evaluation."""
```

- [ ] **Step 2: Create `experiments/config.py`**

```python
"""Experiment configuration: variant definitions and default parameters."""
from dataclasses import dataclass, field


@dataclass
class VariantConfig:
    """Configuration for one retrieval variant (G1-G9)."""
    name: str
    use_text_vector: bool
    use_image_vector: bool
    use_bm25: bool
    use_rrf: bool
    use_rerank: bool
    use_context_recall: bool
    per_retrieval_topk: int = 50
    rrf_k: int = 60
    rrf_topk: int = 5
    rerank_topk: int = 3
    rerank_similarity_threshold: float = 0.7
    context_recall_max_pages: int = 1
    final_topk: int = 3


VARIANTS: dict[str, VariantConfig] = {
    "G1": VariantConfig("仅文本向量",
                        use_text_vector=True, use_image_vector=False, use_bm25=False,
                        use_rrf=False, use_rerank=False, use_context_recall=False,
                        final_topk=5),
    "G2": VariantConfig("仅图片向量",
                        use_text_vector=False, use_image_vector=True, use_bm25=False,
                        use_rrf=False, use_rerank=False, use_context_recall=False,
                        final_topk=5),
    "G3": VariantConfig("仅BM25",
                        use_text_vector=False, use_image_vector=False, use_bm25=True,
                        use_rrf=False, use_rerank=False, use_context_recall=False,
                        final_topk=5),
    "G4": VariantConfig("图片+文本",
                        use_text_vector=True, use_image_vector=True, use_bm25=False,
                        use_rrf=True, use_rerank=True, use_context_recall=False,
                        final_topk=3),
    "G5": VariantConfig("图片+BM25",
                        use_text_vector=False, use_image_vector=True, use_bm25=True,
                        use_rrf=True, use_rerank=True, use_context_recall=False,
                        final_topk=3),
    "G6": VariantConfig("三路-无RRF",
                        use_text_vector=True, use_image_vector=True, use_bm25=True,
                        use_rrf=False, use_rerank=True, use_context_recall=False,
                        final_topk=5),
    "G7": VariantConfig("三路-无Rerank",
                        use_text_vector=True, use_image_vector=True, use_bm25=True,
                        use_rrf=True, use_rerank=False, use_context_recall=False,
                        final_topk=3),
    "G8": VariantConfig("三路-无上下文",
                        use_text_vector=True, use_image_vector=True, use_bm25=True,
                        use_rrf=True, use_rerank=True, use_context_recall=False,
                        final_topk=3),
    "G9": VariantConfig("PAGE-RAG完整",
                        use_text_vector=True, use_image_vector=True, use_bm25=True,
                        use_rrf=True, use_rerank=True, use_context_recall=True,
                        final_topk=3),
}

EXPERIMENT_DEFAULTS = {
    "rrf_k": 60,
    "rrf_topk": 5,
    "rerank_topk": 3,
    "rerank_similarity_threshold": 0.7,
    "per_retrieval_topk": 50,
    "context_recall_max_pages": 1,
    "agentic_max_turns": 10,
    "agentic_max_images": 5,
}
```

- [ ] **Step 3: Verify the module imports cleanly**

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2 && python -c "from experiments.config import VARIANTS, VariantConfig; print(list(VARIANTS.keys()))"
```

Expected: `['G1', 'G2', 'G3', 'G4', 'G5', 'G6', 'G7', 'G8', 'G9']`

- [ ] **Step 4: Commit**

```bash
git add experiments/__init__.py experiments/config.py
git commit -m "feat: add experiments package scaffold and variant config

Defines VariantConfig dataclass and 9 ablation variants (G1-G9).
G1-G3: single-path retrieval, G4-G5: two-path hybrids,
G6-G8: three-path with one component removed, G9: full PAGE-RAG.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Create `test_set_loader.py`

**Files:**
- Create: `experiments/test_set_loader.py`

**Interfaces:**
- Produces: `load_test_set(path: str) -> list[dict]`, `save_test_set(queries: list[dict], path: str) -> None`, `clean_queries(queries: list[dict]) -> tuple[list[dict], dict]`, `stratified_sample(queries: list[dict], n: int) -> list[dict]`

- [ ] **Step 1: Create `experiments/test_set_loader.py`**

```python
"""Load, clean, and sample test queries for retrieval experiments."""
import json
import hashlib
import logging
from collections import Counter
from typing import Any

import numpy as np

logger = logging.getLogger("experiments.test_set_loader")


def load_test_set(path: str) -> list[dict]:
    """Load test queries from a JSONL file.

    Each line: {"id": str, "query": str, "page_id": str, "doc_id": str,
                 "doc_name": str, "course": str, "source_kb_id": str}
    """
    queries: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            queries.append(json.loads(line))
    logger.info(f"Loaded {len(queries)} queries from {path}")
    return queries


def save_test_set(queries: list[dict], path: str) -> None:
    """Save queries to a JSONL file."""
    with open(path, "w", encoding="utf-8") as f:
        for q in queries:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")
    logger.info(f"Saved {len(queries)} queries to {path}")


def _query_hash(query: str) -> str:
    """Normalize and hash a query for dedup."""
    normalized = "".join(query.lower().split())
    return hashlib.md5(normalized.encode()).hexdigest()


VAGUE_PATTERNS = [
    "这一页讲了什么", "介绍这一页", "如图", "这张图",
    "这个页面", "那页", "上面说的", "以下内容", "看这张", "看图",
    "这个ppt", "这页ppt", "该页", "本页", "此页",
    "这里讲了", "上图中", "下图中", "根据这张", "根据这页",
]


def clean_queries(
    queries: list[dict],
    min_len: int = 5,
    max_len: int = 200,
) -> tuple[list[dict], dict]:
    """Clean a list of query dicts: dedup, length-filter, vague-filter.

    Returns (cleaned_queries, report).
    """
    report: dict[str, int] = {"original": len(queries)}
    cleaned = list(queries)

    # 1. Exact dedup by query string
    seen_texts: set[str] = set()
    deduped: list[dict] = []
    for q in cleaned:
        text = q.get("query", "").strip()
        if text not in seen_texts:
            seen_texts.add(text)
            deduped.append(q)
    report["after_exact_dedup"] = len(deduped)
    cleaned = deduped

    # 2. Near-dedup by normalized hash
    seen_hashes: set[str] = set()
    deduped = []
    for q in cleaned:
        h = _query_hash(q.get("query", ""))
        if h not in seen_hashes:
            seen_hashes.add(h)
            deduped.append(q)
    report["after_semantic_dedup"] = len(deduped)
    cleaned = deduped

    # 3. Length filter
    cleaned = [
        q for q in cleaned
        if min_len <= len(q.get("query", "").strip()) <= max_len
    ]
    report["after_length_filter"] = len(cleaned)

    # 4. Vague query filter
    cleaned = [
        q for q in cleaned
        if not any(p in q.get("query", "") for p in VAGUE_PATTERNS)
    ]
    report["after_vague_filter"] = len(cleaned)

    logger.info(f"Query cleaning: {report}")
    return cleaned, report


def stratified_sample(
    queries: list[dict],
    n: int,
    course_key: str = "course",
    doc_key: str = "doc_id",
    min_per_doc: int = 5,
    seed: int = 42,
) -> list[dict]:
    """Stratified sample across courses and documents.

    Args:
        queries: List of query dicts.
        n: Target total sample size.
        course_key: Key for course grouping.
        doc_key: Key for document grouping.
        min_per_doc: Minimum queries per document.
        seed: Random seed.

    Returns:
        Sampled queries.
    """
    rng = np.random.default_rng(seed)

    # Group by course
    courses: dict[str, list[dict]] = {}
    for q in queries:
        course = q.get(course_key, "unknown")
        courses.setdefault(course, []).append(q)

    # Allocate n proportionally across courses
    n_courses = len(courses)
    per_course = max(n // n_courses, 20)

    sampled: list[dict] = []
    sampled_ids: set[str] = set()

    for course, cqs in courses.items():
        # Within each course, group by doc
        docs: dict[str, list[dict]] = {}
        for q in cqs:
            docs.setdefault(q.get(doc_key, "unknown"), []).append(q)

        # Allocate per-course budget across docs
        n_docs = len(docs)
        per_doc_budget = max(per_course // n_docs, min_per_doc)

        course_sample: list[dict] = []
        for doc, dqs in docs.items():
            n_take = min(per_doc_budget, len(dqs))
            chosen = rng.choice(dqs, size=n_take, replace=False)
            course_sample.extend(chosen)

        # If we have more budget, fill up
        remaining_slots = per_course - len(course_sample)
        if remaining_slots > 0:
            not_sampled = [q for q in cqs if q.get("id") not in {s.get("id") for s in course_sample}]
            if not_sampled:
                extra_n = min(remaining_slots, len(not_sampled))
                course_sample.extend(rng.choice(not_sampled, size=extra_n, replace=False))

        for q in course_sample:
            if q.get("id") not in sampled_ids:
                sampled_ids.add(q.get("id"))
                sampled.append(q)

    # Trim to exact n if over
    if len(sampled) > n:
        sampled = list(rng.choice(sampled, size=n, replace=False))

    logger.info(
        f"Stratified sampling: {len(queries)} → {len(sampled)}, "
        f"courses={n_courses}"
    )
    return sampled
```

- [ ] **Step 2: Verify the module imports**

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2 && python -c "from experiments.test_set_loader import load_test_set, clean_queries, stratified_sample; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add experiments/test_set_loader.py
git commit -m "feat: add test set loader with cleaning and sampling

Supports JSONL loading, 4-stage cleaning (exact dedup, semantic
dedup, length filter, vague filter), and stratified sampling across
courses and documents.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Create `metrics.py`

**Files:**
- Create: `experiments/metrics.py`

**Interfaces:**
- Produces: `recall_at_k(results: list[dict], k: int) -> float`, `mrr(results: list[dict]) -> float`, `ndcg_at_k(results: list[dict], k: int) -> float`, `compute_all_metrics(results: list[dict]) -> dict`

- [ ] **Step 1: Create `experiments/metrics.py`**

```python
"""Retrieval evaluation metrics: Recall@K, MRR, NDCG@K."""
from typing import Any

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
```

- [ ] **Step 2: Write and run a quick smoke test**

```python
# Run inline: python -c "
from experiments.metrics import recall_at_k, mrr, ndcg_at_k, compute_all_metrics

results = [
    {'ground_truth_page_id': 'a', 'retrieved_page_ids': ['a', 'b', 'c']},
    {'ground_truth_page_id': 'd', 'retrieved_page_ids': ['a', 'b', 'd']},
    {'ground_truth_page_id': 'x', 'retrieved_page_ids': ['a', 'b', 'c']},
]
print('R@1:', recall_at_k(results, 1))
print('R@3:', recall_at_k(results, 3))
print('MRR:', mrr(results))
print('NDCG@3:', ndcg_at_k(results, 3))
print('All:', compute_all_metrics(results))
"
```

Expected: `R@1: 0.3333...`, `R@3: 0.6666...`, `MRR: 0.5`, `NDCG@3` around 0.63

- [ ] **Step 3: Commit**

```bash
git add experiments/metrics.py
git commit -m "feat: add retrieval metrics (Recall@K, MRR, NDCG@K)

Pure functions operating on result dicts with ground_truth_page_id
and retrieved_page_ids fields.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Create `statistical_tests.py`

**Files:**
- Create: `experiments/statistical_tests.py`

**Interfaces:**
- Produces: `paired_ttest(scores_a: list[float], scores_b: list[float]) -> dict`, `bootstrap_ci(scores: list[float], alpha: float, n_bootstrap: int) -> tuple[float, float]`, `cohens_kappa(labels_a: list[str], labels_b: list[str]) -> float`

- [ ] **Step 1: Create `experiments/statistical_tests.py`**

```python
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
```

- [ ] **Step 2: Run a quick smoke test**

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2 && python -c "
from experiments.statistical_tests import paired_ttest, bootstrap_ci, cohens_kappa
# t-test
r = paired_ttest([1,1,0,1,0], [0,1,0,0,0])
print(f't-test: t={r[\"t_stat\"]:.3f}, p={r[\"p_value\"]:.3f}, d={r[\"cohens_d\"]:.3f}')
# bootstrap
lo, mu, hi = bootstrap_ci([1,1,0,1,0,0,1,1,1,0])
print(f'CI: [{lo:.3f}, {mu:.3f}, {hi:.3f}]')
# kappa
k = cohens_kappa(['a','a','b','c','a'], ['a','a','b','b','a'])
print(f'Kappa: {k:.3f}')
print('OK')
"
```

Expected: t-test shows significant, CI bounds reasonable, Kappa around 0.5-0.7

- [ ] **Step 3: Commit**

```bash
git add experiments/statistical_tests.py
git commit -m "feat: add statistical tests for experiment analysis

Includes paired t-test with Cohen's d, bootstrap CI, Cohen's Kappa,
and per-query score extraction helpers.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Create `variant_runner.py`

**Files:**
- Create: `experiments/variant_runner.py`

**Interfaces:**
- Consumes: `VariantConfig` from `experiments.config`, `MCPToolExecutor` from `rag.agent.server.tools`
- Produces: `class VariantRunner` with `retrieve(query, tenant_ids, kb_ids) -> list[dict]`

- [ ] **Step 1: Create `experiments/variant_runner.py`**

```python
"""Configurable retrieval variant runner that delegates to MCPToolExecutor."""
import logging
from typing import Any

from experiments.config import VariantConfig

logger = logging.getLogger("experiments.variant_runner")


class VariantRunner:
    """Run a single retrieval variant (G1-G9) against the test set.

    Delegates all actual retrieval work to MCPToolExecutor's internal
    methods. The variant config controls which methods are called and in
    what combination.

    Usage:
        from rag.agent.server.tools import MCPToolExecutor
        from rag.nlp.search import Dealer
        from rag.utils.es_conn import ESConnection

        dealer = Dealer(ESConnection())
        executor = MCPToolExecutor(dealer=dealer, embd_mdl=embd_mdl,
                                    rerank_mdl=rerank_mdl)
        runner = VariantRunner(VARIANTS["G9"], executor)
        pages = runner.retrieve("什么是卷积神经网络?", tenant_ids, kb_ids)
    """

    def __init__(self, config: VariantConfig, executor: Any):
        """
        Args:
            config: VariantConfig controlling which components to enable.
            executor: MCPToolExecutor instance with embd_mdl and rerank_mdl set.
        """
        self.config = config
        self.executor = executor

    def retrieve(
        self,
        query: str,
        tenant_ids: list[str],
        kb_ids: list[str],
    ) -> list[dict]:
        """Run the variant's retrieval pipeline.

        Args:
            query: User question text.
            tenant_ids: ES index tenant IDs (determines which indices to search).
            kb_ids: Knowledge base IDs (filter within indices).

        Returns:
            List of page dicts, each with keys: page_id, doc_id, docnm_kwd,
            kb_id, page_num_int, img_url, full_content, similarity/rrf_score/
            rerank_score.
        """
        cfg = self.config
        results: list[dict] = []

        # ── Step 1: Parallel retrieval paths ──
        result_sets: dict[str, dict] = {}

        if cfg.use_image_vector:
            result_sets["image"] = self.executor._tool_vector_search_image(
                query, cfg.per_retrieval_topk, tenant_ids, kb_ids,
            )
        if cfg.use_text_vector:
            result_sets["text"] = self.executor._tool_vector_search_text(
                query, cfg.per_retrieval_topk, tenant_ids, kb_ids,
            )
        if cfg.use_bm25:
            result_sets["keyword"] = self.executor._tool_keyword_search(
                query, cfg.per_retrieval_topk, tenant_ids, kb_ids,
            )

        # ── Step 2: Merge ──
        enabled = [k for k in ["image", "text", "keyword"] if k in result_sets]
        active_results = [result_sets[k] for k in enabled]

        if len(active_results) == 0:
            return []
        elif len(active_results) == 1:
            merged = active_results[0]
        else:
            if cfg.use_rrf:
                merged = self.executor._tool_rrf_fusion(
                    active_results, rrf_k=cfg.rrf_k, top_k=cfg.rrf_topk,
                )
            else:
                merged = self._simple_concat(active_results, top_k=cfg.final_topk)

        candidates = merged.get("chunks", [])

        # ── Step 3: Rerank ──
        if cfg.use_rerank and self.executor.rerank_mdl and candidates:
            reranked = self.executor._tool_rerank_pages(
                query, candidates,
                top_k=cfg.rerank_topk,
                similarity_threshold=cfg.rerank_similarity_threshold,
            )
            candidates = reranked.get("chunks", [])

        # Truncate to final_topk
        candidates = candidates[:cfg.final_topk]

        # ── Step 4: Context recall (adjacent pages) ──
        if cfg.use_context_recall and candidates:
            candidates = self._add_context_pages(candidates, tenant_ids, kb_ids)

        return candidates

    def _simple_concat(self, result_sets: list[dict], top_k: int = 5) -> dict:
        """Simple concatenation fusion (no RRF): take top from each, deduplicate."""
        seen: set[str] = set()
        chunks: list[dict] = []
        for rs in result_sets:
            for chunk in rs.get("chunks", []):
                pid = chunk.get("page_id", "")
                if pid and pid not in seen:
                    seen.add(pid)
                    chunks.append(dict(chunk))
                if len(chunks) >= top_k:
                    break
            if len(chunks) >= top_k:
                break
        return {"total": len(chunks), "chunks": chunks[:top_k]}

    def _add_context_pages(
        self,
        main_pages: list[dict],
        tenant_ids: list[str],
        kb_ids: list[str],
    ) -> list[dict]:
        """Add adjacent pages for each main page (context recall).

        Context pages are marked with is_context=True so consumers can
        distinguish them from direct retrieval results.
        """
        result: list[dict] = []
        seen: set[str] = set()

        for page in main_pages:
            pid = page.get("page_id", "")
            if pid not in seen:
                seen.add(pid)
                page_copy = dict(page)
                page_copy["is_context"] = False
                result.append(page_copy)

            doc_id = page.get("doc_id", "")
            page_num = page.get("page_num_int", 0)
            if not doc_id or not page_num:
                continue

            max_pages = self.config.context_recall_max_pages
            adj = self.executor._tool_get_adjacent_pages(
                doc_id=doc_id,
                page_num=page_num,
                direction="both",
                offset=max_pages,
                tenant_ids=tenant_ids,
                kb_ids=kb_ids,
            )
            for adj_page in adj.get("chunks", []):
                adj_pid = adj_page.get("page_id", "")
                if adj_pid and adj_pid not in seen:
                    seen.add(adj_pid)
                    adj_copy = dict(adj_page)
                    adj_copy["is_context"] = True
                    result.append(adj_copy)

        return result
```

- [ ] **Step 2: Verify the module imports and the class is instantiable**

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2 && python -c "
from experiments.config import VARIANTS
from experiments.variant_runner import VariantRunner
print(f'VariantRunner defined: {VariantRunner}')
print(f'G9 config: {VARIANTS[\"G9\"]}')
print('OK')
"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add experiments/variant_runner.py
git commit -m "feat: add configurable variant runner for G1-G9 ablation

VariantRunner delegates to MCPToolExecutor._tool_* methods.
Config controls which retrieval paths, fusion, rerank, and context
recall to enable. Simple concat fallback for non-RRF variants.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: Create `workflow_runner.py`

**Files:**
- Create: `experiments/workflow_runner.py`

**Interfaces:**
- Consumes: `Dealer.hybrid_page_retrieval` from `rag.nlp.search`
- Produces: `run_workflow_experiment(test_queries, dealer, embd_mdl, rerank_mdl, chat_mdl) -> list[dict]`

- [ ] **Step 1: Create `experiments/workflow_runner.py`**

```python
"""Run Workflow-mode retrieval experiment.

Calls Dealer.hybrid_page_retrieval() directly, matching the production
chat() function's retrieval path exactly.
"""
import logging
import time
from typing import Any

logger = logging.getLogger("experiments.workflow_runner")


def run_workflow_experiment(
    test_queries: list[dict],
    dealer: Any,
    embd_mdl: Any,
    kb_ids: list[str],
    tenant_ids: list[str],
    rerank_mdl: Any = None,
    chat_mdl: Any = None,
    image_topk: int = 50,
    text_topk: int = 50,
    keyword_topk: int = 50,
    rrf_k: int = 60,
    rrf_topk: int = 5,
    rerank_final_topk: int = 3,
    similarity_threshold: float = 0.7,
    enable_context_recall: bool = True,
    context_recall_max_pages: int = 1,
) -> list[dict]:
    """Run Workflow-mode retrieval against the full test set.

    Each query is processed through dealer.hybrid_page_retrieval() with
    the exact same parameters as the production chat() function.

    Args:
        test_queries: List of query dicts from test_set_loader.
        dealer: rag.nlp.search.Dealer instance.
        embd_mdl: Embedding model from LLMBundle.
        kb_ids: Knowledge base IDs.
        tenant_ids: Tenant IDs (ES indices).
        rerank_mdl: Rerank model (optional).
        chat_mdl: Chat model for context recall evaluation (optional).
        image_topk..context_recall_max_pages: Retrieval parameters.

    Returns:
        List of result dicts, each with:
            query_id, query, ground_truth_page_id,
            retrieved_page_ids, hit_at_rank,
            recall_1, recall_3, recall_5, mrr_contrib,
            elapsed_ms
    """
    results: list[dict] = []
    n = len(test_queries)

    for i, q in enumerate(test_queries):
        query_text = q["query"]
        gt_page_id = q["page_id"]

        t0 = time.perf_counter()
        try:
            retrieval_result = dealer.hybrid_page_retrieval(
                question=query_text,
                embd_mdl=embd_mdl,
                tenant_ids=tenant_ids,
                kb_ids=kb_ids,
                rerank_mdl=rerank_mdl,
                chat_mdl=chat_mdl,
                image_topk=image_topk,
                text_topk=text_topk,
                keyword_topk=keyword_topk,
                rrf_k=rrf_k,
                rrf_topk=rrf_topk,
                rerank_final_topk=rerank_final_topk,
                similarity_threshold=similarity_threshold,
                enable_context_recall=enable_context_recall,
                context_recall_max_pages=context_recall_max_pages,
            )
            chunks = retrieval_result.get("chunks", [])
            retrieved_page_ids = [c.get("page_id", "") for c in chunks]
        except Exception as e:
            logger.error(f"Workflow retrieval error for query {q.get('id')}: {e}")
            retrieved_page_ids = []

        elapsed_ms = (time.perf_counter() - t0) * 1000

        hit_rank = None
        try:
            hit_rank = retrieved_page_ids.index(gt_page_id) + 1
        except ValueError:
            pass

        result = {
            "mode": "workflow",
            "query_id": q.get("id", f"q{i}"),
            "query": query_text,
            "ground_truth_page_id": gt_page_id,
            "retrieved_page_ids": retrieved_page_ids,
            "hit_at_rank": hit_rank,
            "recall_1": hit_rank == 1 if hit_rank else False,
            "recall_3": (hit_rank is not None and hit_rank <= 3),
            "recall_5": (hit_rank is not None and hit_rank <= 5),
            "mrr_contrib": 1.0 / hit_rank if hit_rank else 0.0,
            "elapsed_ms": round(elapsed_ms, 1),
        }
        results.append(result)

        if (i + 1) % 50 == 0:
            logger.info(f"Workflow: processed {i + 1}/{n} queries")

    n_hits = sum(1 for r in results if r["recall_3"])
    logger.info(f"Workflow complete: {n_hits}/{n} Recall@3 hits ({n_hits/n:.1%})")
    return results
```

- [ ] **Step 2: Ensure the module imports cleanly**

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2 && python -c "from experiments.workflow_runner import run_workflow_experiment; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add experiments/workflow_runner.py
git commit -m "feat: add workflow-mode experiment runner

Calls Dealer.hybrid_page_retrieval() per query with production params.
Records per-query hit metrics and elapsed time.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: Create `agentic_runner.py`

**Files:**
- Create: `experiments/agentic_runner.py`

**Interfaces:**
- Consumes: `AgentLoop` from `rag.agent.client.loop`, `chat_mdl` from `LLMBundle`, `structure_answer` from `api.apps.conversation_app`
- Produces: `run_agentic_experiment(test_queries, agent_loop_kwargs) -> list[dict]`

- [ ] **Step 1: Create `experiments/agentic_runner.py`**

```python
"""Run Agentic-mode retrieval experiment.

Uses AgentLoop.run() with data-collection hooks. Captures per-turn
tool calls, retrieved pages, and final answer for analysis.
"""
import json
import logging
import time
from typing import Any

logger = logging.getLogger("experiments.agentic_runner")


def run_agentic_experiment(
    test_queries: list[dict],
    mcp_url: str,
    chat_mdl: Any,
    kb_ids: list[str],
    tenant_ids: list[str],
    dialog: Any,
    embd_id: str | None = None,
    rerank_id: str | None = None,
    max_turns: int = 10,
    max_images: int = 5,
) -> list[dict]:
    """Run Agentic-mode retrieval against the full test set.

    For each query, creates a fresh AgentLoop and collects:
    - All tool calls (name, args, result summary) per turn
    - Pages retrieved per turn
    - Final answer and reference
    - Elapsed time

    Args:
        test_queries: List of query dicts.
        mcp_url: MCP server URL (e.g. http://localhost:9390).
        chat_mdl: Chat LLM from LLMBundle.
        kb_ids: Knowledge base IDs.
        tenant_ids: Tenant IDs.
        dialog: Dialog model object (for AgentLoop context).
        embd_id: Embedding model ID.
        rerank_id: Rerank model ID.
        max_turns: Max ReAct loop iterations.
        max_images: Max images injected into final VLM call.

    Returns:
        List of result dicts with agentic-specific metadata.
    """
    from rag.agent.client.loop import AgentLoop

    results: list[dict] = []
    n = len(test_queries)

    for i, q in enumerate(test_queries):
        query_text = q["query"]
        gt_page_id = q["page_id"]

        agent = AgentLoop(mcp_url=mcp_url, chat_mdl=chat_mdl)
        # Override max_tool_calls for experiment
        agent.max_tool_calls = max_turns

        # Collect events from agent.run()
        events: list[dict] = []
        all_retrieved_pages: list[dict] = []
        seen_page_ids: set[str] = set()
        tool_calls_log: list[dict] = []
        turns: int = 0

        t0 = time.perf_counter()
        try:
            for event in agent.run(
                question=query_text,
                history=[],  # Single-turn retrieval; no conversation history
                kb_ids=kb_ids,
                tenant_ids=tenant_ids,
                dialog=dialog,
                embd_id=embd_id,
                rerank_id=rerank_id,
                max_images=max_images,
            ):
                events.append(event)

                # Track retrieved pages from reference
                ref = event.get("reference", {})
                chunks = ref.get("chunks", []) if isinstance(ref, dict) else []
                for chunk in chunks:
                    pid = chunk.get("page_id", "")
                    if pid and pid not in seen_page_ids:
                        seen_page_ids.add(pid)
                        all_retrieved_pages.append(chunk)

                # Count tool calls from answer text
                answer = event.get("answer", "")
                if isinstance(answer, str) and "<tool_call" in answer:
                    turns = answer.count("<tool_call")
        except Exception as e:
            logger.error(f"Agentic error for query {q.get('id')}: {e}")

        elapsed_ms = (time.perf_counter() - t0) * 1000

        # Get final result from last substantive event
        final_event = events[-1] if events else {}
        final_answer = final_event.get("answer", "")
        final_ref = final_event.get("reference", {})

        # Determine hit
        retrieved_page_ids = [p.get("page_id", "") for p in all_retrieved_pages]
        hit_rank = None
        try:
            hit_rank = retrieved_page_ids.index(gt_page_id) + 1
        except ValueError:
            pass

        # Parse tool calls
        parsed_tool_calls = _parse_tool_calls_from_text(
            final_answer if isinstance(final_answer, str) else ""
        )

        result = {
            "mode": "agentic",
            "query_id": q.get("id", f"q{i}"),
            "query": query_text,
            "ground_truth_page_id": gt_page_id,
            "retrieved_page_ids": retrieved_page_ids,
            "hit_at_rank": hit_rank,
            "recall_1": hit_rank == 1 if hit_rank else False,
            "recall_3": (hit_rank is not None and hit_rank <= 3),
            "recall_5": (hit_rank is not None and hit_rank <= 5),
            "mrr_contrib": 1.0 / hit_rank if hit_rank else 0.0,
            "elapsed_ms": round(elapsed_ms, 1),
            # Agentic-specific metadata
            "agentic_turns": turns,
            "agentic_tool_calls": parsed_tool_calls,
            "agentic_pages_retrieved": len(all_retrieved_pages),
            "agentic_first_turn_hit": _check_first_turn_hit(
                all_retrieved_pages, gt_page_id, turns, parsed_tool_calls
            ),
            "agentic_final_answer_len": (
                len(final_answer) if isinstance(final_answer, str) else 0
            ),
            "agentic_reference_count": (
                len(final_ref.get("chunks", []))
                if isinstance(final_ref, dict) else 0
            ),
        }
        results.append(result)

        if (i + 1) % 20 == 0:
            logger.info(f"Agentic: processed {i + 1}/{n} queries")

    n_hits = sum(1 for r in results if r["recall_3"])
    logger.info(f"Agentic complete: {n_hits}/{n} Recall@3 hits ({n_hits/n:.1%})")
    return results


def _parse_tool_calls_from_text(text: str) -> list[dict]:
    """Extract tool call names from agent's tool_call_log text."""
    import re

    calls: list[dict] = []
    # Pattern: <tool_call name="tool_name"> ... </tool_call>
    pattern = r'<tool_call\s+name="([^"]+)"\s*>(.*?)</tool_call>'
    for match in re.finditer(pattern, text, re.DOTALL):
        calls.append({
            "tool": match.group(1),
            "content": match.group(2).strip()[:500],
        })
    return calls


def _check_first_turn_hit(
    pages: list[dict],
    gt_page_id: str,
    total_turns: int,
    tool_calls: list[dict],
) -> bool:
    """Heuristic: check if gt_page_id was found in first turn's results.

    Since AgentLoop doesn't explicitly label turns per page, we approximate:
    if total_turns <= 2 and the page is in retrieved_pages, it was likely
    found in the first retrieval turn.
    """
    if total_turns <= 0:
        return False
    # If only one round of tool calls, any hit is a first-turn hit
    if total_turns == 1:
        return True
    # Otherwise we can't perfectly determine without turn-level tracking
    # from AgentLoop, so we mark as None/unknown
    return False  # Conservative: mark as not first-turn unless exactly 1 turn
```

- [ ] **Step 2: Verify the module imports**

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2 && python -c "from experiments.agentic_runner import run_agentic_experiment; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add experiments/agentic_runner.py
git commit -m "feat: add agentic-mode experiment runner

Wraps AgentLoop.run() with per-query data collection: tool calls,
retrieved pages, turns, elapsed time, and first-turn-hit heuristic.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: Create `annotation.py`

**Files:**
- Create: `experiments/annotation.py`

**Interfaces:**
- Consumes: `chat_mdl` from `LLMBundle`
- Produces: `annotate_queries(queries: list[dict], chat_mdl: Any, batch_size: int) -> list[dict]`

- [ ] **Step 1: Create `experiments/annotation.py`**

```python
"""LLM-based automatic annotation of query types for stratified analysis.

Labels each query along three dimensions:
  - granularity: 单页事实 | 单页概念 | 跨页综合 | 全文档
  - cognitive: 记忆型 | 理解型 | 应用型 | 分析型
  - modality: 纯文本 | 公式数学 | 图表流程图 | 代码伪代码
"""
import json
import logging
import re
from typing import Any

logger = logging.getLogger("experiments.annotation")

ANNOTATION_PROMPT = """你是一个教育数据标注专家。请对以下学生提问进行分类。

问题："{query}"

请从以下三个维度进行分类：

1. **知识粒度**：
   - 单页事实：答案明确出现在某一张课件页面上
   - 单页概念：需要理解某一页的内容并归纳总结
   - 跨页综合：需要结合多页（2页及以上）的内容
   - 全文档/课程：需要跨多个文档或整门课程的宏观理解

2. **认知层次**（Bloom分类法简化）：
   - 记忆型：回忆事实、术语、定义、公式
   - 理解型：用自己的话解释概念、原理
   - 应用型：将知识用到具体场景或计算
   - 分析型：比较、对比、分析、推理

3. **内容模态**：
   - 纯文本：答案主要依赖文字描述
   - 公式/数学：涉及数学公式、符号、推导
   - 图表/流程图：答案依赖图表、流程图、架构图
   - 代码/伪代码：涉及程序代码或算法伪代码

请只输出 JSON，无需解释：
{{"granularity": "单页事实|单页概念|跨页综合|全文档",
  "cognitive": "记忆型|理解型|应用型|分析型",
  "modality": "纯文本|公式数学|图表流程图|代码伪代码"}}"""


def _parse_annotation_response(text: str) -> dict[str, str] | None:
    """Extract JSON from LLM response text."""
    # Try to find JSON block
    json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    # Try parsing the whole text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    return None


def annotate_queries(
    queries: list[dict],
    chat_mdl: Any,
    batch_size: int = 10,
) -> list[dict]:
    """Annotate a list of queries with three-dimension type labels.

    Args:
        queries: List of query dicts (must have 'query' key).
        chat_mdl: Chat LLM from LLMBundle (must support chat() method).
        batch_size: Not used for batching currently; each query is annotated
                    individually for reliability.

    Returns:
        Same list with added keys: granularity, cognitive, modality.
    """
    annotated: list[dict] = []
    n = len(queries)

    for i, q in enumerate(queries):
        query_text = q.get("query", "")
        prompt = ANNOTATION_PROMPT.format(query=query_text)

        result = dict(q)
        try:
            messages = [{"role": "user", "content": prompt}]
            response = chat_mdl.chat(
                system="你是一个精确的数据标注助手。只输出JSON。",
                messages=messages,
                gen_conf={"temperature": 0.0, "max_tokens": 200},
            )
            # response may be str or dict depending on chat_mdl implementation
            response_text = response if isinstance(response, str) else response.get("content", "")

            labels = _parse_annotation_response(response_text)
            if labels:
                result["granularity"] = labels.get("granularity", "unknown")
                result["cognitive"] = labels.get("cognitive", "unknown")
                result["modality"] = labels.get("modality", "unknown")
            else:
                logger.warning(f"Failed to parse annotation for query {q.get('id')}: {response_text[:100]}")
                result["granularity"] = "parse_error"
                result["cognitive"] = "parse_error"
                result["modality"] = "parse_error"
        except Exception as e:
            logger.error(f"Annotation error for query {q.get('id')}: {e}")
            result["granularity"] = "error"
            result["cognitive"] = "error"
            result["modality"] = "error"

        annotated.append(result)

        if (i + 1) % 50 == 0:
            logger.info(f"Annotation: processed {i + 1}/{n} queries")

    # Log distribution
    for dim in ["granularity", "cognitive", "modality"]:
        counts: dict[str, int] = {}
        for q in annotated:
            val = q.get(dim, "unknown")
            counts[val] = counts.get(val, 0) + 1
        logger.info(f"Annotation distribution [{dim}]: {counts}")

    return annotated


def select_annotation_check_sample(
    annotated: list[dict],
    n_per_category: int = 10,
    dim: str = "granularity",
    seed: int = 42,
) -> list[dict]:
    """Select a sample of queries for human verification of LLM annotations.

    Stratified across categories of the given dimension.
    """
    import numpy as np

    rng = np.random.default_rng(seed)

    # Group by category
    groups: dict[str, list[dict]] = {}
    for q in annotated:
        cat = q.get(dim, "unknown")
        groups.setdefault(cat, []).append(q)

    sample: list[dict] = []
    for cat, qs in groups.items():
        n_take = min(n_per_category, len(qs))
        chosen = rng.choice(qs, size=n_take, replace=False)
        for c in chosen:
            sample.append({"query_id": c.get("id"), "query": c.get("query"),
                           dim: c.get(dim), "cognitive": c.get("cognitive"),
                           "modality": c.get("modality")})

    logger.info(f"Selected {len(sample)} queries for annotation verification (dim={dim})")
    return sample
```

- [ ] **Step 2: Check the module imports**

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2 && python -c "from experiments.annotation import annotate_queries, ANNOTATION_PROMPT; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add experiments/annotation.py
git commit -m "feat: add LLM-based query type annotation module

Auto-labels queries along granularity, cognitive, and modality
dimensions. Includes parse-error handling and verification sample
selection for human-in-the-loop quality check.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 9: Create `report_generator.py` — Tables

**Files:**
- Create: `experiments/report_generator.py`

**Interfaces:**
- Consumes: `experiments.metrics`, `experiments.statistical_tests`
- Produces: `generate_latex_ablation_table(summary: dict) -> str`, `generate_latex_paradigm_table(summary: dict) -> str`, `generate_stratified_table(summary: dict, dim: str) -> str`, `generate_summary_json(results: dict) -> dict`

- [ ] **Step 1: Create `experiments/report_generator.py`**

```python
"""Generate LaTeX tables and summary JSON from experiment results."""
import json
import logging
from typing import Any

from experiments.metrics import compute_all_metrics
from experiments.statistical_tests import paired_ttest, per_query_hit_scores, bootstrap_ci

logger = logging.getLogger("experiments.report_generator")

# ── LaTeX table generators ──────────────────────────────────


def generate_latex_ablation_table(variant_results: dict[str, list[dict]]) -> str:
    """Generate the main ablation experiment LaTeX table.

    Args:
        variant_results: {variant_name: [result_dicts]}

    Returns:
        LaTeX table string for the ablation main result table.
    """
    header = (
        r"\begin{table}[htbp]" "\n"
        r"\centering" "\n"
        r"\caption{检索链路消融实验结果}" "\n"
        r"\label{tab:ablation}" "\n"
        r"\begin{tabular}{lccccc}" "\n"
        r"\toprule" "\n"
        r"配置 & Recall@1 & Recall@3 & Recall@5 & MRR & NDCG@5 \\" "\n"
        r"\midrule" "\n"
    )

    rows: list[str] = []
    variant_order = ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9"]

    for vname in variant_order:
        results = variant_results.get(vname, [])
        if not results:
            continue
        m = compute_all_metrics(results)
        ci_lo, _, ci_hi = bootstrap_ci(
            per_query_hit_scores(results, k=3)
        )
        rows.append(
            f"{m.get('_label', vname)} & "
            f"{m['recall_1']:.3f} & "
            f"{m['recall_3']:.3f} & "
            f"{m['recall_5']:.3f} & "
            f"{m['mrr']:.3f} & "
            f"{m['ndcg_5']:.3f} \\\\"
        )

    footer = (
        r"\bottomrule" "\n"
        r"\end{tabular}" "\n"
        r"\end{table}"
    )

    return header + "\n".join(rows) + "\n" + footer


def generate_latex_paradigm_table(
    wf_results: list[dict],
    ag_results: list[dict],
) -> str:
    """Generate Workflow vs Agentic comparison table.

    Args:
        wf_results: Workflow mode per-query results.
        ag_results: Agentic mode per-query results.

    Returns:
        LaTeX table string.
    """
    wf_m = compute_all_metrics(wf_results)
    ag_m = compute_all_metrics(ag_results)

    # Compute per-query scores for t-test
    wf_scores_r3 = per_query_hit_scores(wf_results, k=3)
    ag_scores_r3 = per_query_hit_scores(ag_results, k=3)
    ttest_r3 = paired_ttest(ag_scores_r3, wf_scores_r3)

    wf_mrr_scores = [r["mrr_contrib"] for r in wf_results]
    ag_mrr_scores = [r["mrr_contrib"] for r in ag_results]
    ttest_mrr = paired_ttest(ag_mrr_scores, wf_mrr_scores)

    # Efficiency
    wf_latency = [r.get("elapsed_ms", 0) for r in wf_results]
    ag_latency = [r.get("elapsed_ms", 0) for r in ag_results]
    ag_turns = [r.get("agentic_turns", 0) for r in ag_results]

    import numpy as np

    table = (
        r"\begin{table}[htbp]" "\n"
        r"\centering" "\n"
        r"\caption{Workflow 与 Agentic 范式对比}" "\n"
        r"\label{tab:paradigm}" "\n"
        r"\begin{tabular}{lcc}" "\n"
        r"\toprule" "\n"
        r"指标 & Workflow & Agentic \\" "\n"
        r"\midrule" "\n"
        # Retrieval quality
        f"Recall@3 & {wf_m['recall_3']:.3f} & {ag_m['recall_3']:.3f} \\\\" "\n"
        f"MRR & {wf_m['mrr']:.3f} & {ag_m['mrr']:.3f} \\\\" "\n"
        r"\midrule" "\n"
        # Efficiency
        f"平均延迟 (ms) & {np.mean(wf_latency):.0f} & {np.mean(ag_latency):.0f} \\\\" "\n"
        f"平均检索轮数 & 1.0 & {np.mean(ag_turns):.1f} \\\\" "\n"
        f"首轮命中率 & — & {sum(1 for r in ag_results if r.get('agentic_first_turn_hit')) / max(len(ag_results), 1):.3f} \\\\" "\n"
        r"\midrule" "\n"
        # Statistical tests
        f"R@3 配对t检验 p值 & \\multicolumn{{2}}{{c}}{{p = {ttest_r3['p_value']:.4f}, d = {ttest_r3['cohens_d']:.3f}}} \\\\" "\n"
        r"\bottomrule" "\n"
        r"\end{tabular}" "\n"
        r"\end{table}"
    )
    return table


def generate_stratified_table(
    variant_results: dict[str, list[dict]],
    stratify_dim: str = "granularity",
) -> str:
    """Generate stratified analysis LaTeX table.

    Args:
        variant_results: {variant_name: [annotated_result_dicts]}.
                         Result dicts must have the stratification dimension key.
        stratify_dim: The dimension to stratify by (granularity/cognitive/modality).

    Returns:
        LaTeX table string.
    """
    # Collect all categories
    all_categories: set[str] = set()
    for results in variant_results.values():
        for r in results:
            cat = r.get(stratify_dim, "unknown")
            all_categories.add(cat)

    categories = sorted(all_categories)
    # Variant columns (use select variants for readability)
    variant_cols = ["G1", "G2", "G3", "G9"]

    header = (
        r"\begin{table}[htbp]" "\n"
        r"\centering" "\n"
        rf"\caption{{按{stratify_dim}分层的 Recall@3 对比}}" "\n"
        rf"\label{{tab:stratified_{stratify_dim}}}" "\n"
        r"\begin{tabular}{l" + "c" * len(variant_cols) + "}" "\n"
        r"\toprule" "\n"
        rf"\{stratify_dim} & " + " & ".join(variant_cols) + r" \\" "\n"
        r"\midrule" "\n"
    )

    rows: list[str] = []
    for cat in categories:
        row_parts = [cat]
        for vname in variant_cols:
            results = variant_results.get(vname, [])
            cat_results = [r for r in results if r.get(stratify_dim) == cat]
            if cat_results:
                r3 = sum(1 for r in cat_results if r.get("recall_3")) / len(cat_results)
                row_parts.append(f"{r3:.3f}")
            else:
                row_parts.append("—")
        rows.append(" & ".join(row_parts) + r" \\")

    footer = (
        r"\bottomrule" "\n"
        r"\end{tabular}" "\n"
        r"\end{table}"
    )

    return header + "\n".join(rows) + "\n" + footer


# ── Summary JSON ───────────────────────────────────────────


def generate_summary_json(
    all_results: dict[str, list[dict]],
    annotations: list[dict] | None = None,
) -> dict[str, Any]:
    """Generate a comprehensive summary JSON with all metrics.

    Args:
        all_results: {"G1": [...], "G2": [...], ..., "workflow": [...], "agentic": [...]}
        annotations: Optional annotated query list.

    Returns:
        Nested dict with per-variant metrics, pairwise tests, and distributions.
    """
    summary: dict[str, Any] = {
        "variants": {},
        "paradigm_comparison": {},
        "annotations": {},
    }

    variant_order = ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9"]

    # Per-variant metrics
    for vname in variant_order:
        results = all_results.get(vname, [])
        if not results:
            continue
        m = compute_all_metrics(results)
        m["_n"] = len(results)
        # Bootstrap CI for Recall@3
        lo, _, hi = bootstrap_ci(per_query_hit_scores(results, k=3))
        m["recall_3_ci95"] = [round(lo, 4), round(hi, 4)]
        summary["variants"][vname] = m

    # Pairwise t-tests between key pairs (vs G9)
    g9_results = all_results.get("G9", [])
    if g9_results:
        g9_scores = per_query_hit_scores(g9_results, k=3)
        pairwise: dict[str, dict] = {}
        for vname in variant_order:
            if vname == "G9":
                continue
            vr = all_results.get(vname, [])
            if not vr:
                continue
            vs = per_query_hit_scores(vr, k=3)
            pairwise[f"G9_vs_{vname}"] = paired_ttest(g9_scores, vs)
        summary["pairwise_tests_vs_G9"] = pairwise

    # Paradigm comparison
    wf = all_results.get("workflow", [])
    ag = all_results.get("agentic", [])
    if wf and ag:
        wf_m = compute_all_metrics(wf)
        ag_m = compute_all_metrics(ag)
        ttest_r3 = paired_ttest(
            per_query_hit_scores(ag, k=3),
            per_query_hit_scores(wf, k=3),
        )

        import numpy as np
        ag_turns = [r.get("agentic_turns", 0) for r in ag]

        summary["paradigm_comparison"] = {
            "workflow": wf_m,
            "agentic": ag_m,
            "recall_3_ttest": ttest_r3,
            "agentic_mean_turns": float(np.mean(ag_turns)),
            "agentic_first_turn_hit_rate": (
                sum(1 for r in ag if r.get("agentic_first_turn_hit")) / max(len(ag), 1)
            ),
            "wf_mean_latency_ms": float(np.mean([r.get("elapsed_ms", 0) for r in wf])),
            "ag_mean_latency_ms": float(np.mean([r.get("elapsed_ms", 0) for r in ag])),
        }

    # Annotation distributions
    if annotations:
        for dim in ["granularity", "cognitive", "modality"]:
            counts: dict[str, int] = {}
            for q in annotations:
                val = q.get(dim, "unknown")
                counts[val] = counts.get(val, 0) + 1
            summary["annotations"][f"{dim}_distribution"] = counts

    return summary


# ── Tool call analysis (agentic-specific) ──────────────────


def analyze_tool_usage(agentic_results: list[dict]) -> dict[str, Any]:
    """Analyze tool call patterns from agentic experiment results.

    Returns:
        dict with tool_frequency, turn_distribution, common_sequences.
    """
    from collections import Counter

    tool_counter: Counter = Counter()
    turn_dist: Counter = Counter()
    sequences: Counter = Counter()

    for r in agentic_results:
        turns = r.get("agentic_turns", 0)
        turn_dist[turns] += 1

        tool_calls = r.get("agentic_tool_calls", [])
        seq = tuple(tc.get("tool", "?") for tc in tool_calls)
        if seq:
            sequences[str(seq)] += 1

        for tc in tool_calls:
            tool_counter[tc.get("tool", "?")] += 1

    total_queries = max(len(agentic_results), 1)
    total_calls = sum(tool_counter.values())

    return {
        "total_queries": len(agentic_results),
        "total_tool_calls": total_calls,
        "mean_calls_per_query": total_calls / total_queries,
        "mean_turns_per_query": sum(turn_dist.keys()) / total_queries
        if sum(turn_dist.values()) > 0 else 0,
        "tool_frequency": dict(tool_counter.most_common()),
        "turn_distribution": {str(k): v for k, v in sorted(turn_dist.items())},
        "top_sequences": [
            {"sequence": seq, "count": cnt}
            for seq, cnt in sequences.most_common(10)
        ],
    }
```

- [ ] **Step 2: Check the module imports**

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2 && python -c "from experiments.report_generator import generate_summary_json, analyze_tool_usage; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add experiments/report_generator.py
git commit -m "feat: add report generator with LaTeX tables and summary JSON

Generates ablation table, paradigm comparison table, and stratified
analysis tables. Also produces comprehensive summary JSON with
pairwise t-tests, bootstrap CIs, and tool usage analysis.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 10: Add chart generation to `report_generator.py`

**Files:**
- Modify: `experiments/report_generator.py`
- Append chart functions to the existing file.

**Interfaces:**
- Produces: `generate_ablation_barchart(variant_results, output_path)`, `generate_gain_decay_chart(agentic_results, output_path)`, `generate_tool_usage_pie(agentic_results, output_path)`, `generate_modality_heatmap(variant_results, output_path)`, `generate_latency_boxplot(wf_results, ag_results, output_path)`

- [ ] **Step 1: Append chart functions to report_generator.py**

Append the following to `experiments/report_generator.py`:

```python
# ── Chart generation ───────────────────────────────────────

import os as _os

import matplotlib as _mpl
_mpl.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as _plt
import numpy as _np


def _ensure_output_dir(path: str) -> None:
    _os.makedirs(_os.path.dirname(path), exist_ok=True)


def generate_ablation_barchart(
    variant_results: dict[str, list[dict]],
    output_path: str,
) -> None:
    """Grouped bar chart: Recall@1, Recall@3, Recall@5 for G1-G9."""
    _ensure_output_dir(output_path)

    variant_order = ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9"]
    labels: list[str] = []
    r1_vals: list[float] = []
    r3_vals: list[float] = []
    r5_vals: list[float] = []

    for vname in variant_order:
        results = variant_results.get(vname, [])
        if not results:
            continue
        labels.append(vname)
        r1_vals.append(sum(1 for r in results if r.get("recall_1")) / len(results))
        r3_vals.append(sum(1 for r in results if r.get("recall_3")) / len(results))
        r5_vals.append(sum(1 for r in results if r.get("recall_5")) / len(results))

    x = _np.arange(len(labels))
    width = 0.25

    fig, ax = _plt.subplots(figsize=(12, 5))
    ax.bar(x - width, r1_vals, width, label="Recall@1", color="#4C72B0")
    ax.bar(x, r3_vals, width, label="Recall@3", color="#55A868")
    ax.bar(x + width, r5_vals, width, label="Recall@5", color="#C44E52")

    ax.set_xlabel("Variant")
    ax.set_ylabel("Recall")
    ax.set_title("Retrieval Pipeline Ablation: Recall@K")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.legend()
    ax.set_ylim(0, 1.05)
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    _plt.close(fig)
    logger.info(f"Saved ablation barchart to {output_path}")


def generate_gain_decay_chart(
    agentic_results: list[dict],
    output_path: str,
) -> None:
    """Line chart: cumulative Recall@3 vs retrieval turns for agentic mode.

    Note: Requires turn-level retrieval tracking. If AgentLoop doesn't
    expose per-turn page lists, this produces a simplified version based
    on total turns and final hit.
    """
    _ensure_output_dir(output_path)

    # Group results by number of turns
    max_turns = max((r.get("agentic_turns", 0) for r in agentic_results), default=0)
    turns_range = list(range(1, min(max_turns + 1, 11)))

    cumulative_r3: list[float] = []
    for t in turns_range:
        subset = [r for r in agentic_results if r.get("agentic_turns", 0) <= t]
        if subset:
            r3 = sum(1 for r in subset if r.get("recall_3")) / len(subset)
            cumulative_r3.append(r3)
        else:
            cumulative_r3.append(cumulative_r3[-1] if cumulative_r3 else 0.0)

    fig, ax = _plt.subplots(figsize=(8, 4))
    ax.plot(turns_range, cumulative_r3, marker="o", color="#4C72B0", linewidth=2)
    ax.set_xlabel("Max Retrieval Turns")
    ax.set_ylabel("Cumulative Recall@3")
    ax.set_title("Agentic Retrieval Gain Decay")
    ax.set_ylim(0, 1.05)
    ax.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    _plt.close(fig)
    logger.info(f"Saved gain decay chart to {output_path}")


def generate_tool_usage_pie(
    agentic_results: list[dict],
    output_path: str,
) -> None:
    """Pie chart: tool call frequency distribution."""
    _ensure_output_dir(output_path)

    from collections import Counter

    counter: Counter = Counter()
    for r in agentic_results:
        for tc in r.get("agentic_tool_calls", []):
            counter[tc.get("tool", "?")] += 1

    if not counter:
        logger.warning("No tool calls to plot")
        return

    labels = [k for k, _ in counter.most_common()]
    sizes = [v for _, v in counter.most_common()]
    colors = _plt.cm.Set2(range(len(labels)))

    fig, ax = _plt.subplots(figsize=(7, 7))
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, autopct="%1.1f%%",
        colors=colors, startangle=140,
    )
    ax.set_title("Agentic Tool Call Distribution")

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    _plt.close(fig)
    logger.info(f"Saved tool usage pie to {output_path}")


def generate_modality_heatmap(
    variant_results: dict[str, list[dict]],
    output_path: str,
) -> None:
    """Heatmap: rows=content modality, cols=variant, color=Recall@3."""
    _ensure_output_dir(output_path)

    modalities = ["纯文本", "公式数学", "图表流程图", "代码伪代码"]
    variant_cols = ["G1", "G2", "G3", "G9"]

    data: list[list[float]] = []
    for mod in modalities:
        row: list[float] = []
        for vname in variant_cols:
            results = variant_results.get(vname, [])
            cat_results = [r for r in results if r.get("modality") == mod]
            if cat_results:
                r3 = sum(1 for r in cat_results if r.get("recall_3")) / len(cat_results)
                row.append(r3)
            else:
                row.append(0.0)
        data.append(row)

    data_arr = _np.array(data)

    fig, ax = _plt.subplots(figsize=(8, 5))
    im = ax.imshow(data_arr, cmap="YlOrRd", vmin=0, vmax=1.0, aspect="auto")

    ax.set_xticks(range(len(variant_cols)))
    ax.set_xticklabels(variant_cols)
    ax.set_yticks(range(len(modalities)))
    ax.set_yticklabels(modalities)
    ax.set_title("Recall@3 by Content Modality × Retrieval Variant")

    # Annotate cells
    for i in range(len(modalities)):
        for j in range(len(variant_cols)):
            ax.text(j, i, f"{data_arr[i, j]:.3f}", ha="center", va="center",
                    fontsize=9)

    fig.colorbar(im, ax=ax, label="Recall@3")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    _plt.close(fig)
    logger.info(f"Saved modality heatmap to {output_path}")


def generate_latency_boxplot(
    wf_results: list[dict],
    ag_results: list[dict],
    output_path: str,
) -> None:
    """Box plot: latency distribution comparison (Workflow vs Agentic)."""
    _ensure_output_dir(output_path)

    wf_lat = [r.get("elapsed_ms", 0) / 1000 for r in wf_results]
    ag_lat = [r.get("elapsed_ms", 0) / 1000 for r in ag_results]

    fig, ax = _plt.subplots(figsize=(6, 5))
    bp = ax.boxplot(
        [wf_lat, ag_lat],
        labels=["Workflow", "Agentic"],
        patch_artist=True,
    )
    bp["boxes"][0].set_facecolor("#4C72B0")
    bp["boxes"][1].set_facecolor("#C44E52")

    ax.set_ylabel("Latency (seconds)")
    ax.set_title("End-to-End Latency: Workflow vs Agentic")
    ax.grid(axis="y", alpha=0.3)

    # Add mean markers
    wf_mean = _np.mean(wf_lat)
    ag_mean = _np.mean(ag_lat)
    ax.scatter([1, 2], [wf_mean, ag_mean], marker="D", color="black", zorder=3,
               label=f"Mean (WF={wf_mean:.1f}s, AG={ag_mean:.1f}s)")
    ax.legend()

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    _plt.close(fig)
    logger.info(f"Saved latency boxplot to {output_path}")


def generate_all_charts(
    variant_results: dict[str, list[dict]],
    wf_results: list[dict],
    ag_results: list[dict],
    output_dir: str,
) -> list[str]:
    """Generate all charts and return list of output paths."""
    _os.makedirs(output_dir, exist_ok=True)
    paths: list[str] = []

    p = _os.path.join(output_dir, "ablation_recall.png")
    generate_ablation_barchart(variant_results, p)
    paths.append(p)

    p = _os.path.join(output_dir, "agentic_gain_decay.png")
    generate_gain_decay_chart(ag_results, p)
    paths.append(p)

    p = _os.path.join(output_dir, "agentic_tool_usage.png")
    generate_tool_usage_pie(ag_results, p)
    paths.append(p)

    p = _os.path.join(output_dir, "modality_heatmap.png")
    generate_modality_heatmap(variant_results, p)
    paths.append(p)

    if wf_results and ag_results:
        p = _os.path.join(output_dir, "latency_boxplot.png")
        generate_latency_boxplot(wf_results, ag_results, p)
        paths.append(p)

    return paths
```

- [ ] **Step 2: Verify matplotlib works in non-interactive mode**

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2 && python -c "
from experiments.report_generator import generate_all_charts
print('Chart functions imported successfully')
"
```

Expected: `Chart functions imported successfully`

- [ ] **Step 3: Commit**

```bash
git add experiments/report_generator.py
git commit -m "feat: add matplotlib chart generation to report generator

Charts: ablation grouped bar, agentic gain decay line, tool usage pie,
content modality heatmap, latency boxplot. All use Agg backend.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 11: Create `run_all_experiments.py`

**Files:**
- Create: `experiments/run_all_experiments.py`

**Interfaces:**
- Consumes: All experiment modules, `rag.agent.server.tools.MCPToolExecutor`, `rag.nlp.search.Dealer`, `rag.agent.client.loop.AgentLoop`, `api.db.services.llm_service.LLMBundle`
- Produces: CLI entry point that runs all experiments

- [ ] **Step 1: Create `experiments/run_all_experiments.py`**

```python
#!/usr/bin/env python
"""Run all retrieval experiments and generate reports.

Usage:
    python -m experiments.run_all_experiments \
        --test_set data/test_set.jsonl \
        --output_dir results/ \
        --variants all \
        --compare_modes both

Requirements:
    Running inside the ragflow-plus conda environment with all services up
    (ES, MySQL, MinIO). MCP server must be running if running agentic mode.
"""
import argparse
import json
import logging
import os
import sys
import time
from typing import Any

# Ensure project root is on path
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from experiments.config import VARIANTS, EXPERIMENT_DEFAULTS, VariantConfig
from experiments.test_set_loader import load_test_set, save_test_set
from experiments.variant_runner import VariantRunner
from experiments.metrics import compute_all_metrics
from experiments.report_generator import (
    generate_summary_json,
    generate_latex_ablation_table,
    generate_latex_paradigm_table,
    generate_all_charts,
    analyze_tool_usage,
)

logger = logging.getLogger("experiments")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


def setup_dealer_and_executor(kb_ids: list[str]) -> tuple[Any, Any, Any, Any, Any]:
    """Initialize ES Dealer, MCPToolExecutor, and models.

    Returns (dealer, executor, embd_mdl, rerank_mdl, chat_mdl, kb_ids, tenant_ids).
    """
    from rag.nlp.search import Dealer
    from rag.utils.es_conn import ESConnection
    from api.db.services.llm_service import LLMBundle
    from api.db.services.knowledgebase_service import KnowledgebaseService
    from api.db import LLMType
    from rag.agent.server.tools import MCPToolExecutor

    dealer = Dealer(ESConnection())

    # Get KB info
    kbs = KnowledgebaseService.get_by_ids(kb_ids)
    if not kbs:
        raise ValueError(f"No knowledge bases found for ids: {kb_ids}")

    tenant_ids = list(set(kb.tenant_id for kb in kbs))
    embd_id = kbs[0].embd_id

    # Models — use first KB's tenant
    tenant_id = tenant_ids[0]
    embd_mdl = LLMBundle(tenant_id, LLMType.EMBEDDING, embd_id) if embd_id else None

    # Rerank and Chat models — we need a dialog reference, but for experiments
    # we construct bundles directly using the same tenant
    # In practice, the caller should provide rerank_id and chat_llm_id
    rerank_mdl = None
    chat_mdl = LLMBundle(tenant_id, LLMType.CHAT, embd_id)  # fallback; override via CLI

    executor = MCPToolExecutor(
        dealer=dealer,
        embd_mdl=embd_mdl,
        rerank_mdl=rerank_mdl,
    )

    return dealer, executor, embd_mdl, rerank_mdl, chat_mdl, tenant_ids


def run_variant_experiments(
    test_queries: list[dict],
    executor: Any,
    kb_ids: list[str],
    tenant_ids: list[str],
    variants: list[str] | None = None,
) -> dict[str, list[dict]]:
    """Run all selected variants against the test set.

    Returns {variant_name: [result_dicts]}.
    """
    if variants is None:
        variants = list(VARIANTS.keys())

    all_results: dict[str, list[dict]] = {}
    n = len(test_queries)

    for vname in variants:
        cfg = VARIANTS[vname]
        logger.info(f"=== Running variant {vname}: {cfg.name} ===")
        runner = VariantRunner(cfg, executor)

        results: list[dict] = []
        t0 = time.perf_counter()
        for i, q in enumerate(test_queries):
            query_text = q["query"]
            gt_page_id = q["page_id"]

            try:
                pages = runner.retrieve(query_text, tenant_ids, kb_ids)
                retrieved_page_ids = [p.get("page_id", "") for p in pages]
            except Exception as e:
                logger.error(f"Error in {vname} query {q.get('id')}: {e}")
                retrieved_page_ids = []

            hit_rank = None
            try:
                hit_rank = retrieved_page_ids.index(gt_page_id) + 1
            except ValueError:
                pass

            result = {
                "mode": "variant",
                "variant": vname,
                "query_id": q.get("id", f"q{i}"),
                "query": query_text,
                "ground_truth_page_id": gt_page_id,
                "retrieved_page_ids": retrieved_page_ids,
                "hit_at_rank": hit_rank,
                "recall_1": hit_rank == 1 if hit_rank else False,
                "recall_3": (hit_rank is not None and hit_rank <= 3),
                "recall_5": (hit_rank is not None and hit_rank <= 5),
                "mrr_contrib": 1.0 / hit_rank if hit_rank else 0.0,
                "elapsed_ms": 0.0,  # variant runner doesn't time per query
            }
            # Carry over annotations if present
            for key in ("granularity", "cognitive", "modality"):
                if key in q:
                    result[key] = q[key]

            results.append(result)

            if (i + 1) % 100 == 0:
                logger.info(f"  {vname}: {i + 1}/{n} queries")

        elapsed = time.perf_counter() - t0
        m = compute_all_metrics(results)
        logger.info(
            f"  {vname} complete: R@3={m['recall_3']:.3f}, "
            f"MRR={m['mrr']:.3f}, elapsed={elapsed:.1f}s"
        )
        all_results[vname] = results

    return all_results


def run_paradigm_experiments(
    test_queries: list[dict],
    dealer: Any,
    executor: Any,
    embd_mdl: Any,
    chat_mdl: Any,
    kb_ids: list[str],
    tenant_ids: list[str],
    rerank_id: str | None = None,
) -> tuple[list[dict], list[dict]]:
    """Run both Workflow and Agentic experiments.

    Returns (workflow_results, agentic_results).
    """
    from experiments.workflow_runner import run_workflow_experiment
    from experiments.agentic_runner import run_agentic_experiment

    # Determine models
    rerank_mdl = None

    # Workflow
    logger.info("=== Running Workflow mode ===")
    wf_results = run_workflow_experiment(
        test_queries=test_queries,
        dealer=dealer,
        embd_mdl=embd_mdl,
        kb_ids=kb_ids,
        tenant_ids=tenant_ids,
        rerank_mdl=rerank_mdl,
        chat_mdl=chat_mdl,
        enable_context_recall=True,
    )

    # Agentic
    logger.info("=== Running Agentic mode ===")
    # Agentic needs MCP server at known URL
    mcp_url = os.getenv("MCP_SERVER_URL", "http://localhost:9390")

    # Need a dialog-like object for AgentLoop context
    class _DialogProxy:
        pass

    dialog = _DialogProxy()
    dialog.kb_ids = kb_ids
    dialog.tenant_id = tenant_ids[0] if tenant_ids else ""

    ag_results = run_agentic_experiment(
        test_queries=test_queries,
        mcp_url=mcp_url,
        chat_mdl=chat_mdl,
        kb_ids=kb_ids,
        tenant_ids=tenant_ids,
        dialog=dialog,
        embd_id=embd_mdl.llm_id if embd_mdl else None,
        rerank_id=rerank_id,
        max_turns=EXPERIMENT_DEFAULTS["agentic_max_turns"],
    )

    return wf_results, ag_results


def main():
    parser = argparse.ArgumentParser(description="Run PAGE-RAG retrieval experiments")
    parser.add_argument("--test_set", required=True, help="Path to test_set.jsonl")
    parser.add_argument("--output_dir", default="results/", help="Output directory")
    parser.add_argument(
        "--variants", default="all",
        help="Comma-separated variant names (G1,G2,...,G9) or 'all'"
    )
    parser.add_argument(
        "--compare_modes", default="both",
        choices=["workflow", "agentic", "both", "none"],
        help="Which paradigm comparison to run"
    )
    parser.add_argument(
        "--kb_ids", required=True,
        help="Comma-separated knowledge base IDs (e.g. kb001,kb002)"
    )
    parser.add_argument(
        "--rerank_id", default=None,
        help="Rerank model ID (optional)"
    )
    parser.add_argument(
        "--chat_llm_id", default=None,
        help="Chat LLM model ID for agentic and context recall (optional)"
    )
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Load test set
    test_queries = load_test_set(args.test_set)
    logger.info(f"Loaded {len(test_queries)} test queries")

    kb_ids = [k.strip() for k in args.kb_ids.split(",")]

    # Setup
    dealer, executor, embd_mdl, rerank_mdl, chat_mdl, tenant_ids = setup_dealer_and_executor(kb_ids)

    # Override rerank_mdl if provided
    if args.rerank_id:
        from api.db.services.llm_service import LLMBundle
        from api.db import LLMType
        rerank_mdl = LLMBundle(tenant_ids[0], LLMType.RERANK, args.rerank_id)
        executor.rerank_mdl = rerank_mdl
        logger.info(f"Using rerank model: {args.rerank_id}")

    if args.chat_llm_id:
        from api.db.services.llm_service import LLMBundle
        from api.db import LLMType
        chat_mdl = LLMBundle(tenant_ids[0], LLMType.CHAT, args.chat_llm_id)
        logger.info(f"Using chat model: {args.chat_llm_id}")

    all_results: dict[str, list[dict]] = {}

    # Run variant experiments
    if args.variants == "all":
        variants = list(VARIANTS.keys())
    else:
        variants = [v.strip() for v in args.variants.split(",")]

    if variants:
        variant_results = run_variant_experiments(
            test_queries, executor, kb_ids, tenant_ids, variants,
        )
        all_results.update(variant_results)

        # Save variant results
        for vname, results in variant_results.items():
            path = os.path.join(args.output_dir, f"{vname}_results.jsonl")
            save_test_set(results, path)

    # Run paradigm experiments
    wf_results: list[dict] = []
    ag_results: list[dict] = []
    if args.compare_modes in ("workflow", "both"):
        wf_results, ag_results = run_paradigm_experiments(
            test_queries, dealer, executor, embd_mdl, chat_mdl,
            kb_ids, tenant_ids, args.rerank_id,
        )
        if args.compare_modes == "workflow":
            all_results["workflow"] = wf_results
            save_test_set(wf_results, os.path.join(args.output_dir, "workflow_results.jsonl"))
        else:
            wf_results_part, ag_results = wf_results, ag_results  # type narrowing
            all_results["workflow"] = wf_results_part
            all_results["agentic"] = ag_results
            save_test_set(wf_results_part, os.path.join(args.output_dir, "workflow_results.jsonl"))
            save_test_set(ag_results, os.path.join(args.output_dir, "agentic_results.jsonl"))
    elif args.compare_modes == "agentic":
        _wf, ag_results = run_paradigm_experiments(
            test_queries, dealer, executor, embd_mdl, chat_mdl,
            kb_ids, tenant_ids, args.rerank_id,
        )
        all_results["workflow"] = _wf
        all_results["agentic"] = ag_results
        save_test_set(_wf, os.path.join(args.output_dir, "workflow_results.jsonl"))
        save_test_set(ag_results, os.path.join(args.output_dir, "agentic_results.jsonl"))

    # Generate summary
    summary = generate_summary_json(all_results)

    # Add tool usage analysis
    if ag_results:
        tool_analysis = analyze_tool_usage(ag_results)
        summary["tool_usage"] = tool_analysis

    summary_path = os.path.join(args.output_dir, "summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    logger.info(f"Summary saved to {summary_path}")

    # Generate LaTeX tables
    tables_dir = os.path.join(args.output_dir, "tables")
    os.makedirs(tables_dir, exist_ok=True)

    variant_subset = {k: v for k, v in all_results.items() if k in VARIANTS}
    if variant_subset:
        latex = generate_latex_ablation_table(variant_subset)
        with open(os.path.join(tables_dir, "ablation_main.tex"), "w") as f:
            f.write(latex)

    if wf_results and ag_results:
        latex = generate_latex_paradigm_table(wf_results, ag_results)
        with open(os.path.join(tables_dir, "paradigm_comparison.tex"), "w") as f:
            f.write(latex)

    # Generate charts
    figures_dir = os.path.join(args.output_dir, "figures")
    chart_paths = generate_all_charts(
        {k: v for k, v in all_results.items() if k in VARIANTS},
        all_results.get("workflow", []),
        all_results.get("agentic", []),
        figures_dir,
    )
    for p in chart_paths:
        logger.info(f"Chart: {p}")

    logger.info("=== All experiments complete ===")
    logger.info(f"Results: {args.output_dir}")
    logger.info(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the script syntax**

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2 && python -c "import experiments.run_all_experiments; print('Module OK')"
```

Expected: `Module OK`

- [ ] **Step 3: Commit**

```bash
git add experiments/run_all_experiments.py
git commit -m "feat: add main experiment runner CLI

Single entry point: python -m experiments.run_all_experiments
--test_set <path> --kb_ids <ids> [--variants G1,G2,...] [--compare_modes both]

Orchestrates variant ablation, workflow/agentic comparison, and
generates summary JSON, LaTeX tables, and charts.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 12: Add query cleaning CLI utility

**Files:**
- Create: `experiments/clean_queries.py`

**Interfaces:**
- Produces: Standalone `python experiments/clean_queries.py` for test set construction

- [ ] **Step 1: Create `experiments/clean_queries.py`**

```python
#!/usr/bin/env python
"""Clean and prepare the test query set from raw VLM-generated queries.

Usage:
    python experiments/clean_queries.py \
        --input raw_queries.jsonl \
        --output_test data/test_set.jsonl \
        --output_dev data/dev_set.jsonl \
        --test_size 500 \
        --dev_size 200
"""
import argparse
import logging
import os
import sys

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from experiments.test_set_loader import (
    load_test_set, save_test_set, clean_queries, stratified_sample,
)

logger = logging.getLogger("experiments.clean")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


def main():
    parser = argparse.ArgumentParser(
        description="Clean and prepare test query set from raw VLM-generated queries"
    )
    parser.add_argument("--input", required=True, help="Path to raw queries JSONL")
    parser.add_argument("--output_test", default="data/test_set.jsonl",
                        help="Path for cleaned test set output")
    parser.add_argument("--output_dev", default="data/dev_set.jsonl",
                        help="Path for dev set output")
    parser.add_argument("--test_size", type=int, default=500,
                        help="Test set size (default 500)")
    parser.add_argument("--dev_size", type=int, default=200,
                        help="Dev set size (default 200)")
    parser.add_argument("--min_len", type=int, default=5,
                        help="Minimum query length (default 5)")
    parser.add_argument("--max_len", type=int, default=200,
                        help="Maximum query length (default 200)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed (default 42)")
    args = parser.parse_args()

    # 1. Load raw queries
    raw = load_test_set(args.input)
    logger.info(f"Loaded {len(raw)} raw queries from {args.input}")

    # 2. Clean
    cleaned, report = clean_queries(raw, min_len=args.min_len, max_len=args.max_len)
    logger.info(f"Cleaning report: {report}")
    logger.info(f"After cleaning: {len(cleaned)} queries")

    # 3. Sample
    total_needed = args.test_size + args.dev_size
    if len(cleaned) < total_needed:
        logger.warning(
            f"Only {len(cleaned)} queries available, "
            f"need {total_needed}. Reducing sample sizes proportionally."
        )
        ratio = len(cleaned) / total_needed
        test_size = int(args.test_size * ratio)
        dev_size = len(cleaned) - test_size
    else:
        test_size = args.test_size
        dev_size = args.dev_size

    pool = stratified_sample(cleaned, test_size + dev_size, seed=args.seed)
    test_set = pool[:test_size]
    dev_set = pool[test_size:test_size + dev_size]

    # 4. Save
    os.makedirs(os.path.dirname(args.output_test) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.output_dev) or ".", exist_ok=True)

    save_test_set(test_set, args.output_test)
    save_test_set(dev_set, args.output_dev)

    logger.info(f"Test set: {len(test_set)} queries → {args.output_test}")
    logger.info(f"Dev set: {len(dev_set)} queries → {args.output_dev}")

    # Print course distribution
    for label, qs in [("Test", test_set), ("Dev", dev_set)]:
        courses: dict[str, int] = {}
        for q in qs:
            c = q.get("course", "unknown")
            courses[c] = courses.get(c, 0) + 1
        logger.info(f"{label} course distribution: {courses}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify syntax**

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2 && python -c "import experiments.clean_queries; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add experiments/clean_queries.py
git commit -m "feat: add query cleaning CLI utility

Standalone script for creating test/dev sets from raw VLM-generated
queries. Performs dedup, length filtering, vague query removal, and
stratified sampling across courses and documents.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Plan Summary

| Task | File | Purpose |
|------|------|---------|
| 1 | `experiments/__init__.py`, `config.py` | Package scaffold + variant definitions |
| 2 | `experiments/test_set_loader.py` | Load, clean, sample queries |
| 3 | `experiments/metrics.py` | Recall@K, MRR, NDCG@K |
| 4 | `experiments/statistical_tests.py` | t-test, bootstrap CI, Cohen's Kappa |
| 5 | `experiments/variant_runner.py` | Configurable G1-G9 runner |
| 6 | `experiments/workflow_runner.py` | Workflow mode (Dealer.hybrid_page_retrieval) |
| 7 | `experiments/agentic_runner.py` | Agentic mode (AgentLoop.run) |
| 8 | `experiments/annotation.py` | LLM auto-labeling |
| 9 | `experiments/report_generator.py` | LaTeX tables + summary JSON |
| 10 | Append to `report_generator.py` | matplotlib charts |
| 11 | `experiments/run_all_experiments.py` | CLI entry point |
| 12 | `experiments/clean_queries.py` | Query cleaning utility |
