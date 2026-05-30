# 图片文件上传功能更新

## 📋 更新概述

为支持图片文件的直接上传，系统新增了图片文件的特殊处理逻辑。

## 🎯 核心变更

### 1. 支持的图片格式

```python
IMAGE_EXTES = {"jpg", "jpeg", "png", "bmp"}
```

### 2. 处理流程差异

| 文件类型 | 处理流程 |
|---------|---------|
| **图片文件** | 直接读取 → 上传到 source/ 和 pages/ |
| **文档文件** | 转 PDF → 拆分为图片 → 上传到 source/ 和 pages/ |

### 3. MinIO 存储结构

#### 图片文件
```
{parent_id}/
└── {file_id}/
    ├── source/
    │   └── photo.jpg          # 原始图片
    └── pages/
        └── photo.jpg          # 同一份图片（作为第 1 页）
```

#### 文档文件
```
{parent_id}/
└── {file_id}/
    ├── source/
    │   └── document.pdf       # 转换后的 PDF
    └── pages/
        ├── 0001.jpg          # 第 1 页
        ├── 0002.jpg          # 第 2 页
        └── ...
```

## 📝 修改的文件

### 1. `management/server/services/files/service.py`

**新增常量：**
```python
IMAGE_EXTES = {"jpg", "jpeg", "png", "bmp"}
```

**修改函数：** `upload_files_to_server()`

- 添加图片文件检测逻辑
- 图片文件跳过 PDF 转换
- 使用 Pillow 读取图片信息（宽度、高度、格式）
- 页面文件命名：图片使用原始文件名，文档使用页码

### 2. `management/server/requirements.txt`

**新增依赖：**
```
Pillow>=10.0.0
```

### 3. `management/server/test_image_upload.py`

**新增测试脚本：**
- 创建测试图片
- 测试上传 JPG/PNG 图片
- 验证页面列表 API

### 4. `docs/file-page-split-implementation-part2.md`

**新增章节：** 📸 图片文件特殊处理
- 支持的格式说明
- 处理逻辑详解
- 实现代码示例
- 优势分析

## 🚀 部署步骤

### 1. 安装新依赖

```bash
cd management/server
pip install Pillow>=10.0.0
```

### 2. 重启服务

```bash
# 重启 management 服务
python ragflow_server.py
```

### 3. 测试功能

```bash
# 运行图片上传测试
python test_image_upload.py
```

## ✅ 测试验证

### 测试场景

1. **上传 JPG 图片**
   - 验证文件上传成功
   - 验证 MinIO 存储结构
   - 验证数据库记录

2. **上传 PNG 图片**
   - 验证不同格式支持
   - 验证图片信息读取

3. **获取页面列表**
   - 验证返回单页信息
   - 验证页面位置正确

### 预期结果

```json
{
  "code": 0,
  "data": [
    {
      "id": "xxx-xxx-xxx",
      "name": "photo.jpg",
      "size": 123456,
      "type": "visual",
      "pages": 1,
      "status": "success"
    }
  ],
  "message": "成功上传 1/1 个文件"
}
```

## 🔍 关键代码逻辑

```python
# 判断文件类型
file_ext = ext.lower().lstrip('.')
is_image = file_ext in IMAGE_EXTES

if is_image:
    # 图片：直接读取
    from PIL import Image
    with Image.open(filepath) as img:
        width, height = img.size
        with open(filepath, 'rb') as f:
            img_bytes = f.read()
    page_images = [(img_bytes, width, height)]
else:
    # 文档：转 PDF → 转图片
    pdf_bytes = convert_file(filepath)
    page_images = pdf_to_images(pdf_bytes, dpi=150)

# 上传页面图片
for idx, (img_bytes, width, height) in enumerate(page_images, start=1):
    if is_image:
        page_filename = filename  # 使用原始文件名
    else:
        page_filename = f"{idx:04d}.jpg"  # 使用页码
    
    page_location = f"{file_id}/pages/{page_filename}"
    # ... 上传到 MinIO
```

## 📊 影响范围

- ✅ 向后兼容：不影响现有文档上传功能
- ✅ API 不变：使用相同的上传和查询接口
- ✅ 存储一致：保持统一的 MinIO 存储结构
- ✅ 数据库兼容：使用相同的表结构

## 🎉 优势

1. **统一接口**：图片和文档使用相同的 API
2. **保持质量**：图片不经过 PDF 转换，保持原始质量
3. **简化流程**：减少不必要的格式转换
4. **一致体验**：所有文件类型都有页面预览功能

---

## 🌐 MinIO 公共访问权限

### 新增功能

系统现在会自动为存储桶设置公共读取权限，允许通过 URL 直接访问文件。

### 权限策略

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"AWS": "*"},
      "Action": ["s3:GetObject"],
      "Resource": ["arn:aws:s3:::{bucket}/*"]
    }
  ]
}
```

### 公共 URL 访问

上传成功后，可以通过以下格式直接访问文件：

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

- ✅ 前端直接展示图片（无需通过后端 API）
- ✅ 外部分享文件链接
- ✅ CDN 加速访问
- ✅ 减少服务器负载

### 安全说明

- 只允许读取（GetObject），不允许上传、删除
- 每个桶独立设置权限
- 如需私有访问，可通过 API 下载接口
