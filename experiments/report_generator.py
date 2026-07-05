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
