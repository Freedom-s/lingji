"""
MCPToolExecutor: 检索工具的实际实现。

对外暴露 3 个工具（hybrid_retrieve / web_search / get_adjacent_pages），
内部包含 8 个方法：向量检索 ×2、关键词检索、RRF 融合、重排序、相邻页面、联网搜索、混合检索。
"""

import json
import logging
import math
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import ContextVar
from typing import Any

logger = logging.getLogger("ragflow.agent.tools")

# ContextVars 保存跨请求的 ES 上下文（由 mcp_server.py 的 /initialize 设置）
_current_tenant_ids: ContextVar[list[str]] = ContextVar("tenant_ids", default=[])
_current_kb_ids: ContextVar[list[str]] = ContextVar("kb_ids", default=[])


class MCPToolExecutor:
    """MCP 工具执行器：封装所有检索逻辑"""

    def __init__(self, dealer, embd_mdl=None, rerank_mdl=None, chat_mdl=None):
        """
        Args:
            dealer: rag.nlp.search.Dealer 实例（ES 查询委托器）
            embd_mdl: Embedding 模型实例
            rerank_mdl: Rerank 模型实例
            chat_mdl: Chat 模型实例（用于 VLM 页面评估）
        """
        self.dealer = dealer
        self.embd_mdl = embd_mdl
        self.rerank_mdl = rerank_mdl
        self.chat_mdl = chat_mdl

        self.tenant_ids: list[str] = _current_tenant_ids.get()
        self.kb_ids: list[str] = _current_kb_ids.get()

    def set_context(self, tenant_ids: list[str], kb_ids: list[str]):
        """更新 ES 查询上下文（租户 ID 和知识库 ID）"""
        self.tenant_ids = tenant_ids
        self.kb_ids = kb_ids
        _current_tenant_ids.set(tenant_ids)
        _current_kb_ids.set(kb_ids)

    # ── 辅助方法 ─────────────────────────────────────────────

    def _ensure_string_list(self, val, default=None) -> list[str]:
        if isinstance(val, str):
            return [val]
        if isinstance(val, list):
            return [str(v) for v in val]
        return default or []

    def _build_result(self, chunks: list) -> dict:
        return {"total": len(chunks), "chunks": chunks}

    def _build_error(self, msg: str) -> dict:
        return {"error": msg, "total": 0, "chunks": []}

    # ── Tool 1: 图片向量检索 ─────────────────────────────────

    def _tool_vector_search_image(self, query: str, top_k: int = 50) -> dict:
        if not self.embd_mdl or not self.dealer:
            return self._build_error("embedding 模型或 ES Dealer 不可用")

        try:
            from rag.utils.doc_store_conn import MatchDenseExpr, OrderByExpr
            from rag.nlp.search import index_name, tenant_id_from_index

            tenant_ids = self._ensure_string_list(self.tenant_ids, [])
            kb_ids = self._ensure_string_list(self.kb_ids, [])

            qv = self.embd_mdl.encode_queries(query)
            embedding_data = [float(v) for v in qv[0]]
            vector_dim = len(embedding_data)
            vector_column = f"image_{vector_dim}_vec"

            src = ["page_id", "doc_id", "docnm_kwd", "kb_id", "page_num_int", "img_url", "content_with_weight"]
            match_dense = MatchDenseExpr(vector_column, embedding_data, "float", "cosine", top_k, {})

            sres = self.dealer.dataStore.search(
                src, [], {}, [match_dense], OrderByExpr(),
                0, top_k,
                [index_name(tid) for tid in tenant_ids],
                kb_ids,
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
                    "content_with_weight": chunk.get("content_with_weight", ""),
                    "similarity": float(chunk.get("_score", 0.0)),
                    "tenant_id": tenant_id_from_index(chunk.get("_index", "")),
                })

            return self._build_result(chunks)
        except Exception as e:
            logger.error(f"vector_search_image error: {e}")
            return self._build_error(str(e))

    # ── Tool 2: 文本向量检索 ─────────────────────────────────

    def _tool_vector_search_text(self, query: str, top_k: int = 50) -> dict:
        if not self.embd_mdl or not self.dealer:
            return self._build_error("embedding 模型或 ES Dealer 不可用")

        try:
            from rag.utils.doc_store_conn import MatchDenseExpr, OrderByExpr
            from rag.nlp.search import index_name, tenant_id_from_index

            tenant_ids = self._ensure_string_list(self.tenant_ids, [])
            kb_ids = self._ensure_string_list(self.kb_ids, [])

            qv = self.embd_mdl.encode_queries(query)
            embedding_data = [float(v) for v in qv[0]]
            vector_dim = len(embedding_data)
            vector_column = f"text_{vector_dim}_vec"

            src = ["page_id", "doc_id", "docnm_kwd", "kb_id", "page_num_int", "img_url", "content_with_weight"]
            match_dense = MatchDenseExpr(vector_column, embedding_data, "float", "cosine", top_k, {})

            sres = self.dealer.dataStore.search(
                src, [], {}, [match_dense], OrderByExpr(),
                0, top_k,
                [index_name(tid) for tid in tenant_ids],
                kb_ids,
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
                    "content_with_weight": chunk.get("content_with_weight", ""),
                    "similarity": float(chunk.get("_score", 0.0)),
                    "tenant_id": tenant_id_from_index(chunk.get("_index", "")),
                })

            return self._build_result(chunks)
        except Exception as e:
            logger.error(f"vector_search_text error: {e}")
            return self._build_error(str(e))

    # ── Tool 3: 关键词检索 (BM25) ──────────────────────────────

    def _tool_keyword_search(self, query: str, top_k: int = 50) -> dict:
        if not self.dealer:
            return self._build_error("ES Dealer 不可用")

        try:
            from rag.utils.doc_store_conn import MatchTextExpr, OrderByExpr
            from rag.nlp.search import index_name, tenant_id_from_index

            tenant_ids = self._ensure_string_list(self.tenant_ids, [])
            kb_ids = self._ensure_string_list(self.kb_ids, [])

            src = ["page_id", "doc_id", "docnm_kwd", "kb_id", "page_num_int", "img_url", "content_with_weight"]

            # jieba 分词
            try:
                from management.server.services.knowledgebases.jieba_tokenizer import get_tokenizer
                tknzr = get_tokenizer()
                keywords = tknzr.tokenize(query)
            except Exception:
                # 如果 jieba 不可用，回退到简单空格分词
                keywords = query.split()

            match_text = MatchTextExpr(
                fields=["content_ltks"],
                matching_text=keywords,
                topn=top_k,
                extra_options={"minimum_should_match": "25%", "boost": 1.0},
            )

            sres = self.dealer.dataStore.search(
                src, [], {}, [match_text], OrderByExpr(),
                0, top_k,
                [index_name(tid) for tid in tenant_ids],
                kb_ids,
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
                    "content_with_weight": chunk.get("content_with_weight", ""),
                    "similarity": float(chunk.get("_score", 0.0)),
                    "tenant_id": tenant_id_from_index(chunk.get("_index", "")),
                })

            return self._build_result(chunks)
        except Exception as e:
            logger.error(f"keyword_search error: {e}")
            return self._build_error(str(e))

    # ── Tool 4: RRF 融合 ──────────────────────────────────────

    def _tool_rrf_fusion(self, result_sets: list[dict], rrf_k: int = 60, top_k: int = 5) -> dict:
        """
        RRF (Reciprocal Rank Fusion) 融合多个检索结果集

        Args:
            result_sets: [{"chunks": [...], "query": ""}, ...]
            rrf_k: RRF 平滑参数
            top_k: 返回 Top K 结果
        """
        try:
            # page_id → RRF 分数累加
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

            # 按 RRF 分数降序排序
            sorted_pages = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
            top_pages = sorted_pages[:top_k]

            chunks = []
            for pid, score in top_pages:
                entry = dict(page_data.get(pid, {}))
                entry["rrf_score"] = round(score, 6)
                chunks.append(entry)

            return self._build_result(chunks)
        except Exception as e:
            logger.error(f"rrf_fusion error: {e}")
            return self._build_error(str(e))

    # ── Tool 5: 多模态重排序 ──────────────────────────────────

    def _tool_rerank_pages(
        self,
        query: str,
        candidate_pages: list[dict],
        top_k: int = 3,
        similarity_threshold: float = 0.5,
    ) -> dict:
        if not self.rerank_mdl:
            logger.warning("rerank 模型不可用，返回原始候选")
            return self._build_result(candidate_pages[:top_k])

        try:
            from rag.nlp.search import convert_minio_url_to_base64

            img_urls = []
            for page in candidate_pages:
                url = page.get("img_url", "")
                if url.startswith("minio://"):
                    base64_url = convert_minio_url_to_base64(url)
                    img_urls.append(base64_url or "")
                else:
                    img_urls.append(url)

            texts = [p.get("content_with_weight", "") for p in candidate_pages]
            scores = self.rerank_mdl.similarity(query, texts, img_urls)

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

    # ── Tool 6: 获取相邻页面 ──────────────────────────────────

    def _tool_get_adjacent_pages(
        self,
        doc_id: str,
        page_num: int,
        direction: str = "both",
        offset: int = 1,
    ) -> dict:
        if not self.dealer:
            return self._build_error("ES Dealer 不可用")

        try:
            from rag.utils.doc_store_conn import OrderByExpr
            from rag.nlp.search import index_name

            tenant_ids = self._ensure_string_list(self.tenant_ids, [])
            kb_ids = self._ensure_string_list(self.kb_ids, [])

            if direction == "both":
                page_range = (page_num - offset, page_num + offset)
                page_range = (max(1, page_range[0]), page_range[1])
            elif direction == "prev":
                page_range = (max(1, page_num - offset), page_num - 1)
            elif direction == "next":
                page_range = (page_num + 1, page_num + offset)
            else:
                return self._build_error(f"未知的 direction: {direction}")

            src = ["page_id", "doc_id", "docnm_kwd", "kb_id", "page_num_int", "img_url", "content_with_weight"]

            condition = {
                "doc_id": doc_id,
                "page_num_int": list(range(page_range[0], page_range[1] + 1)),
            }

            sres = self.dealer.dataStore.search(
                src, [], condition, [], OrderByExpr(),
                0, offset * 2 + 2,
                [index_name(tid) for tid in tenant_ids],
                kb_ids,
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
                    "content_with_weight": chunk.get("content_with_weight", ""),
                    "similarity": float(chunk.get("_score", 0.0)),
                })

            return self._build_result(chunks)
        except Exception as e:
            logger.error(f"get_adjacent_pages error: {e}")
            return self._build_error(str(e))

    # ── Tool 7: VLM 页面相关性评估 ─────────────────────────────

    # ── 一键混合检索 ──────────────────────────────────────────

    def _tool_hybrid_retrieve(
        self,
        query: str,
        image_topk: int = 50,
        text_topk: int = 50,
        keyword_topk: int = 50,
        rrf_topk: int = 5,
        rerank_topk: int = 3,
    ) -> dict:
        """
        三路并行检索 → RRF 融合 → 重排序
        """
        # 三路并行检索
        results: dict[str, dict] = {}

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(
                    self._tool_vector_search_image, query, image_topk,
                ): "image",
                executor.submit(
                    self._tool_vector_search_text, query, text_topk,
                ): "text",
                executor.submit(
                    self._tool_keyword_search, query, keyword_topk,
                ): "keyword",
            }

            for future in as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception as e:
                    logger.error(f"hybrid_retrieve: {name} 检索失败: {e}")
                    results[name] = {"total": 0, "chunks": []}

        # RRF 融合
        result_sets = [
            {"chunks": results.get("image", {}).get("chunks", []), "query": f"image:{query}"},
            {"chunks": results.get("text", {}).get("chunks", []), "query": f"text:{query}"},
            {"chunks": results.get("keyword", {}).get("chunks", []), "query": f"keyword:{query}"},
        ]

        rrf_result = self._tool_rrf_fusion(result_sets, rrf_k=60, top_k=rrf_topk)

        # 重排序
        rrf_chunks = rrf_result.get("chunks", [])
        if rrf_chunks and self.rerank_mdl:
            reranked = self._tool_rerank_pages(query, rrf_chunks, top_k=rerank_topk, similarity_threshold=0.3)
            return reranked

        return rrf_result

    # ── Tool 9: Tavily 联网搜索 ───────────────────────────────

    def _tool_web_search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> dict:
        """
        使用 Tavily API 进行联网搜索。

        Args:
            query: 搜索查询词
            max_results: 最大返回结果数
            search_depth: 搜索深度 basic/advanced
            include_domains: 限定搜索域名列表
            exclude_domains: 排除搜索域名列表

        Returns:
            {"total": int, "chunks": [{"title", "url", "content", "score", "type"}], "answer": str}
        """
        api_key = "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"

        try:
            import requests

            params: dict = {
                "api_key": api_key,
                "query": query,
                "max_results": max(max_results, 1),
                "search_depth": search_depth if search_depth in ("basic", "advanced") else "basic",
                "include_answer": True,
            }
            if include_domains:
                params["include_domains"] = include_domains
            if exclude_domains:
                params["exclude_domains"] = exclude_domains

            resp = requests.post(
                "https://api.tavily.com/search",
                json=params,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            # 格式化结果
            chunks = []
            for r in data.get("results", []):
                chunks.append({
                    "type": "page",
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": (r.get("content", "") or ""),
                    "score": r.get("score", 0.0),
                })

            answer = data.get("answer", "")
            return {
                "total": len(chunks),
                "chunks": chunks,
                "answer": answer,
                "response_time": data.get("response_time", 0),
            }
        except Exception as e:
            logger.error(f"web_search error: {e}")
            return self._build_error(str(e))

    # ── Tool 10: 列出知识库文档 ────────────────────────────────

    def _tool_list_documents(self) -> dict:
        """列出知识库中所有文档及其页数范围"""
        if not self.dealer:
            return self._build_error("ES Dealer 不可用")

        tenant_ids = self._ensure_string_list(self.tenant_ids, [])
        kb_ids = self._ensure_string_list(self.kb_ids, [])
        logger.info(f"list_documents called: tenant_ids={tenant_ids}, kb_ids={kb_ids}")

        try:
            from rag.utils.doc_store_conn import OrderByExpr
            from rag.nlp.search import index_name

            src = ["doc_id", "docnm_kwd", "page_num_int"]
            sres = self.dealer.dataStore.search(
                src, [], {}, [], OrderByExpr(),
                0, 2000,
                [index_name(tid) for tid in tenant_ids],
                kb_ids,
            )

            ids = self.dealer.dataStore.getChunkIds(sres)
            fields = self.dealer.dataStore.getFields(sres, src)

            # Python 聚合: doc_id → {name, pages}
            doc_map: dict = {}
            for cid in ids:
                chunk = fields.get(cid)
                if not chunk:
                    continue
                doc_id = str(chunk.get("doc_id", ""))
                if not doc_id:
                    continue
                if doc_id not in doc_map:
                    doc_map[doc_id] = {
                        "doc_id": doc_id,
                        "doc_name": str(chunk.get("docnm_kwd", "")),
                        "pages": set(),
                    }
                pn = chunk.get("page_num_int")
                if pn is not None:
                    doc_map[doc_id]["pages"].add(int(pn))

            documents = []
            for d in doc_map.values():
                pages = sorted(d["pages"])
                documents.append({
                    "doc_id": d["doc_id"],
                    "doc_name": d["doc_name"],
                    "page_count": len(pages),
                    "first_page": pages[0] if pages else 0,
                    "last_page": pages[-1] if pages else 0,
                })

            documents.sort(key=lambda x: x["doc_name"])
            logger.info(f"list_documents: {len(documents)} docs")
            return {"total": len(documents), "documents": documents}
        except Exception as e:
            logger.error(f"list_documents error: {e}")
            return self._build_error(str(e))

    def _tool_list_documents_fallback(self, tenant_ids: list[str], kb_ids: list[str]) -> dict:
        """回退方案：用 search 全量拉取后在 Python 中聚合"""
        try:
            from rag.utils.doc_store_conn import OrderByExpr
            from rag.nlp.search import index_name

            src = ["doc_id", "docnm_kwd", "page_num_int"]
            sres = self.dealer.dataStore.search(
                src, {}, [], OrderByExpr(),
                0, 1000,  # 取足够多的页面
                [index_name(tid) for tid in tenant_ids],
                kb_ids,
            )

            ids = self.dealer.dataStore.getChunkIds(sres)
            fields = self.dealer.dataStore.getFields(sres, src)

            # Python 聚合: doc_id → {name, pages set}
            doc_map: dict[str, dict] = {}
            for chunk_id in ids:
                chunk = fields.get(chunk_id, {})
                doc_id = chunk.get("doc_id", "")
                if not doc_id:
                    continue
                if doc_id not in doc_map:
                    doc_map[doc_id] = {
                        "doc_id": doc_id,
                        "doc_name": chunk.get("docnm_kwd", ""),
                        "pages": set(),
                    }
                pn = chunk.get("page_num_int")
                if pn is not None:
                    doc_map[doc_id]["pages"].add(pn)

            documents = []
            for d in doc_map.values():
                pages = sorted(d["pages"])
                documents.append({
                    "doc_id": d["doc_id"],
                    "doc_name": d["doc_name"],
                    "page_count": len(pages),
                    "first_page": pages[0] if pages else 0,
                    "last_page": pages[-1] if pages else 0,
                })

            documents.sort(key=lambda x: x["doc_name"])
            return {"total": len(documents), "documents": documents}
        except Exception as e:
            logger.error(f"list_documents_fallback error: {e}")
            return self._build_error(str(e))

    # ── Tool 11: 获取页面完整内容 ──────────────────────────────

    def _tool_get_full_page(self, doc_id: str, page_num: int) -> dict:
        """获取某一页的完整 OCR 内容，不做截断"""
        if not self.dealer:
            return self._build_error("ES Dealer 不可用")

        try:
            from rag.utils.doc_store_conn import OrderByExpr
            from rag.nlp.search import index_name

            tenant_ids = self._ensure_string_list(self.tenant_ids, [])
            kb_ids = self._ensure_string_list(self.kb_ids, [])

            src = ["page_id", "doc_id", "docnm_kwd", "kb_id", "page_num_int",
                   "img_url", "content_with_weight"]

            condition = {"doc_id": doc_id, "page_num_int": [page_num]}

            sres = self.dealer.dataStore.search(
                src, [], condition, [], OrderByExpr(),
                0, 1,
                [index_name(tid) for tid in tenant_ids],
                kb_ids,
            )

            ids = self.dealer.dataStore.getChunkIds(sres)
            if not ids:
                return self._build_error(f"未找到文档 {doc_id} 第 {page_num} 页")

            fields = self.dealer.dataStore.getFields(sres, src)
            chunk_id = ids[0]
            chunk = fields.get(chunk_id, {})

            return {
                "found": True,
                "page_id": chunk.get("page_id", chunk_id),
                "doc_id": chunk.get("doc_id", ""),
                "docnm_kwd": chunk.get("docnm_kwd", ""),
                "kb_id": chunk.get("kb_id", ""),
                "page_num_int": chunk.get("page_num_int", 0),
                "full_content": chunk.get("content_with_weight", ""),
                "img_url": chunk.get("img_url", ""),
            }
        except Exception as e:
            logger.error(f"get_full_page error: {e}")
            return self._build_error(str(e))

    # ── Tool 12: 获取知识结构（思维导图） ───────────────────────

    def _tool_get_knowledge_structure(self, doc_id: str) -> dict:
        """获取文档的知识结构（思维导图 + 闪卡/测验数量）"""
        try:
            from api.db.db_models import DocumentGeneration

            rows = list(
                DocumentGeneration.select().where(
                    DocumentGeneration.doc_id == doc_id
                )
            )

            if not rows:
                return {"found": False, "doc_id": doc_id}

            result: dict = {
                "found": True,
                "doc_id": doc_id,
                "mindmap": None,
                "flashcards_count": 0,
                "quiz_count": 0,
            }

            for row in rows:
                if row.generation_type == "mindmap":
                    try:
                        result["mindmap"] = json.loads(row.content)
                    except (json.JSONDecodeError, TypeError):
                        result["mindmap"] = {"raw": row.content}
                elif row.generation_type == "flashcards":
                    try:
                        cards = json.loads(row.content)
                        result["flashcards_count"] = len(cards) if isinstance(cards, list) else 0
                    except (json.JSONDecodeError, TypeError):
                        result["flashcards_count"] = 0
                elif row.generation_type == "quiz":
                    try:
                        quiz = json.loads(row.content)
                        result["quiz_count"] = len(quiz) if isinstance(quiz, list) else 0
                    except (json.JSONDecodeError, TypeError):
                        result["quiz_count"] = 0

            return result
        except Exception as e:
            logger.error(f"get_knowledge_structure error: {e}")
            return self._build_error(str(e))
