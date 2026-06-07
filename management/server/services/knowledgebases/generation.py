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
import unicodedata
from concurrent.futures import ThreadPoolExecutor
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

def _try_extract_partial_json_array(text: str) -> list | None:
    """当完整数组解析失败时，逐对象尝试提取数组中可独立解析的 JSON 对象"""
    valid_objects = []
    depth = 0
    start = -1
    in_string = False
    escape = False

    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                obj_str = text[start : i + 1]
                try:
                    obj = json.loads(obj_str)
                    valid_objects.append(obj)
                except json.JSONDecodeError:
                    pass
                start = -1

    return valid_objects if valid_objects else None


def _estimate_tokens(text: str) -> int:
    """估算文本的 token 数量（中英文混合场景）"""
    cjk_count = 0
    other_chars = 0

    for ch in text:
        # CJK 统一表意文字区块
        if '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f' or '\uff00' <= ch <= '\uffef':
            cjk_count += 1
        elif not ch.isspace():
            other_chars += 1

    # CJK: ~1 token/字（国产模型/中文优化模型通常接近 1:1）
    # 英文/数字: 1 token/4字符
    return int(cjk_count + other_chars / 4)


def extract_json(text: str):
    """从 LLM 返回文本中提取 JSON，支持 markdown 代码块包裹和大数组逐项兜底"""
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
        array_str = t[:end]
        try:
            return json.loads(array_str)
        except json.JSONDecodeError:
            # 整段解析失败 → 逐对象兜底提取
            partial = _try_extract_partial_json_array(array_str)
            if partial:
                logger.warning(f"[Gen-WARN] JSON 数组存在格式问题，已从中提取 {len(partial)} 个有效项")
                return partial
            return None
    if t.startswith("{"):
        end = t.rfind("}") + 1
        try:
            return json.loads(t[:end])
        except json.JSONDecodeError:
            return None
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        return None


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


def _extract_node_info(mindmap_data: dict) -> list[dict]:
    """从思维导图 JSON 中递归提取所有节点的 id 和 label 列表"""
    nodes = []

    def walk(node: dict):
        if not isinstance(node, dict):
            return
        nid = node.get("id")
        label = node.get("label")
        if nid and label:
            nodes.append({"id": nid, "label": label})
        for child in node.get("children", []) or []:
            walk(child)

    root = mindmap_data.get("root")
    if root:
        walk(root)
    return nodes


def generate_mindmap(doc_id: str, full_content: str, tenant_id: str) -> dict | None:
    """为文档生成思维导图（JSON 树形结构），返回解析后的 dict 或 None"""
    try:
        chat_mdl = _get_llm(tenant_id)

        system_prompt = (
            "你是一个教育内容整理专家，擅长从 PPT 课件中提炼知识结构，生成思维导图。"
            "请严格输出 JSON，不要额外文字。"
        )

        user_prompt = f"""请根据以下 PPT 课件内容，生成一个思维导图。要求：
1. 将内容按章节主题整理成树形结构
2. 每个节点简洁明了，不超过 20 字
3. id 命名规则：根节点固定为 "root"，各级子节点按层级编号命名，如 ch1、ch2（一级节点），ch1_1、ch1_2（二级节点），ch1_1_1（三级节点），以此类推
4. 输出格式：{{"title": "课件主题", "root": {{"id": "root", "label": "核心主题", "children": [{{"id": "ch1", "label": "...", "children": [{{"id": "ch1_1", "label": "...", "children": []}}]}}]}}}}

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
            return mindmap_data
        else:
            logger.error(f"[Gen-ERROR] 思维导图解析失败，doc_id={doc_id}，原始返回: {result[:500]}")
            return None

    except Exception:
        logger.error(f"[Gen-ERROR] 思维导图生成异常: {traceback.format_exc()}")
        return None


def generate_flashcards(doc_id: str, full_content: str, page_count: int, tenant_id: str, mindmap_data: dict | None = None):
    """为文档生成概念速记闪卡（Q&A 对），每张卡片通过 knowledge_point_ids 关联思维导图知识点"""
    try:
        chat_mdl = _get_llm(tenant_id)

        system_prompt = (
            "你是一个教育内容整理专家，擅长从课件中提取关键知识点，制作问答卡片。"
            "根据内容自主决定生成多少张卡片，数量要合理覆盖核心知识点，不设上限和下限。"
            "每张卡片必须关联到对应的知识点节点。"
            "请严格输出 JSON 数组，不要额外文字。"
        )

        # 构建知识点节点列表（供 prompt 使用）
        node_info_hint = ""
        if mindmap_data:
            nodes = _extract_node_info(mindmap_data)
            if nodes:
                node_info_hint = (
                    "\n\n知识点节点列表（每张卡片的 knowledge_point_ids 必须从以下 id 中选择，可以关联多个）：\n"
                    + "\n".join(f'  - id="{n["id"]}", 标签="{n["label"]}"' for n in nodes)
                    + "\n"
                )

        user_prompt = f"""请根据以下 PPT 课件内容，自主决定生成多少张概念速记卡片。要求：
1. 每张卡片包含一个核心概念的问题和答案
2. 问题要能考察对概念的理解，表述清晰
3. 答案要准确、简洁，不超过 100 字
4. 覆盖 PPT 中最重要的知识点，避免重复
5. knowledge_point_ids 字段必须包含该卡片关联的知识点 id，从上述列表中选取（可关联多个）
6. 输出 JSON 数组：[{{"id": 0, "knowledge_point_ids": ["ch1", "ch1_1"], "question": "...", "answer": "..."}}, ...]
{node_info_hint}
课件内容：
{full_content}"""

        result = chat_mdl.chat(
            system_prompt,
            [{"role": "user", "content": user_prompt}],
            gen_conf={"temperature": 0.3},
        )

        flashcards_data = extract_json(result)
        if flashcards_data and isinstance(flashcards_data, list):
            # 过滤无效项：必须包含 question 和 answer
            valid_cards = []
            for card in flashcards_data:
                if isinstance(card, dict) and card.get("question") and card.get("answer"):
                    valid_cards.append(card)
            if valid_cards:
                _save_generation(doc_id, "flashcards", valid_cards, page_count)
                logger.info(f"[Gen-INFO] 闪卡生成成功，doc_id={doc_id}，共{len(flashcards_data)}项中有效{len(valid_cards)}项")
            else:
                logger.error(f"[Gen-ERROR] 闪卡全部无效，doc_id={doc_id}，原始返回: {result[:500]}")
        else:
            logger.error(f"[Gen-ERROR] 闪卡解析失败，doc_id={doc_id}，原始返回: {result[:500]}")

    except Exception:
        logger.error(f"[Gen-ERROR] 闪卡生成异常: {traceback.format_exc()}")


def generate_quiz(doc_id: str, full_content: str, page_count: int, tenant_id: str, mindmap_data: dict | None = None):
    """为文档生成随堂测验选择题，每道题通过 knowledge_point_ids 关联思维导图知识点"""
    try:
        chat_mdl = _get_llm(tenant_id)

        system_prompt = (
            "你是一个教育测评专家，擅长根据课件内容设计高质量的选择题。"
            "根据内容自主决定生成多少道题，数量要合理覆盖核心知识点，不设上限和下限。"
            "每道题必须关联到对应的知识点节点。"
            "请严格输出 JSON 数组，不要额外文字。"
        )

        # 构建知识点节点列表（供 prompt 使用）
        node_info_hint = ""
        if mindmap_data:
            nodes = _extract_node_info(mindmap_data)
            if nodes:
                node_info_hint = (
                    "\n\n知识点节点列表（每道题的 knowledge_point_ids 必须从以下 id 中选择，可以关联多个）：\n"
                    + "\n".join(f'  - id="{n["id"]}", 标签="{n["label"]}"' for n in nodes)
                    + "\n"
                )

        user_prompt = f"""请根据以下 PPT 课件内容，自主决定生成多少道选择题。要求：
1. 每道题 4 个选项 (A/B/C/D)，只有 1 个正确答案
2. 考察对核心概念的理解，而非死记硬背
3. 干扰项要有迷惑性
4. 每个选项都要有解释（正确选项说明为什么正确，错误选项说明为什么不对）
5. 覆盖 PPT 中的不同章节
6. knowledge_point_ids 字段必须包含该题考察的知识点 id，从上述列表中选取（可关联多个）
7. 输出 JSON 数组：[{{"id": 0, "knowledge_point_ids": ["ch1", "ch1_1"], "question": "...", "options": {{"A":"...","B":"...","C":"...","D":"..."}}, "correct": "A", "explanations": {{"A":"...","B":"...","C":"...","D":"..."}}}}]
{node_info_hint}
课件内容：
{full_content}"""

        result = chat_mdl.chat(
            system_prompt,
            [{"role": "user", "content": user_prompt}],
            gen_conf={"temperature": 0.3},
        )

        quiz_data = extract_json(result)
        if quiz_data and isinstance(quiz_data, list):
            # 过滤无效项：必须包含 question、options、correct、explanations
            valid_questions = []
            for q in quiz_data:
                if isinstance(q, dict) and q.get("question") and q.get("options") and q.get("correct") and q.get("explanations"):
                    valid_questions.append(q)
            if valid_questions:
                _save_generation(doc_id, "quiz", valid_questions, page_count)
                logger.info(f"[Gen-INFO] 测验生成成功，doc_id={doc_id}，共{len(quiz_data)}项中有效{len(valid_questions)}项")
            else:
                logger.error(f"[Gen-ERROR] 测验全部无效，doc_id={doc_id}，原始返回: {result[:500]}")
        else:
            logger.error(f"[Gen-ERROR] 测验解析失败，doc_id={doc_id}，原始返回: {result[:500]}")

    except Exception:
        logger.error(f"[Gen-ERROR] 测验生成异常: {traceback.format_exc()}")


def generate_all_for_document(doc_id: str, full_content: str, page_count: int, tenant_id: str):
    """解析后统一生成三种内容，失败不阻断"""
    logger.info(f"[Gen-INFO] 开始为文档 {doc_id} 生成内容，页数: {page_count}")

    # 估算 token 数并截断，避免超过 LLM 上下文限制
    # 目标：保留约 12000 tokens（剩余空间留给 prompt 本身）
    MAX_TOKENS = 40000
    estimated_tokens = _estimate_tokens(full_content)
    if estimated_tokens > MAX_TOKENS:
        ratio = MAX_TOKENS / estimated_tokens
        cut_pos = int(len(full_content) * ratio)
        truncated_content = full_content[:cut_pos]
        logger.info(f"[Gen-INFO] 文档内容过长(估算 {estimated_tokens} tokens)，截取前{len(truncated_content)}字符（约 {MAX_TOKENS} tokens）")
    else:
        truncated_content = full_content
        logger.info(f"[Gen-INFO] 文档内容估算 {estimated_tokens} tokens，未超过限制")

    # Phase 1: 先生成思维导图（quiz 需要用其节点 ID 做 knowledge_point_ids）
    mindmap_data = generate_mindmap(doc_id, truncated_content, tenant_id)

    # Phase 2: 并行生成闪卡和测验（测验带上思维导图节点信息）
    with ThreadPoolExecutor(max_workers=2) as executor:
        executor.submit(generate_flashcards, doc_id, truncated_content, page_count, tenant_id, mindmap_data)
        executor.submit(generate_quiz, doc_id, truncated_content, page_count, tenant_id, mindmap_data)

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
