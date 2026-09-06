import html
import json
import re

import mysql.connector

from database import DB_CONFIG


def _decode_json(value, fallback):
    if value is None:
        return fallback
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def _format_datetime(value):
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else ""


def _plain_text(value):
    if not value:
        return ""
    without_tags = re.sub(r"<[^>]+>", " ", str(value))
    return re.sub(r"\s+", " ", html.unescape(without_tags)).strip()


def _normalize_reference(reference):
    if not isinstance(reference, dict):
        return {"documents": [], "chunks": [], "total": 0}

    documents = []
    for item in reference.get("doc_aggs") or []:
        if not isinstance(item, dict):
            continue
        documents.append({
            "documentId": item.get("doc_id", ""),
            "documentName": item.get("doc_name", item.get("docnm_kwd", "未命名文档")),
            "count": item.get("count", 0),
        })

    chunks = []
    for item in reference.get("chunks") or []:
        if not isinstance(item, dict):
            continue
        chunks.append({
            "chunkId": item.get("chunk_id", item.get("id", item.get("page_id", ""))),
            "documentId": item.get("doc_id", ""),
            "documentName": item.get("docnm_kwd", item.get("doc_name", "未命名文档")),
            "pageNumber": item.get("page_num_int"),
            "content": _plain_text(item.get("content_with_weight", item.get("content", ""))),
            "similarity": item.get("similarity"),
        })

    return {
        "documents": documents,
        "chunks": chunks,
        "total": reference.get("total", len(chunks)),
    }


def normalize_conversation_messages(messages, references):
    """把 conversation.message 与按助手回答顺序保存的 reference 对齐。"""
    decoded_messages = _decode_json(messages, [])
    decoded_references = _decode_json(references, [])
    if not isinstance(decoded_messages, list):
        decoded_messages = []
    if not isinstance(decoded_references, list):
        decoded_references = []

    assistant_index = 0
    result = []
    for index, message in enumerate(decoded_messages):
        if not isinstance(message, dict):
            continue
        role = message.get("role", "unknown")
        normalized_reference = None
        if role == "assistant":
            raw_reference = decoded_references[assistant_index] if assistant_index < len(decoded_references) else None
            reference = _normalize_reference(raw_reference)
            if reference["documents"] or reference["chunks"]:
                normalized_reference = reference
            assistant_index += 1

        result.append({
            "id": str(message.get("id") or f"message-{index}"),
            "role": role,
            "content": str(message.get("content") or ""),
            "createdAt": message.get("created_at"),
            "reference": normalized_reference,
        })
    return result


def get_conversation_classes(teacher_id):
    """获取当前老师自己的班级及其学生、会话数量。"""
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT
                c.id,
                c.name,
                COUNT(DISTINCT uc.user_id) AS student_count,
                COUNT(DISTINCT conv.id) AS conversation_count
            FROM class c
            LEFT JOIN user_class uc
                ON uc.class_id = c.id
                AND uc.role = 'student'
                AND uc.status = '1'
            LEFT JOIN class_dialog cd ON cd.class_id = c.id
            LEFT JOIN conversation conv
                ON conv.user_id = uc.user_id
                AND conv.dialog_id = cd.dialog_id
            WHERE c.tenant_id = %s AND c.status = '1'
            GROUP BY c.id, c.name
            ORDER BY c.name ASC
            """,
            (teacher_id,),
        )
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "studentCount": row.get("student_count") or 0,
                "conversationCount": row.get("conversation_count") or 0,
            }
            for row in cursor.fetchall()
        ]
    finally:
        cursor.close()
        conn.close()


def get_class_students(teacher_id, class_id):
    """获取老师指定班级中的学生，并附带该班内会话统计。"""
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT
                u.id,
                u.nickname,
                u.email,
                COUNT(DISTINCT conv.id) AS conversation_count,
                MAX(conv.update_date) AS last_active_at
            FROM class c
            JOIN user_class uc
                ON uc.class_id = c.id
                AND uc.role = 'student'
                AND uc.status = '1'
            JOIN user u ON u.id = uc.user_id
            LEFT JOIN class_dialog cd ON cd.class_id = c.id
            LEFT JOIN conversation conv
                ON conv.user_id = u.id
                AND conv.dialog_id = cd.dialog_id
            WHERE c.id = %s AND c.tenant_id = %s AND c.status = '1'
            GROUP BY u.id, u.nickname, u.email
            ORDER BY u.nickname ASC, u.email ASC
            """,
            (class_id, teacher_id),
        )
        return [
            {
                "id": row["id"],
                "name": row.get("nickname") or row.get("email") or "未命名学生",
                "email": row.get("email") or "",
                "conversationCount": row.get("conversation_count") or 0,
                "lastActiveAt": _format_datetime(row.get("last_active_at")),
            }
            for row in cursor.fetchall()
        ]
    finally:
        cursor.close()
        conn.close()


def _conversation_filters(class_id, teacher_id, student_id=None, keyword=""):
    clauses = [
        "c.id = %s",
        "c.tenant_id = %s",
        "c.status = '1'",
        "uc.role = 'student'",
        "uc.status = '1'",
    ]
    params = [class_id, teacher_id]
    if student_id:
        clauses.append("conv.user_id = %s")
        params.append(student_id)
    if keyword:
        clauses.append("(conv.name LIKE %s OR CAST(conv.message AS CHAR) LIKE %s OR u.nickname LIKE %s)")
        like_keyword = f"%{keyword}%"
        params.extend([like_keyword, like_keyword, like_keyword])
    return " AND ".join(clauses), params


def get_conversations(teacher_id, class_id, student_id=None, keyword="", page=1, size=20):
    """按班级和学生获取真实的 conversation 记录。"""
    page = max(int(page), 1)
    size = min(max(int(size), 1), 100)
    where_sql, params = _conversation_filters(class_id, teacher_id, student_id, keyword.strip())

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        base_from = f"""
            FROM conversation conv
            JOIN user u ON u.id = conv.user_id
            JOIN user_class uc ON uc.user_id = conv.user_id AND uc.class_id = %s
            JOIN class c ON c.id = uc.class_id
            JOIN class_dialog cd ON cd.class_id = c.id AND cd.dialog_id = conv.dialog_id
            JOIN dialog d ON d.id = conv.dialog_id
            WHERE {where_sql}
        """
        query_params = [class_id, *params]
        cursor.execute(f"SELECT COUNT(DISTINCT conv.id) AS total {base_from}", query_params)
        total = cursor.fetchone()["total"]

        cursor.execute(
            f"""
            SELECT DISTINCT
                conv.id,
                conv.name,
                conv.message,
                conv.create_date,
                conv.update_date,
                u.id AS student_id,
                u.nickname AS student_name,
                u.email AS student_email,
                c.id AS class_id,
                c.name AS class_name,
                d.id AS dialog_id,
                d.name AS assistant_name
            {base_from}
            ORDER BY conv.update_date DESC, conv.create_date DESC
            LIMIT %s OFFSET %s
            """,
            [*query_params, size, (page - 1) * size],
        )

        conversations = []
        for row in cursor.fetchall():
            messages = _decode_json(row.get("message"), [])
            if not isinstance(messages, list):
                messages = []
            questions = [
                str(item.get("content") or "")
                for item in messages
                if isinstance(item, dict) and item.get("role") == "user"
            ]
            conversations.append({
                "id": row["id"],
                "name": row.get("name") or "未命名会话",
                "studentId": row["student_id"],
                "studentName": row.get("student_name") or row.get("student_email") or "未命名学生",
                "studentEmail": row.get("student_email") or "",
                "classId": row["class_id"],
                "className": row["class_name"],
                "dialogId": row["dialog_id"],
                "assistantName": row.get("assistant_name") or "未命名助教",
                "messageCount": len(messages),
                "questionCount": len(questions),
                "latestQuestion": questions[-1] if questions else "暂无学生提问",
                "createTime": _format_datetime(row.get("create_date")),
                "updateTime": _format_datetime(row.get("update_date")),
            })
        return conversations, total
    finally:
        cursor.close()
        conn.close()


def get_conversation_detail(teacher_id, class_id, conversation_id):
    """获取会话内容；查询本身强制校验老师、班级、学生和助教四层关系。"""
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT DISTINCT
                conv.id,
                conv.name,
                conv.message,
                conv.reference,
                conv.create_date,
                conv.update_date,
                conv.dialog_id,
                d.name AS assistant_name,
                u.id AS student_id,
                u.nickname AS student_name,
                u.email AS student_email,
                c.id AS class_id,
                c.name AS class_name
            FROM conversation conv
            JOIN user u ON u.id = conv.user_id
            JOIN user_class uc ON uc.user_id = conv.user_id AND uc.class_id = %s
            JOIN class c ON c.id = uc.class_id
            JOIN class_dialog cd ON cd.class_id = c.id AND cd.dialog_id = conv.dialog_id
            JOIN dialog d ON d.id = conv.dialog_id
            WHERE conv.id = %s
                AND c.id = %s
                AND c.tenant_id = %s
                AND c.status = '1'
                AND uc.role = 'student'
                AND uc.status = '1'
            LIMIT 1
            """,
            (class_id, conversation_id, class_id, teacher_id),
        )
        row = cursor.fetchone()
        if not row:
            return None

        messages = normalize_conversation_messages(row.get("message"), row.get("reference"))
        return {
            "id": row["id"],
            "name": row.get("name") or "未命名会话",
            "studentId": row["student_id"],
            "studentName": row.get("student_name") or row.get("student_email") or "未命名学生",
            "studentEmail": row.get("student_email") or "",
            "classId": row["class_id"],
            "className": row["class_name"],
            "dialogId": row["dialog_id"],
            "assistantName": row.get("assistant_name") or "未命名助教",
            "messageCount": len(messages),
            "questionCount": sum(item["role"] == "user" for item in messages),
            "createTime": _format_datetime(row.get("create_date")),
            "updateTime": _format_datetime(row.get("update_date")),
            "messages": messages,
        }
    finally:
        cursor.close()
        conn.close()
