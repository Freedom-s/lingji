from flask import jsonify, request
from services.scores.service import (
    get_scoring_config,
    save_scoring_config,
    get_external_sources,
    create_external_source,
    update_external_source,
    delete_external_source,
    get_external_records,
    upsert_external_records,
    update_external_record,
    calculate_class_scores,
    calculate_student_score,
)
from routes import scoring_bp
from auth import require_superuser


# ========== 评分配置 ==========

@scoring_bp.route('/config/<string:class_id>', methods=['GET'])
@require_superuser
def get_config(class_id):
    try:
        success, result = get_scoring_config(class_id)
        if success:
            return jsonify({"code": 0, "data": result, "message": "获取评分配置成功"})
        else:
            return jsonify({"code": 400, "message": result}), 400
    except Exception as e:
        return jsonify({"code": 500, "message": f"获取评分配置失败: {str(e)}"}), 500


@scoring_bp.route('/config/<string:class_id>', methods=['PUT'])
@require_superuser
def update_config(class_id):
    try:
        data = request.json
        if not data:
            return jsonify({"code": 400, "message": "请求体不能为空"}), 400
        success, result = save_scoring_config(class_id, data)
        if success:
            return jsonify({"code": 0, "data": None, "message": result})
        else:
            return jsonify({"code": 400, "message": result}), 400
    except Exception as e:
        return jsonify({"code": 500, "message": f"保存评分配置失败: {str(e)}"}), 500


# ========== 外部数据源 ==========

@scoring_bp.route('/external-source/<string:class_id>', methods=['GET'])
@require_superuser
def list_external_sources(class_id):
    try:
        sources = get_external_sources(class_id)
        return jsonify({"code": 0, "data": sources, "message": "获取外部数据源列表成功"})
    except Exception as e:
        return jsonify({"code": 500, "message": f"获取外部数据源列表失败: {str(e)}"}), 500


@scoring_bp.route('/external-source', methods=['POST'])
@require_superuser
def add_external_source():
    try:
        data = request.json
        if not data:
            return jsonify({"code": 400, "message": "请求体不能为空"}), 400
        class_id = data.get("class_id", "")
        source_name = data.get("source_name", "")
        max_score = data.get("max_score", 0)
        success, result = create_external_source(class_id, source_name, max_score)
        if success:
            return jsonify({"code": 0, "data": {"id": result}, "message": "创建外部数据源成功"})
        else:
            return jsonify({"code": 400, "message": result}), 400
    except Exception as e:
        return jsonify({"code": 500, "message": f"创建外部数据源失败: {str(e)}"}), 500


@scoring_bp.route('/external-source/<string:source_id>', methods=['PUT'])
@require_superuser
def edit_external_source(source_id):
    try:
        data = request.json
        if not data:
            return jsonify({"code": 400, "message": "请求体不能为空"}), 400
        source_name = data.get("source_name", "")
        max_score = data.get("max_score", 0)
        success, result = update_external_source(source_id, source_name, max_score)
        if success:
            return jsonify({"code": 0, "data": None, "message": result})
        else:
            return jsonify({"code": 400, "message": result}), 400
    except Exception as e:
        return jsonify({"code": 500, "message": f"修改外部数据源失败: {str(e)}"}), 500


@scoring_bp.route('/external-source/<string:source_id>', methods=['DELETE'])
@require_superuser
def remove_external_source(source_id):
    try:
        success, result = delete_external_source(source_id)
        if success:
            return jsonify({"code": 0, "data": None, "message": result})
        else:
            return jsonify({"code": 400, "message": result}), 400
    except Exception as e:
        return jsonify({"code": 500, "message": f"删除外部数据源失败: {str(e)}"}), 500


# ========== 外部评分记录 ==========

@scoring_bp.route('/external-record/<string:source_id>', methods=['GET'])
@require_superuser
def list_external_records(source_id):
    try:
        records = get_external_records(source_id)
        return jsonify({"code": 0, "data": records, "message": "获取外部评分记录成功"})
    except Exception as e:
        return jsonify({"code": 500, "message": f"获取外部评分记录失败: {str(e)}"}), 500


@scoring_bp.route('/external-record/upload', methods=['POST'])
@require_superuser
def upload_external_records():
    try:
        source_id = request.form.get("source_id", "")
        if not source_id:
            return jsonify({"code": 400, "message": "缺少 source_id"}), 400

        file = request.files.get("file")
        if not file:
            return jsonify({"code": 400, "message": "请上传文件"}), 400

        # 读取 Excel
        try:
            import openpyxl
            wb = openpyxl.load_workbook(file, read_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
        except Exception as e:
            return jsonify({"code": 400, "message": f"解析 Excel 失败: {str(e)}"}), 400

        if len(rows) < 2:
            return jsonify({"code": 400, "message": "Excel 至少需要包含表头行和一行数据"}), 400

        # 解析表头
        header = [str(c).strip() if c else "" for c in rows[0]]
        try:
            student_id_col = header.index("学号")
            score_col = header.index("得分")
        except ValueError:
            return jsonify({"code": 400, "message": "Excel 表头必须包含「学号」和「得分」列"}), 400

        # 解析数据行
        records = []
        for row in rows[1:]:
            if not row or len(row) <= max(student_id_col, score_col):
                continue
            sid = str(row[student_id_col]).strip() if row[student_id_col] is not None else ""
            try:
                score = float(row[score_col]) if row[score_col] is not None else 0
            except (ValueError, TypeError):
                continue
            if sid:
                records.append({"student_id": sid, "score": score})

        if not records:
            return jsonify({"code": 400, "message": "没有解析到有效数据"}), 400

        success, result = upsert_external_records(source_id, records)
        if success:
            return jsonify({"code": 0, "data": None, "message": result})
        else:
            return jsonify({"code": 400, "message": result}), 400

    except Exception as e:
        return jsonify({"code": 500, "message": f"上传评分数据失败: {str(e)}"}), 500


@scoring_bp.route('/external-record/<string:record_id>', methods=['PUT'])
@require_superuser
def edit_external_record(record_id):
    try:
        data = request.json
        if not data:
            return jsonify({"code": 400, "message": "请求体不能为空"}), 400
        score = data.get("score")
        if score is None:
            return jsonify({"code": 400, "message": "缺少 score"}), 400
        success, result = update_external_record(record_id, float(score))
        if success:
            return jsonify({"code": 0, "data": None, "message": result})
        else:
            return jsonify({"code": 400, "message": result}), 400
    except Exception as e:
        return jsonify({"code": 500, "message": f"修改评分记录失败: {str(e)}"}), 500


# ========== 评分结果 ==========

@scoring_bp.route('/result/<string:class_id>', methods=['GET'])
@require_superuser
def get_class_scores(class_id):
    try:
        success, result = calculate_class_scores(class_id)
        if success:
            return jsonify({"code": 0, "data": result, "message": "获取评分结果成功"})
        else:
            return jsonify({"code": 400, "message": result}), 400
    except Exception as e:
        return jsonify({"code": 500, "message": f"获取评分结果失败: {str(e)}"}), 500


@scoring_bp.route('/result/<string:class_id>/<string:student_id>', methods=['GET'])
@require_superuser
def get_student_score(class_id, student_id):
    try:
        success, result = calculate_student_score(class_id, student_id)
        if success:
            return jsonify({"code": 0, "data": result, "message": "获取学生评分成功"})
        else:
            return jsonify({"code": 400, "message": result}), 400
    except Exception as e:
        return jsonify({"code": 500, "message": f"获取学生评分失败: {str(e)}"}), 500
