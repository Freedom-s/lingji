"""
MCP Server 入口脚本。

启动方式:
    python -m rag.agent.server.run

MCP 服务器在 http://0.0.0.0:9390 上提供 SSE 传输
健康检查: GET http://127.0.0.1:9390/health
"""

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from rag.agent.server.server import mcp

if __name__ == "__main__":
    print("Starting RAGFlow MCP Server on http://0.0.0.0:9390")
    mcp.run(transport="sse", host="0.0.0.0", port=9390)
