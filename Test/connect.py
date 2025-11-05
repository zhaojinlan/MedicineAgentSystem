import ollama

# client = ollama.Client(host='https://zjlchat.vip.cpolar.cn')  # 1. 先建客户端
# for chunk in client.generate(model='qwen2.5:14b',
#                              prompt='用一句话解释什么是深度学习',
#                              stream=True):
#     print(chunk['response'], end='', flush=True)


client = ollama.Client(host='http://localhost:11434')  # 1. 先建客户端

for chunk in client.generate(model='deepseek-r1:1.5b',
                             prompt='用一句话解释什么是深度学习',
                             stream=True):
    print(chunk['response'], end='', flush=True)