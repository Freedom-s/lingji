import json
import sys
from datetime import date
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
                "explanations": {"A": "应力是围岩压力的表现。", "B": "温度不是压力。"},
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


def test_wrong_question_detail_returns_attempts_for_selected_class():
    cursor = MagicMock()
    cursor.fetchall.side_effect = [
        [{
            "id": "attempt-1",
            "student_id": "student-1",
            "student_name": "张三",
            "student_email": "zhang@example.com",
            "student_answer": "B",
            "is_correct": 0,
            "create_date": "2026-09-14 10:00:00",
            "document_name": "第一章测验",
        }],
        [{
            "doc_id": "doc-1",
            "content": json.dumps([{
                "id": 3,
                "question": "围岩压力是什么？",
                "options": {"A": "应力", "B": "温度"},
                "correct": "A",
                "explanations": {"A": "应力是围岩压力的表现。", "B": "温度不是压力。"},
            }]),
        }],
    ]
    connection = MagicMock()
    connection.cursor.return_value = cursor

    with patch("services.dashboard.service.get_db_connection", return_value=connection):
        success, result = service.get_wrong_question_detail(
            "teacher-1", "doc-1", "3", class_id="class-1", time_range="7d"
        )

    assert success is True
    assert result["question"] == "围岩压力是什么？"
    assert result["correct_answer"] == "A. 应力"
    assert result["attempts"][0]["student_answer"] == "B. 温度"
    assert result["attempts"][0]["answer_explanation"] == "温度不是压力。"
    assert result["explanations"]["A"] == "应力是围岩压力的表现。"
    assert result["wrong_student_count"] == 1
    sql = cursor.execute.call_args_list[0].args[0]
    assert "EXISTS" in sql
    assert "c.id = %s" in sql


def test_learning_insights_scopes_quizzes_to_selected_progress():
    cursor = MagicMock()
    cursor.fetchone.return_value = {
        "id": "progress-1",
        "class_id": "class-1",
        "name": "第1周",
        "week_start": date(2026, 9, 7),
        "week_end": date(2026, 9, 13),
        "class_name": "一班",
    }
    cursor.fetchall.side_effect = [
        [{"id": "class-1", "name": "一班"}],
        [{
            "id": "student-1",
            "nickname": "张三",
            "email": "zhang@example.com",
            "class_ids": "class-1",
            "class_names": "一班",
        }],
        [],
        [],
        [{
            "doc_id": "doc-1",
            "question_index": 0,
            "document_name": "CH2.pptx",
            "attempt_count": 2,
            "wrong_count": 1,
            "wrong_student_count": 1,
        }],
        [{
            "doc_id": "doc-1",
            "document_name": "CH2.pptx",
            "content": json.dumps([{
                "id": 0,
                "question": "下列哪项正确？",
                "options": {"A": "选项 A", "B": "选项 B"},
                "correct": "A",
            }]),
        }],
    ]
    connection = MagicMock()
    connection.cursor.return_value = cursor

    with patch("services.dashboard.service.get_db_connection", return_value=connection):
        success, result = service.get_learning_insights(
            "teacher-1",
            progress_id="progress-1",
        )

    assert success is True
    assert result["summary"]["student_count"] == 1
    assert result["all_questions"][0]["document_name"] == "CH2.pptx"
    assert result["all_questions"][0]["attempt_count"] == 2
    assert result["all_questions"][0]["wrong_count"] == 1
    quiz_sql, quiz_params = cursor.execute.call_args_list[3].args
    assert "weekly_progress_doc" in quiz_sql
    assert "sqr.create_date >= %s" not in quiz_sql
    assert quiz_params == (
        "teacher-1",
        "student-1",
        "teacher-1",
        date(2026, 9, 7),
        date(2026, 9, 13),
    )
