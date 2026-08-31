from io import BytesIO

from flask import jsonify, request, send_file
from services.scores.service import (
    get_scoring_config,
    save_scoring_config,
    get_external_sources,
    create_external_source,
    update_external_source,
    delete_external_source,
    get_external_records,
    get_external_template_context,
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

@scoring_bp.route('/external-record/template/<string:source_id>', methods=['GET'])
@require_superuser
def download_external_template(source_id):
    """按数据源所属班级生成预填学生花名册的 Excel 模板。"""
    try:
        success, result = get_external_template_context(source_id)
        if not success:
            return jsonify({"code": 400, "message": result}), 400

        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.worksheet.datavalidation import DataValidation

        source = result["source"]
        students = result["students"]

        def safe_excel_text(value):
            text = str(value or "")
            return f"'{text}" if text.startswith(("=", "+", "-", "@")) else text

        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        worksheet.title = "成绩导入"
        worksheet.append(["系统学生ID", "学生姓名", "登录邮箱", "得分"])
        for student in students:
            worksheet.append([
                student["id"],
                safe_excel_text(student.get("nickname")),
                safe_excel_text(student.get("email")),
                None,
            ])

        header_fill = PatternFill("solid", fgColor="1F4E78")
        score_fill = PatternFill("solid", fgColor="FFF2CC")
        for cell in worksheet[1]:
            cell.fill = header_fill
            cell.font = Font(color="FFFFFF", bold=True)
            cell.alignment = Alignment(horizontal="center", vertical="center")
        for row_number in range(2, max(len(students) + 2, 3)):
            worksheet.cell(row=row_number, column=4).fill = score_fill

        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = f"A1:D{max(len(students) + 1, 1)}"
        worksheet.column_dimensions["A"].width = 36
        worksheet.column_dimensions["B"].width = 18
        worksheet.column_dimensions["C"].width = 32
        worksheet.column_dimensions["D"].width = 14
        worksheet.row_dimensions[1].height = 24

        max_score = float(source["max_score"])
        validation = DataValidation(
            type="decimal",
            operator="between",
            formula1="0",
            formula2=str(max_score),
            allow_blank=True,
        )
        validation.error = f"得分必须在 0 至 {max_score:g} 之间"
        validation.errorTitle = "得分无效"
        validation.prompt = f"请填写 0 至 {max_score:g} 之间的得分"
        validation.promptTitle = "填写得分"
        validation.showErrorMessage = True
        validation.showInputMessage = True
        worksheet.add_data_validation(validation)
        validation.add(f"D2:D{max(len(students) + 1, 2)}")

        instructions = workbook.create_sheet("填写说明")
        instructions.append(["项目", "内容"])
        instructions.append(["班级", source["class_name"]])
        instructions.append(["数据源", source["source_name"]])
        instructions.append(["满分", source["max_score"]])
        instructions.append(["填写要求", "只填写“得分”列，请勿修改系统学生ID、姓名和登录邮箱。"])
        instructions.append(["空白成绩", "得分为空的学生不会导入，也不会覆盖已有成绩。"])
        instructions.column_dimensions["A"].width = 16
        instructions.column_dimensions["B"].width = 72
        for cell in instructions[1]:
            cell.fill = header_fill
            cell.font = Font(color="FFFFFF", bold=True)

        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        return send_file(
            output,
            as_attachment=True,
            download_name="外部成绩导入模板.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        return jsonify({"code": 500, "message": f"生成成绩模板失败: {str(e)}"}), 500


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
            student_id_col = header.index("系统学生ID")
            score_col = header.index("得分")
        except ValueError:
            return jsonify({"code": 400, "message": "请使用系统下载的模板，表头必须包含「系统学生ID」和「得分」列"}), 400

        # 解析数据行
        records = []
        for row_number, row in enumerate(rows[1:], start=2):
            if not row or len(row) <= max(student_id_col, score_col):
                continue
            sid = str(row[student_id_col]).strip() if row[student_id_col] is not None else ""
            if row[score_col] is None or str(row[score_col]).strip() == "":
                continue
            try:
                score = float(row[score_col])
            except (ValueError, TypeError):
                return jsonify({"code": 400, "message": f"第 {row_number} 行的得分不是有效数字"}), 400
            if sid:
                records.append({"student_id": sid, "score": score, "row_number": row_number})

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
