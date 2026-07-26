# 每周学习进度管理 — 设计规范

## 概述

在管理后台新增「进度管理」模块。老师按班级创建每周学习进度，选择文档并设定完成条件，系统自动校验每个学生的完成状态。未完成的学生在管理后台标红提醒，完成率一目了然。

## 核心决策

| 决策项 | 选择 |
|--------|------|
| 进度定义 | 按文档指定，老师选择文档作为任务单元 |
| 通知方式 | 平台内通知（管理后台完成率概览 + 学生端任务面板），不涉及邮件 |
| 配置范围 | 按班级配置，不同班级可有不同周进度 |
| 校验方式 | 后端实时计算，老师查看时触发刷新 |

---

## 数据库设计

新增 3 张表，全部建在 `rag_flow` 库。

### 1. `weekly_progress` — 每周进度定义

| 列 | 类型 | 说明 |
|---|------|------|
| `id` | varchar(32) PK | UUID |
| `class_id` | varchar(32) NOT NULL INDEX | 关联 `class.id` |
| `name` | varchar(200) NOT NULL | 如"第3周学习任务" |
| `week_start` | date NOT NULL | 周开始日期 |
| `week_end` | date NOT NULL | 周结束日期 |
| `status` | varchar(1) DEFAULT '1' | 1=进行中, 0=已结束 |
| `create_time` | bigint | |
| `create_date` | datetime | |
| `update_time` | bigint | |
| `update_date` | datetime | |

### 2. `weekly_progress_doc` — 进度中的文档任务

| 列 | 类型 | 说明 |
|---|------|------|
| `id` | varchar(32) PK | UUID |
| `progress_id` | varchar(32) NOT NULL INDEX | 关联 `weekly_progress.id` |
| `doc_id` | varchar(32) NOT NULL INDEX | 关联 `document.id` |
| `quiz_threshold` | int DEFAULT 0 | 测验正确率阈值（百分制），0=仅需作答，>0=正确率需达标 |
| `create_time` | bigint | |
| `create_date` | datetime | |
| `update_time` | bigint | |
| `update_date` | datetime | |

UNIQUE(`progress_id`, `doc_id`)

### 3. `student_progress_status` — 学生完成状态

| 列 | 类型 | 说明 |
|---|------|------|
| `id` | varchar(32) PK | UUID |
| `progress_id` | varchar(32) NOT NULL INDEX | |
| `doc_id` | varchar(32) NOT NULL INDEX | |
| `student_id` | varchar(32) NOT NULL INDEX | |
| `is_completed` | tinyint(1) DEFAULT 0 | 该文档任务是否完成 |
| `completed_at` | datetime | 首次完成时间 |
| `video_completed` | tinyint(1) DEFAULT 0 | 视频是否看完 |
| `quiz_passed` | tinyint(1) DEFAULT 0 | 测验是否达标 |
| `has_notes` | tinyint(1) DEFAULT 0 | 是否有笔记 |
| `create_time` | bigint | |
| `create_date` | datetime | |
| `update_time` | bigint | |
| `update_date` | datetime | |

UNIQUE(`progress_id`, `doc_id`, `student_id`)

---

## 数据范围

### 学生范围
通过 `user_class` 表确定班级成员：
```sql
SELECT user_id FROM user_class WHERE class_id = ? AND role = 'student'
```

### 文档范围
与评分系统相同的数据链路：
```
class → class_dialog → dialog → dialog.kb_ids (JSON数组) → knowledgebase → document
```

`GET /docs/<class_id>` 返回的文档列表需要标记每个文档是否有测验（检查 `document_generation` 中是否存在 `generation_type='quiz'` 的记录），前端据此决定是否显示测验阈值输入框。

---

## 完成判定逻辑

刷新 `student_progress_status` 时，对每个 `(progress_id, doc_id, student_id)`：

### 视频文档（`document.type = 'video'`）
```
video_completed = (student_video_progress.is_completed = 1)
quiz_passed = 0  (video 无测验)
has_notes = 0
is_completed = video_completed
```

### 有测验的文档（`document_generation` 中有 `generation_type = 'quiz'` 的记录）
```
quiz_total = COUNT(student_quiz_result WHERE student_id, doc_id)
quiz_correct = SUM(is_correct)
quiz_rate = quiz_total > 0 ? quiz_correct / quiz_total * 100 : 0
quiz_passed = (quiz_total > 0 AND quiz_rate >= quiz_threshold)
has_notes = COUNT(student_note WHERE student_id, doc_id) > 0
is_completed = quiz_passed
```

### 无测验文档（PPT/PDF，无对应 quiz generation）
```
has_notes = COUNT(student_note WHERE student_id, doc_id) > 0
is_completed = has_notes
```

### 汇总
- 学生总完成数 = 该 progress 中 `is_completed = 1` 的文档数
- 学生全部完成 = 总完成数 = 该 progress 的文档总数

---

## 管理后台 API

新增 Blueprint `progress_bp`，前缀 `/api/v1/progress`，全部需要 `@require_superuser`。

### 周进度 CRUD

```
GET    /<class_id>              列表（按 week_start 降序）
POST   /<class_id>              创建 { name, week_start, week_end, doc_ids: [...], quiz_thresholds: {...} }
PUT    /<progress_id>            修改
DELETE /<progress_id>            删除（级联删除 weekly_progress_doc + student_progress_status）
```

### 文档列表

```
GET /docs/<class_id>            获取该班级关联的所有可用文档（含名称、类型、是否有测验）
```

### 完成状态

```
GET  /status/<progress_id>      获取完成情况（触发全量刷新），返回概览 + 每个学生明细
POST /refresh/<progress_id>     手动强制刷新
```

### 响应格式

`GET /status/<progress_id>`：

```json
{
  "code": 0,
  "data": {
    "progress": {
      "id": "xxx",
      "name": "第3周学习任务",
      "week_start": "2026-07-27",
      "week_end": "2026-08-02",
      "status": "1",
      "docs": [
        {"doc_id": "xxx", "doc_name": "视频：RAG概述", "doc_type": "video", "quiz_threshold": 0},
        {"doc_id": "yyy", "doc_name": "课件：向量数据库", "doc_type": "ppt", "quiz_threshold": 60}
      ]
    },
    "summary": {
      "total_students": 35,
      "completed_count": 28,
      "incomplete_count": 7,
      "completion_rate": 80.0
    },
    "students": [
      {
        "student_id": "xxx",
        "student_name": "张三",
        "doc_statuses": [
          {"doc_id": "xxx", "is_completed": true, "video_completed": true, "quiz_passed": false, "has_notes": false},
          {"doc_id": "yyy", "is_completed": false, "video_completed": false, "quiz_passed": false, "has_notes": true}
        ],
        "total_completed": 1,
        "total_docs": 2,
        "is_all_completed": false
      }
    ]
  }
}
```

---

## 管理后台前端

新增路由 `/progress`，菜单名「进度管理」，一个页面两个 Tab。

### 文件结构

```
management/server/routes/progress/__init__.py
management/server/routes/progress/routes.py
management/server/services/progress/service.py

management/web/src/common/apis/progress/index.ts
management/web/src/common/apis/progress/type.ts
management/web/src/pages/progress/index.vue
management/web/src/common/assets/icons/progress.svg
```

### Tab 1：进度列表

- 班级选择器 + 「新建周进度」按钮
- 周进度列表表格：名称、时间范围、状态、操作（查看完成/编辑/删除）
- 新建/编辑弹窗：
  - 名称输入、日期范围选择
  - 文档多选列表（checkbox），每行显示：文档名 + 文档类型标签 + 测验阈值输入（仅对有测验的文档显示）
  - 保存时校验至少选 1 个文档

### Tab 2：完成情况

- 班级选择器 + 周进度选择器（下拉，列出所有周进度）
- 概览卡片：完成率百分比 + 进度条 + 已完成/未完成人数
- 学生明细表格：姓名 + 每个文档状态列（✅/❌）+ 整体完成状态
- 筛选按钮：[全部] [已完成] [未完成]

### 数据流

```
Tab1 创建进度 → POST /api/v1/progress/:class_id
Tab2 选择进度 → GET /api/v1/progress/status/:progress_id → 渲染表格
```

---

## 实施范围

### 本次包含
- [ ] 3 张新表的 DDL 及 Peewee 模型
- [ ] `management/server/services/progress/service.py` — 周进度 CRUD + 完成状态刷新计算
- [ ] `management/server/routes/progress/` — 全部 API 端点 + Blueprint 注册
- [ ] `management/web/src/common/apis/progress/` — TypeScript API 客户端
- [ ] `management/web/src/pages/progress/index.vue` — 进度管理页面（两个 Tab）
- [ ] SVG 图标 + 路由注册

### 本次不包含
- 学生前台「本周任务」面板（后续需求）
- 邮件/企业微信通知
- 跨周进度趋势分析
- 进度自动切换（进行中→已结束根据日期自动判断由前端/手动处理）
