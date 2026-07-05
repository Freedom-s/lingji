"""Generate LaTeX tables and summary JSON from experiment results."""
import logging
from collections import Counter
from typing import Any

import numpy as np

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

    # Efficiency
    wf_latency = [r.get("elapsed_ms", 0) for r in wf_results]
    ag_latency = [r.get("elapsed_ms", 0) for r in ag_results]
    ag_turns = [r.get("agentic_turns", 0) for r in ag_results]

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
        "mean_turns_per_query": sum(k * v for k, v in turn_dist.items()) / total_queries
        if sum(turn_dist.values()) > 0 else 0,
        "tool_frequency": dict(tool_counter.most_common()),
        "turn_distribution": {str(k): v for k, v in sorted(turn_dist.items())},
        "top_sequences": [
            {"sequence": seq, "count": cnt}
            for seq, cnt in sequences.most_common(10)
        ],
    }


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
