import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch


llm_service_module = ModuleType("api.db.services.llm_service")
llm_service_module.LLMBundle = MagicMock()
sys.modules.setdefault("api.db.services.llm_service", llm_service_module)

api_db_module = ModuleType("api.db")
api_db_module.LLMType = SimpleNamespace(CHAT="chat")
sys.modules.setdefault("api.db", api_db_module)

database_module = ModuleType("database")
database_module.DB_CONFIG = {}
database_module.get_db_connection = MagicMock()
database_module.get_es_client = MagicMock()
sys.modules.setdefault("database", database_module)

utils_module = ModuleType("utils")
utils_module.generate_uuid = lambda: "test-id"
sys.modules.setdefault("utils", utils_module)

from services.knowledgebases import generation


def test_generation_status_marks_partial_content_and_lists_missing_types():
    status = generation._build_generation_status("3", {"mindmap", "quiz"})

    assert status == {
        "status": "partial",
        "generated_types": ["mindmap", "quiz"],
        "missing_types": ["flashcards"],
    }


def test_video_generation_status_is_not_applicable():
    status = generation._build_generation_status("3", set(), "video")

    assert status == {
        "status": "not_applicable",
        "generated_types": [],
        "missing_types": [],
    }


def test_generation_status_query_keeps_video_not_applicable():
    cursor = MagicMock()
    cursor.fetchall.return_value = [{
        "id": "video-1",
        "run": "3",
        "type": "video",
        "generation_type": None,
    }]
    connection = MagicMock()
    connection.cursor.return_value = cursor

    with patch.object(generation, "get_db_connection", return_value=connection):
        result = generation.get_generation_statuses(["video-1"], "teacher-1")

    assert result["video-1"]["status"] == "not_applicable"
    assert result["video-1"]["missing_types"] == []


def test_retry_rejects_video_without_calling_generation():
    cursor = MagicMock()
    cursor.fetchone.return_value = {
        "id": "video-1",
        "run": "3",
        "type": "video",
        "chunk_num": 0,
        "tenant_id": "teacher-1",
    }
    connection = MagicMock()
    connection.cursor.return_value = cursor

    with (
        patch.object(generation, "get_db_connection", return_value=connection),
        patch.object(generation, "get_generation_statuses") as get_statuses,
    ):
        try:
            generation.regenerate_missing_for_document("video-1", "teacher-1")
        except ValueError as error:
            assert "视频" in str(error)
        else:
            raise AssertionError("视频文档不应触发学习内容生成")

    get_statuses.assert_not_called()


def test_retry_only_generates_missing_content_without_overwriting_successes():
    cursor = MagicMock()
    cursor.fetchone.return_value = {
        "id": "doc-1",
        "run": "3",
        "type": "pptx",
        "chunk_num": 8,
        "tenant_id": "teacher-1",
    }
    connection = MagicMock()
    connection.cursor.return_value = cursor
    current_status = {
        "status": "partial",
        "generated_types": ["mindmap", "flashcards"],
        "missing_types": ["quiz"],
    }
    final_status = {
        "status": "complete",
        "generated_types": ["mindmap", "flashcards", "quiz"],
        "missing_types": [],
    }

    with (
        patch.object(generation, "get_db_connection", return_value=connection),
        patch.object(generation, "get_generation_statuses", side_effect=[{"doc-1": current_status}, {"doc-1": final_status}]),
        patch.object(generation, "_load_parsed_content", return_value="足够长的已解析文档内容" * 20),
        patch.object(generation, "get_generation", return_value={"root": {"id": "root"}}),
        patch.object(generation, "generate_mindmap") as generate_mindmap,
        patch.object(generation, "generate_flashcards") as generate_flashcards,
        patch.object(generation, "generate_quiz", return_value=True) as generate_quiz,
    ):
        result = generation.regenerate_missing_for_document("doc-1", "teacher-1")

    generate_mindmap.assert_not_called()
    generate_flashcards.assert_not_called()
    generate_quiz.assert_called_once()
    assert result["status"] == "complete"
    assert result["regenerated_types"] == ["quiz"]
