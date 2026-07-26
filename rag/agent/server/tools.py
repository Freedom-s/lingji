"""
MCPToolExecutor: 检索工具的实际实现。

内部包含 12 个方法：向量检索 ×2、关键词检索、RRF 融合、重排序、相邻页面、联网搜索、混合检索、文档列表、完整页面、知识结构。
对外暴露 6 个工具，kb_ids / tenant_ids 由 AgentLoop 自动注入（不暴露给 LLM）。
"""

import json
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

logger = logging.getLogger("ragflow.agent.tools")


class MCPToolExecutor:
    """MCP 工具执行器：封装所有检索逻辑，每次调用自带 kb_ids / tenant_ids"""

    def __init__(self, dealer, embd_mdl=None, rerank_mdl=None, chat_mdl=None):
        self.dealer = dealer
        self.embd_mdl = embd_mdl
        self.rerank_mdl = rerank_mdl
        self.chat_mdl = chat_mdl

    # ── 辅助 ─────────────────────────────────────────────────

    @staticmethod
    def _ensure_string_list(val, default=None) -> list[str]:
        if isinstance(val, str):
            return [val]
        if isinstance(val, list):
            return [str(v) for v in val]
        return default or []

    @staticmethod
    def _build_result(chunks: list) -> dict:
        return {"total": len(chunks), "chunks": chunks}

    @staticmethod
    def _build_error(msg: str) -> dict:
        return {"error": msg, "total": 0, "chunks": []}

    # ── 图片向量检索 ───────────────────────────────────────

    def _tool_vector_search_image(self, query: str, top_k: int,
                                  tenant_ids: list[str], kb_ids: list[str]) -> dict:
        if not self.embd_mdl or not self.dealer:
            return self._build_error("embedding 模型或 ES Dealer 不可用")
        try:
            from rag.utils.doc_store_conn import MatchDenseExpr, OrderByExpr
            from rag.nlp.search import index_name, tenant_id_from_index

            qv = self.embd_mdl.encode_queries(query)
            embedding_data = [float(v) for v in qv[0]]
            vector_dim = len(embedding_data)
            vector_column = f"image_{vector_dim}_vec"

            src = ["page_id", "doc_id", "docnm_kwd", "kb_id", "page_num_int", "img_url", "content_with_weight"]
            match_dense = MatchDenseExpr(vector_column, embedding_data, "float", "cosine", top_k, {})

            sres = self.dealer.dataStore.search(
                src, [], {}, [match_dense], OrderByExpr(),
                0, top_k, [index_name(tid) for tid in tenant_ids], kb_ids,
            )

            return self._parse_es_chunks(sres, src)
        except Exception as e:
            logger.error(f"vector_search_image error: {e}")
            return self._build_error(str(e))

    # ── 文本向量检索 ───────────────────────────────────────

    def _tool_vector_search_text(self, query: str, top_k: int,
                                  tenant_ids: list[str], kb_ids: list[str]) -> dict:
        if not self.embd_mdl or not self.dealer:
            return self._build_error("embedding 模型或 ES Dealer 不可用")
        try:
            from rag.utils.doc_store_conn import MatchDenseExpr, OrderByExpr
            from rag.nlp.search import index_name, tenant_id_from_index

            qv = self.embd_mdl.encode_queries(query)
            embedding_data = [float(v) for v in qv[0]]
            vector_dim = len(embedding_data)
            vector_column = f"text_{vector_dim}_vec"

            src = ["page_id", "doc_id", "docnm_kwd", "kb_id", "page_num_int", "img_url", "content_with_weight"]
            match_dense = MatchDenseExpr(vector_column, embedding_data, "float", "cosine", top_k, {})

            sres = self.dealer.dataStore.search(
                src, [], {}, [match_dense], OrderByExpr(),
                0, top_k, [index_name(tid) for tid in tenant_ids], kb_ids,
            )

            return self._parse_es_chunks(sres, src)
        except Exception as e:
            logger.error(f"vector_search_text error: {e}")
            return self._build_error(str(e))

    # ── 关键词检索 (BM25) ───────────────────────────────────

    def _tool_keyword_search(self, query: str, top_k: int,
                              tenant_ids: list[str], kb_ids: list[str]) -> dict:
        if not self.dealer:
            return self._build_error("ES Dealer 不可用")
        try:
            from rag.utils.doc_store_conn import MatchTextExpr, OrderByExpr
            from rag.nlp.search import index_name, tenant_id_from_index

            src = ["page_id", "doc_id", "docnm_kwd", "kb_id", "page_num_int", "img_url", "content_with_weight"]

            try:
                from management.server.services.knowledgebases.jieba_tokenizer import get_tokenizer
                tknzr = get_tokenizer()
                keywords = tknzr.tokenize(query)
            except Exception:
                keywords = query.split()

            match_text = MatchTextExpr(
                fields=["content_ltks"], matching_text=keywords, topn=top_k,
                extra_options={"minimum_should_match": "25%", "boost": 1.0},
            )

            sres = self.dealer.dataStore.search(
                src, [], {}, [match_text], OrderByExpr(),
                0, top_k, [index_name(tid) for tid in tenant_ids], kb_ids,
            )

            return self._parse_es_chunks(sres, src)
        except Exception as e:
            logger.error(f"keyword_search error: {e}")
            return self._build_error(str(e))

    # ── ES 结果解析 ───────────────────────────────────────

    def _parse_es_chunks(self, sres, src) -> dict:
        from rag.nlp.search import tenant_id_from_index
        chunks = []
        ids = self.dealer.dataStore.getChunkIds(sres)
        fields = self.dealer.dataStore.getFields(sres, src)
        for chunk_id in ids:
            chunk = fields.get(chunk_id, {})
            chunks.append({
                "page_id": chunk.get("page_id", chunk_id),
                "doc_id": chunk.get("doc_id", ""),
                "kb_id": chunk.get("kb_id", ""),
                "docnm_kwd": chunk.get("docnm_kwd", ""),
                "page_num_int": chunk.get("page_num_int", 0),
                "img_url": chunk.get("img_url", ""),
                "full_content": chunk.get("content_with_weight", ""),
                "similarity": float(chunk.get("_score", 0.0)),
                "tenant_id": tenant_id_from_index(chunk.get("_index", "")),
            })
        return self._build_result(chunks)

    # ── RRF 融合 ───────────────────────────────────────────

    def _tool_rrf_fusion(self, result_sets: list[dict], rrf_k: int = 60, top_k: int = 5) -> dict:
        try:
            rrf_scores: dict[str, float] = defaultdict(float)
            page_data: dict[str, dict] = {}
            for rs in result_sets:
                chunks = rs.get("chunks", []) if isinstance(rs, dict) else []
                for rank, chunk in enumerate(chunks, start=1):
                    pid = chunk.get("page_id", "")
                    if not pid:
                        continue
                    rrf_scores[pid] += 1.0 / (rrf_k + rank)
                    if pid not in page_data:
                        page_data[pid] = dict(chunk)
            sorted_pages = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
            chunks = []
            for pid, score in sorted_pages[:top_k]:
                entry = dict(page_data.get(pid, {}))
                entry["rrf_score"] = round(score, 6)
                chunks.append(entry)
            return self._build_result(chunks)
        except Exception as e:
            logger.error(f"rrf_fusion error: {e}")
            return self._build_error(str(e))

    # ── 重排序 ────────────────────────────────────────────

    def _tool_rerank_pages(self, query: str, candidate_pages: list[dict],
                           top_k: int = 3, similarity_threshold: float = 0.5) -> dict:
        if not self.rerank_mdl:
            return self._build_result(candidate_pages[:top_k])
        try:
            texts = [p.get("full_content", "") for p in candidate_pages]
            scores = self.rerank_mdl.similarity(query, texts)
            scored = list(zip(candidate_pages, scores))
            scored.sort(key=lambda x: x[1], reverse=True)
            chunks = []
            for page, score in scored[:top_k]:
                if score < similarity_threshold:
                    continue
                entry = dict(page)
                entry["rerank_score"] = round(float(score), 6)
                chunks.append(entry)
            return self._build_result(chunks)
        except Exception as e:
            logger.error(f"rerank_pages error: {e}")
            return self._build_result(candidate_pages[:top_k])

    # ── 相邻页面 ──────────────────────────────────────────

    def _tool_get_adjacent_pages(self, doc_id: str, page_num: int,
                                  direction: str = "both", offset: int = 1,
                                  tenant_ids: list[str] = None, kb_ids: list[str] = None) -> dict:
        if not self.dealer:
            return self._build_error("ES Dealer 不可用")
        try:
            from rag.utils.doc_store_conn import OrderByExpr
            from rag.nlp.search import index_name

            tenant_ids = self._ensure_string_list(tenant_ids, [])
            kb_ids = self._ensure_string_list(kb_ids, [])

            if direction == "both":
                page_range = (max(1, page_num - offset), page_num + offset)
            elif direction == "prev":
                page_range = (max(1, page_num - offset), page_num - 1)
            elif direction == "next":
                page_range = (page_num + 1, page_num + offset)
            else:
                return self._build_error(f"未知的 direction: {direction}")

            src = ["page_id", "doc_id", "docnm_kwd", "kb_id", "page_num_int", "img_url", "content_with_weight"]
            condition = {"doc_id": doc_id, "page_num_int": list(range(page_range[0], page_range[1] + 1))}

            sres = self.dealer.dataStore.search(
                src, [], condition, [], OrderByExpr(),
                0, offset * 2 + 2,
                [index_name(tid) for tid in tenant_ids], kb_ids,
            )

            chunks = []
            ids = self.dealer.dataStore.getChunkIds(sres)
            fields = self.dealer.dataStore.getFields(sres, src)
            for chunk_id in ids:
                chunk = fields.get(chunk_id, {})
                chunks.append({
                    "page_id": chunk.get("page_id", chunk_id),
                    "doc_id": chunk.get("doc_id", ""),
                    "kb_id": chunk.get("kb_id", ""),
                    "docnm_kwd": chunk.get("docnm_kwd", ""),
                    "page_num_int": chunk.get("page_num_int", 0),
                    "img_url": chunk.get("img_url", ""),
                    "full_content": chunk.get("content_with_weight", ""),
                })
            return self._build_result(chunks)
        except Exception as e:
            logger.error(f"get_adjacent_pages error: {e}")
            return self._build_error(str(e))

    # ── 混合检索 ───────────────────────────────────────────

    def _tool_hybrid_retrieve(self, query: str, rerank_topk: int = 3,
                               image_topk: int = 50, text_topk: int = 50,
                               keyword_topk: int = 50, rrf_topk: int = 5,
                               tenant_ids: list[str] = None, kb_ids: list[str] = None) -> dict:
        """三路并行检索 → RRF 融合 → 重排序"""
        tenant_ids = self._ensure_string_list(tenant_ids, [])
        kb_ids = self._ensure_string_list(kb_ids, [])

        results: dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self._tool_vector_search_image, query, image_topk, tenant_ids, kb_ids): "image",
                executor.submit(self._tool_vector_search_text, query, text_topk, tenant_ids, kb_ids): "text",
                executor.submit(self._tool_keyword_search, query, keyword_topk, tenant_ids, kb_ids): "keyword",
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception as e:
                    logger.error(f"hybrid_retrieve: {name} 检索失败: {e}")
                    results[name] = {"total": 0, "chunks": []}

        result_sets = [
            {"chunks": results.get("image", {}).get("chunks", []), "query": f"image:{query}"},
            {"chunks": results.get("text", {}).get("chunks", []), "query": f"text:{query}"},
            {"chunks": results.get("keyword", {}).get("chunks", []), "query": f"keyword:{query}"},
        ]
        rrf_result = self._tool_rrf_fusion(result_sets, rrf_k=60, top_k=rrf_topk)

        rrf_chunks = rrf_result.get("chunks", [])
        if rrf_chunks and self.rerank_mdl:
            return self._tool_rerank_pages(query, rrf_chunks, top_k=rerank_topk, similarity_threshold=0.7)
        return rrf_result

    # ── 联网搜索 ───────────────────────────────────────────

    def _tool_web_search(self, query: str, max_results: int = 5) -> dict:
        api_key = "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"
        try:
            import requests
            params: dict = {
                "api_key": api_key, "query": query,
                "max_results": max(max_results, 1), "search_depth": "advanced",
            }
            resp = requests.post("https://api.tavily.com/search", json=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            chunks = [{
                "title": r.get("title", ""), "url": r.get("url", ""),
                "content": (r.get("content", "") or ""), "score": r.get("score", 0.0),
            } for r in data.get("results", [])]
            return {"total": len(chunks), "chunks": chunks, "response_time": data.get("response_time", 0)}
        except Exception as e:
            logger.error(f"web_search error: {e}")
            return self._build_error(str(e))

    # ── 列出文档 ───────────────────────────────────────────

    def _tool_list_documents(self, kb_ids: list[str] = None) -> dict:
        kb_ids = self._ensure_string_list(kb_ids, [])
        if not kb_ids:
            return {"total": 0, "documents": []}
        try:
            from api.db.db_models import Document, Knowledgebase

            kb_name_map = {
                k.id: k.name or ""
                for k in Knowledgebase.select(Knowledgebase.id, Knowledgebase.name).where(Knowledgebase.id.in_(kb_ids))
            }

            documents = []
            for kb_id in kb_ids:
                rows = list(Document.select(Document.id, Document.name, Document.kb_id).where(Document.kb_id == kb_id))
                if not rows:
                    continue

                doc_ids = [r.id for r in rows]
                from api.db.db_models import File2Document, FilePage
                from peewee import fn as peewee_fn

                f2d = list(File2Document.select(File2Document.document_id, File2Document.file_id).where(File2Document.document_id.in_(doc_ids)))
                doc_file_map: dict[str, list[str]] = {}
                file_ids = set()
                for f in f2d:
                    doc_file_map.setdefault(f.document_id, []).append(f.file_id)
                    file_ids.add(f.file_id)

                file_page_map: dict[str, int] = {}
                if file_ids:
                    pc_rows = list(
                        FilePage.select(FilePage.file_id, peewee_fn.COUNT(FilePage.id).alias("cnt"))
                        .where(FilePage.file_id.in_(list(file_ids)))
                        .group_by(FilePage.file_id)
                    )
                    file_page_map = {r.file_id: r.cnt or 0 for r in pc_rows}

                for r in rows:
                    page_count = sum(file_page_map.get(fid, 0) for fid in doc_file_map.get(r.id, []))
                    documents.append({
                        "doc_id": r.id, "doc_name": r.name or "",
                        "kb_id": kb_id, "kb_name": kb_name_map.get(kb_id, kb_id),
                        "page_count": page_count,
                    })

            documents.sort(key=lambda x: x["doc_name"])
            return {"total": len(documents), "documents": documents}
        except Exception as e:
            logger.error(f"list_documents error: {e}")
            return self._build_error(str(e))

    # ── 完整页面 ───────────────────────────────────────────

    def _tool_get_full_page(self, doc_id: str, page_num: int,
                             tenant_ids: list[str] = None, kb_ids: list[str] = None) -> dict:
        if not self.dealer:
            return self._build_error("ES Dealer 不可用")
        try:
            from rag.utils.doc_store_conn import OrderByExpr
            from rag.nlp.search import index_name

            tenant_ids = self._ensure_string_list(tenant_ids, [])
            kb_ids = self._ensure_string_list(kb_ids, [])

            src = ["page_id", "doc_id", "docnm_kwd", "kb_id", "page_num_int", "img_url", "content_with_weight"]
            condition = {"doc_id": doc_id, "page_num_int": [page_num]}

            sres = self.dealer.dataStore.search(
                src, [], condition, [], OrderByExpr(),
                0, 1, [index_name(tid) for tid in tenant_ids], kb_ids,
            )

            ids = self.dealer.dataStore.getChunkIds(sres)
            if not ids:
                return self._build_error(f"未找到文档 {doc_id} 第 {page_num} 页")

            fields = self.dealer.dataStore.getFields(sres, src)
            chunk = fields.get(ids[0], {})
            return self._build_result([{
                "page_id": chunk.get("page_id", ids[0]),
                "doc_id": chunk.get("doc_id", ""),
                "docnm_kwd": chunk.get("docnm_kwd", ""),
                "kb_id": chunk.get("kb_id", ""),
                "page_num_int": chunk.get("page_num_int", 0),
                "full_content": chunk.get("content_with_weight", ""),
                "img_url": chunk.get("img_url", ""),
            }])
        except Exception as e:
            logger.error(f"get_full_page error: {e}")
            return self._build_error(str(e))

    # ── 知识结构 ───────────────────────────────────────────

    def _tool_get_knowledge_structure(self, doc_id: str) -> dict:
        try:
            from api.db.db_models import DocumentGeneration

            row = (
                DocumentGeneration.select()
                .where(DocumentGeneration.doc_id == doc_id, DocumentGeneration.generation_type == "mindmap")
                .first()
            )
            if not row:
                return {"doc_id": doc_id, "mindmap": None}
            try:
                mindmap = json.loads(row.content)
            except (json.JSONDecodeError, TypeError):
                mindmap = {"raw": row.content}
            return {"doc_id": doc_id, "mindmap": mindmap}
        except Exception as e:
            logger.error(f"get_knowledge_structure error: {e}")
            return self._build_error(str(e))
