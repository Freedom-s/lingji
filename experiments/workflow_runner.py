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
