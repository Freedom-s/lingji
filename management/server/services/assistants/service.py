import mysql.connector
import pytz
import json
from datetime import datetime
from utils import generate_uuid
from database import DB_CONFIG
from auth import get_current_user


def get_assistants_with_pagination(current_page, page_size, assistant_name='', sort_by="create_date", sort_order="desc"):
    """查询助教信息，支持分页和条件筛选"""
    try:
        # 获取当前登录用户ID
        current_user = get_current_user()
        if not current_user:
            return [], 0

        user_id = current_user['user_id']

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 构建WHERE子句和参数 - 查询当前用户的dialog
        where_clauses = ["d.tenant_id = %s"]
        params = [user_id]

        if assistant_name:
            where_clauses.append("d.name LIKE %s")
            params.append(f"%{assistant_name}%")

        where_sql = "WHERE " + " AND ".join(where_clauses)

        # 验证排序字段
        valid_sort_fields = ["name", "create_date", "update_date"]
        if sort_by not in valid_sort_fields:
            sort_by = "create_date"

        sort_clause = f"ORDER BY d.{sort_by} {sort_order.upper()}"

        # 查询总记录数
        count_sql = f"SELECT COUNT(*) as total FROM dialog d {where_sql}"
        cursor.execute(count_sql, params)
        total = cursor.fetchone()['total']

        # 计算分页偏移量
        offset = (current_page - 1) * page_size

        # 执行分页查询，连表查询知识库名称
        query = f"""
        SELECT d.id, d.name, d.description, d.kb_ids, d.create_date, d.update_date, d.status
        FROM dialog d
        {where_sql}
        {sort_clause}
        LIMIT %s OFFSET %s
        """
        cursor.execute(query, params + [page_size, offset])
        results = cursor.fetchall()

        # 格式化结果
        formatted_assistants = []
        for assistant in results:
            # 解析 kb_ids JSON 数组，查询对应的知识库名称
            kb_ids = json.loads(assistant["kb_ids"]) if assistant["kb_ids"] else []
            kb_names = []

            if kb_ids:
                placeholders = ",".join(["%s"] * len(kb_ids))
                kb_query = f"SELECT id, name FROM knowledgebase WHERE id IN ({placeholders}) AND tenant_id = %s"
                cursor.execute(kb_query, kb_ids + [user_id])
                kb_results = cursor.fetchall()
                kb_names = [kb["name"] for kb in kb_results]

            formatted_assistants.append({
                "id": assistant["id"],
                "name": assistant["name"],
                "description": assistant["description"],
                "knowledgeBaseIds": kb_ids,
                "knowledgeBaseNames": kb_names,
                "createTime": assistant["create_date"].strftime("%Y-%m-%d %H:%M:%S") if assistant["create_date"] else "",
                "updateTime": assistant["update_date"].strftime("%Y-%m-%d %H:%M:%S") if assistant["update_date"] else "",
            })

        cursor.close()
        conn.close()

        return formatted_assistants, total

    except mysql.connector.Error as err:
        print(f"数据库错误: {err}")
        return [], 0


def create_assistant(assistant_data):
    """
    创建新助教（对话助手）
    插入到dialog表
    时间将以 UTC+8 (Asia/Shanghai) 存储。
    """
    try:
        # 获取当前登录用户ID

        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"

        user_id = current_user['user_id']

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 获取基本信息
        assistant_name = assistant_data.get("assistant_name")
        description = assistant_data.get("description", "")
        knowledge_bases = assistant_data.get("knowledge_bases", [])

        # 查询当前租户的 llm_id 和 rerank_id
        cursor.execute("""
            SELECT llm_id, rerank_id
            FROM tenant
            WHERE id = %s
        """, (user_id,))
        tenant_config = cursor.fetchone()

        # 获取到租户的llm模型和rerank模型
        llm_id = tenant_config['llm_id']
        rerank_id = tenant_config['rerank_id']

        # 获取当前时间 (UTC+8)
        utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
        target_tz = pytz.timezone('Asia/Shanghai')
        local_dt = utc_now.astimezone(target_tz)
        create_time = int(local_dt.timestamp() * 1000)
        current_date = local_dt.strftime("%Y-%m-%d %H:%M:%S")

        # 将 knowledge_bases 数组转换为 JSON 数组字符串
        kb_ids_str = json.dumps(knowledge_bases) if knowledge_bases else "[]"

        # 插入dialog表
        dialog_insert_query = """
        INSERT INTO dialog (
            id, create_time, create_date, update_time, update_date,
            tenant_id, name, description, icon, language,
            llm_id, llm_setting, prompt_type, prompt_config,
            similarity_threshold, vector_similarity_weight,
            top_n, top_k, do_refer, rerank_id, kb_ids, status
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s,
            %s, %s, %s, %s, %s, %s
        )
        """

        dialog_id = generate_uuid()
        dialog_data = (
            dialog_id, create_time, current_date, create_time, current_date,
            user_id, assistant_name, description, None, "Chinese",
            llm_id, "{}", "simple", "{}",
            0.2, 0.3,
            8, 1024, "1", rerank_id, kb_ids_str, "1"
        )
        cursor.execute(dialog_insert_query, dialog_data)

        conn.commit()
        cursor.close()
        conn.close()

        return True, dialog_id

    except mysql.connector.Error as err:
        print(f"创建助教错误: {err}")
        return False, str(err)


def delete_assistant(assistant_id):
    """删除指定ID的助教"""
    try:
        # 获取当前登录用户ID
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"

        user_id = current_user['user_id']

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 检查助教是否存在且属于当前用户
        check_query = "SELECT id FROM dialog WHERE id = %s AND tenant_id = %s"
        cursor.execute(check_query, (assistant_id, user_id))
        result = cursor.fetchone()

        if not result:
            cursor.close()
            conn.close()
            return False, "助教不存在或无权删除"

        # 先删除班级助教关联记录
        delete_class_dialog_query = "DELETE FROM class_dialog WHERE dialog_id = %s"
        cursor.execute(delete_class_dialog_query, (assistant_id,))

        # 再删除助教
        delete_query = "DELETE FROM dialog WHERE id = %s AND tenant_id = %s"
        cursor.execute(delete_query, (assistant_id, user_id))

        conn.commit()
        cursor.close()
        conn.close()

        return True, "删除成功"

    except mysql.connector.Error as err:
        print(f"删除助教错误: {err}")
        return False, str(err)


def update_assistant(assistant_id, assistant_data):
    """更新助教信息"""
    try:
        # 获取当前登录用户ID
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"

        user_id = current_user['user_id']

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 检查助教是否存在且属于当前用户
        check_query = "SELECT id FROM dialog WHERE id = %s AND tenant_id = %s"
        cursor.execute(check_query, (assistant_id, user_id))
        result = cursor.fetchone()

        if not result:
            cursor.close()
            conn.close()
            return False, "助教不存在或无权修改"

        # 更新时间
        utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
        target_tz = pytz.timezone('Asia/Shanghai')
        local_dt = utc_now.astimezone(target_tz)
        update_time = int(local_dt.timestamp() * 1000)
        update_date = local_dt.strftime("%Y-%m-%d %H:%M:%S")

        # 获取更新字段
        assistant_name = assistant_data.get("assistant_name")
        description = assistant_data.get("description", "")
        knowledge_bases = assistant_data.get("knowledge_bases", [])

        # 将 knowledge_bases 数组转换为 JSON 数组字符串
        kb_ids_str = json.dumps(knowledge_bases) if knowledge_bases else "[]"

        # 更新助教信息
        query = """
        UPDATE dialog
        SET name = %s, description = %s, kb_ids = %s, update_time = %s, update_date = %s
        WHERE id = %s AND tenant_id = %s
        """
        cursor.execute(query, (assistant_name, description, kb_ids_str, update_time, update_date, assistant_id, user_id))
        conn.commit()

        cursor.close()
        conn.close()

        return True, "更新成功"

    except mysql.connector.Error as err:
        print(f"更新助教错误: {err}")
        return False, f"更新助教失败: {str(err)}"


def reset_assistant_password(assistant_id, new_password):
    """重置助教密码（助教类型为dialog，不支持密码重置）"""
    return False, "助教（对话助手）不支持密码重置操作"
