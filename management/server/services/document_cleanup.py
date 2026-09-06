"""Cross-store cleanup helpers for knowledge-base documents."""

from collections import defaultdict
from datetime import datetime

from database import get_es_client


DOCUMENT_CHILD_TABLES = (
    "student_progress_status",
    "weekly_progress_doc",
    "knowledge_point_mastery",
    "student_video_progress",
    "student_note",
    "student_quiz_result",
    "student_card_progress",
    "document_generation",
    "task",
)


def _unique_documents(documents):
    """Deduplicate document metadata while preserving input order."""
    unique = {}
    for document in documents:
        doc_id = str(document.get("document_id") or document.get("id") or "").strip()
        if doc_id and doc_id not in unique:
            unique[doc_id] = {**document, "document_id": doc_id}
    return list(unique.values())


def delete_es_chunks(documents, es_client=None):
    """
    Delete parsed chunks before removing MySQL/MinIO records.

    Documents with no chunks are skipped. Any ES failure is raised so callers do
    not continue deleting the source objects and leave unreadable orphan chunks.
    """
    parsed_documents = [
        document
        for document in _unique_documents(documents)
        if int(document.get("chunk_num") or 0) > 0
    ]
    if not parsed_documents:
        return 0

    grouped_doc_ids = defaultdict(list)
    for document in parsed_documents:
        tenant_id = str(document.get("es_tenant_id") or "").strip()
        if not tenant_id:
            raise ValueError(f"文档 {document['document_id']} 缺少 ES 租户 ID，已取消删除")
        grouped_doc_ids[tenant_id].append(document["document_id"])

    client = es_client or get_es_client()
    deleted_total = 0
    for tenant_id, doc_ids in grouped_doc_ids.items():
        index_name = f"ragflow_{tenant_id}"
        if not client.indices.exists(index=index_name):
            continue

        result = client.delete_by_query(
            index=index_name,
            body={"query": {"terms": {"doc_id": doc_ids}}},
            refresh=True,
            conflicts="proceed",
        )
        if result.get("timed_out") or result.get("failures") or result.get("version_conflicts"):
            details = result.get("failures") or (
                f"{result.get('version_conflicts')} 个版本冲突"
                if result.get("version_conflicts")
                else "请求超时"
            )
            raise RuntimeError(f"ES 文档分块删除失败: {details}")
        deleted_total += int(result.get("deleted") or 0)

    return deleted_total


def delete_document_rows(cursor, documents, update_knowledgebase_counts=True):
    """Delete document-owned MySQL rows and update knowledge-base counters."""
    unique_documents = _unique_documents(documents)
    if not unique_documents:
        return 0

    doc_ids = [document["document_id"] for document in unique_documents]
    placeholders = ", ".join(["%s"] * len(doc_ids))

    cursor.execute(
        f"""
        DELETE FROM knowledge_point_video_binding
        WHERE video_doc_id IN ({placeholders})
           OR courseware_doc_id IN ({placeholders})
        """,
        (*doc_ids, *doc_ids),
    )

    for table_name in DOCUMENT_CHILD_TABLES:
        cursor.execute(
            f"DELETE FROM {table_name} WHERE doc_id IN ({placeholders})",
            doc_ids,
        )

    cursor.execute(
        f"DELETE FROM file2document WHERE document_id IN ({placeholders})",
        doc_ids,
    )
    cursor.execute(
        f"DELETE FROM document WHERE id IN ({placeholders})",
        doc_ids,
    )

    if update_knowledgebase_counts:
        knowledgebase_deltas = defaultdict(lambda: {"doc_num": 0, "chunk_num": 0})
        for document in unique_documents:
            kb_id = document.get("kb_id")
            if not kb_id:
                continue
            knowledgebase_deltas[kb_id]["doc_num"] += 1
            knowledgebase_deltas[kb_id]["chunk_num"] += int(document.get("chunk_num") or 0)

        update_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for kb_id, delta in knowledgebase_deltas.items():
            cursor.execute(
                """
                UPDATE knowledgebase
                SET doc_num = GREATEST(doc_num - %s, 0),
                    chunk_num = GREATEST(chunk_num - %s, 0),
                    update_date = %s
                WHERE id = %s
                """,
                (delta["doc_num"], delta["chunk_num"], update_date, kb_id),
            )

    return len(doc_ids)
