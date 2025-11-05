import os
from sentence_transformers import SentenceTransformer

# 创建模型存储目录
model_dir = r"O:\MyProject\RAG\models"
os.makedirs(model_dir, exist_ok=True)

# 下载并保存M3E-Base模型到本地
print("正在下载M3E-Base中文向量化模型...")
model = SentenceTransformer('moka-ai/m3e-base')
model_path = os.path.join(model_dir, "m3e-base")

# 保存到本地指定目录
model.save(model_path)
print(f"模型已成功保存到: {model_path}")

# 验证模型是否可以加载
print("验证模型加载...")
reloaded = SentenceTransformer(model_path)
print("模型验证成功！本地部署完成。")