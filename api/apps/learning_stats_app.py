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


def _get_dialog_kb_ids(dialog_id):
    try:
        dialog = Dialog.select().where(
            (Dialog.id == dialog_id) &
            (Dialog.status == StatusEnum.VALID.value)
        ).first()
        if not dialog:
            return []
        return dialog.kb_ids if dialog.kb_ids else []
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
