"""
测试文件上传功能

使用方法：
python test_upload.py
"""

import requests
import os

# 配置
API_URL = "http://localhost:5000/api/v1/files/upload"
TEST_FILE = "test_document.pdf"  # 替换为实际测试文件路径

def test_upload():
    """测试文件上传"""
    if not os.path.exists(TEST_FILE):
        print(f"错误：测试文件不存在: {TEST_FILE}")
        print("请创建一个测试文件或修改 TEST_FILE 变量")
        return
    
    print(f"开始上传文件: {TEST_FILE}")
    
    with open(TEST_FILE, "rb") as f:
        files = {"files": (os.path.basename(TEST_FILE), f)}
        
        try:
            response = requests.post(API_URL, files=files)
            
            print(f"\n响应状态码: {response.status_code}")
            print(f"响应内容: {response.json()}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0 and data.get("data"):
                    file_info = data["data"][0]
                    print(f"\n✅ 上传成功！")
                    print(f"文件ID: {file_info.get('id')}")
                    print(f"文件名: {file_info.get('name')}")
                    print(f"文件大小: {file_info.get('size')} 字节")
                    print(f"页数: {file_info.get('pages')}")
                    
                    # 测试获取页面列表
                    file_id = file_info.get('id')
                    test_get_pages(file_id)
                else:
                    print(f"\n❌ 上传失败: {data.get('message')}")
            else:
                print(f"\n❌ 请求失败")
                
        except Exception as e:
            print(f"\n❌ 错误: {str(e)}")


def test_get_pages(file_id):
    """测试获取页面列表"""
    print(f"\n测试获取页面列表...")
    
    try:
        response = requests.get(f"http://localhost:5000/api/v1/files/{file_id}/pages")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                pages = data.get("data", [])
                print(f"✅ 获取到 {len(pages)} 个页面")
                for page in pages[:3]:  # 只显示前3页
                    print(f"  - 页码 {page['page_number']}: {page['width']}x{page['height']} px, {page['size']} 字节")
            else:
                print(f"❌ 获取失败: {data.get('message')}")
        else:
            print(f"❌ 请求失败: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 错误: {str(e)}")


if __name__ == "__main__":
    print("=" * 60)
    print("文件上传功能测试")
    print("=" * 60)
    test_upload()
    print("\n" + "=" * 60)
