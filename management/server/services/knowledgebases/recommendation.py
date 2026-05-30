"""
个性化推荐引擎

基于 SM-2 遗忘曲线算法，在助教层面（跨 PPT）追踪知识点掌握度，
为学生生成个性化测验——薄弱点多出、掌握的不出。
"""

import json
import random
import sys
import os
import time
import traceback
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))

from database import get_db_connection
from . import logger

# ============================================================
# SM-2 遗忘曲线算法
# ============================================================

# 初始复习间隔（天）
INITIAL_INTERVAL_DAYS = 1

# 难度因子范围
MIN_EASE_FACTOR = 1.3
MAX_EASE_FACTOR = 3.5
DEFAULT_EASE_FACTOR = 2.5

# 最短复习间隔（天）
MIN_INTERVAL_DAYS = 1
MAX_INTERVAL_DAYS = 120


def calc_next_review(correct: bool, current_ease: float, current_interval: int) -> tuple[float, int]:
    """
    根据作答正确/错误，计算新的 ease_factor 和下次复习间隔（天）。

    答对：
      ease_factor += 0.15 (上限 3.5)
      interval *= ease_factor

    答错：
      ease_factor -= 0.2 (下限 1.3)
      interval = 1（明天就该复习）
    """
    if correct:
        new_ease = min(MAX_EASE_FACTOR, current_ease + 0.15)
        new_interval = max(MIN_INTERVAL_DAYS, min(MAX_INTERVAL_DAYS, int(current_interval * new_ease)))
    else:
        new_ease = max(MIN_EASE_FACTOR, current_ease - 0.2)
        new_interval = MIN_INTERVAL_DAYS

    return new_ease, new_interval


# ============================================================
# 知识点得分计算
# ============================================================

def calc_knowledge_priority(
    correct_count: int,
    wrong_count: int,
    last_review_time: float | None,
    next_review_time: float | None,
    review_count: int,
) -> float:
    """
    计算知识点的复习优先级分数。越高越需要复习。

    规则：
      - 从未复习：+4 分
      - 已过期（next_review_time < now）：+3 分
      - 正确率 < 50%：+2 分
      - 正确率 >= 80% 且过期时间 > 3 天：-100 分（已掌握，跳过）
      - 其余：0 分
    """
    now = time.time()
    score = 0.0

    if review_count == 0 or last_review_time is None:
        # 从未复习
        return 4.0

    total = correct_count + wrong_count
    accuracy = correct_count / total if total > 0 else 0.0

    # 已掌握 — 正确率高且还不到复习时间
    if accuracy >= 0.8 and next_review_time and next_review_time > now + 3 * 86400:
        return -100.0

    # 该复习了
    if next_review_time is None or next_review_time < now:
        score += 3.0

    # 错误率高
    if accuracy < 0.5 and total >= 2:
        score += 2.0

    # 最近正确率有所下降（最近 2 次答错）
    if wrong_count >= 2:
        score += 1.0

    return score


# ============================================================
# 题目池聚合（从助教下所有文档的 quiz 中收集题目）
# ============================================================

def _collect_quiz_pool(kb_ids: list[str]) -> list[dict]:
    """
    收集指定知识库下所有文档的测验题目。
    返回列表，每道题包含题目信息 + 来源文档 ID。
    """
    conn = None
    cursor = None
    all_questions = []

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT dg.doc_id, dg.content, d.name AS doc_name
            FROM document_generation dg
            JOIN document d ON d.id = dg.doc_id
            WHERE d.kb_id IN ({}) AND dg.generation_type = 'quiz'
        """.format(",".join(["%s"] * len(kb_ids)))

        cursor.execute(query, kb_ids)
        rows = cursor.fetchall()

        for row in rows:
            try:
                questions = json.loads(row["content"])
                for q in questions:
                    q["_doc_id"] = row["doc_id"]
                    q["_doc_name"] = row.get("doc_name", "")
                all_questions.extend(questions)
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"[Rec-WARNING] 解析 doc {row['doc_id']} 的测验数据失败")
                continue

    except Exception:
        logger.error(f"[Rec-ERROR] 收集题目池失败: {traceback.format_exc()}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return all_questions


# ============================================================
# 个性化组卷
# ============================================================

def get_personalized_quiz(student_id: str, kb_ids: list[str], count: int = 10) -> list[dict]:
    """
    为学生生成个性化测验题目。

    流程：
      1. 收集所有题目
      2. 查询每个知识点的掌握度
      3. 按优先级排序知识点
      4. 从高优先级知识点中选题
    """
    if not kb_ids or not student_id:
        return []

    try:
        # 1. 收集题目池
        quiz_pool = _collect_quiz_pool(kb_ids)
        if not quiz_pool:
            logger.info(f"[Rec-INFO] 知识库 {kb_ids} 下没有可用的测验题目")
            return []

        logger.info(f"[Rec-INFO] 题目池大小: {len(quiz_pool)}")

        # 2. 查询掌握度
        mastery_map = _get_mastery_map(student_id)
        logger.info(f"[Rec-INFO] 已有掌握度记录: {len(mastery_map)} 条")

        # 3. 为每个题目涉及的知识点计算优先级
        # 按知识点分组题目
        kp_to_questions: dict[str, list[dict]] = {}
        for q in quiz_pool:
            kp_ids = q.get("knowledge_point_ids", [])
            if not kp_ids:
                # 没有知识点标签的题，给一个虚拟的「未分类」知识点
                fake_kp = f"uncategorized_{q.get('_doc_id', 'unknown')}"
                kp_ids = [fake_kp]

            for kp_id in kp_ids:
                if kp_id not in kp_to_questions:
                    kp_to_questions[kp_id] = []
                kp_to_questions[kp_id].append(q)

        # 4. 计算每个知识点的优先级
        kp_scores = []
        for kp_id, questions in kp_to_questions.items():
            mastery = mastery_map.get(kp_id, {})
            score = calc_knowledge_priority(
                correct_count=mastery.get("correct_count", 0),
                wrong_count=mastery.get("wrong_count", 0),
                last_review_time=mastery.get("last_review_time"),
                next_review_time=mastery.get("next_review_time"),
                review_count=mastery.get("review_count", 0),
            )
            if score > -50:  # 过滤已掌握的知识点
                kp_scores.append((kp_id, score, questions))

        # 5. 按分数降序排列，选 Top N 知识点，每个知识点 1-2 题
        kp_scores.sort(key=lambda x: x[1], reverse=True)

        selected_questions = []
        used_question_ids = set()

        for kp_id, score, questions in kp_scores[:count]:
            # 过滤掉已选的题
            available = [q for q in questions if q["id"] not in used_question_ids]
            if not available:
                continue

            # 高优先级知识点选 2 题，低优先级选 1 题
            pick_count = 2 if score >= 3 else 1
            pick_count = min(pick_count, len(available))

            picked = random.sample(available, pick_count)
            for q in picked:
                used_question_ids.add(q["id"])
                selected_questions.append({
                    "id": q["id"],
                    "doc_id": q.get("_doc_id", ""),
                    "doc_name": q.get("_doc_name", ""),
                    "knowledge_point_ids": q.get("knowledge_point_ids", []),
                    "question": q["question"],
                    "options": q["options"],
                    "correct": q.get("correct", ""),
                    "explanations": q.get("explanations", {}),
                })

            if len(selected_questions) >= count:
                break

        # 打乱题目顺序
        random.shuffle(selected_questions)
        logger.info(f"[Rec-INFO] 个性化组卷完成，共 {len(selected_questions)} 题")

        return selected_questions

    except Exception:
        logger.error(f"[Rec-ERROR] 个性化组卷失败: {traceback.format_exc()}")
        return []


# ============================================================
# 掌握度查询
# ============================================================

def _get_mastery_map(student_id: str) -> dict:
    """查询学生所有知识点的掌握度，返回 {node_id: {correct_count, wrong_count, ...}}"""
    conn = None
    cursor = None
    result = {}

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """SELECT node_id, correct_count, wrong_count, last_review_time,
               next_review_time, ease_factor, review_count
               FROM knowledge_point_mastery
               WHERE student_id = %s""",
            (student_id,),
        )
        for row in cursor.fetchall():
            result[row["node_id"]] = {
                "correct_count": row["correct_count"],
                "wrong_count": row["wrong_count"],
                "last_review_time": row["last_review_time"],
                "next_review_time": row["next_review_time"],
                "ease_factor": row.get("ease_factor", DEFAULT_EASE_FACTOR),
                "review_count": row.get("review_count", 0),
            }

    except Exception:
        logger.error(f"[Rec-ERROR] 查询掌握度失败: {traceback.format_exc()}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return result


# ============================================================
# 更新掌握度（答题后调用）
# ============================================================

def update_mastery(student_id: str, doc_id: str, knowledge_point_ids: list[str], is_correct: bool):
    """
    答题后更新知识点的掌握度。每个知识点独立计算遗忘曲线。
    """
    if not knowledge_point_ids:
        return

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        now_ts = time.time()
        now_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for kp_id in knowledge_point_ids:
            # 查询现有记录
            cursor.execute(
                """SELECT id, correct_count, wrong_count, ease_factor, review_count
                   FROM knowledge_point_mastery
                   WHERE student_id = %s AND doc_id = %s AND node_id = %s""",
                (student_id, doc_id, kp_id),
            )
            row = cursor.fetchone()

            if row:
                old_interval = 1
                if row["review_count"] > 0:
                    old_interval = max(1, (now_ts - (now_ts - 86400)) / 86400)  # fallback 1 day

                new_ease, new_interval = calc_next_review(
                    is_correct, row["ease_factor"], old_interval
                )

                next_review = now_ts + new_interval * 86400

                cursor.execute(
                    """UPDATE knowledge_point_mastery
                       SET {} = {} + 1,
                           ease_factor = %s,
                           review_count = review_count + 1,
                           last_review_time = %s,
                           next_review_time = %s,
                           update_time = %s,
                           update_date = %s
                       WHERE id = %s""".format(
                        "correct_count" if is_correct else "wrong_count",
                        "correct_count" if is_correct else "wrong_count",
                    ),
                    (
                        new_ease,
                        int(now_ts),
                        int(next_review),
                        int(now_ts),
                        now_dt,
                        row["id"],
                    ),
                )
            else:
                # 新建记录
                new_ease, new_interval = calc_next_review(is_correct, DEFAULT_EASE_FACTOR, INITIAL_INTERVAL_DAYS)
                next_review = now_ts + new_interval * 86400

                import uuid
                new_id = str(uuid.uuid4()).replace("-", "")

                cursor.execute(
                    """INSERT INTO knowledge_point_mastery
                       (id, student_id, doc_id, node_id,
                        correct_count, wrong_count, ease_factor, review_count,
                        last_review_time, next_review_time,
                        create_time, create_date, update_time, update_date)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        new_id,
                        student_id,
                        doc_id,
                        kp_id,
                        1 if is_correct else 0,
                        0 if is_correct else 1,
                        new_ease,
                        1,
                        int(now_ts),
                        int(next_review),
                        int(now_ts),
                        now_dt,
                        int(now_ts),
                        now_dt,
                    ),
                )

        conn.commit()

    except Exception:
        logger.error(f"[Rec-ERROR] 更新掌握度失败: {traceback.format_exc()}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ============================================================
# 知识报告
# ============================================================

def get_knowledge_report(student_id: str, kb_ids: list[str]) -> dict:
    """生成学生的知识点掌握度报告"""
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 获取所有涉及的知识点掌握度
        if not kb_ids:
            return {"weak_points": [], "strong_points": [], "stats": {}}

        # 通过 doc_id 关联知识库
        placeholders = ",".join(["%s"] * len(kb_ids))
        cursor.execute(
            f"""SELECT kpm.*, d.name AS doc_name
                FROM knowledge_point_mastery kpm
                JOIN document d ON d.id = kpm.doc_id
                WHERE kpm.student_id = %s AND d.kb_id IN ({placeholders})""",
            (student_id, *kb_ids),
        )
        rows = cursor.fetchall()

        weak_points = []
        strong_points = []
        total_correct = 0
        total_wrong = 0

        for row in rows:
            total = row["correct_count"] + row["wrong_count"]
            accuracy = row["correct_count"] / total if total > 0 else 0
            entry = {
                "node_id": row["node_id"],
                "doc_name": row["doc_name"],
                "correct_count": row["correct_count"],
                "wrong_count": row["wrong_count"],
                "accuracy": round(accuracy, 2),
                "review_count": row["review_count"],
                "need_review": row["next_review_time"] and row["next_review_time"] < time.time(),
            }

            if accuracy < 0.5 or entry["need_review"]:
                weak_points.append(entry)
            elif accuracy >= 0.8:
                strong_points.append(entry)

            total_correct += row["correct_count"]
            total_wrong += row["wrong_count"]

        total = total_correct + total_wrong
        overall_accuracy = round(total_correct / total, 2) if total > 0 else 0

        return {
            "weak_points": weak_points,
            "strong_points": strong_points,
            "stats": {
                "total_correct": total_correct,
                "total_wrong": total_wrong,
                "total_attempts": total,
                "overall_accuracy": overall_accuracy,
                "knowledge_points_count": len(rows),
            },
        }

    except Exception:
        logger.error(f"[Rec-ERROR] 获取知识报告失败: {traceback.format_exc()}")
        return {"weak_points": [], "strong_points": [], "stats": {}}
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
