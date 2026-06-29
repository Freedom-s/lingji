# AgentLoop 多模态图片注入设计

**日期**: 2026-06-29
**状态**: 设计中
**范围**: `rag/agent/client/loop.py`

## 背景

RAGFlow-Plus 的文档解析管道为每一页课件生成两类数据并存入 Elasticsearch：

- `content_with_weight`：OCR 提取的文本
- `img_url`：课件页面的真实截图（MinIO 路径）

MCP Server 的检索工具（`hybrid_retrieve` 等）返回的每个 chunk 同时包含 `full_content`（OCR 文本）和 `img_url`（截图路径）。

当前 AgentLoop 在 ReAct 决策循环和最终答案生成阶段都只使用 OCR 文本，完全忽略了课件截图。但课件中的**几何图形、公式排版、流程图、表格布局**等视觉信息，OCR 文本无法准确传达。

## 问题

OpenAI 兼容 API 的多模态消息格式限制：图片（`image_url`）只能放在 `role: "user"` 消息中，不能放在 `role: "tool"` 消息中。MCP 协议的工具返回值只能走 tool 角色，因此**无法在 ReAct 循环中向 LLM 传递图片**。

## 方案

**循环后注入**：ReAct 循环保持纯文本决策，循环结束后将最相关的页面截图注入 user 消息，再调用 VLM 生成最终答案。

### 数据流

```
ReAct 循环（不变，纯文本）
  │
  ├─ messages: [system, user, assistant+tool_calls, tool, ...]
  ├─ retrieved_pages: [{page_id, full_content, img_url, rerank_score, ...}, ...]
  │
  ▼ 循环 break
  │
① 图片选择 → 去重 → 按 rerank_score 降序 → 取前 max_images 张
② 图片获取 → MinIO 拉取 → base64 编码
③ 消息改写 → 第一个 user 消息的 content 改为 [text, image_url × N]
④ 生成答案 → chat_streamly()（本身支持 multimodal content）
⑤ 返回 → answer + reference
```

## 设计

### 1. 新增 `_fetch_images_from_minio(retrieved_pages, max_images=5) -> list[str]`

- 按 `page_id` 去重
- 按 `rerank_score` → `rrf_score` → `similarity` 降序排列
- 取前 `max_images` 张，筛选有 `img_url` 的
- 调用 `get_image_base64_from_minio(img_url)` 获取 base64 data URL（复用 `api/db/services/dialog_service.py` 已有函数）
- 返回成功获取的 base64 列表（单张失败跳过，不阻断流程）

### 2. 新增 `_inject_images_to_user_message(messages, images_base64) -> list[dict]`

- 深拷贝 `messages`
- 找到第一个 `role="user"` 且 `content` 为 `str` 的消息
- 将其 `content` 改写为 multimodal 格式：
  ```json
  [
    {"type": "text", "text": "原问题文本"},
    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,...", "detail": "auto"}},
    ...
  ]
  ```
- 如果 `images_base64` 为空，原样返回，不改写

### 3. 修改 `run()` 方法

- 新增参数 `max_images: int = 5`
- 在 ReAct 循环 break 之后、`_stream_answer` 调用之前插入：
  ```python
  images_base64 = self._fetch_images_from_minio(retrieved_pages, max_images)
  messages = self._inject_images_to_user_message(messages, images_base64)
  ```

### 4. 不改动的部分

- MCP Server / Client：不动
- `chat_with_tools()`：不动（ReAct 循环仍然是纯文本）
- `chat_streamly()`：**本身已支持 multimodal content**，无需修改
- `_build_retrieval_context()`：不动（文本上下文仍然全量进入 system prompt）
- `_stream_answer()`：**不改签名**（图片已注入到传入的 messages 中）

## 错误降级

| 场景 | 行为 |
|------|------|
| 所有 chunk 都没有 `img_url` | images_base64 = []，消息不改写，纯文本回答 |
| MinIO 部分图片不可达 | 单张返回 None，跳过，其余正常 |
| MinIO 全部不可达 | 纯文本降级 |
| `get_image_base64_from_minio` import 失败 | 捕获 ImportError，跳过图片注入 |

## 依赖

- `api.db.services.dialog_service.get_image_base64_from_minio` — 已有函数，从 MinIO 拉取图片并返回 base64 data URL
- `rag.llm.chat_model.Base.chat_streamly` — 本身支持 multimodal content list，无需改动

## 测试要点

1. 正常流程：检索到带图片的页面 → 多模态回答
2. 降级流程：检索到无图片的页面 → 纯文本回答
3. MinIO 不可用：跳过图片，不阻断回答
4. `max_images=0`：等同于关闭图片注入
5. 去重正确性：同一 page_id 只在 images 中出现一次
