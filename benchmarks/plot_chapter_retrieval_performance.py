"""Generate figures matching the reduced thesis section exactly."""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np


OUT = Path(".gstack/benchmark-reports/figures/chapter-retrieval")
OUT.mkdir(parents=True, exist_ok=True)

FONT_PATH = "/System/Library/Fonts/Hiragino Sans GB.ttc"
font_manager.fontManager.addfont(FONT_PATH)
CHINESE_FONT = font_manager.FontProperties(fname=FONT_PATH).get_name()

plt.rcParams.update({
    "font.family": CHINESE_FONT,
    "axes.unicode_minus": False,
    "font.size": 10,
    "axes.titlesize": 13,
    "axes.labelsize": 11,
    "legend.fontsize": 9,
    "figure.dpi": 160,
})

concurrency = np.array([1, 2, 5, 10, 20, 30, 40, 50])
qps = np.array([0.082, 0.125, 0.196, 0.320, 0.265, 0.263, 0.394, 0.175])
ttft_avg = np.array([4.619, 4.624, 9.221, 15.851, 30.422, 44.922, 52.341, 59.116])
total_avg = np.array([12.181, 12.385, 16.054, 23.832, 38.643, 55.258, 60.636, 73.732])
response_p50 = np.array([13.429, 14.648, 14.465, 22.532, 37.565, 49.744, 66.442, 68.335])
response_p95 = np.array([19.146, 17.834, 24.395, 36.921, 66.006, 92.691, 97.854, 129.931])
response_p99 = np.array([20.288, 18.208, 25.248, 47.680, 73.486, 136.999, 108.938, 220.370])

loads = ["1–5", "10–20", "30–50"]
stage_avg = {
    "查询处理": [0.061, 0.079, 0.084],
    "多路召回": [0.838, 0.963, 0.915],
    "Rerank 重排序": [4.234, 7.103, 6.764],
    "上下文构建": [0.785, 0.771, 0.825],
    "大语言模型生成": [7.521, 8.243, 11.367],
}
stage_p95 = {
    "查询处理": [0.075, 0.118, 0.107],
    "多路召回": [1.121, 1.614, 1.527],
    "Rerank 重排序": [9.750, 13.846, 12.660],
    "上下文构建": [1.007, 0.847, 0.899],
    "大语言模型生成": [14.620, 14.175, 19.282],
}


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / f"{name}.png", bbox_inches="tight")
    fig.savefig(OUT / f"{name}.svg", bbox_inches="tight")
    plt.close(fig)


# Figure 1: QPS only, matching the retained overall table.
fig, ax = plt.subplots(figsize=(7.2, 4.2))
ax.plot(concurrency, qps, marker="o", linewidth=2.2, color="#2563eb")
ax.fill_between(concurrency, qps, alpha=0.12, color="#2563eb")
ax.set_title("并发数与请求吞吐量")
ax.set_xlabel("并发请求数")
ax.set_ylabel("QPS")
ax.set_xticks(concurrency)
ax.grid(True, alpha=0.25)
save(fig, "01-concurrency-qps")


# Figure 2: average TTFT and average complete response time.
fig, ax = plt.subplots(figsize=(7.2, 4.2))
ax.plot(concurrency, ttft_avg, marker="o", linewidth=2.2, label="TTFT平均", color="#f59e0b")
ax.plot(concurrency, total_avg, marker="o", linewidth=2.2, label="完整响应平均", color="#dc2626")
ax.set_title("并发数与平均响应时间")
ax.set_xlabel("并发请求数")
ax.set_ylabel("时间（秒）")
ax.set_xticks(concurrency)
ax.grid(True, alpha=0.25)
ax.legend(frameon=False)
save(fig, "02-average-latency")


# Figure 3: response percentiles from the retained overall table.
fig, ax = plt.subplots(figsize=(7.2, 4.2))
ax.plot(concurrency, response_p50, marker="o", linewidth=2.0, label="P50", color="#16a34a")
ax.plot(concurrency, response_p95, marker="o", linewidth=2.0, label="P95", color="#f59e0b")
ax.plot(concurrency, response_p99, marker="o", linewidth=2.0, label="P99", color="#dc2626")
ax.set_title("并发数与完整响应时间百分位")
ax.set_xlabel("并发请求数")
ax.set_ylabel("完整响应时间（秒）")
ax.set_xticks(concurrency)
ax.grid(True, alpha=0.25)
ax.legend(frameon=False)
save(fig, "03-response-percentiles")


def stage_chart(data, name, title):
    fig, ax = plt.subplots(figsize=(9.2, 5.0))
    labels = list(data)
    x = np.arange(len(labels))
    width = 0.24
    colors = ["#2563eb", "#f59e0b", "#dc2626"]
    for i, load in enumerate(loads):
        values = [data[label][i] for label in labels]
        ax.bar(x + (i - 1) * width, values, width, label=f"并发 {load}", color=colors[i])
    ax.set_title(title)
    ax.set_ylabel("平均耗时（秒）")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False, ncol=3)
    save(fig, name)


stage_chart(stage_avg, "04-stage-average-latency", "不同并发负载下各阶段平均耗时")
stage_chart(stage_p95, "05-stage-p95-latency", "不同并发负载下各阶段 P95 耗时")


# Figure 6: retrieval pipeline versus generation time.
# These are separately instrumented stage averages; they should not be summed
# as a substitute for the end-to-end response time because stages can overlap.
fig, ax = plt.subplots(figsize=(7.8, 4.6))
x = np.arange(len(loads))
width = 0.34
retrieval_total = np.array([5.863, 8.854, 8.512])
generation = np.array([7.521, 8.243, 11.367])
ax.bar(x - width / 2, retrieval_total, width, label="检索链路总耗时", color="#2563eb")
ax.bar(x + width / 2, generation, width, label="大语言模型生成", color="#dc2626")
ax.set_title("不同并发负载下检索与生成耗时对比")
ax.set_xlabel("并发负载")
ax.set_ylabel("平均耗时（秒）")
ax.set_xticks(x)
ax.set_xticklabels([f"并发 {load}" for load in loads])
ax.grid(axis="y", alpha=0.25)
ax.legend(frameon=False)
save(fig, "06-retrieval-vs-generation")

print(f"Generated figures in {OUT}")
