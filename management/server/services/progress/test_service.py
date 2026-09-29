from services.progress import service
from datetime import date, timedelta
from itertools import count

import mysql.connector

import pytest


class _CreateCursor:
    def __init__(self, conn):
        self.conn = conn
        self.rows = []

    def execute(self, query, params=()):
        db = self.conn
        if "FROM class WHERE" in query:
            class_id, user_id = params
            self.rows = [{"id": class_id}] if db.classes.get(class_id) == user_id else []
        elif "FROM class_dialog cd" in query:
            self.rows = [{"kb_ids": '["kb-1"]'}] if params[0] in db.classes else []
        elif "FROM document WHERE" in query:
            self.rows = [{"id": "doc-1"}] if "kb-1" in params else []
        elif "SELECT id FROM weekly_progress" in query:
            class_id, name, start, end = params
            self.rows = [
                {"id": row["id"]} for row in db.progresses.values()
                if (row["class_id"], row["name"], row["start"], row["end"])
                == (class_id, name, start, end)
            ]
        elif "SELECT doc_id, quiz_threshold" in query:
            self.rows = [
                {"doc_id": doc_id, "quiz_threshold": threshold}
                for progress_id, doc_id, threshold in db.docs
                if progress_id == params[0]
            ]
        elif "INSERT INTO weekly_progress_doc" in query:
            _, progress_id, doc_id, threshold, *_ = params
            db.pending_docs.append((progress_id, doc_id, threshold))
        elif "INSERT INTO weekly_progress" in query:
            progress_id, class_id, name, start, end, *_ = params
            if class_id == db.fail_on_class:
                raise mysql.connector.Error("insert failed")
            db.pending_progresses[progress_id] = {
                "id": progress_id, "class_id": class_id,
                "name": name, "start": start, "end": end,
            }
        else:
            raise AssertionError(query)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class _CreateConnection:
    def __init__(self):
        self.classes = {"class-1": "teacher-1", "class-2": "teacher-1", "foreign": "other"}
        self.progresses = {}
        self.docs = []
        self.pending_progresses = {}
        self.pending_docs = []
        self.fail_on_class = None
        self.commits = 0
        self.rollbacks = 0

    def cursor(self, dictionary=False):
        return _CreateCursor(self)

    def commit(self):
        self.progresses.update(self.pending_progresses)
        self.docs.extend(self.pending_docs)
        self.pending_progresses = {}
        self.pending_docs = []
        self.commits += 1

    def rollback(self):
        self.pending_progresses = {}
        self.pending_docs = []
        self.rollbacks += 1

    def close(self):
        pass


@pytest.fixture
def create_db(monkeypatch):
    db = _CreateConnection()
    ids = count(1)
    monkeypatch.setattr(service, "get_current_user", lambda: {"user_id": "teacher-1"})
    monkeypatch.setattr(service.mysql.connector, "connect", lambda **kwargs: db)
    monkeypatch.setattr(service, "generate_uuid", lambda: f"id-{next(ids)}")
    return db


@pytest.fixture
def create_data():
    return {
        "name": "第1周", "week_start": "2026-09-01", "week_end": "2026-09-07",
        "doc_ids": ["doc-1"], "quiz_thresholds": {"doc-1": 80},
    }


def test_batch_create_and_retry_return_same_ids(create_db, create_data):
    success, ids = service.create_weekly_progresses(["class-1", "class-2"], create_data)
    assert success is True
    assert set(ids) == {"class-1", "class-2"}
    assert len(set(ids.values())) == 2
    assert len(create_db.progresses) == len(create_db.docs) == 2

    assert service.create_weekly_progresses(["class-1", "class-2"], create_data) == (True, ids)
    assert create_db.commits == 1
    assert len(create_db.progresses) == 2


def test_batch_rejects_empty_foreign_and_partial_existing_classes(create_db, create_data):
    assert service.create_weekly_progresses([], create_data)[0] is False
    assert service.create_weekly_progresses(["class-1", "foreign"], create_data)[0] is False
    assert create_db.progresses == {}

    assert service.create_weekly_progress("class-1", create_data)[0] is True
    success, message = service.create_weekly_progresses(["class-1", "class-2"], create_data)
    assert success is False
    assert "部分班级" in message
    assert len(create_db.progresses) == 1


def test_batch_rejects_unavailable_document_and_rolls_back_failed_insert(create_db, create_data):
    unavailable = {**create_data, "doc_ids": ["doc-2"]}
    assert service.create_weekly_progresses(["class-1", "class-2"], unavailable)[0] is False
    assert create_db.progresses == {}

    create_db.fail_on_class = "class-2"
    success, _ = service.create_weekly_progresses(["class-1", "class-2"], create_data)
    assert success is False
    assert create_db.progresses == {}
    assert create_db.docs == []
    assert create_db.rollbacks >= 2


def test_single_class_create_keeps_original_result_shape(create_db, create_data):
    success, progress_id = service.create_weekly_progress("class-1", create_data)
    assert success is True
    assert isinstance(progress_id, str)
    assert service.create_weekly_progress("class-1", create_data) == (True, progress_id)

    changed_threshold = {**create_data, "quiz_thresholds": {"doc-1": 90}}
    success, message = service.create_weekly_progress("class-1", changed_threshold)
    assert success is False
    assert "内容不同" in message
    assert len(create_db.progresses) == 1


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
    assert [student["student_id"] for student in result["students"]] == ["student-1", "student-2"]
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
