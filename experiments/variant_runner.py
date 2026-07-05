"""Configurable retrieval variant runner that delegates to MCPToolExecutor."""
import logging
from typing import Any

from experiments.config import VariantConfig

logger = logging.getLogger("experiments.variant_runner")


class VariantRunner:
    """Run a single retrieval variant (G1-G9) against the test set.

    Delegates all actual retrieval work to MCPToolExecutor's internal
    methods. The variant config controls which methods are called and in
    what combination.

    Usage:
        from rag.agent.server.tools import MCPToolExecutor
        from rag.nlp.search import Dealer
        from rag.utils.es_conn import ESConnection

        dealer = Dealer(ESConnection())
        executor = MCPToolExecutor(dealer=dealer, embd_mdl=embd_mdl,
                                    rerank_mdl=rerank_mdl)
        runner = VariantRunner(VARIANTS["G9"], executor)
        pages = runner.retrieve("什么是卷积神经网络?", tenant_ids, kb_ids)
    """

    def __init__(self, config: VariantConfig, executor: Any):
        """
        Args:
            config: VariantConfig controlling which components to enable.
            executor: MCPToolExecutor instance with embd_mdl and rerank_mdl set.
        """
        self.config = config
        self.executor = executor

    def retrieve(
        self,
        query: str,
        tenant_ids: list[str],
        kb_ids: list[str],
    ) -> list[dict]:
        """Run the variant's retrieval pipeline.

        Args:
            query: User question text.
            tenant_ids: ES index tenant IDs (determines which indices to search).
            kb_ids: Knowledge base IDs (filter within indices).

        Returns:
            List of page dicts, each with keys: page_id, doc_id, docnm_kwd,
            kb_id, page_num_int, img_url, full_content, similarity/rrf_score/
            rerank_score.
        """
        cfg = self.config
        results: list[dict] = []

        # ── Step 1: Parallel retrieval paths ──
        result_sets: dict[str, dict] = {}

        if cfg.use_image_vector:
            result_sets["image"] = self.executor._tool_vector_search_image(
                query, cfg.per_retrieval_topk, tenant_ids, kb_ids,
            )
        if cfg.use_text_vector:
            result_sets["text"] = self.executor._tool_vector_search_text(
                query, cfg.per_retrieval_topk, tenant_ids, kb_ids,
            )
        if cfg.use_bm25:
            result_sets["keyword"] = self.executor._tool_keyword_search(
                query, cfg.per_retrieval_topk, tenant_ids, kb_ids,
            )

        # ── Step 2: Merge ──
        enabled = [k for k in ["image", "text", "keyword"] if k in result_sets]
        active_results = [result_sets[k] for k in enabled]

        if len(active_results) == 0:
            return []
        elif len(active_results) == 1:
            merged = active_results[0]
        else:
            if cfg.use_rrf:
                merged = self.executor._tool_rrf_fusion(
                    active_results, rrf_k=cfg.rrf_k, top_k=cfg.rrf_topk,
                )
            else:
                merged = self._simple_concat(active_results, top_k=cfg.final_topk)

        candidates = merged.get("chunks", [])

        # ── Step 3: Rerank ──
        if cfg.use_rerank and self.executor.rerank_mdl and candidates:
            reranked = self.executor._tool_rerank_pages(
                query, candidates,
                top_k=cfg.rerank_topk,
                similarity_threshold=cfg.rerank_similarity_threshold,
            )
            candidates = reranked.get("chunks", [])

        # Truncate to final_topk
        candidates = candidates[:cfg.final_topk]

        # ── Step 4: Context recall (adjacent pages) ──
        if cfg.use_context_recall and candidates:
            candidates = self._add_context_pages(candidates, tenant_ids, kb_ids)

        return candidates

    def _simple_concat(self, result_sets: list[dict], top_k: int = 5) -> dict:
        """Simple concatenation fusion (no RRF): take top from each, deduplicate."""
        seen: set[str] = set()
        chunks: list[dict] = []
        for rs in result_sets:
            for chunk in rs.get("chunks", []):
                pid = chunk.get("page_id", "")
                if pid and pid not in seen:
                    seen.add(pid)
                    chunks.append(dict(chunk))
                if len(chunks) >= top_k:
                    break
            if len(chunks) >= top_k:
                break
        return {"total": len(chunks), "chunks": chunks[:top_k]}

    def _add_context_pages(
        self,
        main_pages: list[dict],
        tenant_ids: list[str],
        kb_ids: list[str],
    ) -> list[dict]:
        """Add adjacent pages for each main page (context recall).

        Context pages are marked with is_context=True so consumers can
        distinguish them from direct retrieval results.
        """
        result: list[dict] = []
        seen: set[str] = set()

        for page in main_pages:
            pid = page.get("page_id", "")
            if pid not in seen:
                seen.add(pid)
                page_copy = dict(page)
                page_copy["is_context"] = False
                result.append(page_copy)

            doc_id = page.get("doc_id", "")
            page_num = page.get("page_num_int", 0)
            if not doc_id or not page_num:
                continue

            max_pages = self.config.context_recall_max_pages
            adj = self.executor._tool_get_adjacent_pages(
                doc_id=doc_id,
                page_num=page_num,
                direction="both",
                offset=max_pages,
                tenant_ids=tenant_ids,
                kb_ids=kb_ids,
            )
            for adj_page in adj.get("chunks", []):
                adj_pid = adj_page.get("page_id", "")
                if adj_pid and adj_pid not in seen:
                    seen.add(adj_pid)
                    adj_copy = dict(adj_page)
                    adj_copy["is_context"] = True
                    result.append(adj_copy)

        return result
