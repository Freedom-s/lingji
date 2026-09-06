"""
学习页面 API - 思维导图、概念速记闪卡、随堂测验
"""

import json
import logging
import random
import time
from flask import request
from flask_login import login_required, current_user

from api.db.db_models import (
    Conversation,
    Dialog,
    Document,
    DocumentGeneration,
    KnowledgePointMastery,
    KnowledgePointVideoBinding,
    StudentCardProgress,
    StudentNote,
    StudentQuizResult,
    StudentVideoProgress,
)
from api.db.db_models import DB
from api.db.services.document_service import DocumentService
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.utils import get_uuid
from api.utils.api_utils import get_json_result
from api import settings

page_name = "learning"
logger = logging.getLogger(__name__)


@manager.route("/mindmap/<doc_id>", methods=["GET"])
@login_required
def get_mindmap(doc_id):
    """获取文档的思维导图"""
    try:
        row = (
            DocumentGeneration.select()
            .where(
                DocumentGeneration.doc_id == doc_id,
                DocumentGeneration.generation_type == "mindmap",
            )
            .first()
        )
        if row and row.content:
            return get_json_result(data=json.loads(row.content))
        return get_json_result(data=None, message="思维导图尚未生成")
    except Exception as e:
        logger.error(f"get mindmap error: {e}")
        return get_json_result(data=None, message=str(e), code=settings.RetCode.EXCEPTION_ERROR)


@manager.route("/mindmap/<courseware_doc_id>/videos", methods=["GET"])
@login_required
def get_mindmap_videos(courseware_doc_id):
    """返回当前学生可访问的课件中，各思维导图节点挂载的视频。"""
    try:
        if not DocumentService.accessible(courseware_doc_id, current_user.id):
            return get_json_result(
                data={"videos_by_node": {}},
                message="无权访问该课件",
                code=settings.RetCode.AUTHENTICATION_ERROR,
            )

        courseware = Document.select(Document.id, Document.type).where(
            Document.id == courseware_doc_id
        ).first()
        if not courseware or str(courseware.type or "").lower() == "video":
            return get_json_result(
                data={"videos_by_node": {}},
                message="目标课件不存在",
                code=settings.RetCode.NOT_FOUND,
            )

        rows = list(
            KnowledgePointVideoBinding.select(
                KnowledgePointVideoBinding.video_doc_id,
                KnowledgePointVideoBinding.knowledge_point_id,
                KnowledgePointVideoBinding.sort_order,
                Document.name.alias("video_name"),
                Document.type.alias("video_type"),
            )
            .join(Document, on=(KnowledgePointVideoBinding.video_doc_id == Document.id))
            .where(
                (KnowledgePointVideoBinding.courseware_doc_id == courseware_doc_id)
                & (Document.status == "1")
                & (Document.type == "video")
            )
            .order_by(
                KnowledgePointVideoBinding.knowledge_point_id.asc(),
                KnowledgePointVideoBinding.sort_order.asc(),
                Document.create_time.asc(),
            )
            .dicts()
        )
        video_ids = [row["video_doc_id"] for row in rows]
        progress_by_video = {}
        if video_ids:
            progress_by_video = {
                progress.doc_id: progress
                for progress in StudentVideoProgress.select().where(
                    (StudentVideoProgress.student_id == current_user.id)
                    & (StudentVideoProgress.doc_id.in_(video_ids))
                )
            }

        videos_by_node = {}
        for row in rows:
            progress = progress_by_video.get(row["video_doc_id"])
            total_duration = int(progress.total_duration or 0) if progress else 0
            watched_seconds = int(progress.watched_seconds or 0) if progress else 0
            progress_percent = min(
                100,
                round(watched_seconds / total_duration * 100) if total_duration > 0 else 0,
            )
            videos_by_node.setdefault(row["knowledge_point_id"], []).append({
                "id": row["video_doc_id"],
                "name": row["video_name"],
                "type": row["video_type"],
                "sort_order": int(row.get("sort_order") or 0),
                "watched_seconds": watched_seconds,
                "total_duration": total_duration,
                "progress_percent": progress_percent,
                "is_completed": bool(progress.is_completed) if progress else False,
            })

        return get_json_result(data={"videos_by_node": videos_by_node})
    except Exception as e:
        logger.error(f"get mindmap videos error: {e}")
        return get_json_result(
            data={"videos_by_node": {}},
            message=str(e),
            code=settings.RetCode.EXCEPTION_ERROR,
        )


@manager.route("/video-bindings", methods=["GET"])
@login_required
def get_linked_video_ids():
    """返回指定知识库中已挂载的视频，用于学生资料列表归类。"""
    try:
        kb_ids = list(dict.fromkeys(
            item.strip()
            for item in str(request.args.get("kb_ids") or "").split(",")
            if item.strip()
        ))
        if len(kb_ids) > 100:
            return get_json_result(
                data={"bindings": {}},
                message="一次最多查询 100 个知识库",
                code=settings.RetCode.ARGUMENT_ERROR,
            )

        accessible_kb_ids = [
            kb_id for kb_id in kb_ids
            if KnowledgebaseService.accessible(kb_id, current_user.id)
        ]
        if not accessible_kb_ids:
            return get_json_result(data={"bindings": {}})

        courseware_ids = Document.select(Document.id).where(
            Document.kb_id.in_(accessible_kb_ids)
        )
        rows = (
            KnowledgePointVideoBinding.select(
                KnowledgePointVideoBinding.video_doc_id,
                KnowledgePointVideoBinding.courseware_doc_id,
                KnowledgePointVideoBinding.knowledge_point_id,
            )
            .where(KnowledgePointVideoBinding.courseware_doc_id.in_(courseware_ids))
            .dicts()
        )
        bindings = {
            row["video_doc_id"]: {
                "courseware_doc_id": row["courseware_doc_id"],
                "knowledge_point_id": row["knowledge_point_id"],
            }
            for row in rows
        }
        return get_json_result(data={"bindings": bindings})
    except Exception as e:
        logger.error(f"get linked video ids error: {e}")
        return get_json_result(
            data={"bindings": {}},
            message=str(e),
            code=settings.RetCode.EXCEPTION_ERROR,
        )


@manager.route("/flashcards/<doc_id>", methods=["GET"])
@login_required
def get_flashcards(doc_id):
    """获取文档的概念速记闪卡，附带当前学生的学习进度和知识点标签映射"""
    try:
        row = (
            DocumentGeneration.select()
            .where(
                DocumentGeneration.doc_id == doc_id,
                DocumentGeneration.generation_type == "flashcards",
            )
            .first()
        )
        cards = json.loads(row.content) if row and row.content else []

        # 获取当前学生的进度
        progress = {}
        if current_user and hasattr(current_user, "id"):
            progress_rows = (
                StudentCardProgress.select()
                .where(
                    StudentCardProgress.student_id == current_user.id,
                    StudentCardProgress.doc_id == doc_id,
                )
            )
            progress = {p.card_index: p.status for p in progress_rows}

        # 获取知识点标签映射（从思维导图中提取）
        kp_labels = _build_kp_label_map([doc_id]).get(doc_id, {})

        return get_json_result(data={"cards": cards, "progress": progress, "kp_labels": kp_labels})
    except Exception as e:
        logger.error(f"get flashcards error: {e}")
        return get_json_result(data={"cards": [], "progress": {}}, message=str(e), code=settings.RetCode.EXCEPTION_ERROR)


@manager.route("/flashcards/<doc_id>/progress", methods=["POST"])
@login_required
def update_flashcard_progress(doc_id):
    """更新学生对某张卡片的记忆状态"""
    try:
        if not current_user or not hasattr(current_user, "id"):
            return get_json_result(data=False, message="用户未登录", code=settings.RetCode.AUTHENTICATION_ERROR)

        data = request.json
        card_index = data.get("card_index")
        status = data.get("status")

        if card_index is None or not status:
            return get_json_result(data=False, message="card_index、status 为必填项", code=settings.RetCode.ARGUMENT_ERROR)
        if status not in ("remembered", "unclear"):
            return get_json_result(data=False, message="status 必须为 remembered 或 unclear", code=settings.RetCode.ARGUMENT_ERROR)

        # Upsert: 先查再更新/插入
        existing = (
            StudentCardProgress.select()
            .where(
                StudentCardProgress.student_id == current_user.id,
                StudentCardProgress.doc_id == doc_id,
                StudentCardProgress.card_index == card_index,
            )
            .first()
        )

        if existing:
            existing.status = status
            existing.save()
        else:
            StudentCardProgress.create(
                id=get_uuid(),
                student_id=current_user.id,
                doc_id=doc_id,
                card_index=card_index,
                status=status,
            )

        return get_json_result(data=True, message="更新成功")
    except Exception as e:
        logger.error(f"update flashcard progress error: {e}")
        return get_json_result(data=False, message=str(e), code=settings.RetCode.EXCEPTION_ERROR)


@manager.route("/quiz/<doc_id>", methods=["GET"])
@login_required
def get_quiz(doc_id):
    """获取文档的随堂测验题目（不含答案），由后端判题"""
    try:
        row = (
            DocumentGeneration.select()
            .where(
                DocumentGeneration.doc_id == doc_id,
                DocumentGeneration.generation_type == "quiz",
            )
            .first()
        )
        questions = json.loads(row.content) if row and row.content else []

        # 不返回 correct 和 explanations，防止学生从网络请求中看到答案
        sanitized = []
        for q in questions:
            sanitized.append({
                "id": q.get("id"),
                "question": q.get("question", ""),
                "options": q.get("options", {}),
                "knowledge_point_ids": q.get("knowledge_point_ids", []),
            })

        # 获取知识点标签映射（从思维导图中提取）
        kp_labels = _build_kp_label_map([doc_id]).get(doc_id, {})

        return get_json_result(data={"questions": sanitized, "kp_labels": kp_labels})
    except Exception as e:
        logger.error(f"get quiz error: {e}")
        return get_json_result(data={"questions": []}, message=str(e), code=settings.RetCode.EXCEPTION_ERROR)


@manager.route("/quiz/<doc_id>/result", methods=["POST"])
@login_required
def submit_quiz_result(doc_id):
    """提交单道题的作答结果，后端判题并返回是否正确及解析"""
    try:
        if not current_user or not hasattr(current_user, "id"):
            return get_json_result(data=False, message="用户未登录", code=settings.RetCode.AUTHENTICATION_ERROR)

        data = request.json
        question_index = data.get("question_index")
        student_answer = data.get("student_answer")

        if question_index is None:
            return get_json_result(data=False, message="question_index 为必填项", code=settings.RetCode.ARGUMENT_ERROR)

        # 从数据库查出正确 answer，后端判题
        row = (
            DocumentGeneration.select()
            .where(
                DocumentGeneration.doc_id == doc_id,
                DocumentGeneration.generation_type == "quiz",
            )
            .first()
        )
        questions = json.loads(row.content) if row and row.content else []
        question = next((q for q in questions if q.get("id") == question_index), None)
        if not question:
            return get_json_result(data=False, message="题目不存在", code=settings.RetCode.NOT_FOUND)

        correct_answer = question.get("correct", "")
        is_correct = student_answer == correct_answer
        explanations = question.get("explanations", {})

        # 记录作答
        StudentQuizResult.create(
            id=get_uuid(),
            student_id=current_user.id,
            doc_id=doc_id,
            question_index=question_index,
            student_answer=student_answer,
            is_correct=is_correct,
        )

        return get_json_result(data={
            "is_correct": is_correct,
            "correct_answer": correct_answer,
            "explanations": explanations,
        }, message="提交成功")
    except Exception as e:
        logger.error(f"submit quiz result error: {e}")
        return get_json_result(data=False, message=str(e), code=settings.RetCode.EXCEPTION_ERROR)


@manager.route("/quiz/<doc_id>/result", methods=["GET"])
@login_required
def get_quiz_result(doc_id):
    """获取当前学生对某文档的测验结果"""
    try:
        if not current_user or not hasattr(current_user, "id"):
            return get_json_result(data={"results": []}, message="用户未登录")

        rows = (
            StudentQuizResult.select()
            .where(
                StudentQuizResult.student_id == current_user.id,
                StudentQuizResult.doc_id == doc_id,
            )
            .order_by(StudentQuizResult.create_time.desc())
        )
        results = [
            {
                "question_index": r.question_index,
                "student_answer": r.student_answer,
                "is_correct": r.is_correct,
            }
            for r in rows
        ]
        return get_json_result(data={"results": results})
    except Exception as e:
        logger.error(f"get quiz result error: {e}")
        return get_json_result(data={"results": []}, message=str(e), code=settings.RetCode.EXCEPTION_ERROR)


# ============================================================
# 个性化测验 API（SM-2 遗忘曲线 + 知识点追踪）
# ============================================================

def _calc_next_review(correct: bool, ease: float, interval: int):
    """SM-2 算法：计算新的 ease_factor 和下次复习间隔（天）"""
    if correct:
        new_ease = min(3.5, ease + 0.15)
        new_interval = max(1, min(120, int(interval * new_ease)))
    else:
        new_ease = max(1.3, ease - 0.2)
        new_interval = 1
    return new_ease, new_interval


def _extract_kp_labels(mindmap_data: dict) -> dict[str, str]:
    """从思维导图 JSON 中递归提取 {node_id: label} 映射"""
    labels = {}

    def walk(node: dict):
        if not isinstance(node, dict):
            return
        nid = node.get("id")
        label = node.get("label")
        if nid and label:
            labels[str(nid)] = label
        for child in node.get("children", []) or []:
            walk(child)

    if isinstance(mindmap_data, dict):
        root = mindmap_data.get("root")
        if root:
            walk(root)
    return labels


def _build_kp_label_map(doc_ids: list[str]) -> dict[str, dict[str, str]]:
    """为多个文档构建 {doc_id: {node_id: label}} 映射"""
    kp_map: dict[str, dict[str, str]] = {}
    for dg in DocumentGeneration.select().where(
        DocumentGeneration.generation_type == "mindmap",
        DocumentGeneration.doc_id.in_(doc_ids),
    ):
        if not dg.content:
            continue
        try:
            mindmap_data = json.loads(dg.content)
            labels = _extract_kp_labels(mindmap_data)
            if labels:
                kp_map[dg.doc_id] = labels
        except (json.JSONDecodeError, TypeError):
            continue
    return kp_map


def _collect_quiz_pool(kb_ids: list[str]) -> list[dict]:
    """从指定知识库下的所有文档中收集测验题目"""
    all_q = []
    for dg in DocumentGeneration.select().where(
        DocumentGeneration.generation_type == "quiz"
    ):
        if not dg.content:
            continue
        try:
            questions = json.loads(dg.content)
        except (json.JSONDecodeError, TypeError):
            continue
        for q in questions:
            q["_doc_id"] = dg.doc_id
            all_q.append(q)
    # 过滤：只保留归属指定知识库的文档的题目
    doc_ids = list({q["_doc_id"] for q in all_q})
    valid_docs = set()
    for doc in Document.select(Document.id).where(
        Document.id.in_(doc_ids), Document.kb_id.in_(kb_ids)
    ):
        valid_docs.add(doc.id)
    return [q for q in all_q if q["_doc_id"] in valid_docs]


@manager.route("/personalized-quiz/start", methods=["POST"])
@login_required
def start_personalized_quiz():
    """启动个性化测验：传入 dialog_id，返回个性化题目列表"""
    try:
        if not current_user or not hasattr(current_user, "id"):
            return get_json_result(data={"questions": []}, message="用户未登录")

        data = request.json or {}
        dialog_id = data.get("dialog_id")
        count = data.get("count", 10)

        if not dialog_id:
            return get_json_result(data={"questions": []}, message="dialog_id 为必填项", code=settings.RetCode.ARGUMENT_ERROR)

        # 从 dialog 获取 kb_ids
        dialog = Dialog.get_or_none(Dialog.id == dialog_id)
        if not dialog:
            return get_json_result(data={"questions": []}, message="助教不存在", code=settings.RetCode.NOT_FOUND)

        try:
            kb_ids = json.loads(dialog.kb_ids) if isinstance(dialog.kb_ids, str) else dialog.kb_ids
        except (json.JSONDecodeError, TypeError):
            kb_ids = []
        if not kb_ids:
            return get_json_result(data={"questions": []}, message="该助教未关联知识库")

        # 收集题目池
        quiz_pool = _collect_quiz_pool(kb_ids)
        if not quiz_pool:
            return get_json_result(data={"questions": [], "message": "暂无可用题目"})

        # 查询学生知识点掌握度
        mastery_rows = list(
            KnowledgePointMastery.select().where(
                KnowledgePointMastery.student_id == current_user.id
            )
        )
        mastery_map = {}
        for m in mastery_rows:
            mastery_map[m.node_id] = {
                "correct_count": m.correct_count,
                "wrong_count": m.wrong_count,
                "next_review_time": float(m.next_review_time) if m.next_review_time else None,
                "review_count": m.review_count,
            }

        # 构建知识点 ID → 名称映射（从思维导图中提取）
        doc_ids_in_pool = list({q["_doc_id"] for q in quiz_pool})
        kp_label_map = _build_kp_label_map(doc_ids_in_pool)

        # 按知识点分组题目
        kp_to_qs: dict[str, list[dict]] = {}
        for q in quiz_pool:
            kp_ids = q.get("knowledge_point_ids", [])
            if not kp_ids:
                kp_ids = [f"uncat_{q['_doc_id']}"]
            for kp in kp_ids:
                kp_to_qs.setdefault(kp, []).append(q)

        # 计算优先级分数
        now = time.time()
        scored = []
        for kp_id, qs in kp_to_qs.items():
            m = mastery_map.get(kp_id, {})
            score = 0.0
            correct_c = m.get("correct_count", 0)
            wrong_c = m.get("wrong_count", 0)
            review_c = m.get("review_count", 0)
            next_t = m.get("next_review_time")

            if review_c == 0:
                score = 4.0  # 从未复习 → 最优先
            else:
                total = correct_c + wrong_c
                acc = correct_c / total if total > 0 else 0
                if next_t and next_t < now:
                    score += 3.0  # 过期该复习了
                if acc < 0.5 and total >= 2:
                    score += 2.0  # 薄弱点

            if score > -50:
                scored.append((kp_id, score, qs))

        # 排序，取 Top N
        scored.sort(key=lambda x: x[1], reverse=True)

        def _pick_from_pool(kp_list, max_per_kp):
            nonlocal selected, used_ids
            for kp_id, score, qs in kp_list:
                available = [q for q in qs if q["id"] not in used_ids]
                if not available:
                    continue
                pick = min(max_per_kp(score), len(available))
                # 按题目 ID 排序取前 N 个，保证每次点击结果一致
                available.sort(key=lambda x: x["id"])
                for q in available[:pick]:
                    used_ids.add(q["id"])
                    doc_id = q.get("_doc_id", "")
                    kp_ids = q.get("knowledge_point_ids", [])
                    # 解析知识点 ID → 名称
                    doc_labels = kp_label_map.get(doc_id, {})
                    kp_names = [doc_labels.get(kp, kp) for kp in kp_ids]
                    selected.append({
                        "id": q["id"],
                        "doc_id": doc_id,
                        "knowledge_point_ids": kp_ids,
                        "knowledge_point_names": kp_names,
                        "question": q["question"],
                        "options": q["options"],
                    })
                if len(selected) >= count:
                    return True
            return False

        selected = []
        used_ids = set()
        top_kps = scored[:count]

        # 第一轮：每个知识点最多选 2 题（高优先级）或 1 题
        done = _pick_from_pool(top_kps, lambda s: 2 if s >= 3 else 1)
        # 第二轮：如果题目不够，放宽上限，从剩余题目中补齐
        if not done and len(selected) < count:
            _pick_from_pool(scored, lambda s: count - len(selected))

        random.shuffle(selected)
        return get_json_result(data={"questions": selected})

    except Exception as e:
        logger.error(f"personalized quiz start error: {e}")
        return get_json_result(data={"questions": []}, message=str(e), code=settings.RetCode.EXCEPTION_ERROR)


@manager.route("/personalized-quiz/answer", methods=["POST"])
@login_required
def answer_personalized_quiz():
    """提交个性化测验单题答案，后端判题并同步更新知识点掌握度"""
    try:
        if not current_user or not hasattr(current_user, "id"):
            return get_json_result(data=False, message="用户未登录", code=settings.RetCode.AUTHENTICATION_ERROR)

        data = request.json or {}
        doc_id = data.get("doc_id") or ""
        question_id = data.get("question_id", 0)
        knowledge_point_ids = data.get("knowledge_point_ids", [])
        student_answer = data.get("student_answer", "")

        # 从数据库查出正确 answer，后端判题
        row = (
            DocumentGeneration.select()
            .where(
                DocumentGeneration.doc_id == doc_id,
                DocumentGeneration.generation_type == "quiz",
            )
            .first()
        )
        questions = json.loads(row.content) if row and row.content else []
        question = next((q for q in questions if q.get("id") == question_id), None)
        correct_answer = question.get("correct", "") if question else ""
        is_correct = student_answer == correct_answer
        explanations = question.get("explanations", {}) if question else {}

        # 记录作答 (student_quiz_result)
        StudentQuizResult.create(
            id=get_uuid(),
            student_id=current_user.id,
            doc_id=doc_id or "",
            question_index=question_id,
            student_answer=student_answer,
            is_correct=is_correct,
        )

        # 更新知识点掌握度
        if knowledge_point_ids:
            now_ts = int(time.time())
            for kp_id in knowledge_point_ids:
                existing = KnowledgePointMastery.select().where(
                    KnowledgePointMastery.student_id == current_user.id,
                    KnowledgePointMastery.doc_id == doc_id,
                    KnowledgePointMastery.node_id == kp_id,
                ).first()

                if existing:
                    current_interval = max(1, (existing.review_count or 1))
                    new_ease, new_interval = _calc_next_review(
                        is_correct, existing.ease_factor, current_interval
                    )
                    next_review = int(now_ts + new_interval * 86400)
                    if is_correct:
                        existing.correct_count += 1
                    else:
                        existing.wrong_count += 1
                    existing.ease_factor = new_ease
                    existing.review_count = (existing.review_count or 0) + 1
                    existing.last_review_time = now_ts
                    existing.next_review_time = next_review
                    existing.save()
                else:
                    new_ease, new_interval = _calc_next_review(is_correct, 2.5, 1)
                    next_review = int(now_ts + new_interval * 86400)
                    KnowledgePointMastery.create(
                        id=get_uuid(),
                        student_id=current_user.id,
                        doc_id=doc_id or "",
                        node_id=kp_id,
                        correct_count=1 if is_correct else 0,
                        wrong_count=0 if is_correct else 1,
                        ease_factor=new_ease,
                        review_count=1,
                        last_review_time=now_ts,
                        next_review_time=next_review,
                    )

        return get_json_result(data={
            "is_correct": is_correct,
            "correct_answer": correct_answer,
            "explanations": explanations,
        }, message="提交成功")
    except Exception as e:
        logger.error(f"personalized quiz answer error: {e}")
        return get_json_result(data=False, message=str(e), code=settings.RetCode.EXCEPTION_ERROR)


@manager.route("/knowledge-report", methods=["GET"])
@login_required
def get_knowledge_report():
    """获取学生在某助教下的知识点掌握度报告"""
    try:
        if not current_user or not hasattr(current_user, "id"):
            return get_json_result(data={"weak_points": [], "strong_points": [], "stats": {}}, message="用户未登录")

        dialog_id = request.args.get("dialog_id")
        if not dialog_id:
            return get_json_result(data={"weak_points": [], "strong_points": [], "stats": {}}, message="dialog_id 为必填项")

        dialog = Dialog.get_or_none(Dialog.id == dialog_id)
        if not dialog:
            return get_json_result(data={"weak_points": [], "strong_points": [], "stats": {}}, message="助教不存在")

        try:
            kb_ids = json.loads(dialog.kb_ids) if isinstance(dialog.kb_ids, str) else dialog.kb_ids
        except (json.JSONDecodeError, TypeError):
            kb_ids = []

        rows = KnowledgePointMastery.select().where(
            KnowledgePointMastery.student_id == current_user.id,
            KnowledgePointMastery.doc_id.in_(
                Document.select(Document.id).where(Document.kb_id.in_(kb_ids))
            ),
        )

        weak, strong = [], []
        tc, tw = 0, 0
        now = time.time()
        for r in rows:
            total = r.correct_count + r.wrong_count
            acc = r.correct_count / total if total > 0 else 0
            entry = {
                "node_id": r.node_id,
                "correct_count": r.correct_count,
                "wrong_count": r.wrong_count,
                "accuracy": round(acc, 2),
                "review_count": r.review_count,
                "need_review": r.next_review_time and float(r.next_review_time) < now,
            }
            if acc < 0.5 or entry["need_review"]:
                weak.append(entry)
            elif acc >= 0.8:
                strong.append(entry)
            tc += r.correct_count
            tw += r.wrong_count

        total = tc + tw
        return get_json_result(data={
            "weak_points": weak,
            "strong_points": strong,
            "stats": {
                "total_correct": tc,
                "total_wrong": tw,
                "total_attempts": total,
                "overall_accuracy": round(tc / total, 2) if total > 0 else 0,
                "knowledge_points_count": len(rows),
            },
        })
    except Exception as e:
        logger.error(f"knowledge report error: {e}")
        return get_json_result(data={"weak_points": [], "strong_points": [], "stats": {}}, message=str(e), code=settings.RetCode.EXCEPTION_ERROR)


# ============================================================
# 笔记相关 API
# ============================================================

@manager.route("/note/<doc_id>", methods=["GET"])
@login_required
def get_note(doc_id):
    """获取某文档某页的笔记"""
    try:
        if not current_user or not hasattr(current_user, "id"):
            return get_json_result(data={"content": ""}, message="用户未登录")

        page_number = request.args.get("page_number", 1, type=int)

        row = (
            StudentNote.select()
            .where(
                StudentNote.student_id == current_user.id,
                StudentNote.doc_id == doc_id,
                StudentNote.page_number == page_number,
            )
            .first()
        )
        return get_json_result(data={"content": row.content if row else ""})
    except Exception as e:
        logger.error(f"get note error: {e}")
        return get_json_result(data={"content": ""}, message=str(e), code=settings.RetCode.EXCEPTION_ERROR)


@manager.route("/note/<doc_id>", methods=["POST"])
@login_required
def save_note(doc_id):
    """保存或更新某文档某页的笔记（upsert）"""
    try:
        if not current_user or not hasattr(current_user, "id"):
            return get_json_result(data=False, message="用户未登录", code=settings.RetCode.AUTHENTICATION_ERROR)

        data = request.json
        page_number = data.get("page_number")
        content = data.get("content", "")

        if page_number is None:
            return get_json_result(data=False, message="page_number 为必填项", code=settings.RetCode.ARGUMENT_ERROR)

        # Upsert
        existing = (
            StudentNote.select()
            .where(
                StudentNote.student_id == current_user.id,
                StudentNote.doc_id == doc_id,
                StudentNote.page_number == page_number,
            )
            .first()
        )

        if existing:
            existing.content = content
            existing.save()
        else:
            StudentNote.create(
                id=get_uuid(),
                student_id=current_user.id,
                doc_id=doc_id,
                page_number=page_number,
                content=content,
            )

        return get_json_result(data=True, message="保存成功")
    except Exception as e:
        logger.error(f"save note error: {e}")
        return get_json_result(data=False, message=str(e), code=settings.RetCode.EXCEPTION_ERROR)


@manager.route("/notes/<doc_id>", methods=["GET"])
@login_required
def get_all_notes(doc_id):
    """获取某文档所有页面的笔记（用于预览哪些页有笔记）"""
    try:
        if not current_user or not hasattr(current_user, "id"):
            return get_json_result(data={"notes": {}}, message="用户未登录")

        rows = (
            StudentNote.select()
            .where(
                StudentNote.student_id == current_user.id,
                StudentNote.doc_id == doc_id,
            )
        )
        notes = {str(r.page_number): r.content for r in rows}
        return get_json_result(data={"notes": notes})
    except Exception as e:
        logger.error(f"get all notes error: {e}")
        return get_json_result(data={"notes": {}}, message=str(e), code=settings.RetCode.EXCEPTION_ERROR)


# ============================================================
# 学情分析 API
# ============================================================

@manager.route("/analytics/overview", methods=["GET"])
@login_required
def get_analytics_overview():
    """学情分析总览：统计、趋势、掌握度分布、薄弱点、待复习"""
    try:
        if not current_user or not hasattr(current_user, "id"):
            return get_json_result(data={}, message="用户未登录", code=settings.RetCode.AUTHENTICATION_ERROR)

        student_id = current_user.id
        now = time.time()
        thirty_days_ago = int((now - 30 * 86400) * 1000)  # ms

        # ---- stats ----
        total_cards = StudentCardProgress.select().where(
            StudentCardProgress.student_id == student_id
        ).count()
        total_quiz = StudentQuizResult.select().where(
            StudentQuizResult.student_id == student_id
        ).count()
        quiz_correct = StudentQuizResult.select().where(
            StudentQuizResult.student_id == student_id,
            StudentQuizResult.is_correct == True,
        ).count()
        quiz_accuracy = round(quiz_correct / total_quiz, 2) if total_quiz > 0 else 0

        # 知识点掌握度
        kp_rows = list(KnowledgePointMastery.select().where(
            KnowledgePointMastery.student_id == student_id
        ))

        # 构建知识点 ID → 名称映射
        doc_ids = list({r.doc_id for r in kp_rows})
        kp_label_map = _build_kp_label_map(doc_ids)
        def _kp_label(node_id, doc_id):
            return kp_label_map.get(doc_id, {}).get(node_id, node_id)

        kp_all = []
        mastered = 0
        overdue = 0
        for r in kp_rows:
            total = r.correct_count + r.wrong_count
            acc = r.correct_count / total if total > 0 else 0
            need_review = bool(r.next_review_time and float(r.next_review_time) < now)
            kp_all.append({
                "node_id": r.node_id,
                "label": _kp_label(r.node_id, r.doc_id),
                "doc_id": r.doc_id,
                "correct_count": r.correct_count,
                "wrong_count": r.wrong_count,
                "accuracy": round(acc, 2),
                "review_count": r.review_count,
                "need_review": need_review,
            })
            if acc >= 0.8 and total >= 2:
                mastered += 1
            if need_review:
                overdue += 1

        # 学习天数
        study_dates = set()
        for r in StudentCardProgress.select(StudentCardProgress.create_time).where(
            StudentCardProgress.student_id == student_id
        ):
            if r.create_time:
                study_dates.add(time.strftime("%Y-%m-%d", time.localtime(r.create_time / 1000)))
        for r in StudentQuizResult.select(StudentQuizResult.create_time).where(
            StudentQuizResult.student_id == student_id
        ):
            if r.create_time:
                study_dates.add(time.strftime("%Y-%m-%d", time.localtime(r.create_time / 1000)))
        for r in Conversation.select(Conversation.create_time).where(
            Conversation.user_id == student_id
        ):
            if r.create_time:
                study_dates.add(time.strftime("%Y-%m-%d", time.localtime(r.create_time / 1000)))

        # ---- daily_trend: 最近 30 天每日活动 ----
        date_cards = {}
        date_quizzes = {}
        date_convs = {}

        for r in StudentCardProgress.select(
            StudentCardProgress.create_time
        ).where(
            StudentCardProgress.student_id == student_id,
            StudentCardProgress.create_time >= thirty_days_ago,
        ):
            if r.create_time:
                d = time.strftime("%Y-%m-%d", time.localtime(r.create_time / 1000))
                date_cards[d] = date_cards.get(d, 0) + 1

        for r in StudentQuizResult.select(
            StudentQuizResult.create_time
        ).where(
            StudentQuizResult.student_id == student_id,
            StudentQuizResult.create_time >= thirty_days_ago,
        ):
            if r.create_time:
                d = time.strftime("%Y-%m-%d", time.localtime(r.create_time / 1000))
                date_quizzes[d] = date_quizzes.get(d, 0) + 1

        for r in Conversation.select(
            Conversation.create_time
        ).where(
            Conversation.user_id == student_id,
            Conversation.create_time >= thirty_days_ago,
        ):
            if r.create_time:
                d = time.strftime("%Y-%m-%d", time.localtime(r.create_time / 1000))
                date_convs[d] = date_convs.get(d, 0) + 1

        daily_trend = []
        for i in range(29, -1, -1):
            day = time.strftime("%Y-%m-%d", time.localtime(now - i * 86400))
            daily_trend.append({
                "date": day,
                "cards": date_cards.get(day, 0),
                "quizzes": date_quizzes.get(day, 0),
                "conversations": date_convs.get(day, 0),
            })

        # ---- weak_points & review_queue ----
        weak_points = [x for x in kp_all if x["accuracy"] < 0.6 and (x["correct_count"] + x["wrong_count"]) >= 2]
        weak_points.sort(key=lambda x: x["accuracy"])

        review_queue = [x for x in kp_all if x["need_review"]]

        return get_json_result(data={
            "stats": {
                "total_cards_reviewed": total_cards,
                "total_quiz_attempts": total_quiz,
                "quiz_accuracy": quiz_accuracy,
                "knowledge_points_mastered": mastered,
                "total_study_days": len(study_dates),
                "review_overdue_count": overdue,
            },
            "mastery_distribution": kp_all,
            "daily_trend": daily_trend,
            "weak_points": weak_points,
            "review_queue": review_queue,
        })

    except Exception as e:
        logger.error(f"analytics overview error: {e}")
        return get_json_result(data={}, message=str(e), code=settings.RetCode.EXCEPTION_ERROR)
