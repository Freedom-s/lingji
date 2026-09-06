import sys
from enum import Enum
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest


database_module = ModuleType("database")
database_module.DB_CONFIG = {}
database_module.get_db_connection = MagicMock()
database_module.get_es_client = MagicMock()
database_module.get_minio_client = MagicMock()
database_module.get_redis_connection = MagicMock()
sys.modules.setdefault("database", database_module)

auth_module = ModuleType("auth")
auth_module.get_current_user = lambda: {"user_id": "teacher-1"}
sys.modules.setdefault("auth", auth_module)

strenum_module = ModuleType("strenum")


class StrEnum(str, Enum):
    pass


strenum_module.StrEnum = StrEnum
sys.modules.setdefault("strenum", strenum_module)

from services import document_cleanup
from services.files import service as file_service


def test_delete_es_chunks_uses_knowledgebase_tenant_and_groups_documents():
    es_client = MagicMock()
    es_client.indices.exists.return_value = True
    es_client.delete_by_query.return_value = {"deleted": 3, "timed_out": False, "failures": []}
    documents = [
        {"document_id": "doc-1", "chunk_num": 2, "es_tenant_id": "teacher-1"},
        {"document_id": "doc-2", "chunk_num": 1, "es_tenant_id": "teacher-1"},
        {"document_id": "video-1", "chunk_num": 0, "es_tenant_id": "teacher-1"},
    ]

    deleted = document_cleanup.delete_es_chunks(documents, es_client=es_client)

    assert deleted == 3
    es_client.delete_by_query.assert_called_once_with(
        index="ragflow_teacher-1",
        body={"query": {"terms": {"doc_id": ["doc-1", "doc-2"]}}},
        refresh=True,
        conflicts="proceed",
    )


def test_delete_es_chunks_raises_before_source_data_can_be_removed():
    es_client = MagicMock()
    es_client.indices.exists.return_value = True
    es_client.delete_by_query.return_value = {"deleted": 0, "timed_out": True, "failures": []}

    with pytest.raises(RuntimeError, match="ES 文档分块删除失败"):
        document_cleanup.delete_es_chunks(
            [{"document_id": "doc-1", "chunk_num": 2, "es_tenant_id": "teacher-1"}],
            es_client=es_client,
        )


def test_delete_document_rows_cleans_dependents_and_updates_kb_counts():
    cursor = MagicMock()
    documents = [
        {"document_id": "doc-1", "kb_id": "kb-1", "chunk_num": 2},
        {"document_id": "doc-2", "kb_id": "kb-1", "chunk_num": 3},
    ]

    deleted = document_cleanup.delete_document_rows(cursor, documents)

    assert deleted == 2
    executed_sql = [call.args[0] for call in cursor.execute.call_args_list]
    for table_name in document_cleanup.DOCUMENT_CHILD_TABLES:
        assert any(f"DELETE FROM {table_name}" in sql for sql in executed_sql)
    assert any("DELETE FROM file2document" in sql for sql in executed_sql)
    assert any("DELETE FROM document" in sql for sql in executed_sql)

    update_calls = [
        call
        for call in cursor.execute.call_args_list
        if "UPDATE knowledgebase" in call.args[0]
    ]
    assert len(update_calls) == 1
    assert update_calls[0].args[1][0:2] == (2, 5)
    assert update_calls[0].args[1][3] == "kb-1"


def test_file_delete_stops_before_mysql_and_minio_when_es_cleanup_fails():
    cursor = MagicMock()
    cursor.fetchone.return_value = {
        "id": "file-1",
        "parent_id": "teacher-1",
        "name": "course.pdf",
        "location": "file-1/source/course.pdf",
        "type": "pdf",
    }
    cursor.fetchall.side_effect = [
        [{
            "document_id": "doc-1",
            "kb_id": "kb-1",
            "location": "file-1/source/course.pdf",
            "chunk_num": 3,
            "es_tenant_id": "teacher-1",
        }],
        [{"location": "file-1/pages/0001.jpg"}],
    ]
    connection = MagicMock()
    connection.cursor.return_value = cursor
    minio_client = MagicMock()

    with (
        patch.object(file_service, "get_db_connection", return_value=connection),
        patch.object(file_service, "get_minio_client", return_value=minio_client),
        patch.object(file_service, "delete_es_chunks", side_effect=RuntimeError("ES unavailable")),
        pytest.raises(RuntimeError, match="ES unavailable"),
    ):
        file_service.delete_file("file-1")

    executed_sql = [call.args[0] for call in cursor.execute.call_args_list]
    assert not any(sql.lstrip().upper().startswith("DELETE") for sql in executed_sql)
    minio_client.remove_object.assert_not_called()
    cursor.close.assert_called_once()
    connection.close.assert_called_once()
