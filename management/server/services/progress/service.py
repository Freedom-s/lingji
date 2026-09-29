import json
import mysql.connector
import pytz
from datetime import date, datetime
from utils import generate_uuid
from database import DB_CONFIG
from auth import get_current_user


_PROGRESS_STATUS_QUERY = """
    SELECT sps.student_id, u.nickname as student_name, sps.doc_id,
           sps.is_completed, sps.video_completed, sps.quiz_passed, sps.has_notes
    FROM student_progress_status sps
    JOIN user u ON sps.student_id = u.id
    JOIN weekly_progress wp ON wp.id = sps.progress_id
    JOIN user_class uc
      ON uc.class_id = wp.class_id
     AND uc.user_id = sps.student_id
     AND uc.role = 'student'
     AND uc.status = '1'
    WHERE sps.progress_id = %s
    ORDER BY u.nickname
"""


def _get_utc8_time():
    utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
    target_tz = pytz.timezone('Asia/Shanghai')
    local_dt = utc_now.astimezone(target_tz)
    return int(local_dt.timestamp() * 1000), local_dt.strftime("%Y-%m-%d %H:%M:%S")


def _get_utc8_today():
    utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
    return utc_now.astimezone(pytz.timezone('Asia/Shanghai')).date()


def _get_progress_state(start_date, end_date, today):
    if today < start_date:
        return "upcoming", (start_date - today).days
    if today > end_date:
        return "overdue", (today - end_date).days
    return "active", (end_date - today).days


def _evaluate_quiz_completion(total_questions, answered_questions, correct_questions, threshold):
    """按原题数计算达标率：每道题答对过一次即可记为正确。"""
    total_questions = int(total_questions or 0)
    answered_questions = int(answered_questions or 0)
    correct_questions = int(correct_questions or 0)
    threshold = float(threshold or 0)
    quiz_rate = round(correct_questions / total_questions * 100, 1) if total_questions else 0.0
    quiz_passed = (
        total_questions > 0
        and answered_questions >= total_questions
        and quiz_rate >= threshold
    )
    return quiz_rate, quiz_passed


def get_weekly_progress_list(class_id):
    try:
        current_user = get_current_user()
        if not current_user:
            return []
        user_id = current_user["user_id"]

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 校验班级归属
        cursor.execute("SELECT id FROM class WHERE id = %s AND tenant_id = %s", (class_id, user_id))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return []

        cursor.execute(
            "SELECT id, class_id, name, week_start, week_end, status, create_date "
            "FROM weekly_progress WHERE class_id = %s ORDER BY week_start DESC",
            (class_id,)
        )
        rows = cursor.fetchall()
        # 转换 date 类型为字符串
        for r in rows:
            if isinstance(r.get("week_start"), (date, datetime)):
                r["week_start"] = r["week_start"].strftime("%Y-%m-%d")
            if isinstance(r.get("week_end"), (date, datetime)):
                r["week_end"] = r["week_end"].strftime("%Y-%m-%d")
        cursor.close()
        conn.close()
        return rows
    except mysql.connector.Error as err:
        print(f"获取周进度列表失败: {err}")
        return []


def create_weekly_progress(class_id, data):
    """保留原单班级接口的返回格式。"""
    success, result = create_weekly_progresses([class_id], data, validate_docs=False)
    return (success, result[class_id]) if success else (False, result)


def _class_document_ids(cursor, class_id):
    """班级通过关联的智能体可使用的有效文档。"""
    cursor.execute(
        "SELECT d.kb_ids FROM class_dialog cd JOIN dialog d ON d.id = cd.dialog_id "
        "WHERE cd.class_id = %s", (class_id,)
    )
    kb_ids = set()
    for row in cursor.fetchall():
        value = row.get("kb_ids")
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (ValueError, TypeError):
                value = []
        if isinstance(value, list):
            kb_ids.update(kb_id for kb_id in value if kb_id)
    if not kb_ids:
        return set()
    placeholders = ", ".join(["%s"] * len(kb_ids))
    cursor.execute(
        f"SELECT id FROM document WHERE kb_id IN ({placeholders}) AND status = '1'",
        tuple(sorted(kb_ids)),
    )
    return {row["id"] for row in cursor.fetchall()}


def create_weekly_progresses(class_ids, data, validate_docs=True):
    """在一个事务中为多个班级创建同一周进度；重复请求返回原有 ID。"""
    if not isinstance(class_ids, list) or not class_ids or any(
        not isinstance(class_id, str) or not class_id.strip() for class_id in class_ids
    ):
        return False, "至少选择1个班级"
    if len(class_ids) != len(set(class_ids)):
        return False, "班级不能重复选择"
    if not isinstance(data, dict):
        return False, "请求体格式错误"
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        return False, "名称不能为空"
    name = name.strip()
    try:
        week_start = date.fromisoformat(data.get("week_start", ""))
        week_end = date.fromisoformat(data.get("week_end", ""))
    except (TypeError, ValueError):
        return False, "日期格式错误"
    if week_start > week_end:
        return False, "开始日期不能晚于截止日期"
    doc_ids = data.get("doc_ids")
    if not isinstance(doc_ids, list) or not doc_ids or any(
        not isinstance(doc_id, str) or not doc_id for doc_id in doc_ids
    ):
        return False, "至少选择1个文档"
    if len(doc_ids) != len(set(doc_ids)):
        return False, "文档不能重复选择"
    quiz_thresholds = data.get("quiz_thresholds", {})
    if not isinstance(quiz_thresholds, dict):
        return False, "测验达标分数格式错误"
    try:
        thresholds = {doc_id: int(quiz_thresholds.get(doc_id, 0)) for doc_id in doc_ids}
    except (ValueError, TypeError):
        return False, "测验达标分数格式错误"
    if any(value < 0 or value > 100 for value in thresholds.values()):
        return False, "测验达标分数须在0到100之间"

    conn = None
    cursor = None
    committed = False
    try:
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"
        user_id = current_user["user_id"]

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        # 按固定顺序锁定班级行，串行化同一班级的创建及重复请求。
        for class_id in sorted(class_ids):
            cursor.execute(
                "SELECT id FROM class WHERE id = %s AND tenant_id = %s FOR UPDATE",
                (class_id, user_id),
            )
            if not cursor.fetchone():
                return False, "班级不存在或无权操作"

        # 批量创建时，资料须对每个目标班级可见。单班级旧接口保留原有行为。
        if validate_docs:
            for class_id in class_ids:
                if not set(doc_ids).issubset(_class_document_ids(cursor, class_id)):
                    return False, "所选文档并非每个班级都可使用"

        existing = {}
        for class_id in class_ids:
            cursor.execute(
                "SELECT id FROM weekly_progress WHERE class_id = %s AND name = %s "
                "AND week_start = %s AND week_end = %s FOR UPDATE",
                (class_id, name, week_start, week_end),
            )
            rows = cursor.fetchall()
            if rows:
                if len(rows) != 1:
                    return False, "所选班级已有同名、同日期的周进度"
                existing[class_id] = rows[0]["id"]

        if existing:
            if len(existing) != len(class_ids):
                return False, "部分班级已有同名、同日期的周进度，请检查后重试"
            for progress_id in existing.values():
                cursor.execute(
                    "SELECT doc_id, quiz_threshold FROM weekly_progress_doc WHERE progress_id = %s",
                    (progress_id,),
                )
                if {row["doc_id"]: row["quiz_threshold"] for row in cursor.fetchall()} != thresholds:
                    return False, "所选班级已有同名、同日期但内容不同的周进度"
            return True, existing

        ct_ms, ct_date = _get_utc8_time()
        created = {}
        for class_id in class_ids:
            progress_id = generate_uuid()
            created[class_id] = progress_id
            cursor.execute(
                "INSERT INTO weekly_progress (id, class_id, name, week_start, week_end, status, create_time, create_date, update_time, update_date) "
                "VALUES (%s, %s, %s, %s, %s, '1', %s, %s, %s, %s)",
                (progress_id, class_id, name, week_start, week_end, ct_ms, ct_date, ct_ms, ct_date),
            )
            for doc_id in doc_ids:
                cursor.execute(
                    "INSERT INTO weekly_progress_doc (id, progress_id, doc_id, quiz_threshold, create_time, create_date, update_time, update_date) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (generate_uuid(), progress_id, doc_id, thresholds[doc_id], ct_ms, ct_date, ct_ms, ct_date),
                )

        conn.commit()
        committed = True
        return True, created

    except mysql.connector.Error as err:
        print(f"创建周进度失败: {err}")
        return False, str(err)
    finally:
        if conn:
            if not committed:
                conn.rollback()
            if cursor:
                cursor.close()
            conn.close()


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


def get_class_documents(class_id):
    """获取班级关联的所有文档（含名称、类型、是否有测验）"""
    try:
        current_user = get_current_user()
        if not current_user:
            return []
        user_id = current_user["user_id"]

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 校验班级归属
        cursor.execute("SELECT id FROM class WHERE id = %s AND tenant_id = %s", (class_id, user_id))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return []

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
        quiz_question_counts = {}
        if doc_ids:
            placeholders = ", ".join(["%s"] * len(doc_ids))
            cursor.execute(
                f"SELECT doc_id, content FROM document_generation WHERE doc_id IN ({placeholders}) AND generation_type = 'quiz'",
                doc_ids
            )
            for row in cursor.fetchall():
                doc_id = row["doc_id"]
                has_quiz_docs.add(doc_id)
                try:
                    questions = json.loads(row.get("content") or "[]")
                    quiz_question_counts[doc_id] = len(questions) if isinstance(questions, list) else 0
                except (TypeError, json.JSONDecodeError):
                    quiz_question_counts[doc_id] = 0

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
                        "SELECT COUNT(*) as cnt, COUNT(DISTINCT question_index) as answered_questions, "
                        "COUNT(DISTINCT CASE WHEN is_correct = 1 THEN question_index END) as correct_questions "
                        "FROM student_quiz_result "
                        "WHERE student_id = %s AND doc_id = %s",
                        (sid, did)
                    )
                    qr = cursor.fetchone()
                    answered_questions = int(qr["answered_questions"] or 0)
                    correct_questions = int(qr["correct_questions"] or 0)
                    total_questions = quiz_question_counts.get(did, 0)
                    rate, quiz_passed = _evaluate_quiz_completion(
                        total_questions,
                        answered_questions,
                        correct_questions,
                        threshold,
                    )

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

        if isinstance(progress.get("week_start"), (date, datetime)):
            progress["week_start"] = progress["week_start"].strftime("%Y-%m-%d")
        if isinstance(progress.get("week_end"), (date, datetime)):
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
        cursor.execute(_PROGRESS_STATUS_QUERY, (progress_id,))
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


def get_teacher_progress_reminders(class_id=None, progress_id=None):
    """获取当前老师所有周进度的完成提醒，用于后台首页。"""
    current_user = get_current_user()
    if not current_user:
        return False, "获取用户信息失败"

    user_id = current_user["user_id"]
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        conditions = ["c.tenant_id = %s", "wp.status = '1'"]
        query_params = [user_id]
        if class_id:
            conditions.append("wp.class_id = %s")
            query_params.append(class_id)
        if progress_id:
            conditions.append("wp.id = %s")
            query_params.append(progress_id)

        cursor.execute(
            f"""
            SELECT wp.id
            FROM weekly_progress wp
            JOIN class c ON wp.class_id = c.id
            WHERE {' AND '.join(conditions)}
            ORDER BY wp.week_end ASC, wp.week_start ASC
            """,
            tuple(query_params),
        )
        progress_ids = [row["id"] for row in cursor.fetchall()]
        cursor.close()
        conn.close()

        items = []
        today = _get_utc8_today()
        for progress_id in progress_ids:
            success, result = get_progress_status(progress_id)
            if not success:
                continue

            progress = result["progress"]
            start_value = progress.get("week_start")
            end_value = progress.get("week_end")
            start_date = (
                start_value.date() if isinstance(start_value, datetime)
                else start_value if isinstance(start_value, date)
                else datetime.strptime(str(start_value)[:10], "%Y-%m-%d").date()
            )
            end_date = (
                end_value.date() if isinstance(end_value, datetime)
                else end_value if isinstance(end_value, date)
                else datetime.strptime(str(end_value)[:10], "%Y-%m-%d").date()
            )

            state, day_count = _get_progress_state(start_date, end_date, today)

            completed_students = []
            incomplete_students = []
            for student in result["students"]:
                target = completed_students if student["is_all_completed"] else incomplete_students
                target.append({
                    "student_id": student["student_id"],
                    "student_name": student["student_name"],
                    "completed_docs": student["total_completed"],
                    "total_docs": student["total_docs"],
                })

            summary = result["summary"]
            items.append({
                "id": progress["id"],
                "class_id": progress["class_id"],
                "class_name": progress.get("class_name", ""),
                "name": progress["name"],
                "week_start": start_date.strftime("%Y-%m-%d"),
                "week_end": end_date.strftime("%Y-%m-%d"),
                "state": state,
                "day_count": day_count,
                "total_students": summary["total_students"],
                "completed_count": summary["completed_count"],
                "incomplete_count": summary["incomplete_count"],
                "completion_rate": summary["completion_rate"],
                "completed_students": completed_students,
                "incomplete_students": incomplete_students,
            })

        state_priority = {"overdue": 0, "active": 1, "upcoming": 2}
        items.sort(key=lambda item: (
            item["incomplete_count"] == 0,
            state_priority[item["state"]],
            item["week_end"],
        ))
        return True, {
            "summary": {
                "total_progresses": len(items),
                "attention_progresses": sum(1 for item in items if item["incomplete_count"] > 0),
                "overdue_progresses": sum(
                    1 for item in items
                    if item["state"] == "overdue" and item["incomplete_count"] > 0
                ),
                "total_incomplete_students": sum(item["incomplete_count"] for item in items),
            },
            "items": items,
        }
    except (mysql.connector.Error, ValueError) as err:
        print(f"获取教师进度提醒失败: {err}")
        return False, str(err)


def get_teacher_progress_overview(class_id=None):
    """汇总学生跨周进度，用于教师查看整体跟进情况。"""
    success, reminder_result = get_teacher_progress_reminders(class_id=class_id)
    if not success:
        return False, reminder_result

    items = reminder_result.get("items", [])
    ordered_items = sorted(
        items,
        key=lambda item: (item["week_start"], item["week_end"], item["name"]),
    )
    state_priority = {"overdue": 0, "active": 1, "upcoming": 2}
    progress_groups = []
    progress_group_map = {}
    for item in ordered_items:
        group_key = (item["name"], item["week_start"], item["week_end"])
        group = progress_group_map.get(group_key)
        if group is None:
            group = {"key": group_key, "items": []}
            progress_group_map[group_key] = group
            progress_groups.append(group)
        group["items"].append(item)

    progress_columns = [
        {
            "id": "|".join(group["key"]),
            "name": group["key"][0],
            "week_start": group["key"][1],
            "week_end": group["key"][2],
            "state": min(
                (item["state"] for item in group["items"]),
                key=lambda state: state_priority[state],
            ),
        }
        for group in progress_groups
    ]

    student_map = {}
    for item in ordered_items:
        group_key = (item["name"], item["week_start"], item["week_end"])
        student_statuses = {
            student["student_id"]: ("completed", student)
            for student in item["completed_students"]
        }
        student_statuses.update({
            student["student_id"]: (
                "partial" if student["completed_docs"] > 0 else "not_started",
                student,
            )
            for student in item["incomplete_students"]
        })

        for student_id, (progress_status, student) in student_statuses.items():
            key = (item["class_id"], student_id)
            row = student_map.setdefault(
                key,
                {
                    "student_id": student_id,
                    "student_name": student["student_name"],
                    "class_id": item["class_id"],
                    "class_name": item["class_name"],
                    "progress_by_key": {},
                },
            )
            row["progress_by_key"][group_key] = {
                "progress_id": item["id"],
                "name": item["name"],
                "week_start": item["week_start"],
                "week_end": item["week_end"],
                "state": item["state"],
                "status": progress_status,
                "completed_docs": student["completed_docs"],
                "total_docs": student["total_docs"],
            }

    students = []
    for row in student_map.values():
        progress_rows = [
            row["progress_by_key"].get(group["key"], {
                "progress_id": "",
                "name": group["key"][0],
                "week_start": group["key"][1],
                "week_end": group["key"][2],
                "state": "unassigned",
                "status": "unassigned",
                "completed_docs": 0,
                "total_docs": 0,
            })
            for group in progress_groups
        ]
        assigned_rows = [item for item in progress_rows if item["state"] != "unassigned"]
        tracked_rows = [
            item for item in assigned_rows
            if item["state"] != "upcoming"
        ]
        completed_count = sum(1 for item in tracked_rows if item["status"] == "completed")
        partial_count = sum(1 for item in tracked_rows if item["status"] == "partial")
        not_started_count = sum(1 for item in tracked_rows if item["status"] == "not_started")
        completed_task_count = sum(item["completed_docs"] for item in tracked_rows)
        total_task_count = sum(item["total_docs"] for item in tracked_rows)
        overdue_count = sum(
            1
            for item in tracked_rows
            if item["state"] == "overdue" and item["status"] != "completed"
        )

        consecutive_incomplete = 0
        for item in reversed(tracked_rows):
            if item["status"] == "completed":
                break
            consecutive_incomplete += 1

        if not tracked_rows:
            overall_status = "upcoming"
        elif completed_count == len(tracked_rows):
            overall_status = "completed"
        elif completed_count == 0 and partial_count == 0:
            overall_status = "not_started"
        else:
            overall_status = "partial"

        row.update({
            "status": overall_status,
            "total_progresses": len(assigned_rows),
            "tracked_progresses": len(tracked_rows),
            "completed_progresses": completed_count,
            "partial_progresses": partial_count,
            "not_started_progresses": not_started_count,
            "overdue_progresses": overdue_count,
            "consecutive_incomplete_progresses": consecutive_incomplete,
            "completion_rate": (
                round(completed_task_count / total_task_count * 100, 1)
                if total_task_count
                else 0.0
            ),
            "progresses": progress_rows,
        })
        row.pop("progress_by_key")
        students.append(row)

    status_priority = {"not_started": 0, "partial": 1, "upcoming": 2, "completed": 3}
    students.sort(key=lambda row: (
        row["completion_rate"],
        -row["overdue_progresses"],
        status_priority[row["status"]],
        -row["consecutive_incomplete_progresses"],
        row["student_name"],
    ))

    return True, {
        "summary": {
            "total_students": len(students),
            "completed_students": sum(1 for row in students if row["status"] == "completed"),
            "partial_students": sum(1 for row in students if row["status"] == "partial"),
            "not_started_students": sum(1 for row in students if row["status"] == "not_started"),
            "upcoming_students": sum(1 for row in students if row["status"] == "upcoming"),
            "overdue_incomplete_students": sum(
                1 for row in students if row["overdue_progresses"] > 0
            ),
            "total_progresses": len(progress_columns),
        },
        "progresses": progress_columns,
        "students": students,
    }
