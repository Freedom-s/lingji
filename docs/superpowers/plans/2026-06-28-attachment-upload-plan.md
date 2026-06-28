# Attachment Upload Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在助教对话框中新增文件附件上传功能，支持 txt/md/pdf/ppt/pptx/doc/docx/图片，附件存 MinIO temp bucket，MySQL attachment 表记录路径。

**Architecture:** conversation_app.py 中新增 4 个端点 + `_stream_with_attachment()` 流式函数。附件上传 → MinIO + attachment 表；对话时按文件类型分支：图片 base64 → VLM，文本类提取文本 context → LLM。有附件时不走知识库检索。

**Tech Stack:** Python/Flask + Peewee ORM + MinIO + React/TypeScript + Ant Design

## Global Constraints

- 文件大小限制: 10MB
- 支持文件类型: txt, md, pdf, ppt, pptx, doc, docx, jpg, jpeg, png, gif, webp, bmp
- 附件按 conversation 隔离
- 有附件时只用附件回答，不走知识库检索
- 删除 conversation 时级联清理附件

---

## File Structure

### 后端（4 个文件）

| 文件 | 职责 |
|------|------|
| `api/db/db_models.py` | 新增 `Attachment` 模型 + `migrate_db` 迁移条目 |
| `api/db/services/attachment_service.py` | 新建，附件 CRUD（继承 CommonService） |
| `api/apps/conversation_app.py` | 新增 4 个端点 + `_stream_with_attachment()` + import 更新 |
| `api/db/services/conversation_service.py` | 新增 `cleanup_attachments_for_conversation()` 辅助函数 |

### 前端（4 个文件）

| 文件 | 职责 |
|------|------|
| `web/src/utils/api.ts` | 新增 4 个 API URL 常量 |
| `web/src/services/chat-service.ts` | 新增 4 个 API method 定义 |
| `web/src/hooks/temp-file-hooks.ts` | 改为调用新 API，更新类型定义 |
| `web/src/components/message-input/index.tsx` | 扩展文件类型白名单、新增图片缩略图预览、按附件有无分支调用不同 completion |

---

### Task 1: Attachment 数据模型 + 数据库迁移

**Files:**
- Modify: `api/db/db_models.py` (在 Conversation 模型后新增 Attachment，在 migrate_db 末尾新增迁移)

**Interfaces:**
- Produces: `Attachment` Peewee model class (table: `attachment`)
- Produces: `AttachmentService` will consume this model in Task 2

- [ ] **Step 1: 新增 Attachment 模型类**

在 `api/db/db_models.py` 的 `Conversation` 类定义之后（约第 1053 行之前），新增：

```python
class Attachment(DataBaseModel):
    id = CharField(max_length=32, primary_key=True)
    conversation_id = CharField(max_length=32, null=False, index=True, help_text="关联的对话ID")
    user_id = CharField(max_length=32, null=False, index=True, help_text="上传者ID")
    file_name = CharField(max_length=255, null=False, help_text="原始文件名")
    file_type = CharField(max_length=32, null=False, help_text="txt/md/pdf/ppt/pptx/doc/docx/image")
    file_size = IntegerField(default=0, help_text="文件大小(bytes)")
    mime_type = CharField(max_length=128, null=False, help_text="MIME类型")
    minio_path = CharField(max_length=512, null=False, help_text="MinIO存储路径")
    status = CharField(max_length=1, null=True, default="1", help_text="is it validate(0: wasted, 1: validate)", index=True)

    class Meta:
        db_table = "attachment"
```

- [ ] **Step 2: 在 migrate_db() 函数末尾新增迁移条目**

在 `api/db/db_models.py` 的 `migrate_db()` 函数中，最后一个 `try/except` 块之后、函数结束之前，新增：

```python
        try:
            migrate(
                migrator.create_table(Attachment)
            )
        except Exception:
            pass
```

- [ ] **Step 3: 验证数据库迁移**

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2
conda run -n ragflowplus python -c "
from api.db.db_models import migrate_db
migrate_db()
print('Migration OK - attachment table should exist')
"
```

验证 table 创建成功：

```bash
docker exec ragflow-mysql mysql -u root -pinfini_rag_flow rag_flow -e "DESC attachment;"
```

Expected: 显示 attachment 表的字段结构（id, conversation_id, user_id, file_name, file_type, file_size, mime_type, minio_path, status）。

- [ ] **Step 4: Commit**

```bash
git add api/db/db_models.py
git commit -m "feat: add Attachment model and migration"
```

---

### Task 2: AttachmentService 服务层

**Files:**
- Create: `api/db/services/attachment_service.py`

**Interfaces:**
- Consumes: `Attachment` model from `api.db.db_models` (Task 1)
- Produces: `AttachmentService` class
  - `AttachmentService.query(conversation_id=..., user_id=..., status=...)` → list
  - `AttachmentService.get_by_id(id)` → (bool, Attachment)
  - `AttachmentService.save(**kwargs)` → Attachment
  - `AttachmentService.delete_by_id(id)` → int
  - `AttachmentService.update_by_id(id, data)` → int
  - `AttachmentService.get_by_conversation(conversation_id)` → list (status=1)

- [ ] **Step 1: 创建 AttachmentService 类**

```python
# api/db/services/attachment_service.py
from api.db.db_models import Attachment, DB
from api.db.services.common_service import CommonService
from api.db import StatusEnum


class AttachmentService(CommonService):
    model = Attachment

    @classmethod
    @DB.connection_context()
    def get_by_conversation(cls, conversation_id):
        """获取某个对话下所有有效附件"""
        return list(
            cls.model.select().where(
                (cls.model.conversation_id == conversation_id) &
                (cls.model.status == StatusEnum.VALID.value)
            )
        )

    @classmethod
    @DB.connection_context()
    def logical_delete_by_conversation(cls, conversation_id):
        """逻辑删除某个对话下所有附件"""
        return cls.model.update(
            status=StatusEnum.INVALID.value
        ).where(
            cls.model.conversation_id == conversation_id
        ).execute()
```

- [ ] **Step 2: 验证服务层基本可用**

```bash
conda run -n ragflowplus python -c "
from api.db.services.attachment_service import AttachmentService
print('AttachmentService imported OK')
print('Model:', AttachmentService.model)
print('Methods:', [m for m in dir(AttachmentService) if not m.startswith('_')])
"
```

- [ ] **Step 3: Commit**

```bash
git add api/db/services/attachment_service.py
git commit -m "feat: add AttachmentService"
```

---

### Task 3: 文件上传端点 + MinIO 存储

**Files:**
- Modify: `api/apps/conversation_app.py` (新增 import + 新增端点函数)

**Interfaces:**
- Consumes: `AttachmentService` from Task 2
- Consumes: `get_minio_client` from `api.db.services.dialog_service` (via `management/server/database.py`)
- Produces: `POST /v1/conversation/upload_attachment` endpoint
  - Request: multipart/form-data with `file` field
  - Response: `{code: 0, data: {attachment_id, file_name, file_type, file_size, mime_type}}`

- [ ] **Step 1: 在 conversation_app.py 顶部新增 import**

在现有 import 块末尾新增：

```python
import io as std_io
from PIL import Image
from api.db.services.attachment_service import AttachmentService
from management.server.database import get_minio_client
from api.utils import get_uuid, current_timestamp
```

- [ ] **Step 2: 新增 upload_attachment 端点**

在 `conversation_app.py` 的 `upload_temp_file` 端点后、`tts` 端点前（约第 634 行前）新增：

```python
ALLOWED_EXTENSIONS = {
    'txt', 'md', 'pdf', 'ppt', 'pptx', 'doc', 'docx',
    'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'}


def _get_file_type(ext: str) -> str:
    """根据扩展名返回 file_type"""
    if ext in IMAGE_EXTENSIONS:
        return 'image'
    if ext in ('txt', 'md'):
        return ext
    if ext == 'pdf':
        return 'pdf'
    if ext in ('ppt', 'pptx'):
        return 'ppt'
    if ext in ('doc', 'docx'):
        return 'doc'
    return ext


@manager.route("/upload_attachment", methods=["POST"])  # noqa: F821
@login_required
def upload_attachment():
    """上传附件到 MinIO temp bucket + MySQL attachment 表"""
    try:
        if 'file' not in request.files:
            return get_data_error_result(message="未检测到文件")

        file = request.files['file']
        if file.filename == '':
            return get_data_error_result(message="未选择文件")

        # 检查扩展名
        file_ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if file_ext not in ALLOWED_EXTENSIONS:
            return get_data_error_result(
                message=f"不支持的文件格式 .{file_ext}。支持的类型：{', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )

        # 检查文件大小
        file_content = file.read()
        if len(file_content) > MAX_FILE_SIZE:
            return get_data_error_result(message="文件大小不能超过10MB")

        # 生成 ID 和 MinIO 路径
        attachment_id = get_uuid()
        conversation_id = request.form.get('conversation_id', '')
        minio_path = f"{conversation_id}/{attachment_id}/{file.filename}"

        # 上传到 MinIO temp bucket
        minio_client = get_minio_client()
        bucket_name = "temp"
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)

        minio_client.put_object(
            bucket_name,
            minio_path,
            std_io.BytesIO(file_content),
            len(file_content)
        )

        # 写入 MySQL
        file_type = _get_file_type(file_ext)
        AttachmentService.save(
            id=attachment_id,
            conversation_id=conversation_id,
            user_id=current_user.id,
            file_name=file.filename,
            file_type=file_type,
            file_size=len(file_content),
            mime_type=file.content_type or 'application/octet-stream',
            minio_path=minio_path,
            status="1"
        )

        return get_json_result(data={
            "attachment_id": attachment_id,
            "file_name": file.filename,
            "file_type": file_type,
            "file_size": len(file_content),
            "mime_type": file.content_type or 'application/octet-stream'
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return server_error_response(e)
```

- [ ] **Step 3: 验证端点**

```bash
conda run -n ragflowplus python -c "
from api.apps.conversation_app import upload_attachment, ALLOWED_EXTENSIONS
print('upload_attachment imported OK')
print('Allowed extensions:', sorted(ALLOWED_EXTENSIONS))
"
```

- [ ] **Step 4: Commit**

```bash
git add api/apps/conversation_app.py
git commit -m "feat: add upload_attachment endpoint with MinIO storage"
```

---

### Task 4: completion_with_attachment 端点（SSE 流式）

**Files:**
- Modify: `api/apps/conversation_app.py`

**Interfaces:**
- Consumes: `AttachmentService` from Task 2, `LLMBundle` from `api.db.services.llm_service`, `structure_answer` from `conversation_service`
- Produces: `POST /v1/conversation/completion_with_attachment` SSE endpoint
  - Request: `{conversation_id, messages, attachment_ids}`
  - Response: SSE `text/event-stream`，格式与 `/completion` 一致

- [ ] **Step 1: 新增文件内容提取辅助函数**

在 `conversation_app.py` 中 `_should_use_agent` 函数附近新增：

```python
def _extract_attachment_content(minio_path: str, file_type: str) -> str:
    """从 MinIO 读取附件并提取文本内容"""
    minio_client = get_minio_client()
    bucket_name = "temp"
    try:
        response = minio_client.get_object(bucket_name, minio_path)
        content_bytes = response.read()
        response.close()
        response.release_conn()
    except Exception as e:
        return f"[读取附件失败: {e}]"

    if file_type in ('txt', 'md'):
        encodings = ['utf-8', 'gbk', 'gb2312', 'big5', 'latin1']
        for enc in encodings:
            try:
                return content_bytes.decode(enc)
            except UnicodeDecodeError:
                continue
        return content_bytes.decode('utf-8', errors='ignore')

    if file_type == 'doc':
        try:
            import olefile
            from docx2txt import process as docx2txt_process
            import tempfile, os
            with tempfile.NamedTemporaryFile(delete=False, suffix='.doc') as tmp:
                tmp.write(content_bytes)
                tmp_path = tmp.name
            text = docx2txt_process(tmp_path)
            os.unlink(tmp_path)
            return text
        except ImportError:
            return "[缺少 doc 解析库(docx2txt)]"
        except Exception as e:
            return f"[.doc 文件解析失败: {e}]"

    if file_type == 'docx':
        try:
            from docx import Document
            doc_stream = std_io.BytesIO(content_bytes)
            doc = Document(doc_stream)
            paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_text:
                        paragraphs.append(' | '.join(row_text))
            return '\n\n'.join(paragraphs) if paragraphs else '[文档内容为空]'
        except Exception as e:
            return f"[.docx 文件解析失败: {e}]"

    if file_type == 'pdf':
        try:
            import PyPDF2
            pdf_reader = PyPDF2.PdfReader(std_io.BytesIO(content_bytes))
            pages = []
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            return '\n\n'.join(pages) if pages else '[PDF 无可提取文本]'
        except ImportError:
            return '[缺少 PDF 解析库(PyPDF2)]'
        except Exception as e:
            return f"[PDF 解析失败: {e}]"

    if file_type == 'ppt':
        try:
            from pptx import Presentation
            prs = Presentation(std_io.BytesIO(content_bytes))
            slides = []
            for i, slide in enumerate(prs.slides, 1):
                slide_text = []
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        for para in shape.text_frame.paragraphs:
                            if para.text.strip():
                                slide_text.append(para.text.strip())
                if slide_text:
                    slides.append(f"[第{i}页]\n" + '\n'.join(slide_text))
            return '\n\n'.join(slides) if slides else '[PPT 无可提取文本]'
        except ImportError:
            return '[缺少 PPT 解析库(python-pptx)]'
        except Exception as e:
            return f"[PPT 解析失败: {e}]"

    return f"[不支持的内容提取: {file_type}]"


def _get_attachment_image_base64(minio_path: str) -> str:
    """从 MinIO 读取图片并返回 base64 data URL"""
    minio_client = get_minio_client()
    try:
        response = minio_client.get_object("temp", minio_path)
        content_bytes = response.read()
        response.close()
        response.release_conn()
    except Exception as e:
        return f"[读取图片失败: {e}]"

    ext = minio_path.rsplit('.', 1)[-1].lower() if '.' in minio_path else 'jpg'
    mime_map = {'jpg': 'jpeg', 'jpeg': 'jpeg', 'png': 'png', 'gif': 'gif', 'webp': 'webp', 'bmp': 'bmp'}
    mime = f"image/{mime_map.get(ext, 'jpeg')}"
    b64 = base64.b64encode(content_bytes).decode('utf-8')
    return f"data:{mime};base64,{b64}"
```

- [ ] **Step 2: 新增 _stream_with_attachment() 流式函数**

在 `_stream_with_agent()` 函数之后新增：

```python
def _stream_with_attachment(dia, msg, conv, message_id, req):
    """使用附件内容进行流式对话（不走知识库检索）"""
    from api.db.services.llm_service import LLMBundle
    from api.db import LLMType
    import json as json_module

    attachment_ids = req.get("attachment_ids", [])
    if not attachment_ids:
        yield "data:" + json_module.dumps(
            {"code": 500, "message": "缺少附件ID", "data": {"answer": "**ERROR**: 缺少附件ID"}},
            ensure_ascii=False
        ) + "\n\n"
        return

    # 读取附件信息
    attachments = AttachmentService.get_by_ids(attachment_ids)

    # 分类：图片 vs 文本
    image_attachments = []
    text_attachments = []

    for att in attachments:
        if att.file_type == 'image':
            image_attachments.append(att)
        else:
            text_attachments.append(att)

    # 提取文本内容作为 system prompt context
    text_context_parts = []
    for att in text_attachments:
        content = _extract_attachment_content(att.minio_path, att.file_type)
        text_context_parts.append(f"[附件: {att.file_name}]\n{content}")

    system_prompt = "你是一个智能助手，请基于用户上传的文件内容回答问题。"
    if text_context_parts:
        system_prompt += "\n\n以下是用户上传的文件内容：\n\n" + "\n\n---\n\n".join(text_context_parts)

    # 构建 history（不含 system prompt）
    history = []
    for m in msg[:-1]:  # 历史消息
        history.append({"role": m["role"], "content": m.get("content", "")})

    # 构建最后一条用户消息（如果有图片，用 vision 格式）
    last_msg = msg[-1]
    user_content = last_msg.get("content", "")

    chat_mdl = LLMBundle(dia.tenant_id, LLMType.CHAT, dia.llm_id)

    if image_attachments:
        # 多图片：按 OpenAI Vision 格式构建 content array
        content_parts = [{"type": "text", "text": user_content}]
        for att in image_attachments:
            b64_url = _get_attachment_image_base64(att.minio_path)
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": b64_url}
            })
        history.append({"role": "user", "content": content_parts})
    else:
        # 纯文本附件：直接拼接
        history.append({"role": "user", "content": user_content})

    # 流式输出
    for chunk in chat_mdl.chat_streamly(system_prompt, history):
        ans = structure_answer(conv, chunk, message_id, conv.id)
        yield "data:" + json_module.dumps(
            {"code": 0, "message": "", "data": ans},
            ensure_ascii=False
        ) + "\n\n"
```

- [ ] **Step 3: 新增 completion_with_attachment 端点**

```python
@manager.route("/completion_with_attachment", methods=["POST"])  # noqa: F821
@login_required
@validate_request("conversation_id", "messages", "attachment_ids")
def completion_with_attachment():
    req = request.json
    msg = []
    for m in req["messages"]:
        if m["role"] == "system":
            continue
        if m["role"] == "assistant" and not msg:
            continue
        msg.append({"id": m.get("id", str(uuid.uuid4())), "role": m.get("role"), "content": m.get("content"),
                     "attachments": m.get("attachments", [])})

    message_id = msg[-1].get("id")
    try:
        e, conv = ConversationService.get_by_id(req["conversation_id"])
        if not e:
            return get_data_error_result(message="Conversation not found!")

        conv.message = deepcopy(msg)
        if not conv.reference:
            conv.reference = []
        conv.reference.append({"chunks": [], "doc_aggs": []})

        e, dia = DialogService.get_by_id(conv.dialog_id)
        if not e:
            return get_data_error_result(message="Dialog not found!")

        def stream():
            nonlocal dia, msg, req, conv
            try:
                for ans in _stream_with_attachment(dia, msg, conv, message_id, req):
                    yield ans
                ConversationService.update_by_id(conv.id, conv.to_dict())
            except Exception as e:
                traceback.print_exc()
                yield "data:" + json.dumps(
                    {"code": 500, "message": str(e), "data": {"answer": "**ERROR**: " + str(e), "reference": {}}},
                    ensure_ascii=False
                ) + "\n\n"
            yield "data:" + json.dumps({"code": 0, "message": "", "data": True}, ensure_ascii=False) + "\n\n"

        if req.get("stream", True):
            resp = Response(stream(), mimetype="text/event-stream")
            resp.headers.add_header("Cache-control", "no-cache")
            resp.headers.add_header("Connection", "keep-alive")
            resp.headers.add_header("X-Accel-Buffering", "no")
            resp.headers.add_header("Content-Type", "text/event-stream; charset=utf-8")
            return resp

    except Exception as e:
        return server_error_response(e)
```

- [ ] **Step 4: 验证语法正确**

```bash
conda run -n ragflowplus python -c "
import py_compile
py_compile.compile('/Users/suojianhua/PyProjects/ragflow-plus-version2/api/apps/conversation_app.py', doraise=True)
print('conversation_app.py compiles OK')
"
```

- [ ] **Step 5: Commit**

```bash
git add api/apps/conversation_app.py
git commit -m "feat: add completion_with_attachment SSE endpoint"
```

---

### Task 5: 缩略图 + 删除附件端点

**Files:**
- Modify: `api/apps/conversation_app.py`

**Interfaces:**
- Produces: `GET /v1/conversation/attachment/<attachment_id>/thumbnail` → 图片返回 200px 宽缩略图，非图片返回 404
- Produces: `DELETE /v1/conversation/attachment/<attachment_id>` → 删除 MinIO 文件 + 逻辑删除记录

- [ ] **Step 1: 新增缩略图端点**

```python
@manager.route("/attachment/<attachment_id>/thumbnail", methods=["GET"])  # noqa: F821
@login_required
def attachment_thumbnail(attachment_id):
    """获取附件缩略图（仅图片类型）"""
    try:
        e, att = AttachmentService.get_by_id(attachment_id)
        if not e:
            return get_data_error_result(message="附件不存在")

        if att.file_type != 'image':
            return get_data_error_result(message="非图片类型无缩略图", code=404)

        minio_client = get_minio_client()
        response = minio_client.get_object("temp", att.minio_path)
        content_bytes = response.read()
        response.close()
        response.release_conn()

        # 生成 200px 宽缩略图
        image = Image.open(std_io.BytesIO(content_bytes))
        image.thumbnail((200, 200 * image.height // image.width), Image.LANCZOS)
        output = std_io.BytesIO()
        image_format = image.format or 'JPEG'
        image.save(output, format=image_format)
        output.seek(0)

        mime = att.mime_type or 'image/jpeg'
        return Response(output.getvalue(), mimetype=mime)

    except Exception as e:
        return server_error_response(e)
```

- [ ] **Step 2: 新增删除附件端点**

```python
@manager.route("/attachment/<attachment_id>", methods=["DELETE"])  # noqa: F821
@login_required
def delete_attachment(attachment_id):
    """删除单个附件（MinIO + 逻辑删除）"""
    try:
        e, att = AttachmentService.get_by_id(attachment_id)
        if not e:
            return get_data_error_result(message="附件不存在")

        # 从 MinIO 删除文件
        try:
            minio_client = get_minio_client()
            minio_client.remove_object("temp", att.minio_path)
        except Exception:
            pass  # MinIO 文件可能已被清理，忽略

        # 逻辑删除 MySQL 记录
        AttachmentService.update_by_id(attachment_id, {"status": "0"})

        return get_json_result(data=True)
    except Exception as e:
        return server_error_response(e)
```

- [ ] **Step 3: 验证端点语法**

```bash
conda run -n ragflowplus python -c "
import py_compile
py_compile.compile('/Users/suojianhua/PyProjects/ragflow-plus-version2/api/apps/conversation_app.py', doraise=True)
print('OK')
"
```

- [ ] **Step 4: Commit**

```bash
git add api/apps/conversation_app.py
git commit -m "feat: add attachment thumbnail and delete endpoints"
```

---

### Task 6: 对话删除时级联清理附件

**Files:**
- Modify: `api/db/services/conversation_service.py`
- Modify: `api/apps/conversation_app.py` (rm 端点)

**Interfaces:**
- Consumes: `AttachmentService` from Task 2
- Produces: `cleanup_attachments_for_conversation(conversation_id)` function— deletes from MinIO + marks invalid in MySQL

- [ ] **Step 1: 在 conversation_service.py 新增清理函数**

在 `conversation_service.py` 文件末尾新增：

```python
def cleanup_attachments_for_conversation(conversation_id: str):
    """删除指定 conversation 下所有附件（MinIO 文件 + MySQL 逻辑删除）"""
    from api.db.services.attachment_service import AttachmentService
    from management.server.database import get_minio_client

    attachments = AttachmentService.get_by_conversation(conversation_id)
    minio_client = get_minio_client()
    for att in attachments:
        try:
            minio_client.remove_object("temp", att.minio_path)
        except Exception:
            pass  # 文件可能已不存在
    AttachmentService.logical_delete_by_conversation(conversation_id)
```

- [ ] **Step 2: 在 conversation_app.py 的 rm 端点中调用清理**

在 `conversation_app.py` 的 `rm()` 函数（约第 317-335 行），在 `ConversationService.delete_by_id(cid)` 之前新增调用：

找到这段代码：
```python
            for tenant in tenants:
                if DialogService.query(tenant_id=tenant.tenant_id, id=conv.dialog_id):
                    break
            else:
                return get_data_error_result(data=False, message="Only owner of conversation authorized for this operation.", code=settings.RetCode.OPERATING_ERROR)
            ConversationService.delete_by_id(cid)
```

替换为：
```python
            for tenant in tenants:
                if DialogService.query(tenant_id=tenant.tenant_id, id=conv.dialog_id):
                    break
            else:
                return get_data_error_result(data=False, message="Only owner of conversation authorized for this operation.", code=settings.RetCode.OPERATING_ERROR)
            cleanup_attachments_for_conversation(cid)
            ConversationService.delete_by_id(cid)
```

同时在 `conversation_app.py` 顶部 import 中新增：
```python
from api.db.services.conversation_service import ConversationService, structure_answer, cleanup_attachments_for_conversation
```

- [ ] **Step 3: 验证语法正确**

```bash
conda run -n ragflowplus python -c "
from api.db.services.conversation_service import cleanup_attachments_for_conversation
from api.apps.conversation_app import rm
print('All imports OK')
"
```

- [ ] **Step 4: Commit**

```bash
git add api/db/services/conversation_service.py api/apps/conversation_app.py
git commit -m "feat: cascade cleanup attachments on conversation delete"
```

---

### Task 7: 前端 API 层更新

**Files:**
- Modify: `web/src/utils/api.ts`
- Modify: `web/src/services/chat-service.ts`
- Modify: `web/src/hooks/temp-file-hooks.ts`

**Interfaces:**
- Produces: 4 个新 API URL: `uploadAttachment`, `completionWithAttachment`, `getAttachmentThumbnail`, `deleteAttachment`
- Produces: `useUploadAttachment` hook

- [ ] **Step 1: 在 api.ts 中新增 API URL 常量**

在 `web/src/utils/api.ts` 的临时文件 API 后面（约第 127 行后）新增：

```typescript
  // 附件上传和获取API (MinIO持久化方案)
  uploadAttachment: `${api_host}/conversation/upload_attachment`,
  completionWithAttachment: `${api_host}/conversation/completion_with_attachment`,
  getAttachmentThumbnail: (attachmentId: string) =>
    `${api_host}/conversation/attachment/${attachmentId}/thumbnail`,
  deleteAttachment: (attachmentId: string) =>
    `${api_host}/conversation/attachment/${attachmentId}`,
```

- [ ] **Step 2: 在 chat-service.ts 中新增 API method 定义**

在 `web/src/services/chat-service.ts` 的 import 解构中新增变量，在 methods 对象末尾新增：

```typescript
// 在 import 解构中新增（约第 2-32 行）
const {
  // ... 现有变量 ...
  uploadAttachment,
  completionWithAttachment,
  getAttachmentThumbnail,
  deleteAttachment,
} = api;

// 在 methods 对象末尾（约第 139 行前）新增：
  uploadAttachment: {
    url: uploadAttachment,
    method: 'post',
  },
  completionWithAttachment: {
    url: completionWithAttachment,
    method: 'post',
  },
  getAttachmentThumbnail: {
    url: getAttachmentThumbnail,
    method: 'get',
  },
  deleteAttachment: {
    url: deleteAttachment,
    method: 'delete',
  },
```

- [ ] **Step 3: 更新 temp-file-hooks.ts 类型和 API 调用**

替换 `web/src/hooks/temp-file-hooks.ts` 全部内容：

```typescript
import chatService from '@/services/chat-service';
import { useMutation } from '@tanstack/react-query';

export interface IAttachmentInfo {
  attachment_id: string;
  file_name: string;
  file_type: string;
  file_size: number;
  mime_type: string;
}

export const useUploadAttachment = () => {
  const {
    data,
    isPending: loading,
    mutateAsync,
  } = useMutation({
    mutationKey: ['uploadAttachment'],
    mutationFn: async (params: { file: File; conversationId?: string }) => {
      if (!params?.file) {
        throw new Error('No file provided for upload');
      }

      const formData = new FormData();
      formData.append('file', params.file);
      if (params.conversationId) {
        formData.append('conversation_id', params.conversationId);
      }

      const response = await chatService.uploadAttachment(formData);
      const actualResponse = Array.isArray(response) ? response[0] : response;
      const data = actualResponse?.data || actualResponse;

      if (data?.code === 0) {
        return data.data as IAttachmentInfo;
      } else {
        throw new Error(data?.message || 'Upload failed');
      }
    },
  });

  return { data, loading, uploadAttachment: mutateAsync };
};

export const useDeleteAttachment = () => {
  const deleteAttachment = async (attachmentId: string) => {
    const response = await chatService.deleteAttachment({ url: attachmentId });
    const data = response?.data || response;
    if (data?.code === 0) {
      return true;
    }
    throw new Error(data?.message || 'Delete failed');
  };

  return { deleteAttachment };
};

export const getAttachmentThumbnailUrl = (attachmentId: string): string => {
  // chatService.getAttachmentThumbnail uses template URL, construct the URL directly
  return `/v1/conversation/attachment/${attachmentId}/thumbnail`;
};
```

- [ ] **Step 4: 验证前端编译**

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2/web
npx tsc --noEmit --skipLibCheck 2>&1 | head -30
```

- [ ] **Step 5: Commit**

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2/web
git add src/utils/api.ts src/services/chat-service.ts src/hooks/temp-file-hooks.ts
git commit -m "feat: add attachment API layer (hooks + service + URLs)"
```

---

### Task 8: MessageInput 组件更新

**Files:**
- Modify: `web/src/components/message-input/index.tsx`

**Interfaces:**
- Consumes: `useUploadAttachment` hook from Task 7
- Produces: 更新后的 MessageInput，支持扩展文件类型、图片缩略图、分支发送逻辑

- [ ] **Step 1: 更新 import 和文件类型白名单**

在 `web/src/components/message-input/index.tsx` 中，替换 import 行和文件类型常量：

```typescript
// 替换 import
import { IAttachmentInfo, useUploadAttachment } from '@/hooks/temp-file-hooks';

// 新增图片扩展名数组（在组件顶部，getBase64 函数之前）
const IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'];

const isImageFile = (fileName: string) => {
  const ext = fileName.split('.').pop()?.toLowerCase() || '';
  return IMAGE_EXTENSIONS.includes(ext);
};
```

- [ ] **Step 2: 替换 hook 调用**

将组件内部的：
```typescript
const { uploadTempFile } = useUploadTempFile();
```
替换为：
```typescript
const { uploadAttachment } = useUploadAttachment();
```

- [ ] **Step 3: 更新 handleChange 中的上传调用**

将 `handleChange` 中的 `useTempUpload` 分支内的：
```typescript
const tempFileInfo = await uploadTempFile({
  file: fileToUpload,
  conversationId: conversationId,
});
```
替换为：
```typescript
const attachmentInfo = await uploadAttachment({
  file: fileToUpload as File,
  conversationId: conversationId,
});
```

并将后续的 `setTempFiles` 调用改为存储 `IAttachmentInfo` 类型。

- [ ] **Step 4: 更新文件列表渲染，增加图片缩略图**

在渲染文件列表的 `renderItem` 中，新增图片缩略图展示逻辑。在文件名旁边、`<FileIcon>` 之前新增：

```typescript
{isImageFile(fileName) && (
  <img
    src={getAttachmentThumbnailUrl(tempFileInfo?.attachment_id)}
    alt={fileName}
    style={{ width: 40, height: 40, objectFit: 'cover', borderRadius: 4 }}
  />
)}
```

需要在顶部 import 中引入：
```typescript
import { getAttachmentThumbnailUrl } from '@/hooks/temp-file-hooks';
```

- [ ] **Step 5: 更新 handlePressEnter 中的发送分支逻辑**

将现有的 `handlePressEnter` 改为根据有无附件调用不同端点。将其中只发送 `ids` 的逻辑改为：

```typescript
const handlePressEnter = useCallback(async () => {
  if (isUploadingFile) return;

  const ids = getFileIds(fileList.filter((x) => isUploadSuccess(x)));
  
  // 传递附件信息给上层组件
  onPressEnter(ids, tempFiles);
  
  setFileList([]);
  setTempFiles([]);
}, [fileList, tempFiles, onPressEnter, isUploadingFile]);
```

- [ ] **Step 6: 更新 Upload 的 accept 属性**

将 `accept` 属性从：
```typescript
accept={
  useTempUpload
    ? '.txt,.docx,.md,.json,.xml,.csv,.py,.js,.html,.css'
    : undefined
}
```
替换为：
```typescript
accept={
  useTempUpload
    ? '.txt,.md,.pdf,.ppt,.pptx,.doc,.docx,.jpg,.jpeg,.png,.gif,.webp,.bmp'
    : undefined
}
```

- [ ] **Step 7: 更新 beforeUpload 中的文件类型检查**

```typescript
const allowedExtensions = [
  '.txt', '.md', '.pdf', '.ppt', '.pptx', '.doc', '.docx',
  '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp',
];
```

- [ ] **Step 8: 验证前端编译**

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2/web
npx tsc --noEmit --skipLibCheck 2>&1 | head -40
```

- [ ] **Step 9: Commit**

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2/web
git add src/components/message-input/index.tsx
git commit -m "feat: update MessageInput for attachment upload with image thumbnails"
```

---

### Task 9: 发送逻辑分层集成

**Files:**
- Modify: `web/src/pages/chat/hooks.ts` (useSendNextMessage hook, 约第 358-501 行)
- Modify: `web/src/components/message-input/index.tsx` (IProps.onPressEnter 类型)

**Interfaces:**
- Consumes: `IAttachmentInfo` from Task 7, `api.completionWithAttachment` from Task 7
- Produces: `handlePressEnter(documentIds, attachments?)` — 有附件时用 `sendWithAttachment`，否则用 `send`

- [ ] **Step 1: 在 useSendNextMessage 中新增第二个 SSE hook 实例**

`useSendNextMessage` 目前只能用 `useSendMessageWithSse(api.completeConversation)` 这一个 URL。需要新增第二个 hook 实例用于附件对话。

在 `web/src/pages/chat/hooks.ts` 的 `useSendNextMessage` 函数中（约第 364 行），在现有的：
```typescript
const { send, answer, done } = useSendMessageWithSse(
  api.completeConversation,
);
```
之后新增：
```typescript
// 附件对话 SSE（使用 completion_with_attachment 端点）
const {
  send: sendWithAttachment,
  answer: answerWithAttachment,
  done: doneWithAttachment,
} = useSendMessageWithSse(api.completionWithAttachment);
```

同时需要在文件顶部的 import 中引入 `api`（如果尚未引入），以及 `IAttachmentInfo`：
```typescript
import { IAttachmentInfo } from '@/hooks/temp-file-hooks';
```

- [ ] **Step 2: 新增 handleSendMessageWithAttachment 函数**

在 `handleSendMessage` 函数之后（约第 418 行后）新增：

```typescript
const handleSendMessageWithAttachment = useCallback(
  async ({
    message,
    currentConversationId,
    messages,
    attachmentIds,
  }: {
    message: Message;
    currentConversationId?: string;
    messages?: Message[];
    attachmentIds: string[];
  }) => {
    const res = await sendWithAttachment(
      {
        conversation_id: currentConversationId ?? conversationId,
        messages: [...(messages ?? derivedMessages ?? []), message],
        attachment_ids: attachmentIds,
      },
      controller,
    );

    if (res && (res?.response.status !== 200 || res?.data?.code !== 0)) {
      setValue(message.content);
      removeLatestMessage();
    }
  },
  [
    derivedMessages,
    conversationId,
    removeLatestMessage,
    setValue,
    sendWithAttachment,
    controller,
  ],
);
```

- [ ] **Step 3: 更新 handlePressEnter 支持附件参数**

替换现有的 `handlePressEnter`（约第 464-486 行）：

```typescript
const handlePressEnter = useCallback(
  (documentIds: string[], attachments?: IAttachmentInfo[]) => {
    if (trim(value) === '' && !attachments?.length) return;
    const id = uuid();

    const hasAttachments = attachments && attachments.length > 0;
    const attachmentIds = hasAttachments
      ? attachments!.map((a) => a.attachment_id)
      : [];

    addNewestQuestion({
      content: value,
      doc_ids: documentIds,
      id,
      role: MessageType.User,
      ...(hasAttachments && {
        attachments: attachments!.map((a) => ({
          id: a.attachment_id,
          file_name: a.file_name,
          file_type: a.file_type,
          file_size: a.file_size,
          mime_type: a.mime_type,
        })),
      }),
    });

    if (hasAttachments ? doneWithAttachment : done) {
      setValue('');
      const msg: Message = {
        id,
        content: value.trim(),
        role: MessageType.User,
        doc_ids: documentIds,
        ...(hasAttachments && {
          attachments: attachments!.map((a) => ({
            id: a.attachment_id,
            file_name: a.file_name,
            file_type: a.file_type,
            file_size: a.file_size,
            mime_type: a.mime_type,
          })),
        }),
      };

      if (hasAttachments) {
        const isNew = getConversationIsNew();
        if (isNew !== 'true') {
          handleSendMessageWithAttachment({
            message: msg,
            attachmentIds,
          });
        } else {
          // 新对话：先创建 conversation 再发消息
          setConversation(value, true, conversationId).then((data) => {
            if (data.code === 0) {
              setConversationIsNew('');
              handleSendMessageWithAttachment({
                message: msg,
                currentConversationId: data.data.id,
                messages: data.data.message,
                attachmentIds,
              });
            }
          });
        }
      } else {
        handleSendMessage({ message: msg });
      }
    }
  },
  [
    addNewestQuestion,
    handleSendMessage,
    handleSendMessageWithAttachment,
    setConversation,
    setConversationIsNew,
    getConversationIsNew,
    done,
    doneWithAttachment,
    setValue,
    value,
    conversationId,
  ],
);
```

- [ ] **Step 4: 更新 useEffect 订阅附件 answer**

在现有的 answer useEffect（约第 457-462 行）之后新增：

```typescript
useEffect(() => {
  if (answerWithAttachment.answer && conversationId && isNew !== 'true') {
    addNewestAnswer(answerWithAttachment);
  }
}, [answerWithAttachment, addNewestAnswer, conversationId, isNew]);
```

- [ ] **Step 5: 更新返回值新增 doneWithAttachment**

在 `useSendNextMessage` 的返回对象中新增：
```typescript
return {
  handlePressEnter,
  handleInputChange,
  value,
  setValue,
  regenerateMessage,
  sendLoading: !done || !doneWithAttachment,
  loading,
  ref,
  derivedMessages,
  removeMessageById,
  stopOutputMessage,
};
```

- [ ] **Step 6: 更新 MessageInput 的 onPressEnter prop 类型**

在 `web/src/components/message-input/index.tsx` 的 `IProps` 接口中（约第 76-90 行），更新 `onPressEnter` 签名：

```typescript
onPressEnter(documentIds: string[], attachments?: IAttachmentInfo[]): void;
```

同时在该文件顶部的 import 中新增：
```typescript
import { IAttachmentInfo, getAttachmentThumbnailUrl } from '@/hooks/temp-file-hooks';
```

在 `handlePressEnter` 的调用处（约第 228 行），更新调用：
```typescript
// 替换 onPressEnter(ids);
onPressEnter(ids, tempFiles);
```

- [ ] **Step 7: 验证类型检查**

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2/web
npx tsc --noEmit --skipLibCheck 2>&1 | head -40
```

- [ ] **Step 8: Commit**

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2/web
git add src/pages/chat/hooks.ts src/components/message-input/index.tsx
git commit -m "feat: integrate attachment upload with chat send flow"
```
