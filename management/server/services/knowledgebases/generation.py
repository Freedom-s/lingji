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
import threading
import traceback
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# 确保可以导入 api 包
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))

from api.db.services.llm_service import LLMBundle
from api.db import LLMType
from database import get_db_connection, get_es_client
from utils import generate_uuid
from . import logger


GENERATION_TYPES = ("mindmap", "flashcards", "quiz")
VIDEO_DOCUMENT_TYPE = "video"
MAX_GENERATION_ITEMS = 500
MAX_MINDMAP_DEPTH = 12
_REGENERATION_LOCK = threading.Lock()
_REGENERATING_DOCS = set()


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
        return True

    except Exception:
        logger.error(f"[Gen-ERROR] 保存 {generation_type} 失败: {traceback.format_exc()}")
        return False
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


def _normalize_mindmap(content: dict) -> tuple[dict, set[str]]:
    """校验并规范化教师编辑后的思维导图，保证节点 ID 唯一且结构可用。"""
    if not isinstance(content, dict) or not isinstance(content.get("root"), dict):
        raise ValueError("思维导图必须包含根节点")

    seen_ids = set()
    node_count = 0

    def normalize_node(node: dict, depth: int) -> dict:
        nonlocal node_count
        if depth > MAX_MINDMAP_DEPTH:
            raise ValueError(f"思维导图最多支持 {MAX_MINDMAP_DEPTH} 层")
        if not isinstance(node, dict):
            raise ValueError("思维导图节点格式错误")

        node_id = str(node.get("id") or "").strip()
        label = str(node.get("label") or "").strip()
        children = node.get("children") or []
        if not node_id or len(node_id) > 64:
            raise ValueError("思维导图节点 ID 不能为空且不能超过 64 个字符")
        if node_id in seen_ids:
            raise ValueError(f"思维导图节点 ID 重复：{node_id}")
        if not label or len(label) > 200:
            raise ValueError("知识点名称不能为空且不能超过 200 个字符")
        if not isinstance(children, list):
            raise ValueError("思维导图子节点必须是数组")

        node_count += 1
        if node_count > MAX_GENERATION_ITEMS:
            raise ValueError(f"思维导图最多支持 {MAX_GENERATION_ITEMS} 个节点")
        seen_ids.add(node_id)
        return {
            "id": node_id,
            "label": label,
            "children": [normalize_node(child, depth + 1) for child in children],
        }

    root = normalize_node(content["root"], 1)
    title = str(content.get("title") or root["label"]).strip()
    if len(title) > 200:
        raise ValueError("思维导图标题不能超过 200 个字符")
    return {"title": title, "root": root}, seen_ids


def _normalize_knowledge_point_ids(value, valid_node_ids: set[str] | None) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("关联知识点必须是数组")
    normalized = list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))
    if valid_node_ids is None:
        return normalized
    invalid = [node_id for node_id in normalized if node_id not in valid_node_ids]
    if invalid:
        raise ValueError(f"关联了不存在的知识点：{invalid[0]}")
    return normalized


def _normalize_flashcards(content, valid_node_ids: set[str] | None) -> list[dict]:
    if not isinstance(content, list):
        raise ValueError("概念速记内容必须是数组")
    if len(content) > MAX_GENERATION_ITEMS:
        raise ValueError(f"概念速记最多支持 {MAX_GENERATION_ITEMS} 张卡片")

    cards = []
    seen_ids = set()
    for index, item in enumerate(content):
        if not isinstance(item, dict):
            raise ValueError(f"第 {index + 1} 张卡片格式错误")
        question = str(item.get("question") or "").strip()
        answer = str(item.get("answer") or "").strip()
        if not question or not answer:
            raise ValueError(f"第 {index + 1} 张卡片的问题和答案不能为空")
        try:
            item_id = int(item.get("id", index))
        except (TypeError, ValueError):
            raise ValueError(f"第 {index + 1} 张卡片的 ID 必须是整数")
        if item_id < 0 or item_id in seen_ids:
            raise ValueError(f"第 {index + 1} 张卡片的 ID 无效或重复")
        seen_ids.add(item_id)
        cards.append({
            "id": item_id,
            "knowledge_point_ids": _normalize_knowledge_point_ids(
                item.get("knowledge_point_ids"), valid_node_ids
            ),
            "question": question,
            "answer": answer,
        })
    return cards


def _normalize_quiz(content, valid_node_ids: set[str] | None) -> list[dict]:
    if not isinstance(content, list):
        raise ValueError("随堂测验内容必须是数组")
    if len(content) > MAX_GENERATION_ITEMS:
        raise ValueError(f"随堂测验最多支持 {MAX_GENERATION_ITEMS} 道题")

    questions = []
    seen_ids = set()
    option_keys = ("A", "B", "C", "D")
    for index, item in enumerate(content):
        if not isinstance(item, dict):
            raise ValueError(f"第 {index + 1} 道题格式错误")
        question = str(item.get("question") or "").strip()
        options = item.get("options") or {}
        explanations = item.get("explanations") or {}
        correct = str(item.get("correct") or "").strip().upper()
        if not question:
            raise ValueError(f"第 {index + 1} 道题的题干不能为空")
        if not isinstance(options, dict) or any(not str(options.get(key) or "").strip() for key in option_keys):
            raise ValueError(f"第 {index + 1} 道题必须填写 A、B、C、D 四个选项")
        if correct not in option_keys:
            raise ValueError(f"第 {index + 1} 道题的正确答案必须是 A、B、C 或 D")
        if not isinstance(explanations, dict):
            raise ValueError(f"第 {index + 1} 道题的选项解析格式错误")
        try:
            item_id = int(item.get("id", index))
        except (TypeError, ValueError):
            raise ValueError(f"第 {index + 1} 道题的 ID 必须是整数")
        if item_id < 0 or item_id in seen_ids:
            raise ValueError(f"第 {index + 1} 道题的 ID 无效或重复")
        seen_ids.add(item_id)

        questions.append({
            "id": item_id,
            "knowledge_point_ids": _normalize_knowledge_point_ids(
                item.get("knowledge_point_ids"), valid_node_ids
            ),
            "question": question,
            "options": {key: str(options.get(key) or "").strip() for key in option_keys},
            "correct": correct,
            "explanations": {key: str(explanations.get(key) or "").strip() for key in option_keys},
        })
    return questions


def _load_generation_content(cursor, doc_id: str, generation_type: str):
    cursor.execute(
        "SELECT id, content, page_count FROM document_generation WHERE doc_id = %s AND generation_type = %s",
        (doc_id, generation_type),
    )
    row = cursor.fetchone()
    if not row:
        return None, None, 0
    try:
        content = json.loads(row["content"]) if isinstance(row["content"], str) else row["content"]
    except (json.JSONDecodeError, TypeError):
        content = None
    return row["id"], content, int(row.get("page_count") or 0)


def _remove_invalid_node_references(cursor, doc_id: str, valid_node_ids: set[str]):
    """思维导图删节点后，同步移除闪卡和测验中的失效引用。"""
    updated_types = []
    for generation_type in ("flashcards", "quiz"):
        record_id, content, _ = _load_generation_content(cursor, doc_id, generation_type)
        if not record_id or not isinstance(content, list):
            continue
        changed = False
        for item in content:
            if not isinstance(item, dict):
                continue
            current = item.get("knowledge_point_ids") or []
            filtered = [node_id for node_id in current if node_id in valid_node_ids]
            if filtered != current:
                item["knowledge_point_ids"] = filtered
                changed = True
        if changed:
            cursor.execute(
                "UPDATE document_generation SET content = %s WHERE id = %s",
                (json.dumps(content, ensure_ascii=False), record_id),
            )
            updated_types.append(generation_type)
    return updated_types


def _changed_existing_item_ids(old_content, new_content) -> list[int]:
    """找出被修改或删除的旧条目 ID；新增条目不会影响既有学习记录。"""
    if not isinstance(old_content, list):
        return []
    old_items = {}
    for index, item in enumerate(old_content):
        if not isinstance(item, dict):
            continue
        try:
            item_id = int(item.get("id", index))
        except (TypeError, ValueError):
            continue
        canonical_item = dict(item)
        canonical_item["id"] = item_id
        old_items[item_id] = canonical_item
    new_items = {item.get("id"): item for item in new_content if isinstance(item, dict)}
    return sorted(
        int(item_id)
        for item_id, old_item in old_items.items()
        if item_id not in new_items or new_items[item_id] != old_item
    )


def replace_generation_content(
    doc_id: str,
    user_id: str,
    generation_type: str,
    content,
    operation: str = "replace",
    item_index: int | None = None,
) -> dict:
    """保存教师编辑后的学习内容，并修正受影响的学生学习记录。"""
    if generation_type not in GENERATION_TYPES:
        raise ValueError("不支持的学习内容类型")
    if operation not in {"add", "edit", "delete", "replace"}:
        raise ValueError("不支持的编辑操作")

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT d.id, d.run, d.type, d.chunk_num
            FROM document d
            JOIN knowledgebase kb ON kb.id = d.kb_id
            WHERE d.id = %s AND kb.tenant_id = %s
            """,
            (doc_id, user_id),
        )
        document = cursor.fetchone()
        if not document:
            raise PermissionError("文档不存在或无权访问")
        if str(document.get("type") or "").lower() == VIDEO_DOCUMENT_TYPE:
            raise ValueError("视频文件没有可编辑的思维导图、概念速记和随堂测验")
        if str(document.get("run")) != "3":
            raise ValueError("文档尚未解析完成，暂时不能编辑学习内容")

        _, mindmap_content, _ = _load_generation_content(cursor, doc_id, "mindmap")
        valid_node_ids = None
        old_node_ids = set()
        old_node_labels = {}
        if isinstance(mindmap_content, dict) and mindmap_content.get("root"):
            old_node_labels = {
                item["id"]: item["label"] for item in _extract_node_info(mindmap_content)
            }
            old_node_ids = set(old_node_labels)
            valid_node_ids = set(old_node_ids)

        if generation_type == "mindmap":
            normalized_content, valid_node_ids = _normalize_mindmap(content)
        elif generation_type == "flashcards":
            normalized_content = _normalize_flashcards(content, valid_node_ids)
        else:
            normalized_content = _normalize_quiz(content, valid_node_ids)

        record_id, old_content, page_count = _load_generation_content(cursor, doc_id, generation_type)
        now = datetime.now()
        current_ts = int(now.timestamp() * 1000)
        current_date = now.strftime("%Y-%m-%d %H:%M:%S")
        content_json = json.dumps(normalized_content, ensure_ascii=False)
        if record_id:
            cursor.execute(
                """UPDATE document_generation
                SET content = %s, update_time = %s, update_date = %s
                WHERE id = %s""",
                (content_json, current_ts, current_date, record_id),
            )
        else:
            record_id = generate_uuid()
            cursor.execute(
                """INSERT INTO document_generation
                (id, create_time, create_date, update_time, update_date, doc_id, generation_type, content, page_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    record_id, current_ts, current_date, current_ts, current_date,
                    doc_id, generation_type, content_json,
                    page_count or int(document.get("chunk_num") or 0),
                ),
            )

        reset_records = 0
        unbound_videos = 0
        removed_node_ids = []
        references_updated = []
        if generation_type == "mindmap":
            removed_node_ids = sorted(old_node_ids - valid_node_ids)
            new_node_labels = {
                item["id"]: item["label"] for item in _extract_node_info(normalized_content)
            }
            changed_node_ids = sorted(
                node_id for node_id in old_node_ids & valid_node_ids
                if old_node_labels[node_id] != new_node_labels[node_id]
            )
            references_updated = _remove_invalid_node_references(cursor, doc_id, valid_node_ids)
            reset_node_ids = sorted(set(removed_node_ids + changed_node_ids))
            if removed_node_ids:
                placeholders = ", ".join(["%s"] * len(removed_node_ids))
                cursor.execute(
                    f"""
                    DELETE FROM knowledge_point_video_binding
                    WHERE courseware_doc_id = %s
                      AND knowledge_point_id IN ({placeholders})
                    """,
                    (doc_id, *removed_node_ids),
                )
                unbound_videos = cursor.rowcount
            if reset_node_ids:
                placeholders = ", ".join(["%s"] * len(reset_node_ids))
                cursor.execute(
                    f"DELETE FROM knowledge_point_mastery WHERE doc_id = %s AND node_id IN ({placeholders})",
                    (doc_id, *reset_node_ids),
                )
                reset_records += cursor.rowcount
        elif generation_type == "flashcards":
            affected_ids = _changed_existing_item_ids(old_content, normalized_content)
            if affected_ids:
                placeholders = ", ".join(["%s"] * len(affected_ids))
                cursor.execute(
                    f"DELETE FROM student_card_progress WHERE doc_id = %s AND card_index IN ({placeholders})",
                    (doc_id, *affected_ids),
                )
                reset_records += cursor.rowcount
        elif generation_type == "quiz":
            affected_ids = _changed_existing_item_ids(old_content, normalized_content)
            if affected_ids:
                placeholders = ", ".join(["%s"] * len(affected_ids))
                cursor.execute(
                    f"DELETE FROM student_quiz_result WHERE doc_id = %s AND question_index IN ({placeholders})",
                    (doc_id, *affected_ids),
                )
                reset_records += cursor.rowcount
                # 掌握度是累积值，无法只减去某次历史答题，题目变化后按文档重新计算。
                cursor.execute("DELETE FROM knowledge_point_mastery WHERE doc_id = %s", (doc_id,))
                reset_records += cursor.rowcount

        conn.commit()
        return {
            "generation_type": generation_type,
            "content": normalized_content,
            "reset_records": reset_records,
            "unbound_videos": unbound_videos,
            "removed_node_ids": removed_node_ids,
            "references_updated": references_updated,
        }
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


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
            if _save_generation(doc_id, "mindmap", mindmap_data, 0):
                logger.info(f"[Gen-INFO] 思维导图生成成功，doc_id={doc_id}")
                return mindmap_data
            return None
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
                saved = _save_generation(doc_id, "flashcards", valid_cards, page_count)
                if saved:
                    logger.info(f"[Gen-INFO] 闪卡生成成功，doc_id={doc_id}，共{len(flashcards_data)}项中有效{len(valid_cards)}项")
                return saved
            else:
                logger.error(f"[Gen-ERROR] 闪卡全部无效，doc_id={doc_id}，原始返回: {result[:500]}")
        else:
            logger.error(f"[Gen-ERROR] 闪卡解析失败，doc_id={doc_id}，原始返回: {result[:500]}")

    except Exception:
        logger.error(f"[Gen-ERROR] 闪卡生成异常: {traceback.format_exc()}")
    return False


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
                saved = _save_generation(doc_id, "quiz", valid_questions, page_count)
                if saved:
                    logger.info(f"[Gen-INFO] 测验生成成功，doc_id={doc_id}，共{len(quiz_data)}项中有效{len(valid_questions)}项")
                return saved
            else:
                logger.error(f"[Gen-ERROR] 测验全部无效，doc_id={doc_id}，原始返回: {result[:500]}")
        else:
            logger.error(f"[Gen-ERROR] 测验解析失败，doc_id={doc_id}，原始返回: {result[:500]}")

    except Exception:
        logger.error(f"[Gen-ERROR] 测验生成异常: {traceback.format_exc()}")
    return False


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
    results = {"mindmap": mindmap_data is not None}

    # Phase 2: 并行生成闪卡和测验（测验带上思维导图节点信息）
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            "flashcards": executor.submit(generate_flashcards, doc_id, truncated_content, page_count, tenant_id, mindmap_data),
            "quiz": executor.submit(generate_quiz, doc_id, truncated_content, page_count, tenant_id, mindmap_data),
        }
        for generation_type, future in futures.items():
            results[generation_type] = bool(future.result())

    logger.info(f"[Gen-INFO] 文档 {doc_id} 生成任务全部完成")
    return results


def _build_generation_status(run: str, generated_types, document_type: str | None = None) -> dict:
    """根据解析状态和已生成类型构建前端可直接展示的状态。"""
    if str(document_type or "").lower() == VIDEO_DOCUMENT_TYPE:
        return {
            "status": "not_applicable",
            "generated_types": [],
            "missing_types": [],
        }

    generated = [item for item in GENERATION_TYPES if item in set(generated_types or [])]
    missing = [item for item in GENERATION_TYPES if item not in generated]

    if str(run) != "3":
        status = "not_ready"
    elif not missing:
        status = "complete"
    elif not generated:
        status = "missing"
    else:
        status = "partial"

    return {
        "status": status,
        "generated_types": generated,
        "missing_types": missing,
    }


def get_generation_statuses(doc_ids: list[str], user_id: str) -> dict[str, dict]:
    """批量获取当前教师名下文档的衍生内容完整性。"""
    normalized_ids = list(dict.fromkeys(str(doc_id).strip() for doc_id in doc_ids if str(doc_id).strip()))
    if not normalized_ids:
        return {}
    if len(normalized_ids) > 100:
        raise ValueError("一次最多检查 100 个文档")

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        placeholders = ", ".join(["%s"] * len(normalized_ids))
        cursor.execute(
            f"""
            SELECT d.id, d.run, d.type, dg.generation_type
            FROM document d
            JOIN knowledgebase kb ON kb.id = d.kb_id
            LEFT JOIN document_generation dg
                ON dg.doc_id = d.id
                AND dg.generation_type IN ('mindmap', 'flashcards', 'quiz')
                AND dg.content IS NOT NULL
                AND dg.content != ''
            WHERE d.id IN ({placeholders}) AND kb.tenant_id = %s
            """,
            (*normalized_ids, user_id),
        )

        documents = {}
        for row in cursor.fetchall():
            doc_id = str(row["id"])
            document = documents.setdefault(
                doc_id,
                {"run": row.get("run"), "type": row.get("type"), "generated": set()},
            )
            if row.get("generation_type") in GENERATION_TYPES:
                document["generated"].add(row["generation_type"])

        return {
            doc_id: _build_generation_status(
                document["run"], document["generated"], document["type"]
            )
            for doc_id, document in documents.items()
        }
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def _load_parsed_content(doc_id: str, tenant_id: str, page_count: int) -> str:
    """从 Elasticsearch 中按页码恢复已解析的文档文本，避免重新做 OCR 和向量化。"""
    es_client = get_es_client()
    index_name = f"ragflow_{tenant_id}"
    if not es_client.indices.exists(index=index_name):
        raise ValueError("未找到文档的解析索引，请先重新解析文档")

    result = es_client.search(
        index=index_name,
        body={
            "_source": ["content_with_weight", "page_num_int"],
            "query": {"term": {"doc_id": doc_id}},
            "sort": [{"page_num_int": {"order": "asc", "unmapped_type": "long"}}],
            "size": min(max(int(page_count or 1), 100), 10000),
        },
    )
    page_contents = [
        hit.get("_source", {}).get("content_with_weight", "")
        for hit in result.get("hits", {}).get("hits", [])
    ]
    full_content = "\n\n".join(content for content in page_contents if content).strip()
    if len(full_content) <= 100:
        raise ValueError("已解析文本过少，无法生成学习内容，请先重新解析文档")
    return full_content


def _regenerate_missing_for_document(doc_id: str, user_id: str) -> dict:
    """仅重新生成缺失的思维导图、概念速记或随堂测验。"""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT d.id, d.run, d.type, d.chunk_num, kb.created_by AS tenant_id
            FROM document d
            JOIN knowledgebase kb ON kb.id = d.kb_id
            WHERE d.id = %s AND kb.tenant_id = %s
            """,
            (doc_id, user_id),
        )
        document = cursor.fetchone()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    if not document:
        raise PermissionError("文档不存在或无权访问")
    if str(document.get("type") or "").lower() == VIDEO_DOCUMENT_TYPE:
        raise ValueError("视频文件不生成思维导图、概念速记和随堂测验")
    if str(document.get("run")) != "3":
        raise ValueError("文档尚未解析完成，暂时不能生成学习内容")

    current_status = get_generation_statuses([doc_id], user_id)[str(doc_id)]
    missing_types = current_status["missing_types"]
    if not missing_types:
        return {**current_status, "regenerated_types": []}

    page_count = int(document.get("chunk_num") or 0)
    tenant_id = document["tenant_id"]
    full_content = _load_parsed_content(doc_id, tenant_id, page_count)

    estimated_tokens = _estimate_tokens(full_content)
    if estimated_tokens > 40000:
        full_content = full_content[:int(len(full_content) * 40000 / estimated_tokens)]

    regenerated = []
    mindmap_data = get_generation(doc_id, "mindmap")
    if "mindmap" in missing_types:
        mindmap_data = generate_mindmap(doc_id, full_content, tenant_id)
        if mindmap_data is not None:
            regenerated.append("mindmap")

    futures = {}
    with ThreadPoolExecutor(max_workers=2) as executor:
        if "flashcards" in missing_types:
            futures["flashcards"] = executor.submit(
                generate_flashcards, doc_id, full_content, page_count, tenant_id, mindmap_data
            )
        if "quiz" in missing_types:
            futures["quiz"] = executor.submit(
                generate_quiz, doc_id, full_content, page_count, tenant_id, mindmap_data
            )
        for generation_type, future in futures.items():
            if future.result():
                regenerated.append(generation_type)

    final_status = get_generation_statuses([doc_id], user_id)[str(doc_id)]
    logger.info(
        f"[Gen-INFO] 文档 {doc_id} 补生成完成，"
        f"成功={regenerated}，仍缺失={final_status['missing_types']}"
    )
    return {**final_status, "regenerated_types": regenerated}


def regenerate_missing_for_document(doc_id: str, user_id: str) -> dict:
    """防止同一进程内对同一文档重复提交生成任务。"""
    with _REGENERATION_LOCK:
        if doc_id in _REGENERATING_DOCS:
            raise ValueError("该文档正在重新生成学习内容，请稍后")
        _REGENERATING_DOCS.add(doc_id)

    try:
        return _regenerate_missing_for_document(doc_id, user_id)
    finally:
        with _REGENERATION_LOCK:
            _REGENERATING_DOCS.discard(doc_id)


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
