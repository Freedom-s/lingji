import json
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch


database_module = ModuleType("database")
database_module.get_db_connection = MagicMock()
sys.modules.setdefault("database", database_module)

from services.dashboard import service


def test_quiz_lookup_supports_saved_question_ids_and_position_fallback():
    rows = [{
        "doc_id": "doc-1",
        "content": json.dumps([
            {
                "id": 7,
                "question": "围岩压力是什么？",
                "options": {"A": "应力", "B": "温度"},
                "correct": "A",
            }
        ]),
    }]

    lookup = service._build_quiz_lookup(rows)

    assert lookup[("doc-1", "7")]["question"] == "围岩压力是什么？"
    assert lookup[("doc-1", "0")]["correct"] == "A"
    assert service._answer_text(lookup[("doc-1", "7")], "A") == "A. 应力"


def test_invalid_dashboard_range_falls_back_to_seven_days():
    assert service._normalize_time_range("unexpected") == "7d"
    assert service._date_condition("sqr.create_date", "unexpected") == (
        "sqr.create_date >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
    )
    assert service._format_dashboard_time("2026-09-06T20:00:00") == "2026-09-06T20:00:00"


def test_student_detail_is_scoped_to_current_teacher():
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    connection = MagicMock()
    connection.cursor.return_value = cursor

    with patch("services.dashboard.service.get_db_connection", return_value=connection):
        success, result = service.get_student_learning_detail("teacher-1", "student-1")

    sql = cursor.execute.call_args.args[0]
    assert "c.tenant_id = %s" in sql
    assert cursor.execute.call_args.args[1] == ("student-1", "teacher-1")
    assert success is False
    assert result == "学生不存在或不属于当前老师"
