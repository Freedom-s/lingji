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


def test_mindmap_rejects_duplicate_node_ids():
    content = {
        "title": "课程",
        "root": {
            "id": "root",
            "label": "课程",
            "children": [
                {"id": "same", "label": "知识点一", "children": []},
                {"id": "same", "label": "知识点二", "children": []},
            ],
        },
    }

    try:
        generation._normalize_mindmap(content)
    except ValueError as error:
        assert "重复" in str(error)
    else:
        raise AssertionError("重复的思维导图节点 ID 应被拒绝")


def test_flashcard_rejects_unknown_knowledge_point():
    cards = [{
        "id": 0,
        "question": "什么是测试？",
        "answer": "验证预期行为。",
        "knowledge_point_ids": ["missing"],
    }]

    try:
        generation._normalize_flashcards(cards, {"root"})
    except ValueError as error:
        assert "不存在" in str(error)
    else:
        raise AssertionError("关联不存在知识点的卡片应被拒绝")


def test_flashcard_keeps_existing_references_when_mindmap_is_missing():
    cards = [{
        "id": 0,
        "question": "什么是测试？",
        "answer": "验证预期行为。",
        "knowledge_point_ids": ["legacy-node"],
    }]

    normalized = generation._normalize_flashcards(cards, None)

    assert normalized[0]["knowledge_point_ids"] == ["legacy-node"]


def test_quiz_requires_four_complete_options():
    questions = [{
        "id": 0,
        "question": "请选择正确答案",
        "options": {"A": "一", "B": "二", "C": "三"},
        "correct": "A",
        "explanations": {},
        "knowledge_point_ids": [],
    }]

    try:
        generation._normalize_quiz(questions, set())
    except ValueError as error:
        assert "四个选项" in str(error)
    else:
        raise AssertionError("缺少选项的测验题应被拒绝")


def test_changed_item_detection_keeps_progress_for_unchanged_and_new_items():
    old_content = [
        {"id": 0, "question": "旧问题", "answer": "旧答案"},
        {"id": 1, "question": "保留问题", "answer": "保留答案"},
    ]
    new_content = [
        {"id": 0, "question": "新问题", "answer": "旧答案"},
        {"id": 1, "question": "保留问题", "answer": "保留答案"},
        {"id": 2, "question": "新增问题", "answer": "新增答案"},
    ]

    assert generation._changed_existing_item_ids(old_content, new_content) == [0]


def test_collection_ids_are_normalized_to_unique_integers():
    cards = [
        {"id": "3", "question": "问题一", "answer": "答案一", "knowledge_point_ids": []},
        {"id": 3, "question": "问题二", "answer": "答案二", "knowledge_point_ids": []},
    ]

    try:
        generation._normalize_flashcards(cards, set())
    except ValueError as error:
        assert "重复" in str(error)
    else:
        raise AssertionError("数值相同的卡片 ID 应被判定为重复")
