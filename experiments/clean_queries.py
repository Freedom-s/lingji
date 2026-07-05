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

    logger.info(f"Test set: {len(test_set)} queries -> {args.output_test}")
    logger.info(f"Dev set: {len(dev_set)} queries -> {args.output_dev}")

    # Print course distribution
    for label, qs in [("Test", test_set), ("Dev", dev_set)]:
        courses: dict[str, int] = {}
        for q in qs:
            c = q.get("course", "unknown")
            courses[c] = courses.get(c, 0) + 1
        logger.info(f"{label} course distribution: {courses}")


if __name__ == "__main__":
    main()
