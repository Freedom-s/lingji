from flask import Blueprint, request, jsonify
from services.assistants.service import (
    get_assistants_with_pagination,
    create_assistant,
    delete_assistant,
    update_assistant
)
from auth import require_superuser, get_current_user

# 创建助教蓝图
assistants_bp = Blueprint('assistants', __name__, url_prefix='/api/v1/assistants')


@assistants_bp.route('', methods=['GET'])
@require_superuser
def get_assistants():
    """获取助教列表，支持分页和条件查询"""
    try:
        # 获取查询参数
        current_page = int(request.args.get('currentPage', 1))
        page_size = int(request.args.get('size', 10))
        assistant_name = request.args.get('assistant_name', '')
        sort_by = request.args.get("sort_by", "create_date")
        sort_order = request.args.get("sort_order", "desc")

        # 调用服务函数获取分页和筛选后的助教数据
        assistants, total = get_assistants_with_pagination(
            current_page, page_size, assistant_name, sort_by, sort_order
        )

        # 返回符合前端期望格式的数据
        return jsonify({
            "code": 0,
            "data": {
                "list": assistants,
                "total": total
            },
            "message": "获取助教列表成功"
        })
    except Exception as e:
        # 错误处理
        return jsonify({
            "code": 500,
            "message": f"获取助教列表失败: {str(e)}"
        }), 500


@assistants_bp.route('', methods=['POST'])
@require_superuser
def create_assistant_route():
    """创建助教"""
    data = request.json

    # 验证必填字段
    if not data.get("assistant_name"):
        return jsonify({
            "code": 400,
            "message": "缺少必填字段: assistant_name"
        }), 400

    try:
        success, result = create_assistant(assistant_data=data)

        if success:
            return jsonify({
                "code": 0,
                "message": "助教创建成功",
                "data": {"id": result}
            })
        else:
            return jsonify({
                "code": 400,
                "message": f"助教创建失败: {result}"
            }), 400
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"助教创建失败: {str(e)}"
        }), 500


@assistants_bp.route('/<string:assistant_id>', methods=['PUT'])
@require_superuser
def update_assistant_route(assistant_id):
    """更新助教信息"""
    data = request.json

    # 验证必填字段
    if not data.get("assistant_name"):
        return jsonify({
            "code": 400,
            "message": "缺少必填字段: assistant_name"
        }), 400

    try:
        success, message = update_assistant(assistant_id=assistant_id, assistant_data=data)

        if success:
            return jsonify({
                "code": 0,
                "message": message
            })
        else:
            return jsonify({
                "code": 400,
                "message": message
            }), 400
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"更新助教失败: {str(e)}"
        }), 500


@assistants_bp.route('/<string:assistant_id>', methods=['DELETE'])
@require_superuser
def delete_assistant_route(assistant_id):
    """删除助教"""
    try:
        success, message = delete_assistant(assistant_id=assistant_id)

        if success:
            return jsonify({
                "code": 0,
                "message": message
            })
        else:
            return jsonify({
                "code": 404,
                "message": message
            }), 404
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"删除助教失败: {str(e)}"
        }), 500


@assistants_bp.route('/<string:assistant_id>/reset-password', methods=['PUT'])
@require_superuser
def reset_assistant_password_route(assistant_id):
    """重置助教密码（助教类型为dialog，不支持密码重置）"""
    return jsonify({
        "code": 400,
        "message": "助教（对话助手）不支持密码重置操作"
    }), 400
