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
