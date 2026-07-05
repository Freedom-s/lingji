# 视频文件上传 & 知识库集成 — 设计文档

日期: 2026-07-05
状态: 已批准

## 背景

目前知识库只支持文档和图片类文件（pdf, doc, ppt, jpg 等），不支持视频。需要在现有文件上传→知识库→助教→班级的链路中增加视频支持。

## 范围

本次只做**链路打通**，让视频能在整个流程中"透传"，不做视频处理/转码/检索。

### 范围内

- 后端支持上传 mp4 / webm / mov 视频文件（直传 + 分块上传）
- 视频添加到知识库后前端可播放
- 视频文档直接标记完成，跳过解析

### 范围外

- 视频 OCR / ASR / 帧提取
- 视频内容检索
- 视频转码
- 缩略图生成（后续用 opencv-python-headless 补）

## 视频格式

- **mp4** — 主力格式
- **webm** — 浏览器原生支持
- **mov** — Apple 格式，浏览器支持不如 mp4

## 改动清单

### 1. 文件上传 — `management/server/services/files/service.py`

**1a. 扩展允许的文件扩展名**

在 `ALLOWED_EXTENSIONS` 中增加 `"mp4"`, `"webm"`, `"mov"`。

**1b. 新增 VIDEO 文件类型**

在 `utils.py` 的 `FileType` 枚举中添加 `VIDEO = "video"`。

**1c. `filename_type()` 识别视频**

`.mp4` / `.webm` / `.mov` 返回 `FileType.VIDEO.value`。

**1d. `upload_files_to_server()` 视频分支**

在上传处理中，视频文件逻辑：

- 跳过 PDF 转换（`convert_file`）
- 跳过图片转换（`pdf_to_images`）
- 直接读取原始文件字节上传到 MinIO：`{file_id}/source/video.mp4`
- **不创建 `file_page` 记录**（视频没有页面概念）
- 正确设置 Content-Type（`video/mp4` 等），保证浏览器可直接播放

### 2. 路由层 — `management/server/routes/files/routes.py`

`ALLOWED_EXTENSIONS` 与 service 层保持一致，增加视频格式。

### 3. 知识库服务 — `management/server/services/knowledgebases/service.py`

**`add_documents_to_knowledgebase()`** 中创建 document 记录时：

- 如果文件类型是 `video`，document 的 `status` 直接设为 `"1"`（就绪），`run` 直接设为 `"3"`（已完成）
- 这样视频文档不需要点"解析"就已经是可用状态

### 4. 存储结构（MinIO）

```
{user_id}/                     # Bucket (parent_id)
└── {file_id}/
    └── source/
        └── lecture.mp4        # 原始视频
```

对比：
```
文档文件:
└── {file_id}/
    ├── source/document.pdf
    └── pages/0001.jpg, 0002.jpg, ...

视频文件:
└── {file_id}/
    └── source/video.mp4       # 只有原始文件，没有 pages/
```

### 5. 前端 — `management/web/`

- 知识库文档列表中，视频类型显示播放图标或 video 标签
- 点击可以播放视频

## 上传流程对比

```
文档上传:
  file → 存临时文件 → 转 PDF(Gotenberg) → 转图片(pdf2image) → 
  上传 MinIO(source/ + pages/) → 写 file + file_page 记录

视频上传:
  file → 存临时文件 → (跳过所有转换) → 
  上传 MinIO(source/) → 写 file 记录
```

## 添加到知识库后

```
文档: document 记录(status='0', run='0') → 需要手动解析 → chunk + embedding → 可检索
视频: document 记录(status='1', run='3') → 直接完成 → 前端可播放，不参与检索
```

## 涉及文件

| 文件 | 改动类型 |
|---|---|
| `management/server/services/files/service.py` | 核心改动：扩展名、文件类型、上传逻辑分支 |
| `management/server/services/files/utils.py` | 新增 VIDEO 枚举值 |
| `management/server/routes/files/routes.py` | 扩展 ALLOWED_EXTENSIONS |
| `management/server/services/knowledgebases/service.py` | 视频 document 直接标记完成 |
| `management/web/src/` | 前端视频播放支持 |

## 后续迭代

- 缩略图生成：`opencv-python-headless` 提取首帧存到 MinIO
- 视频元信息提取：时长、分辨率
- ASR 语音转文字 → embedding → 可检索
