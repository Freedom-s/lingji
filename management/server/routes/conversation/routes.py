from flask import jsonify, request

from auth import get_current_user, require_superuser
from services.conversation.service import (
    get_class_students,
    get_conversation_classes,
    get_conversation_detail,
    get_conversations as get_conversation_records,
)
from .. import conversation_bp


def _teacher_id():
    current_user = get_current_user() or {}
    return current_user.get("user_id")


def _positive_int(name, default, maximum=None):
    value = int(request.args.get(name, default))
    if value < 1:
        raise ValueError(f"{name} 必须大于 0")
    return min(value, maximum) if maximum else value


@conversation_bp.route("/classes", methods=["GET"])
@require_superuser
def get_classes():
    """列出当前老师自己的班级及会话统计。"""
    try:
        return jsonify({
            "code": 0,
            "data": get_conversation_classes(_teacher_id()),
            "message": "获取班级列表成功",
        })
    except Exception as error:
        return jsonify({"code": 500, "message": f"获取班级列表失败: {error}"}), 500


@conversation_bp.route("/students", methods=["GET"])
@require_superuser
def get_students():
    """列出当前老师指定班级内的学生及会话统计。"""
    class_id = request.args.get("class_id", "").strip()
    if not class_id:
        return jsonify({"code": 400, "message": "班级ID不能为空"}), 400
    try:
        return jsonify({
            "code": 0,
            "data": get_class_students(_teacher_id(), class_id),
            "message": "获取学生列表成功",
        })
    except Exception as error:
        return jsonify({"code": 500, "message": f"获取学生列表失败: {error}"}), 500


@conversation_bp.route("", methods=["GET"])
@require_superuser
def get_conversations():
    """按班级、学生和关键字分页查询真实会话。"""
    class_id = request.args.get("class_id", "").strip()
    if not class_id:
        return jsonify({"code": 400, "message": "班级ID不能为空"}), 400

    try:
        conversations, total = get_conversation_records(
            teacher_id=_teacher_id(),
            class_id=class_id,
            student_id=request.args.get("student_id", "").strip() or None,
            keyword=request.args.get("keyword", ""),
            page=_positive_int("page", 1),
            size=_positive_int("size", 20, 100),
        )
        return jsonify({
            "code": 0,
            "data": {"list": conversations, "total": total},
            "message": "获取会话列表成功",
        })
    except ValueError as error:
        return jsonify({"code": 400, "message": str(error)}), 400
    except Exception as error:
        return jsonify({"code": 500, "message": f"获取会话列表失败: {error}"}), 500


def _conversation_detail_response(conversation_id):
    class_id = request.args.get("class_id", "").strip()
    if not class_id:
        return jsonify({"code": 400, "message": "班级ID不能为空"}), 400
    try:
        detail = get_conversation_detail(_teacher_id(), class_id, conversation_id)
        if not detail:
            return jsonify({"code": 404, "message": "会话不存在或无权查看"}), 404
        return jsonify({"code": 0, "data": detail, "message": "获取会话详情成功"})
    except Exception as error:
        return jsonify({"code": 500, "message": f"获取会话详情失败: {error}"}), 500


@conversation_bp.route("/<conversation_id>", methods=["GET"])
@require_superuser
def get_conversation(conversation_id):
    """获取一条会话的消息和引用，只允许其班级老师查看。"""
    return _conversation_detail_response(conversation_id)


@conversation_bp.route("/<conversation_id>/messages", methods=["GET"])
@require_superuser
def get_messages(conversation_id):
    """保留旧地址，返回与详情接口相同的安全数据。"""
    return _conversation_detail_response(conversation_id)
