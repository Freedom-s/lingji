import json
from collections import defaultdict
from datetime import datetime, timedelta
from database import get_db_connection


VALID_TIME_RANGES = {"24h", "7d", "30d"}


def _normalize_time_range(time_range):
    return time_range if time_range in VALID_TIME_RANGES else "7d"


def _date_condition(column, time_range):
    normalized = _normalize_time_range(time_range)
    if normalized == "24h":
        return f"{column} >= DATE_SUB(NOW(), INTERVAL 24 HOUR)"
    if normalized == "30d":
        return f"{column} >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
    return f"{column} >= DATE_SUB(NOW(), INTERVAL 7 DAY)"


def _decode_json_list(value):
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        decoded = json.loads(value)
        if isinstance(decoded, dict):
            decoded = decoded.get("questions", [])
        return decoded if isinstance(decoded, list) else []
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def _build_quiz_lookup(rows):
    """将文档测验内容转成 (doc_id, question_index) -> 题目，兼容旧题目 ID。"""
    lookup = {}
    for row in rows:
        questions = _decode_json_list(row.get("content"))
        for position, question in enumerate(questions):
            if not isinstance(question, dict):
                continue
            question_id = question.get("id", position)
            lookup[(str(row.get("doc_id")), str(question_id))] = question
            lookup.setdefault((str(row.get("doc_id")), str(position)), question)
    return lookup


def _answer_text(question, answer):
    if not answer:
        return "未作答"
    options = question.get("options") if isinstance(question, dict) else None
    option_text = options.get(str(answer)) if isinstance(options, dict) else None
    return f"{answer}. {option_text}" if option_text else str(answer)


def _answer_explanation(question, answer):
    if not isinstance(question, dict) or not answer:
        return ""
    explanations = question.get("explanations")
    if not isinstance(explanations, dict):
        return ""
    answer_key = str(answer).strip().upper()
    return str(explanations.get(answer_key) or explanations.get(str(answer)) or "")


def _format_dashboard_time(value):
    if not value:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def get_dashboard_overview(tenant_id: str):
    """获取dashboard概览数据（6个基础指标）"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        result = {}

        # 1. 学生数：统计user_tenant中role='normal'且tenant_id=当前租户的数量
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) as count
            FROM user_tenant
            WHERE tenant_id = %s AND role = 'normal' AND status = '1'
        """, (tenant_id,))
        result["student_count"] = cursor.fetchone()["count"]

        # 2. 班级数：统计class表中tenant_id=当前租户的数量
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM class
            WHERE tenant_id = %s AND status = '1'
        """, (tenant_id,))
        result["class_count"] = cursor.fetchone()["count"]

        # 3. 会话数：统计当前租户下所有conversation的数量
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM conversation c
            JOIN dialog d ON c.dialog_id = d.id
            WHERE d.tenant_id = %s
        """, (tenant_id,))
        result["conversation_count"] = cursor.fetchone()["count"]

        # 4. 助教数：统计dialog表中tenant_id=当前租户的数量
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM dialog
            WHERE tenant_id = %s AND status = '1'
        """, (tenant_id,))
        result["assistant_count"] = cursor.fetchone()["count"]

        # 5. 文件数：统计file表中tenant_id=当前租户的数量
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM file
            WHERE tenant_id = %s
        """, (tenant_id,))
        result["file_count"] = cursor.fetchone()["count"]

        # 6. 知识库数量：统计knowledgebase表中tenant_id=当前租户的数量
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM knowledgebase
            WHERE tenant_id = %s AND status = '1'
        """, (tenant_id,))
        result["knowledgebase_count"] = cursor.fetchone()["count"]

        return True, result

    except Exception as e:
        return False, str(e)
    finally:
        cursor.close()
        conn.close()


def get_active_students_chart(tenant_id: str, time_range: str = "24h"):
    """获取活跃学生数趋势图数据"""
    from datetime import datetime, timedelta
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # 根据时间范围确定时间间隔和分组条件
        if time_range == "24h":
            # 过去24小时，按小时分组
            time_unit = "%Y-%m-%d %H:00:00"
            hours = 24
            delta = timedelta(hours=1)
            date_format = "%Y-%m-%d %H:00:00"
        elif time_range == "7d":
            # 过去7天，按天分组
            time_unit = "%Y-%m-%d"
            days = 7
            delta = timedelta(days=1)
            date_format = "%Y-%m-%d"
        else:  # 30d
            # 过去30天，按天分组
            time_unit = "%Y-%m-%d"
            days = 30
            delta = timedelta(days=1)
            date_format = "%Y-%m-%d"

        # 构建时间筛选条件
        if time_range == "24h":
            activity_date_condition = f"activity.activity_time >= DATE_SUB(NOW(), INTERVAL {hours} HOUR)"
            start_time = datetime.now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=hours - 1)
        else:
            activity_date_condition = f"activity.activity_time >= DATE_SUB(CURDATE(), INTERVAL {days - 1} DAY)"
            start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days-1)

        # 查询活跃学生数（按时间分组）。当天看过视频、记过笔记、答过闪卡、
        # 完成答题或产生过对话，均算活跃；同一时间桶内重复活动只计 1 人。
        query = f"""
            SELECT
                DATE_FORMAT(activity.activity_time, '{time_unit}') AS time_label,
                COUNT(DISTINCT activity.user_id) as active_count
            FROM (
                SELECT
                    sqr.student_id AS user_id,
                    COALESCE(sqr.create_date, FROM_UNIXTIME(sqr.create_time)) AS activity_time
                FROM student_quiz_result sqr
                JOIN document doc ON doc.id = sqr.doc_id
                JOIN knowledgebase kb ON kb.id = doc.kb_id
                WHERE kb.tenant_id = %s

                UNION ALL

                SELECT
                    conv.user_id AS user_id,
                    COALESCE(conv.update_date, conv.create_date, FROM_UNIXTIME(conv.update_time), FROM_UNIXTIME(conv.create_time)) AS activity_time
                FROM conversation conv
                JOIN dialog d ON d.id = conv.dialog_id
                WHERE d.tenant_id = %s

                UNION ALL

                SELECT
                    svp.student_id AS user_id,
                    COALESCE(svp.update_date, svp.create_date, FROM_UNIXTIME(svp.update_time), FROM_UNIXTIME(svp.create_time)) AS activity_time
                FROM student_video_progress svp
                JOIN document doc ON doc.id = svp.doc_id
                JOIN knowledgebase kb ON kb.id = doc.kb_id
                WHERE kb.tenant_id = %s

                UNION ALL

                SELECT
                    sn.student_id AS user_id,
                    COALESCE(sn.update_date, sn.create_date, FROM_UNIXTIME(sn.update_time), FROM_UNIXTIME(sn.create_time)) AS activity_time
                FROM student_note sn
                JOIN document doc ON doc.id = sn.doc_id
                JOIN knowledgebase kb ON kb.id = doc.kb_id
                WHERE kb.tenant_id = %s

                UNION ALL

                SELECT
                    scp.student_id AS user_id,
                    COALESCE(scp.update_date, scp.create_date, FROM_UNIXTIME(scp.update_time), FROM_UNIXTIME(scp.create_time)) AS activity_time
                FROM student_card_progress scp
                JOIN document doc ON doc.id = scp.doc_id
                JOIN knowledgebase kb ON kb.id = doc.kb_id
                WHERE kb.tenant_id = %s
            ) activity
            JOIN user_tenant ut
              ON ut.user_id = activity.user_id
             AND ut.tenant_id = %s
             AND ut.role = 'normal'
             AND ut.status = '1'
            WHERE {activity_date_condition}
            GROUP BY time_label
            ORDER BY time_label
        """
        cursor.execute(query, (tenant_id, tenant_id, tenant_id, tenant_id, tenant_id, tenant_id))
        results = cursor.fetchall()

        # 将查询结果转为字典，方便查找
        data_dict = {r["time_label"]: r["active_count"] for r in results}

        # 生成完整的时间序列
        data = []
        if time_range == "24h":
            current = start_time
            for _ in range(hours):
                time_label = current.strftime(date_format)
                data.append({
                    "time": time_label,
                    "count": data_dict.get(time_label, 0)
                })
                current += delta
        else:  # 7d 或 30d
            current = start_time
            for _ in range(days):
                time_label = current.strftime(date_format)
                data.append({
                    "time": time_label,
                    "count": data_dict.get(time_label, 0)
                })
                current += delta

        return True, data

    except Exception as e:
        return False, str(e)
    finally:
        cursor.close()
        conn.close()


def get_conversation_trend_chart(tenant_id: str, time_range: str = "24h"):
    """获取会话数趋势图数据"""
    from datetime import datetime, timedelta
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # 根据时间范围确定时间间隔和分组条件
        if time_range == "24h":
            # 过去24小时，按小时分组
            time_unit = "%Y-%m-%d %H:00:00"
            hours = 24
            delta = timedelta(hours=1)
            date_format = "%Y-%m-%d %H:00:00"
        elif time_range == "7d":
            # 过去7天，按天分组
            time_unit = "%Y-%m-%d"
            days = 7
            delta = timedelta(days=1)
            date_format = "%Y-%m-%d"
        else:  # 30d
            # 过去30天，按天分组
            time_unit = "%Y-%m-%d"
            days = 30
            delta = timedelta(days=1)
            date_format = "%Y-%m-%d"

        # 构建时间筛选条件
        if time_range == "24h":
            time_filter = f"DATE_FORMAT(c.create_date, '{time_unit}')"
            date_condition = f"c.create_date >= DATE_SUB(NOW(), INTERVAL {hours} HOUR)"
            start_time = datetime.now() - timedelta(hours=hours)
        else:
            time_filter = f"DATE_FORMAT(c.create_date, '{time_unit}')"
            date_condition = f"c.create_date >= DATE_SUB(CURDATE(), INTERVAL {days} DAY)"
            start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days-1)

        # 查询会话数趋势
        query = f"""
            SELECT
                {time_filter} as time_label,
                COUNT(*) as conversation_count
            FROM conversation c
            JOIN dialog d ON c.dialog_id = d.id
            WHERE d.tenant_id = %s
                AND {date_condition}
            GROUP BY time_label
            ORDER BY time_label
        """
        cursor.execute(query, (tenant_id,))
        results = cursor.fetchall()

        # 将查询结果转为字典，方便查找
        data_dict = {r["time_label"]: r["conversation_count"] for r in results}

        # 生成完整的时间序列
        data = []
        if time_range == "24h":
            current = start_time
            for _ in range(hours):
                time_label = current.strftime(date_format)
                data.append({
                    "time": time_label,
                    "count": data_dict.get(time_label, 0)
                })
                current += delta
        else:  # 7d 或 30d
            current = start_time
            for _ in range(days):
                time_label = current.strftime(date_format)
                data.append({
                    "time": time_label,
                    "count": data_dict.get(time_label, 0)
                })
                current += delta

        return True, data

    except Exception as e:
        return False, str(e)
    finally:
        cursor.close()
        conn.close()


def get_assistant_ranking(tenant_id: str, limit: int = 10, time_range: str = "24h"):
    """获取最受欢迎的AI助教排行榜"""
    import json
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        if time_range == "24h":
            date_condition = "c.create_date >= DATE_SUB(NOW(), INTERVAL 24 HOUR)"
        elif time_range == "7d":
            date_condition = "c.create_date >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
        else:
            date_condition = "c.create_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)"

        query = f"""
            SELECT
                d.id as assistant_id,
                d.name as assistant_name,
                d.icon as assistant_icon,
                c.reference
            FROM dialog d
            LEFT JOIN conversation c ON d.id = c.dialog_id AND {date_condition}
            WHERE d.tenant_id = %s AND d.status = '1'
        """
        cursor.execute(query, (tenant_id,))
        results = cursor.fetchall()

        assistant_stats = {}
        for row in results:
            assistant_id = row["assistant_id"]
            if assistant_id not in assistant_stats:
                assistant_stats[assistant_id] = {
                    "assistant_id": assistant_id,
                    "assistant_name": row["assistant_name"],
                    "assistant_icon": row["assistant_icon"],
                    "call_count": 0
                }

            if row["reference"]:
                try:
                    reference_data = json.loads(row["reference"])
                    if isinstance(reference_data, list):
                        for item in reference_data:
                            if isinstance(item, dict) and "total" in item:
                                assistant_stats[assistant_id]["call_count"] += item["total"]
                except (json.JSONDecodeError, TypeError, KeyError):
                    pass

        data = list(assistant_stats.values())
        data.sort(key=lambda x: x["call_count"], reverse=True)
        data = data[:limit]

        return True, data

    except Exception as e:
        return False, str(e)
    finally:
        cursor.close()
        conn.close()


def get_class_activity_ranking(tenant_id: str, limit: int = 10, time_range: str = "24h"):
    """获取班级活跃度排行榜"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        if time_range == "24h":
            date_condition = "conv.create_date >= DATE_SUB(NOW(), INTERVAL 24 HOUR)"
        elif time_range == "7d":
            date_condition = "conv.create_date >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
        else:
            date_condition = "conv.create_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)"

        query = f"""
            SELECT
                c.id as class_id,
                c.name as class_name,
                COUNT(DISTINCT conv.id) as conversation_count
            FROM class c
            LEFT JOIN user_class uc ON c.id = uc.class_id AND uc.role = 'student'
            LEFT JOIN conversation conv ON uc.user_id = conv.user_id AND {date_condition}
            WHERE c.tenant_id = %s AND c.status = '1'
            GROUP BY c.id, c.name
            ORDER BY conversation_count DESC
            LIMIT %s
        """
        cursor.execute(query, (tenant_id, limit))
        results = cursor.fetchall()

        data = [
            {
                "class_id": r["class_id"],
                "class_name": r["class_name"],
                "conversation_count": r["conversation_count"]
            }
            for r in results
        ]

        return True, data

    except Exception as e:
        return False, str(e)
    finally:
        cursor.close()
        conn.close()


def get_learning_insights(
    tenant_id: str,
    time_range: str = "7d",
    class_id: str = "",
    progress_id: str = "",
    limit: int = 10,
):
    """教师端学习洞察：学生答题/提问活跃度与高频错题。"""
    normalized_range = _normalize_time_range(time_range)
    limit = min(max(int(limit), 1), 50)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        selected_progress = None
        if progress_id:
            cursor.execute(
                """
                SELECT wp.id, wp.class_id, wp.name, wp.week_start, wp.week_end, c.name AS class_name
                FROM weekly_progress wp
                JOIN class c ON c.id = wp.class_id
                WHERE wp.id = %s AND c.tenant_id = %s AND c.status = '1' AND wp.status = '1'
                """,
                (progress_id, tenant_id),
            )
            selected_progress = cursor.fetchone()
            if not selected_progress:
                return False, "周进度不存在或不属于当前老师"
            # 学习洞察按周统计，不再把周进度所属班级作为额外限制。
            class_id = ""

        cursor.execute(
            """
            SELECT id, name
            FROM class
            WHERE tenant_id = %s AND status = '1'
            ORDER BY name ASC
            """,
            (tenant_id,),
        )
        classes = cursor.fetchall()

        student_where = ["c.tenant_id = %s", "c.status = '1'", "uc.role = 'student'", "uc.status = '1'"]
        student_params = [tenant_id]
        if class_id:
            student_where.append("c.id = %s")
            student_params.append(class_id)

        cursor.execute(
            f"""
            SELECT
                u.id,
                u.nickname,
                u.email,
                GROUP_CONCAT(DISTINCT c.id ORDER BY c.name SEPARATOR ',') AS class_ids,
                GROUP_CONCAT(DISTINCT c.name ORDER BY c.name SEPARATOR '、') AS class_names
            FROM class c
            JOIN user_class uc ON uc.class_id = c.id
            JOIN user u ON u.id = uc.user_id
            WHERE {' AND '.join(student_where)}
            GROUP BY u.id, u.nickname, u.email
            ORDER BY u.nickname ASC, u.email ASC
            """,
            tuple(student_params),
        )
        student_rows = cursor.fetchall()
        student_ids = [row["id"] for row in student_rows]
        student_stats = defaultdict(lambda: {
            "quiz_attempts": 0,
            "correct_answers": 0,
            "wrong_answers": 0,
            "question_count": 0,
            "last_active_at": None,
        })

        wrong_questions = []
        all_questions = []
        if student_ids:
            placeholders = ",".join(["%s"] * len(student_ids))
            quiz_scope_condition = ""
            quiz_scope_params = []
            if selected_progress:
                quiz_scope_condition = """
                  AND EXISTS (
                      SELECT 1
                      FROM weekly_progress_doc wpd
                      JOIN weekly_progress wp ON wp.id = wpd.progress_id
                      JOIN class c ON c.id = wp.class_id
                      WHERE wpd.doc_id = sqr.doc_id
                        AND c.tenant_id = %s
                        AND c.status = '1'
                        AND wp.status = '1'
                        AND wp.week_start = %s
                        AND wp.week_end = %s
                  )
                """
                quiz_scope_params.extend([
                    tenant_id,
                    selected_progress["week_start"],
                    selected_progress["week_end"],
                ])
                quiz_date_condition = "1 = 1"
            else:
                quiz_date_condition = _date_condition("sqr.create_date", normalized_range)
            cursor.execute(
                f"""
                SELECT
                    sqr.student_id,
                    COUNT(*) AS quiz_attempts,
                    SUM(CASE WHEN sqr.is_correct = 1 THEN 1 ELSE 0 END) AS correct_answers,
                    SUM(CASE WHEN sqr.is_correct = 0 THEN 1 ELSE 0 END) AS wrong_answers,
                    MAX(sqr.create_date) AS last_active_at
                FROM student_quiz_result sqr
                JOIN document doc ON doc.id = sqr.doc_id
                JOIN knowledgebase kb ON kb.id = doc.kb_id
                WHERE kb.tenant_id = %s
                  AND sqr.student_id IN ({placeholders})
                  {quiz_scope_condition}
                  AND {quiz_date_condition}
                GROUP BY sqr.student_id
                """,
                (tenant_id, *student_ids, *quiz_scope_params),
            )
            for row in cursor.fetchall():
                stats = student_stats[row["student_id"]]
                stats["quiz_attempts"] = int(row.get("quiz_attempts") or 0)
                stats["correct_answers"] = int(row.get("correct_answers") or 0)
                stats["wrong_answers"] = int(row.get("wrong_answers") or 0)
                stats["last_active_at"] = row.get("last_active_at")

            conversation_params = []
            if selected_progress:
                conversation_date_condition = "conv.update_date >= %s AND conv.update_date < DATE_ADD(%s, INTERVAL 1 DAY)"
                conversation_params.extend([
                    selected_progress["week_start"],
                    selected_progress["week_end"],
                ])
            else:
                conversation_date_condition = _date_condition("conv.update_date", normalized_range)
            cursor.execute(
                f"""
                SELECT conv.user_id, conv.message, conv.update_date
                FROM conversation conv
                JOIN dialog d ON d.id = conv.dialog_id
                WHERE d.tenant_id = %s
                  AND conv.user_id IN ({placeholders})
                  AND {conversation_date_condition}
                """,
                (tenant_id, *student_ids, *conversation_params),
            )
            for row in cursor.fetchall():
                stats = student_stats[row["user_id"]]
                stats["question_count"] += sum(
                    1 for item in _decode_json_list(row.get("message"))
                    if isinstance(item, dict) and item.get("role") == "user"
                )
                active_at = row.get("update_date")
                if active_at and (not stats["last_active_at"] or active_at > stats["last_active_at"]):
                    stats["last_active_at"] = active_at

            question_having = "" if selected_progress else "HAVING wrong_count > 0"
            question_limit = "" if selected_progress else "LIMIT %s"
            question_params = (tenant_id, *student_ids, *quiz_scope_params)
            if not selected_progress:
                question_params += (limit,)
            cursor.execute(
                f"""
                SELECT
                    sqr.doc_id,
                    sqr.question_index,
                    doc.name AS document_name,
                    COUNT(*) AS attempt_count,
                    SUM(CASE WHEN sqr.is_correct = 0 THEN 1 ELSE 0 END) AS wrong_count,
                    COUNT(DISTINCT CASE WHEN sqr.is_correct = 0 THEN sqr.student_id END) AS wrong_student_count
                FROM student_quiz_result sqr
                JOIN document doc ON doc.id = sqr.doc_id
                JOIN knowledgebase kb ON kb.id = doc.kb_id
                WHERE kb.tenant_id = %s
                  AND sqr.student_id IN ({placeholders})
                  {quiz_scope_condition}
                  AND {quiz_date_condition}
                GROUP BY sqr.doc_id, sqr.question_index, doc.name
                {question_having}
                ORDER BY wrong_count DESC, attempt_count DESC
                {question_limit}
                """,
                question_params,
            )
            question_rows = cursor.fetchall()
            wrong_rows = (
                [row for row in question_rows if int(row.get("wrong_count") or 0) > 0][:limit]
                if selected_progress
                else question_rows
            )
            quiz_lookup = {}
            if selected_progress:
                cursor.execute(
                    """
                    SELECT wpd.doc_id, d.name AS document_name, dg.content
                    FROM weekly_progress_doc wpd
                    JOIN weekly_progress wp ON wp.id = wpd.progress_id
                    JOIN class c ON c.id = wp.class_id
                    JOIN document d ON d.id = wpd.doc_id
                    JOIN document_generation dg
                      ON dg.doc_id = wpd.doc_id AND dg.generation_type = 'quiz'
                    WHERE c.tenant_id = %s
                      AND c.status = '1'
                      AND wp.status = '1'
                      AND wp.week_start = %s
                      AND wp.week_end = %s
                    GROUP BY wpd.doc_id, d.name, dg.content
                    ORDER BY d.name ASC
                    """,
                    (
                        tenant_id,
                        selected_progress["week_start"],
                        selected_progress["week_end"],
                    ),
                )
                progress_doc_rows = cursor.fetchall()
                quiz_lookup = _build_quiz_lookup(progress_doc_rows)
                stats_lookup = {
                    (str(row["doc_id"]), str(row["question_index"])): row
                    for row in question_rows
                }
                for doc_row in progress_doc_rows:
                    for position, question in enumerate(_decode_json_list(doc_row.get("content"))):
                        if not isinstance(question, dict):
                            continue
                        question_id = str(question.get("id", position))
                        stat = stats_lookup.get((str(doc_row["doc_id"]), question_id))
                        if not stat:
                            stat = stats_lookup.get((str(doc_row["doc_id"]), str(position)))
                        attempt_count = int(stat.get("attempt_count") or 0) if stat else 0
                        wrong_count = int(stat.get("wrong_count") or 0) if stat else 0
                        correct = question.get("correct", "")
                        all_questions.append({
                            "doc_id": doc_row["doc_id"],
                            "document_name": doc_row.get("document_name") or "未命名课件",
                            "question_index": stat["question_index"] if stat else question.get("id", position),
                            "question": question.get("question") or f"第 {position + 1} 题",
                            "correct_answer": _answer_text(question, correct) if correct else "暂无答案",
                            "attempt_count": attempt_count,
                            "wrong_count": wrong_count,
                            "wrong_student_count": int(stat.get("wrong_student_count") or 0) if stat else 0,
                            "wrong_rate": round(wrong_count / attempt_count * 100) if attempt_count else 0,
                        })
            else:
                wrong_doc_ids = list({str(row["doc_id"]) for row in wrong_rows})
                if wrong_doc_ids:
                    doc_placeholders = ",".join(["%s"] * len(wrong_doc_ids))
                    cursor.execute(
                        f"""
                        SELECT doc_id, content
                        FROM document_generation
                        WHERE generation_type = 'quiz' AND doc_id IN ({doc_placeholders})
                        """,
                        tuple(wrong_doc_ids),
                    )
                    quiz_lookup = _build_quiz_lookup(cursor.fetchall())

            for row in wrong_rows:
                question = quiz_lookup.get((str(row["doc_id"]), str(row["question_index"])), {})
                attempt_count = int(row.get("attempt_count") or 0)
                wrong_count = int(row.get("wrong_count") or 0)
                correct = question.get("correct", "") if isinstance(question, dict) else ""
                wrong_questions.append({
                    "doc_id": row["doc_id"],
                    "document_name": row.get("document_name") or "未命名课件",
                    "question_index": row["question_index"],
                    "question": question.get("question") or f"历史题目 #{row['question_index']}（题目内容已调整）",
                    "correct_answer": _answer_text(question, correct) if correct else "题目内容已调整",
                    "attempt_count": attempt_count,
                    "wrong_count": wrong_count,
                    "wrong_student_count": int(row.get("wrong_student_count") or 0),
                    "wrong_rate": round(wrong_count / attempt_count * 100) if attempt_count else 0,
                })

        students = []
        for row in student_rows:
            stats = student_stats[row["id"]]
            attempts = stats["quiz_attempts"]
            correct = stats["correct_answers"]
            students.append({
                "student_id": row["id"],
                "student_name": row.get("nickname") or row.get("email") or "未命名学生",
                "student_email": row.get("email") or "",
                "class_ids": (row.get("class_ids") or "").split(",") if row.get("class_ids") else [],
                "class_names": row.get("class_names") or "未分班",
                "quiz_attempts": attempts,
                "correct_answers": correct,
                "wrong_answers": stats["wrong_answers"],
                "accuracy": round(correct / attempts * 100) if attempts else 0,
                "question_count": stats["question_count"],
                "activity_count": attempts + stats["question_count"],
                "last_active_at": _format_dashboard_time(stats["last_active_at"]),
            })
        students.sort(key=lambda item: (-item["activity_count"], item["student_name"]))

        return True, {
            "classes": [{"id": row["id"], "name": row["name"]} for row in classes],
            "summary": {
                "student_count": len(students),
                "active_student_count": sum(1 for item in students if item["activity_count"] > 0),
                "quiz_attempt_count": sum(item["quiz_attempts"] for item in students),
                "wrong_answer_count": sum(item["wrong_answers"] for item in students),
                "question_count": sum(item["question_count"] for item in students),
            },
            "students": students,
            "wrong_questions": wrong_questions,
            "all_questions": all_questions,
            "range": normalized_range,
        }
    except Exception as error:
        return False, str(error)
    finally:
        cursor.close()
        conn.close()


def get_student_learning_detail(
    tenant_id: str,
    student_id: str,
    time_range: str = "7d",
    progress_id: str = "",
):
    """获取一名学生的逐题答题记录与实际提问内容。"""
    normalized_range = _normalize_time_range(time_range)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                u.id,
                u.nickname,
                u.email,
                GROUP_CONCAT(DISTINCT c.id ORDER BY c.name SEPARATOR ',') AS class_ids,
                GROUP_CONCAT(DISTINCT c.name ORDER BY c.name SEPARATOR '、') AS class_names
            FROM user u
            JOIN user_class uc ON uc.user_id = u.id AND uc.role = 'student' AND uc.status = '1'
            JOIN class c ON c.id = uc.class_id AND c.status = '1'
            WHERE u.id = %s AND c.tenant_id = %s
            GROUP BY u.id, u.nickname, u.email
            """,
            (student_id, tenant_id),
        )
        student = cursor.fetchone()
        if not student:
            return False, "学生不存在或不属于当前老师"

        quiz_scope_condition = ""
        quiz_scope_params = []
        conversation_scope_params = []
        if progress_id:
            cursor.execute(
                """
                SELECT wp.id, wp.class_id, wp.week_start, wp.week_end
                FROM weekly_progress wp
                JOIN class c ON c.id = wp.class_id
                WHERE wp.id = %s AND c.tenant_id = %s AND c.status = '1' AND wp.status = '1'
                """,
                (progress_id, tenant_id),
            )
            selected_progress = cursor.fetchone()
            if not selected_progress:
                return False, "周进度不存在或不属于当前老师"
            quiz_scope_condition = """
              AND EXISTS (
                  SELECT 1
                  FROM weekly_progress_doc wpd
                  JOIN weekly_progress wp ON wp.id = wpd.progress_id
                  JOIN class c ON c.id = wp.class_id
                  WHERE wpd.doc_id = sqr.doc_id
                    AND c.tenant_id = %s
                    AND c.status = '1'
                    AND wp.status = '1'
                    AND wp.week_start = %s
                    AND wp.week_end = %s
              )
            """
            quiz_scope_params.extend([
                tenant_id,
                selected_progress["week_start"],
                selected_progress["week_end"],
            ])
            quiz_date_condition = "1 = 1"
            conversation_date_condition = "conv.update_date >= %s AND conv.update_date < DATE_ADD(%s, INTERVAL 1 DAY)"
            conversation_scope_params.extend([
                selected_progress["week_start"],
                selected_progress["week_end"],
            ])
        else:
            quiz_date_condition = _date_condition("sqr.create_date", normalized_range)
            conversation_date_condition = _date_condition("conv.update_date", normalized_range)
        cursor.execute(
            f"""
            SELECT
                sqr.id,
                sqr.doc_id,
                sqr.question_index,
                sqr.student_answer,
                sqr.is_correct,
                sqr.create_date,
                doc.name AS document_name
            FROM student_quiz_result sqr
            JOIN document doc ON doc.id = sqr.doc_id
            JOIN knowledgebase kb ON kb.id = doc.kb_id
            WHERE sqr.student_id = %s
              AND kb.tenant_id = %s
              {quiz_scope_condition}
              AND {quiz_date_condition}
            ORDER BY sqr.create_date DESC
            LIMIT 300
            """,
            (student_id, tenant_id, *quiz_scope_params),
        )
        attempt_rows = cursor.fetchall()
        doc_ids = list({str(row["doc_id"]) for row in attempt_rows})
        quiz_lookup = {}
        if doc_ids:
            placeholders = ",".join(["%s"] * len(doc_ids))
            cursor.execute(
                f"""
                SELECT doc_id, content
                FROM document_generation
                WHERE generation_type = 'quiz' AND doc_id IN ({placeholders})
                """,
                tuple(doc_ids),
            )
            quiz_lookup = _build_quiz_lookup(cursor.fetchall())

        quiz_attempts = []
        for row in attempt_rows:
            question = quiz_lookup.get((str(row["doc_id"]), str(row["question_index"])), {})
            correct = question.get("correct", "") if isinstance(question, dict) else ""
            quiz_attempts.append({
                "id": row["id"],
                "doc_id": row["doc_id"],
                "document_name": row.get("document_name") or "未命名课件",
                "question_index": row["question_index"],
                "question": question.get("question") or f"历史题目 #{row['question_index']}（题目内容已调整）",
                "student_answer": _answer_text(question, row.get("student_answer")),
                "correct_answer": _answer_text(question, correct) if correct else "题目内容已调整",
                "is_correct": bool(row.get("is_correct")),
                "answered_at": _format_dashboard_time(row.get("create_date")),
            })

        cursor.execute(
            f"""
            SELECT
                conv.id,
                conv.name,
                conv.message,
                conv.update_date,
                d.name AS assistant_name
            FROM conversation conv
            JOIN dialog d ON d.id = conv.dialog_id
            WHERE conv.user_id = %s
              AND d.tenant_id = %s
              AND {conversation_date_condition}
            ORDER BY conv.update_date DESC
            """,
            (student_id, tenant_id, *conversation_scope_params),
        )
        questions = []
        for conversation in cursor.fetchall():
            for message_index, message in enumerate(_decode_json_list(conversation.get("message"))):
                if not isinstance(message, dict) or message.get("role") != "user":
                    continue
                asked_at = message.get("created_at") or message.get("create_time")
                if isinstance(asked_at, (int, float)):
                    asked_at = datetime.fromtimestamp(asked_at / 1000 if asked_at > 100000000000 else asked_at)
                questions.append({
                    "id": str(message.get("id") or f"{conversation['id']}-{message_index}"),
                    "conversation_id": conversation["id"],
                    "conversation_name": conversation.get("name") or "未命名会话",
                    "assistant_name": conversation.get("assistant_name") or "课程助教",
                    "content": str(message.get("content") or ""),
                    "asked_at": _format_dashboard_time(asked_at or conversation.get("update_date")),
                })

        correct_count = sum(1 for item in quiz_attempts if item["is_correct"])
        return True, {
            "student": {
                "student_id": student["id"],
                "student_name": student.get("nickname") or student.get("email") or "未命名学生",
                "student_email": student.get("email") or "",
                "class_ids": (student.get("class_ids") or "").split(",") if student.get("class_ids") else [],
                "class_names": student.get("class_names") or "未分班",
            },
            "summary": {
                "quiz_attempt_count": len(quiz_attempts),
                "correct_answer_count": correct_count,
                "wrong_answer_count": len(quiz_attempts) - correct_count,
                "accuracy": round(correct_count / len(quiz_attempts) * 100) if quiz_attempts else 0,
                "question_count": len(questions),
            },
            "quiz_attempts": quiz_attempts,
            "questions": questions,
            "range": normalized_range,
        }
    except Exception as error:
        return False, str(error)
    finally:
        cursor.close()
        conn.close()


def get_wrong_question_detail(
    tenant_id: str,
    doc_id: str,
    question_index: str,
    class_id: str = "",
    progress_id: str = "",
    time_range: str = "7d",
):
    """获取一道错题的完整题目、聚合统计和学生作答明细。"""
    normalized_range = _normalize_time_range(time_range)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        selected_progress = None
        if progress_id:
            cursor.execute(
                """
                SELECT wp.id, wp.class_id, wp.week_start, wp.week_end
                FROM weekly_progress wp
                JOIN class c ON c.id = wp.class_id
                WHERE wp.id = %s AND c.tenant_id = %s AND c.status = '1' AND wp.status = '1'
                """,
                (progress_id, tenant_id),
            )
            selected_progress = cursor.fetchone()
            if not selected_progress:
                return False, "周进度不存在或不属于当前老师"
            # 错题详情与学习洞察保持一致，只按周统计所有班级的记录。
            class_id = ""

        membership_conditions = [
            "uc.user_id = sqr.student_id",
            "uc.role = 'student'",
            "uc.status = '1'",
            "c.tenant_id = %s",
            "c.status = '1'",
        ]
        membership_params = [tenant_id]
        if class_id:
            membership_conditions.append("c.id = %s")
            membership_params.append(class_id)

        quiz_scope_params = []
        quiz_scope_condition = ""
        if selected_progress:
            quiz_scope_condition = """
              AND EXISTS (
                  SELECT 1
                  FROM weekly_progress_doc wpd
                  JOIN weekly_progress wp ON wp.id = wpd.progress_id
                  JOIN class c ON c.id = wp.class_id
                  WHERE wpd.doc_id = sqr.doc_id
                    AND c.tenant_id = %s
                    AND c.status = '1'
                    AND wp.status = '1'
                    AND wp.week_start = %s
                    AND wp.week_end = %s
              )
            """
            quiz_scope_params.extend([
                tenant_id,
                selected_progress["week_start"],
                selected_progress["week_end"],
            ])
            quiz_date_condition = "1 = 1"
        else:
            quiz_date_condition = _date_condition("sqr.create_date", normalized_range)
        cursor.execute(
            f"""
            SELECT
                sqr.id,
                sqr.student_id,
                u.nickname AS student_name,
                u.email AS student_email,
                sqr.student_answer,
                sqr.is_correct,
                sqr.create_date,
                doc.name AS document_name
            FROM student_quiz_result sqr
            JOIN user u ON u.id = sqr.student_id
            JOIN document doc ON doc.id = sqr.doc_id
            JOIN knowledgebase kb ON kb.id = doc.kb_id
            WHERE kb.tenant_id = %s
              AND sqr.doc_id = %s
              AND sqr.question_index = %s
              {quiz_scope_condition}
              AND {quiz_date_condition}
              AND EXISTS (
                  SELECT 1
                  FROM user_class uc
                  JOIN class c ON c.id = uc.class_id
                  WHERE {' AND '.join(membership_conditions)}
              )
            ORDER BY sqr.create_date DESC
            """,
            (tenant_id, doc_id, question_index, *quiz_scope_params, *membership_params),
        )
        attempt_rows = cursor.fetchall()
        if not attempt_rows:
            return False, "错题不存在或不属于当前老师"

        cursor.execute(
            """
            SELECT doc_id, content
            FROM document_generation
            WHERE generation_type = 'quiz' AND doc_id = %s
            """,
            (doc_id,),
        )
        quiz_lookup = _build_quiz_lookup(cursor.fetchall())
        question = quiz_lookup.get((str(doc_id), str(question_index)), {})
        question_data = question if isinstance(question, dict) else {}
        correct = question_data.get("correct", "")
        question_index_value = attempt_rows[0].get("question_index", question_index)
        attempt_count = len(attempt_rows)
        wrong_count = sum(1 for row in attempt_rows if not row.get("is_correct"))
        wrong_student_ids = {
            str(row["student_id"])
            for row in attempt_rows
            if not row.get("is_correct")
        }

        attempts = [
            {
                "id": row["id"],
                "student_id": row["student_id"],
                "student_name": row.get("student_name") or row.get("student_email") or "未命名学生",
                "student_email": row.get("student_email") or "",
                "student_answer": _answer_text(question_data, row.get("student_answer")),
                "answer_explanation": _answer_explanation(question_data, row.get("student_answer")),
                "is_correct": bool(row.get("is_correct")),
                "answered_at": _format_dashboard_time(row.get("create_date")),
            }
            for row in attempt_rows
        ]

        return True, {
            "doc_id": doc_id,
            "document_name": attempt_rows[0].get("document_name") or "未命名课件",
            "question_index": question_index_value,
            "question": question_data.get("question") or f"历史题目 #{question_index}（题目内容已调整）",
            "options": question_data.get("options") if isinstance(question_data.get("options"), dict) else {},
            "explanations": question_data.get("explanations") if isinstance(question_data.get("explanations"), dict) else {},
            "correct_answer": _answer_text(question_data, correct) if correct else "题目内容已调整",
            "attempt_count": attempt_count,
            "wrong_count": wrong_count,
            "wrong_student_count": len(wrong_student_ids),
            "wrong_rate": round(wrong_count / attempt_count * 100) if attempt_count else 0,
            "attempts": attempts,
            "range": normalized_range,
        }
    except Exception as error:
        return False, str(error)
    finally:
        cursor.close()
        conn.close()
