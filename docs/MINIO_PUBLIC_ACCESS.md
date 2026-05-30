# MinIO 公共访问权限配置

## 📋 概述

系统在上传文件时，会自动为 MinIO 存储桶设置公共读取权限，允许通过 URL 直接访问文件，无需通过后端 API 转发。

## 🔧 实现方式

### 自动设置权限

在 `upload_files_to_server()` 函数中，创建或使用存储桶时自动设置权限：

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

### 权限策略说明

| 字段 | 值 | 说明 |
|-----|-----|-----|
| **Version** | 2012-10-17 | AWS S3 策略版本 |
| **Effect** | Allow | 允许访问 |
| **Principal** | {"AWS": "*"} | 所有用户 |
| **Action** | ["s3:GetObject"] | 只允许读取对象 |
| **Resource** | arn:aws:s3:::{bucket}/* | 桶内所有对象 |

## 🌐 公共 URL 格式

### URL 结构

```
http://{minio_endpoint}/{bucket}/{object_path}
```

### 实际示例

#### 原始文件
```
http://localhost:9000/kb-001/file-123/source/document.pdf
http://localhost:9000/kb-001/file-456/source/photo.jpg
```

#### 页面图片
```
http://localhost:9000/kb-001/file-123/pages/0001.jpg
http://localhost:9000/kb-001/file-123/pages/0002.jpg
http://localhost:9000/kb-001/file-456/pages/photo.jpg
```

### 参数说明

- **minio_endpoint**: MinIO 服务地址（如 `localhost:9000`）
- **bucket**: 存储桶名称（即 `parent_id`）
- **object_path**: 对象路径（如 `{file_id}/source/{filename}`）

## 💡 使用场景

### 1. 前端直接展示

```html
<!-- 直接使用 MinIO URL -->
<img src="http://localhost:9000/kb-001/file-123/pages/0001.jpg" alt="Page 1">
```

```javascript
// React 示例
const imageUrl = `http://localhost:9000/${bucket}/${fileId}/pages/0001.jpg`;
<img src={imageUrl} alt="Page 1" />
```

### 2. 文件分享

```javascript
// 生成分享链接
const shareUrl = `http://localhost:9000/${bucket}/${fileId}/source/${filename}`;
navigator.clipboard.writeText(shareUrl);
```

### 3. CDN 加速

```nginx
# Nginx 反向代理示例
location /files/ {
    proxy_pass http://minio:9000/;
    proxy_cache my_cache;
    proxy_cache_valid 200 1h;
}
```

### 4. 批量下载

```javascript
// 批量下载页面图片
const pages = [1, 2, 3, 4, 5];
const urls = pages.map(page => 
    `http://localhost:9000/${bucket}/${fileId}/pages/${String(page).padStart(4, '0')}.jpg`
);

// 使用 Promise.all 并发下载
Promise.all(urls.map(url => fetch(url)))
    .then(responses => Promise.all(responses.map(r => r.blob())))
    .then(blobs => {
        // 处理下载的文件
    });
```

## 🔒 安全考虑

### 权限范围

✅ **允许的操作：**
- `s3:GetObject` - 读取对象

❌ **不允许的操作：**
- `s3:PutObject` - 上传对象
- `s3:DeleteObject` - 删除对象
- `s3:ListBucket` - 列出桶内容

### 访问控制建议

1. **桶级隔离**
   - 不同项目使用不同的桶
   - 每个桶独立设置权限

2. **对象路径设计**
   - 使用 UUID 作为文件 ID，避免路径猜测
   - 不在路径中包含敏感信息

3. **额外安全层**
   - 在前端添加访问控制（如登录验证）
   - 使用 CDN 的访问控制功能
   - 配置防盗链（Referer 检查）

4. **私有文件处理**
   - 对于敏感文件，不设置公共权限
   - 通过后端 API 提供临时访问 URL
   - 使用 MinIO 的预签名 URL 功能

## 🛠️ 配置选项

### 环境变量

```bash
# .env 文件
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false  # true 表示使用 HTTPS
```

### 动态配置

如果需要根据环境动态决定是否设置公共权限：

```python
# 添加环境变量控制
ENABLE_PUBLIC_ACCESS = os.getenv("MINIO_PUBLIC_ACCESS", "true").lower() == "true"

if ENABLE_PUBLIC_ACCESS:
    # 设置公共访问权限
    minio_client.set_bucket_policy(parent_id, json.dumps(policy))
```

## 📊 性能优势

### 直接访问 vs API 转发

| 方式 | 延迟 | 服务器负载 | 带宽消耗 |
|-----|------|-----------|---------|
| **直接访问** | 低 | 无 | MinIO 承担 |
| **API 转发** | 高 | 高 | 后端承担 |

### 优势

1. **减少延迟**：客户端直接从 MinIO 获取文件
2. **降低负载**：后端服务器不需要转发文件
3. **节省带宽**：文件流量不经过后端
4. **易于扩展**：可以在 MinIO 前配置 CDN

## 🧪 测试验证

### 手动测试

```bash
# 1. 上传文件
curl -X POST http://localhost:5001/api/v1/files/upload \
  -F "files=@test.jpg"

# 2. 获取文件信息（假设返回 file_id 和 bucket）
# file_id: abc-123
# bucket: kb-001

# 3. 测试公共访问
curl -I http://localhost:9000/kb-001/abc-123/source/test.jpg

# 预期响应：HTTP/1.1 200 OK
```

### 自动化测试

使用提供的测试脚本：

```bash
cd management/server
python test_public_access.py
```

## 🔄 迁移现有数据

如果已有数据需要设置公共权限：

```python
# 批量设置脚本
from database import get_db_connection, get_minio_client
import json

def set_public_access_for_all_buckets():
    """为所有存储桶设置公共访问权限"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 获取所有唯一的 parent_id（bucket）
    cursor.execute("SELECT DISTINCT parent_id FROM file")
    buckets = cursor.fetchall()
    
    minio_client = get_minio_client()
    
    for bucket_row in buckets:
        bucket = bucket_row['parent_id']
        
        if minio_client.bucket_exists(bucket):
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": "*"},
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{bucket}/*"]
                    }
                ]
            }
            minio_client.set_bucket_policy(bucket, json.dumps(policy))
            print(f"✓ 设置桶权限: {bucket}")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    set_public_access_for_all_buckets()
```

## 📝 注意事项

1. **首次设置**：新创建的桶会自动设置权限
2. **现有桶**：需要手动运行迁移脚本
3. **权限验证**：上传后建议测试 URL 是否可访问
4. **HTTPS 配置**：生产环境建议使用 HTTPS
5. **域名配置**：可以为 MinIO 配置自定义域名
