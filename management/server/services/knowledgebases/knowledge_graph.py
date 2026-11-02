"""知识库级知识图谱（第一版）。

第一版使用 MySQL 保存知识库级的图谱快照，而不是引入新的图数据库：
教师可以基于课件已有的思维导图和题目关联生成一份草稿，查看后再发布。
这样既保留了文档级知识点的来源，又为后续按知识点推荐题目保留了稳定入口。
"""

import json
import threading
from datetime import datetime

from database import get_db_connection
from utils import generate_uuid

from . import generation


MAX_SOURCE_DOCUMENTS = 80
MAX_SOURCE_NODES_PER_DOCUMENT = 120
MAX_GRAPH_NODES = 500
MAX_GRAPH_EDGES = 1200
MAX_TEXT_LENGTH = 600
MAX_SOURCE_PROMPT_CHARS = 100000

_GRAPH_LOCK = threading.Lock()


def _now():
    now = datetime.now()
    return int(now.timestamp() * 1000), now.strftime("%Y-%m-%d %H:%M:%S")


def _json_load(value, default):
    if not value:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _clip(value, length=MAX_TEXT_LENGTH):
    text = str(value or "").strip()
    return text if len(text) <= length else text[:length] + "…"


def _ensure_schema(cursor):
    """幂等创建第一版图谱快照表，避免线上还没有迁移工具导致功能不可用。"""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_base_graph (
            id VARCHAR(64) NOT NULL,
            kb_id VARCHAR(64) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'draft',
            version INT NOT NULL DEFAULT 0,
            draft_json LONGTEXT NULL,
            published_json LONGTEXT NULL,
            source_snapshot LONGTEXT NULL,
            created_by VARCHAR(64) NOT NULL,
            generated_at DATETIME NULL,
            published_at DATETIME NULL,
            create_time BIGINT NULL,
            update_time BIGINT NULL,
            create_date DATETIME NULL,
            update_date DATETIME NULL,
            PRIMARY KEY (id),
            UNIQUE KEY uk_knowledge_base_graph_kb (kb_id),
            KEY idx_knowledge_base_graph_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )


def _get_owned_kb(cursor, kb_id, user_id):
    cursor.execute(
        """
        SELECT id, name
        FROM knowledgebase
        WHERE id = %s AND tenant_id = %s
        """,
        (kb_id, user_id),
    )
    row = cursor.fetchone()
    if not row:
        raise PermissionError("知识库不存在或无权访问")
    return row


def _walk_mindmap(node, parent_id=None, result=None):
    result = result if result is not None else []
    if not isinstance(node, dict):
        return result
    node_id = str(node.get("id") or "").strip()
    label = str(node.get("label") or "").strip()
    if node_id and label:
        result.append({"id": node_id, "label": _clip(label, 160), "parent_id": parent_id})
        parent_id = node_id
    for child in node.get("children") or []:
        _walk_mindmap(child, parent_id, result)
    return result


def _build_source_snapshot(cursor, kb_id):
    """只读取课件已有的思维导图，形成全局图谱的 LLM 输入。"""
    cursor.execute(
        """
        SELECT d.id, d.name, dg.content
        FROM document d
        LEFT JOIN document_generation dg
          ON dg.doc_id = d.id
         AND dg.generation_type = 'mindmap'
        WHERE d.kb_id = %s
          AND LOWER(COALESCE(d.type, '')) <> 'video'
        ORDER BY d.create_time ASC, d.id ASC
        """,
        (kb_id,),
    )

    documents = {}
    for row in cursor.fetchall():
        doc_id = str(row["id"])
        document = documents.setdefault(
            doc_id,
            {"doc_id": doc_id, "doc_name": _clip(row.get("name"), 200), "mindmap_nodes": []},
        )
        content = _json_load(row.get("content"), None)
        if isinstance(content, dict):
            nodes = _walk_mindmap(content.get("root"), None)
            document["mindmap_nodes"] = nodes[:MAX_SOURCE_NODES_PER_DOCUMENT]

    documents = [
        document
        for document in list(documents.values())[:MAX_SOURCE_DOCUMENTS]
        if document["mindmap_nodes"]
    ]
    compact_documents = []
    used_chars = 0
    for document in documents:
        compact_document = {
            **document,
            "mindmap_nodes": document["mindmap_nodes"][:80],
        }
        document_chars = len(json.dumps(compact_document, ensure_ascii=False, separators=(",", ":")))
        if compact_documents and used_chars + document_chars > MAX_SOURCE_PROMPT_CHARS:
            break
        compact_documents.append(compact_document)
        used_chars += document_chars

    return {
        "kb_id": str(kb_id),
        "documents": compact_documents,
    }


def _build_prompt(kb_name, source_snapshot):
    source_json = json.dumps(source_snapshot, ensure_ascii=False, separators=(",", ":"))
    system_prompt = (
        "你是高校课程知识图谱设计专家。你的任务是把多个课件中已有的知识点"
        "合并为一套稳定、可复习的全局知识图谱。"
        "只输出合法 JSON，不要输出 Markdown、解释或额外文字。"
    )
    user_prompt = f"""请为知识库“{_clip(kb_name, 120)}”生成知识图谱草稿。

处理原则：
1. 优先合并语义相同或上下位关系明确的知识点，不要因为课件名称不同而重复建点。
2. 节点名称要适合学生复习，简洁明确；aliases 放常见别名。
3. relation 只能是 prerequisite（前置）、part_of（组成/隶属）、related_to（相关）。
4. 尽量覆盖输入中的所有已有知识点；不能确定是否重复时保留节点，不要返回空数组。
5. source_refs 要保留来源课件和原知识点 id，便于教师回溯。
6. confidence 为 0 到 1 的数字。优先保证准确性，不要为了凑数量制造关系。

严格输出以下结构：
{{
  "nodes": [
    {{"id":"kp_1","name":"知识点名称","aliases":[],"parent_id":null,"confidence":0.95,"source_refs":[{{"doc_id":"真实文档ID","source_node_ids":["root"]}}]}}
  ],
  "edges": [
    {{"source":"kp_1","target":"kp_2","relation":"part_of","confidence":0.88,"evidence":"简短依据"}}
  ],
  "questions": []
}}

以下是课件现有的思维导图节点：
{source_json}"""
    return system_prompt, user_prompt


def _normalize_confidence(value):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _normalize_graph(content, source_snapshot):
    if not isinstance(content, dict):
        raise ValueError("模型返回的知识图谱不是 JSON 对象")

    source_doc_ids = {str(item["doc_id"]) for item in source_snapshot["documents"]}
    nodes = []
    node_ids = set()
    for index, item in enumerate(content.get("nodes") or []):
        if not isinstance(item, dict):
            continue
        node_id = str(item.get("id") or f"kp_{index + 1}").strip()
        name = _clip(item.get("name") or item.get("label"), 160)
        if not name or node_id in node_ids:
            continue
        node_ids.add(node_id)
        refs = []
        for ref in item.get("source_refs") or []:
            if not isinstance(ref, dict) or str(ref.get("doc_id")) not in source_doc_ids:
                continue
            refs.append(
                {
                    "doc_id": str(ref.get("doc_id")),
                    "source_node_ids": [str(value) for value in ref.get("source_node_ids") or [] if str(value).strip()],
                }
            )
        parent_id = str(item.get("parent_id") or "").strip() or None
        nodes.append(
            {
                "id": node_id,
                "name": name,
                "aliases": [_clip(value, 80) for value in item.get("aliases") or [] if str(value).strip()][:8],
                "parent_id": parent_id,
                "confidence": _normalize_confidence(item.get("confidence")),
                "source_refs": refs,
            }
        )
        if len(nodes) >= MAX_GRAPH_NODES:
            break

    for node in nodes:
        if node["parent_id"] not in node_ids or node["parent_id"] == node["id"]:
            node["parent_id"] = None

    if not nodes:
        raise ValueError("模型没有生成有效知识点")

    edges = []
    seen_edges = set()
    allowed_relations = {"prerequisite", "part_of", "related_to"}
    for item in content.get("edges") or []:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or "").strip()
        target = str(item.get("target") or "").strip()
        relation = str(item.get("relation") or "related_to").strip()
        key = (source, target, relation)
        if source not in node_ids or target not in node_ids or source == target or relation not in allowed_relations or key in seen_edges:
            continue
        seen_edges.add(key)
        edges.append(
            {
                "source": source,
                "target": target,
                "relation": relation,
                "confidence": _normalize_confidence(item.get("confidence")),
                "evidence": _clip(item.get("evidence"), 300),
            }
        )
        if len(edges) >= MAX_GRAPH_EDGES:
            break

    return {"nodes": nodes, "edges": edges, "questions": []}


def _fallback_graph_from_mindmaps(source_snapshot):
    """模型返回空结果时，基于已有思维导图生成可用的全局草稿。"""
    nodes = []
    edges = []
    node_by_label = {}
    node_by_source = {}

    for document in source_snapshot["documents"]:
        for source_node in document["mindmap_nodes"]:
            label_key = " ".join(str(source_node["label"]).strip().lower().split())
            node = node_by_label.get(label_key)
            if node is None:
                node = {
                    "id": f"kp_{len(nodes) + 1}",
                    "name": source_node["label"],
                    "aliases": [],
                    "parent_id": None,
                    "confidence": 0.65,
                    "source_refs": [],
                }
                node_by_label[label_key] = node
                nodes.append(node)
            node["source_refs"].append(
                {"doc_id": document["doc_id"], "source_node_ids": [source_node["id"]]}
            )
            node_by_source[(document["doc_id"], source_node["id"])] = node

    for document in source_snapshot["documents"]:
        for source_node in document["mindmap_nodes"]:
            parent_id = source_node.get("parent_id")
            if not parent_id:
                continue
            child = node_by_source.get((document["doc_id"], source_node["id"]))
            parent = node_by_source.get((document["doc_id"], parent_id))
            if not child or not parent or child["id"] == parent["id"]:
                continue
            child["parent_id"] = parent["id"]
            edge_key = (child["id"], parent["id"])
            if not any((item["source"], item["target"]) == edge_key for item in edges):
                edges.append(
                    {
                        "source": child["id"],
                        "target": parent["id"],
                        "relation": "part_of",
                        "confidence": 0.8,
                        "evidence": "来自课件思维导图中的父子节点关系",
                    }
                )

    return {"nodes": nodes[:MAX_GRAPH_NODES], "edges": edges[:MAX_GRAPH_EDGES], "questions": []}


def _format_graph_record(row):
    if not row:
        return {
            "status": "empty",
            "version": 0,
            "draft": None,
            "published": None,
            "generated_at": None,
            "published_at": None,
        }
    def format_date(value):
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return value

    return {
        "status": row.get("status") or "draft",
        "version": int(row.get("version") or 0),
        "draft": _json_load(row.get("draft_json"), None),
        "published": _json_load(row.get("published_json"), None),
        "generated_at": format_date(row.get("generated_at")),
        "published_at": format_date(row.get("published_at")),
    }


def get_knowledge_graph(kb_id, user_id):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        _ensure_schema(cursor)
        _get_owned_kb(cursor, kb_id, user_id)
        cursor.execute(
            """
            SELECT status, version, draft_json, published_json, generated_at, published_at
            FROM knowledge_base_graph
            WHERE kb_id = %s
            """,
            (kb_id,),
        )
        return _format_graph_record(cursor.fetchone())
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def generate_knowledge_graph(kb_id, user_id):
    """生成草稿，不覆盖已发布版本。"""
    with _GRAPH_LOCK:
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            _ensure_schema(cursor)
            kb = _get_owned_kb(cursor, kb_id, user_id)
            source_snapshot = _build_source_snapshot(cursor, kb_id)
            if not source_snapshot["documents"]:
                raise ValueError("当前知识库没有可用的课件思维导图，请先完成课件解析")

            system_prompt, user_prompt = _build_prompt(kb["name"], source_snapshot)
            chat_mdl = generation._get_llm(user_id)
            result = chat_mdl.chat(
                system_prompt,
                [{"role": "user", "content": user_prompt}],
                gen_conf={"temperature": 0.2},
            )
            try:
                graph = _normalize_graph(generation.extract_json(result), source_snapshot)
            except ValueError:
                graph = _fallback_graph_from_mindmaps(source_snapshot)
            if not graph["nodes"]:
                raise ValueError("当前课件思维导图中没有可用知识点")
            now_ts, now_date = _now()
            graph_json = json.dumps(graph, ensure_ascii=False)
            source_json = json.dumps(source_snapshot, ensure_ascii=False)
            graph_id = generate_uuid()
            cursor.execute(
                """
                INSERT INTO knowledge_base_graph
                    (id, kb_id, status, version, draft_json, source_snapshot,
                     created_by, generated_at, create_time, update_time, create_date, update_date)
                VALUES (%s, %s, 'draft', 0, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    status = 'draft', draft_json = VALUES(draft_json), source_snapshot = VALUES(source_snapshot),
                    generated_at = VALUES(generated_at), update_time = VALUES(update_time), update_date = VALUES(update_date)
                """,
                (graph_id, kb_id, graph_json, source_json, user_id, now_date, now_ts, now_ts, now_date, now_date),
            )
            conn.commit()
            return get_knowledge_graph(kb_id, user_id)
        except Exception:
            if conn:
                conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()


def publish_knowledge_graph(kb_id, user_id):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        _ensure_schema(cursor)
        _get_owned_kb(cursor, kb_id, user_id)
        cursor.execute(
            "SELECT draft_json, version FROM knowledge_base_graph WHERE kb_id = %s",
            (kb_id,),
        )
        row = cursor.fetchone()
        draft = _json_load(row.get("draft_json") if row else None, None)
        if not draft:
            raise ValueError("还没有可发布的知识图谱草稿")
        now_ts, now_date = _now()
        cursor.execute(
            """
            UPDATE knowledge_base_graph
            SET status = 'published', published_json = draft_json, version = %s,
                published_at = %s, update_time = %s, update_date = %s
            WHERE kb_id = %s
            """,
            (int(row.get("version") or 0) + 1, now_date, now_ts, now_date, kb_id),
        )
        conn.commit()
        return get_knowledge_graph(kb_id, user_id)
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
