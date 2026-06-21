"""
Agent + MCP Architecture for RAGFlow-Plus

MCP (Model Context Protocol) Server running on port 9390.
Provides page-level multi-modal retrieval tools for Agent-driven RAG.

Components:
    - MCPToolExecutor: 12 个内部检索方法，对外暴露 6 个工具
    - MCPServer (FastMCP): 通过 SSE 在端口 9390 暴露工具
    - MCPClient: FastMCP 客户端封装，供 AgentLoop 调用
    - AgentLoop: ReAct 风格 Agent，LLM 自主决策检索 vs 回答

Start MCP Server:
    python -m rag.agent.server.run
"""
