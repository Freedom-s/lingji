import json
import mysql.connector
import pytz
from datetime import date, datetime
from utils import generate_uuid
from database import DB_CONFIG
from auth import get_current_user


def _get_utc8_time():
    utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
    target_tz = pytz.timezone('Asia/Shanghai')
    local_dt = utc_now.astimezone(target_tz)
    return int(local_dt.timestamp() * 1000), local_dt.strftime("%Y-%m-%d %H:%M:%S")


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


def get_teacher_progress_reminders():
    """获取当前老师所有周进度的完成提醒，用于后台首页。"""
    current_user = get_current_user()
    if not current_user:
        return False, "获取用户信息失败"

    user_id = current_user["user_id"]
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT wp.id
            FROM weekly_progress wp
            JOIN class c ON wp.class_id = c.id
            WHERE c.tenant_id = %s AND wp.status = '1'
            ORDER BY wp.week_end ASC, wp.week_start ASC
            """,
            (user_id,),
        )
        progress_ids = [row["id"] for row in cursor.fetchall()]
        cursor.close()
        conn.close()

        items = []
        today = date.today()
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

            if today < start_date:
                state = "upcoming"
                day_count = (start_date - today).days
            elif today > end_date:
                state = "overdue"
                day_count = (today - end_date).days
            else:
                state = "active"
                day_count = (end_date - today).days

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
