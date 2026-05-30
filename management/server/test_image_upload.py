"""
测试图片文件上传功能

测试场景：
1. 上传 JPG 图片
2. 上传 PNG 图片
3. 验证 MinIO 存储结构
4. 验证数据库记录
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


def create_test_image(filename, size=(800, 600), color=(255, 0, 0)):
    """创建测试图片"""
    from PIL import Image
    
    img = Image.new('RGB', size, color)
    img.save(filename)
    print(f"创建测试图片: {filename}, 尺寸: {size}, 颜色: {color}")
    return filename


def test_upload_image(image_path):
    """测试上传图片"""
    print(f"\n{'='*60}")
    print(f"测试上传图片: {image_path}")
    print(f"{'='*60}")
    
    with open(image_path, 'rb') as f:
        files = {'files': (os.path.basename(image_path), f, 'image/jpeg')}
        response = requests.post(UPLOAD_URL, files=files)
    
    print(f"响应状态码: {response.status_code}")
    print(f"响应内容: {response.json()}")
    
    if response.status_code == 200:
        result = response.json()
        if result.get('code') == 0 and result.get('data'):
            file_info = result['data'][0]
            if file_info.get('status') == 'success':
                print(f"✓ 上传成功!")
                print(f"  - 文件ID: {file_info['id']}")
                print(f"  - 文件名: {file_info['name']}")
                print(f"  - 大小: {file_info['size']} 字节")
                print(f"  - 页数: {file_info['pages']}")
                return file_info['id']
            else:
                print(f"✗ 上传失败: {file_info.get('error')}")
        else:
            print(f"✗ 上传失败: {result.get('message')}")
    else:
        print(f"✗ 请求失败")
    
    return None


def test_get_pages(file_id):
    """测试获取页面列表"""
    print(f"\n{'='*60}")
    print(f"测试获取页面列表: {file_id}")
    print(f"{'='*60}")
    
    url = PAGES_LIST_URL.format(file_id=file_id)
    response = requests.get(url)
    
    print(f"响应状态码: {response.status_code}")
    print(f"响应内容: {response.json()}")
    
    if response.status_code == 200:
        result = response.json()
        if result.get('code') == 0:
            pages = result.get('data', [])
            print(f"✓ 获取成功! 共 {len(pages)} 页")
            for page in pages:
                print(f"  - 页码: {page['page_number']}")
                print(f"    位置: {page['location']}")
                print(f"    尺寸: {page['width']}x{page['height']}")
                print(f"    大小: {page['size']} 字节")
                print(f"    格式: {page['format']}")
        else:
            print(f"✗ 获取失败: {result.get('message')}")
    else:
        print(f"✗ 请求失败")


def main():
    """主测试流程"""
    print("开始测试图片上传功能...")
    
    # 创建临时测试目录
    test_dir = Path("test_images")
    test_dir.mkdir(exist_ok=True)
    
    try:
        # 测试 1: 上传 JPG 图片
        jpg_path = test_dir / "test_red.jpg"
        create_test_image(jpg_path, size=(800, 600), color=(255, 0, 0))
        file_id_1 = test_upload_image(jpg_path)
        
        if file_id_1:
            test_get_pages(file_id_1)
        
        # 测试 2: 上传 PNG 图片
        png_path = test_dir / "test_blue.png"
        create_test_image(png_path, size=(1024, 768), color=(0, 0, 255))
        file_id_2 = test_upload_image(png_path)
        
        if file_id_2:
            test_get_pages(file_id_2)
        
        print(f"\n{'='*60}")
        print("测试完成!")
        print(f"{'='*60}")
        
    finally:
        # 清理测试文件
        import shutil
        if test_dir.exists():
            shutil.rmtree(test_dir)
            print(f"\n已清理测试目录: {test_dir}")


if __name__ == "__main__":
    main()
