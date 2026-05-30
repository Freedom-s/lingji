from datetime import datetime, timedelta
from database import get_db_connection


def get_dashboard_overview(tenant_id: str):
    """获取dashboard概览数据（6个基础指标）"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        result = {}

        # 1. 学生数：统计user_tenant中role='normal'且tenant_id=当前租户的数量
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) as count
            FROM user_tenant
            WHERE tenant_id = %s AND role = 'normal' AND status = '1'
        """, (tenant_id,))
        result["student_count"] = cursor.fetchone()["count"]

        # 2. 班级数：统计class表中tenant_id=当前租户的数量
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM class
            WHERE tenant_id = %s AND status = '1'
        """, (tenant_id,))
        result["class_count"] = cursor.fetchone()["count"]

        # 3. 会话数：统计当前租户下所有conversation的数量
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM conversation c
            JOIN dialog d ON c.dialog_id = d.id
            WHERE d.tenant_id = %s
        """, (tenant_id,))
        result["conversation_count"] = cursor.fetchone()["count"]

        # 4. 助教数：统计dialog表中tenant_id=当前租户的数量
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM dialog
            WHERE tenant_id = %s AND status = '1'
        """, (tenant_id,))
        result["assistant_count"] = cursor.fetchone()["count"]

        # 5. 文件数：统计file表中tenant_id=当前租户的数量
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM file
            WHERE tenant_id = %s
        """, (tenant_id,))
        result["file_count"] = cursor.fetchone()["count"]

        # 6. 知识库数量：统计knowledgebase表中tenant_id=当前租户的数量
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM knowledgebase
            WHERE tenant_id = %s AND status = '1'
        """, (tenant_id,))
        result["knowledgebase_count"] = cursor.fetchone()["count"]

        return True, result

    except Exception as e:
        return False, str(e)
    finally:
        cursor.close()
        conn.close()


def get_active_students_chart(tenant_id: str, time_range: str = "24h"):
    """获取活跃学生数趋势图数据"""
    from datetime import datetime, timedelta
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # 根据时间范围确定时间间隔和分组条件
        if time_range == "24h":
            # 过去24小时，按小时分组
            time_unit = "%Y-%m-%d %H:00:00"
            hours = 24
            delta = timedelta(hours=1)
            date_format = "%Y-%m-%d %H:00:00"
        elif time_range == "7d":
            # 过去7天，按天分组
            time_unit = "%Y-%m-%d"
            days = 7
            delta = timedelta(days=1)
            date_format = "%Y-%m-%d"
        else:  # 30d
            # 过去30天，按天分组
            time_unit = "%Y-%m-%d"
            days = 30
            delta = timedelta(days=1)
            date_format = "%Y-%m-%d"

        # 构建时间筛选条件
        if time_range == "24h":
            time_filter = f"DATE_FORMAT(c.create_date, '{time_unit}')"
            date_condition = f"c.create_date >= DATE_SUB(NOW(), INTERVAL {hours} HOUR)"
            start_time = datetime.now() - timedelta(hours=hours)
        else:
            time_filter = f"DATE_FORMAT(c.create_date, '{time_unit}')"
            date_condition = f"c.create_date >= DATE_SUB(CURDATE(), INTERVAL {days} DAY)"
            start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days-1)

        # 查询活跃学生数（按时间分组）- 改为按conversation统计
        query = f"""
            SELECT
                {time_filter} as time_label,
                COUNT(DISTINCT c.user_id) as active_count
            FROM conversation c
            JOIN user_tenant ut ON c.user_id = ut.user_id
            WHERE ut.tenant_id = %s
                AND ut.role = 'normal'
                AND ut.status = '1'
                AND {date_condition}
            GROUP BY time_label
            ORDER BY time_label
        """
        cursor.execute(query, (tenant_id,))
        results = cursor.fetchall()

        # 将查询结果转为字典，方便查找
        data_dict = {r["time_label"]: r["active_count"] for r in results}

        # 生成完整的时间序列
        data = []
        if time_range == "24h":
            current = start_time
            for _ in range(hours):
                time_label = current.strftime(date_format)
                data.append({
                    "time": time_label,
                    "count": data_dict.get(time_label, 0)
                })
                current += delta
        else:  # 7d 或 30d
            current = start_time
            for _ in range(days):
                time_label = current.strftime(date_format)
                data.append({
                    "time": time_label,
                    "count": data_dict.get(time_label, 0)
                })
                current += delta

        return True, data

    except Exception as e:
        return False, str(e)
    finally:
        cursor.close()
        conn.close()


def get_conversation_trend_chart(tenant_id: str, time_range: str = "24h"):
    """获取会话数趋势图数据"""
    from datetime import datetime, timedelta
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # 根据时间范围确定时间间隔和分组条件
        if time_range == "24h":
            # 过去24小时，按小时分组
            time_unit = "%Y-%m-%d %H:00:00"
            hours = 24
            delta = timedelta(hours=1)
            date_format = "%Y-%m-%d %H:00:00"
        elif time_range == "7d":
            # 过去7天，按天分组
            time_unit = "%Y-%m-%d"
            days = 7
            delta = timedelta(days=1)
            date_format = "%Y-%m-%d"
        else:  # 30d
            # 过去30天，按天分组
            time_unit = "%Y-%m-%d"
            days = 30
            delta = timedelta(days=1)
            date_format = "%Y-%m-%d"

        # 构建时间筛选条件
        if time_range == "24h":
            time_filter = f"DATE_FORMAT(c.create_date, '{time_unit}')"
            date_condition = f"c.create_date >= DATE_SUB(NOW(), INTERVAL {hours} HOUR)"
            start_time = datetime.now() - timedelta(hours=hours)
        else:
            time_filter = f"DATE_FORMAT(c.create_date, '{time_unit}')"
            date_condition = f"c.create_date >= DATE_SUB(CURDATE(), INTERVAL {days} DAY)"
            start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days-1)

        # 查询会话数趋势
        query = f"""
            SELECT
                {time_filter} as time_label,
                COUNT(*) as conversation_count
            FROM conversation c
            JOIN dialog d ON c.dialog_id = d.id
            WHERE d.tenant_id = %s
                AND {date_condition}
            GROUP BY time_label
            ORDER BY time_label
        """
        cursor.execute(query, (tenant_id,))
        results = cursor.fetchall()

        # 将查询结果转为字典，方便查找
        data_dict = {r["time_label"]: r["conversation_count"] for r in results}

        # 生成完整的时间序列
        data = []
        if time_range == "24h":
            current = start_time
            for _ in range(hours):
                time_label = current.strftime(date_format)
                data.append({
                    "time": time_label,
                    "count": data_dict.get(time_label, 0)
                })
                current += delta
        else:  # 7d 或 30d
            current = start_time
            for _ in range(days):
                time_label = current.strftime(date_format)
                data.append({
                    "time": time_label,
                    "count": data_dict.get(time_label, 0)
                })
                current += delta

        return True, data

    except Exception as e:
        return False, str(e)
    finally:
        cursor.close()
        conn.close()


def get_assistant_ranking(tenant_id: str, limit: int = 10, time_range: str = "24h"):
    """获取最受欢迎的AI助教排行榜"""
    import json
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        if time_range == "24h":
            date_condition = "c.create_date >= DATE_SUB(NOW(), INTERVAL 24 HOUR)"
        elif time_range == "7d":
            date_condition = "c.create_date >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
        else:
            date_condition = "c.create_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)"

        query = f"""
            SELECT
                d.id as assistant_id,
                d.name as assistant_name,
                d.icon as assistant_icon,
                c.reference
            FROM dialog d
            LEFT JOIN conversation c ON d.id = c.dialog_id AND {date_condition}
            WHERE d.tenant_id = %s AND d.status = '1'
        """
        cursor.execute(query, (tenant_id,))
        results = cursor.fetchall()

        assistant_stats = {}
        for row in results:
            assistant_id = row["assistant_id"]
            if assistant_id not in assistant_stats:
                assistant_stats[assistant_id] = {
                    "assistant_id": assistant_id,
                    "assistant_name": row["assistant_name"],
                    "assistant_icon": row["assistant_icon"],
                    "call_count": 0
                }

            if row["reference"]:
                try:
                    reference_data = json.loads(row["reference"])
                    if isinstance(reference_data, list):
                        for item in reference_data:
                            if isinstance(item, dict) and "total" in item:
                                assistant_stats[assistant_id]["call_count"] += item["total"]
                except (json.JSONDecodeError, TypeError, KeyError):
                    pass

        data = list(assistant_stats.values())
        data.sort(key=lambda x: x["call_count"], reverse=True)
        data = data[:limit]

        return True, data

    except Exception as e:
        return False, str(e)
    finally:
        cursor.close()
        conn.close()


def get_class_activity_ranking(tenant_id: str, limit: int = 10, time_range: str = "24h"):
    """获取班级活跃度排行榜"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        if time_range == "24h":
            date_condition = "conv.create_date >= DATE_SUB(NOW(), INTERVAL 24 HOUR)"
        elif time_range == "7d":
            date_condition = "conv.create_date >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
        else:
            date_condition = "conv.create_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)"

        query = f"""
            SELECT
                c.id as class_id,
                c.name as class_name,
                COUNT(DISTINCT conv.id) as conversation_count
            FROM class c
            LEFT JOIN user_class uc ON c.id = uc.class_id AND uc.role = 'student'
            LEFT JOIN conversation conv ON uc.user_id = conv.user_id AND {date_condition}
            WHERE c.tenant_id = %s AND c.status = '1'
            GROUP BY c.id, c.name
            ORDER BY conversation_count DESC
            LIMIT %s
        """
        cursor.execute(query, (tenant_id, limit))
        results = cursor.fetchall()

        data = [
            {
                "class_id": r["class_id"],
                "class_name": r["class_name"],
                "conversation_count": r["conversation_count"]
            }
            for r in results
        ]

        return True, data

    except Exception as e:
        return False, str(e)
    finally:
        cursor.close()
        conn.close()
