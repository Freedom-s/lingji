# 学生综合评分系统 — 设计规范

## 概述

在管理后台新增「评分管理」模块。老师可为每个班级配置 6 个评分维度的权重，平台根据权重实时计算每个学生的综合评分。计算完全基于已有数据动态聚合，不留存计算结果。

## 核心决策

| 决策项 | 选择 |
|--------|------|
| 评分范围 | 按班级配置，不同班级可有不同权重 |
| 维度启用 | 老师自由勾选，启用维度权重之和 = 100% |
| 外部数据导入 | 支持多源导入，每源独立满分值，全部源归一化后取平均计入 |
| 计算规则 | 系统自动归一化到 0-100，乘权重后求和 |
| 时效性 | 实时计算，不缓存、不落库、不锁档 |

---

## 数据库设计

新增 3 张表，全部建在 `rag_flow` 库。

### 1. `scoring_config` — 班级评分配置

| 列 | 类型 | 说明 |
|---|------|------|
| `id` | varchar(32) PK | UUID |
| `class_id` | varchar(32) UNIQUE NOT NULL | 关联 `class.id`，一个班级仅一条配置 |
| `video_enabled` | tinyint(1) DEFAULT 1 | |
| `video_weight` | int DEFAULT 0 | 权重 0-100 |
| `quiz_enabled` | tinyint(1) DEFAULT 1 | |
| `quiz_weight` | int DEFAULT 0 | |
| `note_enabled` | tinyint(1) DEFAULT 1 | |
| `note_weight` | int DEFAULT 0 | |
| `flashcard_enabled` | tinyint(1) DEFAULT 1 | |
| `flashcard_weight` | int DEFAULT 0 | |
| `qa_enabled` | tinyint(1) DEFAULT 1 | |
| `qa_weight` | int DEFAULT 0 | |
| `external_enabled` | tinyint(1) DEFAULT 0 | 默认关闭 |
| `external_weight` | int DEFAULT 0 | |
| `create_time` | bigint | 标准时间戳 |
| `create_date` | datetime | |
| `update_time` | bigint | |
| `update_date` | datetime | |

约束：应用层校验启用维度的 weight 之和 = 100。

### 2. `external_score_source` — 外部数据源定义

| 列 | 类型 | 说明 |
|---|------|------|
| `id` | varchar(32) PK | UUID |
| `class_id` | varchar(32) NOT NULL INDEX | 所属班级 |
| `source_name` | varchar(100) NOT NULL | 如"学习通章节测验" |
| `max_score` | int NOT NULL | 满分值，如 100 |
| `create_time` | bigint | |
| `create_date` | datetime | |
| `update_time` | bigint | |
| `update_date` | datetime | |

### 3. `external_score_record` — 外部评分记录

| 列 | 类型 | 说明 |
|---|------|------|
| `id` | varchar(32) PK | UUID |
| `source_id` | varchar(32) NOT NULL INDEX | 关联 `external_score_source.id` |
| `student_id` | varchar(32) NOT NULL INDEX | 关联 `user.id` |
| `score` | decimal(8,2) NOT NULL | 该源上的得分 |
| `create_time` | bigint | |
| `create_date` | datetime | |
| `update_time` | bigint | |
| `update_date` | datetime | |

UNIQUE(`source_id`, `student_id`)。

---

## 数据范围

### 学生范围

通过 `user_class` 表确定班级成员：
```sql
SELECT user_id FROM user_class WHERE class_id = ? AND role = 'student'
```

### 文档范围

```
class → class_dialog (WHERE class_id = X)
      → dialog (获取 dialog.kb_ids, JSON 数组)
      → knowledgebase (WHERE id IN kb_ids)
      → document (WHERE kb_id IN ...)
```

具体 SQL 逻辑：

```
1. SELECT dialog_id FROM class_dialog WHERE class_id = ?
2. SELECT kb_ids FROM dialog WHERE id IN (上面的 dialog_ids)
3. 解析 kb_ids JSON 数组, 去重去空
4. SELECT id FROM document WHERE kb_id IN (上面的 kb_ids)
   → 得到该班级的所有文档 ID 集合
5. 各维度的学生行为数据用 doc_id IN (...) 过滤
```

此逻辑封装在评分计算引擎中，每次查询时执行。

---

## 评分计算规则

每个维度独立归一化到 0-100，然后加权求和：

```
总分 = Σ(维度归一化分 × 维度权重 / 100)
```

### ① 视频

- **数据源**：`student_video_progress`
- **范围**：该班级关联文档中类型为 video 的文档
- **算法**：`完成率 = 完成视频数(is_completed=1) / 总视频数 × 100`
- **无视频**：0 分

### ② 测验

- **数据源**：`student_quiz_result`
- **范围**：该班级关联文档的所有答题记录
- **算法**：`正确率 = 正确数 / 总答题数 × 100`
- **无记录**：0 分

### ③ 笔记

- **数据源**：`student_note`
- **范围**：该班级关联文档的所有笔记
- **算法**：`覆盖率 = 有笔记的页面数 / 文档总页面数 × 100`
- **无页面**：0 分

### ④ 概念速记

- **数据源**：`student_card_progress`
- **范围**：该班级关联文档的所有闪卡
- **算法**：`记忆率 = 记住的卡片数 / 总卡片数 × 100`
- **无卡片**：0 分

### ⑤ 问答活跃度

- **数据源**：`conversation`
- **范围**：该班级关联 dialog 中的该学生消息
- **算法**：`活跃分 = min(消息数 / 20 × 100, 100)`
- **无消息**：0 分

### ⑥ 外部导入

- **数据源**：`external_score_record`（仅该班级启用的数据源）
- **算法**：`各源归一化 = score / max_score × 100` → `外部总分 = 所有源归一化分取平均`
- **无数据源或无记录**：0 分

---

## 管理后台 API

新增 Blueprint `scoring_bp`，前缀 `/api/v1/scoring`，全部需要 `@require_superuser`。

### 评分配置

```
GET  /config/<class_id>         获取班级的评分配置（无记录则返回全维度默认等权配置）
PUT  /config/<class_id>         保存/更新，body: { video_enabled, video_weight, ... }
                               校验: 启用维度权重之和 = 100
```

### 外部数据源

```
GET    /external-source/<class_id>    列表
POST   /external-source               新增 { class_id, source_name, max_score }
PUT    /external-source/<source_id>    修改
DELETE /external-source/<source_id>    删除（级联删除关联 external_score_record）
```

### 外部评分记录

```
GET  /external-record/<source_id>              该源所有学生成绩列表
POST /external-record/upload                    上传 Excel（multipart），body 含 source_id
                                               模板列: 学号(student_id) | 得分(score)
                                               批量 upsert（按 source_id + student_id）
PUT  /external-record/<record_id>              手动修改单条 { score }
```

### 评分结果（实时计算）

```
GET /result/<class_id>                 全班学生评分总表（含各维度明细 + 总分）
GET /result/<class_id>/<student_id>    单个学生详情
```

### 响应格式示例

`GET /result/<class_id>`：

```json
{
  "code": 0,
  "data": {
    "class_id": "xxx",
    "class_name": "2024级计算机1班",
    "config": {
      "video_enabled": true, "video_weight": 20,
      "quiz_enabled": true, "quiz_weight": 30,
      "note_enabled": true, "note_weight": 15,
      "flashcard_enabled": true, "flashcard_weight": 15,
      "qa_enabled": true, "qa_weight": 10,
      "external_enabled": true, "external_weight": 10
    },
    "students": [
      {
        "student_id": "xxx",
        "student_name": "张三",
        "dimensions": {
          "video": 85.0,
          "quiz": 72.5,
          "note": 60.0,
          "flashcard": 90.0,
          "qa": 45.0,
          "external": 78.0
        },
        "total_score": 71.75
      }
    ]
  }
}
```

---

## 管理后台前端

新增路由 `/scoring`，菜单名「评分管理」，一个页面两个 Tab。

### 文件结构

```
management/server/routes/scores/__init__.py
management/server/routes/scores/routes.py
management/server/services/scores/service.py       # 配置 CURD + 评分计算

management/web/src/common/apis/scores/index.ts     # API 函数
management/web/src/common/apis/scores/type.ts      # 类型定义
management/web/src/pages/scoring/index.vue         # 评分管理页面
management/web/src/pages/scoring/components/       # 子组件（可选拆分）
```

### Tab 1：评分配置

- **班级选择器**：`el-select` 下拉，加载该老师管辖的所有班级
- **维度权重面板**：每个维度一行
  - `el-switch` 开关启用/禁用
  - `el-slider` 滑块设置权重（0-100）
  - 底部实时显示 `已启用合计: N%`，≠100 时红色高亮 + 保存按钮置灰
- **外部数据源区域**（仅当 external_enabled=true 显示）
  - 表格列出已有数据源（名称、满分、操作按钮）
  - 「添加数据源」按钮 → 弹窗填名称+满分
  - 「上传成绩」→ 选择数据源 → `el-upload` 上传 Excel → 显示解析预览 → 确认导入
  - 提供 Excel 模板下载（学号 | 得分 两列）
- 「保存配置」按钮

### Tab 2：评分结果

- **班级选择器**：同 Tab 1，切换班级重新计算
- **操作栏**：「导出 Excel」按钮，下载当前评分总表
- **评分总表**：`el-table`
  - 固定列：排名、姓名
  - 动态列：根据启用的维度显示对应列（列头标权重，如"测验 30%"）
  - 末列：总分（高亮加粗）
  - 每列支持排序
  - 顶部搜索框按姓名筛选
- **学生详情**：点击学生姓名行展开（或弹窗），显示各维度计算明细（如测验：答对 12/15 题，正确率 80%）

### 数据流

```
Tab1 保存配置 → PUT /api/v1/scoring/config/:class_id
Tab2 切换班级 → GET /api/v1/scoring/result/:class_id → 渲染表格
```

---

## 实施范围

### 本次包含
- [ ] 3 张新表的 DDL（通过 Docker MySQL 执行）及 `api/db/db_models.py` 中的 Peewee 模型定义
- [ ] `management/server/services/scores/service.py` — 配置 CRUD + 数据范围解析 + 评分计算引擎
- [ ] `management/server/routes/scores/` — 全部 API 端点（Blueprint 注册）
- [ ] `management/web/src/common/apis/scores/` — API 客户端（index.ts + type.ts）
- [ ] `management/web/src/pages/scoring/index.vue` — 评分管理页面（两个 Tab）
- [ ] 管理后台路由注册 + 侧边栏菜单项

### 本次不包含
- 学生端前台展示评分（后续需求）
- 评分历史/快照（当前采用实时计算）
- 外部平台 API 直连（仅支持 Excel 导入）
