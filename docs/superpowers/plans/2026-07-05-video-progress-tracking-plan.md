# 视频观看进度追踪 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现视频观看进度追踪：记录有效观看时长，防止拖拽刷进度，前端展示进度条 + 完成标识 + 断点续播。

**Architecture:** 后端用 Peewee ORM 新建 `student_video_progress` 表 + `video_app.py` API（自动注册为 `/v1/video`），前端在 CoursewarePanel 中加进度上报（每 5s）和进度展示（进度条 + 完成 ✓）。

**Tech Stack:** Python 3, Flask, Peewee ORM, React, TypeScript

## Global Constraints

- 有效观看判定：前端每 5s 上报 position，delta ≤ 6s 累加，delta > 6s 视为拖拽不累加
- 完成阈值：watched_seconds ≥ total_duration × 0.9
- 每人每视频一条记录（student_id + doc_id 唯一）
- 前端展示：进度条 + 完成标识 ✓
- 续播：从 last_position 恢复

---

## 文件结构

| 文件 | 职责 | 类型 |
|---|---|---|
| `api/db/db_models.py` | Peewee DataBaseModel | 新增模型 |
| `api/apps/video_app.py` | GET progress / POST report API | 新建 |
| `web/src/pages/learning/courseware-panel/index.tsx` | 进度上报 + 展示 + 续播 | 修改 |
| `web/src/pages/learning/courseware-panel/index.less` | 进度条样式 | 修改 |

---

### Task 1: 数据库模型 — Peewee ORM 模型

**Files:**
- Modify: `api/db/db_models.py`（在 StudentNote 类后面新增）

**Interfaces:**
- Produces: `StudentVideoProgress` Peewee model，表名 `student_video_progress`，由 `init_database_tables()` 自动建表

- [ ] **Step 1: 在 db_models.py 中新增 StudentVideoProgress 模型**

在 `StudentNote` 类定义之后（约第 936 行后）插入：

```python
class StudentVideoProgress(DataBaseModel):
    """学生视频观看进度表"""
    id = CharField(max_length=32, primary_key=True)
    student_id = CharField(max_length=32, null=False, help_text="学生user.id", index=True)
    doc_id = CharField(max_length=32, null=False, help_text="关联document表", index=True)
    watched_seconds = IntegerField(default=0, help_text="累计有效观看秒数")
    total_duration = IntegerField(default=0, help_text="视频总时长（秒）")
    last_position = IntegerField(default=0, help_text="最后播放位置（秒）")
    is_completed = BooleanField(default=False, help_text="是否完成观看")

    class Meta:
        db_table = "student_video_progress"
        indexes = (
            (('student_id', 'doc_id'), True),  # unique
        )
```

- [ ] **Step 2: 验证模型语法**

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2
python -c "
from api.db.db_models import StudentVideoProgress
print(f'Table: {StudentVideoProgress._meta.table_name}')
print(f'Fields: {[f.name for f in StudentVideoProgress._meta.sorted_fields]}')
"
```

预期输出：
```
Table: student_video_progress
Fields: ['id', 'create_time', 'create_date', 'update_time', 'update_date', 'student_id', 'doc_id', 'watched_seconds', 'total_duration', 'last_position', 'is_completed']
```

- [ ] **Step 3: 提交**

```bash
git add api/db/db_models.py
git commit -m "feat: add StudentVideoProgress Peewee model for video watch tracking"
```

---

### Task 2: API 端点 — video_app.py

**Files:**
- Create: `api/apps/video_app.py`

**Interfaces:**
- Consumes: `StudentVideoProgress` model from Task 1
- Produces: `GET /v1/video/progress/<doc_id>` — 查询进度；`POST /v1/video/progress/report` — 上报进度
- 自动注册：`api/apps/__init__.py` 的 `search_pages_path` 扫描 `*_app.py`，自动注册 blueprint 前缀 `/v1/video`

- [ ] **Step 1: 创建 api/apps/video_app.py**

```python
"""
Video Progress API — 视频观看进度追踪

GET  /v1/video/progress/<doc_id>  — 查询当前用户的观看进度
POST /v1/video/progress/report    — 上报播放进度（有效观看判定）
"""
from datetime import datetime

from flask import request
from flask_login import login_required, current_user

from api.db.db_models import StudentVideoProgress
from api.utils.api_utils import get_json_result, get_data_error_result
from api.utils import get_uuid


@manager.route("/progress/<doc_id>", methods=["GET"])  # noqa: F821
@login_required
def get_progress(doc_id):
    """获取当前用户对指定视频的观看进度"""
    student_id = current_user.id

    try:
        record = StudentVideoProgress.select().where(
            (StudentVideoProgress.student_id == student_id) &
            (StudentVideoProgress.doc_id == doc_id)
        ).first()

        if record:
            return get_json_result(data={
                "watched_seconds": record.watched_seconds,
                "total_duration": record.total_duration,
                "last_position": record.last_position,
                "is_completed": record.is_completed,
            })
        else:
            return get_json_result(data={
                "watched_seconds": 0,
                "total_duration": 0,
                "last_position": 0,
                "is_completed": False,
            })
    except Exception as e:
        return get_data_error_result(message=str(e))


@manager.route("/progress/report", methods=["POST"])
@login_required
def report_progress():
    """上报播放进度，后端做有效观看判定"""
    data = request.json
    if not data:
        return get_data_error_result(message="请求数据不能为空")

    doc_id = data.get("doc_id")
    position = data.get("position", 0)
    total_duration = data.get("total_duration", 0)

    if not doc_id:
        return get_data_error_result(message="缺少 doc_id")

    student_id = current_user.id

    try:
        # 查已有记录
        record = StudentVideoProgress.select().where(
            (StudentVideoProgress.student_id == student_id) &
            (StudentVideoProgress.doc_id == doc_id)
        ).first()

        if not record:
            # 首次上报，创建记录
            record = StudentVideoProgress.create(
                id=get_uuid(),
                create_time=int(datetime.now().timestamp()),
                create_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                update_time=int(datetime.now().timestamp()),
                update_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                student_id=student_id,
                doc_id=doc_id,
                watched_seconds=0,
                total_duration=total_duration,
                last_position=0,
                is_completed=False,
            )

        # 有效观看判定：delta > 0 且 ≤ 6 秒（允许 1 秒误差，避免暂停/网络抖动）
        delta = position - record.last_position
        if 0 < delta <= 6:
            record.watched_seconds += delta

        # 更新 last_position 和 total_duration
        record.last_position = position
        if total_duration > 0:
            record.total_duration = total_duration

        # 完成判定：有效观看 ≥ 总时长 × 90%
        if record.total_duration > 0 and record.watched_seconds >= record.total_duration * 0.9:
            record.is_completed = True

        # 更新时间戳
        record.update_time = int(datetime.now().timestamp())
        record.update_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        record.save()

        return get_json_result(data={
            "watched_seconds": record.watched_seconds,
            "is_completed": record.is_completed,
        })
    except Exception as e:
        return get_data_error_result(message=str(e))
```

- [ ] **Step 2: 验证 Python 语法**

```bash
python -c "import ast; ast.parse(open('api/apps/video_app.py').read()); print('syntax OK')"
```

- [ ] **Step 3: 提交**

```bash
git add api/apps/video_app.py
git commit -m "feat: add video progress tracking API endpoints

GET  /v1/video/progress/<doc_id>  — query watch progress
POST /v1/video/progress/report    — report playback position
Anti-skip: delta > 6s treated as scrubbing (not counted)
Completion: watched_seconds >= total_duration * 0.9"
```

---

### Task 3: 前端 — 进度上报 + 展示 + 续播

**Files:**
- Modify: `web/src/pages/learning/courseware-panel/index.tsx`
- Modify: `web/src/pages/learning/courseware-panel/index.less`

**Interfaces:**
- Consumes: `GET /v1/video/progress/<doc_id>` returns `{ watched_seconds, total_duration, last_position, is_completed }`
- Consumes: `POST /v1/video/progress/report` accepts `{ doc_id, position, total_duration }`
- Produces: 视频播放器下方进度条 + 完成标识，续播跳转到 last_position

- [ ] **Step 1: 在 CoursewarePanel 中新增进度相关的 state 和 hooks**

在 `courseware-panel/index.tsx` 中，在现有 state 声明之后添加：

```tsx
// Video progress tracking
const [videoProgress, setVideoProgress] = useState<{
  watched_seconds: number;
  total_duration: number;
  is_completed: boolean;
}>({ watched_seconds: 0, total_duration: 0, is_completed: false });
const [videoResumed, setVideoResumed] = useState(false);
const videoRef = useRef<HTMLVideoElement>(null);
const reportTimerRef = useRef<number | null>(null);
const lastPositionRef = useRef<number>(0);
```

- [ ] **Step 2: 添加进度查询和上报函数**

在 `CoursewarePanel` 组件中，添加以下函数：

```tsx
// Fetch video progress on mount for video docs
useEffect(() => {
  if (!isVideo || !selectedDocId) return;
  const fetchProgress = async () => {
    try {
      const res = await fetch(`/v1/video/progress/${selectedDocId}`);
      const data = await res.json();
      if (data?.code === 0 && data.data) {
        setVideoProgress(data.data);
        // Resume from last position if not completed
        if (data.data.last_position > 0 && !data.data.is_completed && videoRef.current) {
          videoRef.current.currentTime = data.data.last_position;
          setVideoResumed(true);
        }
      }
    } catch {
      // Silently fail — progress is non-critical
    }
  };
  fetchProgress();
}, [isVideo, selectedDocId]);

// Report video progress periodically
const startProgressReport = useCallback(() => {
  if (!selectedDocId) return;
  reportTimerRef.current = window.setInterval(() => {
    if (!videoRef.current || videoRef.current.paused) return;
    const pos = Math.floor(videoRef.current.currentTime);
    const dur = Math.floor(videoRef.current.duration || 0);
    // Only report if position actually changed
    if (pos === lastPositionRef.current) return;
    lastPositionRef.current = pos;

    fetch('/v1/video/progress/report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ doc_id: selectedDocId, position: pos, total_duration: dur }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data?.code === 0 && data.data) {
          setVideoProgress(data.data);
        }
      })
      .catch(() => {});
  }, 5000);
}, [selectedDocId]);

const stopProgressReport = useCallback(() => {
  if (reportTimerRef.current) {
    clearInterval(reportTimerRef.current);
    reportTimerRef.current = null;
  }
}, []);

// Cleanup timer on unmount
useEffect(() => {
  return () => stopProgressReport();
}, [stopProgressReport]);
```

- [ ] **Step 3: 修改视频渲染部分，加入进度展示和续播逻辑**

将现有的视频渲染代码（`isVideo` 分支）替换为：

```tsx
// Video document — show video player with progress tracking
if (isVideo) {
  const progressPercent = videoProgress.total_duration > 0
    ? Math.round((videoProgress.watched_seconds / videoProgress.total_duration) * 100)
    : 0;

  return (
    <div className={styles.videoContainer}>
      <video
        ref={videoRef}
        controls
        className={styles.videoPlayer}
        src={`/v1/document/get/${selectedDocId}`}
        style={{ width: '100%', maxHeight: '62vh' }}
        controlsList="nodownload"
        onPlay={startProgressReport}
        onPause={stopProgressReport}
        onEnded={stopProgressReport}
        onSeeked={() => {
          // Update lastPositionRef to avoid false delta on seek
          if (videoRef.current) {
            lastPositionRef.current = Math.floor(videoRef.current.currentTime);
          }
        }}
      >
        您的浏览器不支持视频播放
      </video>
      {/* Progress bar */}
      <div className={styles.progressBarContainer}>
        <div className={styles.progressBar}>
          <div
            className={styles.progressFill}
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        <span className={styles.progressText}>
          {videoProgress.is_completed
            ? '✓ 已完成'
            : `已观看 ${progressPercent}%`}
        </span>
      </div>
      {/* Resume toast */}
      {videoResumed && (
        <div className={styles.resumeToast}>
          已从上次位置继续播放
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: 添加进度条和大蒜 CSS**

在 `courseware-panel/index.less` 末尾添加：

```less
.progressBarContainer {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  flex-shrink: 0;
}

.progressBar {
  flex: 1;
  height: 6px;
  background-color: #e8e8e8;
  border-radius: 3px;
  overflow: hidden;
}

.progressFill {
  height: 100%;
  background-color: #52c41a;
  border-radius: 3px;
  transition: width 0.5s ease;
}

.progressText {
  font-size: 12px;
  color: #666;
  white-space: nowrap;
  min-width: 90px;
  text-align: right;
}

.resumeToast {
  position: absolute;
  top: 8px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  pointer-events: none;
  animation: fadeInOut 3s ease forwards;
}

@keyframes fadeInOut {
  0% { opacity: 0; }
  10% { opacity: 1; }
  80% { opacity: 1; }
  100% { opacity: 0; }
}
```

- [ ] **Step 5: 新增引用导入**

在 `courseware-panel/index.tsx` 的 import 区添加：

```tsx
import { useCallback, useEffect, useRef, useState } from 'react';
```

确认 `useCallback`, `useRef` 已经在 import 中（`useEffect`, `useState` 已有，`useRef` 已有，只需确认 `useCallback` 存在）。

- [ ] **Step 6: 提交**

```bash
git add web/src/pages/learning/courseware-panel/index.tsx web/src/pages/learning/courseware-panel/index.less
git commit -m "feat: add video watch progress tracking in learning page

- Auto-report playback position every 5s
- Anti-skip enforced server-side (delta > 6s rejected)
- Progress bar + completion checkmark display
- Resume from last position on revisit"
```

---

### Task 4: 端到端验证

- [ ] **Step 1: 确认 api 服务启动，表已自动创建**

```bash
# 启动 api 服务（如果未运行）
# 验证表存在
docker exec ragflow-mysql mysql -u root -pinfini_rag_flow rag_flow -e "DESCRIBE student_video_progress;"
```

- [ ] **Step 2: 测试 API — 查询进度（无记录）**

```bash
curl -s http://localhost:9380/v1/video/progress/<doc_id> \
  -H "Authorization: <token>" | python3 -m json.tool
```

预期：`{"code": 0, "data": {"watched_seconds": 0, "total_duration": 0, "last_position": 0, "is_completed": false}}`

- [ ] **Step 3: 测试 API — 上报进度（正常播放）**

```bash
# 模拟正常播放：position 从 0 → 5 → 10
curl -s -X POST http://localhost:9380/v1/video/progress/report \
  -H "Authorization: <token>" \
  -H "Content-Type: application/json" \
  -d '{"doc_id":"<doc_id>","position":5,"total_duration":600}'

curl -s -X POST http://localhost:9380/v1/video/progress/report \
  -H "Authorization: <token>" \
  -H "Content-Type: application/json" \
  -d '{"doc_id":"<doc_id>","position":10,"total_duration":600}'

# 查询验证
curl -s http://localhost:9380/v1/video/progress/<doc_id> \
  -H "Authorization: <token>"
```

预期：`watched_seconds = 10`

- [ ] **Step 4: 测试 API — 拖拽跳跃（不累加）**

```bash
# 模拟拖拽：position 从 10 → 100（delta=90 > 6）
curl -s -X POST http://localhost:9380/v1/video/progress/report \
  -H "Authorization: <token>" \
  -H "Content-Type: application/json" \
  -d '{"doc_id":"<doc_id>","position":100,"total_duration":600}'

# 查询验证
curl -s http://localhost:9380/v1/video/progress/<doc_id> \
  -H "Authorization: <token>"
```

预期：`watched_seconds 仍为 10`（拖拽不累加），`last_position` 更新为 100

- [ ] **Step 5: 前端验证**

在浏览器中：
1. 登录前台 → 助教中心 → 开始学习
2. 选择视频文档 → 播放
3. 观察进度条是否每 5 秒更新
4. 刷新页面 → 确认从上次位置续播
5. 拖拽到末尾 → 确认不被判定为完成
6. 正常播放到 90% → 确认显示 "✓ 已完成"

- [ ] **Step 6: 提交验证结果**

记录到会话中。
