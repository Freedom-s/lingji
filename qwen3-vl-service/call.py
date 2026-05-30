# 第一种方式：
import openai

client = openai.Client(
    api_key="empty", 
    base_url="http://localhost:8000/v1"
)

resp = client.embeddings.create(
    model="qwen3-vl",
    input="一只在夕阳下奔跑的狗"
)
print(len(resp.data[0].embedding)) # 2048



# 第二种方式，多模态的情况
import openai
import json

client = openai.Client(api_key="empty", base_url="http://localhost:8000/v1")

# 构造多模态输入
multimodal_input = json.dumps({
    "text": "描述这张图片", 
    "image": "https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen-VL/assets/demo.jpeg"
})

resp = client.embeddings.create(
    model="qwen3-vl",
    input=multimodal_input # 传入 JSON 字符串
)

vector = resp.data[0].embedding
print(f"获得向量维度: {len(vector)}")


# 第三种方式：直接使用request请求
import requests

payload = {
    "model": "qwen3-vl",
    "input": [
        {"text": "纯文本查询"},
        {"image": "https://example.com/image.jpg", "text": "带图查询"}
    ]
}

response = requests.post("http://localhost:8000/v1/embeddings", json=payload)
print(response.json())