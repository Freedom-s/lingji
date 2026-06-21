# Agent + MCP 并发安全架构设计

日期：2026-06-22

## 背景

`api/apps/conversation_app.py` 中的 `/completion` 接口每次用户发送一条消息都会触发一次请求。请求中会携带当前对话的完整历史消息，并在服务端通过 `conversation_id` 找到对应的 `conversation` 和 `dialog`。

当前 `_stream_with_agent()` 会在每次请求中整理出一次 Agent 执行所需的上下文：

- `dia`：当前助教配置
- `msg`：完整历史消息，最后一条是当前问题
- `conv`：当前 conversation 记录
- `kb_ids`：当前助教关联的知识库 ID 列表，来自 `dia.kb_ids`
- `tenant_ids`：当前知识库所属租户 ID 列表，来自 `KnowledgebaseService.get_by_ids(dia.kb_ids)`
- `embd_id`：知识库 embedding 模型，来自 `kbs[0].embd_id`
- `rerank_id`：助教 rerank 模型，来自 `dia.rerank_id`
- `chat_mdl`：AgentLoop 本地 ReAct 推理和最终回答使用的 chat 模型，来自 `dia.llm_id`

因此，每次 `/completion` 请求本身已经拥有完整上下文，不需要 MCP server 维护“当前会话上下文”。

## 问题

当前架构中曾考虑通过 MCP server 的 `set_context` 工具将 `kb_ids / tenant_ids / model ids` 存入 server 端 session 状态，再由后续工具通过 `Context.session_id` 读取。但现有 `MCPClient` 每次 `call_tool()` 和 `list_tools()` 都会重新建立一次 SSE 连接，导致每次调用拿到不同的 MCP session_id。

因此，基于 MCP session 的上下文存储不可靠：

```text
call_tool("set_context")       -> SSE session A -> _sessions[A] = context
call_tool("hybrid_retrieve")   -> SSE session B -> _sessions[B] is empty
```

如果改成全局 `_tool_executor` 或全局当前上下文，则多人并发时会互相覆盖：

```text
用户 A initialize -> 当前 kb_ids = A
用户 B initialize -> 当前 kb_ids = B
用户 A 后续检索 -> 错误使用 B 的 kb_ids
```

所以目标是设计一个不依赖 server 端可变会话状态、能支持多人并发的 Agent + MCP 架构。

## 选定方案

采用 **无状态工具调用**。

核心原则：

> MCP server 不保存任何对话上下文；每次工具调用都携带本次执行所需的完整系统上下文，但这些系统上下文由 AgentLoop 自动注入，不由 LLM 生成，也不暴露给 LLM。

## 数据流

### 1. `/completion` 请求入口

`conversation_app.py` 每次请求：

1. 从请求中获得 `conversation_id` 和完整 `messages`
2. 根据 `conversation_id` 查询 `Conversation`
3. 根据 `conv.dialog_id` 查询 `Dialog`
4. 根据 `dia.kb_ids` 查询 `Knowledgebase`
5. 整理出：
   - `question`
   - `history`
   - `kb_ids`
   - `tenant_ids`
   - `embd_id`
   - `rerank_id`
   - `chat_mdl`
6. 创建一个新的 `AgentLoop`
7. 调用 `agent.run(...)`

每次请求创建新的 `AgentLoop` 是合理的，因为 AgentLoop 是一次 ReAct 执行的临时协调器。

### 2. AgentLoop

`AgentLoop` 负责一次对话请求内的 ReAct 流程：

1. 获取 MCP 工具列表
2. 将 MCP 工具转换为 OpenAI function calling schema
3. 过滤掉系统参数，使 LLM 只看到业务参数
4. 构造历史消息和当前问题
5. 调用 chat 模型，让 LLM 决定是否调用工具
6. 在真正调用 MCP 工具前，自动注入系统上下文
7. 收集工具结果，形成检索上下文
8. 最终流式生成答案

AgentLoop 需要持有 `chat_mdl`，因为 ReAct 决策和最终回答发生在 API server 进程内，而不是 MCP server 内。

### 3. MCPClient

`MCPClient` 保持轻量，只负责 JSON-RPC 通信：

- `list_tools()`：获取 MCP server 工具列表
- `get_openai_tools()`：将 MCP 工具 schema 转换为 OpenAI function calling schema，并过滤系统参数
- `call_tool()`：调用指定 MCP 工具

MCPClient 不保存会话上下文，不依赖 SSE session 复用。

### 4. MCP server

`server.py` 负责定义 6 个业务工具并转发到 `tools.py`：

- `hybrid_retrieve`
- `web_search`
- `get_adjacent_pages`
- `list_documents`
- `get_full_page`
- `get_knowledge_structure`

server 层可以接收系统参数，但不存储系统参数。它可以缓存模型实例和 ES Dealer：

- `_dealer`：进程级 ES Dealer 单例
- `_embd_cache[f"{tenant_id}:{embd_id}"]`
- `_rerank_cache[f"{tenant_id}:{rerank_id}"]`

模型缓存是安全的，因为 key 包含 tenant 和 model id，不保存当前对话上下文。

### 5. tools.py

`tools.py` 只执行实际查询逻辑：

- ES 查询显式接收 `tenant_ids / kb_ids`
- MySQL 文档列表显式接收 `kb_ids`
- 混合检索显式接收 `tenant_ids / kb_ids`
- 不使用 `ContextVar`
- 不使用 `self.tenant_ids / self.kb_ids`
- 不依赖全局当前上下文

每个工具调用都是独立的。

## 系统参数隐藏

MCP server 工具函数可以包含系统参数，例如：

```python
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
    ...
```

但 LLM 不应该看到这些系统参数。

`MCPClient.get_openai_tools()` 在转换 schema 时过滤以下字段：

```python
SYSTEM_ARGS = {
    "tenant_ids",
    "kb_ids",
    "tenant_id",
    "embd_id",
    "rerank_id",
}
```

过滤逻辑：

- 从 `properties` 中删除系统参数
- 从 `required` 中删除系统参数
- 保留业务参数

所以 LLM 看到的 `hybrid_retrieve` 只有：

- `query`
- `rerank_topk`

## AgentLoop 参数注入规则

LLM 返回 tool call 后，AgentLoop 在调用 MCP 前注入上下文。

注入规则：

| 工具 | 注入参数 |
| --- | --- |
| `hybrid_retrieve` | `tenant_ids`, `kb_ids`, `tenant_id`, `embd_id`, `rerank_id` |
| `get_full_page` | `tenant_ids`, `kb_ids` |
| `get_adjacent_pages` | `tenant_ids`, `kb_ids` |
| `list_documents` | `kb_ids` |
| `web_search` | 无 |
| `get_knowledge_structure` | 无 |

`get_knowledge_structure` 只需要 `doc_id` 查询 MySQL `document_generation` 表，不需要知识库上下文。

## 并发安全

无状态工具调用的并发边界是每个 tool call 的参数。不同用户请求不会共享“当前上下文”。

```text
用户 A tool call -> args 带 A 的 kb_ids / tenant_ids / model ids
用户 B tool call -> args 带 B 的 kb_ids / tenant_ids / model ids
```

MCP server 中仅缓存可共享资源：

- ES Dealer
- embedding 模型实例
- rerank 模型实例

这些缓存按 tenant/model key 隔离，不会互相覆盖。

## 错误处理

工具层继续返回结构化错误：

```python
{"error": "...", "total": 0, "chunks": []}
```

降级策略：

- embedding 不可用：向量检索失败，但关键词检索仍可返回结果
- rerank 不可用：返回 RRF 结果
- web search 不可用：返回 error，不影响知识库检索
- ES 查询失败：该工具返回 error，AgentLoop 将错误交给 LLM 处理

`/health` 只判断 MCP server 是否可达，不检查某个会话模型是否存在。模型错误应在工具调用时局部处理。

## 文件变更范围

### `api/apps/conversation_app.py`

基本保持不变。确保 `_stream_with_agent()` 将以下参数传给 `AgentLoop.run()`：

- `kb_ids`
- `tenant_ids`
- `embd_id`
- `rerank_id`

### `rag/agent/client/loop.py`

需要：

- 删除 `set_context` 调用
- 添加 `_inject_context()` 私有方法
- 在 `call_tool()` 前调用 `_inject_context()`
- 保持 ReAct 主流程不变

### `rag/agent/client/mcp_client.py`

需要：

- 在 `get_openai_tools()` 中过滤系统参数
- 保持 `list_tools()`、`call_tool()` 简单同步接口
- 不保存 context/session 状态

### `rag/agent/server/server.py`

需要：

- 删除 `set_context`
- 删除 `_sessions`
- 删除 `Context`
- 删除 `/initialize`
- 工具函数保留系统参数，但这些参数由 AgentLoop 注入
- 增加 model cache 和 dealer cache

### `rag/agent/server/tools.py`

需要：

- 去掉 `ContextVar`
- 去掉 `set_context()`
- 所有需要 ES 范围的工具显式接收 `tenant_ids / kb_ids`
- `list_documents` 显式接收 `kb_ids`
- 保持工具返回结构简洁

## 测试计划

### 1. 工具脚本测试

`test_mcp_tools.py` 直接测试底层工具。脚本需要显式传：

```python
tenant_ids=TENANT_IDS
kb_ids=KB_IDS
```

验证：

- `list_documents` 返回当前助教知识库下的文档
- `hybrid_retrieve` 返回正确页
- `get_full_page` 返回完整页内容
- `get_adjacent_pages` 返回相邻页
- `get_knowledge_structure` 返回 mindmap
- `web_search` 返回网页结果

### 2. Tool schema 测试

通过 `MCPClient.list_tools()` + `get_openai_tools()` 验证 LLM 可见 schema：

- `hybrid_retrieve` 只暴露 `query`, `rerank_topk`
- `get_full_page` 只暴露 `doc_id`, `page_num`
- `get_adjacent_pages` 只暴露 `doc_id`, `page_num`, `direction`, `offset`
- `list_documents` 无业务参数
- 没有 `set_context`
- 没有 `tenant_ids / kb_ids / embd_id / rerank_id`

### 3. 并发模拟测试

准备两个不同上下文 A/B，模拟并发调用：

- A 调 `list_documents`
- B 调 `list_documents`
- A 调 `hybrid_retrieve`
- B 调 `hybrid_retrieve`

验证：

- A 只返回 A 的知识库内容
- B 只返回 B 的知识库内容
- 两者互不覆盖

### 4. 真实接口测试

启动：

```bash
python -m rag.agent.server.run
python -m api.ragflow_server
```

通过前端或 curl 调 `/v1/conversation/completion`，验证：

- 流式返回正常
- 工具调用正常
- 多轮工具调用不丢上下文
- 两个浏览器/用户并发时不会串知识库

## 非目标

本设计不处理：

- MCPClient 复用 SSE session
- server 端 session 状态管理
- Redis / 数据库保存 Agent memory
- 长期会话记忆
- 模型缓存 TTL / LRU
- 多进程间共享模型缓存

这些可以后续单独设计。
