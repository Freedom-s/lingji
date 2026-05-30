"""
为现有的 MinIO 存储桶设置公共访问权限

使用场景：
- 系统升级后，需要为已有的存储桶设置公共访问权限
- 批量修改存储桶权限

运行方式：
    python migrate_bucket_permissions.py
"""

import os
import sys
import json

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection, get_minio_client


def get_all_buckets_from_db():
    """从数据库获取所有唯一的存储桶名称（parent_id）"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT DISTINCT parent_id FROM file WHERE parent_id IS NOT NULL")
        buckets = cursor.fetchall()
        return [b['parent_id'] for b in buckets]
    finally:
        cursor.close()
        conn.close()


def set_bucket_public_policy(minio_client, bucket_name):
    """为指定存储桶设置公共读取权限"""
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": "*"},
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
            }
        ]
    }
    
    try:
        minio_client.set_bucket_policy(bucket_name, json.dumps(policy))
        return True, None
    except Exception as e:
        return False, str(e)


def main():
    """主函数"""
    print("="*60)
    print("MinIO 存储桶权限迁移工具")
    print("="*60)
    print()
    
    # 1. 获取所有存储桶
    print("步骤 1: 从数据库获取存储桶列表...")
    try:
        buckets = get_all_buckets_from_db()
        print(f"✓ 找到 {len(buckets)} 个存储桶")
        for bucket in buckets:
            print(f"  - {bucket}")
    except Exception as e:
        print(f"✗ 获取存储桶列表失败: {str(e)}")
        return
    
    if not buckets:
        print("\n没有找到需要处理的存储桶")
        return
    
    print()
    
    # 2. 连接 MinIO
    print("步骤 2: 连接 MinIO...")
    try:
        minio_client = get_minio_client()
        print("✓ MinIO 连接成功")
    except Exception as e:
        print(f"✗ MinIO 连接失败: {str(e)}")
        return
    
    print()
    
    # 3. 设置权限
    print("步骤 3: 设置存储桶公共访问权限...")
    success_count = 0
    failed_count = 0
    
    for bucket in buckets:
        # 检查存储桶是否存在
        if not minio_client.bucket_exists(bucket):
            print(f"⚠️  存储桶不存在，跳过: {bucket}")
            failed_count += 1
            continue
        
        # 设置权限
        success, error = set_bucket_public_policy(minio_client, bucket)
        
        if success:
            print(f"✓ 设置成功: {bucket}")
            success_count += 1
        else:
            print(f"✗ 设置失败: {bucket}")
            print(f"  错误: {error}")
            failed_count += 1
    
    print()
    print("="*60)
    print("迁移完成")
    print("="*60)
    print(f"总计: {len(buckets)} 个存储桶")
    print(f"成功: {success_count} 个")
    print(f"失败: {failed_count} 个")
    print()
    
    if success_count > 0:
        print("✓ 存储桶现在可以通过公共 URL 访问")
        print("  格式: http://{minio_endpoint}/{bucket}/{object_path}")
        print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n操作已取消")
    except Exception as e:
        print(f"\n✗ 发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
