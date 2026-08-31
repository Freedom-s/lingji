"""Student weekly progress reminders.

GET /v1/student_progress/reminders returns the current student's weekly
assignments and refreshes their per-document completion state first.
"""

import json
import logging
from datetime import date, datetime

from flask_login import current_user, login_required
from peewee import fn

from api.db.db_models import (
    Class,
    ClassDialog,
    Dialog,
    Document,
    DocumentGeneration,
    StudentNote,
    StudentProgressStatus,
    StudentQuizResult,
    StudentVideoProgress,
    UserClass,
    WeeklyProgress,
    WeeklyProgressDoc,
)
from api.utils import get_uuid
from api.utils.api_utils import get_json_result, server_error_response


logger = logging.getLogger(__name__)


def _iso_date(value):
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    return str(value or "")


def _progress_state(week_start, week_end):
    today = date.today()
    start = week_start.date() if isinstance(week_start, datetime) else week_start
    end = week_end.date() if isinstance(week_end, datetime) else week_end
    if start and today < start:
        return "upcoming", (start - today).days
    if end and today > end:
        return "overdue", (today - end).days
    return "active", (end - today).days if end else 0


def _dialog_map_for_classes(class_ids):
    """Return {(class_id, kb_id): dialog_id} for direct learning links."""
    result = {}
    if not class_ids:
        return result

    rows = (
        ClassDialog.select(
            ClassDialog.class_id,
            Dialog.id.alias("dialog_id"),
            Dialog.kb_ids,
        )
        .join(Dialog, on=(ClassDialog.dialog_id == Dialog.id))
        .where(ClassDialog.class_id.in_(class_ids))
        .dicts()
    )
    for row in rows:
        kb_ids = row["kb_ids"] or []
        if isinstance(kb_ids, str):
            try:
                kb_ids = json.loads(kb_ids)
            except (json.JSONDecodeError, TypeError):
                kb_ids = [item.strip() for item in kb_ids.split(",") if item.strip()]
        if not isinstance(kb_ids, list):
            continue
        for kb_id in kb_ids:
            result.setdefault((row["class_id"], kb_id), row["dialog_id"])
    return result


def _learning_state(student_id, doc_ids):
    video_completed = set()
    quiz_stats = {}
    noted_docs = set()
    quiz_docs = set()
    if not doc_ids:
        return video_completed, quiz_stats, noted_docs, quiz_docs

    for row in StudentVideoProgress.select().where(
        (StudentVideoProgress.student_id == student_id)
        & (StudentVideoProgress.doc_id.in_(doc_ids))
        & (StudentVideoProgress.is_completed == True)  # noqa: E712
    ):
        video_completed.add(row.doc_id)

    quiz_query = (
        StudentQuizResult.select(
            StudentQuizResult.doc_id,
            fn.COUNT(StudentQuizResult.id).alias("total"),
            fn.SUM(StudentQuizResult.is_correct).alias("correct"),
        )
        .where(
            (StudentQuizResult.student_id == student_id)
            & (StudentQuizResult.doc_id.in_(doc_ids))
        )
        .group_by(StudentQuizResult.doc_id)
    )
    for row in quiz_query.dicts():
        quiz_stats[row["doc_id"]] = {
            "total": int(row["total"] or 0),
            "correct": int(row["correct"] or 0),
        }

    for row in (
        StudentNote.select(StudentNote.doc_id)
        .where(
            (StudentNote.student_id == student_id) & (StudentNote.doc_id.in_(doc_ids))
        )
        .distinct()
    ):
        noted_docs.add(row.doc_id)

    for row in (
        DocumentGeneration.select(DocumentGeneration.doc_id)
        .where(
            (DocumentGeneration.doc_id.in_(doc_ids))
            & (DocumentGeneration.generation_type == "quiz")
        )
        .distinct()
    ):
        quiz_docs.add(row.doc_id)

    return video_completed, quiz_stats, noted_docs, quiz_docs


def _save_status(student_id, progress_id, doc_status):
    existing = (
        StudentProgressStatus.select()
        .where(
            (StudentProgressStatus.student_id == student_id)
            & (StudentProgressStatus.progress_id == progress_id)
            & (StudentProgressStatus.doc_id == doc_status["doc_id"])
        )
        .first()
    )
    now = datetime.now()
    if existing:
        was_completed = bool(existing.is_completed)
        existing.is_completed = doc_status["is_completed"]
        existing.video_completed = doc_status["video_completed"]
        existing.quiz_passed = doc_status["quiz_passed"]
        existing.has_notes = doc_status["has_notes"]
        existing.completed_at = (
            existing.completed_at
            if doc_status["is_completed"] and was_completed
            else now if doc_status["is_completed"] else None
        )
        existing.update_time = int(now.timestamp() * 1000)
        existing.update_date = now
        existing.save()
        return

    StudentProgressStatus.create(
        id=get_uuid(),
        progress_id=progress_id,
        doc_id=doc_status["doc_id"],
        student_id=student_id,
        is_completed=doc_status["is_completed"],
        completed_at=now if doc_status["is_completed"] else None,
        video_completed=doc_status["video_completed"],
        quiz_passed=doc_status["quiz_passed"],
        has_notes=doc_status["has_notes"],
        create_time=int(now.timestamp() * 1000),
        create_date=now,
        update_time=int(now.timestamp() * 1000),
        update_date=now,
    )


@manager.route("/reminders", methods=["GET"])  # noqa: F821
@login_required
def progress_reminders():
    try:
        student_id = current_user.id
        memberships = list(
            UserClass.select().where(
                (UserClass.user_id == student_id)
                & (UserClass.role == "student")
                & (UserClass.status == "1")
            )
        )
        class_ids = [membership.class_id for membership in memberships]
        if not class_ids:
            return get_json_result(data={"summary": {}, "items": []})

        classes = {
            row.id: row.name
            for row in Class.select(Class.id, Class.name).where(Class.id.in_(class_ids))
        }
        progresses = list(
            WeeklyProgress.select()
            .where(
                (WeeklyProgress.class_id.in_(class_ids))
                & (WeeklyProgress.status == "1")
            )
            .order_by(WeeklyProgress.week_end.asc())
        )
        if not progresses:
            return get_json_result(data={"summary": {}, "items": []})

        progress_ids = [progress.id for progress in progresses]
        doc_links = list(
            WeeklyProgressDoc.select(
                WeeklyProgressDoc.progress_id,
                WeeklyProgressDoc.doc_id,
                WeeklyProgressDoc.quiz_threshold,
                Document.name.alias("doc_name"),
                Document.type.alias("doc_type"),
                Document.kb_id,
            )
            .join(Document, on=(WeeklyProgressDoc.doc_id == Document.id))
            .where(WeeklyProgressDoc.progress_id.in_(progress_ids))
            .dicts()
        )
        doc_ids = list({link["doc_id"] for link in doc_links})
        video_completed, quiz_stats, noted_docs, quiz_docs = _learning_state(
            student_id, doc_ids
        )
        dialog_map = _dialog_map_for_classes(class_ids)

        links_by_progress = {}
        for link in doc_links:
            links_by_progress.setdefault(link["progress_id"], []).append(link)

        items = []
        for progress in progresses:
            docs = []
            for link in links_by_progress.get(progress.id, []):
                doc_id = link["doc_id"]
                is_video = link["doc_type"] == "video"
                has_quiz = doc_id in quiz_docs
                stats = quiz_stats.get(doc_id, {"total": 0, "correct": 0})
                quiz_rate = (
                    round(stats["correct"] / stats["total"] * 100, 1)
                    if stats["total"]
                    else 0.0
                )
                video_done = doc_id in video_completed
                quiz_passed = (
                    has_quiz
                    and stats["total"] > 0
                    and quiz_rate >= link["quiz_threshold"]
                )
                has_notes = doc_id in noted_docs
                is_completed = (
                    video_done if is_video else quiz_passed if has_quiz else has_notes
                )
                doc_status = {
                    "doc_id": doc_id,
                    "doc_name": link["doc_name"],
                    "doc_type": link["doc_type"],
                    "dialog_id": dialog_map.get((progress.class_id, link["kb_id"]), ""),
                    "quiz_threshold": link["quiz_threshold"],
                    "quiz_rate": quiz_rate,
                    "video_completed": video_done,
                    "quiz_passed": quiz_passed,
                    "has_notes": has_notes,
                    "is_completed": is_completed,
                }
                _save_status(student_id, progress.id, doc_status)
                docs.append(doc_status)

            completed_docs = sum(1 for doc in docs if doc["is_completed"])
            total_docs = len(docs)
            state, day_count = _progress_state(progress.week_start, progress.week_end)
            items.append(
                {
                    "id": progress.id,
                    "class_id": progress.class_id,
                    "class_name": classes.get(progress.class_id, "未命名班级"),
                    "name": progress.name,
                    "week_start": _iso_date(progress.week_start),
                    "week_end": _iso_date(progress.week_end),
                    "state": state,
                    "day_count": day_count,
                    "completed_docs": completed_docs,
                    "total_docs": total_docs,
                    "completion_rate": (
                        round(completed_docs / total_docs * 100, 1)
                        if total_docs
                        else 0.0
                    ),
                    "is_completed": total_docs > 0 and completed_docs == total_docs,
                    "docs": docs,
                }
            )

        priority = {"overdue": 0, "active": 1, "upcoming": 2}
        items.sort(
            key=lambda item: (
                item["is_completed"],
                priority[item["state"]],
                item["week_end"],
            )
        )
        incomplete = [item for item in items if not item["is_completed"]]
        summary = {
            "total_progresses": len(items),
            "incomplete_progresses": len(incomplete),
            "overdue_progresses": sum(
                1 for item in incomplete if item["state"] == "overdue"
            ),
            "completed_progresses": len(items) - len(incomplete),
        }
        return get_json_result(data={"summary": summary, "items": items})
    except Exception as error:
        logger.exception("student progress reminders failed")
        return server_error_response(error)
