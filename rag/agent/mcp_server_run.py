"""
Backward-compatible MCP Server entry point (delegates to rag.agent.server).

启动方式:
    python -m rag.agent.mcp_server_run
    # 或
    python -m rag.agent.server.run
"""
from rag.agent.server.server import mcp

if __name__ == "__main__":
    print("Starting RAGFlow MCP Server on http://0.0.0.0:9390")
    mcp.run(transport="sse", host="0.0.0.0", port=9390)
