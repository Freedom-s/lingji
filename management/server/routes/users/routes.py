from flask import jsonify, request
from services.users.service import get_users_with_pagination, delete_user, create_user, update_user, reset_user_password
from .. import users_bp
from auth import require_superuser, get_current_user

@users_bp.route('', methods=['GET'])
@require_superuser
def get_users():
    """获取用户的API端点,支持分页和条件查询"""
    try:
        # 获取查询参数
        current_page = int(request.args.get('currentPage', 1))
        page_size = int(request.args.get('size', 10))
        username = request.args.get('username', '')
        email = request.args.get('email', '')
        sort_by = request.args.get("sort_by", "create_time")
        sort_order = request.args.get("sort_order", "desc")
        
        # 调用服务函数获取分页和筛选后的用户数据
        users, total = get_users_with_pagination(current_page, page_size, username, email, sort_by, sort_order)
        
        # 返回符合前端期望格式的数据
        return jsonify({
            "code": 0,  # 成功状态码
            "data": {
                "list": users,
                "total": total
            },
            "message": "获取用户列表成功"
        })
    except Exception as e:
        # 错误处理
        return jsonify({
            "code": 500,
            "message": f"获取用户列表失败: {str(e)}"
        }), 500

@users_bp.route('/<string:user_id>', methods=['DELETE'])
@require_superuser
def delete_user_route(user_id):
    """删除用户的API端点"""
    success, message = delete_user(user_id)

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

@users_bp.route('', methods=['POST'])
@require_superuser
def create_user_route():
    """创建用户的API端点"""
    data = request.json
    try:
        success, message = create_user(user_data=data)
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
            "message": f"用户创建失败: {str(e)}"
        }), 500

@users_bp.route('/<string:user_id>', methods=['PUT'])
@require_superuser
def update_user_route(user_id):
    """更新用户的API端点"""
    data = request.json
    user_id = data.get('id')
    success, message = update_user(user_id=user_id, user_data=data)

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


@users_bp.route('/<string:user_id>/reset-password', methods=['PUT'])
@require_superuser
def reset_password_route(user_id):
    """
    重置用户密码的API端点
    Args:
        user_id (str): 需要重置密码的用户ID
    Returns:
        Response: JSON响应
    """
    try:
        data = request.json
        new_password = data.get('password')

        if not new_password:
            return jsonify({"code": 400, "message": "缺少新密码参数 'password'"}), 400

        success, message = reset_user_password(user_id=user_id, new_password=new_password)

        if success:
            return jsonify({
                "code": 0,
                "message": message
            })
        else:
            return jsonify({"code": 400, "message": message}), 400
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"重置密码失败: {str(e)}"
        }), 500