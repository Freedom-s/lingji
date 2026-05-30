# 文件页面拆分功能 - 部署指南

## 📋 部署前检查

### 1. 确认 Gotenberg 服务运行

```bash
# 检查 Gotenberg 是否运行
curl http://localhost:3000/health

# 如果未运行，启动 Gotenberg
docker run -d \
  --name gotenberg \
  --restart unless-stopped \
  -p 3000:3000 \
  gotenberg/gotenberg:7
```

### 2. 确认数据库连接

```bash
# 测试数据库连接
mysql -h localhost -u root -p
# 或
psql -h localhost -U postgres
```

### 3. 确认 MinIO 服务

```bash
# 检查 MinIO 是否运行
curl http://localhost:9000/minio/health/live
```

## 🚀 部署步骤

### 步骤 1：安装依赖

```bash
cd management/server
pip install -r requirements.txt
```

**新增依赖**：
- PyMuPDF>=1.23.0 (PDF 处理)
- requests>=2.31.0 (HTTP 请求)

### 步骤 2：重启前台服务（创建新表）

```bash
cd api
python ragflow_server.py
```

**预期输出**：
```
[INFO] start create table FilePage
[INFO] create table success: FilePage
```

### 步骤 3：验证表创建

```sql
-- 连接数据库
mysql -u root -p

-- 查看表结构
USE your_database_name;
SHOW TABLES LIKE 'file_page';
DESC file_page;

-- 预期输出：
-- +-------------+--------------+------+-----+---------+-------+
-- | Field       | Type         | Null | Key | Default | Extra |
-- +-------------+--------------+------+-----+---------+-------+
-- | id          | varchar(32)  | NO   | PRI | NULL    |       |
-- | file_id     | varchar(32)  | NO   | MUL | NULL    |       |
-- | page_number | int          | NO   | MUL | NULL    |       |
-- | location    | varchar(255) | NO   |     | NULL    |       |
-- | size        | int          | YES  |     | 0       |       |
-- | width       | int          | YES  |     | 0       |       |
-- | height      | int          | YES  |     | 0       |       |
-- | format      | varchar(16)  | YES  |     | JPEG    |       |
-- | create_time | bigint       | YES  | MUL | NULL    |       |
-- | create_date | datetime     | YES  | MUL | NULL    |       |
-- | update_time | bigint       | YES  | MUL | NULL    |       |
-- | update_date | datetime     | YES  | MUL | NULL    |       |
-- +-------------+--------------+------+-----+---------+-------+
```

### 步骤 4：重启后台服务

```bash
cd management/server
python app.py
```

**预期输出**：
```
 * Running on http://0.0.0.0:5000
```

### 步骤 5：测试上传功能

```bash
cd management/server

# 准备测试文件（任意 Office 文档或 PDF）
# 修改 test_upload.py 中的 TEST_FILE 变量

python test_upload.py
```

**预期输出**：
```
============================================================
文件上传功能测试
============================================================
开始上传文件: test_document.pdf

响应状态码: 200
响应内容: {'code': 0, 'message': '成功上传 1/1 个文件', 'data': [...]}

✅ 上传成功！
文件ID: abc123...
文件名: test_document.pdf
文件大小: 102400 字节
页数: 5

测试获取页面列表...
✅ 获取到 5 个页面
  - 页码 1: 1654x2339 px, 98304 字节
  - 页码 2: 1654x2339 px, 95232 字节
  - 页码 3: 1654x2339 px, 97280 字节

============================================================
```

## 🧪 功能测试

### 测试 1：上传 Word 文档

```bash
curl -X POST http://localhost:5000/api/v1/files/upload \
  -F "files=@test.docx" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 测试 2：获取页面列表

```bash
curl http://localhost:5000/api/v1/files/{file_id}/pages \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 测试 3：下载特定页面

```bash
curl http://localhost:5000/api/v1/files/{file_id}/pages/1 \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o page_1.jpg
```

### 测试 4：验证 MinIO 存储

```bash
# 使用 MinIO 客户端查看
mc ls myminio/{parent_id}/{file_id}/

# 预期输出：
# [2025-01-13 10:00:00] source/
# [2025-01-13 10:00:00] pages/
```

## 🔍 故障排查

### 问题 1：Gotenberg 连接失败

**错误信息**：
```
GotenbergConvertError: Gotenberg 请求失败: Connection refused
```

**解决方案**：
```bash
# 检查 Gotenberg 是否运行
docker ps | grep gotenberg

# 如果未运行，启动服务
docker start gotenberg

# 或重新创建
docker run -d --name gotenberg -p 3000:3000 gotenberg/gotenberg:7
```

### 问题 2：file_page 表不存在

**错误信息**：
```
Table 'database.file_page' doesn't exist
```

**解决方案**：
```bash
# 重启前台服务以创建表
cd api
python ragflow_server.py

# 或手动创建表
mysql -u root -p < create_file_page_table.sql
```

### 问题 3：PyMuPDF 导入失败

**错误信息**：
```
ModuleNotFoundError: No module named 'fitz'
```

**解决方案**：
```bash
pip install PyMuPDF>=1.23.0
```

### 问题 4：MinIO 上传失败

**错误信息**：
```
S3Error: Access Denied
```

**解决方案**：
```bash
# 检查 MinIO 配置
# 确认 ACCESS_KEY 和 SECRET_KEY 正确
# 确认 bucket 权限设置
```

## 📊 监控检查

### 检查日志

```bash
# 后台服务日志
tail -f management/server/logs/parser.log

# 前台服务日志
tail -f api/logs/ragflow.log
```

### 检查数据库

```sql
-- 查看上传的文件
SELECT id, name, type, size, location FROM file ORDER BY create_time DESC LIMIT 10;

-- 查看页面记录
SELECT file_id, COUNT(*) as page_count FROM file_page GROUP BY file_id;

-- 查看最近上传的文件及其页数
SELECT f.id, f.name, COUNT(fp.id) as pages
FROM file f
LEFT JOIN file_page fp ON f.id = fp.file_id
GROUP BY f.id
ORDER BY f.create_time DESC
LIMIT 10;
```

### 检查 MinIO

```bash
# 列出所有 bucket
mc ls myminio/

# 查看特定文件的存储
mc ls myminio/{parent_id}/{file_id}/ --recursive
```

## ✅ 部署完成检查清单

- [ ] Gotenberg 服务运行正常
- [ ] file_page 表创建成功
- [ ] PyMuPDF 依赖安装成功
- [ ] 前台服务启动成功
- [ ] 后台服务启动成功
- [ ] 测试上传功能正常
- [ ] 页面列表获取正常
- [ ] MinIO 存储结构正确
- [ ] 数据库记录正确

## 🎉 部署成功

如果所有检查项都通过，说明部署成功！

现在可以：
1. 通过后台管理界面上传文件
2. 文件会自动转换为 PDF 并拆分为页面图片
3. 可以通过 API 获取页面列表和下载页面图片

## 📞 获取帮助

如有问题，请查看：
- 技术文档：`docs/file-page-split-implementation.md`
- 详细实现：`docs/file-page-split-implementation-part2.md`
- 项目 Issues：https://github.com/zstar1003/ragflow-plus/issues
