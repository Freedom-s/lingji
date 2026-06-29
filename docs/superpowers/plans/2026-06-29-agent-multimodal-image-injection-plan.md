# AgentLoop 多模态图片注入 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 AgentLoop ReAct 循环结束后，将最相关的页面截图注入 user 消息，使 VLM 在最终答案生成时能看到课件截图。

**Architecture:** 纯 Python，在 `rag/agent/client/loop.py` 中新增两个方法和一个参数。循环后图片注入，不动 MCP 协议、不动 `chat_model.py`。复用 `dialog_service.py` 已有的 `get_image_base64_from_minio` 函数。

**Tech Stack:** Python 3.10+, MinIO client, `copy` 标准库

## Global Constraints

- 只改 `rag/agent/client/loop.py`，不动其他文件
- `max_images` 默认 5，0 表示关闭图片注入
- 单张图片获取失败不阻断流程
- `get_image_base64_from_minio` import 失败降级为纯文本

---

## File Structure

```
rag/agent/client/loop.py          ← 全部改动在此文件
  + _fetch_images_from_minio()    ← 新增：去重→排序→截断→MinIO 拉取
  + _inject_images_to_user_message() ← 新增：改写 user 消息为 multimodal
  ~ run()                         ← 修改：加 max_images 参数，循环后调用上述两方法
```

---

### Task 1: 新增 `_fetch_images_from_minio` 方法

**Files:**
- Modify: `rag/agent/client/loop.py` — 在 `_build_final_response` 方法之后（第 395 行后）插入新方法

**Interfaces:**
- Consumes: `retrieved_pages: list[dict]`（ReAct 循环积累的页面）, `max_images: int = 5`
- Produces: `list[str]` — base64 data URL 列表，按相关性降序

- [ ] **Step 1: 写入方法代码**

在 `rag/agent/client/loop.py` 第 395 行（`_build_final_response` 方法结束的 `}` 之后，文件末尾 `AgentLoop` 类结束前）插入：

```python
    def _fetch_images_from_minio(self, retrieved_pages: list[dict], max_images: int = 5) -> list[str]:
        """从检索结果中提取最相关的页面截图并转为 base64 data URL。

        去重 → 按相关性分数降序 → 取前 max_images 张 → MinIO 拉取 → base64。
        单张获取失败跳过，不阻断流程。
        """
        if max_images <= 0 or not retrieved_pages:
            return []

        # 1. 按 page_id 去重
        seen: set[str] = set()
        unique_pages: list[dict] = []
        for p in retrieved_pages:
            pid = p.get("page_id", "")
            if pid and pid not in seen:
                seen.add(pid)
                unique_pages.append(p)

        # 2. 按相关性分数降序排列
        def _score(p: dict) -> float:
            return float(
                p.get("rerank_score")
                or p.get("rrf_score")
                or p.get("similarity")
                or 0.0
            )
        unique_pages.sort(key=_score, reverse=True)

        # 3. 取前 max_images 张，筛选有 img_url 的
        candidates = [p for p in unique_pages[:max_images] if p.get("img_url")]
        if not candidates:
            logger.info("没有可注入的图片（所有候选页面均无 img_url）")
            return []

        # 4. 从 MinIO 获取 base64
        try:
            from api.db.services.dialog_service import get_image_base64_from_minio
        except ImportError:
            logger.warning("无法导入 get_image_base64_from_minio，跳过图片注入")
            return []

        images: list[str] = []
        for p in candidates:
            img_url = p.get("img_url", "")
            page_num = p.get("page_num_int", "?")
            doc_name = p.get("docnm_kwd", "")
            try:
                b64 = get_image_base64_from_minio(img_url)
                if b64:
                    images.append(b64)
                    logger.info(f"图片获取成功: {doc_name} p{page_num} ({len(b64)} chars)")
                else:
                    logger.warning(f"图片获取返回空: {doc_name} p{page_num} {img_url}")
            except Exception as e:
                logger.warning(f"图片获取异常 {doc_name} p{page_num} {img_url}: {e}")
                continue

        logger.info(f"图片注入准备: {len(images)}/{len(candidates)} 张成功")
        return images
```

- [ ] **Step 2: 验证语法正确**

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2 && python -c "import ast; ast.parse(open('rag/agent/client/loop.py').read()); print('Syntax OK')"
```

Expected: `Syntax OK`

- [ ] **Step 3: 验证方法可被 import**

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2 && python -c "
from rag.agent.client.loop import AgentLoop
import inspect
# 确认新方法存在
assert hasattr(AgentLoop, '_fetch_images_from_minio'), 'Method not found!'
sig = inspect.signature(AgentLoop._fetch_images_from_minio)
params = list(sig.parameters.keys())
print(f'_fetch_images_from_minio params: {params}')
assert 'retrieved_pages' in params
assert 'max_images' in params
print('Method signature OK')
"
```

Expected: `_fetch_images_from_minio params: ['self', 'retrieved_pages', 'max_images']` 后跟 `Method signature OK`

- [ ] **Step 4: Commit**

```bash
git add rag/agent/client/loop.py
git commit -m "feat(agent): add _fetch_images_from_minio method for page screenshot retrieval

Deduplicates retrieved pages, sorts by relevance score, fetches top N
page screenshots from MinIO as base64 data URLs.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: 新增 `_inject_images_to_user_message` 方法

**Files:**
- Modify: `rag/agent/client/loop.py` — 在 Task 1 新增的方法之后插入

**Interfaces:**
- Consumes: `messages: list[dict]`, `images_base64: list[str]`
- Produces: `list[dict]` — 改写后的消息列表（深拷贝），第一个 user 消息变为 multimodal

- [ ] **Step 1: 写入方法代码**

在 Task 1 的 `_fetch_images_from_minio` 方法之后插入：

```python
    def _inject_images_to_user_message(self, messages: list[dict], images_base64: list[str]) -> list[dict]:
        """将 base64 图片注入第一个 user 消息，改写为 multimodal content 格式。

        找到第一个 role="user" 且 content 为纯文本的消息，
        将其 content 改写为 [{"type": "text", ...}, {"type": "image_url", ...}, ...]。

        如果 images_base64 为空，原样返回 messages（浅拷贝）。
        始终返回新列表，不修改传入的 messages。
        """
        if not images_base64:
            return list(messages)

        import copy
        msgs = copy.deepcopy(messages)

        for msg in msgs:
            if msg.get("role") == "user" and isinstance(msg.get("content"), str):
                original_text = msg["content"]
                content_parts: list[dict] = [
                    {"type": "text", "text": original_text},
                ]
                for b64 in images_base64:
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": b64, "detail": "auto"},
                    })
                msg["content"] = content_parts
                logger.info(
                    f"user 消息已改写为 multimodal: "
                    f"text_len={len(original_text)}, images={len(images_base64)}"
                )
                break
        else:
            # 没有找到可改写的 user 消息（理论上不会发生）
            logger.warning("未找到 role=user 且 content 为 str 的消息，跳过图片注入")

        return msgs
```

- [ ] **Step 2: 验证语法**

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2 && python -c "import ast; ast.parse(open('rag/agent/client/loop.py').read()); print('Syntax OK')"
```

Expected: `Syntax OK`

- [ ] **Step 3: 单元测试 — 验证消息改写逻辑**

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2 && python -c "
import json
from rag.agent.client.loop import AgentLoop

# 构造 mock agent
class MockChatMdl:
    pass

agent = AgentLoop(mcp_url='http://localhost:9390', chat_mdl=MockChatMdl())

# 测试 1: 正常注入
messages = [
    {'role': 'system', 'content': 'You are a helpful assistant.'},
    {'role': 'user', 'content': '勾股定理是什么？'},
    {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'call_1', 'type': 'function', 'function': {'name': 'hybrid_retrieve', 'arguments': '{}'}}]},
    {'role': 'tool', 'tool_call_id': 'call_1', 'content': '[hybrid_retrieve] 返回 1 个结果...'},
]
images = ['data:image/jpeg;base64,/9j/4AAQ', 'data:image/png;base64,iVBORw0KGgo=']

result = agent._inject_images_to_user_message(messages, images)

assert result is not messages, '应该返回新列表'
assert isinstance(result[1]['content'], list), '第二个消息 content 应为 list'
assert len(result[1]['content']) == 3, f'应为 3 个 part (1 text + 2 images)，实际 {len(result[1][\"content\"])}'
assert result[1]['content'][0] == {'type': 'text', 'text': '勾股定理是什么？'}, '第一个 part 应为原始文本'
assert result[1]['content'][1]['type'] == 'image_url', '第二个 part 应为 image_url'
assert result[1]['content'][2]['type'] == 'image_url', '第三个 part 应为 image_url'
assert result[1]['content'][1]['image_url']['detail'] == 'auto', 'detail 应为 auto'
print('测试 1 通过: 正常注入')

# 测试 2: 空 images 列表
result2 = agent._inject_images_to_user_message(messages, [])
assert isinstance(result2[1]['content'], str), '无图片时 content 应保持 str'
assert result2[1]['content'] == '勾股定理是什么？'
print('测试 2 通过: 空图片列表降级')

# 测试 3: 原始消息不变
original_content = messages[1]['content']
assert original_content == '勾股定理是什么？', '原始 messages 不应被修改'
print('测试 3 通过: 原始消息不变')

print('\\n所有 _inject_images_to_user_message 测试通过 ✅')
"
```

Expected: 3 个测试全部通过

- [ ] **Step 4: Commit**

```bash
git add rag/agent/client/loop.py
git commit -m "feat(agent): add _inject_images_to_user_message method for multimodal message construction

Converts the first user message from plain text to multimodal
[text, image_url x N] format for VLM image understanding.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: 修改 `run()` 方法签名和调用逻辑

**Files:**
- Modify: `rag/agent/client/loop.py` — 改 `run()` 签名（第 52 行）和 ReAct 循环结束后的逻辑（第 206-213 行）

**Interfaces:**
- Consumes: 新增参数 `max_images: int = 5`
- Produces: Generator 不变，`_stream_answer` 现在收到改写后的 multimodal messages

- [ ] **Step 1: 修改 `run()` 方法签名**

在 `rag/agent/client/loop.py` 第 52-61 行，将 `run()` 的参数声明修改为：

```python
    def run(
        self,
        question: str,
        history: list[dict],
        kb_ids: list[str],
        tenant_ids: list[str],
        dialog,
        embd_id: str | None = None,
        rerank_id: str | None = None,
        max_images: int = 5,
    ) -> Generator[dict, None, None]:
```

改动：在第 59 行 `rerank_id` 参数之后加一个逗号，新增第 60 行 `max_images: int = 5,`，其余不变。

- [ ] **Step 2: 在 ReAct 循环后插入图片注入逻辑**

在 `rag/agent/client/loop.py` 第 206 行 `break` 之后、第 208 行 `# 6. 流式生成最终答案` 之前，插入图片注入代码块：

找到：

```python
            # LLM 返回了文本回答（无 tool_calls）→ 退出循环，生成答案
            logger.info(f"[AGENT_TRACE] Turn {turn+1} LLM 决定直接回答，退出 ReAct 循环")
            break

        # 6. 流式生成最终答案
        answer = ""
```

改为：

```python
            # LLM 返回了文本回答（无 tool_calls）→ 退出循环，生成答案
            logger.info(f"[AGENT_TRACE] Turn {turn+1} LLM 决定直接回答，退出 ReAct 循环")
            break

        # 5.5 循环结束后：注入图片到 user 消息（多模态 VLM 支持）
        images_base64 = self._fetch_images_from_minio(retrieved_pages, max_images)
        if images_base64:
            logger.info(f"注入 {len(images_base64)} 张图片到 user 消息")
            messages = self._inject_images_to_user_message(messages, images_base64)

        # 6. 流式生成最终答案
        answer = ""
```

- [ ] **Step 3: 验证语法**

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2 && python -c "import ast; ast.parse(open('rag/agent/client/loop.py').read()); print('Syntax OK')"
```

Expected: `Syntax OK`

- [ ] **Step 4: 验证方法签名完整性**

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2 && python -c "
import inspect
from rag.agent.client.loop import AgentLoop

sig = inspect.signature(AgentLoop.run)
params = list(sig.parameters.keys())
print(f'run() params: {params}')
assert 'max_images' in params, 'max_images parameter missing!'
p = sig.parameters['max_images']
assert p.default == 5, f'Expected default=5, got {p.default}'
print('run() signature OK: max_images=5')
"
```

Expected: `run() params: [...]` 包含 `max_images`，后跟 `run() signature OK: max_images=5`

- [ ] **Step 5: Commit**

```bash
git add rag/agent/client/loop.py
git commit -m "feat(agent): inject page screenshots into VLM prompt after ReAct loop

After the ReAct loop ends, fetch the top N most relevant page screenshots
from MinIO as base64 and inject them into the user message as multimodal
content. This enables VLM to see actual courseware slides for visual
understanding (diagrams, formulas, tables, charts).

max_images defaults to 5, set to 0 to disable.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: 端到端验证

**Files:**
- 无新建文件 — 用已有的 `test_mcp_tools.py` 脚本 + AgentLoop 手动验证

**Interfaces:** 无新增接口

- [ ] **Step 1: 检查上游调用方兼容性**

`max_images` 有默认值 5，上游调用方（`conversation_app.py` 的 `_stream_with_agent`）不需要改动。验证：

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2 && grep -n "\.run(" api/apps/conversation_app.py
```

Expected: 显示调用行。确认调用不传 `max_images` 参数即可正常工作（使用默认值 5）。

- [ ] **Step 2: 运行已有测试确保没有回归**

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2 && python test_mcp_tools.py 2>&1 | tail -5
```

Expected: MCP 工具测试全部通过（如果有测试输出）

- [ ] **Step 3: 代码 diff 复查**

```bash
git diff HEAD~3..HEAD -- rag/agent/client/loop.py
```

逐段检查：
- `_fetch_images_from_minio`: 去重、排序、截断逻辑正确；错误降级覆盖完整
- `_inject_images_to_user_message`: deepcopy 安全；空列表降级；只改第一个 user 消息
- `run()`: max_images 参数默认值正确；循环后注入时机正确

- [ ] **Step 4: Commit**

```bash
# 如果有 UI 或文档改动
git add -A
git diff --cached --stat
git commit -m "chore(agent): finalize multimodal image injection implementation"
```
