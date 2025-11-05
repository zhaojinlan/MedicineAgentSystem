import redis
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
import json

class RedisVectorDB:
    def __init__(self, host='localhost', port=6379, password=None, embedding_model_path=r"O:\MyProject\RAG\models\m3e-base"):
        """
        初始化Redis向量数据库
        
        Args:
            host: Redis主机地址
            port: Redis端口
            password: Redis密码
            embedding_model_path: 本地embedding模型路径
        """
        # 连接Redis
        self.redis_client = redis.Redis(
            host=host,
            port=port,
            password=password,
            decode_responses=True
        )
        
        # 加载本地embedding模型
        print("正在加载embedding模型...")
        self.embedding_model = SentenceTransformer(embedding_model_path)
        print("模型加载完成!")
        
        # 向量维度
        self.vector_dimension = 768  # m3e-base模型的向量维度
        
    def create_index(self, index_name: str, distance_metric: str = "COSINE"):
        """
        创建向量索引
        
        Args:
            index_name: 索引名称
            distance_metric: 距离度量方式 (COSINE, L2, IP)
        """
        try:
            # 检查索引是否已存在
            existing_indexes = self.redis_client.execute_command("FT._LIST")
            if index_name.encode() in existing_indexes:
                print(f"索引 '{index_name}' 已存在")
                return
            
            # 创建向量索引
            schema = {
                "vector": {
                    "type": "FLOAT32",
                    "DIM": self.vector_dimension,
                    "DISTANCE_METRIC": distance_metric
                },
                "text": {"type": "TEXT"},
                "metadata": {"type": "TEXT"}
            }
            
            # 使用RedisSearch创建索引
            self.redis_client.execute_command(
                "FT.CREATE", index_name, "ON", "HASH", "PREFIX", "1", f"vec:{index_name}:",
                "SCHEMA", "vector", "VECTOR", "FLAT", "6", 
                "TYPE", "FLOAT32", 
                "DIM", self.vector_dimension, 
                "DISTANCE_METRIC", distance_metric,
                "text", "TEXT",
                "metadata", "TEXT"
            )
            print(f"索引 '{index_name}' 创建成功")
            
        except Exception as e:
            print(f"创建索引时出错: {e}")

    def get_embedding(self, text: str) -> List[float]:
        """
        获取文本的向量嵌入
        
        Args:
            text: 输入文本
            
        Returns:
            向量嵌入列表
        """
        embedding = self.embedding_model.encode(text)
        return embedding.tolist()

    def add_vector(self, index_name: str, key: str, text: str, metadata: Dict = None):
        """
        添加向量到数据库
        
        Args:
            index_name: 索引名称
            key: 唯一标识符
            text: 文本内容
            metadata: 元数据
        """
        try:
            # 获取向量嵌入
            vector = self.get_embedding(text)
            
            # 准备数据
            pipeline = self.redis_client.pipeline()
            
            # 存储向量数据
            redis_key = f"vec:{index_name}:{key}"
            pipeline.hset(redis_key, mapping={
                "vector": np.array(vector, dtype=np.float32).tobytes(),
                "text": text,
                "metadata": json.dumps(metadata or {})
            })
            
            pipeline.execute()
            print(f"向量 '{key}' 添加成功")
            
        except Exception as e:
            print(f"添加向量时出错: {e}")

    def search_similar(self, index_name: str, query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        搜索相似向量
        
        Args:
            index_name: 索引名称
            query_text: 查询文本
            top_k: 返回最相似的数量
            
        Returns:
            相似结果列表
        """
        try:
            # 获取查询文本的向量
            query_vector = self.get_embedding(query_text)
            
            # 构建查询
            query = (
                f"*=>[KNN {top_k} @vector $query_vector AS vector_score]"
            )
            
            # 执行向量搜索
            results = self.redis_client.execute_command(
                "FT.SEARCH", index_name, query,
                "PARAMS", "2", "query_vector", np.array(query_vector, dtype=np.float32).tobytes(),
                "DIALECT", "2",
                "SORTBY", "vector_score",
                "RETURN", "3", "text", "metadata", "vector_score",
                "LIMIT", "0", str(top_k)
            )
            
            # 解析结果
            similar_items = []
            if results and len(results) > 1:
                total_results = results[0]
                for i in range(1, len(results), 2):
                    item_key = results[i]
                    item_data = results[i + 1]
                    
                    item_dict = {}
                    for j in range(0, len(item_data), 2):
                        field = item_data[j]
                        value = item_data[j + 1]
                        item_dict[field] = value
                    
                    # 转换分数（距离越小越相似）
                    similarity_score = 1 - float(item_dict.get('vector_score', 0))
                    
                    similar_items.append({
                        'key': item_key,
                        'text': item_dict.get('text', ''),
                        'metadata': json.loads(item_dict.get('metadata', '{}')),
                        'score': similarity_score
                    })
            
            return similar_items
            
        except Exception as e:
            print(f"搜索时出错: {e}")
            return []

    def batch_add_vectors(self, index_name: str, items: List[Dict]):
        """
        批量添加向量
        
        Args:
            index_name: 索引名称
            items: 包含key, text, metadata的字典列表
        """
        pipeline = self.redis_client.pipeline()
        
        for item in items:
            key = item['key']
            text = item['text']
            metadata = item.get('metadata', {})
            
            # 获取向量嵌入
            vector = self.get_embedding(text)
            
            # 存储向量数据
            redis_key = f"vec:{index_name}:{key}"
            pipeline.hset(redis_key, mapping={
                "vector": np.array(vector, dtype=np.float32).tobytes(),
                "text": text,
                "metadata": json.dumps(metadata)
            })
        
        pipeline.execute()
        print(f"批量添加了 {len(items)} 个向量")

    def get_index_info(self, index_name: str):
        """获取索引信息"""
        try:
            info = self.redis_client.execute_command("FT.INFO", index_name)
            return info
        except Exception as e:
            print(f"获取索引信息时出错: {e}")
            return None

# 使用示例
def main():
    # 初始化向量数据库
    vector_db = RedisVectorDB(
        host='localhost',
        port=6379,
        password=None,
        embedding_model_path=r"O:\MyProject\RAG\models\m3e-base"
    )
    
    # 创建索引
    index_name = "documents"
    vector_db.create_index(index_name)
    
    # 添加一些示例数据
    sample_data = [
        {
            "key": "doc1",
            "text": "机器学习是人工智能的重要分支",
            "metadata": {"category": "AI", "source": "wiki"}
        },
        {
            "key": "doc2", 
            "text": "深度学习基于神经网络模型",
            "metadata": {"category": "AI", "source": "book"}
        },
        {
            "key": "doc3",
            "text": "自然语言处理让计算机理解人类语言",
            "metadata": {"category": "NLP", "source": "paper"}
        },
        {
            "key": "doc4",
            "text": "计算机视觉处理图像和视频数据",
            "metadata": {"category": "CV", "source": "course"}
        }
    ]
    
    # 批量添加向量
    vector_db.batch_add_vectors(index_name, sample_data)
    
    # 搜索相似内容
    query = "人工智能和神经网络"
    print(f"\n搜索查询: '{query}'")
    
    results = vector_db.search_similar(index_name, query, top_k=3)
    
    print("搜索结果:")
    for i, result in enumerate(results, 1):
        print(f"{i}. 文本: {result['text']}")
        print(f"   相似度: {result['score']:.4f}")
        print(f"   元数据: {result['metadata']}")
        print()

if __name__ == "__main__":
    main()