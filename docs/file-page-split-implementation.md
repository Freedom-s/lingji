# 文件页面拆分功能实现文档

## 📋 文档概述

**功能名称**：文件上传自动拆分为页面图片  
**版本**：v1.0  
**创建日期**：2025-01-13  
**作者**：Kiro AI Assistant  
**项目**：Ragflow-Plus

---

## 🎯 需求背景

### 业务需求

在 Ragflow-Plus 的后台管理系统中，管理员上传文档时，需要实现以下功能：

1. **自动格式转换**：将各种格式文档（Word、Excel、PPT、Markdown、HTML等）统一转换为 PDF
2. **页面拆分**：将 PDF 文档按页拆分为独立的图片文件
3. **分层存储**：在 MinIO 中同时保存原始文件和页面图片
4. **数据记录**：在数据库中记录文件信息和每页图片的元数据

### 应用场景

- **文档预览**：前端可以按页加载图片，提升预览性能
- **图文检索**：支持在 RAG 检索时返回相关页面的图片
- **文档分析**：为后续的 OCR、版面分析等功能提供基础
- **存储优化**：图片可以独立缓存和压缩

---

## 🏗️ 系统架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    Ragflow-Plus 系统                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐         ┌──────────────────┐         │
│  │   前台系统 (api)  │         │ 后台管理 (mgmt)   │         │
│  ├──────────────────┤         ├──────────────────┤         │
│  │ • 用户界面        │         │ • 管理员界面      │         │
│  │ • RAG 检索       │         │ • 文件上传 ⭐     │         │
│  │ • 对话交互        │         │ • 用户管理        │         │
│  │ • web/ (前端)    │         │ • web/ (前端)    │         │
│  │ • api/ (后端)    │         │ • server/ (后端) │         │
│  └──────────────────┘         └──────────────────┘         │
│           │                            │                     │
│           └────────────┬───────────────┘                     │
│                        │                                     │
│              ┌─────────▼─────────┐                          │
│              │   共享数据库       │                          │
│              │  (MySQL/PG)       │                          │
│              │ • file            │                          │
│              │ • file_page ⭐    │                          │
│              │ • document        │                          │
│              └───────────────────┘                          │
│                        │                                     │
│              ┌─────────▼─────────┐                          │
│              │   MinIO 存储      │                          │
│              │ bucket/file_id/   │                          │
│              │  ├─ source/       │                          │
│              │  └─ pages/ ⭐     │                          │
│              └───────────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```



### 核心组件说明

#### 1. 前台系统 (api/)
- **职责**：面向最终用户，提供 RAG 检索、对话交互等功能
- **数据库**：定义所有数据模型（`api/db/db_models.py`）
- **启动入口**：`api/ragflow_server.py`

#### 2. 后台管理系统 (management/)
- **职责**：面向管理员，提供用户管理、文件管理、配置管理等功能
- **数据库**：通过 `database.py` 连接到与前台相同的数据库
- **启动入口**：`management/server/app.py`
- **本次改动重点**：文件上传功能增强

#### 3. 共享数据库
- **类型**：MySQL 或 PostgreSQL
- **模型定义位置**：`api/db/db_models.py`（唯一真实来源）
- **表创建机制**：`init_database_tables()` 自动扫描 `DataBaseModel` 子类
- **本次新增表**：`file_page`

#### 4. MinIO 对象存储
- **用途**：存储文件和图片
- **结构**：分层存储（source + pages）
- **访问**：通过 `get_minio_client()` 获取客户端

---

## 📊 数据库设计

### 现有表结构

#### File 表（现有）
```sql
CREATE TABLE file (
    id VARCHAR(32) PRIMARY KEY,
    parent_id VARCHAR(32) NOT NULL,      -- 父文件夹ID（也是MinIO bucket名）
    tenant_id VARCHAR(32) NOT NULL,      -- 租户ID
    created_by VARCHAR(32) NOT NULL,     -- 创建者ID
    name VARCHAR(255) NOT NULL,          -- 文件名
    location VARCHAR(255),               -- MinIO存储路径
    size INT DEFAULT 0,                  -- 文件大小
    type VARCHAR(32) NOT NULL,           -- 文件类型
    source_type VARCHAR(128) DEFAULT '', -- 来源类型
    create_time BIGINT,
    create_date DATETIME,
    update_time BIGINT,
    update_date DATETIME,
    INDEX idx_parent_id (parent_id),
    INDEX idx_tenant_id (tenant_id),
    INDEX idx_created_by (created_by)
);
```

#### File2Document 表（现有）
```sql
CREATE TABLE file2document (
    id VARCHAR(32) PRIMARY KEY,
    file_id VARCHAR(32),                 -- 关联file表
    document_id VARCHAR(32),             -- 关联document表
    INDEX idx_file_id (file_id),
    INDEX idx_document_id (document_id)
);
```

### 新增表结构

#### FilePage 表（新增）⭐
```sql
CREATE TABLE file_page (
    id VARCHAR(32) PRIMARY KEY,
    file_id VARCHAR(32) NOT NULL,        -- 关联file表
    page_number INT NOT NULL,            -- 页码（从1开始）
    location VARCHAR(255) NOT NULL,      -- MinIO存储路径
    size INT DEFAULT 0,                  -- 图片大小（字节）
    width INT DEFAULT 0,                 -- 图片宽度（像素）
    height INT DEFAULT 0,                -- 图片高度（像素）
    format VARCHAR(16) DEFAULT 'JPEG',   -- 图片格式
    create_time BIGINT,
    create_date DATETIME,
    update_time BIGINT,
    update_date DATETIME,
    INDEX idx_file_id (file_id),
    INDEX idx_page_number (page_number)
);
```



### 表关系图

```
┌─────────────┐
│    File     │
│  (文件表)    │
├─────────────┤
│ id (PK)     │◄─────┐
│ parent_id   │      │
│ name        │      │
│ location    │      │  1:N
│ size        │      │
│ type        │      │
└─────────────┘      │
                     │
                     │
              ┌──────┴──────┐
              │  FilePage   │
              │ (页面表) ⭐  │
              ├─────────────┤
              │ id (PK)     │
              │ file_id (FK)│
              │ page_number │
              │ location    │
              │ size        │
              │ width       │
              │ height      │
              │ format      │
              └─────────────┘
```

**关系说明**：
- 一个 File 可以有多个 FilePage（1:N）
- file_id 是外键，关联到 file.id
- page_number 表示页码顺序

---

## 🗄️ MinIO 存储设计

### 存储结构

```
{parent_id}/                          # Bucket名称（父文件夹ID）
└── {file_id}/                        # 文件ID作为目录
    ├── source/                       # 原始文件目录
    │   └── document.pdf              # 原始文件
    │       location: {file_id}/source/document.pdf
    │
    └── pages/                        # 页面图片目录
        ├── 0001.jpg                  # 第1页
        │   location: {file_id}/pages/0001.jpg
        ├── 0002.jpg                  # 第2页
        │   location: {file_id}/pages/0002.jpg
        ├── 0003.jpg                  # 第3页
        └── ...
```

### 存储规则

1. **Bucket 命名**：使用 `parent_id`（父文件夹ID）
2. **文件目录**：使用 `file_id` 作为一级目录
3. **分层存储**：
   - `source/`：存放原始文件
   - `pages/`：存放页面图片
4. **文件命名**：
   - 原始文件：保持原文件名
   - 页面图片：`{page_number:04d}.jpg`（补零4位，如 0001.jpg）

### 示例

假设上传文件 `report.docx`：

```
parent_id = "folder_abc123"
file_id = "file_xyz789"

MinIO 结构：
folder_abc123/                        # Bucket
└── file_xyz789/                      # 文件目录
    ├── source/
    │   └── report.docx               # 原始文件
    └── pages/
        ├── 0001.jpg                  # 第1页（封面）
        ├── 0002.jpg                  # 第2页
        └── 0003.jpg                  # 第3页

数据库记录：
file 表：
  id: file_xyz789
  parent_id: folder_abc123
  name: report.docx
  location: file_xyz789/source/report.docx
  size: 1024000

file_page 表：
  id: page_001, file_id: file_xyz789, page_number: 1, location: file_xyz789/pages/0001.jpg
  id: page_002, file_id: file_xyz789, page_number: 2, location: file_xyz789/pages/0002.jpg
  id: page_003, file_id: file_xyz789, page_number: 3, location: file_xyz789/pages/0003.jpg
```



---

## 🔄 处理流程

### 完整流程图

```
┌─────────────────────────────────────────────────────────────┐
│                     文件上传处理流程                          │
└─────────────────────────────────────────────────────────────┘

    用户上传文件
         │
         ▼
    ┌─────────────────┐
    │ 1. 接收文件      │
    │ routes.py       │
    │ /upload API     │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ 2. 保存到临时目录 │
    │ /tmp/uploads/   │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ 3. 文件类型判断  │
    │ • PDF: 直接使用  │
    │ • 其他: 转换     │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ 4. 转换为 PDF    │
    │ Gotenberg API   │
    │ • Office → PDF  │
    │ • HTML → PDF    │
    │ • MD → PDF      │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ 5. PDF 转图片    │
    │ PyMuPDF (fitz)  │
    │ • 按页渲染       │
    │ • 生成 JPEG     │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ 6. 上传到 MinIO  │
    │ • source/原始   │
    │ • pages/图片    │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ 7. 保存数据库    │
    │ • file 表       │
    │ • file_page 表  │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ 8. 清理临时文件  │
    │ 删除 /tmp 文件  │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ 9. 返回结果      │
    │ JSON Response   │
    └─────────────────┘
```



### 详细步骤说明

#### 步骤 1：接收文件
**位置**：`management/server/routes/files/routes.py`

```python
@files_bp.route("/upload", methods=["POST"])
def upload_file():
    if "files" not in request.files:
        return jsonify({"code": 400, "message": "未选择文件"}), 400
    
    files = request.files.getlist("files")
    upload_result = upload_files_to_server(files)
    
    return jsonify({"code": 0, "message": "上传成功", "data": upload_result["data"]})
```

**输入**：
- HTTP POST 请求
- Content-Type: multipart/form-data
- 字段名：files（可多文件）

**输出**：
- 调用 `upload_files_to_server()` 处理

---

#### 步骤 2：保存到临时目录
**位置**：`management/server/services/files/service.py`

```python
UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), "uploads")
filepath = os.path.join(UPLOAD_FOLDER, filename)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
file.save(filepath)
```

**目的**：
- 将上传的文件保存到本地临时目录
- 便于后续处理和转换

**临时目录**：
- Linux/Mac: `/tmp/uploads/`
- Windows: `C:\Users\xxx\AppData\Local\Temp\uploads\`

---

#### 步骤 3：文件类型判断
**位置**：`management/server/services/files/service.py`

```python
ext = file_path.rsplit(".", 1)[-1].lower()

if ext in LIBREOFFICE_EXTS:      # doc, docx, ppt, pptx, xls, xlsx, txt, csv
    # 需要转换
elif ext in HTML_EXTS:            # html
    # 需要转换
elif ext in MARKDOWN_EXTS:        # md
    # 需要转换
elif ext in PDF_EXTS:             # pdf
    # 直接使用
else:
    raise ValueError(f"不支持的文件类型: {ext}")
```

**支持的文件类型**：
- Office 文档：doc, docx, ppt, pptx, xls, xlsx
- 文本文件：txt, csv, md
- 网页文件：html
- PDF 文件：pdf

---

#### 步骤 4：转换为 PDF
**位置**：`management/server/services/files/converters/pdf_converter.py`

**依赖服务**：Gotenberg（http://localhost:3000）

**转换函数**：
```python
# Office 文档转 PDF
convert_office_to_pdf(file_path, gotenberg_url="http://localhost:3000")

# HTML 转 PDF
convert_html_to_pdf(file_path, gotenberg_url="http://localhost:3000")

# Markdown 转 PDF
convert_markdown_to_pdf(file_path, gotenberg_url="http://localhost:3000")
```

**返回**：PDF 文件的字节流（bytes）

**Gotenberg API 端点**：
- Office: `/forms/libreoffice/convert`
- HTML: `/forms/chromium/convert/html`
- Markdown: `/forms/chromium/convert/markdown`



---

#### 步骤 5：PDF 转图片
**位置**：`management/server/services/files/converters/image_converter.py`

**使用库**：PyMuPDF (fitz)

**核心代码**：
```python
import fitz  # PyMuPDF

def pdf_to_images(pdf_bytes: bytes, dpi: int = 150) -> List[Tuple[bytes, int, int]]:
    """
    将 PDF 转换为图片列表
    
    Args:
        pdf_bytes: PDF 文件字节流
        dpi: 图片分辨率（默认 150）
    
    Returns:
        List[Tuple[bytes, width, height]]: 每页的(图片字节, 宽度, 高度)
    """
    images = []
    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    for page_num in range(pdf_document.page_count):
        page = pdf_document[page_num]
        
        # 设置缩放比例（DPI 转换）
        zoom = dpi / 72  # PDF 默认 72 DPI
        mat = fitz.Matrix(zoom, zoom)
        
        # 渲染页面为图片
        pix = page.get_pixmap(matrix=mat)
        
        # 转换为 JPEG 字节流
        img_bytes = pix.tobytes(output="jpeg")
        
        images.append((img_bytes, pix.width, pix.height))
    
    pdf_document.close()
    return images
```

**参数说明**：
- `dpi`：图片分辨率
  - 72: 低质量（文件小）
  - 150: 标准质量（推荐）⭐
  - 300: 高质量（文件大）
- `output`：图片格式
  - jpeg: 有损压缩，文件小（推荐）⭐
  - png: 无损压缩，文件大

**返回值**：
- 每页返回一个元组：`(图片字节流, 宽度, 高度)`
- 列表顺序即为页码顺序

---

#### 步骤 6：上传到 MinIO
**位置**：`management/server/services/files/service.py`

**6.1 上传原始文件**
```python
minio_client = get_minio_client()

# 确保 bucket 存在
if not minio_client.bucket_exists(parent_id):
    minio_client.make_bucket(parent_id)

# 上传原始文件到 source/
source_location = f"{file_id}/source/{filename}"
with open(filepath, "rb") as f:
    minio_client.put_object(
        bucket_name=parent_id,
        object_name=source_location,
        data=f,
        length=os.path.getsize(filepath)
    )
```

**6.2 上传页面图片**
```python
from io import BytesIO

for idx, (img_bytes, width, height) in enumerate(page_images, start=1):
    page_location = f"{file_id}/pages/{idx:04d}.jpg"
    
    img_stream = BytesIO(img_bytes)
    minio_client.put_object(
        bucket_name=parent_id,
        object_name=page_location,
        data=img_stream,
        length=len(img_bytes),
        content_type="image/jpeg"
    )
```

**关键点**：
- `bucket_name`：使用 `parent_id`
- `object_name`：完整路径（包含目录）
- `content_type`：设置正确的 MIME 类型



---

#### 步骤 7：保存数据库
**位置**：`management/server/services/files/service.py`

**7.1 插入 file 记录**
```python
conn = get_db_connection()
cursor = conn.cursor()

file_record = {
    "id": file_id,                          # UUID
    "parent_id": parent_id,                 # 父文件夹ID（bucket）
    "tenant_id": user_id,                   # 租户ID
    "created_by": user_id,                  # 创建者ID
    "name": filename,                       # 文件名
    "type": filetype,                       # 文件类型
    "size": os.path.getsize(filepath),      # 文件大小
    "location": source_location,            # MinIO路径
    "source_type": "local",                 # 来源类型
    "create_time": current_time,            # 创建时间戳
    "create_date": current_date,            # 创建日期
    "update_time": current_time,
    "update_date": current_date,
}

columns = ", ".join(file_record.keys())
placeholders = ", ".join(["%s"] * len(file_record))
query = f"INSERT INTO file ({columns}) VALUES ({placeholders})"
cursor.execute(query, list(file_record.values()))
```

**7.2 批量插入 file_page 记录**
```python
page_records = []
for idx, (img_bytes, width, height) in enumerate(page_images, start=1):
    page_records.append({
        "id": get_uuid(),                   # UUID
        "file_id": file_id,                 # 关联file表
        "page_number": idx,                 # 页码（从1开始）
        "location": page_location,          # MinIO路径
        "size": len(img_bytes),             # 图片大小
        "width": width,                     # 图片宽度
        "height": height,                   # 图片高度
        "format": "JPEG",                   # 图片格式
        "create_time": current_time,
        "create_date": current_date,
        "update_time": current_time,
        "update_date": current_date,
    })

# 批量插入
columns = ", ".join(page_records[0].keys())
placeholders = ", ".join(["%s"] * len(page_records[0]))
query = f"INSERT INTO file_page ({columns}) VALUES ({placeholders})"

for page_record in page_records:
    cursor.execute(query, list(page_record.values()))

conn.commit()
```

**事务处理**：
- 所有数据库操作在同一事务中
- 任何失败都会回滚
- 回滚时需要清理 MinIO 中已上传的文件

---

#### 步骤 8：清理临时文件
```python
finally:
    # 删除临时文件
    if os.path.exists(filepath):
        os.remove(filepath)
```

**清理内容**：
- 删除 `/tmp/uploads/` 中的临时文件
- 无论成功或失败都要清理

---

#### 步骤 9：返回结果
```python
results.append({
    "id": file_id,
    "name": filename,
    "size": file_record["size"],
    "type": filetype,
    "pages": len(page_images),      # 页数
    "status": "success"
})

return {
    "code": 0,
    "data": results,
    "message": f"成功上传 {success_count}/{total_count} 个文件"
}
```

**返回格式**：
```json
{
  "code": 0,
  "message": "成功上传 1/1 个文件",
  "data": [
    {
      "id": "file_xyz789",
      "name": "report.docx",
      "size": 1024000,
      "type": "word",
      "pages": 3,
      "status": "success"
    }
  ]
}
```



---

## 🔧 技术实现细节

### 1. 数据库模型定义

**文件位置**：`api/db/db_models.py`

**添加位置**：在 `File2Document` 类之后

```python
class FilePage(DataBaseModel):
    """文件页面表 - 存储每页图片的元数据"""
    id = CharField(max_length=32, primary_key=True)
    file_id = CharField(max_length=32, null=False, help_text="关联file表", index=True)
    page_number = IntegerField(null=False, help_text="页码（从1开始）", index=True)
    location = CharField(max_length=255, null=False, help_text="MinIO存储路径")
    size = IntegerField(default=0, help_text="图片大小（字节）")
    width = IntegerField(default=0, help_text="图片宽度（像素）")
    height = IntegerField(default=0, help_text="图片高度（像素）")
    format = CharField(max_length=16, default="JPEG", help_text="图片格式")
    
    class Meta:
        db_table = "file_page"
```

**重要说明**：
- ✅ 只需在 `api/db/db_models.py` 中定义一次
- ✅ 继承 `DataBaseModel` 会自动包含时间戳字段
- ✅ 下次启动 `ragflow_server.py` 时自动创建表
- ❌ 不需要在 `management/server/services/files/models/__init__.py` 中重复定义

---

### 2. 转换器模块

#### 目录结构
```
management/server/services/files/
└── converters/
    ├── __init__.py
    ├── pdf_converter.py      # 文件转PDF
    └── image_converter.py    # PDF转图片
```

#### pdf_converter.py
**来源**：移动 `test/convert_file_2_pdf.py` 到此处

**主要函数**：
- `convert_office_to_pdf()`: Office 文档转 PDF
- `convert_html_to_pdf()`: HTML 转 PDF
- `convert_markdown_to_pdf()`: Markdown 转 PDF
- `convert_file()`: 统一入口，根据扩展名调用对应函数

**依赖**：Gotenberg 服务（http://localhost:3000）

#### image_converter.py
**新建文件**

**主要函数**：
```python
def pdf_to_images(
    pdf_bytes: bytes,
    dpi: int = 150,
    image_format: str = "JPEG",
    quality: int = 85
) -> List[Tuple[bytes, int, int]]:
    """将 PDF 转换为图片列表"""
    pass
```

**依赖**：PyMuPDF (fitz)

---

### 3. 核心上传逻辑

**文件位置**：`management/server/services/files/service.py`

**函数名**：`upload_files_to_server()`

**主要改动**：
1. 添加 PDF 转换逻辑
2. 添加图片生成逻辑
3. 修改 MinIO 上传逻辑（分层存储）
4. 添加 file_page 记录插入

**伪代码**：
```python
def upload_files_to_server(files, parent_id=None, user_id=None):
    for file in files:
        # 1. 保存到临时目录
        file.save(filepath)
        
        # 2. 转换为 PDF
        pdf_bytes = convert_file(filepath)
        
        # 3. PDF 转图片
        page_images = pdf_to_images(pdf_bytes)
        
        # 4. 上传到 MinIO
        upload_source_file(file_id, filepath)
        upload_page_images(file_id, page_images)
        
        # 5. 保存数据库
        with transaction:
            insert_file_record()
            insert_file_page_records()
        
        # 6. 清理临时文件
        os.remove(filepath)
```

