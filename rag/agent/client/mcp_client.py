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
        """延迟初始化 fastmcp 客户端（已废弃，保留兼容）"""
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

    # ── 异步核心方法 ──────────────────────────────────────────

    async def _list_tools_async(self) -> list[dict]:
        """异步获取工具列表（原生 SSE 协议，绕过 FastMCP Client 的 event loop 限制）"""
        return await self._mcp_jsonrpc_request("tools/list", {})

    async def _call_tool_async(self, tool_name: str, arguments: dict) -> dict:
        """异步调用工具（原生 SSE 协议）"""
        return await self._mcp_jsonrpc_request("tools/call", {"name": tool_name, "arguments": arguments})

    async def _mcp_jsonrpc_request(self, method: str, params: dict) -> list[dict] | dict:
        """
        原生 MCP SSE 协议实现：
        1. GET /sse → 获取 session_id + 保持 SSE 连接
        2. POST /messages/?session_id={id} → 发送 JSON-RPC 请求
        3. 从同一个 SSE 连接中读取响应（响应通过 SSE 事件返回）
        """
        import aiohttp

        connector = aiohttp.TCPConnector()
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        async with aiohttp.ClientSession(
            connector=connector, timeout=timeout, trust_env=False,
        ) as session:
            # Step 1: 建立 SSE 连接，获取 session_id
            sse_url = f"{self.base_url}/sse"
            sse_stream = None
            try:
                sse_stream = await session.get(sse_url)
                sse_stream.raise_for_status()

                # 读取第一个 SSE 事件获取 endpoint (session_id)
                session_id = None
                async for line_bytes in sse_stream.content:
                    line = line_bytes.decode("utf-8").strip()
                    if line.startswith("data:") and "session_id=" in line:
                        import re
                        match = re.search(r"session_id=([^\s&]+)", line)
                        if match:
                            session_id = match.group(1)
                            logger.info(f"MCP SSE session established: {session_id[:16]}...")
                            break

                if not session_id:
                    raise RuntimeError("Failed to get session_id from MCP SSE endpoint")

                msg_url = f"{self.base_url}/messages/?session_id={session_id}"

                # Step 2: MCP Initialize 握手（必须先做）
                async with session.post(msg_url, json={
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "ragflow-agent", "version": "1.0"},
                    },
                    "id": 0,
                }) as init_resp:
                    if init_resp.status not in (200, 202):
                        logger.warning(f"MCP initialize returned {init_resp.status}")

                # 读取 initialize 响应
                async for line_bytes in sse_stream.content:
                    line = line_bytes.decode("utf-8").strip()
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        try:
                            data = json.loads(data_str)
                            if isinstance(data, dict) and "result" in data:
                                logger.info("MCP initialize: OK")
                                break
                        except json.JSONDecodeError:
                            continue

                # 发送 initialized 通知
                async with session.post(msg_url, json={
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                }) as _:
                    pass

                # Step 3: 发送实际的 JSON-RPC 请求
                payload = {
                    "jsonrpc": "2.0",
                    "method": method,
                    "params": params,
                    "id": 1,
                }
                async with session.post(msg_url, json=payload) as msg_resp:
                    msg_resp.raise_for_status()
                    if msg_resp.status not in (200, 202):
                        text = await msg_resp.text()
                        logger.warning(f"MCP POST returned {msg_resp.status}: {text[:200]}")

                # Step 4: 从同一个 SSE 连接读取服务端推送的响应
                response_data = None
                async for line_bytes in sse_stream.content:
                    line = line_bytes.decode("utf-8").strip()
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        try:
                            data = json.loads(data_str)
                            if isinstance(data, dict) and "result" in data:
                                response_data = data["result"]
                                break
                        except json.JSONDecodeError:
                            continue
                    # 如果连续多行没有 data，可能没有更多响应
                    if not line:
                        continue

            finally:
                if sse_stream is not None:
                    sse_stream.close()

            if response_data is None:
                raise RuntimeError(f"No result received for MCP method: {method}")

            # Step 4: 解析结果
            logger.info(f"MCP response for {method}: {json.dumps(response_data, ensure_ascii=False)[:300]}")

            if method == "tools/list":
                tools = response_data.get("tools", [])
                logger.info(f"MCP tools/list: received {len(tools)} tools")
                return [
                    {"name": t["name"], "description": t.get("description", ""),
                     "inputSchema": t.get("inputSchema", {})}
                    for t in tools
                ]

            # tools/call 返回结果
            if isinstance(response_data, dict) and "content" in response_data:
                for c in response_data["content"]:
                    if isinstance(c, dict) and "text" in c:
                        try:
                            return json.loads(c["text"])
                        except (json.JSONDecodeError, TypeError):
                            return {"result": c["text"]}
            return response_data if isinstance(response_data, dict) else {"result": str(response_data)}

    # ── 同步接口（供 AgentLoop 调用） ──────────────────────────

    def list_tools(self) -> list[dict]:
        """获取 MCP Server 上的工具列表"""
        return self._run_async(self._list_tools_async())

    def get_openai_tools(self, mcp_tools: list[dict] | None = None) -> list[dict]:
        """将 MCP 工具转换为 OpenAI function calling 格式"""
        if mcp_tools is None:
            mcp_tools = self.list_tools()
        from rag.agent.mcp_protocol import to_openai_tools
        return to_openai_tools(mcp_tools)

    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """调用 MCP Server 上的单个工具"""
        try:
            return self._run_async(self._call_tool_async(tool_name, arguments))
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
