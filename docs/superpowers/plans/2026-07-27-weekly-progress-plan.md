# 每周学习进度管理 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在管理后台新增「进度管理」模块，老师按班级创建每周文档任务，系统自动校验每个学生的完成状态。

**Architecture:** 管理后台新增 3 张 MySQL 表，后端新增 `services/progress/` 服务层（周进度 CRUD + 完成状态刷新引擎）和 `routes/progress/` 路由层（Flask Blueprint），前端新增 `pages/progress/index.vue` 页面（Vue 3 + Element Plus，两个 Tab）。

**Tech Stack:** Python 3 + Flask + mysql.connector (raw SQL), Vue 3 + TypeScript + Element Plus + axios

## Global Constraints

- 管理后台全部接口需 `@require_superuser` 装饰器
- 所有 ID 为 32 位 UUID hex 字符串（通过 `generate_uuid()` 生成）
- 时间字段使用 UTC+8（Asia/Shanghai）时区
- 服务层返回 `(True, data)` / `(False, error_string)` 元组
- 所有写操作必须校验班级归属（`class.tenant_id = current_user.user_id`）
- 路由响应格式：`{"code": 0/N, "data": ..., "message": "..."}`
- 前端 `request<T>` 泛型为 `ApiResponseData<T>`（全局声明）
- 文档数据范围链路：`class → class_dialog → dialog → dialog.kb_ids(JSON) → knowledgebase → document`

---

## 文件结构

```
新建:
management/server/services/progress/__init__.py
management/server/services/progress/service.py
management/server/routes/progress/__init__.py
management/server/routes/progress/routes.py
management/web/src/common/apis/progress/index.ts
management/web/src/common/apis/progress/type.ts
management/web/src/pages/progress/index.vue
management/web/src/common/assets/icons/progress.svg

修改:
api/db/db_models.py             — 新增 3 个 Peewee 模型
management/server/routes/__init__.py  — 注册 progress_bp
management/web/src/router/index.ts     — 新增 /progress 路由
```

---

### Task 1: 创建数据库表 + Peewee 模型

**Files:**
- DDL（通过 Docker MySQL 执行）
- Modify: `api/db/db_models.py` — 新增 3 个 Peewee 模型

**Produces:** 3 张 MySQL 表及 Peewee 模型类 `WeeklyProgress`, `WeeklyProgressDoc`, `StudentProgressStatus`

- [ ] **Step 1: 执行 DDL 创建 3 张表**

```bash
docker exec ragflow-mysql mysql -u root -pinfini_rag_flow rag_flow -e "
CREATE TABLE IF NOT EXISTS weekly_progress (
    id VARCHAR(32) PRIMARY KEY,
    class_id VARCHAR(32) NOT NULL,
    name VARCHAR(200) NOT NULL,
    week_start DATE NOT NULL,
    week_end DATE NOT NULL,
    status VARCHAR(1) DEFAULT '1',
    create_time BIGINT,
    create_date DATETIME,
    update_time BIGINT,
    update_date DATETIME,
    INDEX idx_class_id (class_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS weekly_progress_doc (
    id VARCHAR(32) PRIMARY KEY,
    progress_id VARCHAR(32) NOT NULL,
    doc_id VARCHAR(32) NOT NULL,
    quiz_threshold INT DEFAULT 0,
    create_time BIGINT,
    create_date DATETIME,
    update_time BIGINT,
    update_date DATETIME,
    UNIQUE KEY uk_progress_doc (progress_id, doc_id),
    INDEX idx_progress_id (progress_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS student_progress_status (
    id VARCHAR(32) PRIMARY KEY,
    progress_id VARCHAR(32) NOT NULL,
    doc_id VARCHAR(32) NOT NULL,
    student_id VARCHAR(32) NOT NULL,
    is_completed TINYINT(1) DEFAULT 0,
    completed_at DATETIME,
    video_completed TINYINT(1) DEFAULT 0,
    quiz_passed TINYINT(1) DEFAULT 0,
    has_notes TINYINT(1) DEFAULT 0,
    create_time BIGINT,
    create_date DATETIME,
    update_time BIGINT,
    update_date DATETIME,
    UNIQUE KEY uk_progress_doc_student (progress_id, doc_id, student_id),
    INDEX idx_progress_id (progress_id),
    INDEX idx_student_id (student_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"
```

- [ ] **Step 2: 验证表创建成功**

```bash
docker exec ragflow-mysql mysql -u root -pinfini_rag_flow rag_flow -e "SHOW CREATE TABLE weekly_progress\G"
docker exec ragflow-mysql mysql -u root -pinfini_rag_flow rag_flow -e "SHOW CREATE TABLE weekly_progress_doc\G"
docker exec ragflow-mysql mysql -u root -pinfini_rag_flow rag_flow -e "SHOW CREATE TABLE student_progress_status\G"
```

- [ ] **Step 3: 在 api/db/db_models.py 中添加 Peewee 模型**

在 `ExternalScoreRecord` 模型之后（约 line 1022）添加：

```python
class WeeklyProgress(DataBaseModel):
    id = CharField(max_length=32, primary_key=True)
    class_id = CharField(max_length=32, null=False, index=True)
    name = CharField(max_length=200, null=False)
    week_start = DateField(null=False)
    week_end = DateField(null=False)
    status = CharField(max_length=1, null=True, default="1")

    class Meta:
        db_table = "weekly_progress"


class WeeklyProgressDoc(DataBaseModel):
    id = CharField(max_length=32, primary_key=True)
    progress_id = CharField(max_length=32, null=False, index=True)
    doc_id = CharField(max_length=32, null=False, index=True)
    quiz_threshold = IntegerField(default=0)

    class Meta:
        db_table = "weekly_progress_doc"
        indexes = (
            (("progress_id", "doc_id"), True),
        )


class StudentProgressStatus(DataBaseModel):
    id = CharField(max_length=32, primary_key=True)
    progress_id = CharField(max_length=32, null=False, index=True)
    doc_id = CharField(max_length=32, null=False, index=True)
    student_id = CharField(max_length=32, null=False, index=True)
    is_completed = BooleanField(default=False)
    completed_at = DateTimeField(null=True)
    video_completed = BooleanField(default=False)
    quiz_passed = BooleanField(default=False)
    has_notes = BooleanField(default=False)

    class Meta:
        db_table = "student_progress_status"
        indexes = (
            (("progress_id", "doc_id", "student_id"), True),
        )
```

- [ ] **Step 4: 提交**

```bash
git add api/db/db_models.py
git commit -m "feat: add weekly progress tracking models

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: 周进度服务层

**Files:**
- Create: `management/server/services/progress/__init__.py`
- Create: `management/server/services/progress/service.py`

**Produces:**
- `get_weekly_progress_list(class_id) -> list`
- `create_weekly_progress(class_id, data) -> Tuple[bool, str]`
- `update_weekly_progress(progress_id, data) -> Tuple[bool, str]`
- `delete_weekly_progress(progress_id) -> Tuple[bool, str]`
- `get_class_documents(class_id) -> list` — 含 name, type, has_quiz 标记
- `get_progress_status(progress_id) -> Tuple[bool, dict]` — 触发刷新+返回结果
- `refresh_progress_status(progress_id) -> Tuple[bool, str]`

- [ ] **Step 1: 创建 service 文件骨架**

创建 `management/server/services/progress/__init__.py`（空文件）。

创建 `management/server/services/progress/service.py`：

```python
import json
import mysql.connector
import pytz
from datetime import datetime
from utils import generate_uuid
from database import DB_CONFIG
from auth import get_current_user


def _get_utc8_time():
    utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
    target_tz = pytz.timezone('Asia/Shanghai')
    local_dt = utc_now.astimezone(target_tz)
    return int(local_dt.timestamp() * 1000), local_dt.strftime("%Y-%m-%d %H:%M:%S")
```

- [ ] **Step 2: 实现周进度 CRUD**

```python
def get_weekly_progress_list(class_id):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, class_id, name, week_start, week_end, status, create_date "
            "FROM weekly_progress WHERE class_id = %s ORDER BY week_start DESC",
            (class_id,)
        )
        rows = cursor.fetchall()
        # 转换 date 类型为字符串
        for r in rows:
            if isinstance(r.get("week_start"), datetime):
                r["week_start"] = r["week_start"].strftime("%Y-%m-%d")
            if isinstance(r.get("week_end"), datetime):
                r["week_end"] = r["week_end"].strftime("%Y-%m-%d")
        cursor.close()
        conn.close()
        return rows
    except mysql.connector.Error as err:
        print(f"获取周进度列表失败: {err}")
        return []


def create_weekly_progress(class_id, data):
    try:
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"
        user_id = current_user["user_id"]

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        check_query = "SELECT id FROM class WHERE id = %s AND tenant_id = %s"
        cursor.execute(check_query, (class_id, user_id))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return False, "班级不存在或无权操作"

        name = data.get("name", "").strip()
        if not name:
            cursor.close()
            conn.close()
            return False, "名称不能为空"

        week_start = data.get("week_start", "")
        week_end = data.get("week_end", "")
        doc_ids = data.get("doc_ids", [])
        quiz_thresholds = data.get("quiz_thresholds", {})

        if not doc_ids:
            cursor.close()
            conn.close()
            return False, "至少选择1个文档"

        ct_ms, ct_date = _get_utc8_time()
        progress_id = generate_uuid()

        cursor.execute(
            "INSERT INTO weekly_progress (id, class_id, name, week_start, week_end, status, create_time, create_date, update_time, update_date) "
            "VALUES (%s, %s, %s, %s, %s, '1', %s, %s, %s, %s)",
            (progress_id, class_id, name, week_start, week_end, ct_ms, ct_date, ct_ms, ct_date)
        )

        for doc_id in doc_ids:
            threshold = int(quiz_thresholds.get(doc_id, 0))
            doc_link_id = generate_uuid()
            cursor.execute(
                "INSERT INTO weekly_progress_doc (id, progress_id, doc_id, quiz_threshold, create_time, create_date, update_time, update_date) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (doc_link_id, progress_id, doc_id, threshold, ct_ms, ct_date, ct_ms, ct_date)
            )

        conn.commit()
        cursor.close()
        conn.close()
        return True, progress_id

    except mysql.connector.Error as err:
        print(f"创建周进度失败: {err}")
        return False, str(err)


def update_weekly_progress(progress_id, data):
    try:
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"
        user_id = current_user["user_id"]

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        check_query = """
            SELECT wp.id FROM weekly_progress wp
            JOIN class c ON wp.class_id = c.id
            WHERE wp.id = %s AND c.tenant_id = %s
        """
        cursor.execute(check_query, (progress_id, user_id))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return False, "进度不存在或无权操作"

        name = data.get("name", "").strip()
        week_start = data.get("week_start", "")
        week_end = data.get("week_end", "")
        doc_ids = data.get("doc_ids", [])
        quiz_thresholds = data.get("quiz_thresholds", {})

        if not doc_ids:
            cursor.close()
            conn.close()
            return False, "至少选择1个文档"

        ct_ms, ct_date = _get_utc8_time()

        cursor.execute(
            "UPDATE weekly_progress SET name=%s, week_start=%s, week_end=%s, update_time=%s, update_date=%s WHERE id=%s",
            (name, week_start, week_end, ct_ms, ct_date, progress_id)
        )

        # 重建文档关联：删旧 + 插新
        cursor.execute("DELETE FROM weekly_progress_doc WHERE progress_id = %s", (progress_id,))
        # 级联删除旧的完成状态
        cursor.execute("DELETE FROM student_progress_status WHERE progress_id = %s", (progress_id,))

        for doc_id in doc_ids:
            threshold = int(quiz_thresholds.get(doc_id, 0))
            doc_link_id = generate_uuid()
            cursor.execute(
                "INSERT INTO weekly_progress_doc (id, progress_id, doc_id, quiz_threshold, create_time, create_date, update_time, update_date) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (doc_link_id, progress_id, doc_id, threshold, ct_ms, ct_date, ct_ms, ct_date)
            )

        conn.commit()
        cursor.close()
        conn.close()
        return True, "修改成功"

    except mysql.connector.Error as err:
        print(f"修改周进度失败: {err}")
        return False, str(err)


def delete_weekly_progress(progress_id):
    try:
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"
        user_id = current_user["user_id"]

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        check_query = """
            SELECT wp.id FROM weekly_progress wp
            JOIN class c ON wp.class_id = c.id
            WHERE wp.id = %s AND c.tenant_id = %s
        """
        cursor.execute(check_query, (progress_id, user_id))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return False, "进度不存在或无权操作"

        cursor.execute("DELETE FROM student_progress_status WHERE progress_id = %s", (progress_id,))
        cursor.execute("DELETE FROM weekly_progress_doc WHERE progress_id = %s", (progress_id,))
        cursor.execute("DELETE FROM weekly_progress WHERE id = %s", (progress_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "删除成功"

    except mysql.connector.Error as err:
        print(f"删除周进度失败: {err}")
        return False, str(err)
```

- [ ] **Step 3: 实现文档列表查询**

```python
def get_class_documents(class_id):
    """获取班级关联的所有文档（含名称、类型、是否有测验）"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 复用评分系统的数据链路：class → class_dialog → dialog → kb_ids → document
        cursor.execute("SELECT dialog_id FROM class_dialog WHERE class_id = %s", (class_id,))
        dialog_rows = cursor.fetchall()
        dialog_ids = [r["dialog_id"] for r in dialog_rows]

        if not dialog_ids:
            cursor.close()
            conn.close()
            return []

        placeholders = ", ".join(["%s"] * len(dialog_ids))
        cursor.execute(
            f"SELECT id, kb_ids FROM dialog WHERE id IN ({placeholders})",
            dialog_ids
        )
        kb_id_set = set()
        for row in cursor.fetchall():
            kb_ids = row.get("kb_ids")
            if isinstance(kb_ids, str):
                try:
                    kb_ids = json.loads(kb_ids)
                except (json.JSONDecodeError, TypeError):
                    kb_ids = []
            if isinstance(kb_ids, list):
                for kb_id in kb_ids:
                    if kb_id:
                        kb_id_set.add(kb_id)

        if not kb_id_set:
            cursor.close()
            conn.close()
            return []

        kb_placeholders = ", ".join(["%s"] * len(kb_id_set))
        cursor.execute(
            f"SELECT id, name, type FROM document WHERE kb_id IN ({kb_placeholders}) AND status = '1'",
            list(kb_id_set)
        )
        docs = cursor.fetchall()

        # 查询哪些文档有测验
        doc_ids = [d["id"] for d in docs]
        has_quiz_set = set()
        if doc_ids:
            doc_placeholders = ", ".join(["%s"] * len(doc_ids))
            cursor.execute(
                f"SELECT DISTINCT doc_id FROM document_generation WHERE doc_id IN ({doc_placeholders}) AND generation_type = 'quiz'",
                doc_ids
            )
            for row in cursor.fetchall():
                has_quiz_set.add(row["doc_id"])

        for d in docs:
            d["has_quiz"] = d["id"] in has_quiz_set

        cursor.close()
        conn.close()
        return docs

    except mysql.connector.Error as err:
        print(f"获取班级文档失败: {err}")
        return []
```

- [ ] **Step 4: 实现完成状态刷新和查询**

```python
def _get_class_students_for_progress(class_id):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT u.id, u.nickname, u.email
        FROM user u JOIN user_class uc ON u.id = uc.user_id
        WHERE uc.class_id = %s AND uc.role = 'student' AND uc.status = '1'
    """, (class_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def refresh_progress_status(progress_id):
    """刷新指定进度的所有学生完成状态"""
    try:
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"
        user_id = current_user["user_id"]

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 校验归属
        check_query = """
            SELECT wp.id, wp.class_id FROM weekly_progress wp
            JOIN class c ON wp.class_id = c.id
            WHERE wp.id = %s AND c.tenant_id = %s
        """
        cursor.execute(check_query, (progress_id, user_id))
        progress_row = cursor.fetchone()
        if not progress_row:
            cursor.close()
            conn.close()
            return False, "进度不存在或无权操作"

        class_id = progress_row["class_id"]

        # 获取进度的文档列表
        cursor.execute(
            "SELECT wpd.doc_id, wpd.quiz_threshold, d.type "
            "FROM weekly_progress_doc wpd JOIN document d ON wpd.doc_id = d.id "
            "WHERE wpd.progress_id = %s",
            (progress_id,)
        )
        progress_docs = cursor.fetchall()

        # 获取该班级学生
        students = _get_class_students_for_progress(class_id)

        # 判断哪些文档有测验
        doc_ids = [d["doc_id"] for d in progress_docs]
        has_quiz_docs = set()
        if doc_ids:
            placeholders = ", ".join(["%s"] * len(doc_ids))
            cursor.execute(
                f"SELECT DISTINCT doc_id FROM document_generation WHERE doc_id IN ({placeholders}) AND generation_type = 'quiz'",
                doc_ids
            )
            for row in cursor.fetchall():
                has_quiz_docs.add(row["doc_id"])

        ct_ms, ct_date = _get_utc8_time()
        now_dt = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(pytz.timezone('Asia/Shanghai'))
        now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

        for student in students:
            sid = student["id"]

            for pdoc in progress_docs:
                did = pdoc["doc_id"]
                threshold = pdoc["quiz_threshold"]
                doc_type = pdoc["type"]

                video_completed = False
                quiz_passed = False
                has_notes = False
                is_completed = False

                # 视频文档
                if doc_type == "video":
                    cursor.execute(
                        "SELECT is_completed FROM student_video_progress WHERE student_id = %s AND doc_id = %s",
                        (sid, did)
                    )
                    svp = cursor.fetchone()
                    video_completed = bool(svp and svp["is_completed"])
                    is_completed = video_completed

                # 有测验的文档：测验达标即完成
                elif did in has_quiz_docs:
                    cursor.execute(
                        "SELECT COUNT(*) as cnt, SUM(is_correct) as correct FROM student_quiz_result WHERE student_id = %s AND doc_id = %s",
                        (sid, did)
                    )
                    qr = cursor.fetchone()
                    total = int(qr["cnt"] or 0)
                    correct = int(qr["correct"] or 0)
                    rate = (correct / total * 100) if total > 0 else 0
                    quiz_passed = (total > 0 and rate >= threshold)

                    cursor.execute(
                        "SELECT COUNT(*) as cnt FROM student_note WHERE student_id = %s AND doc_id = %s",
                        (sid, did)
                    )
                    has_notes = int((cursor.fetchone() or {}).get("cnt", 0)) > 0

                    is_completed = quiz_passed

                # 无测验文档（PPT/PDF）：有笔记即完成
                else:
                    cursor.execute(
                        "SELECT COUNT(*) as cnt FROM student_note WHERE student_id = %s AND doc_id = %s",
                        (sid, did)
                    )
                    has_notes = int((cursor.fetchone() or {}).get("cnt", 0)) > 0
                    is_completed = has_notes

                # Upsert 状态
                cursor.execute(
                    "SELECT id, is_completed FROM student_progress_status WHERE progress_id = %s AND doc_id = %s AND student_id = %s",
                    (progress_id, did, sid)
                )
                existing = cursor.fetchone()

                if existing:
                    prev_completed = existing["is_completed"]
                    new_completed_at = existing.get("completed_at")
                    if is_completed and not prev_completed:
                        new_completed_at = now_str
                    elif not is_completed:
                        new_completed_at = None

                    cursor.execute(
                        "UPDATE student_progress_status SET is_completed=%s, completed_at=%s, "
                        "video_completed=%s, quiz_passed=%s, has_notes=%s, update_time=%s, update_date=%s WHERE id=%s",
                        (is_completed, new_completed_at, video_completed, quiz_passed, has_notes, ct_ms, ct_date, existing["id"])
                    )
                else:
                    new_id = generate_uuid()
                    new_completed_at = now_str if is_completed else None
                    cursor.execute(
                        "INSERT INTO student_progress_status (id, progress_id, doc_id, student_id, is_completed, completed_at, "
                        "video_completed, quiz_passed, has_notes, create_time, create_date, update_time, update_date) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (new_id, progress_id, did, sid, is_completed, new_completed_at,
                         video_completed, quiz_passed, has_notes, ct_ms, ct_date, ct_ms, ct_date)
                    )

        conn.commit()
        cursor.close()
        conn.close()
        return True, "刷新完成"

    except mysql.connector.Error as err:
        print(f"刷新进度状态失败: {err}")
        return False, str(err)


def get_progress_status(progress_id):
    """获取进度完成情况（先刷新再返回）"""
    success, msg = refresh_progress_status(progress_id)
    if not success:
        return False, msg

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 进度基本信息
        cursor.execute("""
            SELECT wp.id, wp.class_id, wp.name, wp.week_start, wp.week_end, wp.status, c.name as class_name
            FROM weekly_progress wp JOIN class c ON wp.class_id = c.id
            WHERE wp.id = %s
        """, (progress_id,))
        progress = cursor.fetchone()
        if not progress:
            cursor.close()
            conn.close()
            return False, "进度不存在"

        if isinstance(progress.get("week_start"), datetime):
            progress["week_start"] = progress["week_start"].strftime("%Y-%m-%d")
        if isinstance(progress.get("week_end"), datetime):
            progress["week_end"] = progress["week_end"].strftime("%Y-%m-%d")

        # 文档列表
        cursor.execute(
            "SELECT wpd.doc_id, wpd.quiz_threshold, d.name as doc_name, d.type as doc_type "
            "FROM weekly_progress_doc wpd JOIN document d ON wpd.doc_id = d.id "
            "WHERE wpd.progress_id = %s",
            (progress_id,)
        )
        docs = cursor.fetchall()

        # 学生完成状态
        cursor.execute("""
            SELECT sps.student_id, u.nickname as student_name, sps.doc_id,
                   sps.is_completed, sps.video_completed, sps.quiz_passed, sps.has_notes
            FROM student_progress_status sps
            JOIN user u ON sps.student_id = u.id
            WHERE sps.progress_id = %s
            ORDER BY u.nickname
        """, (progress_id,))
        status_rows = cursor.fetchall()

        cursor.close()
        conn.close()

        # 汇总
        total_docs = len(docs)
        student_map = {}
        for row in status_rows:
            sid = row["student_id"]
            if sid not in student_map:
                student_map[sid] = {
                    "student_id": sid,
                    "student_name": row["student_name"],
                    "doc_statuses": [],
                    "total_completed": 0,
                    "total_docs": total_docs,
                }
            student_map[sid]["doc_statuses"].append({
                "doc_id": row["doc_id"],
                "is_completed": bool(row["is_completed"]),
                "video_completed": bool(row["video_completed"]),
                "quiz_passed": bool(row["quiz_passed"]),
                "has_notes": bool(row["has_notes"]),
            })
            if row["is_completed"]:
                student_map[sid]["total_completed"] += 1

        students_list = list(student_map.values())
        for s in students_list:
            s["is_all_completed"] = s["total_completed"] == total_docs

        total_students = len(students_list)
        completed_count = sum(1 for s in students_list if s["is_all_completed"])

        summary = {
            "total_students": total_students,
            "completed_count": completed_count,
            "incomplete_count": total_students - completed_count,
            "completion_rate": round(completed_count / total_students * 100, 1) if total_students > 0 else 0.0,
        }

        return True, {
            "progress": {**progress, "docs": docs},
            "summary": summary,
            "students": students_list,
        }

    except mysql.connector.Error as err:
        print(f"获取进度状态失败: {err}")
        return False, str(err)
```

- [ ] **Step 5: 提交**

```bash
git add management/server/services/progress/
git commit -m "feat: add weekly progress CRUD and completion refresh service

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: API 路由 + Blueprint 注册

**Files:**
- Create: `management/server/routes/progress/__init__.py`
- Create: `management/server/routes/progress/routes.py`
- Modify: `management/server/routes/__init__.py`

**Consumes:** Task 2 的所有 service 函数

- [ ] **Step 1: 创建 routes.py**

```python
from flask import jsonify, request
from services.progress.service import (
    get_weekly_progress_list,
    create_weekly_progress,
    update_weekly_progress,
    delete_weekly_progress,
    get_class_documents,
    get_progress_status,
    refresh_progress_status,
)
from routes import progress_bp
from auth import require_superuser


@progress_bp.route('/<string:class_id>', methods=['GET'])
@require_superuser
def list_progress(class_id):
    try:
        data = get_weekly_progress_list(class_id)
        return jsonify({"code": 0, "data": data, "message": "获取周进度列表成功"})
    except Exception as e:
        return jsonify({"code": 500, "message": f"获取周进度列表失败: {str(e)}"}), 500


@progress_bp.route('/<string:class_id>', methods=['POST'])
@require_superuser
def create_progress(class_id):
    try:
        data = request.json
        if not data:
            return jsonify({"code": 400, "message": "请求体不能为空"}), 400
        success, result = create_weekly_progress(class_id, data)
        if success:
            return jsonify({"code": 0, "data": {"id": result}, "message": "创建周进度成功"})
        return jsonify({"code": 400, "message": result}), 400
    except Exception as e:
        return jsonify({"code": 500, "message": f"创建周进度失败: {str(e)}"}), 500


@progress_bp.route('/detail/<string:progress_id>', methods=['PUT'])
@require_superuser
def edit_progress(progress_id):
    try:
        data = request.json
        if not data:
            return jsonify({"code": 400, "message": "请求体不能为空"}), 400
        success, result = update_weekly_progress(progress_id, data)
        if success:
            return jsonify({"code": 0, "data": None, "message": result})
        return jsonify({"code": 400, "message": result}), 400
    except Exception as e:
        return jsonify({"code": 500, "message": f"修改周进度失败: {str(e)}"}), 500


@progress_bp.route('/detail/<string:progress_id>', methods=['DELETE'])
@require_superuser
def remove_progress(progress_id):
    try:
        success, result = delete_weekly_progress(progress_id)
        if success:
            return jsonify({"code": 0, "data": None, "message": result})
        return jsonify({"code": 400, "message": result}), 400
    except Exception as e:
        return jsonify({"code": 500, "message": f"删除周进度失败: {str(e)}"}), 500


@progress_bp.route('/docs/<string:class_id>', methods=['GET'])
@require_superuser
def list_docs(class_id):
    try:
        docs = get_class_documents(class_id)
        return jsonify({"code": 0, "data": docs, "message": "获取文档列表成功"})
    except Exception as e:
        return jsonify({"code": 500, "message": f"获取文档列表失败: {str(e)}"}), 500


@progress_bp.route('/status/<string:progress_id>', methods=['GET'])
@require_superuser
def get_status(progress_id):
    try:
        success, result = get_progress_status(progress_id)
        if success:
            return jsonify({"code": 0, "data": result, "message": "获取完成状态成功"})
        return jsonify({"code": 400, "message": result}), 400
    except Exception as e:
        return jsonify({"code": 500, "message": f"获取完成状态失败: {str(e)}"}), 500


@progress_bp.route('/refresh/<string:progress_id>', methods=['POST'])
@require_superuser
def refresh_status(progress_id):
    try:
        success, result = refresh_progress_status(progress_id)
        if success:
            return jsonify({"code": 0, "data": None, "message": result})
        return jsonify({"code": 400, "message": result}), 400
    except Exception as e:
        return jsonify({"code": 500, "message": f"刷新状态失败: {str(e)}"}), 500
```

- [ ] **Step 2: 注册 Blueprint**

在 `management/server/routes/__init__.py` 中：

在 Blueprint 定义区域（`scoring_bp` 之后）添加：
```python
progress_bp = Blueprint('progress', __name__, url_prefix='/api/v1/progress')
```

在 import 区域添加：
```python
from .progress.routes import *
```

在 `register_routes` 函数中添加：
```python
app.register_blueprint(progress_bp)
```

- [ ] **Step 3: 提交**

```bash
git add management/server/routes/progress/ management/server/routes/__init__.py
git commit -m "feat: add weekly progress API routes with blueprint registration

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: 前端 API 客户端

**Files:**
- Create: `management/web/src/common/apis/progress/index.ts`
- Create: `management/web/src/common/apis/progress/type.ts`

- [ ] **Step 1: 创建 type.ts**

```ts
export interface WeeklyProgressItem {
  id: string
  class_id: string
  name: string
  week_start: string
  week_end: string
  status: string
  create_date?: string
}

export interface CreateProgressData {
  name: string
  week_start: string
  week_end: string
  doc_ids: string[]
  quiz_thresholds: Record<string, number>
}

export interface ClassDocument {
  id: string
  name: string
  type: string
  has_quiz: boolean
}

export interface ProgressDocInfo {
  doc_id: string
  doc_name: string
  doc_type: string
  quiz_threshold: number
}

export interface DocStatus {
  doc_id: string
  is_completed: boolean
  video_completed: boolean
  quiz_passed: boolean
  has_notes: boolean
}

export interface StudentProgressStatus {
  student_id: string
  student_name: string
  doc_statuses: DocStatus[]
  total_completed: number
  total_docs: number
  is_all_completed: boolean
}

export interface ProgressSummary {
  total_students: number
  completed_count: number
  incomplete_count: number
  completion_rate: number
}

export interface ProgressStatusResult {
  progress: {
    id: string
    class_id: string
    class_name?: string
    name: string
    week_start: string
    week_end: string
    status: string
    docs: ProgressDocInfo[]
  }
  summary: ProgressSummary
  students: StudentProgressStatus[]
}
```

- [ ] **Step 2: 创建 index.ts**

```ts
import type {
  ClassDocument,
  CreateProgressData,
  ProgressStatusResult,
  WeeklyProgressItem
} from "./type"
import { request } from "@/http/axios"

export function getWeeklyProgressListApi(classId: string) {
  return request<WeeklyProgressItem[]>({
    url: `api/v1/progress/${classId}`,
    method: "get"
  })
}

export function createWeeklyProgressApi(classId: string, data: CreateProgressData) {
  return request<{ id: string }>({
    url: `api/v1/progress/${classId}`,
    method: "post",
    data
  })
}

export function updateWeeklyProgressApi(progressId: string, data: CreateProgressData) {
  return request({
    url: `api/v1/progress/detail/${progressId}`,
    method: "put",
    data
  })
}

export function deleteWeeklyProgressApi(progressId: string) {
  return request({
    url: `api/v1/progress/detail/${progressId}`,
    method: "delete"
  })
}

export function getClassDocumentsApi(classId: string) {
  return request<ClassDocument[]>({
    url: `api/v1/progress/docs/${classId}`,
    method: "get"
  })
}

export function getProgressStatusApi(progressId: string) {
  return request<ProgressStatusResult>({
    url: `api/v1/progress/status/${progressId}`,
    method: "get"
  })
}

export function refreshProgressStatusApi(progressId: string) {
  return request({
    url: `api/v1/progress/refresh/${progressId}`,
    method: "post"
  })
}
```

- [ ] **Step 3: 提交**

```bash
git add management/web/src/common/apis/progress/
git commit -m "feat: add progress tracking API client with TypeScript types

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: 前端页面 + 路由注册

**Files:**
- Create: `management/web/src/pages/progress/index.vue`
- Create: `management/web/src/common/assets/icons/progress.svg`
- Modify: `management/web/src/router/index.ts`

- [ ] **Step 1: 创建 SVG 图标**

创建 `management/web/src/common/assets/icons/progress.svg`：

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
  <line x1="16" y1="2" x2="16" y2="6" />
  <line x1="8" y1="2" x2="8" y2="6" />
  <line x1="3" y1="10" x2="21" y2="10" />
  <path d="M9 16l2 2 4-4" />
</svg>
```

- [ ] **Step 2: 创建 Vue 页面**

创建 `management/web/src/pages/progress/index.vue`：

```vue
<script lang="ts" setup>
import type { ClassDocument, CreateProgressData, WeeklyProgressItem, ProgressStatusResult } from "@@/apis/progress/type"
import type { FormInstance } from "element-plus"
import {
  getWeeklyProgressListApi, createWeeklyProgressApi, updateWeeklyProgressApi,
  deleteWeeklyProgressApi, getClassDocumentsApi, getProgressStatusApi
} from "@@/apis/progress"
import { getTableDataApi } from "@@/apis/teams"
import { ElMessage, ElMessageBox } from "element-plus"
import { Calendar, CircleCheck, Clock, Delete, Edit, Plus, RefreshRight, Search, View } from "@element-plus/icons-vue"
import { onMounted, reactive, ref, watch } from "vue"

defineOptions({ name: "ProgressManagement" })

const loading = ref(false)
const activeTab = ref("list")

// ============ 班级选择 ============
interface ClassOption { id: string; name: string }
const classOptions = ref<ClassOption[]>([])
const selectedClassId = ref("")

function loadClasses() {
  getTableDataApi({ currentPage: 1, size: 1000 }).then(({ data }) => {
    classOptions.value = data.list.map((c: any) => ({ id: c.id, name: c.name }))
  })
}
onMounted(() => loadClasses())

// ============ Tab 1: 进度列表 ============
const progressList = ref<WeeklyProgressItem[]>([])

function loadProgressList() {
  if (!selectedClassId.value) return
  loading.value = true
  getWeeklyProgressListApi(selectedClassId.value).then(({ data }) => {
    progressList.value = data || []
  }).finally(() => loading.value = false)
}
watch(selectedClassId, () => { if (activeTab.value === "list") loadProgressList() })

// 新建/编辑弹窗
const dialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref("")
const formRef = ref<FormInstance | null>(null)
const formData = reactive<CreateProgressData>({ name: "", week_start: "", week_end: "", doc_ids: [], quiz_thresholds: {} })

// 文档列表
const availableDocs = ref<ClassDocument[]>([])
const docSelection = reactive<Record<string, boolean>>({})
const docThresholds = reactive<Record<string, number>>({})

function openCreate() {
  isEditing.value = false
  editingId.value = ""
  formData.name = ""
  formData.week_start = ""
  formData.week_end = ""
  formData.doc_ids = []
  formData.quiz_thresholds = {}
  // 重置选择
  availableDocs.value.forEach(d => { docSelection[d.id] = false; docThresholds[d.id] = 0 })
  dialogVisible.value = true
  if (selectedClassId.value) loadDocs()
}

function openEdit(row: WeeklyProgressItem) {
  isEditing.value = true
  editingId.value = row.id
  formData.name = row.name
  formData.week_start = row.week_start
  formData.week_end = row.week_end
  dialogVisible.value = true
  loadDocs()
  // 等文档数据加载后再设置选中状态——这里简化处理，从后端获取已有数据
  getProgressStatusApi(row.id).then(({ data: statusData }) => {
    const pDocs = statusData.progress.docs
    availableDocs.value.forEach(d => { docSelection[d.id] = false; docThresholds[d.id] = 0 })
    pDocs.forEach((pd: any) => {
      docSelection[pd.doc_id] = true
      docThresholds[pd.doc_id] = pd.quiz_threshold
    })
  })
}

function loadDocs() {
  if (!selectedClassId.value) return
  getClassDocumentsApi(selectedClassId.value).then(({ data }) => {
    availableDocs.value = data || []
    availableDocs.value.forEach(d => {
      if (!(d.id in docSelection)) { docSelection[d.id] = false; docThresholds[d.id] = 0 }
    })
  })
}

function buildFormFromSelection() {
  formData.doc_ids = []
  formData.quiz_thresholds = {}
  availableDocs.value.forEach(d => {
    if (docSelection[d.id]) {
      formData.doc_ids.push(d.id)
      formData.quiz_thresholds[d.id] = d.has_quiz ? docThresholds[d.id] : 0
    }
  })
}

function handleSave() {
  if (!formData.name.trim()) { ElMessage.warning("请输入名称"); return }
  if (!formData.week_start || !formData.week_end) { ElMessage.warning("请选择时间范围"); return }

  buildFormFromSelection()
  if (formData.doc_ids.length === 0) { ElMessage.warning("至少选择1个文档"); return }

  loading.value = true
  const api = isEditing.value
    ? updateWeeklyProgressApi(editingId.value, { ...formData })
    : createWeeklyProgressApi(selectedClassId.value, { ...formData })

  api.then(() => {
    ElMessage.success(isEditing.value ? "修改成功" : "创建成功")
    dialogVisible.value = false
    loadProgressList()
  }).finally(() => loading.value = false)
}

function handleDelete(row: WeeklyProgressItem) {
  ElMessageBox.confirm(`确认删除「${row.name}」？`, "提示", {
    confirmButtonText: "确定", cancelButtonText: "取消", type: "warning"
  }).then(() => {
    deleteWeeklyProgressApi(row.id).then(() => { ElMessage.success("删除成功"); loadProgressList() })
  })
}

// ============ Tab 2: 完成情况 ============
const progressOptions = ref<WeeklyProgressItem[]>([])
const selectedProgressId = ref("")
const statusResult = ref<ProgressStatusResult | null>(null)
const statusFilter = ref("all")  // all | completed | incomplete

function loadProgressOptions() {
  if (!selectedClassId.value) return
  getWeeklyProgressListApi(selectedClassId.value).then(({ data }) => {
    progressOptions.value = data || []
  })
}
watch(selectedClassId, () => { if (activeTab.value === "status") loadProgressOptions() })

function loadStatus() {
  if (!selectedProgressId.value) { statusResult.value = null; return }
  loading.value = true
  getProgressStatusApi(selectedProgressId.value).then(({ data }) => {
    statusResult.value = data
  }).finally(() => loading.value = false)
}

const filteredStudents = ref<any[]>([])
watch([statusResult, statusFilter], () => {
  if (!statusResult.value) { filteredStudents.value = []; return }
  const all = statusResult.value.students
  if (statusFilter.value === "completed") filteredStudents.value = all.filter(s => s.is_all_completed)
  else if (statusFilter.value === "incomplete") filteredStudents.value = all.filter(s => !s.is_all_completed)
  else filteredStudents.value = all
}, { deep: true })

function getDocTypeTag(docType: string) {
  return docType === "video" ? "success" : "primary"
}

function getDocStatus(student: any, docId: string) {
  return student.doc_statuses?.find((d: any) => d.doc_id === docId)
}
</script>

<template>
  <div class="app-container">
    <!-- 班级选择器 -->
    <el-card shadow="never" class="class-selector-card">
      <div class="class-selector-row">
        <span class="selector-label">班级：</span>
        <el-select v-model="selectedClassId" placeholder="请选择班级" style="width: 280px" clearable>
          <el-option v-for="c in classOptions" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
      </div>
    </el-card>

    <el-card v-loading="loading" shadow="never" class="main-card">
      <el-tabs v-model="activeTab" @tab-change="(tab: string) => { if (tab === 'list') loadProgressList(); if (tab === 'status') loadProgressOptions() }">
        <!-- Tab 1: 进度列表 -->
        <el-tab-pane label="进度列表" name="list">
          <div v-if="!selectedClassId" class="empty-hint">请先选择班级</div>
          <template v-else>
            <div style="margin-bottom: 16px">
              <el-button type="primary" :icon="Plus" @click="openCreate">新建周进度</el-button>
            </div>
            <el-table :data="progressList" border stripe size="small">
              <el-table-column prop="name" label="名称" min-width="160" />
              <el-table-column label="时间范围" min-width="180">
                <template #default="scope">
                  {{ scope.row.week_start }} ~ {{ scope.row.week_end }}
                </template>
              </el-table-column>
              <el-table-column prop="status" label="状态" width="80" align="center">
                <template #default="scope">
                  <el-tag :type="scope.row.status === '1' ? 'success' : 'info'" size="small">
                    {{ scope.row.status === '1' ? '进行中' : '已结束' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="200" align="center">
                <template #default="scope">
                  <el-button type="primary" text size="small" :icon="View" @click="selectedProgressId = scope.row.id; activeTab = 'status'; loadStatus()">查看</el-button>
                  <el-button type="success" text size="small" :icon="Edit" @click="openEdit(scope.row)">编辑</el-button>
                  <el-button type="danger" text size="small" :icon="Delete" @click="handleDelete(scope.row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </template>
        </el-tab-pane>

        <!-- Tab 2: 完成情况 -->
        <el-tab-pane label="完成情况" name="status">
          <div v-if="!selectedClassId" class="empty-hint">请先选择班级</div>
          <template v-else>
            <div style="margin-bottom: 16px; display: flex; gap: 12px; align-items: center">
              <span style="font-weight: 500">选择进度：</span>
              <el-select v-model="selectedProgressId" placeholder="请选择周进度" style="width: 300px" @change="loadStatus">
                <el-option v-for="p in progressOptions" :key="p.id" :label="`${p.name} (${p.week_start} ~ ${p.week_end})`" :value="p.id" />
              </el-select>
            </div>

            <template v-if="statusResult">
              <!-- 概览卡片 -->
              <el-row :gutter="16" style="margin-bottom: 20px">
                <el-col :span="6">
                  <el-statistic title="学生总数" :value="statusResult.summary.total_students" />
                </el-col>
                <el-col :span="6">
                  <el-statistic title="已完成" :value="statusResult.summary.completed_count">
                    <template #suffix><span style="color: #67c23a">/ {{ statusResult.summary.total_students }}</span></template>
                  </el-statistic>
                </el-col>
                <el-col :span="6">
                  <el-statistic title="未完成" :value="statusResult.summary.incomplete_count">
                    <template #suffix>
                      <span :style="{ color: statusResult.summary.incomplete_count > 0 ? '#f56c6c' : '#67c23a' }">
                        ⚠ {{ statusResult.summary.incomplete_count }} 人
                      </span>
                    </template>
                  </el-statistic>
                </el-col>
                <el-col :span="6">
                  <el-statistic title="完成率" :value="statusResult.summary.completion_rate">
                    <template #suffix><span>%</span></template>
                  </el-statistic>
                </el-col>
              </el-row>

              <el-progress
                :percentage="statusResult.summary.completion_rate"
                :color="statusResult.summary.completion_rate >= 80 ? '#67c23a' : statusResult.summary.completion_rate >= 50 ? '#e6a23c' : '#f56c6c'"
                style="margin-bottom: 20px"
              />

              <!-- 筛选 -->
              <el-radio-group v-model="statusFilter" size="small" style="margin-bottom: 12px">
                <el-radio-button value="all">全部</el-radio-button>
                <el-radio-button value="completed">已完成</el-radio-button>
                <el-radio-button value="incomplete">未完成</el-radio-button>
              </el-radio-group>

              <!-- 学生明细表 -->
              <el-table :data="filteredStudents" border stripe size="small">
                <el-table-column prop="student_name" label="姓名" min-width="100" fixed />
                <el-table-column
                  v-for="doc in statusResult.progress.docs"
                  :key="doc.doc_id"
                  :label="doc.doc_name"
                  min-width="120"
                  align="center"
                >
                  <template #default="scope">
                    <span v-if="getDocStatus(scope.row, doc.doc_id)?.is_completed" style="color: #67c23a; font-size: 16px">✅</span>
                    <span v-else style="color: #f56c6c; font-size: 16px">❌</span>
                  </template>
                </el-table-column>
                <el-table-column label="状态" width="100" align="center" fixed="right">
                  <template #default="scope">
                    <el-tag :type="scope.row.is_all_completed ? 'success' : 'danger'" size="small">
                      {{ scope.row.is_all_completed ? '已完成' : '未完成' }}
                    </el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </template>
            <div v-else class="empty-hint">请选择要查看的周进度</div>
          </template>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 新建/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isEditing ? '编辑周进度' : '新建周进度'" width="650px" @closed="formRef?.resetFields()">
      <el-form ref="formRef" :model="formData" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="formData.name" placeholder="如：第4周学习任务" />
        </el-form-item>
        <el-form-item label="时间范围" required>
          <el-date-picker v-model="formData.week_start" type="date" placeholder="开始日期" value-format="YYYY-MM-DD" style="width: 180px" />
          <span style="margin: 0 8px">至</span>
          <el-date-picker v-model="formData.week_end" type="date" placeholder="结束日期" value-format="YYYY-MM-DD" style="width: 180px" />
        </el-form-item>
        <el-form-item label="选择文档" required>
          <div class="doc-selection-list">
            <div v-for="doc in availableDocs" :key="doc.id" class="doc-row">
              <el-checkbox v-model="docSelection[doc.id]">
                {{ doc.name }}
                <el-tag :type="doc.type === 'video' ? 'success' : 'primary'" size="small" style="margin-left: 6px">
                  {{ doc.type === 'video' ? '视频' : doc.type }}
                </el-tag>
              </el-checkbox>
              <span v-if="doc.has_quiz" class="threshold-input">
                测验阈值:
                <el-input-number v-model="docThresholds[doc.id]" :min="0" :max="100" :step="5" size="small" style="width: 100px" /> %
              </span>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.class-selector-card {
  margin-bottom: 16px;
  .class-selector-row {
    display: flex; align-items: center; gap: 12px;
    .selector-label { font-weight: 500; font-size: 14px; }
  }
}
.main-card { :deep(.el-card__body) { padding: 20px 24px; } }
.empty-hint { text-align: center; padding: 60px 0; color: #c0c4cc; font-size: 15px; }
.doc-selection-list {
  max-height: 350px; overflow-y: auto; border: 1px solid #eee; border-radius: 4px; padding: 8px;
  .doc-row {
    display: flex; align-items: center; justify-content: space-between;
    padding: 8px 4px; border-bottom: 1px solid #f5f5f5;
    .threshold-input { font-size: 12px; color: #909399; display: flex; align-items: center; gap: 4px; }
  }
}
</style>
```
- [ ] **Step 3: 注册路由**

在 `management/web/src/router/index.ts` 的 `constantRoutes` 中，`/scoring` 路由之后添加：

```ts
{
  path: "/progress",
  component: Layouts,
  redirect: "/progress/index",
  children: [
    {
      path: "index",
      component: () => import("@/pages/progress/index.vue"),
      name: "ProgressManagement",
      meta: {
        title: "进度管理",
        svgIcon: "progress",
        affix: false,
        keepAlive: true
      }
    }
  ]
},
```

- [ ] **Step 4: 提交**

```bash
git add management/web/src/pages/progress/ management/web/src/common/assets/icons/progress.svg management/web/src/router/index.ts
git commit -m "feat: add progress management page with list and status tabs

Co-Authored-By: Claude <noreply@anthropic.com>"
```
