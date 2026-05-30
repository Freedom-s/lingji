"""
文档内容生成模块

负责在文档解析完成后，调用 LLM 为 PPT 课件生成：
- 思维导图 (mindmap)
- 概念速记闪卡 (flashcards)
- 随堂测验选择题 (quiz)

同时提供学生互动记录的读写方法。
"""

import json
import re
import sys
import os
import traceback
from datetime import datetime

# 确保可以导入 api 包
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))

from api.db.services.llm_service import LLMBundle
from api.db import LLMType
from database import get_db_connection
from utils import generate_uuid
from . import logger


# ============================================================
# 辅助函数
# ============================================================

def extract_json(text: str):
    """从 LLM 返回文本中提取 JSON，支持 markdown 代码块包裹的情况"""
    if not text:
        return None
    t = text.strip()

    # 尝试提取 ```json ... ``` 或 ``` ... ``` 代码块
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", t)
    if m:
        t = m.group(1).strip()

    # 找到最外层的 JSON 数组或对象
    t = t.strip()
    if t.startswith("["):
        end = t.rfind("]") + 1
        return json.loads(t[:end])
    if t.startswith("{"):
        end = t.rfind("}") + 1
        return json.loads(t[:end])
    return json.loads(t)


def _get_llm(tenant_id: str) -> LLMBundle:
    """获取租户的默认 chat 模型"""
    return LLMBundle(tenant_id, LLMType.CHAT, lang="Chinese")


# ============================================================
# 生成函数
# ============================================================

def _save_generation(doc_id: str, generation_type: str, content: dict | list, page_count: int):
    """
    保存生成内容到 document_generation 表，支持 upsert。
    先删除旧记录再插入新记录（避免唯一索引冲突）。
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        now = datetime.now()
        current_ts = int(now.timestamp() * 1000)
        current_date = now.strftime("%Y-%m-%d %H:%M:%S")

        # 先删除旧的同类型记录
        cursor.execute(
            "DELETE FROM document_generation WHERE doc_id = %s AND generation_type = %s",
            (doc_id, generation_type),
        )

        # 插入新记录
        gen_id = generate_uuid()
        content_str = json.dumps(content, ensure_ascii=False)
        cursor.execute(
            """INSERT INTO document_generation
            (id, create_time, create_date, update_time, update_date, doc_id, generation_type, content, page_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (gen_id, current_ts, current_date, current_ts, current_date, doc_id, generation_type, content_str, page_count),
        )
        conn.commit()
        logger.info(f"[Gen-INFO] {generation_type} 生成内容已保存，doc_id={doc_id}")

    except Exception:
        logger.error(f"[Gen-ERROR] 保存 {generation_type} 失败: {traceback.format_exc()}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def generate_mindmap(doc_id: str, full_content: str, tenant_id: str):
    """为文档生成思维导图（JSON 树形结构）"""
    try:
        chat_mdl = _get_llm(tenant_id)

        system_prompt = (
            "你是一个教育内容整理专家，擅长从 PPT 课件中提炼知识结构，生成思维导图。"
            "请严格输出 JSON，不要额外文字。"
        )

        user_prompt = f"""请根据以下 PPT 课件内容，生成一个思维导图。要求：
1. 将内容按章节主题整理成树形结构
2. 每个节点简洁明了，不超过 20 字
3. 输出格式：{{"title": "课件主题", "root": {{"id": "root", "label": "核心主题", "children": [...]}}}}，children 中每个元素为 {{"id": "...", "label": "...", "children": [...]}}

课件内容：
{full_content}"""

        result = chat_mdl.chat(
            system_prompt,
            [{"role": "user", "content": user_prompt}],
            gen_conf={"temperature": 0.3},
        )

        mindmap_data = extract_json(result)
        if mindmap_data:
            _save_generation(doc_id, "mindmap", mindmap_data, 0)
            logger.info(f"[Gen-INFO] 思维导图生成成功，doc_id={doc_id}")
        else:
            logger.error(f"[Gen-ERROR] 思维导图解析失败，doc_id={doc_id}，原始返回: {result[:500]}")

    except Exception:
        logger.error(f"[Gen-ERROR] 思维导图生成异常: {traceback.format_exc()}")


def generate_flashcards(doc_id: str, full_content: str, page_count: int, tenant_id: str):
    """为文档生成概念速记闪卡（Q&A 对），数量由模型根据内容自行决定"""
    try:
        chat_mdl = _get_llm(tenant_id)

        system_prompt = (
            "你是一个教育内容整理专家，擅长从课件中提取关键知识点，制作问答卡片。"
            "请严格输出 JSON 数组，不要额外文字。"
        )

        user_prompt = f"""请根据以下 PPT 课件内容，生成概念速记卡片。要求：
1. 每张卡片包含一个核心概念的问题和答案
2. 问题要能考察对概念的理解，表述清晰
3. 答案要准确、简洁，不超过 100 字
4. 覆盖 PPT 中最重要的知识点，避免重复
5. 自行判断需要多少张卡片，数量适中即可
6. 输出 JSON 数组：[{{"id": 0, "question": "...", "answer": "..."}}, ...]

课件内容：
{full_content}"""

        result = chat_mdl.chat(
            system_prompt,
            [{"role": "user", "content": user_prompt}],
            gen_conf={"temperature": 0.3},
        )

        flashcards_data = extract_json(result)
        if flashcards_data and isinstance(flashcards_data, list):
            _save_generation(doc_id, "flashcards", flashcards_data, page_count)
            logger.info(f"[Gen-INFO] 闪卡生成成功，doc_id={doc_id}，数量={len(flashcards_data)}")
        else:
            logger.error(f"[Gen-ERROR] 闪卡解析失败，doc_id={doc_id}，原始返回: {result[:500]}")

    except Exception:
        logger.error(f"[Gen-ERROR] 闪卡生成异常: {traceback.format_exc()}")


def generate_quiz(doc_id: str, full_content: str, page_count: int, tenant_id: str, mindmap_node_ids: list[str] | None = None):
    """为文档生成随堂测验选择题，数量由模型根据内容自行决定，每道题绑定知识点"""
    try:
        chat_mdl = _get_llm(tenant_id)

        system_prompt = (
            "你是一个教育测评专家，擅长根据课件内容设计高质量的选择题。"
            "请严格输出 JSON 数组，不要额外文字。"
        )

        # 构建知识点 ID 列表说明
        kp_hint = ""
        if mindmap_node_ids:
            kp_hint = f"\n可参考的知识点 ID 列表：{json.dumps(mindmap_node_ids, ensure_ascii=False)}\n每道题需要选择 1-2 个最相关的知识点 ID 填入 knowledge_point_ids 字段。"

        user_prompt = f"""请根据以下 PPT 课件内容，生成选择题。要求：
1. 每道题 4 个选项 (A/B/C/D)，只有 1 个正确答案
2. 考察对核心概念的理解，而非死记硬背
3. 干扰项要有迷惑性
4. 每个选项都要有解释（正确选项说明为什么正确，错误选项说明为什么不对）
5. 覆盖 PPT 中的不同章节，尽量多出题，数量不限{kp_hint}
6. 输出 JSON 数组：[{{"id": 0, "knowledge_point_ids": ["node-1"], "question": "...", "options": {{"A":"...","B":"...","C":"...","D":"..."}}, "correct": "A", "explanations": {{"A":"...","B":"...","C":"...","D":"..."}}}}]

课件内容：
{full_content}"""

        result = chat_mdl.chat(
            system_prompt,
            [{"role": "user", "content": user_prompt}],
            gen_conf={"temperature": 0.3},
        )

        quiz_data = extract_json(result)
        if quiz_data and isinstance(quiz_data, list):
            _save_generation(doc_id, "quiz", quiz_data, page_count)
            logger.info(f"[Gen-INFO] 测验生成成功，doc_id={doc_id}，数量={len(quiz_data)}")
        else:
            logger.error(f"[Gen-ERROR] 测验解析失败，doc_id={doc_id}，原始返回: {result[:500]}")

    except Exception:
        logger.error(f"[Gen-ERROR] 测验生成异常: {traceback.format_exc()}")


def _extract_mindmap_node_ids(mindmap_data: dict) -> list[str]:
    """从思维导图 JSON 中递归提取所有节点 ID"""
    ids = []

    def walk(node: dict):
        if not isinstance(node, dict):
            return
        nid = node.get("id")
        if nid:
            ids.append(str(nid))
        for child in node.get("children", []) or []:
            walk(child)

    if isinstance(mindmap_data, dict):
        root = mindmap_data.get("root")
        if root:
            walk(root)
    return ids


def generate_all_for_document(doc_id: str, full_content: str, page_count: int, tenant_id: str):
    """解析后统一生成三种内容，失败不阻断"""
    logger.info(f"[Gen-INFO] 开始为文档 {doc_id} 生成内容，页数: {page_count}")

    # 内容太长则截断，避免超过 LLM 上下文限制
    # 保留前 50000 字符作为输入
    truncated_content = full_content[:50000] if len(full_content) > 50000 else full_content
    if len(full_content) > 50000:
        logger.info(f"[Gen-INFO] 文档内容过长({len(full_content)}字符)，截取前50000字符")

    generate_mindmap(doc_id, truncated_content, tenant_id)
    generate_flashcards(doc_id, truncated_content, page_count, tenant_id)

    # 读取已生成的思维导图，提取知识点 ID 传给测验生成
    mindmap_node_ids: list[str] = []
    try:
        mindmap_data = get_generation(doc_id, "mindmap")
        if mindmap_data:
            mindmap_node_ids = _extract_mindmap_node_ids(mindmap_data)
            logger.info(f"[Gen-INFO] 提取到 {len(mindmap_node_ids)} 个知识点节点")
    except Exception:
        logger.warning(f"[Gen-WARNING] 提取知识点节点失败，继续生成测验")

    generate_quiz(doc_id, truncated_content, page_count, tenant_id, mindmap_node_ids)

    logger.info(f"[Gen-INFO] 文档 {doc_id} 生成任务全部完成")


# ============================================================
# 读取生成内容
# ============================================================

def get_generation(doc_id: str, generation_type: str) -> dict | list | None:
    """从 DB 读取指定类型的生成内容"""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT content FROM document_generation WHERE doc_id = %s AND generation_type = %s",
            (doc_id, generation_type),
        )
        row = cursor.fetchone()
        if row and row.get("content"):
            return json.loads(row["content"])
        return None

    except Exception:
        logger.error(f"[Gen-ERROR] 读取 {generation_type} 失败: {traceback.format_exc()}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ============================================================
# 学生互动记录
# ============================================================

def save_card_progress(student_id: str, doc_id: str, card_index: int, status: str):
    """
    保存单张卡片的学习状态，支持 upsert。
    如果已存在 (student_id, doc_id, card_index) 则更新 status。
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        now = datetime.now()
        current_ts = int(now.timestamp() * 1000)
        current_date = now.strftime("%Y-%m-%d %H:%M:%S")

        # 检查是否已有记录
        cursor.execute(
            "SELECT id FROM student_card_progress WHERE student_id = %s AND doc_id = %s AND card_index = %s",
            (student_id, doc_id, card_index),
        )
        existing = cursor.fetchone()

        if existing:
            cursor.execute(
                """UPDATE student_card_progress
                SET status = %s, update_time = %s, update_date = %s
                WHERE id = %s""",
                (status, current_ts, current_date, existing["id"]),
            )
        else:
            record_id = generate_uuid()
            cursor.execute(
                """INSERT INTO student_card_progress
                (id, create_time, create_date, update_time, update_date, student_id, doc_id, card_index, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (record_id, current_ts, current_date, current_ts, current_date, student_id, doc_id, card_index, status),
            )

        conn.commit()

    except Exception:
        logger.error(f"[Gen-ERROR] 保存闪卡进度失败: {traceback.format_exc()}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def get_card_progress(student_id: str, doc_id: str) -> dict[int, str]:
    """获取学生对某文档所有卡片的进度，返回 {card_index: status}"""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT card_index, status FROM student_card_progress WHERE student_id = %s AND doc_id = %s",
            (student_id, doc_id),
        )
        rows = cursor.fetchall()
        return {row["card_index"]: row["status"] for row in rows}

    except Exception:
        logger.error(f"[Gen-ERROR] 读取闪卡进度失败: {traceback.format_exc()}")
        return {}
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def save_quiz_result(student_id: str, doc_id: str, question_index: int, student_answer: str, is_correct: bool):
    """保存单道题的作答结果"""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        now = datetime.now()
        current_ts = int(now.timestamp() * 1000)
        current_date = now.strftime("%Y-%m-%d %H:%M:%S")

        record_id = generate_uuid()
        cursor.execute(
            """INSERT INTO student_quiz_result
            (id, create_time, create_date, update_time, update_date, student_id, doc_id, question_index, student_answer, is_correct)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (record_id, current_ts, current_date, current_ts, current_date, student_id, doc_id, question_index, student_answer, int(is_correct)),
        )

        conn.commit()

    except Exception:
        logger.error(f"[Gen-ERROR] 保存测验结果失败: {traceback.format_exc()}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def get_quiz_results(student_id: str, doc_id: str) -> list[dict]:
    """获取学生对某文档的测验结果列表"""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT question_index, student_answer, is_correct FROM student_quiz_result WHERE student_id = %s AND doc_id = %s ORDER BY create_time DESC",
            (student_id, doc_id),
        )
        return cursor.fetchall()

    except Exception:
        logger.error(f"[Gen-ERROR] 读取测验结果失败: {traceback.format_exc()}")
        return []
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
