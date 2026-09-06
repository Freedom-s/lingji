"""教师端知识点视频挂载服务。"""

import json
from datetime import datetime

from database import get_db_connection
from utils import generate_uuid


def _load_json(value):
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return None
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return None


def _normalize_node(node):
    if not isinstance(node, dict):
        return None
    node_id = str(node.get("id") or "").strip()
    label = str(node.get("label") or "").strip()
    if not node_id or not label:
        return None
    children = []
    for child in node.get("children") or []:
        normalized = _normalize_node(child)
        if normalized:
            children.append(normalized)
    return {"id": node_id, "label": label, "children": children}


def _mindmap_root(content):
    data = _load_json(content)
    if not isinstance(data, dict):
        return None
    return _normalize_node(data.get("root"))


def _node_labels(root):
    labels = {}

    def walk(node):
        if not node:
            return
        labels[node["id"]] = node["label"]
        for child in node.get("children") or []:
            walk(child)

    walk(root)
    return labels


def _assert_owned_knowledgebase(cursor, kb_id, user_id):
    cursor.execute(
        "SELECT id FROM knowledgebase WHERE id = %s AND tenant_id = %s",
        (kb_id, user_id),
    )
    if not cursor.fetchone():
        raise PermissionError("知识库不存在或无权访问")


def get_binding_options(kb_id: str, user_id: str) -> dict:
    """返回同一知识库内可挂载的已解析课件及其思维导图。"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        _assert_owned_knowledgebase(cursor, kb_id, user_id)
        cursor.execute(
            """
            SELECT d.id, d.name, d.type, dg.content AS mindmap_content
            FROM document d
            LEFT JOIN document_generation dg
                ON dg.doc_id = d.id AND dg.generation_type = 'mindmap'
            WHERE d.kb_id = %s AND d.type <> 'video' AND d.run = '3'
            ORDER BY d.name ASC, d.create_time ASC
            """,
            (kb_id,),
        )
        coursewares = []
        for row in cursor.fetchall():
            root = _mindmap_root(row.get("mindmap_content"))
            if not root:
                continue
            coursewares.append({
                "id": row["id"],
                "name": row["name"],
                "type": row.get("type"),
                "root": root,
            })
        return {"coursewares": coursewares}
    finally:
        cursor.close()
        conn.close()


def get_video_binding(video_doc_id: str, user_id: str) -> dict | None:
    """获取老师名下某视频当前的知识点挂载。"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT
                v.id AS video_doc_id,
                v.name AS video_name,
                v.kb_id,
                b.courseware_doc_id,
                b.knowledge_point_id,
                b.sort_order,
                c.name AS courseware_name,
                dg.content AS mindmap_content
            FROM document v
            JOIN knowledgebase kb ON kb.id = v.kb_id
            LEFT JOIN knowledge_point_video_binding b ON b.video_doc_id = v.id
            LEFT JOIN document c ON c.id = b.courseware_doc_id
            LEFT JOIN document_generation dg
                ON dg.doc_id = c.id AND dg.generation_type = 'mindmap'
            WHERE v.id = %s AND v.type = 'video' AND kb.tenant_id = %s
            """,
            (video_doc_id, user_id),
        )
        row = cursor.fetchone()
        if not row:
            raise PermissionError("视频不存在或无权访问")
        if not row.get("courseware_doc_id"):
            return None
        labels = _node_labels(_mindmap_root(row.get("mindmap_content")))
        return {
            "video_doc_id": row["video_doc_id"],
            "video_name": row["video_name"],
            "kb_id": row["kb_id"],
            "courseware_doc_id": row["courseware_doc_id"],
            "courseware_name": row.get("courseware_name"),
            "knowledge_point_id": row["knowledge_point_id"],
            "knowledge_point_name": labels.get(row["knowledge_point_id"], row["knowledge_point_id"]),
            "sort_order": int(row.get("sort_order") or 0),
        }
    finally:
        cursor.close()
        conn.close()


def get_knowledgebase_video_bindings(kb_id: str, user_id: str) -> dict:
    """返回知识库内全部有效视频及挂载状态，供老师按知识点集中管理。"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        _assert_owned_knowledgebase(cursor, kb_id, user_id)
        cursor.execute(
            """
            SELECT
                v.id AS video_doc_id,
                v.name AS video_name,
                b.courseware_doc_id,
                b.knowledge_point_id,
                b.sort_order,
                c.name AS courseware_name,
                dg.content AS mindmap_content
            FROM document v
            LEFT JOIN knowledge_point_video_binding b ON b.video_doc_id = v.id
            LEFT JOIN document c ON c.id = b.courseware_doc_id
            LEFT JOIN document_generation dg
                ON dg.doc_id = c.id AND dg.generation_type = 'mindmap'
            WHERE v.kb_id = %s AND v.type = 'video' AND v.status = '1'
            ORDER BY v.name ASC, v.create_time ASC
            """,
            (kb_id,),
        )
        videos = []
        for row in cursor.fetchall():
            labels = _node_labels(_mindmap_root(row.get("mindmap_content")))
            videos.append({
                "video_doc_id": row["video_doc_id"],
                "video_name": row["video_name"],
                "courseware_doc_id": row.get("courseware_doc_id"),
                "courseware_name": row.get("courseware_name"),
                "knowledge_point_id": row.get("knowledge_point_id"),
                "knowledge_point_name": labels.get(row.get("knowledge_point_id")),
                "sort_order": int(row.get("sort_order") or 0),
            })
        return {"videos": videos}
    finally:
        cursor.close()
        conn.close()


def save_video_binding(
    video_doc_id: str,
    courseware_doc_id: str,
    knowledge_point_id: str,
    user_id: str,
) -> dict:
    """新增或修改视频挂载；不修改视频文档和学生观看记录。"""
    knowledge_point_id = str(knowledge_point_id or "").strip()
    if not courseware_doc_id or not knowledge_point_id:
        raise ValueError("课件和知识点不能为空")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("START TRANSACTION")
        cursor.execute(
            """
            SELECT
                v.id AS video_doc_id,
                v.name AS video_name,
                v.kb_id AS video_kb_id,
                v.type AS video_type,
                c.id AS courseware_doc_id,
                c.name AS courseware_name,
                c.kb_id AS courseware_kb_id,
                c.type AS courseware_type,
                c.run AS courseware_run
            FROM document v
            JOIN knowledgebase kb ON kb.id = v.kb_id
            JOIN document c ON c.id = %s
            WHERE v.id = %s AND kb.tenant_id = %s
            """,
            (courseware_doc_id, video_doc_id, user_id),
        )
        documents = cursor.fetchone()
        if not documents:
            raise PermissionError("视频或课件不存在，或者无权访问")
        if str(documents.get("video_type") or "").lower() != "video":
            raise ValueError("只能把视频文件挂载到知识点")
        if documents["video_kb_id"] != documents["courseware_kb_id"]:
            raise ValueError("视频和课件必须属于同一个知识库")
        if str(documents.get("courseware_type") or "").lower() == "video":
            raise ValueError("视频不能作为目标课件")
        if str(documents.get("courseware_run")) != "3":
            raise ValueError("目标课件尚未解析完成")

        cursor.execute(
            """
            SELECT content FROM document_generation
            WHERE doc_id = %s AND generation_type = 'mindmap'
            """,
            (courseware_doc_id,),
        )
        mindmap = cursor.fetchone()
        labels = _node_labels(_mindmap_root(mindmap.get("content") if mindmap else None))
        if knowledge_point_id not in labels:
            raise ValueError("所选知识点不存在，请刷新后重新选择")

        cursor.execute(
            """
            SELECT id, courseware_doc_id, knowledge_point_id, sort_order
            FROM knowledge_point_video_binding
            WHERE video_doc_id = %s
            FOR UPDATE
            """,
            (video_doc_id,),
        )
        existing = cursor.fetchone()
        keep_order = (
            existing
            and existing["courseware_doc_id"] == courseware_doc_id
            and existing["knowledge_point_id"] == knowledge_point_id
        )
        if keep_order:
            sort_order = int(existing.get("sort_order") or 0)
        else:
            cursor.execute(
                """
                SELECT COALESCE(MAX(sort_order), -1) + 1 AS next_order
                FROM knowledge_point_video_binding
                WHERE courseware_doc_id = %s AND knowledge_point_id = %s
                """,
                (courseware_doc_id, knowledge_point_id),
            )
            sort_order = int(cursor.fetchone()["next_order"] or 0)

        now = datetime.now()
        timestamp = int(now.timestamp() * 1000)
        if existing:
            cursor.execute(
                """
                UPDATE knowledge_point_video_binding
                SET courseware_doc_id = %s,
                    knowledge_point_id = %s,
                    sort_order = %s,
                    update_time = %s,
                    update_date = %s
                WHERE id = %s
                """,
                (
                    courseware_doc_id,
                    knowledge_point_id,
                    sort_order,
                    timestamp,
                    now,
                    existing["id"],
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO knowledge_point_video_binding
                    (id, create_time, create_date, update_time, update_date,
                     video_doc_id, courseware_doc_id, knowledge_point_id, sort_order, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    generate_uuid(),
                    timestamp,
                    now,
                    timestamp,
                    now,
                    video_doc_id,
                    courseware_doc_id,
                    knowledge_point_id,
                    sort_order,
                    user_id,
                ),
            )
        conn.commit()
        return {
            "video_doc_id": video_doc_id,
            "video_name": documents["video_name"],
            "kb_id": documents["video_kb_id"],
            "courseware_doc_id": courseware_doc_id,
            "courseware_name": documents["courseware_name"],
            "knowledge_point_id": knowledge_point_id,
            "knowledge_point_name": labels[knowledge_point_id],
            "sort_order": sort_order,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def reorder_knowledge_point_videos(
    courseware_doc_id: str,
    knowledge_point_id: str,
    video_doc_ids: list[str],
    user_id: str,
) -> dict:
    """调整同一知识点下视频顺序，不修改视频和学习记录。"""
    if not knowledge_point_id:
        raise ValueError("知识点不能为空")
    if len(video_doc_ids) != len(set(video_doc_ids)):
        raise ValueError("视频列表中存在重复项")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("START TRANSACTION")
        cursor.execute(
            """
            SELECT c.id, dg.content AS mindmap_content
            FROM document c
            JOIN knowledgebase kb ON kb.id = c.kb_id
            LEFT JOIN document_generation dg
                ON dg.doc_id = c.id AND dg.generation_type = 'mindmap'
            WHERE c.id = %s AND c.type <> 'video' AND kb.tenant_id = %s
            """,
            (courseware_doc_id, user_id),
        )
        courseware = cursor.fetchone()
        if not courseware:
            raise PermissionError("课件不存在或无权访问")
        labels = _node_labels(_mindmap_root(courseware.get("mindmap_content")))
        if knowledge_point_id not in labels:
            raise ValueError("所选知识点不存在，请刷新后重试")

        cursor.execute(
            """
            SELECT video_doc_id
            FROM knowledge_point_video_binding
            WHERE courseware_doc_id = %s AND knowledge_point_id = %s
            FOR UPDATE
            """,
            (courseware_doc_id, knowledge_point_id),
        )
        existing_ids = [row["video_doc_id"] for row in cursor.fetchall()]
        if set(existing_ids) != set(video_doc_ids):
            raise ValueError("视频挂载状态已变化，请刷新后重试")

        for sort_order, video_doc_id in enumerate(video_doc_ids):
            cursor.execute(
                """
                UPDATE knowledge_point_video_binding
                SET sort_order = %s, update_time = %s, update_date = %s
                WHERE video_doc_id = %s
                  AND courseware_doc_id = %s
                  AND knowledge_point_id = %s
                """,
                (
                    sort_order,
                    int(datetime.now().timestamp() * 1000),
                    datetime.now(),
                    video_doc_id,
                    courseware_doc_id,
                    knowledge_point_id,
                ),
            )
        conn.commit()
        return {"video_doc_ids": video_doc_ids}
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def delete_video_binding(video_doc_id: str, user_id: str) -> bool:
    """解除挂载，不删除视频或任何学生观看记录。"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT v.id
            FROM document v
            JOIN knowledgebase kb ON kb.id = v.kb_id
            WHERE v.id = %s AND v.type = 'video' AND kb.tenant_id = %s
            """,
            (video_doc_id, user_id),
        )
        if not cursor.fetchone():
            raise PermissionError("视频不存在或无权访问")
        cursor.execute(
            "DELETE FROM knowledge_point_video_binding WHERE video_doc_id = %s",
            (video_doc_id,),
        )
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
