# 文件页面拆分功能实现文档（续）

## 📸 图片文件特殊处理

### 支持的图片格式

```python
IMAGE_EXTES = {"jpg", "jpeg", "png", "bmp"}
```

### 处理逻辑

对于上传的图片文件（JPG、JPEG、PNG、BMP），系统采用特殊处理流程：

1. **跳过 PDF 转换**
   - 图片文件不需要转换为 PDF
   - 直接读取图片的宽度、高度、格式等信息

2. **双重存储**
   - `source/` 文件夹：存储原始图片文件
   - `pages/` 文件夹：存储同一份图片（作为第 1 页）

3. **MinIO 存储结构**
   ```
   {parent_id}/                    # Bucket
   └── {file_id}/                  # 文件目录
       ├── source/                 # 原始图片
       │   └── image.jpg
       └── pages/                  # 页面图片（同一份）
           └── image.jpg           # 使用原始文件名
   ```

4. **数据库记录**
   - `file` 表：记录原始图片信息
   - `file_page` 表：记录单页信息（page_number = 1）

### 实现代码

```python
# 判断是否为图片文件
file_ext = ext.lower().lstrip('.')
is_image = file_ext in IMAGE_EXTES

if is_image:
    # 图片文件：直接读取，不转换为 PDF
    from PIL import Image
    
    with Image.open(filepath) as img:
        width, height = img.size
        img_format = img.format or "JPEG"
        
        with open(filepath, 'rb') as f:
            img_bytes = f.read()
    
    # 构造页面图片列表（只有一页）
    page_images = [(img_bytes, width, height)]
else:
    # 非图片文件：转换为 PDF，再转为图片
    pdf_bytes = convert_file(filepath)
    page_images = pdf_to_images(pdf_bytes, dpi=150)

# 上传页面图片
for idx, (img_bytes, width, height) in enumerate(page_images, start=1):
    # 图片文件使用原始文件名，其他文件使用页码命名
    if is_image:
        page_filename = filename
    else:
        page_filename = f"{idx:04d}.jpg"
    
    page_location = f"{file_id}/pages/{page_filename}"
    # ... 上传到 MinIO
```

### 优势

1. **保持原始质量**：图片不经过 PDF 转换，保持原始质量
2. **统一接口**：图片和文档使用相同的 API 接口
3. **一致的存储结构**：所有文件类型都有 source/ 和 pages/ 目录
4. **简化处理**：减少不必要的格式转换

---

## 🌐 MinIO 公共访问权限

### 权限设置

系统在创建或使用存储桶时，会自动设置公共读取权限，允许通过 URL 直接访问文件。

### 权限策略

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"AWS": "*"},
      "Action": ["s3:GetObject"],
      "Resource": ["arn:aws:s3:::{bucket_name}/*"]
    }
  ]
}
```

### 实现代码

```python
# 确保 bucket 存在
bucket_created = False
if not minio_client.bucket_exists(parent_id):
    minio_client.make_bucket(parent_id)
    bucket_created = True

# 设置桶的公共访问权限
import json
policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"AWS": "*"},
            "Action": ["s3:GetObject"],
            "Resource": [f"arn:aws:s3:::{parent_id}/*"]
        }
    ]
}
minio_client.set_bucket_policy(parent_id, json.dumps(policy))
```

### 公共 URL 格式

上传成功后，文件可以通过以下 URL 格式直接访问：

```
# 原始文件
http://{minio_endpoint}/{bucket}/{file_id}/source/{filename}

# 页面图片
http://{minio_endpoint}/{bucket}/{file_id}/pages/{page_filename}
```

**示例：**
```
http://localhost:9000/kb-001/file-123/source/document.pdf
http://localhost:9000/kb-001/file-123/pages/0001.jpg
http://localhost:9000/kb-001/file-456/pages/photo.jpg
```

### 使用场景

1. **前端直接展示**：前端可以直接使用 MinIO URL 显示图片
2. **外部分享**：可以将 URL 分享给其他用户访问
3. **CDN 加速**：可以在 MinIO 前面配置 CDN 加速访问
4. **减少服务器负载**：不需要通过后端 API 转发文件

### 安全考虑

1. **只读权限**：只允许 GetObject 操作，不允许上传、删除
2. **桶级隔离**：每个桶独立设置权限
3. **可选配置**：如需私有访问，可以不设置公共权限，通过 API 下载
4. **访问控制**：可以在前端或 CDN 层面添加额外的访问控制

---

## 🛡️ 错误处理与回滚

### 错误场景

1. **文件格式不支持**
   - 检查：文件扩展名验证
   - 处理：返回错误信息，不进行后续处理

2. **Gotenberg 服务不可用**
   - 检查：HTTP 请求超时或失败
   - 处理：捕获异常，返回转换失败信息

3. **PDF 转图片失败**
   - 检查：PyMuPDF 处理异常
   - 处理：捕获异常，清理已上传文件

4. **MinIO 上传失败**
   - 检查：网络错误或权限问题
   - 处理：回滚数据库事务，清理部分上传文件

5. **数据库插入失败**
   - 检查：SQL 执行异常
   - 处理：回滚事务，清理 MinIO 文件

### 回滚机制

```python
def upload_files_to_server(files, parent_id=None, user_id=None):
    for file in files:
        try:
            # 1-5 步骤...
            
            # 6. 保存数据库（事务）
            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                
                # 插入 file 记录
                cursor.execute(insert_file_query, file_record)
                
                # 插入 file_page 记录
                for page_record in page_records:
                    cursor.execute(insert_page_query, page_record)
                
                conn.commit()
                
            except Exception as e:
                # 数据库失败：回滚事务
                conn.rollback()
                
                # 清理 MinIO 文件
                cleanup_minio_files(minio_client, parent_id, file_id)
                
                raise
            finally:
                cursor.close()
                conn.close()
                
        except Exception as e:
            # 记录失败
            results.append({
                "name": filename,
                "error": str(e),
                "status": "failed"
            })
        finally:
            # 清理临时文件
            if os.path.exists(filepath):
                os.remove(filepath)
```

### 清理函数

```python
def cleanup_minio_files(minio_client, bucket, file_id):
    """清理 MinIO 中的文件（上传失败时回滚）"""
    try:
        # 删除 source 目录
        objects = minio_client.list_objects(
            bucket, 
            prefix=f"{file_id}/source/", 
            recursive=True
        )
        for obj in objects:
            minio_client.remove_object(bucket, obj.object_name)
        
        # 删除 pages 目录
        objects = minio_client.list_objects(
            bucket, 
            prefix=f"{file_id}/pages/", 
            recursive=True
        )
        for obj in objects:
            minio_client.remove_object(bucket, obj.object_name)
            
    except Exception as e:
        logging.error(f"清理 MinIO 文件失败: {e}")
```



---

## 📦 依赖与配置

### Python 依赖

**文件位置**：`management/server/requirements.txt`

**新增依赖**：
```
PyMuPDF>=1.23.0    # PDF 处理和图片生成
```

**现有依赖**（需要确认）：
```
Flask>=2.0.0
flask-cors
python-dotenv
mysql-connector-python  # 或 psycopg2-binary
minio
redis
requests
```

### 环境配置

**文件位置**：`docker/.env` 或 `management/.env`

**新增配置**：
```bash
# 图片转换配置
IMAGE_DPI=150                    # 图片分辨率（72-300）
IMAGE_FORMAT=JPEG                # 图片格式（JPEG/PNG）
IMAGE_QUALITY=85                 # JPEG 质量（1-100）
MAX_IMAGE_WIDTH=2000             # 最大宽度限制（像素）
ENABLE_PAGE_SPLIT=true           # 是否启用页面拆分

# Gotenberg 配置
GOTENBERG_URL=http://localhost:3000
GOTENBERG_TIMEOUT=60
```

### 外部服务

#### Gotenberg
**用途**：文档转 PDF

**部署方式**：Docker
```bash
docker run -d \
  --name gotenberg \
  -p 3000:3000 \
  gotenberg/gotenberg:7
```

**健康检查**：
```bash
curl http://localhost:3000/health
```

**API 文档**：https://gotenberg.dev/docs/routes

---

## 🧪 测试方案

### 单元测试

#### 1. PDF 转换测试
```python
def test_convert_office_to_pdf():
    """测试 Office 文档转 PDF"""
    file_path = "test_files/sample.docx"
    pdf_bytes = convert_office_to_pdf(file_path)
    
    assert pdf_bytes is not None
    assert pdf_bytes.startswith(b'%PDF')  # PDF 文件头
    assert len(pdf_bytes) > 0
```

#### 2. PDF 转图片测试
```python
def test_pdf_to_images():
    """测试 PDF 转图片"""
    with open("test_files/sample.pdf", "rb") as f:
        pdf_bytes = f.read()
    
    images = pdf_to_images(pdf_bytes, dpi=150)
    
    assert len(images) > 0
    for img_bytes, width, height in images:
        assert len(img_bytes) > 0
        assert width > 0
        assert height > 0
```

#### 3. MinIO 上传测试
```python
def test_minio_upload():
    """测试 MinIO 上传"""
    minio_client = get_minio_client()
    bucket = "test-bucket"
    file_id = "test-file-123"
    
    # 上传测试文件
    with open("test_files/sample.jpg", "rb") as f:
        minio_client.put_object(
            bucket_name=bucket,
            object_name=f"{file_id}/pages/0001.jpg",
            data=f,
            length=os.path.getsize("test_files/sample.jpg")
        )
    
    # 验证文件存在
    objects = list(minio_client.list_objects(bucket, prefix=f"{file_id}/"))
    assert len(objects) > 0
```

### 集成测试

#### 完整上传流程测试
```python
def test_upload_file_complete():
    """测试完整上传流程"""
    # 准备测试文件
    with open("test_files/sample.docx", "rb") as f:
        files = [("files", ("sample.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))]
        
        # 发送上传请求
        response = client.post("/api/v1/files/upload", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert len(data["data"]) == 1
        
        file_info = data["data"][0]
        assert file_info["status"] == "success"
        assert file_info["pages"] > 0
        
        # 验证数据库记录
        file_id = file_info["id"]
        file_record = get_file_info(file_id)
        assert file_record is not None
        
        page_records = get_file_pages_list(file_id)
        assert len(page_records) == file_info["pages"]
        
        # 验证 MinIO 文件
        minio_client = get_minio_client()
        # 检查原始文件
        # 检查页面图片
```



### 性能测试

#### 1. 大文件处理测试
```python
def test_large_file_upload():
    """测试大文件上传（100+ 页）"""
    import time
    
    start_time = time.time()
    result = upload_files_to_server([large_file])
    end_time = time.time()
    
    assert result["code"] == 0
    print(f"处理时间: {end_time - start_time:.2f} 秒")
    print(f"页数: {result['data'][0]['pages']}")
```

#### 2. 并发上传测试
```python
def test_concurrent_upload():
    """测试并发上传"""
    from concurrent.futures import ThreadPoolExecutor
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(upload_file, f"file_{i}.docx") for i in range(10)]
        results = [f.result() for f in futures]
    
    success_count = sum(1 for r in results if r["status"] == "success")
    assert success_count == 10
```

---

## 🚀 部署步骤

### 步骤 1：更新数据库模型

**文件**：`api/db/db_models.py`

在 `File2Document` 类之后添加：
```python
class FilePage(DataBaseModel):
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

### 步骤 2：创建转换器模块

**创建目录**：
```bash
mkdir -p management/server/services/files/converters
```

**移动文件**：
```bash
cp test/convert_file_2_pdf.py management/server/services/files/converters/pdf_converter.py
```

**创建新文件**：`management/server/services/files/converters/image_converter.py`

**创建 __init__.py**：
```python
# management/server/services/files/converters/__init__.py
from .pdf_converter import convert_file, convert_office_to_pdf, convert_html_to_pdf, convert_markdown_to_pdf
from .image_converter import pdf_to_images

__all__ = [
    'convert_file',
    'convert_office_to_pdf',
    'convert_html_to_pdf',
    'convert_markdown_to_pdf',
    'pdf_to_images',
]
```

### 步骤 3：修改上传逻辑

**文件**：`management/server/services/files/service.py`

在 `upload_files_to_server()` 函数中添加转换和拆分逻辑。

### 步骤 4：安装依赖

```bash
cd management/server
pip install PyMuPDF>=1.23.0
```

或更新 `requirements.txt` 后：
```bash
pip install -r requirements.txt
```

### 步骤 5：启动 Gotenberg 服务

```bash
docker run -d \
  --name gotenberg \
  --restart unless-stopped \
  -p 3000:3000 \
  gotenberg/gotenberg:7
```

### 步骤 6：重启服务

**重启前台服务**（创建新表）：
```bash
cd api
python ragflow_server.py
```

**重启后台服务**：
```bash
cd management/server
python app.py
```

### 步骤 7：验证部署

**检查表是否创建**：
```sql
SHOW TABLES LIKE 'file_page';
DESC file_page;
```

**测试上传**：
```bash
curl -X POST http://localhost:5000/api/v1/files/upload \
  -F "files=@test.docx" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 📊 性能优化建议

### 1. 图片压缩

**当前配置**：
- DPI: 150
- 格式: JPEG
- 质量: 85

**优化方案**：
```python
# 根据页面大小动态调整 DPI
def calculate_optimal_dpi(page_width, page_height):
    """计算最优 DPI"""
    max_dimension = max(page_width, page_height)
    
    if max_dimension > 2000:
        return 100  # 大页面用低 DPI
    elif max_dimension > 1000:
        return 150  # 中等页面用标准 DPI
    else:
        return 200  # 小页面用高 DPI
```

### 2. 异步处理

**问题**：大文件上传阻塞请求

**解决方案**：使用任务队列
```python
from celery import Celery

@celery.task
def process_file_async(file_id, filepath):
    """异步处理文件"""
    # 1. 转换为 PDF
    # 2. 生成图片
    # 3. 上传 MinIO
    # 4. 更新数据库
    pass

# 上传接口立即返回
@files_bp.route("/upload", methods=["POST"])
def upload_file():
    # 保存文件
    file_id = save_temp_file(file)
    
    # 提交异步任务
    task = process_file_async.delay(file_id, filepath)
    
    return jsonify({
        "code": 0,
        "data": {"task_id": task.id, "file_id": file_id},
        "message": "文件上传成功，正在处理中"
    })
```

### 3. 缓存优化

**缓存策略**：
- 使用 Redis 缓存文件元数据
- 使用 CDN 缓存页面图片
- 设置合理的过期时间

```python
import redis

def get_file_pages_cached(file_id):
    """获取文件页面（带缓存）"""
    cache_key = f"file_pages:{file_id}"
    
    # 尝试从缓存获取
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # 从数据库查询
    pages = get_file_pages_list(file_id)
    
    # 写入缓存（1小时过期）
    redis_client.setex(cache_key, 3600, json.dumps(pages))
    
    return pages
```

### 4. 批量处理

**优化数据库插入**：
```python
# 使用 executemany 批量插入
cursor.executemany(
    "INSERT INTO file_page (...) VALUES (...)",
    [tuple(record.values()) for record in page_records]
)
```

---

## 🔍 监控与日志

### 日志记录

**关键节点日志**：
```python
import logging

logger = logging.getLogger(__name__)

def upload_files_to_server(files, parent_id=None, user_id=None):
    logger.info(f"开始上传文件，数量: {len(files)}, parent_id: {parent_id}")
    
    for file in files:
        logger.info(f"处理文件: {file.filename}")
        
        try:
            # 转换
            logger.debug(f"转换为 PDF: {file.filename}")
            pdf_bytes = convert_file(filepath)
            logger.info(f"PDF 大小: {len(pdf_bytes)} 字节")
            
            # 生成图片
            logger.debug(f"生成页面图片: {file.filename}")
            page_images = pdf_to_images(pdf_bytes)
            logger.info(f"生成 {len(page_images)} 页图片")
            
            # 上传
            logger.debug(f"上传到 MinIO: {file.filename}")
            # ...
            
            logger.info(f"文件处理成功: {file.filename}")
            
        except Exception as e:
            logger.error(f"文件处理失败: {file.filename}, 错误: {str(e)}", exc_info=True)
```

### 性能监控

**关键指标**：
```python
import time

def upload_files_to_server(files, parent_id=None, user_id=None):
    metrics = {
        "total_time": 0,
        "convert_time": 0,
        "image_gen_time": 0,
        "upload_time": 0,
        "db_time": 0,
    }
    
    start_time = time.time()
    
    # 转换
    convert_start = time.time()
    pdf_bytes = convert_file(filepath)
    metrics["convert_time"] = time.time() - convert_start
    
    # 生成图片
    image_start = time.time()
    page_images = pdf_to_images(pdf_bytes)
    metrics["image_gen_time"] = time.time() - image_start
    
    # ... 其他步骤
    
    metrics["total_time"] = time.time() - start_time
    
    logger.info(f"性能指标: {metrics}")
```



---

## 🔐 安全考虑

### 1. 文件类型验证

**白名单验证**：
```python
ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "ppt", "pptx", 
    "xls", "xlsx", "txt", "md", "html", "csv"
}

def allowed_file(filename):
    """检查文件扩展名"""
    if not filename or "." not in filename:
        return False
    
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS
```

**MIME 类型验证**：
```python
import magic

def validate_file_type(filepath):
    """验证文件真实类型"""
    mime = magic.from_file(filepath, mime=True)
    
    allowed_mimes = {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        # ... 其他类型
    }
    
    return mime in allowed_mimes
```

### 2. 文件大小限制

```python
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

def check_file_size(file):
    """检查文件大小"""
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    
    if size > MAX_FILE_SIZE:
        raise ValueError(f"文件过大: {size} 字节，最大允许 {MAX_FILE_SIZE} 字节")
```

### 3. 路径遍历防护

```python
import os

def safe_filename(filename):
    """安全的文件名处理"""
    # 移除路径分隔符
    filename = filename.replace("/", "_").replace("\\", "_")
    
    # 移除特殊字符
    filename = re.sub(r'[^\w\s.-]', '_', filename)
    
    # 限制长度
    name, ext = os.path.splitext(filename)
    if len(name) > 200:
        name = name[:200]
    
    return name + ext
```

### 4. 权限控制

```python
def check_upload_permission(user_id, parent_id):
    """检查上传权限"""
    # 检查用户是否有权限上传到该文件夹
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT * FROM file 
        WHERE id = %s AND (created_by = %s OR tenant_id = %s)
    """, (parent_id, user_id, user_id))
    
    folder = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not folder:
        raise PermissionError("无权限上传到该文件夹")
```

---

## 📝 API 文档

### 上传文件 API

**端点**：`POST /api/v1/files/upload`

**请求头**：
```
Content-Type: multipart/form-data
Authorization: Bearer {token}
```

**请求体**：
```
files: File[] (必需)
parent_id: string (可选，默认使用第一个文件夹)
```

**响应**：
```json
{
  "code": 0,
  "message": "成功上传 2/2 个文件",
  "data": [
    {
      "id": "file_abc123",
      "name": "report.docx",
      "size": 1024000,
      "type": "word",
      "pages": 5,
      "status": "success"
    },
    {
      "id": "file_def456",
      "name": "presentation.pptx",
      "size": 2048000,
      "type": "ppt",
      "pages": 10,
      "status": "success"
    }
  ]
}
```

**错误响应**：
```json
{
  "code": 400,
  "message": "未选择文件",
  "data": null
}
```

### 获取文件页面列表 API（新增）

**端点**：`GET /api/v1/files/{file_id}/pages`

**请求头**：
```
Authorization: Bearer {token}
```

**响应**：
```json
{
  "code": 0,
  "message": "获取成功",
  "data": [
    {
      "id": "page_001",
      "page_number": 1,
      "location": "file_abc123/pages/0001.jpg",
      "size": 102400,
      "width": 1654,
      "height": 2339,
      "format": "JPEG"
    },
    {
      "id": "page_002",
      "page_number": 2,
      "location": "file_abc123/pages/0002.jpg",
      "size": 98304,
      "width": 1654,
      "height": 2339,
      "format": "JPEG"
    }
  ]
}
```

### 下载页面图片 API（新增）

**端点**：`GET /api/v1/files/{file_id}/pages/{page_number}`

**请求头**：
```
Authorization: Bearer {token}
```

**响应**：
- Content-Type: image/jpeg
- 二进制图片数据

---

## 🎯 实施计划

### 阶段 1：准备工作（1天）
- [x] 编写技术文档
- [ ] 评审技术方案
- [ ] 准备测试数据
- [ ] 搭建测试环境

### 阶段 2：数据库改造（0.5天）
- [ ] 在 `api/db/db_models.py` 添加 `FilePage` 模型
- [ ] 重启前台服务，自动创建表
- [ ] 验证表结构

### 阶段 3：转换器开发（1天）
- [ ] 创建 converters 目录
- [ ] 移动 pdf_converter.py
- [ ] 开发 image_converter.py
- [ ] 编写单元测试

### 阶段 4：核心逻辑改造（2天）
- [ ] 修改 upload_files_to_server() 函数
- [ ] 添加 PDF 转换逻辑
- [ ] 添加图片生成逻辑
- [ ] 修改 MinIO 上传逻辑
- [ ] 添加 file_page 记录插入
- [ ] 添加错误处理和回滚

### 阶段 5：API 扩展（1天）
- [ ] 实现获取页面列表 API
- [ ] 实现下载页面图片 API
- [ ] 编写 API 文档

### 阶段 6：测试（2天）
- [ ] 单元测试
- [ ] 集成测试
- [ ] 性能测试
- [ ] 安全测试

### 阶段 7：部署上线（1天）
- [ ] 部署到测试环境
- [ ] 用户验收测试
- [ ] 部署到生产环境
- [ ] 监控运行状态

**总计**：约 8.5 个工作日

---

## 📚 参考资料

### 技术文档
- [Gotenberg 官方文档](https://gotenberg.dev/docs/routes)
- [PyMuPDF 文档](https://pymupdf.readthedocs.io/)
- [MinIO Python SDK](https://min.io/docs/minio/linux/developers/python/minio-py.html)
- [Peewee ORM 文档](http://docs.peewee-orm.com/)

### 相关代码
- `test/convert_file_2_pdf.py` - PDF 转换示例
- `test/main.py` - 批量转换示例
- `management/server/services/files/service.py` - 现有上传逻辑
- `api/db/db_models.py` - 数据库模型定义

### 项目文档
- [Ragflow-Plus 项目文档](https://xdxsb.top/ragflow-plus)
- [Ragflow 原项目](https://github.com/infiniflow/ragflow)

---

## ❓ 常见问题

### Q1: 为什么要转换为 PDF 再转图片，而不是直接转图片？
**A**: 
1. PDF 是标准格式，便于统一处理
2. PDF 保留了文档的版面信息
3. 后续可以进行 OCR、文本提取等操作
4. 便于存档和分享

### Q2: 图片 DPI 如何选择？
**A**:
- 72 DPI: 屏幕预览（文件小，质量低）
- 150 DPI: 标准质量（推荐）⭐
- 300 DPI: 打印质量（文件大）

### Q3: 为什么使用 JPEG 而不是 PNG？
**A**:
- JPEG 有损压缩，文件更小
- 对于文档图片，JPEG 质量足够
- PNG 无损压缩，文件大 3-5 倍
- 如需透明背景，可使用 PNG

### Q4: 如何处理超大文件（1000+ 页）？
**A**:
1. 使用异步任务队列（Celery）
2. 分批处理页面
3. 限制单次上传文件大小
4. 提供进度反馈

### Q5: MinIO 存储成本如何控制？
**A**:
1. 调整图片 DPI 和质量
2. 定期清理过期文件
3. 使用对象生命周期策略
4. 考虑使用 CDN 缓存

### Q6: 数据库表为什么只在 api/db/db_models.py 定义？
**A**:
- 前台和后台共享同一数据库
- api/db/db_models.py 是唯一真实来源
- management 通过 database.py 连接同一数据库
- 避免模型定义不一致

---

## ✅ 检查清单

### 开发前检查
- [ ] 已阅读完整技术文档
- [ ] 已理解系统架构
- [ ] 已准备测试环境
- [ ] Gotenberg 服务已启动
- [ ] MinIO 服务正常
- [ ] 数据库连接正常

### 开发中检查
- [ ] 代码符合项目规范
- [ ] 添加了必要的注释
- [ ] 编写了单元测试
- [ ] 处理了异常情况
- [ ] 添加了日志记录

### 部署前检查
- [ ] 所有测试通过
- [ ] 性能测试达标
- [ ] 安全检查通过
- [ ] 文档已更新
- [ ] 回滚方案已准备

---

## 📞 联系方式

如有问题，请联系：
- 技术负责人：[姓名]
- 邮箱：[email]
- 项目地址：https://github.com/zstar1003/ragflow-plus

---

**文档版本**：v1.0  
**最后更新**：2025-01-13  
**作者**：Kiro AI Assistant

