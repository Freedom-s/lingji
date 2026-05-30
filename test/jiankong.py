import pandas as pd
from sqlalchemy import create_engine, text
import time
import os
from colorama import init, Fore, Style

# 初始化颜色打印
init(autoreset=True)

# ================= ⚙️ 配置区 =================
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5455,
    "user": "root",             # 数据库用户名
    "password": "infini_rag_flow", # 数据库密码
    "database": "rag_flow",  # 你的数据库名
    "charset": "utf8mb4"
}

def get_db_engine():
    """创建数据库连接"""
    conn_str = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}?charset={DB_CONFIG['charset']}"
    return create_engine(conn_str)

def get_all_tables(engine):
    """获取数据库中所有的表名"""
    sql = "SHOW TABLES;"
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        return [row[0] for row in result]

def take_snapshot(engine, table_list):
    """
    对所有表进行快照
    返回格式: {'users': DataFrame, 'orders': DataFrame, ...}
    """
    snapshot = {}
    print(Fore.YELLOW + f"📸 正在扫描全库 ({len(table_list)} 张表)...", end="\r")
    
    for table in table_list:
        try:
            # 读取全表数据
            df = pd.read_sql(f"SELECT * FROM `{table}`", engine)
            snapshot[table] = df
        except Exception as e:
            # 某些表可能无法读取（如权限问题），跳过
            snapshot[table] = pd.DataFrame()
            
    print(Fore.GREEN + f"✅ 全库扫描完成！已缓存 {len(table_list)} 张表的状态。      ")
    return snapshot

def find_diff(old_snapshot, new_snapshot):
    """对比两份快照，找出所有表的新增数据"""
    changes_found = False
    
    for table_name, df_new in new_snapshot.items():
        df_old = old_snapshot.get(table_name, pd.DataFrame())
        
        # 如果新旧都为空，跳过
        if df_new.empty and df_old.empty:
            continue

        # 核心对比逻辑：找出 df_new 中有，但 df_old 中没有的行
        if df_old.empty:
            added_rows = df_new
        else:
            # 使用 merge indicator 找出差异
            # 这种方法比直接 drop_duplicates 更准确，因为它比较整行
            try:
                merged = df_new.merge(df_old, how='outer', indicator=True)
                added_rows = merged[merged['_merge'] == 'left_only'].drop(columns=['_merge'])
            except Exception:
                # 如果表结构发生了变化（列不对齐），这种对比会报错，简单处理
                added_rows = pd.DataFrame()

        if not added_rows.empty:
            changes_found = True
            print(Fore.CYAN + "=" * 60)
            print(Fore.CYAN + f"🚨 发现变化！表名: [{table_name}]  (新增 {len(added_rows)} 行)")
            print(Fore.CYAN + "=" * 60)
            print(Style.BRIGHT + str(added_rows))
            print("\n")

    if not changes_found:
        print(Fore.RED + "😴 整个数据库静悄悄，没有任何数据增加。")

def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print(Fore.MAGENTA + "🔍 全局数据库监控工具 (All Tables Monitor)")
    print(Fore.WHITE + "------------------------------------------------")
    
    engine = get_db_engine()
    
    # 1. 获取表清单
    try:
        tables = get_all_tables(engine)
    except Exception as e:
        print(Fore.RED + f"连接失败: {e}")
        return

    # 2. 初始快照
    print(Fore.WHITE + "\n[阶段 1] 建立基准...")
    snapshot_start = take_snapshot(engine, tables)
    
    while True:
        # 3. 等待用户操作
        input(Fore.MAGENTA + "\n>>> 请去执行你的网页操作，完成后按【回车键】全库搜查...\n")
        
        # 4. 新快照
        print(Fore.WHITE + "[阶段 2] 获取最新状态...")
        snapshot_end = take_snapshot(engine, tables)
        
        # 5. 对比并输出
        print(Fore.WHITE + "正在比对差异...")
        find_diff(snapshot_start, snapshot_end)
        
        # 6. 询问是否重置
        print(Fore.WHITE + "-" * 50)
        cmd = input("输入 'r' 更新基准点(以此为起点测下一步)，直接回车保持原起点: ").strip().lower()
        if cmd == 'r':
            snapshot_start = snapshot_end
            print(Fore.BLUE + "ℹ️  基准已更新。")
        else:
            print(Fore.BLUE + "ℹ️  基准保持不变。")

if __name__ == "__main__":
    main()