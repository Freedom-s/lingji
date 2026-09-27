from services.progress import service
from datetime import date, timedelta

import pytest


def test_progress_status_query_only_includes_current_class_students():
    query = service._PROGRESS_STATUS_QUERY

    assert "JOIN user_class uc" in query
    assert "uc.class_id = wp.class_id" in query
    assert "uc.user_id = sps.student_id" in query
    assert "uc.role = 'student'" in query
    assert "uc.status = '1'" in query


def test_quiz_completion_counts_each_question_once():
    # A student may retry questions. One successful retry is enough for that
    # question, but every question still has to be answered.
    rate, passed = service._evaluate_quiz_completion(
        total_questions=15,
        answered_questions=15,
        correct_questions=13,
        threshold=70,
    )

    assert rate == 86.7
    assert passed is True


def test_quiz_completion_rejects_unanswered_questions():
    rate, passed = service._evaluate_quiz_completion(
        total_questions=15,
        answered_questions=14,
        correct_questions=14,
        threshold=70,
    )

    assert rate == 93.3
    assert passed is False


def test_progress_state_includes_today_and_excludes_future_week():
    today = date(2026, 9, 27)

    state, day_count = service._get_progress_state(
        date(2026, 9, 21), date(2026, 9, 27), today
    )
    assert state == "active"
    assert day_count == 0

    state, day_count = service._get_progress_state(
        date(2026, 9, 28), date(2026, 10, 4), today
    )
    assert state == "upcoming"
    assert day_count == 1


class _ReminderCursor:
    def __init__(self):
        self.calls = []

    def execute(self, query, params=()):
        self.calls.append((query, params))

    def fetchall(self):
        return [{"id": "progress-1"}]

    def close(self):
        pass


class _ReminderConnection:
    def __init__(self, cursor):
        self.cursor_instance = cursor

    def cursor(self, dictionary=False):
        return self.cursor_instance

    def close(self):
        pass


@pytest.mark.parametrize(
    ("class_id", "progress_id", "expected_params"),
    [
        (None, None, ("teacher-1",)),
        ("class-1", None, ("teacher-1", "class-1")),
        ("class-1", "progress-1", ("teacher-1", "class-1", "progress-1")),
    ],
)
def test_teacher_progress_reminders_applies_class_and_progress_filters(
    monkeypatch, class_id, progress_id, expected_params
):
    cursor = _ReminderCursor()
    monkeypatch.setattr(service, "get_current_user", lambda: {"user_id": "teacher-1"})
    monkeypatch.setattr(
        service.mysql.connector,
        "connect",
        lambda **kwargs: _ReminderConnection(cursor),
    )
    monkeypatch.setattr(
        service,
        "get_progress_status",
        lambda _: (
            True,
            {
                "progress": {
                    "id": "progress-1",
                    "class_id": "class-1",
                    "class_name": "一班",
                    "name": "第1周",
                    "week_start": date.today() - timedelta(days=1),
                    "week_end": date.today() + timedelta(days=5),
                },
                "summary": {
                    "total_students": 0,
                    "completed_count": 0,
                    "incomplete_count": 0,
                    "completion_rate": 0.0,
                },
                "students": [],
            },
        ),
    )

    success, result = service.get_teacher_progress_reminders(class_id, progress_id)

    assert success is True
    assert result["summary"]["total_progresses"] == 1
    query, params = cursor.calls[0]
    assert params == expected_params
    if class_id:
        assert "wp.class_id = %s" in query
    else:
        assert "wp.class_id = %s" not in query
    if progress_id:
        assert "wp.id = %s" in query
    else:
        assert "wp.id = %s" not in query


def test_teacher_progress_overview_distinguishes_partial_and_not_started_students(monkeypatch):
    def reminder_result(class_id=None, progress_id=None):
        return True, {
            "items": [
                {
                    "id": "week-1",
                    "class_id": "class-1",
                    "class_name": "一班",
                    "name": "第1周",
                    "week_start": "2026-09-01",
                    "week_end": "2026-09-07",
                    "state": "active",
                    "completed_students": [
                        {"student_id": "student-2", "student_name": "李四", "completed_docs": 1, "total_docs": 1},
                    ],
                    "incomplete_students": [
                        {"student_id": "student-1", "student_name": "张三", "completed_docs": 0, "total_docs": 1},
                    ],
                },
                {
                    "id": "week-2",
                    "class_id": "class-1",
                    "class_name": "一班",
                    "name": "第2周",
                    "week_start": "2026-09-08",
                    "week_end": "2026-09-14",
                    "state": "overdue",
                    "completed_students": [
                        {"student_id": "student-2", "student_name": "李四", "completed_docs": 2, "total_docs": 2},
                    ],
                    "incomplete_students": [
                        {"student_id": "student-1", "student_name": "张三", "completed_docs": 1, "total_docs": 2},
                    ],
                },
            ],
        }

    monkeypatch.setattr(service, "get_teacher_progress_reminders", reminder_result)

    success, result = service.get_teacher_progress_overview()

    assert success is True
    assert result["summary"]["total_students"] == 2
    assert result["summary"]["completed_students"] == 1
    assert result["summary"]["partial_students"] == 1
    assert result["summary"]["not_started_students"] == 0
    zhang = next(student for student in result["students"] if student["student_id"] == "student-1")
    assert zhang["status"] == "partial"
    assert zhang["overdue_progresses"] == 1
    assert zhang["consecutive_incomplete_progresses"] == 2
    assert zhang["completion_rate"] == 33.3


def test_teacher_progress_overview_merges_same_week_across_classes(monkeypatch):
    def reminder_result(class_id=None, progress_id=None):
        items = []
        for class_id_value, class_name, student_id, student_name in [
            ("class-1", "一班", "student-1", "张三"),
            ("class-2", "二班", "student-2", "李四"),
        ]:
            for index in (1, 2):
                items.append({
                    "id": f"{class_id_value}-week-{index}",
                    "class_id": class_id_value,
                    "class_name": class_name,
                    "name": f"第{index}周",
                    "week_start": f"2026-09-{index * 7 - 6:02d}",
                    "week_end": f"2026-09-{index * 7:02d}",
                    "state": "overdue",
                    "completed_students": [
                        {"student_id": student_id, "student_name": student_name, "completed_docs": 1, "total_docs": 1},
                    ],
                    "incomplete_students": [],
                })
        return True, {"items": items}

    monkeypatch.setattr(service, "get_teacher_progress_reminders", reminder_result)

    success, result = service.get_teacher_progress_overview()

    assert success is True
    assert [progress["name"] for progress in result["progresses"]] == ["第1周", "第2周"]
    assert all(len(student["progresses"]) == 2 for student in result["students"])
    assert all(
        all(progress["status"] != "unassigned" for progress in student["progresses"])
        for student in result["students"]
    )
