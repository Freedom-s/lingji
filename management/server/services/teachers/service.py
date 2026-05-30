import mysql.connector
import pytz
from datetime import datetime
from utils import generate_uuid, encrypt_password
from database import DB_CONFIG


def get_teachers_with_pagination(current_page, page_size, username='', email='', sort_by="create_time", sort_order="desc"):
    """查询教师信息，支持分页和条件筛选"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 构建WHERE子句和参数 - 只查询教师 (is_superuser = 1 且 is_system = 0)
        where_clauses = ["is_superuser = 1 AND is_system = 0"]
        params = []

        if username:
            where_clauses.append("nickname LIKE %s")
            params.append(f"%{username}%")

        if email:
            where_clauses.append("email LIKE %s")
            params.append(f"%{email}%")

        where_sql = "WHERE " + " AND ".join(where_clauses)

        # 验证排序字段
        valid_sort_fields = ["nickname", "email", "create_time", "create_date"]
        if sort_by not in valid_sort_fields:
            sort_by = "create_time"

        sort_clause = f"ORDER BY {sort_by} {sort_order.upper()}"

        # 查询总记录数
        count_sql = f"SELECT COUNT(*) as total FROM user {where_sql}"
        cursor.execute(count_sql, params)
        total = cursor.fetchone()['total']

        # 计算分页偏移量
        offset = (current_page - 1) * page_size

        # 执行分页查询
        query = f"""
        SELECT id, nickname, email, create_date, update_date, status, is_superuser, is_system
        FROM user
        {where_sql}
        {sort_clause}
        LIMIT %s OFFSET %s
        """
        cursor.execute(query, params + [page_size, offset])
        results = cursor.fetchall()

        cursor.close()
        conn.close()

        # 格式化结果
        formatted_teachers = []
        for teacher in results:
            formatted_teachers.append({
                "id": teacher["id"],
                "username": teacher["nickname"],
                "email": teacher["email"],
                "createTime": teacher["create_date"].strftime("%Y-%m-%d %H:%M:%S") if teacher["create_date"] else "",
                "updateTime": teacher["update_date"].strftime("%Y-%m-%d %H:%M:%S") if teacher["update_date"] else "",
            })

        return formatted_teachers, total

    except mysql.connector.Error as err:
        print(f"数据库错误: {err}")
        return [], 0


def create_teacher(teacher_data):
    """
    创建新教师，并加入最早用户的团队，并使用相同的模型配置。
    时间将以 UTC+8 (Asia/Shanghai) 存储。
    """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 检查用户表是否为空
        check_users_query = "SELECT COUNT(*) as user_count FROM user"
        cursor.execute(check_users_query)
        user_count = cursor.fetchone()['user_count']

        # 如果有用户，则查询最早的tenant和用户配置
        if user_count > 0:
            # 查询最早创建的tenant配置
            query_earliest_tenant = """
            SELECT id, llm_id, embd_id, asr_id, img2txt_id, rerank_id, tts_id, parser_ids, credit
            FROM tenant
            WHERE create_time = (SELECT MIN(create_time) FROM tenant)
            LIMIT 1
            """
            cursor.execute(query_earliest_tenant)
            earliest_tenant = cursor.fetchone()

            # 查询最早创建的用户ID
            query_earliest_user = """
            SELECT id FROM user
            WHERE create_time = (SELECT MIN(create_time) FROM user)
            LIMIT 1
            """
            cursor.execute(query_earliest_user)
            earliest_user = cursor.fetchone()

            # 查询最早用户的所有tenant_llm配置
            query_earliest_user_tenant_llms = """
            SELECT llm_factory, model_type, llm_name, api_key, api_base, max_tokens, used_tokens
            FROM tenant_llm
            WHERE tenant_id = %s
            """
            cursor.execute(query_earliest_user_tenant_llms, (earliest_user['id'],))
            earliest_user_tenant_llms = cursor.fetchall()

        # 检查邮箱或昵称是否已存在
        username = teacher_data.get("username")
        email = teacher_data.get("email")
        password = teacher_data.get("password")

        # 判断不能有重复的用户名或者邮箱
        check_query = "SELECT COUNT(*) as count FROM user WHERE email = %s OR nickname = %s"
        cursor.execute(check_query, (email, username))
        if cursor.fetchone()['count'] > 0:
            cursor.close()
            conn.close()
            return False, "用户名或邮箱已存在"

        # 开始插入
        user_id = generate_uuid()
        # 加密密码
        encrypted_password = encrypt_password(password)

        # --- 修改时间获取和格式化逻辑 ---
        # 获取当前 UTC 时间
        utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
        # 定义目标时区 (UTC+8)
        target_tz = pytz.timezone('Asia/Shanghai')
        # 将 UTC 时间转换为目标时区时间
        local_dt = utc_now.astimezone(target_tz)

        # 使用转换后的时间
        create_time = int(local_dt.timestamp() * 1000) # 使用本地化时间戳
        current_date = local_dt.strftime("%Y-%m-%d %H:%M:%S") # 使用本地化时间格式化
        # --- 时间逻辑修改结束 ---

        # 插入用户表 (教师: is_superuser=1, is_system=0)
        user_insert_query = """
        INSERT INTO user (
            id, create_time, create_date, update_time, update_date, access_token,
            nickname, password, email, avatar, language, color_schema, timezone,
            last_login_time, is_authenticated, is_active, is_anonymous, login_channel,
            status, is_superuser, is_system
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s
        )
        """
        user_data_tuple = (
            user_id, create_time, current_date, create_time, current_date, None, # 使用修改后的时间
            username, encrypted_password, email, None, "Chinese", "Bright", "UTC+8 Asia/Shanghai",
            current_date, 1, 1, 0, "password", # last_login_time 也使用 UTC+8 时间
            1, 1, 0  # 教师: is_superuser=1, is_system=0
        )
        cursor.execute(user_insert_query, user_data_tuple)

        # 插入租户表
        tenant_insert_query = """
        INSERT INTO tenant (
            id, create_time, create_date, update_time, update_date, name,
            public_key, llm_id, embd_id, asr_id, img2txt_id, rerank_id, tts_id,
            parser_ids, credit, status
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s
        )
        """

        if user_count > 0:
            # 如果有现有用户，复制其模型配置
            tenant_data = (
                user_id, create_time, current_date, create_time, current_date, username + "'s Kingdom", # 使用修改后的时间
                None, str(earliest_tenant['llm_id']), str(earliest_tenant['embd_id']),
                str(earliest_tenant['asr_id']), str(earliest_tenant['img2txt_id']),
                str(earliest_tenant['rerank_id']), str(earliest_tenant['tts_id']),
                str(earliest_tenant['parser_ids']), str(earliest_tenant['credit']), 1
            )
        else:
            # 如果是第一个用户，模型ID使用空字符串
            tenant_data = (
                user_id, create_time, current_date, create_time, current_date, username + "'s Kingdom", # 使用修改后的时间
                None, '', '', '', '', '', '',
                '', "1000", 1
            )
        cursor.execute(tenant_insert_query, tenant_data)

        # 插入用户租户关系表（owner角色）
        user_tenant_insert_owner_query = """
        INSERT INTO user_tenant (
            id, create_time, create_date, update_time, update_date, user_id,
            tenant_id, role, invited_by, status
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s
        )
        """
        # 创建他自己的团队
        user_tenant_data_owner = (
            generate_uuid(), create_time, current_date, create_time, current_date, user_id, # 使用修改后的时间
            user_id, "owner", user_id, 1
        )
        cursor.execute(user_tenant_insert_owner_query, user_tenant_data_owner)

        # 只有在存在其他用户时，才加入最早用户的团队
        if user_count > 0:
            # 插入用户租户关系表（normal角色）
            # 加入system的团队
            user_tenant_insert_normal_query = """
            INSERT INTO user_tenant (
                id, create_time, create_date, update_time, update_date, user_id,
                tenant_id, role, invited_by, status
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            """
            user_tenant_data_normal = (
                generate_uuid(), create_time, current_date, create_time, current_date, user_id, # 使用修改后的时间
                earliest_tenant['id'], "normal", earliest_tenant['id'], 1
            )
            cursor.execute(user_tenant_insert_normal_query, user_tenant_data_normal)

            # 为新用户复制最早用户的所有tenant_llm配置
            tenant_llm_insert_query = """
            INSERT INTO tenant_llm (
                create_time, create_date, update_time, update_date, tenant_id,
                llm_factory, model_type, llm_name, api_key, api_base, max_tokens, used_tokens
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s
            )
            """

            # 遍历最早用户的所有tenant_llm配置并复制给新用户
            for tenant_llm in earliest_user_tenant_llms:
                tenant_llm_data = (
                    create_time, current_date, create_time, current_date, user_id, # 使用修改后的时间
                    str(tenant_llm['llm_factory']), str(tenant_llm['model_type']), str(tenant_llm['llm_name']),
                    str(tenant_llm['api_key']), str(tenant_llm['api_base']), str(tenant_llm['max_tokens']), 0
                )
                cursor.execute(tenant_llm_insert_query, tenant_llm_data)

        conn.commit()
        cursor.close()
        conn.close()

        return True, user_id

    except mysql.connector.Error as err:
        print(f"创建教师错误: {err}")
        return False, str(err)


def delete_teacher(teacher_id):
    """删除指定ID的教师，并删除该租户下的所有学生"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 检查是否是教师 (is_superuser=1 且 is_system=0)
        check_query = "SELECT is_superuser, is_system FROM user WHERE id = %s"
        cursor.execute(check_query, (teacher_id,))
        result = cursor.fetchone()

        if not result:
            cursor.close()
            conn.close()
            return False, "教师不存在"

        if result[0] != 1 or result[1] != 0:
            cursor.close()
            conn.close()
            return False, "该用户不是教师"

        # 1. 先查询该租户下的所有学生 ID
        students_query = """
        SELECT DISTINCT ut.user_id
        FROM user_tenant ut
        JOIN user u ON ut.user_id = u.id
        WHERE ut.tenant_id = %s AND u.is_superuser = 0
        """
        cursor.execute(students_query, (teacher_id,))
        student_ids = [row[0] for row in cursor.fetchall()]

        # 2. 删除所有学生的 user 记录
        if student_ids:
            # 删除学生与该租户的关系
            cursor.execute("DELETE FROM user_tenant WHERE tenant_id = %s", (teacher_id,))
            # 删除学生账户
            placeholders = ','.join(['%s'] * len(student_ids))
            cursor.execute(f"DELETE FROM user WHERE id IN ({placeholders})", student_ids)

        # 3. 删除教师自己与租户的关系
        cursor.execute("DELETE FROM user_tenant WHERE user_id = %s", (teacher_id,))

        # 4. 删除教师自己的 user 记录
        cursor.execute("DELETE FROM user WHERE id = %s", (teacher_id,))

        # 5. 删除租户
        cursor.execute("DELETE FROM tenant WHERE id = %s", (teacher_id,))

        # 6. 删除租户的模型配置
        cursor.execute("DELETE FROM tenant_llm WHERE tenant_id = %s", (teacher_id,))

        conn.commit()
        cursor.close()
        conn.close()

        return True, f"删除成功，共删除 {len(student_ids)} 名学生"
    except mysql.connector.Error as err:
        print(f"删除教师错误: {err}")
        return False, str(err)


def update_teacher(teacher_id, teacher_data):
    """更新教师信息"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 检查是否是教师 (is_superuser=1 且 is_system=0)
        check_query = "SELECT is_superuser, is_system FROM user WHERE id = %s"
        cursor.execute(check_query, (teacher_id,))
        result = cursor.fetchone()

        if not result:
            cursor.close()
            conn.close()
            return False, "教师不存在"

        if result['is_superuser'] != 1 or result['is_system'] != 0:
            cursor.close()
            conn.close()
            return False, "该用户不是教师"

        # 检查邮箱或昵称是否与其他用户冲突
        username = teacher_data.get("username")
        email = teacher_data.get("email")

        check_conflict_query = """
        SELECT COUNT(*) as count FROM user
        WHERE (email = %s OR nickname = %s) AND id != %s
        """
        cursor.execute(check_conflict_query, (email, username, teacher_id))
        if cursor.fetchone()['count'] > 0:
            cursor.close()
            conn.close()
            return False, "用户名或邮箱已被其他用户使用"

        # 更新时间
        utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
        target_tz = pytz.timezone('Asia/Shanghai')
        local_dt = utc_now.astimezone(target_tz)
        update_time = int(local_dt.timestamp() * 1000)
        update_date = local_dt.strftime("%Y-%m-%d %H:%M:%S")

        # 更新教师信息
        query = """
        UPDATE user
        SET nickname = %s, email = %s, update_time = %s, update_date = %s
        WHERE id = %s
        """
        cursor.execute(query, (username, email, update_time, update_date, teacher_id))
        conn.commit()

        cursor.close()
        conn.close()

        return True, "更新成功"
    except mysql.connector.Error as err:
        print(f"更新教师错误: {err}")
        return False, str(err)


def reset_teacher_password(teacher_id, new_password):
    """重置教师密码"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 检查是否是教师 (is_superuser=1 且 is_system=0)
        check_query = "SELECT is_superuser, is_system FROM user WHERE id = %s"
        cursor.execute(check_query, (teacher_id,))
        result = cursor.fetchone()

        if not result:
            cursor.close()
            conn.close()
            return False, "教师不存在"

        if result[0] != 1 or result[1] != 0:
            cursor.close()
            conn.close()
            return False, "该用户不是教师"

        # 加密新密码
        encrypted_password = encrypt_password(new_password)

        # 更新时间
        utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
        target_tz = pytz.timezone('Asia/Shanghai')
        local_dt = utc_now.astimezone(target_tz)
        update_time = int(local_dt.timestamp() * 1000)
        update_date = local_dt.strftime("%Y-%m-%d %H:%M:%S")

        # 更新密码
        update_query = """
        UPDATE user
        SET password = %s, update_time = %s, update_date = %s
        WHERE id = %s
        """
        cursor.execute(update_query, (encrypted_password, update_time, update_date, teacher_id))

        if cursor.rowcount == 0:
            conn.rollback()
            cursor.close()
            conn.close()
            return False, "教师不存在"

        conn.commit()
        cursor.close()
        conn.close()

        return True, "密码重置成功"

    except mysql.connector.Error as err:
        print(f"重置密码错误: {err}")
        return False, str(err)
