# Agent + MCP 并发安全架构 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 MCP server 从有状态改为无状态工具调用，AgentLoop 自动注入 `tenant_ids/kb_ids/model_ids`，支持多人并发。

**Architecture:** 每次 tool call 都是自包含的——AgentLoop 在 LLM 决定的参数之外自动补充系统上下文参数。MCP server 不保存会话状态，仅缓存模型实例和 ES Dealer。LLM 通过 `get_openai_tools()` 过滤看不到系统参数。

**Tech Stack:** Python 3.10+, FastMCP SSE, Peewee ORM, Elasticsearch

## Global Constraints

- 不引入新的依赖
- `MCPClient` 保持简单，不维护 SSE session 状态
- MCP server 不保存 `_sessions` 或 `_tool_executor` 全局可变状态
- Model cache key: `f"{tenant_id}:{model_id}"`
- 删除: `set_context`, `_sessions`, `Context`, `/initialize`, `ContextVar`, `set_context()`
- LLM 看不到: `tenant_ids`, `kb_ids`, `tenant_id`, `embd_id`, `rerank_id`

---

## File Map

| 文件 | 操作 | 职责 |
|------|------|------|
| `rag/agent/server/tools.py` | Modify | 工具实现：去掉 ContextVar / set_context，方法显式接收 kb_ids/tenant_ids |
| `rag/agent/server/server.py` | Modify | 工具定义 + model cache：去掉 set_context/_sessions/Context，加 _dealer/_embd_cache/_rerank_cache |
| `rag/agent/client/mcp_client.py` | Modify | JSON-RPC 客户端：get_openai_tools() 过滤系统参数 |
| `rag/agent/client/loop.py` | Modify | ReAct Agent：加 _inject_context()，去掉 set_context 调用 |
| `test_mcp_tools.py` | Modify | 测试脚本：测试函数显式传 kb_ids/tenant_ids |

---

### Task 1: tools.py — 去掉全局上下文，方法显式接收 kb_ids/tenant_ids

**Files:**
- Modify: `rag/agent/server/tools.py`

**Interfaces:**
- Consumes: nothing new
- Produces: `MCPToolExecutor` without `set_context()` or `ContextVar`, methods accept explicit `kb_ids`/`tenant_ids` params

- [ ] **Step 1: Delete ContextVar and set_context**

Remove lines importing/using `ContextVar`, remove `_current_tenant_ids` / `_current_kb_ids`, remove `set_context()` method, remove `self.tenant_ids` / `self.kb_ids` from `__init__`.

Current `__init__`:
```python
def __init__(self, dealer, embd_mdl=None, rerank_mdl=None, chat_mdl=None):
    self.dealer = dealer
    self.embd_mdl = embd_mdl
    self.rerank_mdl = rerank_mdl
    self.chat_mdl = chat_mdl
    self.tenant_ids: list[str] = _current_tenant_ids.get()
    self.kb_ids: list[str] = _current_kb_ids.get()
```

New `__init__`:
```python
def __init__(self, dealer, embd_mdl=None, rerank_mdl=None, chat_mdl=None):
    self.dealer = dealer
    self.embd_mdl = embd_mdl
    self.rerank_mdl = rerank_mdl
    self.chat_mdl = chat_mdl
```

Delete `set_context()` entirely.

- [ ] **Step 2: Verify existing method signatures**

Each method that already accepts `kb_ids`/`tenant_ids` params is ready. Confirm:
- `_tool_vector_search_image(query, top_k, tenant_ids, kb_ids)` — already has tenant_ids/kb_ids
- `_tool_vector_search_text(query, top_k, tenant_ids, kb_ids)` — already has
- `_tool_keyword_search(query, top_k, tenant_ids, kb_ids)` — already has
- `_tool_get_adjacent_pages(doc_id, page_num, direction, offset, tenant_ids, kb_ids)` — already has
- `_tool_get_full_page(doc_id, page_num, tenant_ids, kb_ids)` — already has
- `_tool_hybrid_retrieve(..., tenant_ids, kb_ids)` — already has
- `_tool_list_documents(kb_ids)` — already has
- `_tool_get_knowledge_structure(doc_id)` — no context needed
- `_tool_web_search(query, max_results)` — no context needed

- [ ] **Step 3: Run existing test to verify**

```bash
/opt/anaconda3/envs/ragflowplus/bin/python3 test_mcp_tools.py 2>&1
```

Expected: tools still return results (test passes correct kb_ids/tenant_ids explicitly). If `set_context` is still called in test script, that's fine for now — will fix in Task 5.

- [ ] **Step 4: Commit**

```bash
git add rag/agent/server/tools.py
git commit -m "refactor(tools): remove ContextVar and set_context, methods accept explicit kb_ids/tenant_ids

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: server.py — 去掉会话状态，加 model cache，保持 6 个工具

**Files:**
- Modify: `rag/agent/server/server.py`

**Interfaces:**
- Consumes: updated `tools.py` (Task 1)
- Produces: 6 MCP tools with system params accepted, model cache, dealer cache, no set_context

- [ ] **Step 1: Rewrite server.py imports and caches**

Remove `Context`, `_sessions`, model cache, dealer cache. Add:
```python
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
```

- [ ] **Step 2: Define 6 tools with system params**

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
```

- [ ] **Step 3: Add health check**

```python
@mcp.custom_route(path="/health", methods=["GET"])
async def health(request) -> JSONResponse:
    return JSONResponse({"status": "ok", "framework": "FastMCP"})
```

- [ ] **Step 4: Run basic health check**

```bash
curl -s http://127.0.0.1:9390/health
```

Expected: `{"status":"ok","framework":"FastMCP"}`

- [ ] **Step 5: Commit**

```bash
git add rag/agent/server/server.py
git commit -m "refactor(server): remove session state, add model cache, tools accept system params

- Remove set_context, _sessions dict, Context dependency
- Add _dealer, _embd_cache, _rerank_cache
- All tools accept kb_ids/tenant_ids as optional params
- Model instances cached by tenant_id:model_id

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: mcp_client.py — get_openai_tools() 过滤系统参数

**Files:**
- Modify: `rag/agent/client/mcp_client.py`

**Interfaces:**
- Consumes: nothing (independent utility change)
- Produces: `get_openai_tools()` returns OpenAI tools without system params

- [ ] **Step 1: Add SYSTEM_ARGS constant and filtering logic**

In `get_openai_tools()`, add filtering:

```python
SYSTEM_ARGS = {
    "tenant_ids",
    "kb_ids",
    "tenant_id",
    "embd_id",
    "rerank_id",
}
```

Modify the method:

```python
def get_openai_tools(self, mcp_tools: list[dict] | None = None) -> list[dict]:
    """将 MCP 工具转换为 OpenAI function calling 格式，过滤系统参数"""
    if mcp_tools is None:
        mcp_tools = self.list_tools()
    result = []
    for t in mcp_tools:
        schema = t.get("inputSchema") or t.get("parameters", {})
        properties = dict(schema.get("properties", {}))
        required = list(schema.get("required", []))
        # 过滤系统参数
        properties = {k: v for k, v in properties.items() if k not in SYSTEM_ARGS}
        required = [k for k in required if k not in SYSTEM_ARGS]
        result.append({
            "type": "function",
            "function": {
                "name": t.get("name", ""),
                "description": t.get("description", ""),
                "parameters": {
                    "type": schema.get("type", "object"),
                    "properties": properties,
                    "required": required,
                },
            },
        })
    return result
```

- [ ] **Step 2: Add SYSTEM_ARGS to class-level constant**

Move inside `MCPClient` class or keep as module-level constant. Module-level is simpler:

```python
# After imports, before class definition
SYSTEM_ARGS = {
    "tenant_ids",
    "kb_ids",
    "tenant_id",
    "embd_id",
    "rerank_id",
}
```

- [ ] **Step 3: Commit**

```bash
git add rag/agent/client/mcp_client.py
git commit -m "feat(mcp_client): filter system args from OpenAI tool schema

LLM will no longer see tenant_ids, kb_ids, tenant_id, embd_id, rerank_id
in tool definitions. These are auto-injected by AgentLoop.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: loop.py — 加 _inject_context，去掉 set_context

**Files:**
- Modify: `rag/agent/client/loop.py`

**Interfaces:**
- Consumes: updated `mcp_client.py` (Task 3), updated `server.py` (Task 2)
- Produces: `AgentLoop.run()` that auto-injects system context before each tool call

- [ ] **Step 1: Remove set_context call**

Delete lines 49-56 that call `self.mcp_client.call_tool("set_context", ...)`.

- [ ] **Step 2: Add _inject_context method**

```python
@staticmethod
def _inject_context(tool_name: str, args: dict, kb_ids: list[str],
                    tenant_ids: list[str], tenant_id: str,
                    embd_id: str | None, rerank_id: str | None):
    """自动注入系统上下文参数。LLM 不传这些参数，AgentLoop 补上。"""
    needs_all = tool_name in ("hybrid_retrieve",)
    needs_es = tool_name in ("get_full_page", "get_adjacent_pages")
    needs_kb = tool_name in ("list_documents",)

    if needs_all:
        args.setdefault("tenant_ids", tenant_ids)
        args.setdefault("kb_ids", kb_ids)
        args.setdefault("tenant_id", tenant_id)
        args.setdefault("embd_id", embd_id or "")
        args.setdefault("rerank_id", rerank_id or "")
    elif needs_es:
        args.setdefault("tenant_ids", tenant_ids)
        args.setdefault("kb_ids", kb_ids)
    elif needs_kb:
        args.setdefault("kb_ids", kb_ids)
```

- [ ] **Step 3: Add tenant_id extraction and injection call in run()**

After `_tenant_id = tenant_ids[0] if tenant_ids else ""` line, keep variable. Before `result = self.mcp_client.call_tool(tool_name, args)`, add:

```python
self._inject_context(tool_name, args, kb_ids, tenant_ids,
                     _tenant_id, embd_id, rerank_id)
```

- [ ] **Step 4: Remove set_context from tools list**

Add filter in run():

```python
mcp_tools = self.mcp_client.list_tools()
mcp_tools = [t for t in mcp_tools if t.get("name") != "set_context"]
openai_tools = self.mcp_client.get_openai_tools(mcp_tools)
```

Note: `set_context` is already gone from server.py after Task 2, so this filter is a safety net.

- [ ] **Step 5: Run test script to verify**

```bash
/opt/anaconda3/envs/ragflowplus/bin/python3 test_mcp_tools.py 2>&1
```

Expected: tools still work with explicitly passed kb_ids/tenant_ids.

- [ ] **Step 6: Commit**

```bash
git add rag/agent/client/loop.py
git commit -m "feat(agent): auto-inject system context into tool calls

- Add _inject_context() to inject kb_ids/tenant_ids/model_ids
- Remove set_context MCP call at start of run()
- Filter set_context from LLM tool list as safety net

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: test_mcp_tools.py — 调整测试脚本

**Files:**
- Modify: `test_mcp_tools.py`

**Interfaces:**
- Consumes: updated `tools.py` (Task 1)
- Produces: working test script that passes kb_ids/tenant_ids explicitly

- [ ] **Step 1: Remove set_context call from init()**

Delete line with `_executor.set_context(TENANT_IDS, KB_IDS)`.

- [ ] **Step 2: Ensure test functions pass context**

Verify all test functions pass the correct params:

```python
def test_list_documents():
    exe = init()
    run("list_documents", exe._tool_list_documents, kb_ids=KB_IDS)

def test_hybrid_retrieve():
    exe = init()
    run("hybrid_retrieve", exe._tool_hybrid_retrieve,
        "传教士野人问题如何解决？", rerank_topk=3,
        tenant_ids=TENANT_IDS, kb_ids=KB_IDS)

def test_get_full_page():
    exe = init()
    run("get_full_page", exe._tool_get_full_page,
        DOC_ID, PAGE_NUM, tenant_ids=TENANT_IDS, kb_ids=KB_IDS)

def test_get_adjacent_pages():
    exe = init()
    run("get_adjacent_pages", exe._tool_get_adjacent_pages,
        DOC_ID, PAGE_NUM, "both", 1,
        tenant_ids=TENANT_IDS, kb_ids=KB_IDS)

def test_get_knowledge_structure():
    exe = init()
    run("get_knowledge_structure", exe._tool_get_knowledge_structure, DOC_ID)

def test_web_search():
    exe = init()
    run("web_search", exe._tool_web_search,
        "人工智能教育最新进展", max_results=5)
```

- [ ] **Step 3: Run all tests**

```bash
/opt/anaconda3/envs/ragflowplus/bin/python3 test_mcp_tools.py 2>&1
```

Expected: all 6 tools return correct results.

- [ ] **Step 4: Commit**

```bash
git add test_mcp_tools.py
git commit -m "test: update test_mcp_tools for stateless tool calls

- Remove set_context usage
- Explicitly pass kb_ids/tenant_ids to each tool call

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: conversation_app.py — 确认无需改动

**Files:**
- Check: `api/apps/conversation_app.py`

`_stream_with_agent()` already passes `kb_ids`, `tenant_ids`, `embd_id`, `rerank_id` to `agent.run()`. No changes needed.

- [ ] **Step 1: Verify conversation_app.py接口无需变更**

```bash
grep -A 20 "def _stream_with_agent" api/apps/conversation_app.py
```

Expected output shows: `agent.run(question=..., history=..., kb_ids=..., tenant_ids=..., dialog=..., embd_id=..., rerank_id=...)`.

- [ ] **Step 2: If matches, skip commit (no changes needed)**

If the function signature is correct, conversation_app.py requires zero changes.

---

### Task 7: Integration smoke test

- [ ] **Step 1: Start MCP server**

```bash
/opt/anaconda3/envs/ragflowplus/bin/python3 -m rag.agent.server.run &
```

Expected: "Starting RAGFlow MCP Server on http://0.0.0.0:9390"

- [ ] **Step 2: Verify health**

```bash
curl -s http://127.0.0.1:9390/health
```

Expected: `{"status":"ok","framework":"FastMCP"}`

- [ ] **Step 3: Check tools/list (no system params in schema)**

```python
/opt/anaconda3/envs/ragflowplus/bin/python3 -c "
import sys, os
sys.path.insert(0, '.')
os.environ['LIGHTEN'] = '1'
from rag.agent.client.mcp_client import MCPClient
c = MCPClient('http://127.0.0.1:9390', timeout=30)
tools = c.list_tools()
openai_tools = c.get_openai_tools(tools)
for t in openai_tools:
    props = list(t['function']['parameters']['properties'].keys())
    print(f'{t[\"function\"][\"name\"]}: {props}')
"
```

Expected output — no `tenant_ids`/`kb_ids`/`tenant_id`/`embd_id`/`rerank_id` in any tool's properties.

- [ ] **Step 4: Run test script**

```bash
/opt/anaconda3/envs/ragflowplus/bin/python3 test_mcp_tools.py 2>&1
```

Expected: PASS, all 6 tools return results.

- [ ] **Step 5: Kill MCP server**

```bash
kill %1
```

---

### Task 8: Documentation update

- [ ] **Step 1: Update CLAUDE.md if needed**

Check if `CLAUDE.md` mentions `set_context` or `/initialize`:
```bash
grep -n "set_context\|/initialize\|_sessions" CLAUDE.md
```

If any references found, update them to reflect the new stateless architecture. Currently expected: no references (these were implementation details).

- [ ] **Step 2: Update rag/agent/__init__.py docstring if exists**

```bash
cat rag/agent/__init__.py 2>/dev/null || echo "No __init__.py"
```

Expected: the init file was deleted in cleanup, so no changes needed.

- [ ] **Step 3: Commit if changes made**

```bash
git add CLAUDE.md rag/agent/__init__.py
git commit -m "docs: update documentation for stateless MCP architecture

Co-Authored-By: Claude <noreply@anthropic.com>"
```
