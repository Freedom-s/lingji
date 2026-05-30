from flask import jsonify, request
from services.teams.service import get_teams_with_pagination, get_team_by_id, delete_team, get_team_members, add_team_member, remove_team_member, create_team, add_class_assistant, get_class_assistants, remove_class_assistant, batch_delete_teams
from routes import teams_bp
from auth import require_superuser

@teams_bp.route('', methods=['POST'])
@require_superuser
def create_team_route():
    """创建班级"""
    data = request.json

    # 验证必填字段
    if not data.get("name"):
        return jsonify({
            "code": 400,
            "message": "缺少必填字段: name"
        }), 400

    try:
        success, result = create_team(team_data=data)

        if success:
            return jsonify({
                "code": 0,
                "message": "班级创建成功",
                "data": {"id": result}
            })
        else:
            return jsonify({
                "code": 400,
                "message": f"班级创建失败: {result}"
            }), 400
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"班级创建失败: {str(e)}"
        }), 500


@teams_bp.route('', methods=['GET'])
@require_superuser
def get_teams():
    """获取团队列表的API端点，支持分页和条件查询"""
    try:
        # 获取查询参数
        current_page = int(request.args.get('currentPage', 1))
        page_size = int(request.args.get('size', 10))
        team_name = request.args.get('name', '')
        sort_by = request.args.get("sort_by", "create_time")
        sort_order = request.args.get("sort_order", "desc")
        
        # 调用服务函数获取分页和筛选后的团队数据
        teams, total = get_teams_with_pagination(current_page, page_size, team_name, sort_by, sort_order)
        
        # 返回符合前端期望格式的数据
        return jsonify({
            "code": 0,
            "data": {
                "list": teams,
                "total": total
            },
            "message": "获取团队列表成功"
        })
    except Exception as e:
        # 错误处理
        return jsonify({
            "code": 500,
            "message": f"获取团队列表失败: {str(e)}"
        }), 500

@teams_bp.route('/<string:team_id>', methods=['GET'])
@require_superuser
def get_team(team_id):
    """获取单个团队详情的API端点"""
    try:
        team = get_team_by_id(team_id)
        if team:
            return jsonify({
                "code": 0,
                "data": team,
                "message": "获取团队详情成功"
            })
        else:
            return jsonify({
                "code": 404,
                "message": f"团队 {team_id} 不存在"
            }), 404
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"获取团队详情失败: {str(e)}"
        }), 500


@teams_bp.route('/<string:team_id>', methods=['DELETE'])
@require_superuser
def delete_team_route(team_id):
    """删除团队的API端点"""
    try:
        success = delete_team(team_id)
        if success:
            return jsonify({
                "code": 0,
                "message": f"团队 {team_id} 删除成功"
            })
        else:
            return jsonify({
                "code": 404,
                "message": f"团队 {team_id} 不存在或删除失败"
            }), 404
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"删除团队失败: {str(e)}"
        }), 500


@teams_bp.route('/batch', methods=['POST'])
@require_superuser
def batch_delete_teams_route():
    """批量删除班级的API端点"""
    try:
        data = request.json
        class_ids = data.get('ids')

        if not class_ids:
            return jsonify({
                "code": 400,
                "message": "缺少必填字段: ids"
            }), 400

        success, message = batch_delete_teams(class_ids)
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
            "message": f"批量删除失败: {str(e)}"
        }), 500

@teams_bp.route('/<string:team_id>/members', methods=['GET'])
@require_superuser
def get_team_members_route(team_id):
    """获取团队成员的API端点"""
    try:
        members = get_team_members(team_id)
        
        return jsonify({
            "code": 0,
            "data": members,
            "message": "获取团队成员成功"
        })
    except Exception as e:
        print(f"获取团队成员异常: {str(e)}")
        return jsonify({
            "code": 500,
            "message": f"获取团队成员失败: {str(e)}"
        }), 500

@teams_bp.route('/<string:team_id>/members', methods=['POST'])
@require_superuser
def add_team_member_route(team_id):
    """添加团队成员的API端点"""
    try:
        data = request.json
        user_id = data.get('user_id')
        success = add_team_member(team_id, user_id)
        if success:
            return jsonify({
                "code": 0,
                "message": "添加团队成员成功"
            })
        else:
            return jsonify({
                "code": 400,
                "message": "添加团队成员失败"
            }), 400
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"添加团队成员失败: {str(e)}"
        }), 500

@teams_bp.route('/<string:team_id>/members/<string:user_id>', methods=['DELETE'])
@require_superuser
def remove_team_member_route(team_id, user_id):
    """移除团队成员的API端点"""
    try:
        success = remove_team_member(team_id, user_id)
        if success:
            return jsonify({
                "code": 0,
                "message": "移除团队成员成功"
            })
        else:
            return jsonify({
                "code": 400,
                "message": "移除团队成员失败"
            }), 400
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"移除团队成员失败: {str(e)}"
        }), 500


@teams_bp.route('/<string:team_id>/assistants', methods=['POST'])
@require_superuser
def add_class_assistant_route(team_id):
    """为班级添加助教的API端点"""
    try:
        data = request.json
        dialog_id = data.get('dialog_id')

        if not dialog_id:
            return jsonify({
                "code": 400,
                "message": "缺少必填字段: dialog_id"
            }), 400

        success, message = add_class_assistant(team_id, dialog_id)
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
            "message": f"添加助教失败: {str(e)}"
        }), 500


@teams_bp.route('/<string:team_id>/assistants', methods=['GET'])
@require_superuser
def get_class_assistants_route(team_id):
    """获取班级助教列表的API端点"""
    try:
        assistants = get_class_assistants(team_id)

        return jsonify({
            "code": 0,
            "data": assistants,
            "message": "获取班级助教列表成功"
        })
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"获取班级助教列表失败: {str(e)}"
        }), 500


@teams_bp.route('/<string:team_id>/assistants/<string:assistant_id>', methods=['DELETE'])
@require_superuser
def remove_class_assistant_route(team_id, assistant_id):
    """移除班级助教的API端点"""
    try:
        success, message = remove_class_assistant(team_id, assistant_id)
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
            "message": f"移除助教失败: {str(e)}"
        }), 500