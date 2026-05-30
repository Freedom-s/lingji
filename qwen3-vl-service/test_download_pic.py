import asyncio
import aiohttp
from minio import Minio
# 注意：这里导入整个 app 模块，而不是具体的变量，方便我们要修改它的全局变量
import app 
from app import fetch_image, MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_SECURE

async def test_fetch_image():
    print("--- 开始初始化测试环境 ---")

    # 1. 手动初始化 MinIO 客户端
    # 注意：这里我们把初始化好的 client 赋值给 app.minio_client
    app.minio_client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=MINIO_SECURE
    )
    print("✅ MinIO 客户端已注入到 app 模块")

    # 2. 手动初始化 HTTP Session (aiohttp)
    # 必须在 async 函数中初始化，并赋值给 app.http_session
    async with aiohttp.ClientSession() as session:
        app.http_session = session
        print("✅ HTTP Session 已注入到 app 模块")

        # 3. 定义测试用例
        test_cases = [
            # 修正了 tps -> https
            "https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen-VL/assets/demo.jpeg",
            
            # 你的 MinIO 路径 (确保路径和 Bucket 权限正确)
            "minio://8754d45ef11711f0affc420839d2c59a/886c4a52f11711f0affc420839d2c59a/pages/0001.jpg",
            
            # 边界情况
            "",  
            "invalid://url",
        ]

        print("\n--- 开始执行测试 ---")
        for url in test_cases:
            print(f"\n🔍 Testing URL: {url}")
            try:
                # 调用 app.py 中的函数
                image = await fetch_image(url)
                
                if image:
                    print(f"   🎉 成功! 尺寸: {image.size}, 模式: {image.mode}")
                    image.show() # 如果在服务器上运行，请注释掉这行
                else:
                    print("   ⚠️  下载失败 (返回 None)")
            except Exception as e:
                print(f"   ❌ 发生异常: {e}")

if __name__ == "__main__":
    asyncio.run(test_fetch_image())