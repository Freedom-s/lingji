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
# rag/agent/server/server.py → 项目根需要向上 3 层
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from fastmcp import FastMCP
from rag.agent.server.tools import MCPToolExecutor
from starlette.responses import JSONResponse

logger = logging.getLogger("ragflow.agent.mcp_server")

# ── FastMCP 实例 ─────────────────────────────────────────────

mcp = FastMCP(
    "ragflow-retrieval",
    instructions=(
        "RAGFlow-Plus 知识库检索服务，提供页面级多模态检索能力。"
        "支持向量语义检索、关键词精确检索、RRF 融合、多模态重排序、文档列表、完整页面、知识结构等 12 个内部方法，对外暴露 6 个工具。"
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
        from rag.utils.es_conn import ESConnection
        from api.db.services.llm_service import LLMBundle
        from api.db import LLMType

        doc_store = ESConnection()
        dealer = Dealer(doc_store)

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


# ── 6 个 MCP 工具 ────────────────────────────────────────────

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


@mcp.tool()
def get_adjacent_pages(doc_id: str, page_num: int, direction: str = "both", offset: int = 1) -> dict:
    """获取指定页面的相邻页面（前/后 N 页），用于扩展上下文、查看前后文。"""
    return get_executor()._tool_get_adjacent_pages(doc_id, page_num, direction, offset)


@mcp.tool()
def list_documents() -> dict:
    """列出知识库中所有文档及其页数范围，用于了解知识库中有哪些课件、每个课件的页数。在需要回答'有哪些课件'或需要确定检索范围时优先调用。"""
    return get_executor()._tool_list_documents()


@mcp.tool()
def get_full_page(doc_id: str, page_num: int) -> dict:
    """获取某一页的完整内容（全文 + 图片），不做截断。当 hybrid_retrieve 返回的片段不够详细时，用此工具获取页面完整信息。参数: doc_id(文档ID), page_num(页码)"""
    return get_executor()._tool_get_full_page(doc_id, page_num)


@mcp.tool()
def get_knowledge_structure(doc_id: str) -> dict:
    """获取课件的知识结构（思维导图 + 知识点层级），用于了解课件的知识框架、章节组织。当需要回答'XX课件包含哪些知识点'或'XX章节讲什么'时调用。参数: doc_id(文档ID)"""
    return get_executor()._tool_get_knowledge_structure(doc_id)


# ── 自定义 HTTP 路由 ─────────────────────────────────────────

@mcp.custom_route(path="/health", methods=["GET"])
async def health(request) -> JSONResponse:
    """健康检查端点"""
    try:
        from rag.nlp.search import Dealer
        dealer_status = "connected"
    except Exception:
        dealer_status = "disconnected"

    return JSONResponse({
        "status": "ok",
        "dealer": dealer_status,
        "framework": "FastMCP",
    })


@mcp.custom_route(path="/initialize", methods=["POST"])
async def initialize(request) -> JSONResponse:
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
        from rag.utils.es_conn import ESConnection

        doc_store = ESConnection()
        dealer = Dealer(doc_store)
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

        return JSONResponse({
            "status": "ok",
            "tenant_ids": tenant_ids,
            "kb_ids": kb_ids,
        })
    except Exception as e:
        logger.error(f"initialize error: {e}")
        return JSONResponse({"status": "error", "message": str(e)})
