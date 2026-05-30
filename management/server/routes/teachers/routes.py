from flask import Blueprint, request, jsonify
from services.teachers.service import (
    get_teachers_with_pagination,
    create_teacher,
    delete_teacher,
    update_teacher,
    reset_teacher_password
)
from auth import require_system_admin, get_current_user

# 创建教师蓝图
teachers_bp = Blueprint('teachers', __name__, url_prefix='/api/v1/teachers')


@teachers_bp.route('', methods=['GET'])
@require_system_admin  # 只有系统超级管理员可以查看教师列表
def get_teachers():
    """获取教师列表，支持分页和条件查询"""
    try:
        # 获取查询参数
        current_page = int(request.args.get('currentPage', 1))
        page_size = int(request.args.get('size', 10))
        username = request.args.get('username', '')
        email = request.args.get('email', '')
        sort_by = request.args.get("sort_by", "create_time")
        sort_order = request.args.get("sort_order", "desc")

        # 调用服务函数获取分页和筛选后的教师数据
        teachers, total = get_teachers_with_pagination(
            current_page, page_size, username, email, sort_by, sort_order
        )

        # 返回符合前端期望格式的数据
        return jsonify({
            "code": 0,
            "data": {
                "list": teachers,
                "total": total
            },
            "message": "获取教师列表成功"
        })
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"获取教师列表失败: {str(e)}"
        }), 500


@teachers_bp.route('', methods=['POST'])
@require_system_admin  # 只有系统超级管理员可以创建教师
def create_teacher_route():
    """
    创建教师

    创建教师的时候，
    要向user表中添加一条信息
    tenant表中添加一条信息，一个租户其实就是一个老师。

    """
    data = request.json

    # 获取当前用户信息（用于日志记录等场景）
    current_user = get_current_user()
    print(f"系统管理员 {current_user['username']} 正在创建教师")

    # 验证必填字段
    if not data.get("username") or not data.get("email") or not data.get("password"):
        return jsonify({
            "code": 400,
            "message": "缺少必填字段: username, email, password"
        }), 400

    try:
        success, result = create_teacher(teacher_data=data)

        if success:
            return jsonify({
                "code": 0,
                "message": "教师创建成功",
                "data": {"id": result}
            })
        else:
            return jsonify({
                "code": 400,
                "message": f"教师创建失败: {result}"
            }), 400
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"教师创建失败: {str(e)}"
        }), 500


@teachers_bp.route('/<string:teacher_id>', methods=['PUT'])
@require_system_admin  # 只有系统超级管理员可以更新教师
def update_teacher_route(teacher_id):
    """更新教师信息"""
    data = request.json

    # 验证必填字段
    if not data.get("username") or not data.get("email"):
        return jsonify({
            "code": 400,
            "message": "缺少必填字段: username, email"
        }), 400

    try:
        success, message = update_teacher(teacher_id=teacher_id, teacher_data=data)

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
            "message": f"更新教师失败: {str(e)}"
        }), 500


@teachers_bp.route('/<string:teacher_id>', methods=['DELETE'])
@require_system_admin  # 只有系统超级管理员可以删除教师
def delete_teacher_route(teacher_id):
    """删除教师"""
    try:
        success, message = delete_teacher(teacher_id=teacher_id)

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
            "message": f"删除教师失败: {str(e)}"
        }), 500


@teachers_bp.route('/<string:teacher_id>/reset-password', methods=['PUT'])
@require_system_admin  # 只有系统超级管理员可以重置教师密码
def reset_teacher_password_route(teacher_id):
    """重置教师密码"""
    data = request.json

    # 验证必填字段
    if not data.get('password'):
        return jsonify({
            "code": 400,
            "message": "缺少新密码参数 'password'"
        }), 400

    try:
        success, message = reset_teacher_password(
            teacher_id=teacher_id,
            new_password=data.get('password')
        )

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
            "message": f"重置密码失败: {str(e)}"
        }), 500
