import json
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch


mysql_module = ModuleType("mysql")
mysql_connector_module = ModuleType("mysql.connector")
mysql_connector_module.connect = MagicMock()
mysql_connector_module.Error = Exception
mysql_module.connector = mysql_connector_module
sys.modules.setdefault("mysql", mysql_module)
sys.modules.setdefault("mysql.connector", mysql_connector_module)

database_module = ModuleType("database")
database_module.DB_CONFIG = {}
database_module.get_db_connection = MagicMock()
sys.modules.setdefault("database", database_module)

from services.conversation import service


def test_messages_keep_their_matching_assistant_references():
    messages = [
        {"id": "u-1", "role": "user", "content": "什么是围岩压力？"},
        {"id": "a-1", "role": "assistant", "content": "围岩压力是……"},
        {"id": "u-2", "role": "user", "content": "有哪些分类？"},
        {"id": "a-2", "role": "assistant", "content": "可分为……"},
    ]
    references = [
        {"chunks": [{"docnm_kwd": "第一章.pdf", "page_num_int": 3}], "doc_aggs": []},
        {"chunks": [{"docnm_kwd": "第二章.pptx", "page_num_int": 8}], "doc_aggs": []},
    ]

    result = service.normalize_conversation_messages(messages, references)

    assert result[0]["reference"] is None
    assert result[1]["reference"]["chunks"][0]["documentName"] == "第一章.pdf"
    assert result[3]["reference"]["chunks"][0]["pageNumber"] == 8


def test_conversation_detail_is_scoped_to_teacher_class_and_student_membership():
    cursor = MagicMock()
    cursor.fetchone.return_value = {
        "id": "conv-1",
        "name": "围岩压力讨论",
        "dialog_id": "dialog-1",
        "assistant_name": "课程助教",
        "student_id": "student-1",
        "student_name": "李明",
        "student_email": "20260001@student.cumtb.edu.cn",
        "class_id": "class-1",
        "class_name": "采矿一班",
        "message": json.dumps([{"role": "user", "content": "问题"}]),
        "reference": "[]",
        "create_date": None,
        "update_date": None,
    }
    connection = MagicMock()
    connection.cursor.return_value = cursor

    with patch("services.conversation.service.mysql.connector.connect", return_value=connection):
        detail = service.get_conversation_detail("teacher-1", "class-1", "conv-1")

    sql = cursor.execute.call_args.args[0]
    assert "c.tenant_id = %s" in sql
    assert "uc.role = 'student'" in sql
    assert "cd.dialog_id = conv.dialog_id" in sql
    assert cursor.execute.call_args.args[1] == ("class-1", "conv-1", "class-1", "teacher-1")
    assert detail["studentName"] == "李明"


def test_html_is_removed_from_reference_snippets():
    messages = [{"role": "assistant", "content": "回答"}]
    references = [{
        "chunks": [{
            "docnm_kwd": "课件.pdf",
            "content_with_weight": "<p>围岩<strong>压力</strong></p>",
            "similarity": 0.92,
        }],
        "doc_aggs": [],
    }]

    result = service.normalize_conversation_messages(messages, references)

    assert result[0]["reference"]["chunks"][0]["content"] == "围岩 压力"
    assert result[0]["reference"]["chunks"][0]["similarity"] == 0.92
