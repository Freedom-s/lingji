#!/usr/bin/env python3
"""
导出 RAGFlow 系统所有数据库表结构到 Markdown 文件（DESCRIBE 表格格式）。
"""

import pymysql

DB_CONFIG = {
    "host": "localhost",
    "port": 5455,
    "user": "root",
    "password": "infini_rag_flow",
    "database": "rag_flow",
    "charset": "utf8mb4",
}

import os
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "database_schema.md")


def main():
    conn = pymysql.connect(**DB_CONFIG)

    try:
        with conn.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]

            lines = [
                "# RAGFlow 数据库表结构",
                "",
                f"> 数据库: `{DB_CONFIG['database']}` | 主机: `{DB_CONFIG['host']}:{DB_CONFIG['port']}` | 表数量: {len(tables)}",
                "",
                "---",
                "",
            ]

            for table_name in tables:
                cursor.execute(f"DESCRIBE `{table_name}`")
                rows = cursor.fetchall()

                lines.append(f"## `{table_name}`")
                lines.append("")
                lines.append("| Field | Type | Null | Key | Default | Extra |")
                lines.append("|-------|------|------|-----|---------|-------|")

                for row in rows:
                    field, type_, null, key, default, extra = row
                    null = null or ""
                    key = key or ""
                    default = default if default is not None else "NULL"
                    extra = extra or ""
                    lines.append(f"| {field} | {type_} | {null} | {key} | {default} | {extra} |")

                lines.append("")

            # 确保 docs 目录存在
            os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

            print(f"表结构已导出到: {OUTPUT_FILE}")
            print(f"共导出 {len(tables)} 张表")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
