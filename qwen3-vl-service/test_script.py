import requests
import json
import time

url = "http://localhost:8000/v1/embeddings"

# 构造混合 Batch 请求：包含纯文本、网络图片、以及（模拟的）错误链接
# 这里是需要把本地的图片给base64吗？还是提供一个minio的地址？
payload = {
    "model": "qwen3-vl",
    "input": [
        "https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen-VL/assets/demo.jpeg",
        "555",
        "A woman a joyful moment with her golden retriever on a sun-drenched beach at sunset, as the dog offers its paw in a heartwarming display of companionship and trust."
        #"minio://8754d45ef11711f0affc420839d2c59a/886c4a52f11711f0affc420839d2c59a/pages/0001.jpg"
    ]
}

print("发送请求中...")
start_time = time.time()

try:
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        data = response.json()
        print(f"✅ 成功! 耗时: {time.time() - start_time:.2f}s")
        print(f"返回向量数量: {len(data['data'])}")
        print(f"向量维度: {len(data['data'][0]['embedding'])}") # 应该是 2048
        for item in data:
            print(data)
    else:
        print(f"❌ 失败: {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"❌ 请求错误: {e}")