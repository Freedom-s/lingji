"""
FastMCP Server: 在端口 9390 上提供 8 个检索工具的 SSE 服务。

启动方式:
    python -m rag.agent.mcp_server_run

自定义路由:
    GET  /health      — 健康检查
    POST /initialize  — 初始化上下文（tenant_ids, kb_ids, LLM models）
"""

import json
import logging
import sys
import os
from contextvars import ContextVar

# 将项目根目录加入 sys.path，确保可以导入 api 模块
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from fastmcp import FastMCP
from rag.agent.server.tools import MCPToolExecutor

logger = logging.getLogger("ragflow.agent.mcp_server")

# ── FastMCP 实例 ─────────────────────────────────────────────

mcp = FastMCP(
    "ragflow-retrieval",
    instructions=(
        "RAGFlow-Plus 知识库检索服务，提供页面级多模态检索能力。"
        "支持向量语义检索、关键词精确检索、RRF 融合、多模态重排序等 8 个工具。"
    ),
)

# ── 全局状态 ─────────────────────────────────────────────────

_tool_executor: MCPToolExecutor | None = None

_current_tenant_ids: ContextVar[list[str]] = ContextVar("tenant_ids", default=[])
_current_kb_ids: ContextVar[list[str]] = ContextVar("kb_ids", default=[])


def get_executor() -> MCPToolExecutor:
    global _tool_executor
    if _tool_executor is None:
        _init_executor()
    return _tool_executor  # type: ignore


def _init_executor():
    """延迟初始化 MCPToolExecutor，连接 ES 和 LLM"""
    global _tool_executor

    try:
        from rag.nlp.search import Dealer
        from api.db.services.llm_service import LLMBundle
        from api.db import LLMType

        dealer = Dealer()

        # 尝试初始化 LLM 模型（embd/rerank/chat 可选）
        embd_mdl = None
        rerank_mdl = None
        chat_mdl = None

        try:
            from api import settings
            embd_mdl = LLMBundle(settings.PLATFORM_TENANT_ID, LLMType.EMBEDDING)
        except Exception as e:
            logger.warning(f"embd_mdl 初始化失败: {e}")

        try:
            rerank_mdl = LLMBundle(
                getattr(settings, "PLATFORM_TENANT_ID", ""),
                LLMType.RERANK,
            )
        except Exception as e:
            logger.warning(f"rerank_mdl 初始化失败: {e}")

        try:
            chat_mdl = LLMBundle(
                getattr(settings, "PLATFORM_TENANT_ID", ""),
                LLMType.CHAT,
            )
        except Exception as e:
            logger.warning(f"chat_mdl 初始化失败: {e}")

        _tool_executor = MCPToolExecutor(
            dealer=dealer,
            embd_mdl=embd_mdl,
            rerank_mdl=rerank_mdl,
            chat_mdl=chat_mdl,
        )
        logger.info("MCPToolExecutor 初始化成功")

    except Exception as e:
        logger.error(f"MCPToolExecutor 初始化失败: {e}")
        raise


# ── 8 个 MCP 工具 ────────────────────────────────────────────

@mcp.tool()
def vector_search_image(query: str, top_k: int = 50) -> dict:
    """基于图片向量进行语义检索。使用 image embedding 进行 dense vector 余弦相似度匹配。"""
    return get_executor()._tool_vector_search_image(query, top_k)


@mcp.tool()
def vector_search_text(query: str, top_k: int = 50) -> dict:
    """基于文本向量进行语义检索。使用 text embedding 进行 dense vector 余弦相似度匹配。"""
    return get_executor()._tool_vector_search_text(query, top_k)


@mcp.tool()
def keyword_search(query: str, top_k: int = 50) -> dict:
    """BM25 关键词精确检索，对中文进行 jieba 分词后在 content_ltks 字段匹配。"""
    return get_executor()._tool_keyword_search(query, top_k)


@mcp.tool()
def rrf_fusion(result_sets: list[dict], rrf_k: int = 60, top_k: int = 5) -> dict:
    """RRF 倒数排序融合，将多个检索结果集合并排序。"""
    return get_executor()._tool_rrf_fusion(result_sets, rrf_k, top_k)


@mcp.tool()
def rerank_pages(query: str, candidate_pages: list[dict], top_k: int = 3, similarity_threshold: float = 0.5) -> dict:
    """多模态重排序：使用 rerank 模型计算 query 与候选页面的相关性分数。"""
    return get_executor()._tool_rerank_pages(query, candidate_pages, top_k, similarity_threshold)


@mcp.tool()
def get_adjacent_pages(doc_id: str, page_num: int, direction: str = "both", offset: int = 1) -> dict:
    """获取指定页面的相邻页面（前/后 N 页）。"""
    return get_executor()._tool_get_adjacent_pages(doc_id, page_num, direction, offset)


@mcp.tool()
def evaluate_page_relevance(page: dict, question: str) -> dict:
    """使用 VLM 评估单个页面与问题的相关性。"""
    return get_executor()._tool_evaluate_page_relevance(page, question)


@mcp.tool()
def hybrid_retrieve(
    query: str,
    image_topk: int = 50,
    text_topk: int = 50,
    keyword_topk: int = 50,
    rrf_topk: int = 5,
    rerank_topk: int = 3,
) -> dict:
    """一键混合检索：三路并行检索 → RRF 融合 → 重排序。推荐的首选检索工具。"""
    return get_executor()._tool_hybrid_retrieve(
        query, image_topk, text_topk, keyword_topk, rrf_topk, rerank_topk,
    )


@mcp.tool()
def web_search(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> dict:
    """使用 Tavily API 进行联网搜索，获取互联网上的最新信息。适用于知识库未覆盖的时新话题。"""
    return get_executor()._tool_web_search(
        query, max_results, search_depth, include_domains, exclude_domains,
    )


# ── 自定义 HTTP 路由 ─────────────────────────────────────────

@mcp.custom_route(path="/health", methods=["GET"])
async def health(request) -> dict:
    """健康检查端点"""
    try:
        from rag.nlp.search import Dealer
        dealer_status = "connected"
    except Exception:
        dealer_status = "disconnected"

    return {
        "status": "ok",
        "dealer": dealer_status,
        "framework": "FastMCP",
    }


@mcp.custom_route(path="/initialize", methods=["POST"])
async def initialize(request) -> dict:
    """初始化上下文：设置 tenant_ids、kb_ids，创建 LLM 模型实例"""
    try:
        body = await request.json()
    except Exception:
        body = {}

    tenant_ids = body.get("tenant_ids", [])
    kb_ids = body.get("kb_ids", [])
    embd_id = body.get("embd_id")
    rerank_id = body.get("rerank_id")
    chat_id = body.get("chat_id")

    if isinstance(tenant_ids, str):
        tenant_ids = [tenant_ids]
    if isinstance(kb_ids, str):
        kb_ids = [kb_ids]

    _current_tenant_ids.set(tenant_ids)
    _current_kb_ids.set(kb_ids)

    try:
        from api.db.services.llm_service import LLMBundle
        from api.db import LLMType

        if getattr(body, "tenant_id", None):
            tenant_id_val = body["tenant_id"]
        else:
            tenant_id_val = tenant_ids[0] if tenant_ids else ""

        # 重新初始化 executor，使用新的 LLM 配置
        global _tool_executor
        from rag.nlp.search import Dealer

        dealer = Dealer()
        embd_mdl = LLMBundle(tenant_id_val, LLMType.EMBEDDING, embd_id) if embd_id else None
        rerank_mdl = LLMBundle(tenant_id_val, LLMType.RERANK, rerank_id) if rerank_id else None
        chat_mdl = LLMBundle(tenant_id_val, LLMType.CHAT, chat_id) if chat_id else None

        _tool_executor = MCPToolExecutor(
            dealer=dealer,
            embd_mdl=embd_mdl,
            rerank_mdl=rerank_mdl,
            chat_mdl=chat_mdl,
        )
        _tool_executor.set_context(tenant_ids, kb_ids)

        return {
            "status": "ok",
            "tenant_ids": tenant_ids,
            "kb_ids": kb_ids,
        }
    except Exception as e:
        logger.error(f"initialize error: {e}")
        return {"status": "error", "message": str(e)}
