# Attachment Upload Feature Design

> 日期：2026-06-28
> 状态：已确认
> 范围：助教问答对话框中新增文件附件上传功能

## 1. 概述

用户在助教对话框中可以上传附件（txt/md/pdf/ppt/pptx/doc/docx/图片），系统基于附件内容回答用户问题。附件通过 MinIO 存储，MySQL `attachment` 表记录路径，按 conversation 隔离。

### 核心决策

| 决策 | 结论 |
|------|------|
| 附件 vs 知识库 | 有附件时只用附件回答，不走知识库检索 |
| 附件作用域 | 按 conversation 隔离 |
| 附件信息存储 | 存到 conversation 的 message JSON 中 |
| 附件存储 | MinIO `temp` bucket + MySQL `attachment` 表 |
| 生命周期 | 删除 conversation 时级联清理 |

---

## 2. 数据库设计

### 2.1 Attachment 表

```python
class Attachment(DataBaseModel):
    id = CharField(max_length=32, primary_key=True)          # UUID
    conversation_id = CharField(max_length=32, index=True)    # 关联对话
    user_id = CharField(max_length=32, index=True)            # 上传者
    file_name = CharField(max_length=255)                     # 原始文件名
    file_type = CharField(max_length=32)                      # txt/md/pdf/ppt/pptx/doc/docx/image
    file_size = IntegerField(default=0)                       # 字节数
    mime_type = CharField(max_length=128)                     # MIME 类型
    minio_path = CharField(max_length=512)                    # MinIO 路径
    status = CharField(max_length=1, default="1", index=True) # 1=有效 0=已删除
    create_time = BigIntegerField(default=0)
    update_time = BigIntegerField(default=0)

    class Meta:
        db_table = "attachment"
```

位置：`api/db/db_models.py`，在 `migrate_db()` 函数（第 1111 行附近）中新增迁移。

### 2.2 message JSON 中的附件信息

```json
{
  "id": "msg-uuid",
  "role": "user",
  "content": "请帮我分析这个文档",
  "attachments": [
    {
      "id": "attachment-uuid",
      "file_name": "课程大纲.pdf",
      "file_type": "pdf",
      "file_size": 204800,
      "mime_type": "application/pdf"
    }
  ]
}
```

---

## 3. MinIO 存储

### 3.1 Bucket 与路径

- Bucket: `temp`（新建，首次上传时自动创建）
- 路径模式: `{conversation_id}/{attachment_id}/{original_filename}`
- 示例: `temp/abc123/def456/课程大纲.pdf`

---

## 4. API 设计

### 4.1 附件上传

```
POST /v1/conversation/upload_attachment
```

- Content-Type: `multipart/form-data`
- 字段: `file`
- 文件类型白名单: txt, md, pdf, ppt, pptx, doc, docx, jpg, jpeg, png, gif, webp, bmp
- 大小限制: 10MB
- 响应:
```json
{
  "code": 0,
  "data": {
    "attachment_id": "uuid",
    "file_name": "课程大纲.pdf",
    "file_type": "pdf",
    "file_size": 204800,
    "mime_type": "application/pdf"
  }
}
```

### 4.2 附件对话（流式）

```
POST /v1/conversation/completion_with_attachment
```

- Content-Type: `application/json`
- 请求体:
```json
{
  "conversation_id": "xxx",
  "messages": [
    {"id": "1", "role": "user", "content": "总结一下", "attachments": [{"id": "att-1", ...}]}
  ],
  "attachment_ids": ["att-1", "att-2"]
}
```
- 响应: `text/event-stream` SSE 流式，格式与现有 `/completion` 一致
- 处理流程：读取附件 → 按类型提取内容 → 拼 prompt → LLM 流式返回

### 4.3 缩略图

```
GET /v1/conversation/attachment/<attachment_id>/thumbnail
```

- 仅图片类型返回缩略图（等比压缩到 200px 宽），非图片类型返回 404

### 4.4 删除附件

```
DELETE /v1/conversation/attachment/<attachment_id>
```

- 从 MinIO 删除文件，逻辑删除 attachment 记录（status → 0）

---

## 5. 后端处理逻辑

### 5.1 文件处理分支

```
completion_with_attachment
  │
  ├─ 图片 (jpg/png/gif/webp/bmp)
  │   └─ MinIO 读取 → base64 编码 → 拼入 VLM message（OpenAI Vision 格式）
  │
  ├─ 文本 (txt/md/doc/docx)
  │   └─ MinIO 读取 → 文本提取 → 拼入 system prompt
  │
  ├─ PDF
  │   └─ MinIO 读取 → PyPDF2/pdfplumber 提取 → 拼入 system prompt
  │
  ├─ PPT/PPTX
  │   └─ MinIO 读取 → python-pptx 提取 → 拼入 system prompt
  │
  └─ 不支持的格式 → 返回错误
```

### 5.2 新增函数

在 `conversation_app.py` 中新增 `_stream_with_attachment()`:
- 不走 agent / MCP / 知识库检索
- 直接用 `LLMBundle` 调用 chat 模型（VLM）
- 图片传 base64，文本类拼入 system prompt context
- 输出与 `structure_answer()` 兼容的 SSE 格式

### 5.3 级联清理

在 `ConversationService.delete_by_id()` 中新增钩子：
1. 查询该 conversation 下所有有效 attachment
2. 逐个从 MinIO `temp` bucket 删除对应文件
3. 逻辑删除 attachment 记录（status → 0）

---

## 6. 前端设计

### 6.1 MessageInput 组件改动

文件: `web/src/components/message-input/index.tsx`

- 上传端点改为 `POST /v1/conversation/upload_attachment`
- 支持的文件类型扩展为: `.txt, .md, .pdf, .ppt, .pptx, .doc, .docx, .jpg, .jpeg, .png, .gif, .webp, .bmp`
- 图片上传后显示缩略图预览

### 6.2 发送流程

```
发送消息
  │
  ├─ 有附件？→ 调用 /v1/conversation/completion_with_attachment
  └─ 无附件？→ 调用 /v1/conversation/completion（现有逻辑）
```

### 6.3 消息气泡附件展示

- 文本类文件（txt/md/pdf/doc/pptx 等）：显示文件名 + 文件类型图标（复用 `FileIcon` 组件）
- 图片文件：显示缩略图，可点击放大

---

## 7. 文件清单

### 后端

| 文件 | 改动 |
|------|------|
| `api/db/db_models.py` | 新增 `Attachment` 模型 + `migrate_db` 迁移 |
| `api/db/services/attachment_service.py` | 新建，附件 CRUD |
| `api/apps/conversation_app.py` | 新增 4 个端点 + `_stream_with_attachment()` |
| `api/db/services/conversation_service.py` | 删除时级联清理附件 |

### 前端

| 文件 | 改动 |
|------|------|
| `web/src/components/message-input/index.tsx` | 扩展文件类型、新上传端点、图片缩略图 |
| `web/src/hooks/temp-file-hooks.ts` | 改为调用新 API `/v1/conversation/upload_attachment` |
| `web/src/components/message-item/` | 消息气泡中渲染附件信息（如有改动） |

---

## 8. 不在范围内

- 不实现附件内容检索（有附件时不走知识库）
- 不支持视频、音频、压缩包等类型
- 不实现附件跨 conversation 共享
- 不实现定时清理任务（仅级联删除）
