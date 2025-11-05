import requests
import json

url = "https://zjlchat.vip.cpolar.cn/v1/chat/completions"
headers = {"Content-Type": "application/json"}
data = {
    "model": "qwen2.5:14b",
    "messages": [
        {"role": "user", "content": "你好，我是小明，我是一个学生，我正在学习Python编程语言"}
    ]
}

response = requests.post(url, headers=headers, data=json.dumps(data))
print(response.status_code)
print(response.json())