# 视频观看进度追踪 — 设计文档

日期: 2026-07-05
状态: 已批准

## 背景

视频已支持上传和播放，但无法追踪学生的观看进度。需要像学习通那样，记录"有效观看时长"，防止学生直接拖拽到末尾刷完成度。

## 范围

### 范围内

- 后端 API：上报观看进度 + 查询进度
- 有效观看判定：播放时定期上报，拖拽跳跃不计入
- 完成判定：有效观看秒数 ≥ 视频总时长 × 90%
- 前端：续播（从 last_position 恢复）+ 进度展示（进度条/百分比/完成标识）
- 数据库：新建 `student_video_progress` 表

### 范围外

- 教师后台统计汇总（后续可加）
- 分片级覆盖追踪（当前用简单累加方案）
- 多设备同步（每个学生每条视频一条记录）

## 数据库

### 新建表：`student_video_progress`

```sql
CREATE TABLE student_video_progress (
    id VARCHAR(32) PRIMARY KEY,
    create_time BIGINT,
    create_date DATETIME,
    update_time BIGINT,
    update_date DATETIME,
    student_id VARCHAR(32) NOT NULL,
    doc_id VARCHAR(32) NOT NULL,
    watched_seconds INT NOT NULL DEFAULT 0,
    total_duration INT NOT NULL DEFAULT 0,
    last_position INT NOT NULL DEFAULT 0,
    is_completed TINYINT(1) NOT NULL DEFAULT 0,
    UNIQUE KEY uk_student_doc (student_id, doc_id)
);
```

| 字段 | 说明 |
|------|------|
| `student_id` | 学生用户 ID |
| `doc_id` | 视频文档 ID |
| `watched_seconds` | 累计有效观看秒数 |
| `total_duration` | 视频总时长（秒），前端上报 |
| `last_position` | 最后一次上报的播放位置（秒），用于续播 |
| `is_completed` | 有效观看 ≥ 总时长 × 90% 则为 1 |

## API（api/ 服务，端口 9380）

### `GET /v1/video/progress/<doc_id>`

查询当前用户的观看进度。

请求：无 body，通过 Flask-Login 获取 current_user

响应：
```json
{
  "code": 0,
  "data": {
    "watched_seconds": 120,
    "total_duration": 600,
    "last_position": 125,
    "is_completed": false
  }
}
```

如果无记录，返回全 0 的 data。

### `POST /v1/video/progress/report`

上报播放进度。

请求：
```json
{
  "doc_id": "xxx",
  "position": 125,
  "total_duration": 600
}
```

后端逻辑：
1. 查已有记录（按 `student_id + doc_id`）
2. 若无记录，创建记录，`watched_seconds = 0`, `last_position = 0`
3. 计算 `delta = position - last_position`
4. 如果 `0 < delta ≤ 6`（正常播放，允许 1 秒误差），`watched_seconds += delta`
5. 如果 `delta > 6`（跳转/拖拽），不累加
6. 更新 `last_position = position`
7. 检查 `watched_seconds ≥ total_duration × 0.9` → `is_completed = 1`

响应：
```json
{
  "code": 0,
  "data": {
    "watched_seconds": 120,
    "is_completed": false
  }
}
```

### 防拖拽判定

```
正常播放: 0→5→10→15→20    delta=5, 5≤6 → 累加 ✅
暂停后继续: 30→35           delta=5, 5≤6 → 累加 ✅
拖拽跳跃: 10→60             delta=50, 50>6 → 不累加 ❌
回拖: 60→30                 delta=-30, ≤0 → 不累加 ❌
```

## 前端（web/）

### 上报（VideoProgressReporter）

在视频 `<video>` 元素上：

- **播放中**：每 5 秒（通过 `timeupdate` 事件节流）调 POST `/v1/video/progress/report` 上报当前 `currentTime`
- **暂停/结束**：停止上报
- **首次加载时**：调 POST 上报 `total_duration`（通过 `loadedmetadata` 事件获取 `video.duration`）

### 续播（Resume）

在 CoursewarePanel 视频渲染时：
- 调 GET `/v1/video/progress/<doc_id>` 获取进度
- 如果 `last_position > 0` 且 `!is_completed`：
  - 设置 `video.currentTime = last_position`
  - 可选展示提示"从上次位置继续播放"

### 进度展示

在 CoursewarePanel 视频区域：

- **进度条**：已观看百分比 = `watched_seconds / total_duration × 100%`，绿色进度条
- **完成标识**：当 `is_completed = true` 时，显示绿色勾 ✓ "已完成"
- 进度条放在视频播放器下方，不遮挡视频

### 交互流程

```
学生选择视频文档
  → GET /v1/video/progress/<doc_id>
  → 有记录且未完成 → 从 last_position 续播
  → 无记录 → 从 0 开始
  → 播放中每 5s 上报
  → 累加达标 → is_completed = true → 显示 ✓
```

## 涉及文件

| 文件 | 改动类型 |
|---|---|
| `api/apps/video_app.py`（新建） | 进度上报 + 查询 API |
| `api/apps/__init__.py` | 注册 blueprint |
| `api/db/db_models.py` | Peewee ORM 模型 |
| `api/db/services/video_service.py`（新建） | 进度 CRUD |
| `web/src/pages/learning/courseware-panel/index.tsx` | 视频进度展示 + 续播 + 上报逻辑 |

## 后续迭代

- 教师后台统计：班级整体视频完成率、单个学生观看详情
- 严格分片覆盖判定（可选升级）
- 视频观看时长计入学生学习时长统计
