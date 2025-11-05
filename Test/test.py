import requests
import json

url = "https://zjlchat.vip.cpolar.cn/api/embeddings"
headers = {"Content-Type": "application/json"}
data = {
    "model": "qllama/bge-m3:f16",
    "prompt": "你好，我是小明，我是一个学生，我正在学习Python编程语言"  # 也可以是文本列表，如 ["text1", "text2"]
}

response = requests.post(url, headers=headers, data=json.dumps(data))
print(response.status_code)
print(response.json())
