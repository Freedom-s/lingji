# 文件页面拆分功能 - 文档索引

## 📚 文档列表

### 1. 快速开始
- **[QUICK_START.md](QUICK_START.md)** - 5分钟快速部署指南
  - 适合：想要快速体验功能
  - 内容：最简化的部署步骤

### 2. 技术设计文档
- **[file-page-split-implementation.md](file-page-split-implementation.md)** - 技术设计（第一部分）
  - 需求背景
  - 系统架构
  - 数据库设计
  - MinIO 存储设计
  - 处理流程
  
- **[file-page-split-implementation-part2.md](file-page-split-implementation-part2.md)** - 技术设计（第二部分）
  - 技术实现细节
  - 错误处理与回滚
  - 依赖与配置
  - 测试方案
  - 性能优化
  - 安全考虑
  - API 文档

### 3. 部署指南
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - 完整部署指南
  - 部署前检查
  - 详细部署步骤
  - 功能测试
  - 故障排查
  - 监控检查

### 4. 实现总结
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - 实现总结
  - 已完成的工作
  - 代码统计
  - 功能特性
  - 技术要点
  - 使用示例

### 5. 数据库脚本
- **[create_file_page_table.sql](create_file_page_table.sql)** - 建表 SQL
  - 手动创建 file_page 表

## 🎯 根据需求选择文档

### 我想快速体验功能
👉 阅读 [QUICK_START.md](QUICK_START.md)

### 我想了解技术设计
👉 阅读 [file-page-split-implementation.md](file-page-split-implementation.md) 和 [file-page-split-implementation-part2.md](file-page-split-implementation-part2.md)

### 我想部署到生产环境
👉 阅读 [DEPLOYMENT.md](DEPLOYMENT.md)

### 我想了解实现细节
👉 阅读 [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)

### 我遇到了问题
👉 查看 [DEPLOYMENT.md#故障排查](DEPLOYMENT.md#故障排查)

## 📊 功能概览

### 支持的文件格式
- PDF (.pdf)
- Word (.doc, .docx)
- Excel (.xls, .xlsx, .csv)
- PowerPoint (.ppt, .pptx)
- 文本 (.txt)
- Markdown (.md)
- HTML (.html)

### 核心功能
1. **自动格式转换**：将各种格式统一转为 PDF
2. **页面拆分**：按页生成高质量图片
3. **分层存储**：MinIO 中分别存储原始文件和页面图片
4. **元数据记录**：记录每页的宽度、高度、大小等信息
5. **API 查询**：提供页面列表查询和图片下载接口

### 技术栈
- **文档转换**：Gotenberg (LibreOffice + Chromium)
- **PDF 处理**：PyMuPDF (fitz)
- **对象存储**：MinIO
- **数据库**：MySQL / PostgreSQL
- **后端框架**：Flask

## 🏗️ 系统架构

```
用户上传文件
    ↓
转换为 PDF (Gotenberg)
    ↓
拆分为图片 (PyMuPDF)
    ↓
MinIO 存储
    ├── source/原始文件
    └── pages/页面图片
    ↓
数据库记录
    ├── file 表
    └── file_page 表
```

## 📦 MinIO 存储结构

```
{parent_id}/                    # Bucket
└── {file_id}/                  # 文件目录
    ├── source/                 # 原始文件
    │   └── document.pdf
    └── pages/                  # 页面图片
        ├── 0001.jpg
        ├── 0002.jpg
        └── ...
```

## 🗄️ 数据库结构

```
file 表
├── id
├── name
├── location → {file_id}/source/document.pdf
└── ...

file_page 表 (新增)
├── id
├── file_id (FK)
├── page_number
├── location → {file_id}/pages/0001.jpg
├── size, width, height
└── ...
```

## 🔗 相关链接

- **项目地址**：https://github.com/zstar1003/ragflow-plus
- **项目文档**：https://xdxsb.top/ragflow-plus
- **Gotenberg 文档**：https://gotenberg.dev/docs/routes
- **PyMuPDF 文档**：https://pymupdf.readthedocs.io/

## 📞 获取帮助

如有问题，请：
1. 查看 [DEPLOYMENT.md#故障排查](DEPLOYMENT.md#故障排查)
2. 查看项目 Issues
3. 提交新的 Issue

---

**版本**：v1.0  
**日期**：2025-01-13  
**作者**：Kiro AI Assistant
