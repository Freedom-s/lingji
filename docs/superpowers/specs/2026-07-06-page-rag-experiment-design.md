# 页级多模态 RAG 检索实验方案设计

> 面向硕士学位论文的实验方案，涵盖检索链路消融实验和 Workflow vs Agentic 范式对比实验。

---

## 目录

1. [背景与实验目标](#1-背景与实验目标)
2. [测试集构造](#2-测试集构造)
3. [对比方法设计](#3-对比方法设计)
4. [评价指标体系](#4-评价指标体系)
5. [实验一：检索链路消融实验](#5-实验一检索链路消融实验)
6. [实验二：Workflow vs Agentic 范式对比](#6-实验二workflow-vs-agentic-范式对比)
7. [实验三：问题类型分层分析](#7-实验三问题类型分层分析)
8. [实施计划](#8-实施计划)

---

## 1. 背景与实验目标

### 1.1 系统概述

本系统采用**页级多模态 RAG（Page-level Multimodal RAG）**架构，核心设计思路：

- **检索单元**：每个课件页面作为一个不可分割的检索单元，不进行次级文本分块
- **多模态索引**：每页同时索引图片向量（`image_2048_vec`）、文本向量（`text_2048_vec`）和关键词（`content_ltks`）
- **混合检索**：三路并行召回 → RRF 融合 → Rerank 精排 → 上下页上下文召回
- **多模态生成**：检索到的页面截图通过 VLM（视觉语言模型）直接理解并生成答案

系统实现了两种检索范式：
- **Workflow 模式**：固定流水线，一次性检索
- **Agentic 模式**：基于 ReAct Agent，LLM 自主决策检索策略

### 1.2 实验目标

| 实验 | 核心问题 | 对应论文章节 |
|------|---------|------------|
| 实验一 | PAGE-RAG 检索链路中每个组件的独立贡献有多大？ | 检索方法验证 |
| 实验二 | Workflow 和 Agentic 两种范式在效果和效率上各有什么优劣？ | 范式对比分析 |
| 实验三 | 不同问题类型下，各组件的表现有何差异？ | 深度分析讨论 |

---

## 2. 测试集构造

### 2.1 数据来源

- **课件来源**：3-5 门课程，每门约 10+ 个 PPT 文件，总计约 200-500 页截图
- **Query 生成方式**：对每页截图调用 VLM，生成 1-3 个与该页内容相关的自然语言提问
- **数据规模**：约 3,000 条 query
- **Ground Truth**：每条 query 的标准答案页面 = 生成该 query 的原始页面 ID（单页 ground truth）

数据格式：
```json
{
  "id": "q001",
  "query": "什么是卷积神经网络？",
  "page_id": "abc123",
  "doc_id": "doc001",
  "doc_name": "深度学习基础.pptx",
  "course": "机器学习",
  "source_kb_id": "kb001"
}
```

### 2.2 Query 质量清洗

由于 3,000 条 query 由 VLM 自动生成且未经人工审核，需进行清洗：

| 清洗步骤 | 规则 | 预期剩余 |
|---------|------|---------|
| 精确去重 | 完全相同的 query 去重 | ~2,800 |
| 语义去重 | Embedding 相似度 > 0.95 的 query 对，保留一条 | ~2,600 |
| 长度过滤 | query < 5 字符或 > 200 字符的剔除 | ~2,500 |
| 泛问剔除 | 匹配"这一页讲了什么"、"介绍这一页"、"如图"等泛问模式 | ~2,400 |
| 非知识问题剔除 | 涉及排版/配色/设计而非知识内容的 query | ~2,300 |
| 人工抽查 | 每门课随机抽 30-50 条，校验 query 质量和 ground truth 正确性 | — |

### 2.3 分层抽样策略

从清洗后的有效 query 中抽取测试集：

| 层级 | 策略 | 说明 |
|------|------|------|
| 按课程 | 每门课等比例分配名额 | 确保课程覆盖面 |
| 按文档 | 每个 PPT 文件至少 10 条 | 确保文档覆盖面 |
| 总量 | 测试集 500 条 + Dev set 200 条 | Dev set 用于预实验调参，不纳入最终报告 |
| 人工核验 | 从 500 条中随机抽取 100 条人工验证 ground truth | 如错误率 > 5%，扩大核验范围 |

### 2.4 Ground Truth 补充标注

在人工核验 100 条的同时，额外标注：
- 该 query 是否存在**其他相关页面**（跨页情况）
- 如果有，记录额外相关页面的 page_id

此标注用于：
- 评估单页 ground truth 的局限性
- 为跨页问题的分析提供依据

---

## 3. 对比方法设计

### 3.1 实验组标识

| 编号 | 组名 | 检索配置 | 返回 Top-K | 所属实验 |
|------|------|---------|-----------|---------|
| G1 | 仅文本向量 | `text_2048_vec` 单路余弦检索 | 5 | 实验一 |
| G2 | 仅图片向量 | `image_2048_vec` 单路余弦检索 | 5 | 实验一 |
| G3 | 仅 BM25 | `content_ltks` 关键词检索 | 5 | 实验一 |
| G4 | 图片+文本 | 图片向量 + 文本向量 → RRF → Rerank | 3 | 实验一 |
| G5 | 图片+BM25 | 图片向量 + BM25 → RRF → Rerank | 3 | 实验一 |
| G6 | 三路-无RRF | 三路各自取 top 3，简单拼接去重，取前 5 | 5 | 实验一 |
| G7 | 三路-无Rerank | 三路 → RRF → 直接取 RRF top 3 | 3 | 实验一 |
| G8 | 三路-无上下文 | 完整链路但不做 context_recall | 3 | 实验一 |
| **G9** | **PAGE-RAG 完整** | 三路 → RRF → Rerank → context_recall | 3 | 实验一 |
| **WF** | **Workflow** | 同 G9，固定流水线单次执行 | 3 | 实验二 |
| **AG** | **Agentic** | ReAct Agent + 6 种工​​具自主决策 | 3（最终） | 实验二 |

### 3.2 Agentic 模式工具集

| 工具 | 功能 | Workflow 可用 | Agentic 可用 |
|------|------|:---:|:---:|
| `hybrid_retrieve` | 三路混合检索（等价于 G9） | ✅ 固定调用 | ✅ 可选 |
| `get_full_page` | 按 doc_id + 页码精确获取单页 | ❌ | ✅ |
| `get_adjacent_pages` | 获取某页的上下相邻页 | ❌ | ✅ |
| `list_documents` | 列出知识库中的文档列表 | ❌ | ✅ |
| `get_knowledge_structure` | 获取文档思维导图结构 | ❌ | ✅ |
| `web_search` | 联网搜索（Tavily API） | ❌ | ✅ |

### 3.3 统一实验参数

所有实验组共享以下参数，确保公平对比：

| 参数 | 值 | 说明 |
|------|-----|------|
| Embedding 模型 | 当前 KB 配置的模型 | 保持生产环境一致 |
| Rerank 模型 | 当前 Dialog 配置的模型 | 保持生产环境一致 |
| Embedding 维度 | 2048 | 与 ES 索引中 `image_2048_vec` / `text_2048_vec` 匹配 |
| RRF k 值 | 60 | 当前生产配置 |
| 各路检索 top_k | 50 | 各路宽召回后用 RRF 压缩 |
| RRF top_k | 5 | RRF 融合后的候选集大小 |
| Rerank top_k | 3 | 最终返回给 VLM 的页面数 |
| Rerank 相似度阈值 | 0.7 | 低于此阈值的页面被过滤 |
| Context recall 页数 | ±1 页 | 每个检索结果上下各召回 1 页 |
| Agentic 最大轮数 | 10 | ReAct 循环上限 |

---

## 4. 评价指标体系

### 4.1 检索质量指标

| 指标 | 定义 | 说明 |
|------|------|------|
| **Recall@1** | 相关页面在检索结果第 1 位的 query 占比 | 第一位命中率 |
| **Recall@3** | 相关页面在检索结果前 3 位的 query 占比 | **核心指标**——对应实际返回给 VLM 的 3 页 |
| **Recall@5** | 相关页面在检索结果前 5 位的 query 占比 | 对应 RRF 候选集大小 |
| **MRR** | `1/|Q| · Σ(1/rank)` | 首个相关页面的平均倒数排名 |
| **NDCG@5** | 归一化折损累积增益 | 考虑位置权重的排序质量 |

### 4.2 效率指标（实验二专用）

| 指标 | 计算方式 | 说明 |
|------|---------|------|
| 平均检索轮数 | Agentic LLM 调用工具的总轮次 / 总 query 数 | 是否过度检索 |
| 平均工具调用次数 | 所有工具调用总次数 / 总 query 数 | 每轮可能多工具并行 |
| 首轮命中率 | 第一轮检索即命中相关页面的 query 占比 | Agentic 首次检索的覆盖能力 |
| 端到端平均延迟 | 提交 query 到返回答案的时间（秒） | 含 LLM 推理 + 检索 + VLM 生成 |
| P50/P95 延迟 | 延迟的中位数和第 95 百分位 | 长尾延迟特征 |
| 无效检索率 | 检索了但最终未引用任何检索结果的 query 占比 | Agentic 是否做无用功 |

### 4.3 统计分析

| 方法 | 用途 | 实现 |
|------|------|------|
| 配对 t 检验 | 两组方法在所有 query 上的指标差异显著性 | `scipy.stats.ttest_rel` |
| 95% 置信区间 | 各指标点估计 ± 区间 | Bootstrap 或正态近似 |
| Cohen's d | 效应量（差异的实际大小） | `|mean_diff| / pooled_std` |
| Cohen's Kappa | LLM 自动标注与人工标注的一致性 | `sklearn.metrics.cohen_kappa_score` |

显著性水平：p < 0.05 为显著，p < 0.01 为高度显著。

### 4.4 问题类型分层维度（实验三专用）

#### 维度一：知识粒度

| 类型 | 定义 | 示例 |
|------|------|------|
| 单页事实 | 答案明确出现在某一页 | "Batch Normalization 的公式是什么？" |
| 单页概念 | 需要对一页内容做归纳总结 | "简述 ResNet 的核心思想" |
| 跨页综合 | 需要结合 2 页及以上 | "对比 SGD 和 Adam 的优缺点" |
| 全文档/课程 | 需要跨文档的宏观理解 | "这门课讲了哪些优化算法？" |

#### 维度二：认知层次（Bloom 分类法简化）

| 类型 | 定义 | 示例 |
|------|------|------|
| 记忆型 | 回忆事实、术语、定义 | "L2 正则化的全称是什么？" |
| 理解型 | 用自己的话解释概念 | "为什么 Dropout 能防止过拟合？" |
| 应用型 | 将知识用到具体场景 | "如果学习率设为 0.01，计算第 3 步的权重" |
| 分析型 | 比较、对比、推理 | "对比 Sigmoid 和 ReLU 的优劣" |

#### 维度三：内容模态

| 类型 | 定义 |
|------|------|
| 纯文本 | 答案仅依赖文字信息 |
| 公式/数学 | 涉及数学公式或推导 |
| 图表/流程图 | 答案依赖图表或流程图 |
| 代码/伪代码 | 涉及程序代码 |

---

## 5. 实验一：检索链路消融实验

### 5.1 实验目的

验证 PAGE-RAG 检索链路中每个组件的独立贡献：

1. 单路检索各自的检索能力如何？
2. 两路混合比单路好多少？三路比两路好多少？
3. RRF 融合比简单拼接好多少？
4. Rerank 精排对最终 top 3 的增益有多大？
5. 上下页召回的实际价值？

### 5.2 实验方法

对测试集 500 条 query，分别在 G1-G9 配置下运行检索，记录检索结果中的 page_id 列表，与 ground truth page_id 比对。

- 因检索是确定性的（无随机性），每组实验跑 1 次即可
- 每条 query 记录：检索到的 top 5 page_id 列表（按排序）、ground truth 所在位次

### 5.3 结果呈现模板

**主结果表：**

| 组名 | Recall@1 | Recall@3 | Recall@5 | MRR | NDCG@5 |
|------|----------|----------|----------|-----|--------|
| G1 仅文本向量 | | | | | |
| G2 仅图片向量 | | | | | |
| G3 仅 BM25 | | | | | |
| G4 图片+文本 | | | | | |
| G5 图片+BM25 | | | | | |
| G6 三路-无RRF | | | | | |
| G7 三路-无Rerank | | | | | |
| G8 三路-无上下文 | | | | | |
| **G9 完整 PAGE-RAG** | | | | | |

**消融增益分析（以 G9 为基准）：**

| 对比 | 移除的组件 | Recall@3 差值 | 说明 |
|------|-----------|-------------|------|
| G9 vs G8 | 上下文召回 | | 上下页召回贡献 |
| G9 vs G7 | Rerank 精排 | | Rerank 精排贡献（预期最大） |
| G9 vs G6 | RRF 融合 | | RRF vs 简单拼接 |
| G9 vs G4 | BM25 + 上下文 | | BM25 关键词检索增量 |
| G9 vs G5 | 文本向量 + 上下文 | | 文本向量增量 |
| G9 vs G1 | 图片+BM25+融合机制 | | 总体增益 |

**配对 t 检验矩阵（Recall@3，仅关键对比）：**

_仅展示有分析价值的对比对，不枚举全部 9×9 矩阵_

| 对比对 | 预期显著性 | 说明 |
|--------|-----------|------|
| G9 vs G1（完整 vs 仅文本） | p < .001 | 三路混合应大幅优于单路 |
| G9 vs G2（完整 vs 仅图片） | p < .001 | 同上 |
| G9 vs G3（完整 vs 仅 BM25） | p < .001 | 同上 |
| G9 vs G7（有无 Rerank） | p < .01 | Rerank 预期增益最大 |
| G9 vs G8（有无上下文） | p < .05 | 仅在部分跨页 query 上有差异 |
| G9 vs G6（有无 RRF） | p < .05 | 若各路重叠高，差异可能不显著 |
| G2 vs G1（图片 vs 文本） | 待验证 | 课件场景下图片向量可能更优 |
| G3 vs G1（BM25 vs 文本向量） | 待验证 | BM25 在专业术语上可能有优势 |

### 5.4 预期分析要点

**单路对比（G1 vs G2 vs G3）：**
- 课件场景下 G2（图片向量）可能优于 G1（文本向量）：VLM 生成 query 时看的是截图，语义偏向视觉特征；课件文本解析（尤其公式、表格）可能不完整
- G3（BM25）在精确术语匹配上可能有优势：如"卷积神经网络"在文本向量中可能被近似到"CNN"，而 BM25 可以精确命中

**多路增益：**
- 两路混合 > 单路：信息互补效应
- 三路 > 任意两路组合：三模态覆盖更全面

**RRF vs 简单拼接（G6 vs G9）：**
- 如果各路检索结果高度重叠（各路的 top 结果差不多），G6 和 G9 差异可能不显著
- RRF 的价值在于当各路对同一页面的排名不一致时，通过投票机制给出更稳健的综合排序

**Rerank 增益（G7 vs G9）：**
- Rerank 用专门的语义匹配模型替代向量余弦相似度，这是链路中最强的一环
- 预期增益在消融实验中最大
- 如果增益极小，需要检讨 rerank 模型配置或阈值设置

**上下文召回（G8 vs G9）：**
- 仅在答案跨页的 query 上有增益
- 对单页 query 可能引入噪音（无关的相邻页被加入）
- 需要按跨页/非跨页分层分析

---

## 6. 实验二：Workflow vs Agentic 范式对比

### 6.1 实验目的

对比两种检索范式在效果、效率、工具使用模式上的差异：

1. Agentic 多出的工具（翻页、文档浏览、知识结构）是否带来检索效果提升？
2. Agentic 是否有"过度检索"问题？
3. Agentic 的效率代价有多大？
4. Agentic 工具箱中哪些工具最有价值？

### 6.2 实验方法

- **WF 组**：对每条 query 调用 `chat()` 函数（或直接使用 G9 检索结果），记录检索到的页面 ID
- **AG 组**：对每条 query 调用 `AgentLoop.run()`，关闭流式输出，记录：
  - 每轮调用的工具及参数
  - 每轮检索到的页面 ID
  - 最终答案引用的页面 ID
  - 端到端耗时
- **最大检索轮数**：10
- **底层模型**：两组使用相同的 Embedding / Rerank / Chat 模型

### 6.3 结果呈现模板

#### 检索效果对比

| 指标 | Workflow | Agentic | Δ | p-value |
|------|----------|---------|---|---------|
| Recall@3 | | | | |
| MRR | | | | |
| 首轮命中率 | — | | | |
| Recall@5 | | | | |

#### 检索效率对比

| 指标 | Workflow | Agentic | 说明 |
|------|----------|---------|------|
| 平均检索轮数 | 1.0 | | Agentic 多轮次数 |
| 平均工具调用数 | 1.0 | | 每轮可能多工具并行 |
| 平均延迟 (s) | | | 端到端，含 LLM 推理 + 检索 |
| P50 延迟 (s) | | | 中位数用户感知延迟 |
| P95 延迟 (s) | | | 最差 5% 用户的延迟 |
| 无效检索率 | 0% | | 检索了但未引用 |

#### 检索轮数分布（Agentic 专属）

| 检索轮数 | Query 数 | 占比 | 累计 Recall@3 |
|---------|---------|------|-------------|
| 1 轮 | | | |
| 2 轮 | | | |
| 3 轮 | | | |
| 4 轮+ | | | |

#### 检索增益衰减（Agentic 专属）

| 轮数 | 该轮累计命中数 | 该轮新增命中 | 新增占比 |
|------|-------------|------------|---------|
| 第 1 轮 | | | — |
| 第 2 轮 | | | |
| 第 3 轮 | | | |
| 第 4 轮+ | | | |

**关键判断：如果第 2 轮后新增命中占比 < 5%，建议限制 Agentic 最大检索轮数为 2。**

#### 工具使用分析（Agentic 专属）

| 工具 | 调用次数 | 占比 | 命中率 | 平均每 query 调用 |
|------|---------|------|--------|-----------------|
| hybrid_retrieve | | | | |
| get_full_page | | | | |
| get_adjacent_pages | | | | |
| list_documents | | | | |
| get_knowledge_structure | | | | |
| web_search | | | | |

**命中率**：调用该工具后找到新相关页面的比例。

#### 工具调用序列分析（Agentic 专属）

常见工具调用序列模式（top 5）：

| 序列模式 | 出现次数 | 占比 | 典型场景 |
|---------|---------|------|---------|
| hybrid_retrieve → 回答 | | | 简单事实型 |
| hybrid_retrieve → get_adjacent_pages → 回答 | | | 跨页型 |
| hybrid_retrieve → list_documents → hybrid_retrieve → 回答 | | | 不确定在哪个文档 |

#### 问题类型分层对比

| 问题类型 | Workflow Recall@3 | Agentic Recall@3 | Δ | 分析 |
|---------|-------------------|------------------|-----|------|
| 单页事实 | | | | 预期持平 |
| 单页概念 | | | | 预期持平 |
| 跨页综合 | | | | **预期 Agentic 显著优** |
| 全文档 | | | | **预期 Agentic 显著优** |

### 6.4 预期分析要点

- **跨页问题**：Agentic 的核心优势场景。`get_adjacent_pages` 和多次检索覆盖跨页内容的能力应带来显著提升
- **简单事实型**：Workflow 一次检索已足够，Agentic 多轮可能浪费
- **效率代价**：Agentic 平均延迟可能是 Workflow 的 2-5 倍（多轮 LLM 推理 + 工具调用），需在实际应用价值与延迟代价间做权衡
- **工具使用效率**：预期 `hybrid_retrieve` 使用频率最高，`web_search` 和 `get_knowledge_structure` 使用较少但有不可替代的场景

---

## 7. 实验三：问题类型分层分析

### 7.1 实验目的

从问题本身特征出发，分析不同方法在不同问题类型上的表现差异：

1. PAGE-RAG 在不同问题类型上的优势和劣势分别是什么？
2. 三路检索各自的贡献如何随问题类型变化？
3. Agentic 的多工具能力在哪些场景真正有价值？

### 7.2 标注方法

对测试集 500 条 query 进行三维标注：

| 步骤 | 方法 | 说明 |
|------|------|------|
| Step 1 | LLM 自动初标 | 用 prompt 让 LLM 对每条 query 打三维标签 |
| Step 2 | 人工校验 | 从自动标注中每类抽 20 条（共约 150 条）人工验证 |
| Step 3 | 一致性检验 | 计算 Cohen's Kappa，如 > 0.8 接受自动标注；< 0.6 需优化 prompt 重标 |

### 7.3 结果呈现模板

#### 分析一：知识粒度 × 检索方法

| 知识粒度 | 占比 | G1 文本 Recall@3 | G2 图片 Recall@3 | G3 BM25 Recall@3 | G9 完整 Recall@3 | WF Recall@3 | AG Recall@3 |
|---------|------|----------------|----------------|----------------|----------------|------------|------------|
| 单页事实 | | | | | | | |
| 单页概念 | | | | | | | |
| 跨页综合 | | | | | | | |
| 全文档 | | | | | | | |

**关键预期**：
- 单页事实/概念：所有方法表现好，WF 和 AG 基本持平
- 跨页综合/全文档：整体 Recall 下降，但 AG 降幅应小于 WF（翻页工具起效）

#### 分析二：认知层次 × 检索方法

| 认知层次 | 占比 | G9 完整 Recall@3 | WF Recall@3 | AG Recall@3 |
|---------|------|----------------|------------|------------|
| 记忆型 | | | | |
| 理解型 | | | | |
| 应用型 | | | | |
| 分析型 | | | | |

**关键预期**：
- 记忆型 Recall 最高（答案明确在单页），预期 > 90%
- 分析型 Recall 最低（需要多页对比），但 AG 相对 WF 的增益应在分析型上最大

#### 分析三：内容模态 × 单路检索贡献

| 内容模态 | 占比 | G1 文本向量 Recall@3 | G2 图片向量 Recall@3 | G3 BM25 Recall@3 | G9 完整 Recall@3 |
|---------|------|---------------------|---------------------|------------------|----------------|
| 纯文本 | | | | | |
| 公式/数学 | | | | | |
| 图表/流程图 | | | | | |
| 代码/伪代码 | | | | | |

**关键预期**：
- 图表/流程图：G2（图片向量）应显著优于 G1 和 G3 → 这是论证"为什么需要图片向量检索"的核心证据
- 公式/数学：G3（BM25）可能有优势（精确符号匹配），G1（文本向量）因公式 OCR 不完整可能表现差
- 纯文本：G1 应最优

#### 分析四：Agentic 工具价值按问题类型

| 问题类型 | hybrid_retrieve 贡献 | get_adjacent_pages 贡献 | 其他工具贡献 |
|---------|---------------------|------------------------|------------|
| 单页事实 | 几乎全部 | 几乎 0 | 几乎 0 |
| 单页概念 | 几乎全部 | 几乎 0 | 极少 |
| 跨页综合 | 首次命中 | **显著** | 中等 |
| 全文档 | 中等 | **显著** | **显著** |

### 7.4 可视化建议

| 图表 | 类型 | 用途 |
|------|------|------|
| 问题三维分类分布 | 堆叠柱状图 | 展示知识粒度/认知层次/内容模态的分布 |
| 消融 Recall@3 对比 | 分组柱状图 | 9 组消融变体的 Recall@1/3/5 对比 |
| WF vs AG 对比 | 双柱对比图 | 两个范式在各类指标上的直观对比 |
| 单路检索贡献热力图 | 热力图 | 行=内容模态，列=检索路（文本/图片/BM25），颜色=Recall@3 |
| Agentic 检索增益衰减 | 折线图 | x=检索轮数，y=累计 Recall@3，标注新增命中占比 |
| 工具调用分布 | 饼图 | 各工具调用占比 |
| 工具调用流向 | 桑基图 | 首次工具 → 二次工具的转换模式 |
| 延迟分布对比 | 箱线图 | WF vs AG 端到端延迟分布 |

---

## 8. 实施计划

### 8.1 步骤概览

```
步骤 1：测试集构造与清洗（1 天）
   ├── 提取 3000 条 query 数据
   ├── 自动化清洗
   ├── 分层抽样 → test_set.jsonl + dev_set.jsonl
   └── 人工核验 100 条 ground truth
        ↓
步骤 2：问题类型标注（1-2 天）
   ├── LLM 自动标注 500 条
   ├── 人工校验 150 条
   └── 一致性检验（Cohen's Kappa）
        ↓
步骤 3：实验代码编写（1-2 天）
   ├── experiments/ 模块框架
   ├── 消融变体运行器
   ├── 指标计算 + 统计检验
   └── 报告生成
        ↓
步骤 4：运行实验（1-2 天）
   ├── 批量运行所有实验组
   ├── 收集结果数据
   └── 汇总
        ↓
步骤 5：数据分析与可视化（2-3 天）
   ├── 统计检验
   ├── 生成图表
   └── 撰写实验分析文字
```

### 8.2 实验代码架构

代码放在新的 `experiments/` 目录下，不污染生产代码：

```
ragflow-plus-version2/
├── experiments/
│   ├── __init__.py
│   ├── config.py                 # 实验参数配置
│   ├── test_set_loader.py        # 加载 test_set.jsonl
│   ├── variant_runner.py         # 消融变体运行器（G1-G9）
│   ├── workflow_runner.py        # Workflow 模式运行器
│   ├── agentic_runner.py         # Agentic 模式运行器
│   ├── metrics.py                # Recall@K, MRR, NDCG 计算
│   ├── statistical_tests.py      # t 检验, 置信区间, Cohen's d, Cohen's Kappa
│   ├── annotation.py             # LLM 自动标注问题类型
│   ├── report_generator.py       # 输出表格（LaTeX/Markdown）和图表
│   └── run_all_experiments.py    # 主入口，一键跑全部
```

**核心设计原则**：

- 消融变体通过参数化配置控制，不需要重新实现检索逻辑
- 复用现有 `rag/agent/server/tools.py` 中的 `_tool_vector_search_image`、`_tool_vector_search_text`、`_tool_keyword_search`、`_tool_rrf_fusion`、`_tool_rerank_pages`、`_tool_get_adjacent_pages`
- Agentic 模式复用 `rag/agent/client/loop.py` 的 `AgentLoop.run()`，关闭流式输出，收集实验数据

#### 消融变体运行器伪代码

```python
class VariantRunner:
    """通过参数化配置控制检索链路，一个类跑全部 9 个变体"""

    def __init__(self, config: VariantConfig, embd_mdl, rerank_mdl, dealer):
        self.config = config
        self.embd_mdl = embd_mdl
        self.rerank_mdl = rerank_mdl
        self.dealer = dealer

    def retrieve(self, query: str, tenant_ids: list[str], kb_ids: list[str]) -> list[dict]:
        results = []

        # 各检索路
        if self.config.use_text_vector:
            results.append(self._vector_search_text(query, tenant_ids, kb_ids))
        if self.config.use_image_vector:
            results.append(self._vector_search_image(query, tenant_ids, kb_ids))
        if self.config.use_bm25:
            results.append(self._keyword_search(query, tenant_ids, kb_ids))

        # 融合
        if len(results) == 1:
            merged = results[0]
        elif self.config.use_rrf:
            merged = self._rrf_fusion(results, k=self.config.rrf_k, top_k=self.config.rrf_topk)
        else:
            merged = self._simple_concat(results, top_k=self.config.rrf_topk)

        # 重排序
        if self.config.use_rerank and self.rerank_mdl:
            merged = self._rerank(query, merged, top_k=self.config.rerank_topk)

        # 上下文召回
        if self.config.use_context_recall:
            merged = self._context_recall(merged, tenant_ids, kb_ids)

        return merged[:self.config.final_topk]

    # 内部方法直接委托给 MCPToolExecutor 的对应方法
    def _vector_search_image(self, query, tenant_ids, kb_ids):
        return self.dealer._tool_vector_search_image(query, self.config.per_retrieval_topk,
                                                       tenant_ids, kb_ids)
    # ... 其余类似
```

#### 变体配置定义

```python
from dataclasses import dataclass

@dataclass
class VariantConfig:
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
    final_topk: int = 5

VARIANTS = {
    "G1": VariantConfig("仅文本向量", True, False, False, False, False, False),
    "G2": VariantConfig("仅图片向量", False, True, False, False, False, False),
    "G3": VariantConfig("仅BM25", False, False, True, False, False, False),
    "G4": VariantConfig("图片+文本", True, True, False, True, True, False),
    "G5": VariantConfig("图片+BM25", False, True, True, True, True, False),
    "G6": VariantConfig("三路-无RRF", True, True, True, False, True, False),
    "G7": VariantConfig("三路-无Rerank", True, True, True, True, False, False),
    "G8": VariantConfig("三路-无上下文", True, True, True, True, True, False),
    "G9": VariantConfig("PAGE-RAG完整", True, True, True, True, True, True),
}
```

#### 指标计算

```python
import numpy as np
from scipy import stats

def recall_at_k(results: list[dict], k: int) -> float:
    """计算 Recall@K"""
    hits = sum(1 for r in results
               if r['ground_truth_page_id'] in r['retrieved_page_ids'][:k])
    return hits / len(results)

def mrr(results: list[dict]) -> float:
    """计算 Mean Reciprocal Rank"""
    scores = []
    for r in results:
        try:
            rank = r['retrieved_page_ids'].index(r['ground_truth_page_id']) + 1
            scores.append(1.0 / rank)
        except ValueError:
            scores.append(0.0)
    return float(np.mean(scores))

def paired_ttest(scores_a: list[float], scores_b: list[float]) -> dict:
    """配对 t 检验 + Cohen's d"""
    t_stat, p_value = stats.ttest_rel(scores_a, scores_b)
    pooled_std = np.sqrt((np.var(scores_a) + np.var(scores_b)) / 2)
    cohens_d = abs(np.mean(scores_a) - np.mean(scores_b)) / pooled_std if pooled_std > 0 else 0
    return {
        "t_stat": float(t_stat),
        "p_value": float(p_value),
        "cohens_d": float(cohens_d),
        "significant": p_value < 0.05,
    }
```

### 8.3 运行实验

```bash
# 一键运行全部实验
cd experiments
python run_all_experiments.py \
    --test_set data/test_set.jsonl \
    --output_dir results/ \
    --variants all \
    --compare_modes both
```

输出目录结构：
```
results/
├── G1_text_vector_only.jsonl       # 每条 query 的检索结果
├── G2_image_vector_only.jsonl
├── ...
├── G9_full_page_rag.jsonl
├── workflow_baseline.jsonl
├── agentic_result.jsonl
├── annotations.jsonl               # 问题类型标注
├── summary.json                    # 汇总所有指标
├── tables/                         # LaTeX 表格
│   ├── ablation_main.tex
│   ├── paradigm_comparison.tex
│   └── stratified_analysis.tex
└── figures/                        # 图表
    ├── ablation_recall_barchart.png
    ├── paradigm_delay_boxplot.png
    ├── agentic_tool_usage_pie.png
    ├── agentic_gain_decay_line.png
    └── modality_heatmap.png
```

每条实验结果格式：
```json
{
  "variant": "G9",
  "query_id": "q001",
  "query": "什么是卷积神经网络？",
  "ground_truth_page_id": "abc123",
  "retrieved_page_ids": ["abc123", "def456", "ghi789"],
  "hit_at_rank": 1,
  "recall_1": true,
  "recall_3": true,
  "recall_5": true,
  "mrr_contrib": 1.0,
  "agentic_metadata": {
    "turns": 2,
    "tool_calls": ["hybrid_retrieve", "get_adjacent_pages"],
    "first_turn_hit": true,
    "tool_call_log": "..."
  }
}
```

### 8.4 时间线

| 阶段 | 任务 | 预估工时 | 累计 |
|------|------|---------|------|
| 测试集 | 清洗 + 抽样 + 人工核验 | 1 天 | 1 天 |
| 标注 | LLM 标注 + 人工校验 + 一致性检验 | 1-2 天 | 3 天 |
| 代码 | 实验模块编写 + 调通 | 1-2 天 | 5 天 |
| 运行 | 批量跑实验 + 收集数据 | 1-2 天 | 7 天 |
| 分析 | 统计检验 + 可视化 + 撰写分析 | 2-3 天 | 10 天 |

总计约 **2 周**（含缓冲），紧凑执行约 **1 周**。

### 8.5 风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| 消融实验中某些对比组差异不显著 | 论文说服力下降 | 在分层分析中找差异显著的子集；差异不显著本身也可作为发现（如 RRF vs 简单拼接在高度重叠时无差异，说明各模态检索结果一致性高） |
| Agentic 效果未显著优于 Workflow | 范式对比实验价值降低 | 转向效率分析——论证"简单问题不需要 Agentic"，为实际部署中的自适应路由提供依据 |
| 3000 条 query 清洗后有效数量不足 | 测试集规模偏小 | 降低抽样量（300 条也可），增加人工审核比例保证质量；或重新生成更多 query |
| LLM 标注与人工标注一致性低 | 分层分析可信度下降 | 缩小分层维度，或改为全人工标注（500 条约 2 人天） |
| Agentic 运行慢（每 query 数秒到数十秒） | 实验周期过长 | 先在小样本（100 条）上跑通，确认无 bug 后再全量运行；可并行执行 |

---

## 附录 A：论文实验章节大纲（建议）

```
第 X 章 实验设计与结果分析
├── X.1 实验设置
│   ├── X.1.1 测试集构造
│   ├── X.1.2 评价指标体系
│   ├── X.1.3 对比方法概述
│   └── X.1.4 实验环境与参数配置
├── X.2 实验一：检索链路消融实验
│   ├── X.2.1 单路检索对比
│   ├── X.2.2 多路混合增益分析
│   ├── X.2.3 RRF 融合与 Rerank 精排的影响
│   └── X.2.4 上下文召回的贡献
├── X.3 实验二：检索范式对比实验
│   ├── X.3.1 检索效果对比
│   ├── X.3.2 检索效率分析
│   ├── X.3.3 Agentic 工具使用分析
│   └── X.3.4 检索增益衰减分析
├── X.4 实验三：问题类型分层分析
│   ├── X.4.1 知识粒度维度分析
│   ├── X.4.2 认知层次维度分析
│   └── X.4.3 内容模态维度分析
├── X.5 综合讨论
│   ├── X.5.1 各组件贡献总结
│   ├── X.5.2 范式选择建议
│   └── X.5.3 局限性与未来工作
└── X.6 本章小结
```

---

## 附录 B：LLM 自动标注 Prompt 模板

```markdown
你是一个教育数据标注专家。请对以下学生提问进行分类。

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
  "modality": "纯文本|公式数学|图表流程图|代码伪代码"}}
```

---

> **文档状态**：待用户审核
> **创建日期**：2026-07-06
