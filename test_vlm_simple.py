"""
测试：图片放在 tool 返回结果中（多模态数组格式），发给 GPT-5.5
用法：python test_vlm_simple.py
"""
import json
import base64
from openai import OpenAI

# 配置
API_KEY = "sk-6613290e9d6176fac69aa6cd55552d495b1bfa670f5ffec4a29b833d5ca09a89"
BASE_URL = "https://ai.ovocloud.vip/v1"
MODEL = "gpt-5.5"

# ====== 在这里填你的图片路径 ======
IMAGE_PATH = "/Users/suojianhua/Downloads/page-4.png"
# ==================================

with open(IMAGE_PATH, "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode()

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# 工具定义
tools = [{
    "type": "function",
    "function": {
        "name": "extract_page_content",
        "description": "提取图片中的文字和内容信息",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "标题"},
                "text": {"type": "string", "description": "正文内容，逐字转录"},
                "summary": {"type": "string", "description": "一句话总结"}
            },
            "required": ["title", "text", "summary"]
        }
    }
}]

# 图片封装在 tool 返回结果中
messages = [
    {"role": "system", "content": "你是 OCR 助手。请使用 extract_page_content 工具提取 tool 返回的图片中的文字。"},
    {"role": "user", "content": "帮我获取第 4 页课件截图，看看上面写了什么。"},
    # 模拟助手调用了 search_ppt_pages
    {"role": "assistant", "content": None, "tool_calls": [
        {"id": "call_abc123", "type": "function",
         "function": {"name": "search_ppt_pages", "arguments": "{\"page_number\": 4}"}}
    ]},
    # tool 返回纯文本
    {"role": "tool", "tool_call_id": "call_abc123", "name": "search_ppt_pages",
     "content": "已获取第 4 页课件截图"},
    # 图片通过 user 消息传入（触发视觉编码）
    {"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
    ]},
]

print("=" * 60)
print("调用模型（tool返回文本 + user消息传图片）")
print("=" * 60)

response = client.chat.completions.create(
    model=MODEL,
    messages=messages,
    temperature=0.1
)

print(json.dumps(response.model_dump(), ensure_ascii=False, indent=2))
