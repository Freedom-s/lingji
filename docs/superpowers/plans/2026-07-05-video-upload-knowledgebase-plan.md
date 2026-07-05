# 视频文件上传 & 知识库集成 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打通视频文件上传→知识库→前端播放的完整链路，视频不做转换不参与检索。

**Architecture:** 在现有文件上传和知识库服务中新增视频分支。视频跳过 PDF 转换和页面图片生成，直接存 MinIO 原始文件 + 写 file 记录（不写 file_page）。添加到知识库时直接将 document 状态标记为完成。

**Tech Stack:** Python 3, Flask, mysql.connector, MinIO, ffmpeg

## Global Constraints

- 视频格式：mp4（主力），webm，mov
- 视频不做转换处理，不做缩略图，不参与检索
- 存储方式：直传 + 分块上传两种方式都支持
- 视频不生成 file_page 记录
- 视频 document 直接标记 status='1', run='3'（完成），无需解析步骤

---

## 文件结构

| 文件 | 职责 | 改动类型 |
|---|---|---|
| `management/server/services/files/utils.py` | FileType 枚举 | 新增 VIDEO 枚举值 |
| `management/server/routes/files/routes.py` | 文件上传路由，ALLOWED_EXTENSIONS | 新增视频扩展名 |
| `management/server/services/files/service.py` | 文件上传/删除/列表核心逻辑 | 核心改动：扩展名、类型识别、content_type_map、上传分支 |
| `management/server/services/knowledgebases/service.py` | 知识库文档管理 | 视频 document 跳过解析，直接标记完成 |

---

### Task 1: 扩展 FileType 枚举 + 路由层允许的扩展名

**Files:**
- Modify: `management/server/services/files/utils.py:7-16`
- Modify: `management/server/routes/files/routes.py:11`

**Interfaces:**
- Produces: `FileType.VIDEO = "video"`，路由层 `ALLOWED_EXTENSIONS` 新增 `"mp4", "webm", "mov"`

- [ ] **Step 1: 修改 utils.py 添加 VIDEO 枚举值**

```python
class FileType(StrEnum):
    FOLDER = "folder"
    PDF = "pdf"
    WORD = "word"
    EXCEL = "excel"
    PPT = "ppt"
    VISUAL = "visual"
    TEXT = "txt"
    HTML = "html"
    VIDEO = "video"
    OTHER = "other"
```

- [ ] **Step 2: 修改 routes/files/routes.py 扩展 ALLOWED_EXTENSIONS**

将第 11 行：
```python
ALLOWED_EXTENSIONS = {"txt", "pdf", "png", "jpg", "jpeg", "gif", "doc", "docx", "xls", "xlsx"}
```

改为：
```python
ALLOWED_EXTENSIONS = {"txt", "pdf", "png", "jpg", "jpeg", "gif", "doc", "docx", "xls", "xlsx", "mp4", "webm", "mov"}
```

- [ ] **Step 3: 提交**

```bash
git add management/server/services/files/utils.py management/server/routes/files/routes.py
git commit -m "feat: add VIDEO file type and video extensions to allowlist"
```

---

### Task 2: 扩展 service.py 的视频支持（核心）

**Files:**
- Modify: `management/server/services/files/service.py`

**Interfaces:**
- Consumes: `FileType.VIDEO` from Task 1
- Produces: 视频上传不转码，直接存 MinIO，不写 file_page 记录

- [ ] **Step 1: 扩展 ALLOWED_EXTENSIONS 和新增 VIDEO_EXTES**

将第 18 行：
```python
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "jpg", "jpeg", "png", "bmp", "txt", "md", "html", "csv"}
IMAGE_EXTES = {"jpg", "jpeg", "png", "bmp"}
```

改为：
```python
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "jpg", "jpeg", "png", "bmp", "txt", "md", "html", "csv", "mp4", "webm", "mov"}
IMAGE_EXTES = {"jpg", "jpeg", "png", "bmp"}
VIDEO_EXTES = {"mp4", "webm", "mov"}
```

- [ ] **Step 2: 更新 filename_type() 函数添加视频识别**

将第 27-46 行的 `filename_type()` 函数中，在 `return FileType.OTHER.value` 前增加视频判断：

```python
def filename_type(filename):
    """根据文件名确定文件类型"""
    ext = os.path.splitext(filename)[1].lower()

    if ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp"]:
        return FileType.VISUAL.value
    elif ext in [".pdf"]:
        return FileType.PDF.value
    elif ext in [".doc", ".docx"]:
        return FileType.WORD.value
    elif ext in [".xls", ".xlsx", ".csv"]:
        return FileType.EXCEL.value
    elif ext in [".ppt", ".pptx"]:
        return FileType.PPT.value
    elif ext in [".txt", ".md"]:
        return FileType.TEXT.value
    elif ext in [".html"]:
        return FileType.HTML.value
    elif ext in [".mp4", ".webm", ".mov"]:
        return FileType.VIDEO.value

    return FileType.OTHER.value
```

- [ ] **Step 3: 扩展 content_type_map 添加视频 MIME 类型**

将第 646-654 行的 `content_type_map` 改为：

```python
content_type_map = {
    '.pdf': 'application/pdf',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.bmp': 'image/bmp',
    '.webp': 'image/webp',
    '.mp4': 'video/mp4',
    '.webm': 'video/webm',
    '.mov': 'video/quicktime',
}
```

- [ ] **Step 4: 在 upload_files_to_server() 中添加视频分支**

在 `upload_files_to_server()` 中，**第 574-576 行**后（`is_image` 判断后面），增加视频分支。

即找到：
```python
                # 2. 判断文件类型，图片文件特殊处理
                file_ext = ext.lower().lstrip('.')
                is_image = file_ext in IMAGE_EXTES
                
                if is_image:
```

改为：
```python
                # 2. 判断文件类型，图片文件特殊处理
                file_ext = ext.lower().lstrip('.')
                is_image = file_ext in IMAGE_EXTES
                is_video = file_ext in VIDEO_EXTES
                
                if is_video:
                    # 视频文件：直接存储原始文件，不做转换
                    print(f"检测到视频文件: {filename}，跳过 PDF/图片转换")
                    page_images = []  # 视频没有页面图片
                    
                elif is_image:
```

- [ ] **Step 5: 提交**

```bash
git add management/server/services/files/service.py
git commit -m "feat: add video upload support - skip conversion, store raw video to MinIO"
```

---

### Task 3: 知识库添加视频文档时跳过解析

**Files:**
- Modify: `management/server/services/knowledgebases/service.py:556-752`

**Interfaces:**
- Consumes: `FileType.VIDEO.value = "video"` from Task 1
- Produces: 视频 document 的 `status='1'`（就绪）, `run='3'`（已完成），无需手动解析

- [ ] **Step 1: 修改 add_documents_to_knowledgebase() 中视频 document 的 status 和 run**

将第 698-704 行附近的 doc_params 构建改为按文件类型区分：

找到：
```python
                doc_params = [
                    doc_id,
                    create_time,
                    current_date,
                    create_time,
                    current_date,  # ID和时间
                    None,
                    kb_id,
                    default_parser_id,
                    default_parser_config,
                    default_source_type,  # thumbnail到source_type
                    file_type,
                    created_by,
                    file_name,
                    file_location,
                    file_size,  # type到size
                    0,
                    0,
                    0.0,
                    None,
                    None,  # token_num到process_begin_at
                    0.0,
                    None,
                    "0",
                    "1",  # process_duation到status
                ]
```

改为：
```python
                # 视频文件直接标记为完成，跳过解析
                is_video_doc = (file_type == FileType.VIDEO.value if hasattr(FileType, 'VIDEO') else file_type == "video")
                doc_run = "3" if is_video_doc else "0"
                doc_status = "1" if is_video_doc else "1"

                doc_params = [
                    doc_id,
                    create_time,
                    current_date,
                    create_time,
                    current_date,  # ID和时间
                    None,
                    kb_id,
                    default_parser_id,
                    default_parser_config,
                    default_source_type,  # thumbnail到source_type
                    file_type,
                    created_by,
                    file_name,
                    file_location,
                    file_size,  # type到size
                    0,
                    0,
                    0.0,
                    None,
                    None,  # token_num到process_begin_at
                    0.0,
                    None,
                    doc_run,
                    doc_status,  # process_duation到status
                ]
```

**注意：** 需要在 `add_documents_to_knowledgebase` 文件顶部导入区（原文件没有显式导入 FileType，因为它在 services/files/utils.py 中）。在当前的 `from utils import generate_uuid` 附近添加 `from services.files.utils import FileType`。

- [ ] **Step 2: 验证视频 document 不会被"未解析"拦截**

检查 `parse_document()` 方法（第 837 行）——当 `run='3'`（已完成）时，`_run_sequential_batch_parse` 中的查询 `WHERE kb_id = %s AND run != '3'` 会跳过该视频 document，确保不会尝试解析视频。

当前代码已经使用 `run != '3'` 过滤（第 1316 行），无需额外修改。

- [ ] **Step 3: 提交**

```bash
git add management/server/services/knowledgebases/service.py
git commit -m "feat: mark video documents as complete on add to knowledgebase"
```

---

### Task 4: 验证端到端流程 + 补充边界情况

**Files:**
- Modify: `management/server/services/files/service.py`

**说明：** 验证视频在删除（delete_file / batch_delete_files）时的行为。由于视频没有 `file_page` 记录和 `document` 记录中的页面信息，这些查询会返回空结果，删除逻辑天然兼容——但需要确认 `cleanup_minio_files()` 中的页面清理不会报错。

- [ ] **Step 1: 确认 cleanup_minio_files() 对视频兼容**

检查 `cleanup_minio_files()`（第 793-815 行）：它用 `list_objects(bucket, prefix=f"{file_id}/source/")` 和 `list_objects(bucket, prefix=f"{file_id}/pages/")` 遍历删除。视频只有 `source/` 目录，`pages/` 遍历结果为空，不会抛异常。

无需代码改动。

- [ ] **Step 2: 确认 delete_file() 对视频兼容**

检查 `delete_file()`（第 224-373 行）：
- 查询 `file2document` 和 `file_page` 关联记录 —— 视频无 page，`page_mappings` 为空
- 删除 `file_page` 记录 —— DELETE 条件 `WHERE file_id = %s`，对视频影响 0 行
- MinIO 删除 page 循环 —— 空列表不进入循环
- MinIO 删除 document 文件 —— 视频 document 的 `location` 字段存的是 source 路径，已在 file 删除中覆盖

无需代码改动。

- [ ] **Step 3: 提交（如果有改动）**

```bash
git commit -m "chore: verify video files compatible with existing delete logic"
```

---

### Task 5: 手动验证端到端流程

**Files:** 无代码改动

- [ ] **Step 1: 确认管理后台服务运行中**

```bash
# 确认 4 个服务都在运行
curl -s http://localhost:5000/api/v1/files 2>&1 | head -5
```

如果服务未启动，参考 CLAUDE.md 中的启动命令启动 management/server。

- [ ] **Step 2: 测试视频上传（小视频直传）**

用一个测试 mp4 文件（< 50MB）通过 API 上传：
```bash
# 先登录获取 token
TOKEN=$(curl -s -X POST http://localhost:5000/api/v1/login \
  -H "Content-Type: application/json" \
  -d '{"email":"teacher1@qq.com","password":"teacher1"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['token'])")

# 上传视频
curl -X POST http://localhost:5000/api/v1/files/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "files=@/path/to/test.mp4"
```

预期：返回 `"code": 0`，`"type": "video"`。

- [ ] **Step 3: 测试视频添加到知识库**

```bash
# 先创建一个知识库
KB_ID=$(curl -s -X POST http://localhost:5000/api/v1/knowledgebases \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"视频测试知识库","description":"test"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")

# 将视频添加到知识库
curl -X POST "http://localhost:5000/api/v1/knowledgebases/${KB_ID}/documents" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"file_ids\": [\"<上一步返回的视频 file_id>\"]}"
```

预期：返回 `"code": 201`。

- [ ] **Step 4: 验证 document 状态**

```bash
docker exec ragflow-mysql mysql -u root -pinfini_rag_flow rag_flow -e \
  "SELECT id, name, type, run, status FROM document WHERE kb_id='<KB_ID>'"
```

预期：视频 document 的 `type='video'`, `run='3'`, `status='1'`。

- [ ] **Step 5: 总结验证结果**

如果上面步骤都通过，记录到对话中："视频上传链路已验证通过：上传→知识库→document 状态正确"
```

