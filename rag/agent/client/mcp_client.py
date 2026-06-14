"""
MCPClient: FastMCP 客户端封装，提供同步接口供 AgentLoop 调用。
"""

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger("ragflow.agent.mcp_client")


class MCPClient:
    """FastMCP 客户端封装：SSE 通信，同步接口"""

    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = None

    def _run_async(self, coro):
        """同步封装：在当前事件循环中运行协程，如果没有则创建新循环"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            # 在已有事件循环中运行（不创建新循环避免冲突）
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result(timeout=self.timeout)
        else:
            return asyncio.run(coro)

    def _get_client(self):
        """延迟初始化 fastmcp 客户端"""
        if self._client is None:
            from fastmcp import Client
            self._client = Client(self.base_url)
        return self._client

    # ── HTTP 直连方法 ─────────────────────────────────────────

    def health(self) -> dict:
        """GET /health"""
        import requests
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=self.timeout)
            return resp.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def initialize(
        self,
        tenant_ids: list[str],
        kb_ids: list[str],
        embd_id: str | None = None,
        rerank_id: str | None = None,
        chat_id: str | None = None,
    ) -> dict:
        """POST /initialize"""
        import requests
        try:
            resp = requests.post(
                f"{self.base_url}/initialize",
                json={
                    "tenant_ids": tenant_ids,
                    "kb_ids": kb_ids,
                    "embd_id": embd_id,
                    "rerank_id": rerank_id,
                    "chat_id": chat_id,
                },
                timeout=self.timeout,
            )
            return resp.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ── MCP 工具方法 ──────────────────────────────────────────

    def list_tools(self) -> list[dict]:
        """获取 MCP Server 上的工具列表（Schema 由 @mcp.tool() 自动生成）"""
        client = self._get_client()
        tools = self._run_async(client.list_tools())
        return [{"name": t.name, "description": t.description, "inputSchema": t.inputSchema} for t in tools]

    def get_openai_tools(self, mcp_tools: list[dict] | None = None) -> list[dict]:
        """将 MCP 工具转换为 OpenAI function calling 格式"""
        if mcp_tools is None:
            mcp_tools = self.list_tools()
        from rag.agent.mcp_protocol import to_openai_tools
        return to_openai_tools(mcp_tools)

    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """调用 MCP Server 上的单个工具"""
        try:
            client = self._get_client()
            result = self._run_async(client.call_tool(tool_name, arguments))
            if hasattr(result, "content"):
                # FastMCP 返回的是 ContentBlock 对象
                content = result.content
                if isinstance(content, list):
                    for c in content:
                        if hasattr(c, "text"):
                            try:
                                return json.loads(c.text)
                            except (json.JSONDecodeError, TypeError):
                                return {"result": c.text}
                return {"result": str(content)}
            return result if isinstance(result, dict) else {"result": str(result)}
        except Exception as e:
            logger.error(f"call_tool({tool_name}) error: {e}")
            return {"error": str(e)}

    def batch_call(self, tool_calls: list[dict]) -> list[dict]:
        """批量调用工具（串行，带错误处理）"""
        results = []
        for tc in tool_calls:
            name = tc.get("function", {}).get("name", "")
            args = tc.get("function", {}).get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            results.append(self.call_tool(name, args))
        return results

    def close(self):
        """清理资源"""
        self._client = None
