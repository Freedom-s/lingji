import json
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch


database_module = ModuleType("database")
database_module.get_db_connection = MagicMock()
sys.modules.setdefault("database", database_module)

utils_module = ModuleType("utils")
utils_module.generate_uuid = lambda: "binding-id"
sys.modules.setdefault("utils", utils_module)

from services.knowledgebases import video_binding


def test_mindmap_nodes_are_normalized_for_tree_selector():
    content = json.dumps({
        "root": {
            "id": "root",
            "label": "课程",
            "children": [{"id": "ch1", "label": "第一章", "children": []}],
        },
    })

    root = video_binding._mindmap_root(content)

    assert root["id"] == "root"
    assert video_binding._node_labels(root) == {"root": "课程", "ch1": "第一章"}


def test_save_binding_only_inserts_relation_and_never_touches_video_progress():
    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        {
            "video_doc_id": "video-1",
            "video_name": "实验视频.mp4",
            "video_kb_id": "kb-1",
            "video_type": "video",
            "courseware_doc_id": "doc-1",
            "courseware_name": "第一章.pptx",
            "courseware_kb_id": "kb-1",
            "courseware_type": "pptx",
            "courseware_run": "3",
        },
        {"content": json.dumps({"root": {"id": "root", "label": "课程", "children": []}})},
        None,
        {"next_order": 0},
    ]
    connection = MagicMock()
    connection.cursor.return_value = cursor

    with patch.object(video_binding, "get_db_connection", return_value=connection):
        result = video_binding.save_video_binding(
            "video-1", "doc-1", "root", "teacher-1"
        )

    sql_statements = [str(call.args[0]) for call in cursor.execute.call_args_list]
    assert result["video_doc_id"] == "video-1"
    assert any("INSERT INTO knowledge_point_video_binding" in sql for sql in sql_statements)
    assert all("student_video_progress" not in sql for sql in sql_statements)
    assert all("UPDATE document" not in sql for sql in sql_statements)
    connection.commit.assert_called_once()


def test_cross_knowledgebase_binding_is_rejected():
    cursor = MagicMock()
    cursor.fetchone.return_value = {
        "video_doc_id": "video-1",
        "video_name": "实验视频.mp4",
        "video_kb_id": "kb-1",
        "video_type": "video",
        "courseware_doc_id": "doc-2",
        "courseware_name": "其他课件.pptx",
        "courseware_kb_id": "kb-2",
        "courseware_type": "pptx",
        "courseware_run": "3",
    }
    connection = MagicMock()
    connection.cursor.return_value = cursor

    with patch.object(video_binding, "get_db_connection", return_value=connection):
        try:
            video_binding.save_video_binding(
                "video-1", "doc-2", "root", "teacher-1"
            )
        except ValueError as error:
            assert "同一个知识库" in str(error)
        else:
            raise AssertionError("跨知识库挂载应被拒绝")

    connection.rollback.assert_called_once()


def test_unbinding_deletes_relation_only():
    cursor = MagicMock()
    cursor.fetchone.return_value = {"id": "video-1"}
    cursor.rowcount = 1
    connection = MagicMock()
    connection.cursor.return_value = cursor

    with patch.object(video_binding, "get_db_connection", return_value=connection):
        deleted = video_binding.delete_video_binding("video-1", "teacher-1")

    sql_statements = [str(call.args[0]) for call in cursor.execute.call_args_list]
    assert deleted is True
    assert any("DELETE FROM knowledge_point_video_binding" in sql for sql in sql_statements)
    assert all("student_video_progress" not in sql for sql in sql_statements)


def test_reorder_only_updates_binding_rows():
    cursor = MagicMock()
    cursor.fetchone.return_value = {
        "id": "doc-1",
        "mindmap_content": json.dumps({
            "root": {"id": "root", "label": "课程", "children": []}
        }),
    }
    cursor.fetchall.return_value = [
        {"video_doc_id": "video-1"},
        {"video_doc_id": "video-2"},
    ]
    connection = MagicMock()
    connection.cursor.return_value = cursor

    with patch.object(video_binding, "get_db_connection", return_value=connection):
        result = video_binding.reorder_knowledge_point_videos(
            "doc-1", "root", ["video-2", "video-1"], "teacher-1"
        )

    sql_statements = [str(call.args[0]) for call in cursor.execute.call_args_list]
    assert result["video_doc_ids"] == ["video-2", "video-1"]
    assert sum("UPDATE knowledge_point_video_binding" in sql for sql in sql_statements) == 2
    assert all("student_video_progress" not in sql for sql in sql_statements)
    connection.commit.assert_called_once()
