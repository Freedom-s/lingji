import mysql.connector
import pytz
from datetime import datetime
from utils import generate_uuid
from database import DB_CONFIG
from auth import get_current_user


def create_team(team_data):
    """
    创建新班级
    插入到class表
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
        name = team_data.get("name")
        description = team_data.get("description", "")

        if not name:
            cursor.close()
            conn.close()
            return False, "班级名称不能为空"

        # 获取当前时间 (UTC+8)
        utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
        target_tz = pytz.timezone('Asia/Shanghai')
        local_dt = utc_now.astimezone(target_tz)
        create_time = int(local_dt.timestamp() * 1000)
        current_date = local_dt.strftime("%Y-%m-%d %H:%M:%S")

        # 插入class表
        class_insert_query = """
        INSERT INTO class (
            id, create_time, create_date, update_time, update_date,
            tenant_id, name, description, status
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s
        )
        """

        class_id = generate_uuid()
        class_data = (
            class_id, create_time, current_date, create_time, current_date,
            user_id, name, description, "1"
        )
        cursor.execute(class_insert_query, class_data)

        # 将当前用户添加为班级负责人
        user_class_insert_query = """
        INSERT INTO user_class (
            id, create_time, create_date, update_time, update_date,
            user_id, class_id, role, status
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s
        )
        """
        user_class_data = (
            generate_uuid(), create_time, current_date, create_time, current_date,
            user_id, class_id, "teacher", "1"
        )
        cursor.execute(user_class_insert_query, user_class_data)

        conn.commit()
        cursor.close()
        conn.close()

        return True, class_id

    except mysql.connector.Error as err:
        print(f"创建班级错误: {err}")
        return False, str(err)


def get_teams_with_pagination(current_page, page_size, name='', sort_by="create_time", sort_order="desc"):
    """查询班级信息，支持分页和条件筛选"""
    try:
        # 获取当前登录用户ID
        current_user = get_current_user()
        if not current_user:
            return [], 0

        user_id = current_user['user_id']

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 构建WHERE子句和参数
        where_clauses = ["c.tenant_id = %s"]
        params = [user_id]

        if name:
            where_clauses.append("c.name LIKE %s")
            params.append(f"%{name}%")

        # 组合WHERE子句
        where_sql = "WHERE " + " AND ".join(where_clauses)

        # 验证排序字段
        valid_sort_fields = ["name", "create_time", "create_date", "update_date"]
        if sort_by not in valid_sort_fields:
            sort_by = "create_time"

        # 构建排序子句
        sort_clause = f"ORDER BY c.{sort_by} {sort_order.upper()}"

        # 查询目前总共有多少个班级满足条件
        count_sql = f"SELECT COUNT(*) as total FROM class c {where_sql}"
        cursor.execute(count_sql, params)
        total = cursor.fetchone()['total']

        # 计算分页偏移量
        offset = (current_page - 1) * page_size

        # 执行分页查询，包含负责人信息、学生数量和助教信息
        query = f"""
        SELECT
            c.id,
            c.name,
            c.create_date,
            c.update_date,
            c.status,
            uc_t.nickname as owner_name,
            (SELECT COUNT(*) FROM user_class uc
             WHERE uc.class_id = c.id AND uc.role = 'student' AND uc.status = '1') as student_count,
            (SELECT COUNT(*) FROM class_dialog cd
             WHERE cd.class_id = c.id) as assistant_count,
            (SELECT GROUP_CONCAT(d.name SEPARATOR ', ')
             FROM class_dialog cd
             JOIN dialog d ON cd.dialog_id = d.id
             WHERE cd.class_id = c.id) as assistant_names
        FROM
            class c
        LEFT JOIN user_class uc ON c.id = uc.class_id AND uc.role = 'teacher'
        LEFT JOIN user uc_t ON uc.user_id = uc_t.id
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
        formatted_teams = []
        for team in results:
            owner_name = team["owner_name"] if team["owner_name"] else "未指定"
            assistant_names = team["assistant_names"] if team["assistant_names"] else ""
            assistant_list = assistant_names.split(", ") if assistant_names else []

            formatted_teams.append({
                "id": team["id"],
                "name": team["name"],
                "ownerName": owner_name,
                "studentCount": team["student_count"] if team["student_count"] else 0,
                "assistantCount": team["assistant_count"] if team["assistant_count"] else 0,
                "assistantNames": assistant_list,
                "createTime": team["create_date"].strftime("%Y-%m-%d %H:%M:%S") if team["create_date"] else "",
                "updateTime": team["update_date"].strftime("%Y-%m-%d %H:%M:%S") if team["update_date"] else "",
                "status": team["status"]
            })

        return formatted_teams, total

    except mysql.connector.Error as err:
        print(f"数据库错误: {err}")
        return [], 0


def get_team_by_id(team_id):
    """根据ID获取团队详情"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        query = """
        SELECT id, name, create_date, update_date, status, credit
        FROM tenant
        WHERE id = %s
        """
        cursor.execute(query, (team_id,))
        team = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if team:
            return {
                "id": team["id"],
                "name": team["name"],
                "createTime": team["create_date"].strftime("%Y-%m-%d %H:%M:%S") if team["create_date"] else "",
                "updateTime": team["update_date"].strftime("%Y-%m-%d %H:%M:%S") if team["update_date"] else "",
                "status": team["status"],
                "credit": team["credit"]
            }
        return None
        
    except mysql.connector.Error as err:
        print(f"数据库错误: {err}")
        return None

def delete_team(team_id):
    """删除指定ID的班级"""
    try:
        # 获取当前登录用户ID
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"

        user_id = current_user['user_id']

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 检查班级是否存在且属于当前用户
        check_query = "SELECT id FROM class WHERE id = %s AND tenant_id = %s"
        cursor.execute(check_query, (team_id, user_id))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return False, "班级不存在或无权操作"

        # 删除班级成员关系
        member_query = "DELETE FROM user_class WHERE class_id = %s"
        cursor.execute(member_query, (team_id,))

        # 删除班级助教关系
        assistant_query = "DELETE FROM class_dialog WHERE class_id = %s"
        cursor.execute(assistant_query, (team_id,))

        # 删除班级
        class_query = "DELETE FROM class WHERE id = %s"
        cursor.execute(class_query, (team_id,))

        affected_rows = cursor.rowcount

        conn.commit()
        cursor.close()
        conn.close()

        if affected_rows == 0:
            return False, "班级不存在"

        return True, "删除成功"

    except mysql.connector.Error as err:
        print(f"删除班级错误: {err}")
        return False, f"删除失败: {str(err)}"


def batch_delete_teams(class_ids):
    """批量删除班级"""
    try:
        # 获取当前登录用户ID
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"

        user_id = current_user['user_id']

        if not class_ids or len(class_ids) == 0:
            return False, "请选择要删除的班级"

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 检查哪些班级属于当前用户
        placeholders = ','.join(['%s'] * len(class_ids))
        check_query = f"SELECT id FROM class WHERE id IN ({placeholders}) AND tenant_id = %s"
        cursor.execute(check_query, class_ids + [user_id])
        valid_ids = [row['id'] for row in cursor.fetchall()]

        if len(valid_ids) == 0:
            cursor.close()
            conn.close()
            return False, "没有可删除的班级"

        # 删除班级成员关系
        member_query = f"DELETE FROM user_class WHERE class_id IN ({placeholders})"
        cursor.execute(member_query, valid_ids)

        # 删除班级助教关系
        assistant_query = f"DELETE FROM class_dialog WHERE class_id IN ({placeholders})"
        cursor.execute(assistant_query, valid_ids)

        # 删除班级
        class_query = f"DELETE FROM class WHERE id IN ({placeholders})"
        cursor.execute(class_query, valid_ids)

        deleted_count = cursor.rowcount

        conn.commit()
        cursor.close()
        conn.close()

        return True, f"成功删除 {deleted_count} 个班级"

    except mysql.connector.Error as err:
        print(f"批量删除班级错误: {err}")
        return False, f"批量删除失败: {str(err)}"

def get_team_members(team_id):
    """获取班级成员列表（学生）"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        query = """
        SELECT uc.user_id, u.nickname, u.email, uc.role, uc.status, uc.create_date
        FROM user_class uc
        JOIN user u ON uc.user_id = u.id
        WHERE uc.class_id = %s AND uc.role = 'student'
        ORDER BY uc.create_date DESC
        """
        cursor.execute(query, (team_id,))
        results = cursor.fetchall()

        cursor.close()
        conn.close()

        # 格式化结果
        formatted_members = []
        for member in results:
            formatted_members.append({
                "userId": member["user_id"],
                "username": member["nickname"],
                "email": member["email"],
                "role": member["role"],  # student
                "status": member["status"],  # 1 正常, 0 禁用
                "joinTime": member["create_date"].strftime("%Y-%m-%d %H:%M:%S") if member["create_date"] else ""
            })

        return formatted_members

    except mysql.connector.Error as err:
        print(f"获取班级成员错误: {err}")
        return []

def add_team_member(team_id, user_id, role="student"):
    """添加班级成员"""
    try:
        # 获取当前登录用户ID
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"

        user_id_current = current_user['user_id']

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 检查班级是否属于当前用户
        check_class_query = "SELECT id FROM class WHERE id = %s AND tenant_id = %s"
        cursor.execute(check_class_query, (team_id, user_id_current))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return False, "班级不存在或无权操作"

        # 检查用户是否已经是班级成员
        check_query = """
        SELECT id, status FROM user_class
        WHERE class_id = %s AND user_id = %s
        """
        cursor.execute(check_query, (team_id, user_id))
        existing = cursor.fetchone()

        if existing:
            cursor.close()
            conn.close()
            return False, "该用户已在此班级中"
        else:
            # 如果不是成员，添加新记录
            utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
            target_tz = pytz.timezone('Asia/Shanghai')
            local_dt = utc_now.astimezone(target_tz)
            create_time = int(local_dt.timestamp() * 1000)
            current_date = local_dt.strftime("%Y-%m-%d %H:%M:%S")

            insert_query = """
            INSERT INTO user_class (
                id, create_time, create_date, update_time, update_date, user_id,
                class_id, role, status
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s
            )
            """

            user_class_data = (
                generate_uuid(), create_time, current_date, create_time, current_date, user_id,
                team_id, role, "1"
            )
            cursor.execute(insert_query, user_class_data)

        conn.commit()
        cursor.close()
        conn.close()

        return True, "添加成员成功"

    except mysql.connector.Error as err:
        print(f"添加班级成员错误: {err}")
        return False, f"添加成员失败: {str(err)}"

def remove_team_member(team_id, user_id):
    """移除班级成员"""
    try:
        # 获取当前登录用户ID
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"

        user_id_current = current_user['user_id']

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 检查班级是否属于当前用户
        check_class_query = "SELECT id FROM class WHERE id = %s AND tenant_id = %s"
        cursor.execute(check_class_query, (team_id, user_id_current))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return False, "班级不存在或无权操作"

        # 检查要移除的用户角色
        check_user_role_query = """
        SELECT role FROM user_class
        WHERE class_id = %s AND user_id = %s
        """
        cursor.execute(check_user_role_query, (team_id, user_id))
        user_role = cursor.fetchone()

        # 不允许移除负责人（teacher）
        if user_role and user_role['role'] == 'teacher':
            cursor.close()
            conn.close()
            return False, "不能移除班级负责人"

        # 移除成员
        delete_query = """
        DELETE FROM user_class
        WHERE class_id = %s AND user_id = %s
        """
        cursor.execute(delete_query, (team_id, user_id))
        affected_rows = cursor.rowcount

        conn.commit()
        cursor.close()
        conn.close()

        if affected_rows == 0:
            return False, "成员不存在"

        return True, "移除成员成功"

    except mysql.connector.Error as err:
        print(f"移除班级成员错误: {err}")
        return False, f"移除成员失败: {str(err)}"


def add_class_assistant(class_id, dialog_id):
    """为班级添加助教"""
    try:
        # 获取当前登录用户ID
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"

        user_id = current_user['user_id']

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 检查班级是否属于当前用户
        check_class_query = "SELECT id FROM class WHERE id = %s AND tenant_id = %s"
        cursor.execute(check_class_query, (class_id, user_id))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return False, "班级不存在或无权操作"

        # 检查助教是否存在且属于当前用户
        check_dialog_query = "SELECT id FROM dialog WHERE id = %s AND tenant_id = %s"
        cursor.execute(check_dialog_query, (dialog_id, user_id))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return False, "助教不存在或无权操作"

        # 检查是否已经添加过该助教
        check_existing_query = "SELECT id FROM class_dialog WHERE class_id = %s AND dialog_id = %s"
        cursor.execute(check_existing_query, (class_id, dialog_id))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return False, "该助教已添加到此班级"

        # 获取当前时间 (UTC+8)
        utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
        target_tz = pytz.timezone('Asia/Shanghai')
        local_dt = utc_now.astimezone(target_tz)
        create_time = int(local_dt.timestamp() * 1000)
        current_date = local_dt.strftime("%Y-%m-%d %H:%M:%S")

        # 插入class_dialog表
        insert_query = """
        INSERT INTO class_dialog (
            id, create_time, create_date, update_time, update_date,
            class_id, dialog_id
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s
        )
        """

        class_dialog_data = (
            generate_uuid(), create_time, current_date, create_time, current_date,
            class_id, dialog_id
        )
        cursor.execute(insert_query, class_dialog_data)

        conn.commit()
        cursor.close()
        conn.close()

        return True, "添加助教成功"

    except mysql.connector.Error as err:
        print(f"添加班级助教错误: {err}")
        return False, f"添加助教失败: {str(err)}"


def get_class_assistants(class_id):
    """获取班级助教列表"""
    try:
        # 获取当前登录用户ID
        current_user = get_current_user()
        if not current_user:
            return []

        user_id = current_user['user_id']

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 检查班级是否属于当前用户
        check_class_query = "SELECT id FROM class WHERE id = %s AND tenant_id = %s"
        cursor.execute(check_class_query, (class_id, user_id))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return []

        # 查询班级助教列表
        query = """
        SELECT cd.id, cd.dialog_id, d.name, d.description, cd.create_date
        FROM class_dialog cd
        JOIN dialog d ON cd.dialog_id = d.id
        WHERE cd.class_id = %s
        ORDER BY cd.create_date DESC
        """
        cursor.execute(query, (class_id,))
        results = cursor.fetchall()

        cursor.close()
        conn.close()

        # 格式化结果
        formatted_assistants = []
        for assistant in results:
            formatted_assistants.append({
                "id": assistant["id"],
                "dialogId": assistant["dialog_id"],
                "name": assistant["name"],
                "description": assistant["description"],
                "addTime": assistant["create_date"].strftime("%Y-%m-%d %H:%M:%S") if assistant["create_date"] else ""
            })

        return formatted_assistants

    except mysql.connector.Error as err:
        print(f"获取班级助教错误: {err}")
        return []


def remove_class_assistant(class_id, assistant_id):
    """移除班级助教"""
    try:
        # 获取当前登录用户ID
        current_user = get_current_user()
        if not current_user:
            return False, "获取用户信息失败"

        user_id = current_user['user_id']

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # 检查班级是否属于当前用户
        check_class_query = "SELECT id FROM class WHERE id = %s AND tenant_id = %s"
        cursor.execute(check_class_query, (class_id, user_id))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return False, "班级不存在或无权操作"

        # 移除助教
        delete_query = "DELETE FROM class_dialog WHERE id = %s AND class_id = %s"
        cursor.execute(delete_query, (assistant_id, class_id))
        affected_rows = cursor.rowcount

        conn.commit()
        cursor.close()
        conn.close()

        if affected_rows == 0:
            return False, "助教不存在"

        return True, "移除助教成功"

    except mysql.connector.Error as err:
        print(f"移除班级助教错误: {err}")
        return False, f"移除助教失败: {str(err)}"