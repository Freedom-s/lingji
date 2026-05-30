# 快速开始指南

## 🚀 5分钟快速部署

### 前置条件
- ✅ Python 3.8+
- ✅ MySQL 或 PostgreSQL
- ✅ Docker（用于 Gotenberg）
- ✅ MinIO

### 步骤 1：启动 Gotenberg（1分钟）

```bash
docker run -d \
  --name gotenberg \
  --restart unless-stopped \
  -p 3000:3000 \
  gotenberg/gotenberg:7

# 验证
curl http://localhost:3000/health
# 预期输出：{"status":"up"}
```

### 步骤 2：安装依赖（1分钟）

```bash
cd management/server
pip install PyMuPDF>=1.23.0 requests>=2.31.0
```

### 步骤 3：创建数据库表（1分钟）

**方式 A：自动创建（推荐）**
```bash
cd api
python ragflow_server.py
# 表会自动创建
```

**方式 B：手动创建**
```bash
mysql -u root -p your_database < docs/create_file_page_table.sql
```

### 步骤 4：启动服务（1分钟）

```bash
# 启动后台管理服务
cd management/server
python app.py
```

### 步骤 5：测试功能（1分钟）

```bash
# 准备测试文件
echo "测试文档" > test.txt

# 上传测试
curl -X POST http://localhost:5000/api/v1/files/upload \
  -F "files=@test.txt"

# 查看结果
# 应该返回包含 pages 字段的 JSON
```

## ✅ 完成！

现在你可以：
1. 上传各种格式的文档（Word、Excel、PPT、PDF等）
2. 文档会自动转换为 PDF 并拆分为页面图片
3. 通过 API 获取页面列表和下载页面图片

## 📚 下一步

- 查看完整文档：`docs/file-page-split-implementation.md`
- 查看部署指南：`docs/DEPLOYMENT.md`
- 查看实现总结：`docs/IMPLEMENTATION_SUMMARY.md`

## ❓ 遇到问题？

查看故障排查：`docs/DEPLOYMENT.md#故障排查`
