"""
Agent + MCP Architecture for RAGFlow-Plus

MCP (Model Context Protocol) Server running on port 9390.
Provides page-level multi-modal retrieval tools for Agent-driven RAG.

Architecture:
    User Question -> Planner -> MCP Server -> MCPToolExecutor -> ES
                                                      |
                                              Observer evaluates quality
                                                      |
                                              Reflector replans if needed
                                                      |
                                              Generator streams answer

Components:
    - MCPToolExecutor: executes 8 retrieval tools against ES
    - MCPServer (FastMCP): exposes tools via SSE on port 9390
    - MCPClient: wraps fastmcp.Client for sync agent usage
    - AgentLoop: ReAct-style agent loop (plan -> execute -> observe -> generate)
    - Planner: LLM function calling to decide retrieval strategy
    - Observer: evaluates retrieval quality
    - MemoryManager: 3-tier memory (working / short-term / long-term)

Start MCP Server:
    python -m rag.agent.mcp_server_run
"""
