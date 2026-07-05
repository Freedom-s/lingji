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


def setup_dealer_and_executor(kb_ids: list[str]) -> tuple[Any, Any, Any, Any, Any, list[str]]:
    """Initialize ES Dealer, MCPToolExecutor, and models.

    Returns (dealer, executor, embd_mdl, rerank_mdl, chat_mdl, tenant_ids).
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
        embd_id=embd_mdl.llm_name if embd_mdl else None,
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
            all_results["workflow"] = wf_results
            all_results["agentic"] = ag_results
            save_test_set(wf_results, os.path.join(args.output_dir, "workflow_results.jsonl"))
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
