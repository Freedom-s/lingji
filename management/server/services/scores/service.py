import json
import mysql.connector
import pytz
from datetime import datetime
from utils import generate_uuid
from database import DB_CONFIG
from auth import get_current_user


def _get_utc8_time():
    """返回 (create_time_ms, create_date_str) UTC+8"""
    utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
    target_tz = pytz.timezone('Asia/Shanghai')
    local_dt = utc_now.astimezone(target_tz)
    return int(local_dt.timestamp() * 1000), local_dt.strftime("%Y-%m-%d %H:%M:%S")


def get_scoring_config(class_id):
    """获取班级的评分配置，不存在则返回默认等权配置"""
    try:
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"
        user_id = current_user["user_id"]

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 校验班级归属
        check_query = "SELECT id FROM class WHERE id = %s AND tenant_id = %s"
        cursor.execute(check_query, (class_id, user_id))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return False, "班级不存在或无权操作"

        query = "SELECT * FROM scoring_config WHERE class_id = %s"
        cursor.execute(query, (class_id,))
        row = cursor.fetchone()

        cursor.close()
        conn.close()

        if row:
            # 转换 Decimal/timedelta 等非 JSON 兼容类型
            config = {
                "id": row["id"],
                "class_id": row["class_id"],
                "video_enabled": bool(row["video_enabled"]),
                "video_weight": row["video_weight"],
                "quiz_enabled": bool(row["quiz_enabled"]),
                "quiz_weight": row["quiz_weight"],
                "note_enabled": bool(row["note_enabled"]),
                "note_weight": row["note_weight"],
                "flashcard_enabled": bool(row["flashcard_enabled"]),
                "flashcard_weight": row["flashcard_weight"],
                "qa_enabled": bool(row["qa_enabled"]),
                "qa_weight": row["qa_weight"],
                "external_enabled": bool(row["external_enabled"]),
                "external_weight": row["external_weight"],
            }
            return True, config
        else:
            # 返回默认配置：全部启用，均分权重
            default_weights = {
                "video": 20, "quiz": 20, "note": 20,
                "flashcard": 20, "qa": 20, "external": 0
            }
            config = {
                "id": None,
                "class_id": class_id,
                "video_enabled": True, "video_weight": default_weights["video"],
                "quiz_enabled": True, "quiz_weight": default_weights["quiz"],
                "note_enabled": True, "note_weight": default_weights["note"],
                "flashcard_enabled": True, "flashcard_weight": default_weights["flashcard"],
                "qa_enabled": True, "qa_weight": default_weights["qa"],
                "external_enabled": False, "external_weight": 0,
            }
            return True, config

    except mysql.connector.Error as err:
        print(f"获取评分配置失败: {err}")
        return False, str(err)


def save_scoring_config(class_id, data):
    """保存/更新班级评分配置，校验权重之和=100"""
    try:
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"
        user_id = current_user["user_id"]

        # 校验班级归属
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        check_query = "SELECT id FROM class WHERE id = %s AND tenant_id = %s"
        cursor.execute(check_query, (class_id, user_id))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return False, "班级不存在或无权操作"

        # 校验权重：启用维度之和 = 100
        dimensions = ["video", "quiz", "note", "flashcard", "qa", "external"]
        total_weight = 0
        for dim in dimensions:
            if data.get(f"{dim}_enabled", False):
                total_weight += int(data.get(f"{dim}_weight", 0))

        if total_weight != 100:
            cursor.close()
            conn.close()
            return False, f"启用的维度权重之和必须等于 100，当前为 {total_weight}"

        # Upsert
        ct_ms, ct_date = _get_utc8_time()
        existing = None
        cursor.execute("SELECT id FROM scoring_config WHERE class_id = %s", (class_id,))
        existing = cursor.fetchone()

        if existing:
            # Update
            set_clauses = []
            params = []
            for dim in dimensions:
                set_clauses.append(f"{dim}_enabled = %s")
                params.append(1 if data.get(f"{dim}_enabled") else 0)
                set_clauses.append(f"{dim}_weight = %s")
                params.append(int(data.get(f"{dim}_weight", 0)))
            set_clauses.append("update_time = %s")
            params.append(ct_ms)
            set_clauses.append("update_date = %s")
            params.append(ct_date)
            params.append(class_id)

            update_query = f"UPDATE scoring_config SET {', '.join(set_clauses)} WHERE class_id = %s"
            cursor.execute(update_query, params)
        else:
            # Insert
            config_id = generate_uuid()
            columns = ["id", "class_id", "create_time", "create_date", "update_time", "update_date"]
            values = [config_id, class_id, ct_ms, ct_date, ct_ms, ct_date]
            for dim in dimensions:
                columns.append(f"{dim}_enabled")
                values.append(1 if data.get(f"{dim}_enabled") else 0)
                columns.append(f"{dim}_weight")
                values.append(int(data.get(f"{dim}_weight", 0)))

            placeholders = ", ".join(["%s"] * len(values))
            insert_query = f"INSERT INTO scoring_config ({', '.join(columns)}) VALUES ({placeholders})"
            cursor.execute(insert_query, values)

        conn.commit()
        cursor.close()
        conn.close()
        return True, "保存成功"

    except mysql.connector.Error as err:
        print(f"保存评分配置失败: {err}")
        return False, str(err)


def get_external_sources(class_id):
    """获取班级的所有外部数据源"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, class_id, source_name, max_score, create_date FROM external_score_source WHERE class_id = %s ORDER BY create_date",
            (class_id,)
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except mysql.connector.Error as err:
        print(f"获取外部数据源失败: {err}")
        return []


def create_external_source(class_id, source_name, max_score):
    """新增外部数据源"""
    try:
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"
        user_id = current_user["user_id"]

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 校验班级归属
        check_query = "SELECT id FROM class WHERE id = %s AND tenant_id = %s"
        cursor.execute(check_query, (class_id, user_id))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return False, "班级不存在或无权操作"

        if not source_name or not source_name.strip():
            cursor.close()
            conn.close()
            return False, "数据源名称不能为空"

        if max_score <= 0:
            cursor.close()
            conn.close()
            return False, "满分值必须大于 0"

        source_id = generate_uuid()
        ct_ms, ct_date = _get_utc8_time()

        cursor.execute(
            "INSERT INTO external_score_source (id, class_id, source_name, max_score, create_time, create_date, update_time, update_date) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (source_id, class_id, source_name.strip(), max_score, ct_ms, ct_date, ct_ms, ct_date)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True, source_id

    except mysql.connector.Error as err:
        print(f"创建外部数据源失败: {err}")
        return False, str(err)


def update_external_source(source_id, source_name, max_score):
    """修改外部数据源"""
    try:
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"
        user_id = current_user["user_id"]

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 校验所有权：source → class → tenant
        check_query = """
            SELECT ess.id FROM external_score_source ess
            JOIN class c ON ess.class_id = c.id
            WHERE ess.id = %s AND c.tenant_id = %s
        """
        cursor.execute(check_query, (source_id, user_id))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return False, "数据源不存在或无权操作"

        ct_ms, ct_date = _get_utc8_time()
        cursor.execute(
            "UPDATE external_score_source SET source_name = %s, max_score = %s, update_time = %s, update_date = %s WHERE id = %s",
            (source_name.strip(), max_score, ct_ms, ct_date, source_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True, "修改成功"

    except mysql.connector.Error as err:
        print(f"修改外部数据源失败: {err}")
        return False, str(err)


def delete_external_source(source_id):
    """删除外部数据源，级联删除关联记录"""
    try:
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"
        user_id = current_user["user_id"]

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        check_query = """
            SELECT ess.id FROM external_score_source ess
            JOIN class c ON ess.class_id = c.id
            WHERE ess.id = %s AND c.tenant_id = %s
        """
        cursor.execute(check_query, (source_id, user_id))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return False, "数据源不存在或无权操作"

        # 级联删除
        cursor.execute("DELETE FROM external_score_record WHERE source_id = %s", (source_id,))
        cursor.execute("DELETE FROM external_score_source WHERE id = %s", (source_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "删除成功"

    except mysql.connector.Error as err:
        print(f"删除外部数据源失败: {err}")
        return False, str(err)


def get_external_records(source_id):
    """获取某数据源下所有学生的成绩，join user 获取姓名"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT esr.id, esr.student_id, u.nickname AS student_name, esr.score, esr.create_date
            FROM external_score_record esr
            JOIN user u ON esr.student_id = u.id
            WHERE esr.source_id = %s
            ORDER BY esr.score DESC
        """, (source_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except mysql.connector.Error as err:
        print(f"获取外部评分记录失败: {err}")
        return []


def upsert_external_records(source_id, records):
    """批量 upsert 外部评分记录
    records: [{"student_id": "xxx", "score": 85.5}, ...]
    """
    try:
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"
        user_id = current_user["user_id"]

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 校验数据源归属
        check_query = """
            SELECT ess.id, ess.class_id FROM external_score_source ess
            JOIN class c ON ess.class_id = c.id
            WHERE ess.id = %s AND c.tenant_id = %s
        """
        cursor.execute(check_query, (source_id, user_id))
        source_row = cursor.fetchone()
        if not source_row:
            cursor.close()
            conn.close()
            return False, "数据源不存在或无权操作"

        if not records:
            cursor.close()
            conn.close()
            return False, "没有要导入的数据"

        ct_ms, ct_date = _get_utc8_time()
        inserted = 0
        updated = 0

        for rec in records:
            sid = rec.get("student_id", "").strip()
            score = rec.get("score", 0)
            if not sid:
                continue

            cursor.execute(
                "SELECT id FROM external_score_record WHERE source_id = %s AND student_id = %s",
                (source_id, sid)
            )
            existing = cursor.fetchone()
            if existing:
                cursor.execute(
                    "UPDATE external_score_record SET score = %s, update_time = %s, update_date = %s WHERE id = %s",
                    (score, ct_ms, ct_date, existing["id"])
                )
                updated += 1
            else:
                record_id = generate_uuid()
                cursor.execute(
                    "INSERT INTO external_score_record (id, source_id, student_id, score, create_time, create_date, update_time, update_date) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (record_id, source_id, sid, score, ct_ms, ct_date, ct_ms, ct_date)
                )
                inserted += 1

        conn.commit()
        cursor.close()
        conn.close()
        return True, f"导入完成：新增 {inserted} 条，更新 {updated} 条"

    except mysql.connector.Error as err:
        print(f"导入外部评分记录失败: {err}")
        return False, str(err)


def update_external_record(record_id, score):
    """手动修改单条外部评分记录"""
    try:
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"
        user_id = current_user["user_id"]

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 校验所有权链路：record → source → class → tenant
        check_query = """
            SELECT esr.id FROM external_score_record esr
            JOIN external_score_source ess ON esr.source_id = ess.id
            JOIN class c ON ess.class_id = c.id
            WHERE esr.id = %s AND c.tenant_id = %s
        """
        cursor.execute(check_query, (record_id, user_id))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return False, "记录不存在或无权操作"

        ct_ms, ct_date = _get_utc8_time()
        cursor.execute(
            "UPDATE external_score_record SET score = %s, update_time = %s, update_date = %s WHERE id = %s",
            (score, ct_ms, ct_date, record_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True, "修改成功"

    except mysql.connector.Error as err:
        print(f"修改外部评分记录失败: {err}")
        return False, str(err)


def _get_class_doc_ids_and_dialog_ids(class_id):
    """获取班级关联的所有文档 ID 和 dialog ID 集合
    Returns: (doc_rows: list of dict, dialog_ids: list)
    """
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    # Step 1: 获取班级关联的 dialog_ids
    cursor.execute("SELECT dialog_id FROM class_dialog WHERE class_id = %s", (class_id,))
    dialog_rows = cursor.fetchall()
    dialog_ids = [r["dialog_id"] for r in dialog_rows]

    if not dialog_ids:
        cursor.close()
        conn.close()
        return [], []

    # Step 2: 获取 dialog 的 kb_ids
    placeholders = ", ".join(["%s"] * len(dialog_ids))
    cursor.execute(
        f"SELECT id, kb_ids FROM dialog WHERE id IN ({placeholders})",
        dialog_ids
    )
    dialog_rows = cursor.fetchall()

    # Step 3: 解析 kb_ids JSON 数组，收集所有 kb_id
    kb_id_set = set()
    for row in dialog_rows:
        kb_ids = row.get("kb_ids")
        if kb_ids:
            if isinstance(kb_ids, str):
                try:
                    kb_ids = json.loads(kb_ids)
                except (json.JSONDecodeError, TypeError):
                    kb_ids = []
            if isinstance(kb_ids, list):
                for kb_id in kb_ids:
                    if kb_id:
                        kb_id_set.add(kb_id)

    if not kb_id_set:
        cursor.close()
        conn.close()
        return [], dialog_ids

    # Step 4: 获取这些 kb 下的所有 valid 文档
    kb_placeholders = ", ".join(["%s"] * len(kb_id_set))
    cursor.execute(
        f"SELECT id, type, chunk_num FROM document WHERE kb_id IN ({kb_placeholders}) AND status = '1'",
        list(kb_id_set)
    )
    doc_rows = cursor.fetchall()

    cursor.close()
    conn.close()
    return doc_rows, dialog_ids  # 返回文档详情列表 + dialog_ids


def _get_class_students(class_id):
    """获取班级学生列表"""
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT u.id, u.nickname, u.email
        FROM user u
        JOIN user_class uc ON u.id = uc.user_id
        WHERE uc.class_id = %s AND uc.role = 'student' AND uc.status = '1'
        ORDER BY u.nickname
    """, (class_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def _calc_video_score(student_id, doc_ids, video_doc_ids):
    """视频维度: 完成率 = 完成数 / 总视频数 × 100"""
    if not video_doc_ids:
        return 0.0
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    placeholders = ", ".join(["%s"] * len(video_doc_ids))
    cursor.execute(
        f"SELECT COUNT(*) as cnt, SUM(is_completed) as completed FROM student_video_progress WHERE student_id = %s AND doc_id IN ({placeholders})",
        [student_id] + video_doc_ids
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    total = len(video_doc_ids)
    completed = int(row["completed"] or 0) if row else 0
    return round(completed / total * 100, 1)


def _calc_quiz_score(student_id, doc_ids):
    """测验维度: 正确率 = 正确数 / 总答题数 × 100"""
    if not doc_ids:
        return 0.0
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    placeholders = ", ".join(["%s"] * len(doc_ids))
    cursor.execute(
        f"SELECT COUNT(*) as cnt, SUM(is_correct) as correct FROM student_quiz_result WHERE student_id = %s AND doc_id IN ({placeholders})",
        [student_id] + doc_ids
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    total = int(row["cnt"] or 0) if row else 0
    if total == 0:
        return 0.0
    correct = int(row["correct"] or 0)
    return round(correct / total * 100, 1)


def _calc_note_score(student_id, doc_ids, doc_page_map):
    """笔记维度: 覆盖率 = 有笔记的页面数 / 文档总页面数 × 100"""
    if not doc_ids:
        return 0.0
    total_pages = sum(doc_page_map.get(did, 0) for did in doc_ids)
    if total_pages == 0:
        return 0.0
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    placeholders = ", ".join(["%s"] * len(doc_ids))
    cursor.execute(
        f"SELECT COUNT(DISTINCT CONCAT(doc_id, '-', page_number)) as cnt FROM student_note WHERE student_id = %s AND doc_id IN ({placeholders})",
        [student_id] + doc_ids
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    noted_pages = int(row["cnt"] or 0) if row else 0
    return round(min(noted_pages / total_pages, 1.0) * 100, 1)


def _calc_flashcard_score(student_id, doc_ids, doc_flashcard_map):
    """概念速记维度: 记忆率 = 记住的卡片数 / 总卡片数 × 100"""
    relevant_docs = [did for did in doc_ids if doc_flashcard_map.get(did, 0) > 0]
    if not relevant_docs:
        return 0.0
    total_cards = sum(doc_flashcard_map.get(did, 0) for did in relevant_docs)
    if total_cards == 0:
        return 0.0
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    placeholders = ", ".join(["%s"] * len(relevant_docs))
    cursor.execute(
        f"SELECT COUNT(*) as cnt FROM student_card_progress WHERE student_id = %s AND doc_id IN ({placeholders}) AND status = 'remembered'",
        [student_id] + relevant_docs
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    remembered = int(row["cnt"] or 0) if row else 0
    return round(remembered / total_cards * 100, 1)


def _calc_qa_score(student_id, dialog_ids):
    """问答活跃度: min(会话数 / 10 × 100, 100)"""
    if not dialog_ids:
        return 0.0
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    placeholders = ", ".join(["%s"] * len(dialog_ids))
    cursor.execute(
        f"SELECT COUNT(*) as cnt FROM conversation WHERE user_id = %s AND dialog_id IN ({placeholders})",
        [student_id] + dialog_ids
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    msg_count = int(row["cnt"] or 0) if row else 0
    return round(min(msg_count / 10 * 100, 100), 1)


def _calc_external_score(student_id, class_id):
    """外部导入维度: 各源归一化分取平均"""
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT ess.id, ess.max_score, esr.score
        FROM external_score_source ess
        LEFT JOIN external_score_record esr ON ess.id = esr.source_id AND esr.student_id = %s
        WHERE ess.class_id = %s
    """, (student_id, class_id))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        return 0.0

    normalized_scores = []
    for row in rows:
        if row["score"] is not None and row["max_score"] > 0:
            normalized_scores.append(min(row["score"] / row["max_score"] * 100, 100))

    if not normalized_scores:
        return 0.0
    return round(sum(normalized_scores) / len(normalized_scores), 1)


def _get_doc_metadata(doc_rows):
    """从文档列表提取元数据
    Returns: (doc_ids, video_doc_ids, doc_page_map, doc_flashcard_map)
    """
    doc_ids = []
    video_doc_ids = []
    doc_page_map = {}      # doc_id → total pages
    doc_flashcard_map = {}  # doc_id → total flashcards

    for row in doc_rows:
        did = row["id"]
        doc_ids.append(did)
        doc_page_map[did] = row.get("chunk_num", 0) or 0
        if row.get("type") == "video":
            video_doc_ids.append(did)

    # 查询文档的闪卡总数
    if doc_ids:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        placeholders = ", ".join(["%s"] * len(doc_ids))
        cursor.execute(
            f"SELECT doc_id, content FROM document_generation WHERE doc_id IN ({placeholders}) AND generation_type = 'flashcards'",
            doc_ids
        )
        for row in cursor.fetchall():
            try:
                content = json.loads(row["content"]) if isinstance(row["content"], str) else row["content"]
                doc_flashcard_map[row["doc_id"]] = len(content) if isinstance(content, list) else 0
            except (json.JSONDecodeError, TypeError):
                doc_flashcard_map[row["doc_id"]] = 0
        cursor.close()
        conn.close()

    # 未查询到的文档闪卡数默认为 0
    for did in doc_ids:
        if did not in doc_flashcard_map:
            doc_flashcard_map[did] = 0

    return doc_ids, video_doc_ids, doc_page_map, doc_flashcard_map


def calculate_class_scores(class_id):
    """计算整个班级的学生评分总表"""
    try:
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"
        # 用户认证和班级归属校验由 get_scoring_config 隐式完成

        # 1. 获取评分配置
        success, config = get_scoring_config(class_id)
        if not success:
            return False, config

        # 2. 获取学生列表
        students = _get_class_students(class_id)
        if not students:
            return True, {
                "class_id": class_id,
                "config": config,
                "students": []
            }

        # 3. 获取文档和 dialog 数据
        doc_rows, dialog_ids = _get_class_doc_ids_and_dialog_ids(class_id)
        doc_ids, video_doc_ids, doc_page_map, doc_flashcard_map = _get_doc_metadata(doc_rows)

        # 4. 逐学生计算各维度得分
        student_results = []
        for student in students:
            sid = student["id"]
            dimensions = {}
            if config["video_enabled"]:
                dimensions["video"] = _calc_video_score(sid, doc_ids, video_doc_ids)
            if config["quiz_enabled"]:
                dimensions["quiz"] = _calc_quiz_score(sid, doc_ids)
            if config["note_enabled"]:
                dimensions["note"] = _calc_note_score(sid, doc_ids, doc_page_map)
            if config["flashcard_enabled"]:
                dimensions["flashcard"] = _calc_flashcard_score(sid, doc_ids, doc_flashcard_map)
            if config["qa_enabled"]:
                dimensions["qa"] = _calc_qa_score(sid, dialog_ids)
            if config["external_enabled"]:
                dimensions["external"] = _calc_external_score(sid, class_id)

            # 计算总分
            total = 0.0
            for dim_key, dim_val in dimensions.items():
                weight = config.get(f"{dim_key}_weight", 0)
                total += dim_val * weight / 100

            student_results.append({
                "student_id": sid,
                "student_name": student.get("nickname", "") or student.get("email", ""),
                "dimensions": dimensions,
                "total_score": round(total, 2)
            })

        # 按总分降序排列
        student_results.sort(key=lambda x: x["total_score"], reverse=True)

        return True, {
            "class_id": class_id,
            "config": config,
            "students": student_results
        }

    except Exception as e:
        print(f"计算班级评分失败: {e}")
        return False, str(e)


def calculate_student_score(class_id, student_id):
    """计算单个学生的评分详情"""
    success, result = calculate_class_scores(class_id)
    if not success:
        return False, result
    for s in result["students"]:
        if s["student_id"] == student_id:
            return True, s
    return False, "学生不在该班级中"
