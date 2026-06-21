"""
FastMCP Server: 在端口 9390 上提供 6 个检索工具的 SSE 服务。

启动方式:
    python -m rag.agent.server.run

架构:
    - 无会话状态: 所有上下文参数由 LLM 调用时显式传递
    - 模型缓存: 嵌入/重排序模型实例按 tenant_id:model_id 缓存
    - ES 连接: Dealer 单例
"""

import logging
import sys
import os
from typing import Annotated

from pydantic import Field

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from fastmcp import FastMCP
from rag.agent.server.tools import MCPToolExecutor
from starlette.responses import JSONResponse

logger = logging.getLogger("ragflow.agent.mcp_server")

mcp = FastMCP(
    "ragflow-retrieval",
    instructions=(
        "RAGFlow-Plus 知识库检索服务，提供页面级多模态检索能力。"
        "支持向量语义检索、关键词精确检索、RRF 融合、多模态重排序、文档列表、完整页面、知识结构等 12 个内部方法，对外暴露 6 个工具。"
    ),
)

# ── 模型缓存 ─────────────────────────────────────────────
from rag.nlp.search import Dealer
from rag.utils.es_conn import ESConnection

_dealer = Dealer(ESConnection())
_embd_cache: dict[str, object] = {}
_rerank_cache: dict[str, object] = {}


def _get_embd_mdl(tenant_id: str, embd_id: str):
    if not tenant_id or not embd_id:
        return None
    key = f"{tenant_id}:{embd_id}"
    if key not in _embd_cache:
        from api.db.services.llm_service import LLMBundle
        from api.db import LLMType
        _embd_cache[key] = LLMBundle(tenant_id, LLMType.EMBEDDING, embd_id)
    return _embd_cache[key]


def _get_rerank_mdl(tenant_id: str, rerank_id: str):
    if not tenant_id or not rerank_id:
        return None
    key = f"{tenant_id}:{rerank_id}"
    if key not in _rerank_cache:
        from api.db.services.llm_service import LLMBundle
        from api.db import LLMType
        _rerank_cache[key] = LLMBundle(tenant_id, LLMType.RERANK, rerank_id)
    return _rerank_cache[key]


def _executor(tenant_id: str = "", embd_id: str = "", rerank_id: str = "") -> MCPToolExecutor:
    return MCPToolExecutor(
        dealer=_dealer,
        embd_mdl=_get_embd_mdl(tenant_id, embd_id),
        rerank_mdl=_get_rerank_mdl(tenant_id, rerank_id),
    )


# ── 6 个 MCP 工具（无 set_context，系统参数由 LLM 调用时传递） ──

@mcp.tool()
def hybrid_retrieve(
    query: Annotated[str, Field(description="检索内容，应传入用户问题的核心内容")],
    rerank_topk: Annotated[int, Field(default=3, description="最终返回结果数量", ge=1, le=5)],
    tenant_ids: list[str] | None = None,
    kb_ids: list[str] | None = None,
    tenant_id: str = "",
    embd_id: str = "",
    rerank_id: str = "",
) -> dict:
    """一键混合检索：三路并行检索（文本向量+图片向量+关键词） → RRF 融合 → 重排序。推荐的首选检索工具。"""
    return _executor(tenant_id, embd_id, rerank_id)._tool_hybrid_retrieve(
        query=query, rerank_topk=rerank_topk,
        tenant_ids=tenant_ids or [], kb_ids=kb_ids or [],
    )


@mcp.tool()
def web_search(
    query: Annotated[str, Field(description="传入对应的搜索问题")],
    max_results: Annotated[int, Field(default=5, description="返回结果数量。", ge=1, le=10)],
) -> dict:
    """联网搜索。使用 Tavily API 检索互联网最新信息。"""
    return _executor()._tool_web_search(query, max_results)


@mcp.tool()
def get_adjacent_pages(
    doc_id: Annotated[str, Field(description="文档 ID")],
    page_num: Annotated[int, Field(description="当前页码")],
    direction: Annotated[str, Field(default="both", description="翻页方向: both(上下), prev(前), next(后)")] = "both",
    offset: Annotated[int, Field(default=1, description="偏移页数，默认取前后各 1 页")] = 1,
    tenant_ids: list[str] | None = None,
    kb_ids: list[str] | None = None,
) -> dict:
    """获取指定页面的相邻页面（前/后 N 页），用于扩展上下文、查看前后文。"""
    return _executor()._tool_get_adjacent_pages(
        doc_id, page_num, direction, offset,
        tenant_ids=tenant_ids or [], kb_ids=kb_ids or [],
    )


@mcp.tool()
def list_documents(
    kb_ids: list[str] | None = None,
) -> dict:
    """列出当前助教所关联知识库中的所有文档。在需要了解有哪些课件、确定检索范围时优先调用。"""
    return _executor()._tool_list_documents(kb_ids=kb_ids or [])


@mcp.tool()
def get_full_page(
    doc_id: Annotated[str, Field(description="文档 ID")],
    page_num: Annotated[int, Field(description="页码")],
    tenant_ids: list[str] | None = None,
    kb_ids: list[str] | None = None,
) -> dict:
    """获取某一页的完整内容（全文 + 图片），不做截断。"""
    return _executor()._tool_get_full_page(
        doc_id, page_num, tenant_ids=tenant_ids or [], kb_ids=kb_ids or [],
    )


@mcp.tool()
def get_knowledge_structure(
    doc_id: Annotated[str, Field(description="文档 ID")],
) -> dict:
    """获取课件的知识结构（思维导图 + 知识点层级），用于了解课件的知识框架、章节组织。"""
    return _executor()._tool_get_knowledge_structure(doc_id)


# ── 健康检查 ─────────────────────────────────────────────

@mcp.custom_route(path="/health", methods=["GET"])
async def health(request) -> JSONResponse:
    return JSONResponse({"status": "ok", "framework": "FastMCP"})
