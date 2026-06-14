"""
Learning Stats API — 学习统计接口

提供助教卡片所需的进度、提问次数、测验次数等数据。
从 conversation（web 对话）、student_quiz_result、document 等表聚合计算。
"""
import json
from datetime import date, timedelta
from flask import request
from flask_login import login_required, current_user

from api.db.db_models import (
    Conversation, Dialog, Document, DocumentGeneration, StudentQuizResult, DB,
)
from api.db import StatusEnum
from api.db.services.user_class_service import UserClassService
from api.db.services.class_dialog_service import ClassDialogService
from api.utils.api_utils import server_error_response, get_data_error_result, get_json_result
from api.db.services.llm_service import LLMBundle
from api.db import LLMType


def _get_dialog_kb_ids(dialog_id):
    try:
        dialog = Dialog.select().where(
            (Dialog.id == dialog_id) &
            (Dialog.status == StatusEnum.VALID.value)
        ).first()
        if not dialog or not dialog.kb_ids:
            return []
        kb_ids = dialog.kb_ids
        # kb_ids 可能存为 JSON 数组字符串 '["id1","id2"]' 或逗号分隔字符串
        if isinstance(kb_ids, str):
            kb_ids = kb_ids.strip()
            if kb_ids.startswith('['):
                import json
                try:
                    kb_ids = json.loads(kb_ids)
                except (json.JSONDecodeError, TypeError):
                    kb_ids = [k.strip() for k in kb_ids.strip('[]').split(',') if k.strip().strip('"')]
            else:
                kb_ids = [k.strip() for k in kb_ids.split(',') if k.strip()]
        return kb_ids if isinstance(kb_ids, list) else [kb_ids]
    except Exception:
        return []


def _get_doc_ids_for_kbs(kb_ids):
    if not kb_ids:
        return []
    try:
        docs = Document.select(Document.id).where(
            Document.kb_id.in_(kb_ids)
        )
        return [d.id for d in docs]
    except Exception:
        return []


def _get_session_count(dialog_id, user_id):
    """会话数 — conversation 表的行数"""
    try:
        return Conversation.select().where(
            (Conversation.dialog_id == dialog_id) &
            (Conversation.user_id == user_id)
        ).count()
    except Exception:
        return 0


def _get_question_count(dialog_id, user_id):
    """提问数 — 所有会话 message JSON 中 role='user' 的条目数"""
    try:
        sessions = Conversation.select(Conversation.message).where(
            (Conversation.dialog_id == dialog_id) &
            (Conversation.user_id == user_id)
        )
        total = 0
        for s in sessions:
            if s.message and isinstance(s.message, list):
                total += sum(1 for m in s.message if m.get('role') == 'user')
        return total
    except Exception:
        return 0


def _get_quiz_count(doc_ids, student_id):
    """答题数 — student_quiz_result 中该学生的记录条数"""
    if not doc_ids:
        return 0
    try:
        return StudentQuizResult.select().where(
            (StudentQuizResult.doc_id.in_(doc_ids)) &
            (StudentQuizResult.student_id == student_id)
        ).count()
    except Exception:
        return 0


def _get_question_progress(doc_ids, student_id):
    """题目掌握进度 = 答对题数 / 总题数 × 100"""
    if not doc_ids:
        return 0
    try:
        total_questions = 0
        quiz_records = DocumentGeneration.select().where(
            (DocumentGeneration.doc_id.in_(doc_ids)) &
            (DocumentGeneration.generation_type == 'quiz')
        )
        for qr in quiz_records:
            if qr.content:
                try:
                    questions = json.loads(qr.content) if isinstance(qr.content, str) else qr.content
                    if isinstance(questions, list):
                        total_questions += len(questions)
                except (json.JSONDecodeError, TypeError):
                    pass

        if total_questions == 0:
            return 0

        # 答对的唯一题目数（doc_id + question_index 去重，避免重复作答虚高）
        placeholders = ','.join(['%s'] * len(doc_ids))
        cursor = DB.execute_sql(
            f"""
            SELECT COUNT(DISTINCT CONCAT(doc_id, '_', question_index))
            FROM student_quiz_result
            WHERE doc_id IN ({placeholders})
              AND student_id = %s
              AND is_correct = 1
            """,
            (*doc_ids, student_id)
        )
        correct = int(cursor.fetchone()[0] or 0)

        return round(correct / total_questions * 100)
    except Exception:
        return 0


def _get_doc_progress(doc_ids, student_id):
    """文档覆盖率 = 做过测验的文档数 / 总文档数 × 100"""
    if not doc_ids:
        return 0
    try:
        total = len(doc_ids)
        answered = (
            StudentQuizResult
            .select(StudentQuizResult.doc_id)
            .where(
                (StudentQuizResult.doc_id.in_(doc_ids)) &
                (StudentQuizResult.student_id == student_id)
            )
            .distinct()
            .count()
        )
        return round(answered / total * 100) if total > 0 else 0
    except Exception:
        return 0


def _get_active_dates(user_id):
    """获取用户有对话记录的所有日期（conversation 表），按日期倒序"""
    try:
        cursor = DB.execute_sql(
            """
            SELECT DISTINCT DATE(create_date) as activity_date
            FROM conversation
            WHERE user_id = %s
            ORDER BY activity_date DESC
            """,
            (user_id,)
        )
        return [row[0] for row in cursor.fetchall()]
    except Exception:
        return []


def _calculate_streak(user_id):
    """计算连续学习天数（从今天往回数连续有对话的天数）"""
    dates = _get_active_dates(user_id)
    if not dates:
        return 0

    today = date.today()
    yesterday = today - timedelta(days=1)

    if dates[0] not in (today, yesterday):
        return 0

    expected = today if dates[0] == today else yesterday
    streak = 0
    for d in dates:
        if d == expected:
            streak += 1
            expected -= timedelta(days=1)
        elif d < expected:
            break

    return streak


def _get_today_sessions(user_id):
    """获取今日对话次数（conversation 表）"""
    try:
        cursor = DB.execute_sql(
            """
            SELECT COUNT(*)
            FROM conversation
            WHERE user_id = %s AND DATE(create_date) = CURDATE()
            """,
            (user_id,)
        )
        return int(cursor.fetchone()[0] or 0)
    except Exception:
        return 0


def _get_user_dialogs(user):
    """
    获取当前用户可访问的所有有效 dialog。
    老师看自己租户下的，学生看班级关联的。
    """
    if user.is_superuser:
        return Dialog.select().where(
            (Dialog.tenant_id == user.id) &
            (Dialog.status == StatusEnum.VALID.value)
        )
    else:
        user_classes = UserClassService.get_by_user(user.id, status=StatusEnum.VALID.value)
        if not user_classes:
            return []
        class_ids = [uc.class_id for uc in user_classes]
        class_dialogs = ClassDialogService.model.select().where(
            ClassDialogService.model.class_id.in_(class_ids)
        )
        dialog_ids = [cd.dialog_id for cd in class_dialogs]
        if not dialog_ids:
            return []
        return Dialog.select().where(
            (Dialog.id.in_(dialog_ids)) &
            (Dialog.status == StatusEnum.VALID.value)
        )


def _get_radar_data(doc_ids, user_id, dialog_id):
    """六维雷达图数据 — quiz_performance, knowledge_mastery, qa_participation,
    courseware_coverage, flashcard_memory, learning_consistency（0-100）"""
    try:
        # 1. 测验成绩 — 复用已有
        quiz_performance = _get_question_progress(doc_ids, user_id)

        # 2. 知识点掌握率 — ease_factor >= 2.5 且 correct_count >= 2
        knowledge_mastery = 0
        try:
            if doc_ids:
                placeholders = ", ".join(["%s"] * len(doc_ids))
                row = DB.execute_sql(
                    f"""
                    SELECT
                        SUM(CASE WHEN ease_factor >= 2.5 AND correct_count >= 2 THEN 1 ELSE 0 END) AS mastered,
                        COUNT(*) AS total
                    FROM knowledge_point_mastery
                    WHERE student_id = %s AND doc_id IN ({placeholders})
                    """,
                    (user_id, *doc_ids)
                ).fetchone()
                if row and row[1] > 0:
                    knowledge_mastery = round((row[0] or 0) / row[1] * 100)
        except Exception:
            pass

        # 3. 问答参与度 — 提问数 / 10 * 100，上限 100
        qa_participation = 0
        try:
            qc = _get_question_count(dialog_id, user_id)
            qa_participation = min(round(qc / 10 * 100), 100)
        except Exception:
            pass

        # 4. 课件覆盖率 — 复用已有
        courseware_coverage = _get_doc_progress(doc_ids, user_id)

        # 5. 闪卡记忆率 — remembered / total
        flashcard_memory = 0
        try:
            if doc_ids:
                placeholders = ", ".join(["%s"] * len(doc_ids))
                row = DB.execute_sql(
                    f"""
                    SELECT
                        SUM(CASE WHEN status = 'remembered' THEN 1 ELSE 0 END) AS remembered,
                        COUNT(*) AS total
                    FROM student_card_progress
                    WHERE student_id = %s AND doc_id IN ({placeholders})
                    """,
                    (user_id, *doc_ids)
                ).fetchone()
                if row and row[1] > 0:
                    flashcard_memory = round((row[0] or 0) / row[1] * 100)
        except Exception:
            pass

        # 6. 学习持续性 — streak / 30 * 100，上限 100
        learning_consistency = 0
        try:
            streak = _calculate_streak(user_id)
            learning_consistency = min(round(streak / 30 * 100), 100)
        except Exception:
            pass

        return {
            "quiz_performance": quiz_performance,
            "knowledge_mastery": knowledge_mastery,
            "qa_participation": qa_participation,
            "courseware_coverage": courseware_coverage,
            "flashcard_memory": flashcard_memory,
            "learning_consistency": learning_consistency,
        }
    except Exception:
        return {
            "quiz_performance": 0,
            "knowledge_mastery": 0,
            "qa_participation": 0,
            "courseware_coverage": 0,
            "flashcard_memory": 0,
            "learning_consistency": 0,
        }


def _get_node_label_map(doc_ids):
    """从 document_generation 的 mindmap 中提取 node_id → label 映射"""
    node_labels = {}
    try:
        import json
        mindmaps = DocumentGeneration.select().where(
            (DocumentGeneration.doc_id.in_(doc_ids)) &
            (DocumentGeneration.generation_type == 'mindmap')
        )
        for mm in mindmaps:
            if not mm.content:
                continue
            try:
                content = json.loads(mm.content) if isinstance(mm.content, str) else mm.content
            except (json.JSONDecodeError, TypeError):
                continue
            # mindmap 结构: {"root": {"id": "...", "label": "...", "children": [...]}}
            stack = [content.get('root')]
            while stack:
                node = stack.pop()
                if not node or not isinstance(node, dict):
                    continue
                nid = node.get('id')
                nlabel = node.get('label')
                if nid and nlabel:
                    node_labels[nid] = nlabel
                children = node.get('children', [])
                if children and isinstance(children, list):
                    stack.extend(children)
    except Exception:
        pass
    return node_labels


def _get_knowledge_points(doc_ids, user_id):
    """知识点掌握度列表 — 每个节点返回 node_id, label, doc_id, doc_name,
    correct_count, wrong_count, mastery (0-100%), level (mastered/learning/needs_review)"""
    results = []
    try:
        if not doc_ids:
            return results
        node_labels = _get_node_label_map(doc_ids)
        # 构建 doc_id → doc_name 映射
        doc_names = {}
        try:
            docs = Document.select(Document.id, Document.name).where(
                Document.id.in_(doc_ids)
            )
            for d in docs:
                doc_names[d.id] = d.name
        except Exception:
            pass

        placeholders = ','.join(['%s'] * len(doc_ids))
        cursor = DB.execute_sql(
            f"""
            SELECT kpm.node_id, kpm.doc_id, kpm.correct_count, kpm.wrong_count,
                   kpm.ease_factor, kpm.review_count
            FROM knowledge_point_mastery kpm
            WHERE kpm.student_id = %s AND kpm.doc_id IN ({placeholders})
            ORDER BY kpm.doc_id, kpm.node_id
            """,
            (user_id, *doc_ids)
        )
        for row in cursor.fetchall():
            node_id, doc_id, correct, wrong, ease_factor, review_count = row
            correct = correct or 0
            wrong = wrong or 0

            total_attempts = correct + wrong
            mastery = round(correct / total_attempts * 100) if total_attempts > 0 else 0

            if ease_factor >= 2.5 and correct >= 2:
                level = "mastered"
            elif review_count and review_count >= 1:
                level = "learning"
            elif wrong > correct:
                level = "needs_review"
            else:
                level = "learning"

            results.append({
                "node_id": node_id,
                "label": node_labels.get(node_id, node_id),
                "doc_id": doc_id,
                "doc_name": doc_names.get(doc_id, doc_id[:12]),
                "correct_count": correct,
                "wrong_count": wrong,
                "mastery": mastery,
                "level": level,
            })
    except Exception:
        pass
    return results


def _get_weak_points(doc_ids, user_id):
    """薄弱知识点 Top-5 — wrong_count > 0，按 wrong_count DESC、correct_count ASC 排序"""
    results = []
    try:
        if not doc_ids:
            return results
        node_labels = _get_node_label_map(doc_ids)
        placeholders = ", ".join(["%s"] * len(doc_ids))
        cursor = DB.execute_sql(
            f"""
            SELECT node_id, doc_id, correct_count, wrong_count,
                   COALESCE(update_date, create_date) AS last_wrong_date
            FROM knowledge_point_mastery
            WHERE student_id = %s
              AND doc_id IN ({placeholders})
              AND wrong_count > 0
            ORDER BY wrong_count DESC, correct_count ASC
            LIMIT 5
            """,
            (user_id, *doc_ids)
        )
        for row in cursor.fetchall():
            node_id, doc_id, correct, wrong, last_wrong_date = row
            results.append({
                "node_id": node_id,
                "label": node_labels.get(node_id, node_id),
                "doc_id": doc_id,
                "wrong_count": wrong or 0,
                "correct_count": correct or 0,
                "last_wrong_date": str(last_wrong_date) if last_wrong_date else "",
            })
    except Exception:
        pass
    return results


def _get_recent_activity(dialog_id, user_id):
    """最近 14 天学习动态 — 合并 quiz / qa / flashcard 时间线，按日期倒序，最多 20 条"""
    results = []
    cutoff = (date.today() - timedelta(days=14)).isoformat()
    try:
        # 测验记录
        if dialog_id:
            kb_ids = _get_dialog_kb_ids(dialog_id)
            doc_ids = _get_doc_ids_for_kbs(kb_ids)
            if doc_ids:
                placeholders = ", ".join(["%s"] * len(doc_ids))
                cursor = DB.execute_sql(
                    f"""
                    SELECT DATE(sqr.create_date) AS dt,
                           SUM(CASE WHEN sqr.is_correct = 1 THEN 1 ELSE 0 END) AS correct,
                           COUNT(*) AS total
                    FROM student_quiz_result sqr
                    WHERE sqr.student_id = %s
                      AND sqr.doc_id IN ({placeholders})
                      AND sqr.create_date >= %s
                    GROUP BY DATE(sqr.create_date)
                    ORDER BY dt DESC
                    """,
                    (user_id, *doc_ids, cutoff)
                )
                for row in cursor.fetchall():
                    dt, correct, total = row
                    pct = round(correct / total * 100) if total > 0 else 0
                    results.append({
                        "date": str(dt),
                        "type": "quiz",
                        "detail": f"完成测验 {total} 题，正确 {correct} 题",
                        "score": pct,
                    })

        # 问答记录
        cursor = DB.execute_sql(
            """
            SELECT DATE(create_date) AS dt, COUNT(*) AS cnt
            FROM conversation
            WHERE user_id = %s AND dialog_id = %s AND create_date >= %s
            GROUP BY DATE(create_date)
            ORDER BY dt DESC
            """,
            (user_id, dialog_id, cutoff)
        )
        for row in cursor.fetchall():
            dt, cnt = row
            results.append({
                "date": str(dt),
                "type": "qa",
                "detail": f"提问 {cnt} 次，参与课程问答",
                "count": cnt,
            })

        # 闪卡记录
        if dialog_id:
            kb_ids = _get_dialog_kb_ids(dialog_id)
            doc_ids = _get_doc_ids_for_kbs(kb_ids)
            if doc_ids:
                placeholders = ", ".join(["%s"] * len(doc_ids))
                cursor = DB.execute_sql(
                    f"""
                    SELECT DATE(create_date) AS dt, COUNT(*) AS cnt
                    FROM student_card_progress
                    WHERE student_id = %s
                      AND doc_id IN ({placeholders})
                      AND create_date >= %s
                    GROUP BY DATE(create_date)
                    ORDER BY dt DESC
                    """,
                    (user_id, *doc_ids, cutoff)
                )
                for row in cursor.fetchall():
                    dt, cnt = row
                    results.append({
                        "date": str(dt),
                        "type": "flashcard",
                        "detail": f"复习闪卡 {cnt} 张",
                        "count": cnt,
                    })

        # 按日期倒序，取前 20
        results.sort(key=lambda x: x["date"], reverse=True)
        results = results[:20]
    except Exception:
        pass
    return results


def _get_active_calendar(user_id):
    """最近 90 天活跃日历 — 按天统计 conversation 次数"""
    results = []
    try:
        cursor = DB.execute_sql(
            """
            SELECT DATE(create_date) AS dt, COUNT(*) AS cnt
            FROM conversation
            WHERE user_id = %s
              AND create_date >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
            GROUP BY DATE(create_date)
            ORDER BY dt ASC
            """,
            (user_id,)
        )
        for row in cursor.fetchall():
            results.append({"date": str(row[0]), "count": int(row[1])})
    except Exception:
        pass
    return results


# ============================================================
# Routes
# ============================================================

@manager.route("/dialog/<dialog_id>", methods=["GET"])  # noqa: F821
@login_required
def dialog_stats(dialog_id):
    try:
        user_id = current_user.id
        kb_ids = _get_dialog_kb_ids(dialog_id)
        doc_ids = _get_doc_ids_for_kbs(kb_ids)

        stats = {
            "dialog_id": dialog_id,
            "question_progress": _get_question_progress(doc_ids, user_id),
            "doc_progress": _get_doc_progress(doc_ids, user_id),
            "session_count": _get_session_count(dialog_id, user_id),
            "question_count": _get_question_count(dialog_id, user_id),
            "quiz_count": _get_quiz_count(doc_ids, user_id),
        }
        return get_json_result(data=stats)
    except Exception as e:
        return server_error_response(e)


@manager.route("/activity", methods=["GET"])
@login_required
def learning_activity():
    try:
        user_id = current_user.id
        data = {
            "streak": _calculate_streak(user_id),
            "today_sessions": _get_today_sessions(user_id),
        }
        return get_json_result(data=data)
    except Exception as e:
        return server_error_response(e)


@manager.route("/all", methods=["GET"])
@login_required
def all_dialog_stats():
    try:
        user_id = current_user.id
        dialogs = _get_user_dialogs(current_user)

        dialog_stats = []
        for dialog in dialogs:
            s_count = _get_session_count(dialog.id, user_id)
            q_count = _get_question_count(dialog.id, user_id)
            kb_ids = dialog.kb_ids if dialog.kb_ids else []
            doc_ids = _get_doc_ids_for_kbs(kb_ids)
            quiz_count = _get_quiz_count(doc_ids, user_id)

            # 只返回当前用户有实际使用记录的助教（有会话或测验）
            if s_count == 0 and quiz_count == 0:
                continue

            dialog_stats.append({
                "dialog_id": dialog.id,
                "question_progress": _get_question_progress(doc_ids, user_id),
                "doc_progress": _get_doc_progress(doc_ids, user_id),
                "session_count": s_count,
                "question_count": q_count,
                "quiz_count": quiz_count,
            })

        data = {
            "dialogs": dialog_stats,
            "streak": _calculate_streak(user_id),
            "today_sessions": _get_today_sessions(user_id),
        }
        return get_json_result(data=data)
    except Exception as e:
        return server_error_response(e)


@manager.route("/analytics", methods=["GET"])
@login_required
def learning_analytics():
    try:
        user_id = current_user.id
        dialog_id = request.args.get("dialog_id", "").strip()
        if not dialog_id:
            return get_data_error_result(message="dialog_id is required")

        kb_ids = _get_dialog_kb_ids(dialog_id)
        doc_ids = _get_doc_ids_for_kbs(kb_ids)

        data = {
            "radar": _get_radar_data(doc_ids, user_id, dialog_id),
            "knowledge_points": _get_knowledge_points(doc_ids, user_id),
            "weak_points": _get_weak_points(doc_ids, user_id),
            "recent_activity": _get_recent_activity(dialog_id, user_id),
            "active_calendar": _get_active_calendar(user_id),
        }
        return get_json_result(data=data)
    except Exception as e:
        return server_error_response(e)


def _build_evaluation_prompt(radar, knowledge_points, weak_points, recent_activity, dialog_name):
    """构建发给 LLM 的学情评价 prompt"""
    dim_labels = {
        "quiz_performance": "测验表现", "knowledge_mastery": "知识点掌握",
        "qa_participation": "问答参与", "courseware_coverage": "课件覆盖",
        "flashcard_memory": "闪卡记忆", "learning_consistency": "学习持续力",
    }
    dim_lines = []
    for key, label in dim_labels.items():
        val = radar.get(key, 0) if radar else 0
        dim_lines.append(f"  {label}: {val} 分")
    dim_summary = "\n".join(dim_lines)

    weak_str = "无"
    if weak_points:
        items = [f"{wp.get('label', wp.get('node_id', ''))}（错误 {wp.get('wrong_count', 0)} 次）"
                 for wp in weak_points[:5]]
        weak_str = "、".join(items)

    doc_map = {}
    if knowledge_points:
        for kp in knowledge_points:
            dn = kp.get("doc_name", "未知文档")
            if dn not in doc_map:
                doc_map[dn] = {"total": 0, "mastered": 0}
            doc_map[dn]["total"] += 1
            if kp.get("level") == "mastered":
                doc_map[dn]["mastered"] += 1
    doc_lines = [f"  - {dn}: {s['mastered']}/{s['total']} 已掌握" for dn, s in doc_map.items()]
    doc_summary = "\n".join(doc_lines) if doc_lines else "无文档数据"

    activity_str = "无"
    if recent_activity:
        items = [f"{a.get('date', '')} {a.get('detail', '')}" for a in recent_activity[:5]]
        activity_str = "\n".join(items)

    return f"""你是一位专业的教育 AI 评价师，负责为学生生成个性化学习评价与建议。

【课程名称】{dialog_name}

【六维学习画像（满分 100）】
{dim_summary}

【文档覆盖情况】
{doc_summary}

【薄弱知识点】
{weak_str}

【最近学习动态】
{activity_str}

请基于以上数据，用中文写一段 150-250 字的综合学情评价。要求：
1. 先肯定学生的优点（至少 1 项）
2. 指出最需要改进的 1-2 个方面
3. 给出具体可操作的学习建议
4. 语气温暖鼓励，像一位关心学生的导师
5. 不要使用 Markdown 格式，直接输出纯文本段落"""


@manager.route("/evaluation", methods=["GET"])
@login_required
def learning_evaluation():
    try:
        dialog_id = request.args.get("dialog_id", "").strip()
        if not dialog_id:
            return get_data_error_result(message="dialog_id is required")

        dialog = Dialog.select().where(
            (Dialog.id == dialog_id) & (Dialog.status == StatusEnum.VALID.value)
        ).first()
        if not dialog:
            return get_data_error_result(message="dialog not found")

        kb_ids = _get_dialog_kb_ids(dialog_id)
        doc_ids = _get_doc_ids_for_kbs(kb_ids)

        radar = _get_radar_data(doc_ids, current_user.id, dialog_id)
        knowledge_points = _get_knowledge_points(doc_ids, current_user.id)
        weak_points = _get_weak_points(doc_ids, current_user.id)
        recent_activity = _get_recent_activity(dialog_id, current_user.id)

        prompt = _build_evaluation_prompt(
            radar, knowledge_points, weak_points, recent_activity, dialog.name
        )

        chat_mdl = LLMBundle(dialog.tenant_id, LLMType.CHAT, dialog.llm_id)
        evaluation = chat_mdl.chat(
            "你是一位专业的教育 AI 评价师。",
            [{"role": "user", "content": prompt}],
            {"temperature": 0.7, "max_tokens": 800},
        )

        return get_json_result(data={
            "evaluation": evaluation,
            "dialog_name": dialog.name,
        })
    except Exception as e:
        return server_error_response(e)
