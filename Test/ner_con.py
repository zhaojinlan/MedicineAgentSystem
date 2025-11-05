import requests

url = "https://zjlchat-ner.vip.cpolar.cn/predict"
data = {"text": "当出现组织缺血性坏死时，可出现皮肤大片瘀斑、张力升高、水泡或血泡融合、坏死破溃、皮 下捻发音、 皮肤发黑或呈暗红色， 病灶范围扩大蔓延 [10,20,34-35] 。 一项系统评价与 Meta 分析检索 1980 -2013 年 9 个病例系列 研究， 共计 1 463 例 NSTIs 患者， NSTIs 早期出现肿胀（ 81% ） 、 疼痛（ 79% ） 、红斑（ 71% ）和发热（ 44% ） [20] 。一项前瞻性 研究纳入急诊科 2015 年 4 月至 2018 年 8 月 187 例 NSTIs 患者， 出现浆液性大疱患者占 18.7% ，出现出血性大疱占 21.9% ， 这两组与无大疱患者相比更容易出现皮肤坏死和休克，且出 血性大疱患者截肢率发生最高 [36]"}
headers = {"Content-Type": "application/json"}

try:
    response = requests.post(url, json=data, headers=headers, timeout=30)
    
    # 打印状态码
    print(f"状态码: {response.status_code}")
    
    # 打印响应头
    print(f"响应头: {response.headers}")
    
    # 打印原始响应内容
    print(f"原始响应内容: {response.text}")
    
    # 检查状态码
    response.raise_for_status()
    
    # 尝试解析 JSON
    result = response.json()
    print(f"\nJSON 响应: {result}")
    
except requests.exceptions.ConnectionError as e:
    print(f"连接错误: {e}")
except requests.exceptions.Timeout as e:
    print(f"请求超时: {e}")
except requests.exceptions.HTTPError as e:
    print(f"HTTP 错误: {e}")
except requests.exceptions.JSONDecodeError as e:
    print(f"JSON 解析错误: {e}")
    print(f"响应内容不是有效的 JSON 格式")
except Exception as e:
    print(f"其他错误: {e}")