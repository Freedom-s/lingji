"""
测试 LLM 带工具调用时的原始返回值。
"""
from openai import OpenAI

MODEL = "Qwen/Qwen3-VL-32B-Instruct"
API_KEY = "sk-ddmuwiogctbqpznflymvdrdbasdelejzahfhickpovhlcpzr"
BASE_URL = "https://api.siliconflow.cn/v1"

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

SYSTEM_PROMPT = """你是一个名为"灵机"的智能教学助手。如果学生询问具体的课程概念、知识点，你必须优先使用工具进行检索。"""

tools = [
    {
        "type": "function",
        "function": {
            "name": "list_documents",
            "description": "列出知识库中的所有文档",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hybrid_retrieve",
            "description": "混合检索课件页面",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "检索查询"},
                },
                "required": ["question"],
            },
        },
    },
]

messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": "你好啊"},
]

print(f"模型: {MODEL}")
print(f"问题: {messages[-1]['content']}")
print("=" * 70)

response = client.chat.completions.create(
    model=MODEL,
    messages=messages,
    tools=tools,
    tool_choice="auto",
    temperature=0.0,
    top_p=1.0,
)

import json
raw = response.model_dump()
print(json.dumps(raw, indent=2, ensure_ascii=False))

"""
需要调用工具的时候
{
"finish_reason": "stop",
"index": 0,
"logprobs": null,
"message": {
    "content": "",
    "refusal": null,
    "role": "assistant",
    "annotations": null,
    "audio": null,
    "function_call": null,
    "tool_calls": null,
    "reasoning_content": "<tool_call>\n{\"name\": \"hybrid_retrieve\", \"arguments\": {\"question\": \"机器学习的基本概念\"}}\n</tool_call>"
}
不需要调用工具的时候
{
"finish_reason": "stop",
"index": 0,
"logprobs": null,
"message": {
    "content": "",
    "refusal": null,
    "role": "assistant",
    "annotations": null,
    "audio": null,
    "function_call": null,
    "tool_calls": null,
    "reasoning_content": "你好！我是灵机，你的智能教学助手。有什么课程内容或知识点需要我帮你查找或讲解吗？"
    }
}

"""