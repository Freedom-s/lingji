"""
MCP Protocol Definitions: JSON-RPC 2.0 types, MCP method enums,
tool JSON schemas, and OpenAI function calling format converters.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ── JSON-RPC 2.0 ─────────────────────────────────────────────

class MCPMethods(str, Enum):
    """MCP 协议方法名"""
    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"
    RESOURCES_LIST = "resources/list"
    RESOURCES_READ = "resources/read"
    PROMPTS_LIST = "prompts/list"
    PROMPTS_GET = "prompts/get"
    INITIALIZE = "initialize"
    PING = "ping"


# JSON-RPC error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
TOOL_EXECUTION_ERROR = -32000


@dataclass
class JSONRPCRequest:
    jsonrpc: str = "2.0"
    method: str = ""
    params: dict = field(default_factory=dict)
    id: str | int | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "JSONRPCRequest":
        return cls(
            jsonrpc=d.get("jsonrpc", "2.0"),
            method=d.get("method", ""),
            params=d.get("params", {}),
            id=d.get("id"),
        )


@dataclass
class JSONRPCResponse:
    jsonrpc: str = "2.0"
    result: Any = None
    error: dict | None = None
    id: str | int | None = None

    def to_dict(self) -> dict:
        return {
            "jsonrpc": self.jsonrpc,
            "result": self.result,
            "error": self.error,
            "id": self.id,
        }


def make_error(code: int, message: str, data: Any = None) -> dict:
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return err


# ── Tool Schemas (OpenAI function calling format) ────────────

MCP_TOOL_SCHEMAS: dict[str, dict] = {}

def _register(name: str, description: str, properties: dict, required: list[str] | None = None):
    MCP_TOOL_SCHEMAS[name] = {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required or list(properties.keys()),
            },
        },
    }


_register(
    "vector_search_image",
    "基于图片向量进行语义检索，适用于查找与查询描述视觉相似的页面图片。"
    "使用 image_embedding 字段进行 dense vector 余弦相似度匹配。",
    {
        "query": {"type": "string", "description": "搜索查询文本"},
        "top_k": {"type": "integer", "description": "返回结果数量，默认 50", "default": 50},
    },
)

_register(
    "vector_search_text",
    "基于文本向量进行语义检索，适用于自然语言描述的语义匹配。"
    "使用 text_embedding 字段进行 dense vector 余弦相似度匹配。",
    {
        "query": {"type": "string", "description": "搜索查询文本"},
        "top_k": {"type": "integer", "description": "返回结果数量，默认 50", "default": 50},
    },
)

_register(
    "keyword_search",
    "基于 BM25 算法的关键词精确检索，适用于专有名词、术语、数字等精确匹配场景。"
    "对中文进行 jieba 分词后在 content_ltks 字段上匹配。",
    {
        "query": {"type": "string", "description": "关键词查询"},
        "top_k": {"type": "integer", "description": "返回结果数量，默认 50", "default": 50},
    },
)

_register(
    "rrf_fusion",
    "倒数排序融合（Reciprocal Rank Fusion），将多个检索结果集合并排序。"
    "对每个结果的排名取倒数后加权求和，适用于融合不同检索策略的结果。",
    {
        "result_sets": {
            "type": "array",
            "description": "多个检索结果集，每个元素为 {'pages': [...], 'query': '...'}",
            "items": {"type": "object"},
        },
        "rrf_k": {"type": "integer", "description": "RRF 平滑参数 k，默认 60", "default": 60},
        "top_k": {"type": "integer", "description": "返回 Top K 结果，默认 5", "default": 5},
    },
)

_register(
    "rerank_pages",
    "对候选页面进行多模态重排序（文本相似度 + 视觉相似度）。"
    "使用 rerank 模型计算 query 与每个候选页面的相关性分数，"
    "自动将 MinIO 图片 URL 转为 base64 用于视觉重排序。",
    {
        "query": {"type": "string", "description": "排序参考查询"},
        "candidate_pages": {
            "type": "array",
            "description": "候选页面列表",
            "items": {"type": "object"},
        },
        "top_k": {"type": "integer", "description": "返回 Top K 结果，默认 3", "default": 3},
        "similarity_threshold": {
            "type": "number",
            "description": "相似度阈值（0-1），低于此值的页面将被过滤，默认 0.5",
            "default": 0.5,
        },
    },
)

_register(
    "get_adjacent_pages",
    "获取指定页面的相邻页面（前/后 N 页），适用于查看上下文、扩展阅读场景。",
    {
        "doc_id": {"type": "string", "description": "文档 ID"},
        "page_num": {"type": "integer", "description": "当前页码"},
        "direction": {
            "type": "string",
            "description": "方向：'prev' 前 N 页, 'next' 后 N 页, 'both' 前后各 N 页",
            "enum": ["prev", "next", "both"],
            "default": "both",
        },
        "offset": {"type": "integer", "description": "偏移页数，默认 1", "default": 1},
    },
)

_register(
    "evaluate_page_relevance",
    "使用 VLM 模型评估单个页面与问题的相关性。"
    "返回相关性评分和判断理由，可用于过滤低质量检索结果。",
    {
        "page": {
            "type": "object",
            "description": "页面对象，需包含 page_content、img_url 或 image_base64 字段",
        },
        "question": {"type": "string", "description": "需要判断相关性的问题"},
    },
)

_register(
    "hybrid_retrieve",
    "一键式混合检索：并行执行 vector_search_text + vector_search_image + keyword_search，"
    "通过 RRF 融合后重排序返回最优结果。是默认推荐的首选检索工具。",
    {
        "query": {"type": "string", "description": "搜索查询"},
        "image_topk": {"type": "integer", "description": "图片向量检索 TopK，默认 50", "default": 50},
        "text_topk": {"type": "integer", "description": "文本向量检索 TopK，默认 50", "default": 50},
        "keyword_topk": {"type": "integer", "description": "关键词检索 TopK，默认 50", "default": 50},
        "rrf_topk": {"type": "integer", "description": "RRF 融合后保留 TopK，默认 5", "default": 5},
        "rerank_topk": {"type": "integer", "description": "重排序后保留 TopK，默认 3", "default": 3},
    },
)

_register(
    "web_search",
    "使用 Tavily API 进行联网搜索，获取互联网上的最新信息。"
    "适用于知识库中没有覆盖的时新话题、最新新闻、实时信息查询。"
    "返回搜索结果列表，每项包含标题、URL、内容和相关性评分。",
    {
        "query": {"type": "string", "description": "搜索查询词"},
        "max_results": {"type": "integer", "description": "最大返回结果数，默认 5", "default": 5},
        "search_depth": {
            "type": "string",
            "description": "搜索深度：basic 快速搜索，advanced 深度搜索",
            "enum": ["basic", "advanced"],
            "default": "basic",
        },
        "include_domains": {
            "type": "array",
            "description": "限定搜索域名列表（可选）",
            "items": {"type": "string"},
        },
        "exclude_domains": {
            "type": "array",
            "description": "排除搜索域名列表（可选）",
            "items": {"type": "string"},
        },
    },
)


def get_all_tool_schemas() -> list[dict]:
    return list(MCP_TOOL_SCHEMAS.values())


def get_tool_schema(tool_name: str) -> dict | None:
    return MCP_TOOL_SCHEMAS.get(tool_name)


def to_openai_tools(tools: list[dict]) -> list[dict]:
    """将 MCP tool 信息转换为 OpenAI function calling 格式"""
    result = []
    for t in tools:
        name = t.get("name", "")
        description = t.get("description", "")
        schema = t.get("inputSchema", {})
        result.append({
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": schema.get("type", "object"),
                    "properties": schema.get("properties", {}),
                    "required": schema.get("required", []),
                },
            },
        })
    return result
