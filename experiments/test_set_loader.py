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
