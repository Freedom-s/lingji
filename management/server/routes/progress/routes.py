from flask import jsonify, request
from services.progress.service import (
    get_weekly_progress_list,
    create_weekly_progress,
    update_weekly_progress,
    delete_weekly_progress,
    get_class_documents,
    get_progress_status,
    refresh_progress_status,
)
from routes import progress_bp
from auth import require_superuser


@progress_bp.route('/<string:class_id>', methods=['GET'])
@require_superuser
def list_progress(class_id):
    try:
        data = get_weekly_progress_list(class_id)
        return jsonify({"code": 0, "data": data, "message": "获取周进度列表成功"})
    except Exception as e:
        return jsonify({"code": 500, "message": f"获取周进度列表失败: {str(e)}"}), 500


@progress_bp.route('/<string:class_id>', methods=['POST'])
@require_superuser
def create_progress(class_id):
    try:
        data = request.json
        if not data:
            return jsonify({"code": 400, "message": "请求体不能为空"}), 400
        success, result = create_weekly_progress(class_id, data)
        if success:
            return jsonify({"code": 0, "data": {"id": result}, "message": "创建周进度成功"})
        return jsonify({"code": 400, "message": result}), 400
    except Exception as e:
        return jsonify({"code": 500, "message": f"创建周进度失败: {str(e)}"}), 500


@progress_bp.route('/detail/<string:progress_id>', methods=['PUT'])
@require_superuser
def edit_progress(progress_id):
    try:
        data = request.json
        if not data:
            return jsonify({"code": 400, "message": "请求体不能为空"}), 400
        success, result = update_weekly_progress(progress_id, data)
        if success:
            return jsonify({"code": 0, "data": None, "message": result})
        return jsonify({"code": 400, "message": result}), 400
    except Exception as e:
        return jsonify({"code": 500, "message": f"修改周进度失败: {str(e)}"}), 500


@progress_bp.route('/detail/<string:progress_id>', methods=['DELETE'])
@require_superuser
def remove_progress(progress_id):
    try:
        success, result = delete_weekly_progress(progress_id)
        if success:
            return jsonify({"code": 0, "data": None, "message": result})
        return jsonify({"code": 400, "message": result}), 400
    except Exception as e:
        return jsonify({"code": 500, "message": f"删除周进度失败: {str(e)}"}), 500


@progress_bp.route('/docs/<string:class_id>', methods=['GET'])
@require_superuser
def list_docs(class_id):
    try:
        docs = get_class_documents(class_id)
        return jsonify({"code": 0, "data": docs, "message": "获取文档列表成功"})
    except Exception as e:
        return jsonify({"code": 500, "message": f"获取文档列表失败: {str(e)}"}), 500


@progress_bp.route('/status/<string:progress_id>', methods=['GET'])
@require_superuser
def get_status(progress_id):
    try:
        success, result = get_progress_status(progress_id)
        if success:
            return jsonify({"code": 0, "data": result, "message": "获取完成状态成功"})
        return jsonify({"code": 400, "message": result}), 400
    except Exception as e:
        return jsonify({"code": 500, "message": f"获取完成状态失败: {str(e)}"}), 500


@progress_bp.route('/refresh/<string:progress_id>', methods=['POST'])
@require_superuser
def refresh_status(progress_id):
    try:
        success, result = refresh_progress_status(progress_id)
        if success:
            return jsonify({"code": 0, "data": None, "message": result})
        return jsonify({"code": 400, "message": result}), 400
    except Exception as e:
        return jsonify({"code": 500, "message": f"刷新状态失败: {str(e)}"}), 500
