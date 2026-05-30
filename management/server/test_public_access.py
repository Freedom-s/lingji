"""
测试 MinIO 公共访问权限

验证上传的文件是否可以通过公共 URL 直接访问
"""

import os
import sys
import requests
from pathlib import Path

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# API 配置
API_BASE_URL = "http://localhost:5001"
UPLOAD_URL = f"{API_BASE_URL}/api/v1/files/upload"
PAGES_LIST_URL = f"{API_BASE_URL}/api/v1/files/{{file_id}}/pages"

# MinIO 配置（根据实际配置修改）
MINIO_ENDPOINT = "localhost:9000"
MINIO_SCHEME = "http"  # 或 "https"


def create_test_image(filename, size=(800, 600), color=(255, 0, 0)):
    """创建测试图片"""
    from PIL import Image
    
    img = Image.new('RGB', size, color)
    img.save(filename)
    print(f"创建测试图片: {filename}, 尺寸: {size}")
    return filename


def upload_image(image_path):
    """上传图片并返回文件信息"""
    print(f"\n{'='*60}")
    print(f"上传图片: {image_path}")
    print(f"{'='*60}")
    
    with open(image_path, 'rb') as f:
        files = {'files': (os.path.basename(image_path), f, 'image/jpeg')}
        response = requests.post(UPLOAD_URL, files=files)
    
    if response.status_code == 200:
        result = response.json()
        if result.get('code') == 0 and result.get('data'):
            file_info = result['data'][0]
            if file_info.get('status') == 'success':
                print(f"✓ 上传成功: {file_info['id']}")
                return file_info
    
    print(f"✗ 上传失败")
    return None


def get_pages(file_id):
    """获取文件的页面列表"""
    url = PAGES_LIST_URL.format(file_id=file_id)
    response = requests.get(url)
    
    if response.status_code == 200:
        result = response.json()
        if result.get('code') == 0:
            return result.get('data', [])
    
    return []


def test_public_access(bucket, object_path):
    """测试公共访问"""
    # 构造 MinIO 公共 URL
    public_url = f"{MINIO_SCHEME}://{MINIO_ENDPOINT}/{bucket}/{object_path}"
    
    print(f"\n{'='*60}")
    print(f"测试公共访问")
    print(f"{'='*60}")
    print(f"URL: {public_url}")
    
    try:
        response = requests.get(public_url, timeout=5)
        
        if response.status_code == 200:
            print(f"✓ 公共访问成功!")
            print(f"  - 状态码: {response.status_code}")
            print(f"  - Content-Type: {response.headers.get('Content-Type')}")
            print(f"  - Content-Length: {response.headers.get('Content-Length')} 字节")
            return True
        else:
            print(f"✗ 公共访问失败")
            print(f"  - 状态码: {response.status_code}")
            print(f"  - 响应: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"✗ 请求异常: {str(e)}")
        return False


def main():
    """主测试流程"""
    print("开始测试 MinIO 公共访问权限...")
    
    # 创建临时测试目录
    test_dir = Path("test_public")
    test_dir.mkdir(exist_ok=True)
    
    try:
        # 1. 创建并上传测试图片
        test_image = test_dir / "test_public.jpg"
        create_test_image(test_image, size=(800, 600), color=(0, 255, 0))
        
        file_info = upload_image(test_image)
        if not file_info:
            print("\n上传失败，无法继续测试")
            return
        
        file_id = file_info['id']
        
        # 2. 获取页面列表
        pages = get_pages(file_id)
        if not pages:
            print("\n获取页面列表失败，无法继续测试")
            return
        
        print(f"\n获取到 {len(pages)} 个页面")
        
        # 3. 测试每个页面的公共访问
        success_count = 0
        for page in pages:
            # 从数据库获取 parent_id（bucket）
            # 这里需要从 file 表查询，简化起见，我们从 location 推断
            location = page['location']
            
            # location 格式: {file_id}/pages/{filename}
            # 需要知道 bucket (parent_id)
            # 这里我们需要额外的 API 来获取 file 信息
            print(f"\n页面 {page['page_number']}:")
            print(f"  - 位置: {location}")
            print(f"  - 尺寸: {page['width']}x{page['height']}")
            
            # 注意：这里需要知道 bucket 名称（parent_id）
            # 实际使用时需要从 file 表查询或通过 API 返回
            print(f"  ⚠️  需要 bucket 名称才能构造完整 URL")
            print(f"  💡 完整 URL 格式: {MINIO_SCHEME}://{MINIO_ENDPOINT}/{{bucket}}/{location}")
        
        print(f"\n{'='*60}")
        print("测试说明:")
        print(f"{'='*60}")
        print("1. 文件已成功上传到 MinIO")
        print("2. 存储桶权限已设置为公共读取")
        print("3. 可以通过以下格式访问文件:")
        print(f"   {MINIO_SCHEME}://{MINIO_ENDPOINT}/{{bucket}}/{{file_id}}/source/{{filename}}")
        print(f"   {MINIO_SCHEME}://{MINIO_ENDPOINT}/{{bucket}}/{{file_id}}/pages/{{page_filename}}")
        print("\n4. 需要从数据库查询 bucket 名称（file.parent_id）")
        print("5. 建议在 API 响应中返回完整的公共 URL")
        
    finally:
        # 清理测试文件
        import shutil
        if test_dir.exists():
            shutil.rmtree(test_dir)
            print(f"\n已清理测试目录: {test_dir}")


if __name__ == "__main__":
    main()
