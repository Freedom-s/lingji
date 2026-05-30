# Dashboard 接口文档

## 概述

Dashboard 接口用于让老师监控当前租户下的数据统计信息，包括基础指标、流量趋势和排行榜数据。

**Base URL**: `http://localhost:5000/api/v1/dashboard`

**认证**: 所有接口都需要 Bearer Token 认证，且要求教师权限（`@require_superuser`）

---

## 1. 基础指标概览

获取当前租户下的 6 个核心指标数据。

### 接口信息

- **URL**: `/overview`
- **方法**: `GET`
- **认证**: 需要

### 请求示例

```bash
curl -X GET "http://localhost:5000/api/v1/dashboard/overview" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 响应示例

```json
{
  "code": 0,
  "data": {
    "student_count": 150,           // 学生数：当前租户下有多少个学生
    "class_count": 12,              // 班级数：当前老师创建了多少个班级
    "conversation_count": 2500,     // 会话数：当前租户下总计有多少个conversation
    "assistant_count": 8,           // 助教数：当前创建了多少个助教
    "file_count": 320,              // 文件数：当前租户下有多少个文件
    "knowledgebase_count": 5        // 知识库数量：当前租户创建了多少个知识库
  },
  "message": "获取概览数据成功"
}
```

### 统计逻辑

| 指标 | 统计逻辑 |
|------|----------|
| 学生数 | `COUNT(user_tenant.user_id)` WHERE `role='student'` AND `tenant_id=当前租户` |
| 班级数 | `COUNT(class.id)` WHERE `tenant_id=当前租户` AND `status='1'` |
| 会话数 | `COUNT(conversation.id)` JOIN `dialog` WHERE `dialog.tenant_id=当前租户` |
| 助教数 | `COUNT(dialog.id)` WHERE `tenant_id=当前租户` AND `status='1'` |
| 文件数 | `COUNT(file.id)` WHERE `tenant_id=当前租户` |
| 知识库数 | `COUNT(knowledgebase.id)` WHERE `tenant_id=当前租户` AND `status='1'` |

---

## 2. 活跃学生数趋势

统计每天/每小时有多少学生登录系统，返回折线图数据。

### 接口信息

- **URL**: `/chart/active-students`
- **方法**: `GET`
- **认证**: 需要

### 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| range | string | 否 | 24h | 时间范围：24h、7d、30d |

### 请求示例

```bash
# 过去24小时（按小时统计）
curl -X GET "http://localhost:5000/api/v1/dashboard/chart/active-students?range=24h" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 过去7天（按天统计）
curl -X GET "http://localhost:5000/api/v1/dashboard/chart/active-students?range=7d" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 过去30天（按天统计）
curl -X GET "http://localhost:5000/api/v1/dashboard/chart/active-students?range=30d" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 响应示例

```json
{
  "code": 0,
  "data": [
    {"time": "2026-04-25 00:00:00", "count": 45},
    {"time": "2026-04-25 01:00:00", "count": 12},
    {"time": "2026-04-25 02:00:00", "count": 8},
    // ...
  ],
  "message": "获取活跃学生趋势数据成功"
}
```

---

## 3. 会话数趋势

统计每天/每小时有多少个 conversation 被创建，返回折线图数据。

### 接口信息

- **URL**: `/chart/conversation-trend`
- **方法**: `GET`
- **认证**: 需要

### 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| range | string | 否 | 24h | 时间范围：24h、7d、30d |

### 请求示例

```bash
curl -X GET "http://localhost:5000/api/v1/dashboard/chart/conversation-trend?range=7d" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 响应示例

```json
{
  "code": 0,
  "data": [
    {"time": "2026-04-19", "count": 320},
    {"time": "2026-04-20", "count": 450},
    {"time": "2026-04-21", "count": 380},
    // ...
  ],
  "message": "获取会话趋势数据成功"
}
```

---

## 4. 最受欢迎的AI助教排行榜

根据指定时间范围内的 conversation 统计哪个 dialog（助教）被调用的次数最多。

### 接口信息

- **URL**: `/ranking/assistants`
- **方法**: `GET`
- **认证**: 需要

### 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| limit | int | 否 | 10 | 返回前N名 |
| range | string | 否 | 24h | 时间范围：24h、7d、30d |

### 请求示例

```bash
curl -X GET "http://localhost:5000/api/v1/dashboard/ranking/assistants?range=7d&limit=10" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 统计逻辑

- 仅统计指定时间范围内的 `conversation` 记录
- 通过 `conversation.dialog_id = dialog.id` 关联到助教
- 对每条 conversation 的 `reference` 字段进行 JSON 解析
- `reference` 是一个 JSON 数组字符串，数组中每个对象的 `total` 字段会被累加
- 最终按每个助教的总调用次数 `call_count` 降序排列

### 响应示例

```json
{
  "code": 0,
  "data": [
    {
      "assistant_id": "dialog_001",
      "assistant_name": "Python编程助教",
      "assistant_icon": "base64_icon_data",
      "call_count": 1250
    },
    {
      "assistant_id": "dialog_002",
      "assistant_name": "数学解题助手",
      "assistant_icon": "base64_icon_data",
      "call_count": 980
    }
  ],
  "message": "获取助教排行榜数据成功"
}
```

---

## 5. 班级活跃度排行榜

统计指定时间范围内哪些 class 的 conversation 记录最多。

### 接口信息

- **URL**: `/ranking/classes`
- **方法**: `GET`
- **认证**: 需要

### 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| limit | int | 否 | 10 | 返回前N名 |
| range | string | 否 | 24h | 时间范围：24h、7d、30d |

### 请求示例

```bash
curl -X GET "http://localhost:5000/api/v1/dashboard/ranking/classes?range=30d&limit=10" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 统计逻辑

- 仅统计指定时间范围内的 `conversation` 记录
- 通过 `class -> user_class -> conversation` 关联统计
- 只统计 `user_class.role = 'student'` 的学生会话，不统计老师会话
- 通过 `conversation.user_id = user_class.user_id` 关联到班级学生
- 最终按每个班级的会话数量 `conversation_count` 降序排列

### 响应示例

```json
{
  "code": 0,
  "data": [
    {
      "class_id": "class_001",
      "class_name": "2024前端冲刺班",
      "conversation_count": 850
    },
    {
      "class_id": "class_002",
      "class_name": "Python进阶班",
      "conversation_count": 620
    }
  ],
  "message": "获取班级活跃度排行榜数据成功"
}
```

---

## 6. 一键获取所有数据

一次性获取所有 dashboard 数据，减少前端请求次数。

### 接口信息

- **URL**: `/all`
- **方法**: `GET`
- **认证**: 需要

### 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| range | string | 否 | 24h | 趋势图时间范围：24h、7d、30d |
| limit | int | 否 | 10 | 排行榜返回前N名 |

### 请求示例

```bash
curl -X GET "http://localhost:5000/api/v1/dashboard/all?range=7d&limit=10" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 响应示例

```json
{
  "code": 0,
  "data": {
    "overview": {
      "student_count": 150,
      "class_count": 12,
      "conversation_count": 2500,
      "assistant_count": 8,
      "file_count": 320,
      "knowledgebase_count": 5
    },
    "active_students": [
      {"time": "2026-04-19", "count": 45},
      {"time": "2026-04-20", "count": 52},
      // ...
    ],
    "conversation_trend": [
      {"time": "2026-04-19", "count": 320},
      {"time": "2026-04-20", "count": 450},
      // ...
    ],
    "assistant_ranking": [
      {
        "assistant_id": "dialog_001",
        "assistant_name": "Python编程助教",
        "assistant_icon": "base64_icon_data",
        "call_count": 1250
      },
      // ...
    ],
    "class_ranking": [
      {
        "class_id": "class_001",
        "class_name": "2024前端冲刺班",
        "conversation_count": 850
      },
      // ...
    ]
  },
  "message": "获取dashboard数据成功"
}
```

---

## 错误响应

所有接口在发生错误时返回以下格式：

```json
{
  "code": 400,  // 或 401, 403, 500
  "message": "错误信息描述"
}
```

### 常见错误码

| 错误码 | 说明 |
|--------|------|
| 400 | 请求参数错误或用户未关联租户 |
| 401 | 缺少认证令牌或令牌已过期 |
| 403 | 权限不足（需要教师权限） |
| 500 | 服务器内部错误 |

---

## 数据库表依赖

本接口依赖以下数据库表：

- `user` - 用户信息表
- `user_tenant` - 用户租户关联表（获取租户ID和角色）
- `class` - 班级表
- `user_class` - 用户班级关联表
- `dialog` - 助教（对话）表
- `conversation` - 会话记录表
- `file` - 文件表
- `knowledgebase` - 知识库表

---

## 前端对接建议

### 基础指标展示

使用卡片（Card）组件展示 6 个数字指标。

### 趋势图展示

使用折线图（Line Chart）组件：
- X 轴：时间
- Y 轴：数量
- 支持切换 24h/7d/30d

### 排行榜展示

使用柱状图（Bar Chart）或列表组件：
- 助教排行榜：横轴为调用次数
- 班级排行榜：横轴为会话数量

### 数据刷新

建议：
- 基础指标：每 5 分钟刷新一次
- 趋势图：用户切换时间范围时刷新
- 排行榜：每 10 分钟刷新一次
