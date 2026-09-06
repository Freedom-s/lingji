from flask import Blueprint, request, jsonify
from services.dashboard.service import (
    get_dashboard_overview,
    get_active_students_chart,
    get_conversation_trend_chart,
    get_assistant_ranking,
    get_class_activity_ranking,
    get_learning_insights,
    get_student_learning_detail,
)
from auth import require_superuser, get_current_user

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/v1/dashboard')


@dashboard_bp.route('/overview', methods=['GET'])
@require_superuser
def dashboard_overview():
    """获取dashboard概览数据（6个基础指标）"""
    try:
        current_user = get_current_user()
        # 用户ID即为租户ID
        tenant_id = current_user["user_id"]

        # 获取概览数据
        success, result = get_dashboard_overview(tenant_id)

        if success:
            return jsonify({
                "code": 0,
                "data": result,
                "message": "获取概览数据成功"
            })
        else:
            return jsonify({
                "code": 500,
                "message": f"获取概览数据失败: {result}"
            }), 500

    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"获取概览数据失败: {str(e)}"
        }), 500


@dashboard_bp.route('/chart/active-students', methods=['GET'])
@require_superuser
def active_students_chart():
    """
    获取活跃学生数趋势图数据
    
    说明：只有用户登录系统，并且产生了conversation，才能够算作活跃，否则不算活跃。
    """
    try:
        current_user = get_current_user()
        tenant_id = current_user["user_id"]
        time_range = request.args.get('range', '24h')  # 24h, 7d, 30d

        # 获取活跃学生趋势数据
        success, result = get_active_students_chart(tenant_id, time_range)

        if success:
            return jsonify({
                "code": 0,
                "data": result,
                "message": "获取活跃学生趋势数据成功"
            })
        else:
            return jsonify({
                "code": 500,
                "message": f"获取活跃学生趋势数据失败: {result}"
            }), 500

    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"获取活跃学生趋势数据失败: {str(e)}"
        }), 500


@dashboard_bp.route('/chart/conversation-trend', methods=['GET'])
@require_superuser
def conversation_trend_chart():
    """获取会话数趋势图数据"""
    try:
        current_user = get_current_user()
        tenant_id = current_user["user_id"]
        time_range = request.args.get('range', '24h')  # 24h, 7d, 30d

        # 获取会话趋势数据
        success, result = get_conversation_trend_chart(tenant_id, time_range)

        if success:
            return jsonify({
                "code": 0,
                "data": result,
                "message": "获取会话趋势数据成功"
            })
        else:
            return jsonify({
                "code": 500,
                "message": f"获取会话趋势数据失败: {result}"
            }), 500

    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"获取会话趋势数据失败: {str(e)}"
        }), 500


@dashboard_bp.route('/ranking/assistants', methods=['GET'])
@require_superuser
def assistant_ranking():
    """获取最受欢迎的AI助教排行榜"""
    try:
        current_user = get_current_user()
        tenant_id = current_user["user_id"]
        limit = int(request.args.get('limit', 10))
        time_range = request.args.get('range', '24h')

        # 获取助教排行榜数据
        success, result = get_assistant_ranking(tenant_id, limit, time_range)

        if success:
            return jsonify({
                "code": 0,
                "data": result,
                "message": "获取助教排行榜数据成功"
            })
        else:
            return jsonify({
                "code": 500,
                "message": f"获取助教排行榜数据失败: {result}"
            }), 500

    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"获取助教排行榜数据失败: {str(e)}"
        }), 500


@dashboard_bp.route('/ranking/classes', methods=['GET'])
@require_superuser
def class_activity_ranking():
    """获取班级活跃度排行榜"""
    try:
        current_user = get_current_user()
        tenant_id = current_user["user_id"]
        limit = int(request.args.get('limit', 10))
        time_range = request.args.get('range', '24h')

        # 获取班级活跃度排行榜数据
        success, result = get_class_activity_ranking(tenant_id, limit, time_range)

        if success:
            return jsonify({
                "code": 0,
                "data": result,
                "message": "获取班级活跃度排行榜数据成功"
            })
        else:
            return jsonify({
                "code": 500,
                "message": f"获取班级活跃度排行榜数据失败: {result}"
            }), 500

    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"获取班级活跃度排行榜数据失败: {str(e)}"
        }), 500


@dashboard_bp.route('/all', methods=['GET'])
@require_superuser
def dashboard_all():
    """一次性获取所有dashboard数据"""
    try:
        current_user = get_current_user()
        tenant_id = current_user["user_id"]
        time_range = request.args.get('range', '24h')
        limit = int(request.args.get('limit', 10))

        # 获取所有数据
        result = {}

        # 1. 概览数据
        success, overview = get_dashboard_overview(tenant_id)
        if success:
            result["overview"] = overview
        else:
            result["overview"] = None

        # 2. 活跃学生趋势
        success, active_students = get_active_students_chart(tenant_id, time_range)
        if success:
            result["active_students"] = active_students
        else:
            result["active_students"] = []

        # 3. 会话趋势
        success, conversation_trend = get_conversation_trend_chart(tenant_id, time_range)
        if success:
            result["conversation_trend"] = conversation_trend
        else:
            result["conversation_trend"] = []

        # 4. 助教排行榜
        success, assistant_rank = get_assistant_ranking(tenant_id, limit, time_range)
        if success:
            result["assistant_ranking"] = assistant_rank
        else:
            result["assistant_ranking"] = []

        # 5. 班级活跃度排行榜
        success, class_rank = get_class_activity_ranking(tenant_id, limit, time_range)
        if success:
            result["class_ranking"] = class_rank
        else:
            result["class_ranking"] = []

        return jsonify({
            "code": 0,
            "data": result,
            "message": "获取dashboard数据成功"
        })

    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"获取dashboard数据失败: {str(e)}"
        }), 500


@dashboard_bp.route('/learning-insights', methods=['GET'])
@require_superuser
def learning_insights():
    """获取教师所带学生的答题、提问和高频错题概览。"""
    try:
        current_user = get_current_user()
        success, result = get_learning_insights(
            tenant_id=current_user["user_id"],
            time_range=request.args.get('range', '7d'),
            class_id=request.args.get('class_id', '').strip(),
            limit=min(max(int(request.args.get('limit', 10)), 1), 50),
        )
        if success:
            return jsonify({"code": 0, "data": result, "message": "获取学习洞察成功"})
        return jsonify({"code": 500, "message": f"获取学习洞察失败: {result}"}), 500
    except ValueError:
        return jsonify({"code": 400, "message": "limit 必须是正整数"}), 400
    except Exception as error:
        return jsonify({"code": 500, "message": f"获取学习洞察失败: {error}"}), 500


@dashboard_bp.route('/students/<student_id>/learning-detail', methods=['GET'])
@require_superuser
def student_learning_detail(student_id):
    """获取当前老师名下一名学生的逐题记录和提问内容。"""
    try:
        current_user = get_current_user()
        success, result = get_student_learning_detail(
            tenant_id=current_user["user_id"],
            student_id=student_id,
            time_range=request.args.get('range', '7d'),
        )
        if success:
            return jsonify({"code": 0, "data": result, "message": "获取学生学习明细成功"})
        status = 404 if result == "学生不存在或不属于当前老师" else 500
        return jsonify({"code": status, "message": result}), status
    except Exception as error:
        return jsonify({"code": 500, "message": f"获取学生学习明细失败: {error}"}), 500
