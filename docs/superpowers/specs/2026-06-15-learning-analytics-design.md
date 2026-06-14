# 学生学情分析系统设计

日期：2026-06-15

## 背景

当前系统已经积累了丰富的学生学习数据（`student_quiz_result`、`knowledge_point_mastery`、`student_card_progress`、`conversation`、`document_generation`），但这些数据没有被有效转化为学生可见的学情分析。学生无法知道自己的薄弱知识点、各维度掌握程度和学习趋势。

本设计将新增一个**学情分析页面**，基于多维度雷达图展示学生能力画像，并提供知识点级别的薄弱分析，形成"诊断→推荐→学习"的闭环。

## 目标

1. 学生能在助教卡片上看到学情入口，点击进入独立的学情分析页。
2. 学情分析页展示六维雷达图（测验 / 知识点 / 问答 / 课件 / 闪卡 / 持续力）。
3. 展现章节级别的知识点掌握详情，标注薄弱点并给出推荐动作。
4. 展示最近学习动态和时间热力图。
5. 不改变现有的助教中心页面结构，只增加入口。
6. 新增 1 个后端 API，前端独立页面，保持数据流清晰。

## 非目标

1. 不改变班级、助教、知识库的管理逻辑。
2. 不引入 AI 自动出题或自适应学习路径（留待后续）。
3. 不做教师视角的班级学情对比（教师端已有 dashboard）。
4. 不做综合评分的单一数字（采用雷达图多维展示）。

## 页面定位

### 学情分析中心 (`/learning-analytics?dialogId=xxx`)

学生选择一个课程助教后，看到自己在该课程中的完整学情画像。页面定位为"我的学习诊断报告"，而非简单的数据统计页。

## 整体结构

```
/learning-analytics?dialogId=xxx

┌─────────────────────────────────────────────────┐
│ 顶部导航：← 返回助教中心    学情分析 · 课程名称    │
│ 学期选择器（可选）                                │
└─────────────────────────────────────────────────┘

┌──────────────────────────┐ ┌────────────────────┐
│ 六维雷达图 (ECharts)      │ │ 学习活跃热力图      │
│ 测验 · 知识点 · 问答      │ │ (GitHub 风格日历)   │
│ 课件 · 闪卡 · 持续力      │ │                    │
│                          │ │                    │
│ 当前：B+ 综合表现         │ │ 近 30 天学习分布     │
└──────────────────────────┘ └────────────────────┘

┌─────────────────────────────────────────────────┐
│ 知识点掌握详情                                   │
│ ch1 知识表示方法    ████████░░ 80% 已掌握 5/6   │
│ ch3 谓词逻辑法      ████░░░░░░ 33% 建议复习 2/6 │
│ ch4 语义网络法      暂无数据                     │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ 薄弱知识点与推荐                                 │
│ ⚠ ch3.4 置换与合一算法 — 答错 3 次              │
│   → 重新做测验  → 查看课件文档  → 向 AI 助教提问  │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ 最近学习动态                                     │
│ 6/14 完成测验 12 题，正确 9 题 (75%)             │
│ 6/13 提问 5 次，涉及 ch2-ch4                    │
│ 6/12 复习闪卡 8 张，记住 6 张                    │
└─────────────────────────────────────────────────┘
```

## 数据维度定义

六个雷达图维度全部有数据库字段支撑：

| 维度 | 数据来源 | 计算方式 | 满分含义 |
|------|----------|----------|----------|
| 测验表现 | `student_quiz_result.is_correct` | 正确率 × 100 | 所有测验题全部答对 |
| 知识点掌握 | `knowledge_point_mastery` | 已掌握数 / 总数 (ease_factor ≥ 2.5 视为掌握) | 所有知识点 ease ≥ 2.5 |
| 问答参与 | `conversation.message` | min(提问总数/目标数×100, 100)，目标数=10 | 提问 10 次以上 |
| 课件覆盖 | `student_quiz_result.doc_id` distinct | 已学习文档 / 关联文档总数 × 100 | 覆盖所有课件文档 |
| 闪卡记忆 | `student_card_progress.status` | remembered / 总数 × 100 | 所有闪卡都已记住 |
| 学习持续力 | 连续活跃天数 | min(连续天数/30×100, 100) | 连续 30 天有学习记录 |

**知识点掌握等级：**
- `ease_factor ≥ 2.5` 且 `correct_count ≥ 2` → `mastered`（已掌握）
- `review_count ≥ 1` → `learning`（学习中）
- `wrong_count > correct_count` → `needs_review`（建议复习）
- 无记录 → `untouched`（未学习）

## 新 API

### `GET /v1/learning_stats/analytics?dialog_id=xxx`

**请求：** `dialog_id` (query param, required)

**响应：**
```json
{
  "data": {
    "radar": {
      "quiz_performance": 75,
      "knowledge_mastery": 62,
      "qa_participation": 48,
      "courseware_coverage": 80,
      "flashcard_memory": 90,
      "learning_consistency": 53
    },
    "knowledge_points": [
      {
        "node_id": "ch1",
        "label": "知识表示方法",
        "correct_count": 5,
        "wrong_count": 1,
        "mastery": 83,
        "level": "mastered"
      }
    ],
    "weak_points": [
      {
        "node_id": "ch3_4",
        "label": "置换与合一算法",
        "doc_id": "004d2375d1454bbca9593fbe64466bd7",
        "wrong_count": 3,
        "last_wrong_date": "2026-06-07"
      }
    ],
    "recent_activity": [
      {
        "date": "2026-06-14",
        "type": "quiz",
        "detail": "完成测验 12 题，正确 9 题",
        "score": 75,
        "dialog_id": "xxx"
      }
    ],
    "active_calendar": [
      { "date": "2026-06-14", "count": 3 },
      { "date": "2026-06-13", "count": 5 }
    ]
  }
}
```

**数据来源：**
- `radar` — 聚合 `student_quiz_result`、`knowledge_point_mastery`、`conversation`、`student_card_progress`
- `knowledge_points` — 从 `knowledge_point_mastery` 按 node_id 聚合，关联 `document_generation` 获取 label
- `weak_points` — 筛选 `wrong_count > 0` 且 mastery 最低的 TOP 5
- `recent_activity` — 从 `student_quiz_result` + `conversation` + `student_card_progress` 合并最近 14 天时间线
- `active_calendar` — 按天聚合会话数，最近 90 天

## 前端改造

### 1. 新增学情分析页面

文件：
- `web/src/pages/learning-analytics/index.tsx` — 页面主体（路由参数获取 dialogId，调用 API，组装模块）
- `web/src/pages/learning-analytics/index.less` — 页面样式
- `web/src/pages/learning-analytics/components/RadarChart.tsx` — ECharts 雷达图
- `web/src/pages/learning-analytics/components/CalendarHeatmap.tsx` — 活跃热力图（或用 recharts）
- `web/src/pages/learning-analytics/components/KnowledgeTree.tsx` — 知识点掌握树
- `web/src/pages/learning-analytics/components/WeakPoints.tsx` — 薄弱点列表+推荐
- `web/src/pages/learning-analytics/components/ActivityTimeline.tsx` — 学习动态时间线

### 2. 助教卡片增加学情入口

在 `TeachingAssistantCard` 中增加「查看学情分析」链接，点击跳转 `/learning-analytics?dialogId=xxx`。

### 3. 路由

`web/src/routes.ts` 新增：
```ts
{
  path: '/learning-analytics',
  component: '@/pages/learning-analytics',
}
```

### 4. API 客户端

`web/src/services/learning-analytics-service.ts` 新增调用。

`web/src/utils/api.ts` 新增：
```ts
getLearningAnalytics: (dialogId: string) =>
  `${api_host}/learning_stats/analytics?dialog_id=${dialogId}`,
```

## 后端改造

在 `api/apps/learning_stats_app.py` 新增 `/analytics` 路由：

```python
@manager.route("/analytics", methods=["GET"])
@login_required
def learning_analytics():
    dialog_id = request.args.get("dialog_id")
    # 聚合六个维度的数据
    # 返回 radar, knowledge_points, weak_points, recent_activity, active_calendar
```

## 视觉风格

延续助教中心的教育科技风（`#2563EB` / `#14B8A6` / `#F59E0B`）：

- 雷达图：蓝色系为主，各维度用不同透明度
- 知识点树：绿色(已掌握) / 灰色(未学习) / 琥珀色(建议复习)
- 薄弱点卡片：左侧红色/琥珀色警示条
- 活跃热力图：浅绿到深绿渐变
- 整体背景：浅蓝+浅绿渐变，与助教中心一致

## 状态处理

无数据时：
- 雷达图显示全零，提示「暂无学习数据，开始第一次测验吧」
- 知识点列表显示所有章节为「未学习」
- 活跃热力图全空

加载态：
- 使用 Ant Design Skeleton 占位
- 雷达图和卡片区域骨架屏

错误态：
- 使用 Ant Design Result 组件显示错误信息和重试按钮

## 测试清单

1. 有学习数据时，六维雷达图正常渲染
2. 无学习数据时，显示友好空状态
3. 知识点树按章节层级正确展开/折叠
4. 薄弱点列表按错误次数排序
5. 点击「重新做测验」跳转到测验页面
6. 点击「查看课件文档」跳转到文档页面
7. 点击「向 AI 助教提问」跳转到学习页面对话
8. 活跃热力图正确显示近 90 天数据
9. 最近动态时间线按日期倒序
10. 从助教卡片点击学情入口正确跳转
11. 浅色/暗色主题均可读
12. 窄屏下雷达图缩小，卡片单列
