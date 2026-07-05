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
