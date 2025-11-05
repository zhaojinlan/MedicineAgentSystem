"""该代码使用redis作为向量数据库，完成了对文档的切分以及检索功能"""

import os
import redis
import numpy as np
from llama_index.core import SimpleDirectoryReader
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core.schema import TextNode
import json

class RedisVectorDB:
    def __init__(self, host='localhost', port=6379, password=None):
        """
        初始化Redis向量数据库
        
        Args:
            host: Redis主机地址
            port: Redis端口
            password: Redis密码
        """
        # 连接Redis
        self.redis_client = redis.Redis(
            host=host,
            port=port,
            password=password,
            decode_responses=True
        )
        
        # 初始化embedding模型
        print("正在加载embedding模型...")
        self.embed_model = HuggingFaceEmbedding(
            model_name=r"O:\MyProject\RAG\models\m3e-base"
        )
        print("模型加载完成!")
        
        # 向量维度
        self.vector_dimension = 768

    def create_index(self, index_name: str):
        """
        在Redis中创建向量索引
        """
        try:
            # 检查索引是否已存在
            existing_indexes = self.redis_client.execute_command("FT._LIST")
            if index_name.encode() in existing_indexes:
                print(f"索引 '{index_name}' 已存在")
                return
            
            # 创建向量索引
            self.redis_client.execute_command(
                "FT.CREATE", index_name, "ON", "HASH", "PREFIX", "1", f"vec:{index_name}:",
                "SCHEMA", 
                "vector", "VECTOR", "FLAT", "6", 
                "TYPE", "FLOAT32", 
                "DIM", self.vector_dimension, 
                "DISTANCE_METRIC", "COSINE",
                "content", "TEXT",
                "metadata", "TEXT",
                "chunk_id", "TEXT"
            )
            print(f"Redis索引 '{index_name}' 创建成功")
            
        except Exception as e:
            print(f"创建索引时出错: {e}")

    def load_and_split_document(self, file_path: str):
        """
        加载并分割文档
        
        Args:
            file_path: 文档路径
            
        Returns:
            分割后的节点列表
        """
        print(f"正在加载文档: {file_path}")
        
        # 加载文档
        documents = SimpleDirectoryReader(input_files=[file_path]).load_data()
        print(f"成功加载文档，共 {len(documents)} 个文档")
        
        # 配置文本分割器
        splitter = SentenceSplitter(
            chunk_size=1500,
            chunk_overlap=150,
            separator="\n\n## ",
            paragraph_separator="\n\n\n\n",
        )
        
        # 分割文档
        nodes = splitter.get_nodes_from_documents(documents)
        print(f"分割完成，共得到 {len(nodes)} 个文本块")
        
        return nodes

    def store_to_redis(self, index_name: str, nodes: list):
        """
        将文本块存储到Redis
        
        Args:
            index_name: 索引名称
            nodes: 文本块列表
        """
        print("开始存储到Redis...")
        
        stored_count = 0
        for i, node in enumerate(nodes):
            # 获取文本内容
            content = node.text
            
            # 生成向量嵌入
            embedding = self.embed_model.get_text_embedding(content)
            
            # 准备元数据
            metadata = {
                "chunk_id": f"chunk_{i}",
                "file_path": node.metadata.get("file_path", ""),
                "text_length": len(content)
            }
            
            # Redis键名
            redis_key = f"vec:{index_name}:chunk_{i}"
            
            # 存储到Redis
            self.redis_client.hset(redis_key, mapping={
                "vector": np.array(embedding, dtype=np.float32).tobytes(),
                "content": content,
                "metadata": json.dumps(metadata, ensure_ascii=False),
                "chunk_id": f"chunk_{i}"
            })
            
            stored_count += 1
            
            # 显示进度
            if stored_count % 50 == 0:
                print(f"已存储 {stored_count} 个文本块")
        
        print(f"存储完成！共存储 {stored_count} 个文本块到Redis")

    def search(self, index_name: str, query: str, top_k: int = 5):
        """
        搜索相似内容
        
        Args:
            index_name: 索引名称
            query: 查询文本
            top_k: 返回结果数量
            
        Returns:
            搜索结果列表
        """
        print(f"正在搜索: '{query}'")
        
        # 生成查询向量
        query_embedding = self.embed_model.get_text_embedding(query)
        query_vector = np.array(query_embedding, dtype=np.float32).tobytes()
        
        # 执行向量搜索
        results = self.redis_client.execute_command(
            "FT.SEARCH", index_name,
            f"*=>[KNN {top_k} @vector $query_vector AS vector_score]",
            "PARAMS", "2", "query_vector", query_vector,
            "DIALECT", "2",
            "SORTBY", "vector_score",
            "RETURN", "3", "content", "metadata", "vector_score",
            "LIMIT", "0", str(top_k)
        )
        
        # 解析结果
        search_results = []
        if results and len(results) > 1:
            for i in range(1, len(results), 2):
                item_data = results[i + 1]
                
                # 提取字段
                item_dict = {}
                for j in range(0, len(item_data), 2):
                    field = item_data[j]
                    value = item_data[j + 1]
                    item_dict[field] = value
                
                # 计算相似度分数
                similarity_score = 1 - float(item_dict.get('vector_score', 0))
                
                search_results.append({
                    'content': item_dict.get('content', ''),
                    'metadata': json.loads(item_dict.get('metadata', '{}')),
                    'score': similarity_score
                })
        
        return search_results

    def get_stats(self, index_name: str):
        """
        获取索引统计信息
        """
        # 统计文本块数量
        pattern = f"vec:{index_name}:*"
        keys = self.redis_client.keys(pattern)
        
        return {
            "total_chunks": len(keys),
            "index_name": index_name
        }


def main():
    """主函数"""
    # 初始化Redis向量数据库
    print("=" * 50)
    print("Redis向量数据库初始化")
    print("=" * 50)
    
    vector_db = RedisVectorDB(host='localhost', port=6379)
    
    # 创建索引
    index_name = "medical_docs"
    vector_db.create_index(index_name)
    
    # 加载和分割文档
    file_path = r"O:\MyProject\RAG\DB\uploads\output.md"
    nodes = vector_db.load_and_split_document(file_path)
    
    if not nodes:
        print("文档分割失败！")
        return
    
    # 存储到Redis
    vector_db.store_to_redis(index_name, nodes)
    
    # 显示统计信息
    stats = vector_db.get_stats(index_name)
    print(f"\n统计信息: 共存储 {stats['total_chunks']} 个文本块")
    
    # 测试搜索功能
    print("\n" + "=" * 50)
    print("测试搜索功能")
    print("=" * 50)
    
    test_queries = [
        "坏死性软组织感染的诊断",
        "NSTIs的治疗方法", 
        "LRINEC评分是什么",
        "手术探查的指征",
        "肿胀发热怎么处理"
    ]
    
    for query in test_queries:
        print(f"\n搜索: '{query}'")
        results = vector_db.search(index_name, query, top_k=3)
        
        if results:
            for i, result in enumerate(results, 1):
                content_preview = result['content'][:150] + "..." if len(result['content']) > 150 else result['content']
                print(f"  {i}. 相似度: {result['score']:.4f}")
                print(f"     内容: {content_preview}")
        else:
            print("  未找到相关结果")


# 简单的搜索函数，方便直接调用
def simple_search(query: str, top_k: int = 3):
    """
    简单的搜索函数
    
    Args:
        query: 搜索查询
        top_k: 返回结果数量
    """
    vector_db = RedisVectorDB()
    index_name = "medical_docs"
    
    results = vector_db.search(index_name, query, top_k)
    
    print(f"\n搜索: '{query}'")
    print(f"找到 {len(results)} 个结果:")
    
    for i, result in enumerate(results, 1):
        print(f"\n{i}. 相似度: {result['score']:.4f}")
        print(f"内容: {result['content']}")

    return results


if __name__ == "__main__":
    # # 运行主程序
    # main()
    
    # # 示例：单独搜索
    # print("\n" + "=" * 50)
    # print("单独搜索示例")
    # print("=" * 50)
    
    # 可以直接调用simple_search函数进行搜索
    simple_search("治疗方案")