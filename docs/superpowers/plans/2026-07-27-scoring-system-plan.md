# 学生综合评分系统 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在管理后台新增「评分管理」模块，老师为每个班级配置 6 个评分维度的权重，平台实时计算每个学生的综合评分。

**Architecture:** 管理后台新增 3 张 MySQL 表存储配置和外部数据，后端新增 `services/scores/` 服务层（原始 SQL 聚合 + 实时计算引擎）和 `routes/scores/` 路由层（Flask Blueprint），前端新增 `pages/scoring/index.vue` 页面（Vue 3 + Element Plus，两个 Tab）。

**Tech Stack:** Python 3 + Flask + mysql.connector (raw SQL) + openpyxl (Excel parsing), Vue 3 + TypeScript + Element Plus + axios

**Note:** The management backend service layer uses raw SQL (no ORM). `request<T>` generic in the Vue frontend expects `ApiResponseData<T>` (the globally-declared wrapper: `{code, data, message}`).

## Global Constraints

- 管理后台全部接口需 `@require_superuser` 装饰器
- 启用维度的 weight 之和必须等于 100（应用层校验）
- 评分结果实时计算，不落库、不缓存
- 外部导入维度默认关闭（`external_enabled` default 0）
- 所有 ID 为 32 位 UUID hex 字符串（通过 `generate_uuid()` 生成）
- 时间字段使用 UTC+8（Asia/Shanghai）时区的毫秒时间戳和 datetime 字符串

---

## 文件结构

```
# 新建
management/server/services/scores/__init__.py          # 空文件
management/server/services/scores/service.py           # 全部服务逻辑
management/server/routes/scores/__init__.py             # 空文件
management/server/routes/scores/routes.py               # 全部 API 端点
management/web/src/common/apis/scores/index.ts          # API 函数
management/web/src/common/apis/scores/type.ts           # TypeScript 类型
management/web/src/pages/scoring/index.vue              # 评分管理页面
management/web/src/common/assets/icons/scoring.svg      # 菜单图标

# 修改
api/db/db_models.py                                     # 新增 3 个 Peewee 模型
management/server/routes/__init__.py                     # 注册 scoring_bp
management/web/src/router/index.ts                       # 新增 /scoring 路由
```

---

### Task 1: 创建数据库表

**Files:**
- Create: DDL（通过 Docker MySQL 执行）
- Modify: `api/db/db_models.py` — 新增 3 个 Peewee 模型

**Interfaces:**
- Produces: 3 张 MySQL 表 `scoring_config`、`external_score_source`、`external_score_record` 及对应的 Peewee 模型类

- [ ] **Step 1: 执行 DDL 创建 scoring_config 表**

```bash
docker exec ragflow-mysql mysql -u root -pinfini_rag_flow rag_flow -e "
CREATE TABLE IF NOT EXISTS scoring_config (
    id VARCHAR(32) PRIMARY KEY,
    class_id VARCHAR(32) NOT NULL,
    video_enabled TINYINT(1) DEFAULT 1,
    video_weight INT DEFAULT 0,
    quiz_enabled TINYINT(1) DEFAULT 1,
    quiz_weight INT DEFAULT 0,
    note_enabled TINYINT(1) DEFAULT 1,
    note_weight INT DEFAULT 0,
    flashcard_enabled TINYINT(1) DEFAULT 1,
    flashcard_weight INT DEFAULT 0,
    qa_enabled TINYINT(1) DEFAULT 1,
    qa_weight INT DEFAULT 0,
    external_enabled TINYINT(1) DEFAULT 0,
    external_weight INT DEFAULT 0,
    create_time BIGINT,
    create_date DATETIME,
    update_time BIGINT,
    update_date DATETIME,
    UNIQUE KEY uk_class_id (class_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"
```

- [ ] **Step 2: 执行 DDL 创建 external_score_source 表**

```bash
docker exec ragflow-mysql mysql -u root -pinfini_rag_flow rag_flow -e "
CREATE TABLE IF NOT EXISTS external_score_source (
    id VARCHAR(32) PRIMARY KEY,
    class_id VARCHAR(32) NOT NULL,
    source_name VARCHAR(100) NOT NULL,
    max_score INT NOT NULL,
    create_time BIGINT,
    create_date DATETIME,
    update_time BIGINT,
    update_date DATETIME,
    INDEX idx_class_id (class_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"
```

- [ ] **Step 3: 执行 DDL 创建 external_score_record 表**

```bash
docker exec ragflow-mysql mysql -u root -pinfini_rag_flow rag_flow -e "
CREATE TABLE IF NOT EXISTS external_score_record (
    id VARCHAR(32) PRIMARY KEY,
    source_id VARCHAR(32) NOT NULL,
    student_id VARCHAR(32) NOT NULL,
    score DECIMAL(8,2) NOT NULL,
    create_time BIGINT,
    create_date DATETIME,
    update_time BIGINT,
    update_date DATETIME,
    UNIQUE KEY uk_source_student (source_id, student_id),
    INDEX idx_source_id (source_id),
    INDEX idx_student_id (student_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"
```

- [ ] **Step 4: 验证表创建成功**

```bash
docker exec ragflow-mysql mysql -u root -pinfini_rag_flow rag_flow -e "SHOW CREATE TABLE scoring_config\G"
docker exec ragflow-mysql mysql -u root -pinfini_rag_flow rag_flow -e "SHOW CREATE TABLE external_score_source\G"
docker exec ragflow-mysql mysql -u root -pinfini_rag_flow rag_flow -e "SHOW CREATE TABLE external_score_record\G"
```

- [ ] **Step 5: 在 api/db/db_models.py 中添加 Peewee 模型**

在文件末尾（`knowledge_point_mastery` 模型之后，约 line 977）添加：

```python
class ScoringConfig(DataBaseModel):
    id = CharField(max_length=32, primary_key=True)
    class_id = CharField(max_length=32, null=False, unique=True)
    video_enabled = BooleanField(default=True)
    video_weight = IntegerField(default=0)
    quiz_enabled = BooleanField(default=True)
    quiz_weight = IntegerField(default=0)
    note_enabled = BooleanField(default=True)
    note_weight = IntegerField(default=0)
    flashcard_enabled = BooleanField(default=True)
    flashcard_weight = IntegerField(default=0)
    qa_enabled = BooleanField(default=True)
    qa_weight = IntegerField(default=0)
    external_enabled = BooleanField(default=False)
    external_weight = IntegerField(default=0)

    class Meta:
        db_table = "scoring_config"


class ExternalScoreSource(DataBaseModel):
    id = CharField(max_length=32, primary_key=True)
    class_id = CharField(max_length=32, null=False, index=True)
    source_name = CharField(max_length=100, null=False)
    max_score = IntegerField(null=False)

    class Meta:
        db_table = "external_score_source"


class ExternalScoreRecord(DataBaseModel):
    id = CharField(max_length=32, primary_key=True)
    source_id = CharField(max_length=32, null=False, index=True)
    student_id = CharField(max_length=32, null=False, index=True)
    score = DecimalField(max_digits=8, decimal_places=2, null=False)

    class Meta:
        db_table = "external_score_record"
        indexes = (
            (("source_id", "student_id"), True),
        )
```

- [ ] **Step 6: 提交**

```bash
git add api/db/db_models.py
git commit -m "feat: add scoring_config, external_score_source, external_score_record models

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: 评分配置与外部数据源 CRUD 服务

**Files:**
- Create: `management/server/services/scores/__init__.py`
- Create: `management/server/services/scores/service.py`

**Interfaces:**
- Produces:
  - `get_scoring_config(class_id: str) -> Tuple[bool, dict]`
  - `save_scoring_config(class_id: str, data: dict) -> Tuple[bool, str]`
  - `get_external_sources(class_id: str) -> list`
  - `create_external_source(class_id: str, source_name: str, max_score: int) -> Tuple[bool, str]`
  - `update_external_source(source_id: str, source_name: str, max_score: int) -> Tuple[bool, str]`
  - `delete_external_source(source_id: str) -> Tuple[bool, str]`
  - `get_external_records(source_id: str) -> list`
  - `upsert_external_records(source_id: str, records: list) -> Tuple[bool, str]`
  - `update_external_record(record_id: str, score: float) -> Tuple[bool, str]`

- [ ] **Step 1: 创建 service 文件骨架**

创建 `management/server/services/scores/__init__.py`（空文件）。

创建 `management/server/services/scores/service.py`，写入以下 imports 和辅助函数：

```python
import json
import mysql.connector
import pytz
from datetime import datetime
from utils import generate_uuid
from database import DB_CONFIG
from auth import get_current_user


def _get_utc8_time():
    """返回 (create_time_ms, create_date_str) UTC+8"""
    utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
    target_tz = pytz.timezone('Asia/Shanghai')
    local_dt = utc_now.astimezone(target_tz)
    return int(local_dt.timestamp() * 1000), local_dt.strftime("%Y-%m-%d %H:%M:%S")
```

- [ ] **Step 2: 实现 get_scoring_config**

```python
def get_scoring_config(class_id):
    """获取班级的评分配置，不存在则返回默认等权配置"""
    try:
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"
        user_id = current_user["user_id"]

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 校验班级归属
        check_query = "SELECT id FROM class WHERE id = %s AND tenant_id = %s"
        cursor.execute(check_query, (class_id, user_id))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return False, "班级不存在或无权操作"

        query = "SELECT * FROM scoring_config WHERE class_id = %s"
        cursor.execute(query, (class_id,))
        row = cursor.fetchone()

        cursor.close()
        conn.close()

        if row:
            # 转换 Decimal/timedelta 等非 JSON 兼容类型
            config = {
                "id": row["id"],
                "class_id": row["class_id"],
                "video_enabled": bool(row["video_enabled"]),
                "video_weight": row["video_weight"],
                "quiz_enabled": bool(row["quiz_enabled"]),
                "quiz_weight": row["quiz_weight"],
                "note_enabled": bool(row["note_enabled"]),
                "note_weight": row["note_weight"],
                "flashcard_enabled": bool(row["flashcard_enabled"]),
                "flashcard_weight": row["flashcard_weight"],
                "qa_enabled": bool(row["qa_enabled"]),
                "qa_weight": row["qa_weight"],
                "external_enabled": bool(row["external_enabled"]),
                "external_weight": row["external_weight"],
            }
            return True, config
        else:
            # 返回默认配置：全部启用，均分权重
            default_weights = {
                "video": 20, "quiz": 20, "note": 20,
                "flashcard": 20, "qa": 20, "external": 0
            }
            config = {
                "id": None,
                "class_id": class_id,
                "video_enabled": True, "video_weight": default_weights["video"],
                "quiz_enabled": True, "quiz_weight": default_weights["quiz"],
                "note_enabled": True, "note_weight": default_weights["note"],
                "flashcard_enabled": True, "flashcard_weight": default_weights["flashcard"],
                "qa_enabled": True, "qa_weight": default_weights["qa"],
                "external_enabled": False, "external_weight": 0,
            }
            return True, config

    except mysql.connector.Error as err:
        print(f"获取评分配置失败: {err}")
        return False, str(err)
```

- [ ] **Step 3: 实现 save_scoring_config**

```python
def save_scoring_config(class_id, data):
    """保存/更新班级评分配置，校验权重之和=100"""
    try:
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"
        user_id = current_user["user_id"]

        # 校验班级归属
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        check_query = "SELECT id FROM class WHERE id = %s AND tenant_id = %s"
        cursor.execute(check_query, (class_id, user_id))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return False, "班级不存在或无权操作"

        # 校验权重：启用维度之和 = 100
        dimensions = ["video", "quiz", "note", "flashcard", "qa", "external"]
        total_weight = 0
        for dim in dimensions:
            if data.get(f"{dim}_enabled", False):
                total_weight += int(data.get(f"{dim}_weight", 0))

        if total_weight != 100:
            cursor.close()
            conn.close()
            return False, f"启用的维度权重之和必须等于 100，当前为 {total_weight}"

        # Upsert
        ct_ms, ct_date = _get_utc8_time()
        existing = None
        cursor.execute("SELECT id FROM scoring_config WHERE class_id = %s", (class_id,))
        existing = cursor.fetchone()

        if existing:
            # Update
            set_clauses = []
            params = []
            for dim in dimensions:
                set_clauses.append(f"{dim}_enabled = %s")
                params.append(1 if data.get(f"{dim}_enabled") else 0)
                set_clauses.append(f"{dim}_weight = %s")
                params.append(int(data.get(f"{dim}_weight", 0)))
            set_clauses.append("update_time = %s")
            params.append(ct_ms)
            set_clauses.append("update_date = %s")
            params.append(ct_date)
            params.append(class_id)

            update_query = f"UPDATE scoring_config SET {', '.join(set_clauses)} WHERE class_id = %s"
            cursor.execute(update_query, params)
        else:
            # Insert
            config_id = generate_uuid()
            columns = ["id", "class_id", "create_time", "create_date", "update_time", "update_date"]
            values = [config_id, class_id, ct_ms, ct_date, ct_ms, ct_date]
            for dim in dimensions:
                columns.append(f"{dim}_enabled")
                values.append(1 if data.get(f"{dim}_enabled") else 0)
                columns.append(f"{dim}_weight")
                values.append(int(data.get(f"{dim}_weight", 0)))

            placeholders = ", ".join(["%s"] * len(values))
            insert_query = f"INSERT INTO scoring_config ({', '.join(columns)}) VALUES ({placeholders})"
            cursor.execute(insert_query, values)

        conn.commit()
        cursor.close()
        conn.close()
        return True, "保存成功"

    except mysql.connector.Error as err:
        print(f"保存评分配置失败: {err}")
        return False, str(err)
```

- [ ] **Step 4: 实现外部数据源 CRUD**

```python
def get_external_sources(class_id):
    """获取班级的所有外部数据源"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, class_id, source_name, max_score, create_date FROM external_score_source WHERE class_id = %s ORDER BY create_date",
            (class_id,)
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except mysql.connector.Error as err:
        print(f"获取外部数据源失败: {err}")
        return []


def create_external_source(class_id, source_name, max_score):
    """新增外部数据源"""
    try:
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"
        user_id = current_user["user_id"]

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 校验班级归属
        check_query = "SELECT id FROM class WHERE id = %s AND tenant_id = %s"
        cursor.execute(check_query, (class_id, user_id))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return False, "班级不存在或无权操作"

        if not source_name or not source_name.strip():
            cursor.close()
            conn.close()
            return False, "数据源名称不能为空"

        if max_score <= 0:
            cursor.close()
            conn.close()
            return False, "满分值必须大于 0"

        source_id = generate_uuid()
        ct_ms, ct_date = _get_utc8_time()

        cursor.execute(
            "INSERT INTO external_score_source (id, class_id, source_name, max_score, create_time, create_date, update_time, update_date) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (source_id, class_id, source_name.strip(), max_score, ct_ms, ct_date, ct_ms, ct_date)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True, source_id

    except mysql.connector.Error as err:
        print(f"创建外部数据源失败: {err}")
        return False, str(err)


def update_external_source(source_id, source_name, max_score):
    """修改外部数据源"""
    try:
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"
        user_id = current_user["user_id"]

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 校验所有权：source → class → tenant
        check_query = """
            SELECT ess.id FROM external_score_source ess
            JOIN class c ON ess.class_id = c.id
            WHERE ess.id = %s AND c.tenant_id = %s
        """
        cursor.execute(check_query, (source_id, user_id))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return False, "数据源不存在或无权操作"

        ct_ms, ct_date = _get_utc8_time()
        cursor.execute(
            "UPDATE external_score_source SET source_name = %s, max_score = %s, update_time = %s, update_date = %s WHERE id = %s",
            (source_name.strip(), max_score, ct_ms, ct_date, source_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True, "修改成功"

    except mysql.connector.Error as err:
        print(f"修改外部数据源失败: {err}")
        return False, str(err)


def delete_external_source(source_id):
    """删除外部数据源，级联删除关联记录"""
    try:
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"
        user_id = current_user["user_id"]

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        check_query = """
            SELECT ess.id FROM external_score_source ess
            JOIN class c ON ess.class_id = c.id
            WHERE ess.id = %s AND c.tenant_id = %s
        """
        cursor.execute(check_query, (source_id, user_id))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return False, "数据源不存在或无权操作"

        # 级联删除
        cursor.execute("DELETE FROM external_score_record WHERE source_id = %s", (source_id,))
        cursor.execute("DELETE FROM external_score_source WHERE id = %s", (source_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "删除成功"

    except mysql.connector.Error as err:
        print(f"删除外部数据源失败: {err}")
        return False, str(err)
```

- [ ] **Step 5: 实现外部评分记录 CRUD**

```python
def get_external_records(source_id):
    """获取某数据源下所有学生的成绩，join user 获取姓名"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT esr.id, esr.student_id, u.nickname AS student_name, esr.score, esr.create_date
            FROM external_score_record esr
            JOIN user u ON esr.student_id = u.id
            WHERE esr.source_id = %s
            ORDER BY esr.score DESC
        """, (source_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except mysql.connector.Error as err:
        print(f"获取外部评分记录失败: {err}")
        return []


def upsert_external_records(source_id, records):
    """批量 upsert 外部评分记录
    records: [{"student_id": "xxx", "score": 85.5}, ...]
    """
    try:
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"
        user_id = current_user["user_id"]

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 校验数据源归属
        check_query = """
            SELECT ess.id, ess.class_id FROM external_score_source ess
            JOIN class c ON ess.class_id = c.id
            WHERE ess.id = %s AND c.tenant_id = %s
        """
        cursor.execute(check_query, (source_id, user_id))
        source_row = cursor.fetchone()
        if not source_row:
            cursor.close()
            conn.close()
            return False, "数据源不存在或无权操作"

        if not records:
            cursor.close()
            conn.close()
            return False, "没有要导入的数据"

        ct_ms, ct_date = _get_utc8_time()
        inserted = 0
        updated = 0

        for rec in records:
            sid = rec.get("student_id", "").strip()
            score = rec.get("score", 0)
            if not sid:
                continue

            cursor.execute(
                "SELECT id FROM external_score_record WHERE source_id = %s AND student_id = %s",
                (source_id, sid)
            )
            existing = cursor.fetchone()
            if existing:
                cursor.execute(
                    "UPDATE external_score_record SET score = %s, update_time = %s, update_date = %s WHERE id = %s",
                    (score, ct_ms, ct_date, existing["id"])
                )
                updated += 1
            else:
                record_id = generate_uuid()
                cursor.execute(
                    "INSERT INTO external_score_record (id, source_id, student_id, score, create_time, create_date, update_time, update_date) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (record_id, source_id, sid, score, ct_ms, ct_date, ct_ms, ct_date)
                )
                inserted += 1

        conn.commit()
        cursor.close()
        conn.close()
        return True, f"导入完成：新增 {inserted} 条，更新 {updated} 条"

    except mysql.connector.Error as err:
        print(f"导入外部评分记录失败: {err}")
        return False, str(err)


def update_external_record(record_id, score):
    """手动修改单条外部评分记录"""
    try:
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"
        user_id = current_user["user_id"]

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 校验所有权链路：record → source → class → tenant
        check_query = """
            SELECT esr.id FROM external_score_record esr
            JOIN external_score_source ess ON esr.source_id = ess.id
            JOIN class c ON ess.class_id = c.id
            WHERE esr.id = %s AND c.tenant_id = %s
        """
        cursor.execute(check_query, (record_id, user_id))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return False, "记录不存在或无权操作"

        ct_ms, ct_date = _get_utc8_time()
        cursor.execute(
            "UPDATE external_score_record SET score = %s, update_time = %s, update_date = %s WHERE id = %s",
            (score, ct_ms, ct_date, record_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True, "修改成功"

    except mysql.connector.Error as err:
        print(f"修改外部评分记录失败: {err}")
        return False, str(err)
```

- [ ] **Step 6: 提交**

```bash
git add management/server/services/scores/
git commit -m "feat: add scoring config and external source CRUD services

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: 评分计算引擎

**Files:**
- Modify: `management/server/services/scores/service.py` — 追加评分计算函数

**Interfaces:**
- Produces:
  - `calculate_class_scores(class_id: str) -> Tuple[bool, dict]`
  - `calculate_student_score(class_id: str, student_id: str) -> Tuple[bool, dict]`

- [ ] **Step 1: 实现数据范围解析辅助函数**

在 `service.py` 中追加：

```python
def _get_class_doc_ids_and_dialog_ids(class_id):
    """获取班级关联的所有文档 ID 和 dialog ID 集合
    Returns: (doc_ids: list, dialog_ids: list)
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    # Step 1: 获取班级关联的 dialog_ids
    cursor.execute("SELECT dialog_id FROM class_dialog WHERE class_id = %s", (class_id,))
    dialog_rows = cursor.fetchall()
    dialog_ids = [r["dialog_id"] for r in dialog_rows]

    if not dialog_ids:
        cursor.close()
        conn.close()
        return [], []

    # Step 2: 获取 dialog 的 kb_ids
    placeholders = ", ".join(["%s"] * len(dialog_ids))
    cursor.execute(
        f"SELECT id, kb_ids FROM dialog WHERE id IN ({placeholders})",
        dialog_ids
    )
    dialog_rows = cursor.fetchall()

    # Step 3: 解析 kb_ids JSON 数组，收集所有 kb_id
    kb_id_set = set()
    for row in dialog_rows:
        kb_ids = row.get("kb_ids")
        if kb_ids:
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
        return [], dialog_ids

    # Step 4: 获取这些 kb 下的所有 valid 文档
    kb_placeholders = ", ".join(["%s"] * len(kb_id_set))
    cursor.execute(
        f"SELECT id, type, chunk_num FROM document WHERE kb_id IN ({kb_placeholders}) AND status = '1'",
        list(kb_id_set)
    )
    doc_rows = cursor.fetchall()

    cursor.close()
    conn.close()
    return doc_rows, dialog_ids  # 返回文档详情列表 + dialog_ids


def _get_class_students(class_id):
    """获取班级学生列表"""
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT u.id, u.nickname, u.email
        FROM user u
        JOIN user_class uc ON u.id = uc.user_id
        WHERE uc.class_id = %s AND uc.role = 'student' AND uc.status = '1'
        ORDER BY u.nickname
    """, (class_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows
```

- [ ] **Step 2: 实现各维度计算函数**

```python
def _calc_video_score(student_id, doc_ids, video_doc_ids):
    """视频维度: 完成率 = 完成数 / 总视频数 × 100"""
    if not video_doc_ids:
        return 0.0
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    placeholders = ", ".join(["%s"] * len(video_doc_ids))
    cursor.execute(
        f"SELECT COUNT(*) as cnt, SUM(is_completed) as completed FROM student_video_progress WHERE student_id = %s AND doc_id IN ({placeholders})",
        [student_id] + video_doc_ids
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    total = len(video_doc_ids)
    completed = int(row["completed"] or 0) if row else 0
    return round(completed / total * 100, 1)


def _calc_quiz_score(student_id, doc_ids):
    """测验维度: 正确率 = 正确数 / 总答题数 × 100"""
    if not doc_ids:
        return 0.0
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    placeholders = ", ".join(["%s"] * len(doc_ids))
    cursor.execute(
        f"SELECT COUNT(*) as cnt, SUM(is_correct) as correct FROM student_quiz_result WHERE student_id = %s AND doc_id IN ({placeholders})",
        [student_id] + doc_ids
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    total = int(row["cnt"] or 0) if row else 0
    if total == 0:
        return 0.0
    correct = int(row["correct"] or 0)
    return round(correct / total * 100, 1)


def _calc_note_score(student_id, doc_ids, doc_page_map):
    """笔记维度: 覆盖率 = 有笔记的页面数 / 文档总页面数 × 100"""
    if not doc_ids:
        return 0.0
    total_pages = sum(doc_page_map.get(did, 0) for did in doc_ids)
    if total_pages == 0:
        return 0.0
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    placeholders = ", ".join(["%s"] * len(doc_ids))
    cursor.execute(
        f"SELECT COUNT(DISTINCT CONCAT(doc_id, '-', page_number)) as cnt FROM student_note WHERE student_id = %s AND doc_id IN ({placeholders})",
        [student_id] + doc_ids
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    noted_pages = int(row["cnt"] or 0) if row else 0
    return round(min(noted_pages / total_pages, 1.0) * 100, 1)


def _calc_flashcard_score(student_id, doc_ids, doc_flashcard_map):
    """概念速记维度: 记忆率 = 记住的卡片数 / 总卡片数 × 100"""
    relevant_docs = [did for did in doc_ids if doc_flashcard_map.get(did, 0) > 0]
    if not relevant_docs:
        return 0.0
    total_cards = sum(doc_flashcard_map.get(did, 0) for did in relevant_docs)
    if total_cards == 0:
        return 0.0
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    placeholders = ", ".join(["%s"] * len(relevant_docs))
    cursor.execute(
        f"SELECT COUNT(*) as cnt FROM student_card_progress WHERE student_id = %s AND doc_id IN ({placeholders}) AND status = 'remembered'",
        [student_id] + relevant_docs
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    remembered = int(row["cnt"] or 0) if row else 0
    return round(remembered / total_cards * 100, 1)


def _calc_qa_score(student_id, dialog_ids):
    """问答活跃度: min(消息数 / 20 × 100, 100)"""
    if not dialog_ids:
        return 0.0
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    placeholders = ", ".join(["%s"] * len(dialog_ids))
    cursor.execute(
        f"SELECT COUNT(*) as cnt FROM conversation WHERE user_id = %s AND dialog_id IN ({placeholders})",
        [student_id] + dialog_ids
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    msg_count = int(row["cnt"] or 0) if row else 0
    return round(min(msg_count / 20 * 100, 100), 1)


def _calc_external_score(student_id, class_id):
    """外部导入维度: 各源归一化分取平均"""
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT ess.id, ess.max_score, esr.score
        FROM external_score_source ess
        LEFT JOIN external_score_record esr ON ess.id = esr.source_id AND esr.student_id = %s
        WHERE ess.class_id = %s
    """, (student_id, class_id))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        return 0.0

    normalized_scores = []
    for row in rows:
        if row["score"] is not None and row["max_score"] > 0:
            normalized_scores.append(min(row["score"] / row["max_score"] * 100, 100))

    if not normalized_scores:
        return 0.0
    return round(sum(normalized_scores) / len(normalized_scores), 1)
```

- [ ] **Step 3: 实现预计算辅助函数（文档级元数据）**

```python
def _get_doc_metadata(doc_rows):
    """从文档列表提取元数据
    Returns: (doc_ids, video_doc_ids, doc_page_map, doc_flashcard_map)
    """
    doc_ids = []
    video_doc_ids = []
    doc_page_map = {}      # doc_id → total pages
    doc_flashcard_map = {}  # doc_id → total flashcards

    for row in doc_rows:
        did = row["id"]
        doc_ids.append(did)
        doc_page_map[did] = row.get("chunk_num", 0) or 0
        if row.get("type") == "video":
            video_doc_ids.append(did)

    # 查询文档的闪卡总数
    if doc_ids:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        placeholders = ", ".join(["%s"] * len(doc_ids))
        cursor.execute(
            f"SELECT doc_id, content FROM document_generation WHERE doc_id IN ({placeholders}) AND generation_type = 'flashcards'",
            doc_ids
        )
        for row in cursor.fetchall():
            try:
                content = json.loads(row["content"]) if isinstance(row["content"], str) else row["content"]
                doc_flashcard_map[row["doc_id"]] = len(content) if isinstance(content, list) else 0
            except (json.JSONDecodeError, TypeError):
                doc_flashcard_map[row["doc_id"]] = 0
        cursor.close()
        conn.close()

    # 未查询到的文档闪卡数默认为 0
    for did in doc_ids:
        if did not in doc_flashcard_map:
            doc_flashcard_map[did] = 0

    return doc_ids, video_doc_ids, doc_page_map, doc_flashcard_map
```

- [ ] **Step 4: 实现 calculate_class_scores**

```python
def calculate_class_scores(class_id):
    """计算整个班级的学生评分总表"""
    try:
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"
        user_id = current_user["user_id"]

        # 1. 获取评分配置
        success, config = get_scoring_config(class_id)
        if not success:
            return False, config

        # 2. 获取学生列表
        students = _get_class_students(class_id)
        if not students:
            return True, {
                "class_id": class_id,
                "config": config,
                "students": []
            }

        # 3. 获取文档和 dialog 数据
        doc_rows, dialog_ids = _get_class_doc_ids_and_dialog_ids(class_id)
        doc_ids, video_doc_ids, doc_page_map, doc_flashcard_map = _get_doc_metadata(doc_rows)

        # 4. 逐学生计算各维度得分
        student_results = []
        for student in students:
            sid = student["id"]
            dimensions = {}
            if config["video_enabled"]:
                dimensions["video"] = _calc_video_score(sid, doc_ids, video_doc_ids)
            if config["quiz_enabled"]:
                dimensions["quiz"] = _calc_quiz_score(sid, doc_ids)
            if config["note_enabled"]:
                dimensions["note"] = _calc_note_score(sid, doc_ids, doc_page_map)
            if config["flashcard_enabled"]:
                dimensions["flashcard"] = _calc_flashcard_score(sid, doc_ids, doc_flashcard_map)
            if config["qa_enabled"]:
                dimensions["qa"] = _calc_qa_score(sid, dialog_ids)
            if config["external_enabled"]:
                dimensions["external"] = _calc_external_score(sid, class_id)

            # 计算总分
            total = 0.0
            for dim_key, dim_val in dimensions.items():
                weight = config.get(f"{dim_key}_weight", 0)
                total += dim_val * weight / 100

            student_results.append({
                "student_id": sid,
                "student_name": student.get("nickname", "") or student.get("email", ""),
                "dimensions": dimensions,
                "total_score": round(total, 2)
            })

        # 按总分降序排列
        student_results.sort(key=lambda x: x["total_score"], reverse=True)

        return True, {
            "class_id": class_id,
            "config": config,
            "students": student_results
        }

    except Exception as e:
        print(f"计算班级评分失败: {e}")
        return False, str(e)


def calculate_student_score(class_id, student_id):
    """计算单个学生的评分详情"""
    success, result = calculate_class_scores(class_id)
    if not success:
        return False, result
    for s in result["students"]:
        if s["student_id"] == student_id:
            return True, s
    return False, "学生不在该班级中"
```

- [ ] **Step 5: 提交**

```bash
git add management/server/services/scores/service.py
git commit -m "feat: add scoring calculation engine with 6-dimension scoring

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: API 路由 + Blueprint 注册

**Files:**
- Create: `management/server/routes/scores/__init__.py`
- Create: `management/server/routes/scores/routes.py`
- Modify: `management/server/routes/__init__.py`

**Interfaces:**
- Consumes: 所有 Task 2-3 的 service 函数
- Produces: REST API endpoints under `/api/v1/scoring`

- [ ] **Step 1: 创建 routes.py**

创建 `management/server/routes/scores/__init__.py`（空文件）。

创建 `management/server/routes/scores/routes.py`：

```python
from flask import jsonify, request
from services.scores.service import (
    get_scoring_config,
    save_scoring_config,
    get_external_sources,
    create_external_source,
    update_external_source,
    delete_external_source,
    get_external_records,
    upsert_external_records,
    update_external_record,
    calculate_class_scores,
    calculate_student_score,
)
from routes import scoring_bp
from auth import require_superuser


# ========== 评分配置 ==========

@scoring_bp.route('/config/<string:class_id>', methods=['GET'])
@require_superuser
def get_config(class_id):
    try:
        success, result = get_scoring_config(class_id)
        if success:
            return jsonify({"code": 0, "data": result, "message": "获取评分配置成功"})
        else:
            return jsonify({"code": 400, "message": result}), 400
    except Exception as e:
        return jsonify({"code": 500, "message": f"获取评分配置失败: {str(e)}"}), 500


@scoring_bp.route('/config/<string:class_id>', methods=['PUT'])
@require_superuser
def update_config(class_id):
    try:
        data = request.json
        if not data:
            return jsonify({"code": 400, "message": "请求体不能为空"}), 400
        success, result = save_scoring_config(class_id, data)
        if success:
            return jsonify({"code": 0, "data": None, "message": result})
        else:
            return jsonify({"code": 400, "message": result}), 400
    except Exception as e:
        return jsonify({"code": 500, "message": f"保存评分配置失败: {str(e)}"}), 500


# ========== 外部数据源 ==========

@scoring_bp.route('/external-source/<string:class_id>', methods=['GET'])
@require_superuser
def list_external_sources(class_id):
    try:
        sources = get_external_sources(class_id)
        return jsonify({"code": 0, "data": sources, "message": "获取外部数据源列表成功"})
    except Exception as e:
        return jsonify({"code": 500, "message": f"获取外部数据源列表失败: {str(e)}"}), 500


@scoring_bp.route('/external-source', methods=['POST'])
@require_superuser
def add_external_source():
    try:
        data = request.json
        if not data:
            return jsonify({"code": 400, "message": "请求体不能为空"}), 400
        class_id = data.get("class_id", "")
        source_name = data.get("source_name", "")
        max_score = data.get("max_score", 0)
        success, result = create_external_source(class_id, source_name, max_score)
        if success:
            return jsonify({"code": 0, "data": {"id": result}, "message": "创建外部数据源成功"})
        else:
            return jsonify({"code": 400, "message": result}), 400
    except Exception as e:
        return jsonify({"code": 500, "message": f"创建外部数据源失败: {str(e)}"}), 500


@scoring_bp.route('/external-source/<string:source_id>', methods=['PUT'])
@require_superuser
def edit_external_source(source_id):
    try:
        data = request.json
        if not data:
            return jsonify({"code": 400, "message": "请求体不能为空"}), 400
        source_name = data.get("source_name", "")
        max_score = data.get("max_score", 0)
        success, result = update_external_source(source_id, source_name, max_score)
        if success:
            return jsonify({"code": 0, "data": None, "message": result})
        else:
            return jsonify({"code": 400, "message": result}), 400
    except Exception as e:
        return jsonify({"code": 500, "message": f"修改外部数据源失败: {str(e)}"}), 500


@scoring_bp.route('/external-source/<string:source_id>', methods=['DELETE'])
@require_superuser
def remove_external_source(source_id):
    try:
        success, result = delete_external_source(source_id)
        if success:
            return jsonify({"code": 0, "data": None, "message": result})
        else:
            return jsonify({"code": 400, "message": result}), 400
    except Exception as e:
        return jsonify({"code": 500, "message": f"删除外部数据源失败: {str(e)}"}), 500


# ========== 外部评分记录 ==========

@scoring_bp.route('/external-record/<string:source_id>', methods=['GET'])
@require_superuser
def list_external_records(source_id):
    try:
        records = get_external_records(source_id)
        return jsonify({"code": 0, "data": records, "message": "获取外部评分记录成功"})
    except Exception as e:
        return jsonify({"code": 500, "message": f"获取外部评分记录失败: {str(e)}"}), 500


@scoring_bp.route('/external-record/upload', methods=['POST'])
@require_superuser
def upload_external_records():
    try:
        source_id = request.form.get("source_id", "")
        if not source_id:
            return jsonify({"code": 400, "message": "缺少 source_id"}), 400

        file = request.files.get("file")
        if not file:
            return jsonify({"code": 400, "message": "请上传文件"}), 400

        # 读取 Excel
        try:
            import openpyxl
            wb = openpyxl.load_workbook(file, read_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
        except Exception as e:
            return jsonify({"code": 400, "message": f"解析 Excel 失败: {str(e)}"}), 400

        if len(rows) < 2:
            return jsonify({"code": 400, "message": "Excel 至少需要包含表头行和一行数据"}), 400

        # 解析表头
        header = [str(c).strip() if c else "" for c in rows[0]]
        try:
            student_id_col = header.index("学号")
            score_col = header.index("得分")
        except ValueError:
            return jsonify({"code": 400, "message": "Excel 表头必须包含「学号」和「得分」列"}), 400

        # 解析数据行
        records = []
        for row in rows[1:]:
            if not row or len(row) <= max(student_id_col, score_col):
                continue
            sid = str(row[student_id_col]).strip() if row[student_id_col] is not None else ""
            try:
                score = float(row[score_col]) if row[score_col] is not None else 0
            except (ValueError, TypeError):
                continue
            if sid:
                records.append({"student_id": sid, "score": score})

        if not records:
            return jsonify({"code": 400, "message": "没有解析到有效数据"}), 400

        success, result = upsert_external_records(source_id, records)
        if success:
            return jsonify({"code": 0, "data": None, "message": result})
        else:
            return jsonify({"code": 400, "message": result}), 400

    except Exception as e:
        return jsonify({"code": 500, "message": f"上传评分数据失败: {str(e)}"}), 500


@scoring_bp.route('/external-record/<string:record_id>', methods=['PUT'])
@require_superuser
def edit_external_record(record_id):
    try:
        data = request.json
        if not data:
            return jsonify({"code": 400, "message": "请求体不能为空"}), 400
        score = data.get("score")
        if score is None:
            return jsonify({"code": 400, "message": "缺少 score"}), 400
        success, result = update_external_record(record_id, float(score))
        if success:
            return jsonify({"code": 0, "data": None, "message": result})
        else:
            return jsonify({"code": 400, "message": result}), 400
    except Exception as e:
        return jsonify({"code": 500, "message": f"修改评分记录失败: {str(e)}"}), 500


# ========== 评分结果 ==========

@scoring_bp.route('/result/<string:class_id>', methods=['GET'])
@require_superuser
def get_class_scores(class_id):
    try:
        success, result = calculate_class_scores(class_id)
        if success:
            return jsonify({"code": 0, "data": result, "message": "获取评分结果成功"})
        else:
            return jsonify({"code": 400, "message": result}), 400
    except Exception as e:
        return jsonify({"code": 500, "message": f"获取评分结果失败: {str(e)}"}), 500


@scoring_bp.route('/result/<string:class_id>/<string:student_id>', methods=['GET'])
@require_superuser
def get_student_score(class_id, student_id):
    try:
        success, result = calculate_student_score(class_id, student_id)
        if success:
            return jsonify({"code": 0, "data": result, "message": "获取学生评分成功"})
        else:
            return jsonify({"code": 400, "message": result}), 400
    except Exception as e:
        return jsonify({"code": 500, "message": f"获取学生评分失败: {str(e)}"}), 500
```

- [ ] **Step 2: 注册 Blueprint**

在 `management/server/routes/__init__.py` 中添加：

找到其他 Blueprint 定义行（约 line 10-12），添加：
```python
scoring_bp = Blueprint('scoring', __name__, url_prefix='/api/v1/scoring')
```

找到 `from .conversation.routes import *`（约 line 17），在其后添加：
```python
from .scores.routes import *
```

找到 `register_routes` 函数，在 `app.register_blueprint(conversation_bp)` 之后添加：
```python
app.register_blueprint(scoring_bp)
```

- [ ] **Step 3: 提交**

```bash
git add management/server/routes/scores/ management/server/routes/__init__.py
git commit -m "feat: add scoring API routes with blueprint registration

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: 前端 API 客户端

**Files:**
- Create: `management/web/src/common/apis/scores/index.ts`
- Create: `management/web/src/common/apis/scores/type.ts`

**Interfaces:**
- Produces: 所有 API 函数的 TypeScript 类型定义和 axios 调用

- [ ] **Step 1: 创建 type.ts**

创建 `management/web/src/common/apis/scores/type.ts`：

```ts
/** 评分配置 */
export interface ScoringConfig {
  id: string | null
  class_id: string
  video_enabled: boolean
  video_weight: number
  quiz_enabled: boolean
  quiz_weight: number
  note_enabled: boolean
  note_weight: number
  flashcard_enabled: boolean
  flashcard_weight: number
  qa_enabled: boolean
  qa_weight: number
  external_enabled: boolean
  external_weight: number
}

export interface SaveScoringConfigData {
  video_enabled: boolean
  video_weight: number
  quiz_enabled: boolean
  quiz_weight: number
  note_enabled: boolean
  note_weight: number
  flashcard_enabled: boolean
  flashcard_weight: number
  qa_enabled: boolean
  qa_weight: number
  external_enabled: boolean
  external_weight: number
}

/** 外部数据源 */
export interface ExternalScoreSource {
  id: string
  class_id: string
  source_name: string
  max_score: number
  create_date?: string
}

export interface CreateExternalSourceData {
  class_id: string
  source_name: string
  max_score: number
}

/** 外部评分记录 */
export interface ExternalScoreRecord {
  id: string
  student_id: string
  student_name: string
  score: number
  create_date?: string
}

/** 评分结果 — 维度明细 */
export interface ScoreDimensions {
  video?: number
  quiz?: number
  note?: number
  flashcard?: number
  qa?: number
  external?: number
}

/** 评分结果 — 单个学生 */
export interface StudentScore {
  student_id: string
  student_name: string
  dimensions: ScoreDimensions
  total_score: number
}

/** 评分结果 — 全班 */
export interface ClassScoreResult {
  class_id: string
  config: ScoringConfig
  students: StudentScore[]
}
```

- [ ] **Step 2: 创建 index.ts**

创建 `management/web/src/common/apis/scores/index.ts`：

```ts
import type {
  ClassScoreResult,
  CreateExternalSourceData,
  ExternalScoreRecord,
  ExternalScoreSource,
  SaveScoringConfigData,
  ScoringConfig,
  StudentScore
} from "./type"
import { request } from "@/http/axios"

/** 获取班级评分配置 */
export function getScoringConfigApi(classId: string) {
  return request<ScoringConfig>({
    url: `api/v1/scoring/config/${classId}`,
    method: "get"
  })
}

/** 保存班级评分配置 */
export function saveScoringConfigApi(classId: string, data: SaveScoringConfigData) {
  return request({
    url: `api/v1/scoring/config/${classId}`,
    method: "put",
    data
  })
}

/** 获取班级外部数据源列表 */
export function getExternalSourcesApi(classId: string) {
  return request<ExternalScoreSource[]>({
    url: `api/v1/scoring/external-source/${classId}`,
    method: "get"
  })
}

/** 新增外部数据源 */
export function createExternalSourceApi(data: CreateExternalSourceData) {
  return request<{ id: string }>({
    url: "api/v1/scoring/external-source",
    method: "post",
    data
  })
}

/** 修改外部数据源 */
export function updateExternalSourceApi(sourceId: string, data: { source_name: string; max_score: number }) {
  return request({
    url: `api/v1/scoring/external-source/${sourceId}`,
    method: "put",
    data
  })
}

/** 删除外部数据源 */
export function deleteExternalSourceApi(sourceId: string) {
  return request({
    url: `api/v1/scoring/external-source/${sourceId}`,
    method: "delete"
  })
}

/** 获取外部评分记录 */
export function getExternalRecordsApi(sourceId: string) {
  return request<ExternalScoreRecord[]>({
    url: `api/v1/scoring/external-record/${sourceId}`,
    method: "get"
  })
}

/** 上传 Excel 导入外部评分 */
export function uploadExternalRecordsApi(sourceId: string, file: File) {
  const formData = new FormData()
  formData.append("source_id", sourceId)
  formData.append("file", file)
  return request({
    url: "api/v1/scoring/external-record/upload",
    method: "post",
    data: formData,
    headers: { "Content-Type": "multipart/form-data" }
  })
}

/** 手动修改外部评分记录 */
export function updateExternalRecordApi(recordId: string, score: number) {
  return request({
    url: `api/v1/scoring/external-record/${recordId}`,
    method: "put",
    data: { score }
  })
}

/** 获取班级评分总表 */
export function getClassScoresApi(classId: string) {
  return request<ClassScoreResult>({
    url: `api/v1/scoring/result/${classId}`,
    method: "get"
  })
}

/** 获取单个学生评分详情 */
export function getStudentScoreApi(classId: string, studentId: string) {
  return request<StudentScore>({
    url: `api/v1/scoring/result/${classId}/${studentId}`,
    method: "get"
  })
}
```

- [ ] **Step 3: 提交**

```bash
git add management/web/src/common/apis/scores/
git commit -m "feat: add scoring API client with TypeScript types

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: 前端评分管理页面 + 路由注册

**Files:**
- Create: `management/web/src/pages/scoring/index.vue`
- Create: `management/web/src/common/assets/icons/scoring.svg`
- Modify: `management/web/src/router/index.ts`

**Interfaces:**
- Consumes: Task 5 的 API 客户端函数和类型
- Consumes: 已有的 `getTeamsDataApi`（加载班级列表）

- [ ] **Step 1: 创建评分管理页面**

创建 `management/web/src/pages/scoring/index.vue`：

```vue
<script lang="ts" setup>
import type { ScoringConfig, ExternalScoreSource, ClassScoreResult } from "@@/apis/scores/type"
import type { FormInstance } from "element-plus"
import {
  getScoringConfigApi,
  saveScoringConfigApi,
  getExternalSourcesApi,
  createExternalSourceApi,
  updateExternalSourceApi,
  deleteExternalSourceApi,
  uploadExternalRecordsApi,
  getClassScoresApi
} from "@@/apis/scores"
import { getTeamsDataApi } from "@@/apis/teams"
import { ElMessage, ElMessageBox } from "element-plus"
import { Download, Plus, Refresh, Search, Upload } from "@element-plus/icons-vue"
import { onMounted, reactive, ref, watch } from "vue"

defineOptions({ name: "ScoringManagement" })

const loading = ref(false)
const activeTab = ref("config")

// ============ 班级选择 ============
interface ClassOption {
  id: string
  name: string
}
const classOptions = ref<ClassOption[]>([])
const selectedClassId = ref("")

function loadClasses() {
  getTeamsDataApi({ currentPage: 1, size: 1000 }).then(({ data }) => {
    classOptions.value = data.list.map((c: any) => ({ id: c.id, name: c.name }))
  })
}

onMounted(() => loadClasses())

// ============ Tab 1: 评分配置 ============
const DIMENSION_LABELS: Record<string, string> = {
  video: "视频",
  quiz: "测验",
  note: "笔记",
  flashcard: "概念速记",
  qa: "问答活跃度",
  external: "外部导入"
}

const DIMENSION_KEYS = ["video", "quiz", "note", "flashcard", "qa", "external"]

const dimensionEnabled = reactive<Record<string, boolean>>({})
const dimensionWeight = reactive<Record<string, number>>({})

function initDimensions() {
  DIMENSION_KEYS.forEach(key => {
    dimensionEnabled[key] = true
    dimensionWeight[key] = 20
  })
  dimensionEnabled["external"] = false
  dimensionWeight["external"] = 0
}
initDimensions()

const totalWeight = ref(100)

function recalcTotal() {
  totalWeight.value = DIMENSION_KEYS.reduce((sum, key) => {
    return sum + (dimensionEnabled[key] ? dimensionWeight[key] : 0)
  }, 0)
}

watch(dimensionWeight, () => recalcTotal(), { deep: true })
watch(dimensionEnabled, () => {
  DIMENSION_KEYS.forEach(key => {
    if (!dimensionEnabled[key]) dimensionWeight[key] = 0
  })
  recalcTotal()
}, { deep: true })

function loadConfig() {
  if (!selectedClassId.value) return
  loading.value = true
  getScoringConfigApi(selectedClassId.value).then(({ data: config }) => {
    DIMENSION_KEYS.forEach(key => {
      dimensionEnabled[key] = config[`${key}_enabled` as keyof ScoringConfig] as boolean
      dimensionWeight[key] = config[`${key}_weight` as keyof ScoringConfig] as number
    })
    recalcTotal()
  }).finally(() => { loading.value = false })
}

watch(selectedClassId, () => {
  if (activeTab.value === "config") loadConfig()
  if (activeTab.value === "result") loadScores()
})

function handleSaveConfig() {
  if (!selectedClassId.value) {
    ElMessage.warning("请先选择班级")
    return
  }
  if (totalWeight.value !== 100) {
    ElMessage.error("已启用维度权重之和必须等于 100")
    return
  }
  loading.value = true
  const data: any = {}
  DIMENSION_KEYS.forEach(key => {
    data[`${key}_enabled`] = dimensionEnabled[key]
    data[`${key}_weight`] = dimensionWeight[key]
  })
  saveScoringConfigApi(selectedClassId.value, data).then(() => {
    ElMessage.success("保存成功")
    loadConfig()
  }).finally(() => { loading.value = false })
}

// ============ 外部数据源管理 ============
const externalSources = ref<ExternalScoreSource[]>([])
const sourceDialogVisible = ref(false)
const sourceFormRef = ref<FormInstance | null>(null)
const sourceForm = reactive({ id: "" as string | undefined, source_name: "", max_score: 100 })
const isEditingSource = ref(false)

function loadExternalSources() {
  if (!selectedClassId.value) return
  getExternalSourcesApi(selectedClassId.value).then(({ data }) => {
    externalSources.value = data || []
  })
}

watch(() => dimensionEnabled["external"], (enabled) => {
  if (enabled) loadExternalSources()
})

function openAddSource() {
  isEditingSource.value = false
  sourceForm.id = undefined
  sourceForm.source_name = ""
  sourceForm.max_score = 100
  sourceDialogVisible.value = true
}

function openEditSource(source: ExternalScoreSource) {
  isEditingSource.value = true
  sourceForm.id = source.id
  sourceForm.source_name = source.source_name
  sourceForm.max_score = source.max_score
  sourceDialogVisible.value = true
}

function handleSaveSource() {
  if (!sourceForm.source_name.trim()) {
    ElMessage.warning("请输入数据源名称")
    return
  }
  if (sourceForm.max_score <= 0) {
    ElMessage.warning("满分值必须大于 0")
    return
  }
  if (isEditingSource.value && sourceForm.id) {
    updateExternalSourceApi(sourceForm.id, {
      source_name: sourceForm.source_name,
      max_score: sourceForm.max_score
    }).then(() => {
      ElMessage.success("修改成功")
      sourceDialogVisible.value = false
      loadExternalSources()
    })
  } else {
    createExternalSourceApi({
      class_id: selectedClassId.value,
      source_name: sourceForm.source_name,
      max_score: sourceForm.max_score
    }).then(() => {
      ElMessage.success("创建成功")
      sourceDialogVisible.value = false
      loadExternalSources()
    })
  }
}

function handleDeleteSource(source: ExternalScoreSource) {
  ElMessageBox.confirm(`确认删除数据源「${source.source_name}」？相关评分记录也将被删除。`, "提示", {
    confirmButtonText: "确定",
    cancelButtonText: "取消",
    type: "warning"
  }).then(() => {
    deleteExternalSourceApi(source.id).then(() => {
      ElMessage.success("删除成功")
      loadExternalSources()
    })
  })
}

// ============ 上传成绩 ============
const uploadSourceId = ref("")
const uploadRef = ref<any>(null)

function handleUploadChange(file: any) {
  if (!uploadSourceId.value) {
    ElMessage.warning("请先选择数据源")
    return
  }
  const rawFile = file.raw || file
  uploadExternalRecordsApi(uploadSourceId.value, rawFile).then(() => {
    ElMessage.success("导入成功")
  })
}

// ============ Tab 2: 评分结果 ============
const scoreResult = ref<ClassScoreResult | null>(null)
const searchName = ref("")

function loadScores() {
  if (!selectedClassId.value) return
  loading.value = true
  getClassScoresApi(selectedClassId.value).then(({ data }) => {
    scoreResult.value = data
  }).finally(() => { loading.value = false })
}

const filteredStudents = ref<any[]>([])
watch([scoreResult, searchName], () => {
  if (!scoreResult.value) {
    filteredStudents.value = []
    return
  }
  const kw = searchName.value.toLowerCase()
  filteredStudents.value = scoreResult.value.students.filter(s =>
    !kw || s.student_name.toLowerCase().includes(kw)
  )
}, { deep: true })

/** 获取启用的维度列表（用于动态表格列） */
function getEnabledDimensions(): string[] {
  if (!scoreResult.value) return []
  const config = scoreResult.value.config
  return DIMENSION_KEYS.filter(key => config[`${key}_enabled` as keyof ScoringConfig])
}

// ============ 导出 ============
function handleExport() {
  if (!scoreResult.value) return
  const dims = getEnabledDimensions()
  const headers = ["排名", "姓名", ...dims.map(d => `${DIMENSION_LABELS[d]}(${scoreResult.value!.config[`${d}_weight` as keyof ScoringConfig]}%)`), "总分"]
  const rows = scoreResult.value.students.map((s, i) => {
    const cells = [String(i + 1), s.student_name]
    dims.forEach(d => cells.push(String(s.dimensions[d] ?? 0)))
    cells.push(String(s.total_score))
    return cells.join("\t")
  })
  const csv = "﻿" + headers.join("\t") + "\n" + rows.join("\n")
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = "评分结果.csv"
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="app-container">
    <!-- 班级选择器（全局） -->
    <el-card shadow="never" class="class-selector-card">
      <div class="class-selector-row">
        <span class="selector-label">班级：</span>
        <el-select v-model="selectedClassId" placeholder="请选择班级" style="width: 280px" clearable>
          <el-option v-for="c in classOptions" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
      </div>
    </el-card>

    <!-- Tabs -->
    <el-card v-loading="loading" shadow="never" class="main-card">
      <el-tabs v-model="activeTab" @tab-change="(tab: string) => { if (tab === 'config') loadConfig(); if (tab === 'result') loadScores(); }">
        <!-- ============ Tab 1: 评分配置 ============ -->
        <el-tab-pane label="评分配置" name="config">
          <div v-if="!selectedClassId" class="empty-hint">请先选择班级</div>
          <template v-else>
            <div class="dimension-list">
              <div v-for="key in DIMENSION_KEYS" :key="key" class="dimension-row">
                <div class="dimension-left">
                  <el-switch v-model="dimensionEnabled[key]" size="large" />
                  <span class="dimension-label">{{ DIMENSION_LABELS[key] }}</span>
                </div>
                <div class="dimension-right">
                  <el-slider
                    v-model="dimensionWeight[key]"
                    :min="0"
                    :max="100"
                    :step="1"
                    :disabled="!dimensionEnabled[key]"
                    style="width: 200px"
                    show-input
                  />
                  <span class="weight-unit">%</span>
                </div>
              </div>
            </div>

            <div class="total-row">
              <span>已启用合计：</span>
              <span :class="['total-value', totalWeight !== 100 ? 'error' : 'ok']">
                {{ totalWeight }}%
              </span>
              <span v-if="totalWeight !== 100" class="error-hint">（必须等于 100%）</span>
            </div>

            <el-button
              type="primary"
              :disabled="totalWeight !== 100"
              :loading="loading"
              style="margin-top: 16px"
              @click="handleSaveConfig"
            >
              保存配置
            </el-button>

            <!-- 外部数据源（仅当启用时显示） -->
            <template v-if="dimensionEnabled['external']">
              <el-divider />
              <div class="section-title">外部数据源</div>

              <div style="margin-bottom: 12px; display: flex; gap: 12px; align-items: center">
                <el-button type="primary" :icon="Plus" size="small" @click="openAddSource">添加数据源</el-button>

                <span style="font-size: 13px; color: #909399">导入成绩：</span>
                <el-select v-model="uploadSourceId" placeholder="选择数据源" size="small" style="width: 180px" clearable>
                  <el-option v-for="s in externalSources" :key="s.id" :label="s.source_name" :value="s.id" />
                </el-select>
                <el-upload
                  ref="uploadRef"
                  :show-file-list="false"
                  :auto-upload="false"
                  :on-change="handleUploadChange"
                  accept=".xlsx,.xls"
                >
                  <el-button type="success" :icon="Upload" size="small" plain>上传 Excel</el-button>
                </el-upload>
                <span style="font-size: 11px; color: #c0c4cc">模板：学号 | 得分</span>
              </div>

              <el-table :data="externalSources" border stripe size="small">
                <el-table-column prop="source_name" label="数据源名称" min-width="160" />
                <el-table-column prop="max_score" label="满分" width="80" align="center" />
                <el-table-column label="操作" width="140" align="center">
                  <template #default="scope">
                    <el-button type="primary" text size="small" @click="openEditSource(scope.row)">编辑</el-button>
                    <el-button type="danger" text size="small" @click="handleDeleteSource(scope.row)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </template>
          </template>
        </el-tab-pane>

        <!-- ============ Tab 2: 评分结果 ============ -->
        <el-tab-pane label="评分结果" name="result">
          <div v-if="!selectedClassId" class="empty-hint">请先选择班级</div>
          <template v-else>
            <div class="toolbar-wrapper">
              <div class="toolbar-left">
                <el-input
                  v-model="searchName"
                  placeholder="搜索学生姓名"
                  :prefix-icon="Search"
                  clearable
                  style="width: 220px"
                />
              </div>
              <div class="toolbar-right">
                <el-button :icon="Refresh" @click="loadScores">刷新</el-button>
                <el-button type="primary" :icon="Download" @click="handleExport" :disabled="!scoreResult || scoreResult.students.length === 0">导出 CSV</el-button>
              </div>
            </div>

            <el-table :data="filteredStudents" border stripe highlight-current-row size="small">
              <el-table-column type="index" label="排名" width="60" align="center" />
              <el-table-column prop="student_name" label="姓名" min-width="100" fixed />
              <el-table-column
                v-for="dim in getEnabledDimensions()"
                :key="dim"
                :prop="`dimensions.${dim}`"
                :label="`${DIMENSION_LABELS[dim]}(${scoreResult?.config?.[`${dim}_weight` as keyof ScoringConfig]}%)`"
                min-width="110"
                align="center"
                sortable
              >
                <template #default="scope">
                  {{ scope.row.dimensions[dim] ?? 0 }}
                </template>
              </el-table-column>
              <el-table-column prop="total_score" label="总分" min-width="100" align="center" sortable>
                <template #default="scope">
                  <strong>{{ scope.row.total_score }}</strong>
                </template>
              </el-table-column>
            </el-table>

            <div v-if="scoreResult && scoreResult.students.length === 0" class="empty-hint">
              暂无评分数据
            </div>
          </template>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 添加/编辑外部数据源弹窗 -->
    <el-dialog
      v-model="sourceDialogVisible"
      :title="isEditingSource ? '编辑数据源' : '添加数据源'"
      width="400px"
    >
      <el-form ref="sourceFormRef" :model="sourceForm" label-width="100px">
        <el-form-item label="数据源名称" required>
          <el-input v-model="sourceForm.source_name" placeholder="如：学习通章节测验" />
        </el-form-item>
        <el-form-item label="满分值" required>
          <el-input-number v-model="sourceForm.max_score" :min="1" :max="10000" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="sourceDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveSource">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.class-selector-card {
  margin-bottom: 16px;
  .class-selector-row {
    display: flex;
    align-items: center;
    gap: 12px;
    .selector-label { font-weight: 500; font-size: 14px; }
  }
}

.main-card {
  :deep(.el-card__body) { padding: 20px 24px; }
}

.dimension-list {
  .dimension-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 0;
    border-bottom: 1px solid #f0f0f0;
    .dimension-left {
      display: flex;
      align-items: center;
      gap: 12px;
      .dimension-label { font-size: 14px; font-weight: 500; min-width: 80px; }
    }
    .dimension-right {
      display: flex;
      align-items: center;
      gap: 8px;
      .weight-unit { font-size: 14px; color: #909399; }
    }
  }
}

.total-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
  font-size: 15px;
  font-weight: 500;
  .total-value.ok { color: #67c23a; font-size: 18px; }
  .total-value.error { color: #f56c6c; font-size: 18px; }
  .error-hint { color: #f56c6c; font-size: 12px; }
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  margin: 16px 0 12px;
}

.toolbar-wrapper {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  .toolbar-left, .toolbar-right { display: flex; align-items: center; gap: 10px; }
}

.empty-hint {
  text-align: center;
  padding: 60px 0;
  color: #c0c4cc;
  font-size: 15px;
}
</style>
```

- [ ] **Step 2: 创建菜单图标 SVG**

创建 `management/web/src/common/assets/icons/scoring.svg`：

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2" />
  <rect x="9" y="3" width="6" height="4" rx="1" />
  <path d="M9 14l2 2 4-4" />
</svg>
```

- [ ] **Step 3: 注册路由**

在 `management/web/src/router/index.ts` 的 `constantRoutes` 数组中，找一个合适位置（建议在 `/conversation` 路由之后）添加：

```ts
{
  path: "/scoring",
  component: Layouts,
  redirect: "/scoring/index",
  children: [
    {
      path: "index",
      component: () => import("@/pages/scoring/index.vue"),
      name: "ScoringManagement",
      meta: {
        title: "评分管理",
        svgIcon: "scoring",
        affix: false,
        keepAlive: true
      }
    }
  ]
},
```

- [ ] **Step 4: 提交**

```bash
git add management/web/src/pages/scoring/index.vue \
        management/web/src/common/assets/icons/scoring.svg \
        management/web/src/router/index.ts
git commit -m "feat: add scoring management page with config and results tabs

Co-Authored-By: Claude <noreply@anthropic.com>"
```
