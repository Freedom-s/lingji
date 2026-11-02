#!/usr/bin/env python3
"""Render thesis-friendly figures from the online RAG benchmark JSON files."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / ".gstack" / "benchmark-reports"
FIGURE_DIR = REPORT_DIR / "figures"

COLORS = {
    "p50": "#0072B2",
    "p95": "#D55E00",
    "p99": "#CC79A7",
    "qps": "#009E73",
    "success": "#E69F00",
}


def load(name: str) -> dict:
    with (REPORT_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def all_results() -> dict[int, dict]:
    merged = {}
    for name in (
        "2026-09-29-gunicorn-round1.json",
        "2026-09-29-gunicorn-round2.json",
        "2026-09-29-gunicorn-round3.json",
    ):
        merged.update({int(k): v for k, v in load(name)["results"].items()})
    return dict(sorted(merged.items()))


def save(fig: plt.Figure, stem: str) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_DIR / f"{stem}.png", dpi=220, bbox_inches="tight")
    fig.savefig(FIGURE_DIR / f"{stem}.svg", bbox_inches="tight")
    plt.close(fig)


def style_axes(ax: plt.Axes, title: str, ylabel: str) -> None:
    ax.set_title(title, fontsize=13, pad=10, weight="bold")
    ax.set_xlabel("Concurrency (requests)", fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.7, alpha=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_xticks(list(all_results()))


def plot_qps(results: dict[int, dict]) -> None:
    x = np.array(list(results))
    qps = np.array([results[n]["qps"] for n in x])
    success = np.array([results[n]["success_rate"] * 100 for n in x])

    fig, ax = plt.subplots(figsize=(7.2, 4.5))
    ax.plot(x, qps, color=COLORS["qps"], marker="o", linewidth=2.2, label="QPS")
    ax.fill_between(x, qps, color=COLORS["qps"], alpha=0.10)
    style_axes(ax, "Throughput and Success Rate", "Requests per second (QPS)")
    ax.set_ylim(bottom=0)
    ax2 = ax.twinx()
    ax2.plot(x, success, color=COLORS["success"], marker="s", linewidth=1.8, label="Success rate")
    ax2.set_ylabel("Success rate (%)", fontsize=10)
    ax2.set_ylim(0, 105)
    ax2.spines["top"].set_visible(False)
    ax2.grid(False)
    ax.axvline(10, color="#666666", linestyle="--", linewidth=1, alpha=0.8)
    ax.text(10.35, max(qps) * 0.77, "saturation\nstarts", fontsize=9, color="#555555")
    lines, labels = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines + lines2, labels + labels2, frameon=False, loc="upper left")
    save(fig, "throughput-success-rate")


def plot_latency(results: dict[int, dict], field: str, title: str, stem: str) -> None:
    x = np.array(list(results))
    fig, ax = plt.subplots(figsize=(7.2, 4.5))
    for key, label in (("p50", "P50"), ("p95", "P95"), ("p99", "P99")):
        values = np.array([results[n][field][key] / 1000 for n in x])
        ax.plot(x, values, marker="o", linewidth=2.1, color=COLORS[key], label=label)
    style_axes(ax, title, "Latency (seconds)")
    ax.set_ylim(bottom=0)
    ax.legend(frameon=False, ncol=3, loc="upper left")
    save(fig, stem)


def plot_stage_latency() -> None:
    rounds = [
        ("Concurrency 1–5", load("2026-09-29-gunicorn-round1.json")["stage_summary_ms"]),
        ("Concurrency 10–20", load("2026-09-29-gunicorn-round2.json")["stage_summary_ms"]),
        ("Concurrency 30–50", load("2026-09-29-gunicorn-round3.json")["stage_summary_ms"]),
    ]
    stages = [
        ("Intent recognition", "intent_llm"),
        ("Parallel retrieval", "parallel_retrieval"),
        ("Rerank", "rerank_pipeline"),
        ("Context recall", "context_recall"),
        ("Total retrieval", "retrieval_total"),
        ("LLM generation", "llm_generation"),
    ]
    y = np.arange(len(stages))
    height = 0.24
    fig, ax = plt.subplots(figsize=(8.2, 5.0))
    for index, (label, data) in enumerate(rounds):
        values = [data[key]["avg"] / 1000 for _, key in stages]
        ax.barh(y + (index - 1) * height, values, height=height, label=label,
                color=(COLORS["p50"], COLORS["p95"], COLORS["qps"])[index], alpha=0.90)
    ax.set_yticks(y)
    ax.set_yticklabels([label for label, _ in stages])
    ax.invert_yaxis()
    ax.set_xlabel("Average stage time (seconds)", fontsize=10)
    ax.set_title("Average RAG Stage Latency by Load Range", fontsize=13, pad=10, weight="bold")
    ax.grid(axis="x", color="#D9D9D9", linewidth=0.7, alpha=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(frameon=False, loc="lower right")
    save(fig, "stage-latency-by-load")


def main() -> None:
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "axes.titleweight": "bold",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
    })
    results = all_results()
    plot_qps(results)
    plot_latency(results, "ttft_ms", "Time to First Token", "ttft-percentiles")
    plot_latency(results, "total_ms", "End-to-End Response Latency", "response-latency-percentiles")
    plot_stage_latency()
    print(f"Generated figures in {FIGURE_DIR}")


if __name__ == "__main__":
    main()
