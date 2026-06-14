"""
MCP Protocol Definitions: JSON-RPC 2.0 types, MCP method enums,
and OpenAI function calling format converter.

工具 Schema 由 FastMCP 的 @mcp.tool() 根据函数类型注解自动生成，
不再手动维护。通过 MCP Server 的 tools/list 接口即可获取。
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


# ── OpenAI 格式转换 ──────────────────────────────────────────

def to_openai_tools(tools: list[dict]) -> list[dict]:
    """将 MCP tools/list 返回的工具信息转换为 OpenAI function calling 格式"""
    result = []
    for t in tools:
        name = t.get("name", "")
        description = t.get("description", "")
        schema = t.get("inputSchema") or t.get("parameters", {})
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
