import requests

url = "https://api.siliconflow.cn/v1/chat/completions"

payload = {
    "model": "Qwen/Qwen2.5-7B-Instruct",
    "messages": [
        {
            "role": "user",
            "content": "1+1=?"
        }
    ]
}
headers = {
    "Authorization": "Bearer sk-ddmuwiogctbqpznflymvdrdbasdelejzahfhickpovhlcpzr",
    "Content-Type": "application/json"
}

response = requests.post(url, json=payload, headers=headers)

print(response.text)