import mysql.connector
import pytz
from datetime import datetime
from utils import generate_uuid, encrypt_password
from database import DB_CONFIG
from auth import get_current_user

def get_users_with_pagination(current_page, page_size, username='', email='', sort_by="create_time", sort_order="desc"):
    """查询当前登录用户租户下的学生信息，支持分页和条件筛选"""
    try:
        # 获取当前登录用户信息
        current_user = get_current_user()
        if not current_user:
            return [], 0

        current_user_id = current_user['user_id']

        # 建立数据库连接
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 构建WHERE子句和参数
        where_clauses = [
            "u.is_superuser = 0",           # 只查询学生
            "ut.tenant_id = %s",              # 只查询当前登录用户的租户
            "u.id != %s"                       # 排除当前登录用户自己
        ]
        params = [current_user_id, current_user_id]

        if username:
            where_clauses.append("u.nickname LIKE %s")
            params.append(f"%{username}%")

        if email:
            where_clauses.append("u.email LIKE %s")
            params.append(f"%{email}%")

        # 组合WHERE子句
        where_sql = "WHERE " + " AND ".join(where_clauses)

        # 验证排序字段
        valid_sort_fields = ["nickname", "email", "create_time", "create_date"]
        if sort_by not in valid_sort_fields:
            sort_by = "create_time"

        # 构建排序子句
        sort_clause = f"ORDER BY u.{sort_by} {sort_order.upper()}"

        # 查询总记录数
        count_sql = f"""
        SELECT COUNT(*) as total
        FROM user u
        JOIN user_tenant ut ON u.id = ut.user_id
        {where_sql}
        """
        cursor.execute(count_sql, params)
        total = cursor.fetchone()['total']

        # 计算分页偏移量
        offset = (current_page - 1) * page_size

        # 执行分页查询
        query = f"""
        SELECT DISTINCT u.id, u.nickname, u.email, u.create_time, u.create_date, u.update_date, u.status, u.is_superuser
        FROM user u
        JOIN user_tenant ut ON u.id = ut.user_id
        {where_sql}
        {sort_clause}
        LIMIT %s OFFSET %s
        """
        cursor.execute(query, params + [page_size, offset])
        results = cursor.fetchall()

        # 关闭连接
        cursor.close()
        conn.close()

        # 格式化结果
        formatted_users = []
        for user in results:
            formatted_users.append({
                "id": user["id"],
                "username": user["nickname"],
                "email": user["email"],
                "createTime": user["create_date"].strftime("%Y-%m-%d %H:%M:%S") if user["create_date"] else "",
                "updateTime": user["update_date"].strftime("%Y-%m-%d %H:%M:%S") if user["update_date"] else "",
            })

        return formatted_users, total

    except mysql.connector.Error as err:
        print(f"数据库错误: {err}")
        return [], 0

def delete_user(user_id):
    """删除指定ID的用户（学生）- 只能删除当前登录用户租户下的学生"""
    try:
        from flask import request
        from auth import get_current_user

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 获取当前登录用户信息
        current_user = get_current_user()
        if not current_user:
            cursor.close()
            conn.close()
            return False, "获取当前用户信息失败"

        current_user_id = current_user['user_id']

        # 先删除 user_tenant 表中的关联记录（只删除当前租户下的关系）
        user_tenant_query = "DELETE FROM user_tenant WHERE user_id = %s AND tenant_id = %s"
        cursor.execute(user_tenant_query, (user_id, current_user_id))

        # 检查是否删除成功（是否有受影响的行）
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return False, "该学生不在您的租户下，无法删除"

        # 再删除 user 表中的用户记录
        query = "DELETE FROM user WHERE id = %s"
        cursor.execute(query, (user_id,))

        conn.commit()
        cursor.close()
        conn.close()

        return True, "删除成功"
    except mysql.connector.Error as err:
        print(f"删除用户错误: {err}")
        return False, f"删除失败: {str(err)}"

def create_user(user_data):
    """
    创建学生（普通用户）
    1. 创建 user 表记录（is_superuser=0, is_system=0）
    2. 创建 user_tenant 关系，把学生加入到当前登录用户（教师）的租户下
    """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 获取当前登录用户信息，即租户的信息
        current_user = get_current_user()
        if not current_user:
            cursor.close()
            conn.close()
            return False, "获取当前用户信息失败"

        current_user_id = current_user['user_id']

        # 获取基本信息
        username = user_data.get("username")
        email = user_data.get("email")
        password = user_data.get("password")

        # 检查邮箱或昵称是否已存在
        check_query = "SELECT COUNT(*) as count FROM user WHERE email = %s OR nickname = %s"
        cursor.execute(check_query, (email, username))
        if cursor.fetchone()['count'] > 0:
            cursor.close()
            conn.close()
            return False, "用户名或邮箱已存在"

        # 查询当前登录用户的 tenant_id
        tenant_query = "SELECT id FROM tenant WHERE id = %s"
        cursor.execute(tenant_query, (current_user_id,))
        current_tenant = cursor.fetchone()

        if not current_tenant:
            cursor.close()
            conn.close()
            return False, "当前用户的租户不存在"

        # 开始插入
        user_id = generate_uuid()
        encrypted_password = encrypt_password(password)

        # 获取当前时间 (UTC+8)
        utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
        target_tz = pytz.timezone('Asia/Shanghai')
        local_dt = utc_now.astimezone(target_tz)
        create_time = int(local_dt.timestamp() * 1000)
        current_date = local_dt.strftime("%Y-%m-%d %H:%M:%S")

        # 插入用户表（学生: is_superuser=0, is_system=0）
        user_insert_query = """
        INSERT INTO user (
            id, create_time, create_date, update_time, update_date,
            nickname, password, email, language, color_schema, timezone,
            is_authenticated, is_active, is_anonymous, login_channel,
            status, is_superuser, is_system
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s
        )
        """
        user_data_tuple = (
            user_id, create_time, current_date, create_time, current_date,
            username, encrypted_password, email, "Chinese", "Bright", "UTC+8 Asia/Shanghai",
            1, 1, 0, "password",
            1, 0, 0  # 学生: is_superuser=0, is_system=0
        )
        cursor.execute(user_insert_query, user_data_tuple)

        # 插入用户租户关系表（加入当前登录用户的租户）
        user_tenant_insert_query = """
        INSERT INTO user_tenant (
            id, create_time, create_date, update_time, update_date,
            user_id, tenant_id, role, invited_by, status
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s
        )
        """
        user_tenant_data = (
            generate_uuid(), create_time, current_date, create_time, current_date,
            user_id,                      # 新学生用户ID
            current_tenant['id'],         # 当前登录用户的租户ID
            "normal",                     # 角色：普通成员
            current_user_id,              # 邀请人：当前登录用户
            1
        )
        cursor.execute(user_tenant_insert_query, user_tenant_data)

        conn.commit()
        cursor.close()
        conn.close()

        return True, "用户创建成功"

    except mysql.connector.Error as err:
        print(f"创建用户错误: {err}")
        return False, f"创建用户失败: {str(err)}"


def update_user(user_id, user_data):
    """更新用户信息"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 检查用户名是否与其他用户冲突
        username = user_data.get("username")
        check_conflict_query = """
        SELECT COUNT(*) as count FROM user
        WHERE nickname = %s AND id != %s
        """
        cursor.execute(check_conflict_query, (username, user_id))
        if cursor.fetchone()['count'] > 0:
            cursor.close()
            conn.close()
            return False, "用户名已被其他用户使用"

        # 更新时间
        utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
        target_tz = pytz.timezone('Asia/Shanghai')
        local_dt = utc_now.astimezone(target_tz)
        update_time = int(local_dt.timestamp() * 1000)
        update_date = local_dt.strftime("%Y-%m-%d %H:%M:%S")

        query = """
        UPDATE user SET nickname = %s, update_time = %s, update_date = %s WHERE id = %s
        """
        cursor.execute(query, (username, update_time, update_date, user_id))

        if cursor.rowcount == 0:
            conn.rollback()
            cursor.close()
            conn.close()
            return False, "用户不存在"

        conn.commit()
        cursor.close()
        conn.close()

        return True, "更新成功"

    except mysql.connector.Error as err:
        print(f"更新用户错误: {err}")
        return False, f"更新用户失败: {str(err)}"

def reset_user_password(user_id, new_password):
    """
    重置指定用户的密码。
    时间将以 UTC+8 (Asia/Shanghai) 存储。
    Args:
        user_id (str): 用户ID
        new_password (str): 新的明文密码
    Returns:
        (bool, str): 操作是否成功和消息
    """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 加密新密码
        encrypted_password = encrypt_password(new_password)

        # 获取当前 UTC 时间
        utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
        target_tz = pytz.timezone('Asia/Shanghai')
        local_dt = utc_now.astimezone(target_tz)

        update_time = int(local_dt.timestamp() * 1000)
        update_date = local_dt.strftime("%Y-%m-%d %H:%M:%S")

        # 更新用户密码
        update_query = """
        UPDATE user
        SET password = %s, update_time = %s, update_date = %s
        WHERE id = %s
        """
        cursor.execute(update_query, (encrypted_password, update_time, update_date, user_id))

        if cursor.rowcount == 0:
            conn.rollback()
            cursor.close()
            conn.close()
            return False, "用户不存在"

        conn.commit()
        cursor.close()
        conn.close()

        return True, "密码重置成功"

    except mysql.connector.Error as err:
        print(f"重置密码时数据库错误: {err}")
        if 'conn' in locals() and conn.is_connected():
            conn.rollback()
            cursor.close()
            conn.close()
        return False, f"重置密码失败: {str(err)}"
    except Exception as e:
        print(f"重置密码时发生未知错误: {e}")
        if 'conn' in locals() and conn.is_connected():
            conn.rollback()
            cursor.close()
            conn.close()
        return False, f"重置密码失败: {str(e)}"