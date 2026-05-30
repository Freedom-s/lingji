import requests
import json
import time

url = "http://localhost:8001/v1/rerank"

payload = {
    "query": """
To endow the model with universal representation capabilities across diverse modalities, tasks, and
domains, we curated a massive-scale dataset. The distribution of different categories within the dataset
is illustrated in Figure 3. However, both publicly available and proprietary in-house data exhibit
significant imbalances and, in specific scenarios, notable scarcity across these dimensions. To address
these challenges, we leverage data synthesis to construct a balanced training corpus that ensures robust
coverage across all modalities, tasks, and domains.""",
    "documents": [
        "To endow the model with universal representation capabilities across diverse modalities, tasks",
        "To address these challenges, we leverage data synthesis to construct a balanced training corpus that ensures robust coverage across all modalities, tasks, and domains."
    ]
}

print("发送 Rerank 请求...")
start = time.time()
try:
    resp = requests.post(url, json=payload)
    if resp.status_code == 200:
        data = resp.json()
        print(f"✅ 成功! 耗时: {time.time()-start:.2f}s")
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(f"❌ 失败: {resp.text}")
except Exception as e:
    print(f"Error: {e}")