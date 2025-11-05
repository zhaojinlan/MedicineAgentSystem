"""
知识图谱RAG向量化工具
功能：将构建的知识图谱文档向量化并存储到Redis，用于后续的语义检索
该模块绑定前端的"构建知识图谱"按钮，在知识图谱构建完成后自动执行
"""

import os
import sys
import redis
import numpy as np
from pathlib import Path
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import json
from typing import List, Dict, Optional
from datetime import datetime

# 导入全局配置
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
from config import get_path


class KnowledgeRAGVectorizer:
    """知识图谱RAG向量化器"""
    
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
            model_name=str(get_path("m3e_model"))
        )
        print("模型加载完成!")
        
        # 向量维度
        self.vector_dimension = 768

    def create_index(self, index_name: str):
        """
        在Redis中创建向量索引
        
        Args:
            index_name: 索引名称（建议使用文档名称作为索引名）
        """
        try:
            # 检查索引是否已存在
            existing_indexes = self.redis_client.execute_command("FT._LIST")
            if index_name.encode() in existing_indexes:
                print(f"索引 '{index_name}' 已存在，将删除后重建")
                # 删除旧索引
                self.redis_client.execute_command("FT.DROPINDEX", index_name, "DD")
            
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
                "chunk_id", "TEXT",
                "entity_type", "TEXT",  # 实体类型
                "source_document", "TEXT"  # 来源文档
            )
            print(f"Redis索引 '{index_name}' 创建成功")
            
        except Exception as e:
            print(f"创建索引时出错: {e}")

    def vectorize_from_markdown(self, markdown_path: str, document_name: str, 
                                chunk_size: int = 1500, chunk_overlap: int = 150):
        """
        从markdown文件创建向量索引
        
        Args:
            markdown_path: markdown文件路径
            document_name: 文档名称（用作索引名）
            chunk_size: 文本块大小
            chunk_overlap: 文本块重叠大小
            
        Returns:
            存储的文本块数量
        """
        print(f"正在从markdown文件创建向量索引: {markdown_path}")
        
        # 读取markdown内容
        with open(markdown_path, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
        
        # 配置文本分割器
        splitter = SentenceSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separator="\n\n## ",
            paragraph_separator="\n\n\n\n",
        )
        
        # 分割文档
        text_chunks = splitter.split_text(markdown_content)
        print(f"文档分割完成，共得到 {len(text_chunks)} 个文本块")
        
        # 创建索引（使用文档名称的安全版本）
        index_name = f"kg_{document_name.replace(' ', '_').replace('-', '_')}"
        self.create_index(index_name)
        
        # 存储到Redis
        stored_count = 0
        for i, chunk_text in enumerate(text_chunks):
            # 生成向量嵌入
            embedding = self.embed_model.get_text_embedding(chunk_text)
            
            # 准备元数据
            metadata = {
                "chunk_id": f"chunk_{i}",
                "source_document": document_name,
                "chunk_type": "markdown",
                "text_length": len(chunk_text),
                "chunk_index": i,
                "total_chunks": len(text_chunks)
            }
            
            # Redis键名
            redis_key = f"vec:{index_name}:chunk_{i}"
            
            # 存储到Redis
            self.redis_client.hset(redis_key, mapping={
                "vector": np.array(embedding, dtype=np.float32).tobytes(),
                "content": chunk_text,
                "metadata": json.dumps(metadata, ensure_ascii=False),
                "chunk_id": f"chunk_{i}",
                "entity_type": "Document",
                "source_document": document_name
            })
            
            stored_count += 1
            
            # 显示进度
            if stored_count % 50 == 0:
                print(f"已存储 {stored_count}/{len(text_chunks)} 个文本块")
        
        print(f"向量化完成！共存储 {stored_count} 个文本块到Redis索引: {index_name}")
        return stored_count

    def vectorize_from_knowledge_graph(self, kg_json_path: str, document_name: str):
        """
        从知识图谱JSON文件创建向量索引
        将实体和关系信息向量化存储
        
        ⚠️ 注意：不推荐使用此功能
        理由：
        1. 实体已存储在Neo4j图数据库中，具有更强大的查询能力
        2. Neo4j支持向量索引（symptom_vectorizer已实现）
        3. 图数据库的关系查询比向量检索更适合实体间推理
        4. 重复存储会浪费存储空间和维护成本
        
        推荐：只向量化markdown文档，用于全文语义检索
        
        Args:
            kg_json_path: 知识图谱JSON文件路径
            document_name: 文档名称
            
        Returns:
            存储的实体数量
        """
        print(f"正在从知识图谱JSON创建向量索引: {kg_json_path}")
        
        # 读取知识图谱JSON
        with open(kg_json_path, 'r', encoding='utf-8') as f:
            kg_data = json.load(f)
        
        entities = kg_data.get('entities', [])
        relationships = kg_data.get('relationships', [])
        
        print(f"知识图谱包含 {len(entities)} 个实体，{len(relationships)} 个关系")
        
        # 创建索引
        index_name = f"kg_entities_{document_name.replace(' ', '_').replace('-', '_')}"
        self.create_index(index_name)
        
        # 为每个实体创建向量
        stored_count = 0
        for i, entity in enumerate(entities):
            entity_name = entity.get('name', '')
            entity_type = entity.get('entity_type', '')
            entity_desc = entity.get('description', '')
            
            # 构建实体的完整文本表示（用于向量化）
            entity_text = f"{entity_name}"
            if entity_desc:
                entity_text += f"\n{entity_desc}"
            
            # 添加相关关系信息
            related_relations = []
            for rel in relationships:
                if rel.get('source') == entity_name:
                    target = rel.get('target', '')
                    rel_type = rel.get('relation_type', '')
                    related_relations.append(f"{rel_type} {target}")
                elif rel.get('target') == entity_name:
                    source = rel.get('source', '')
                    rel_type = rel.get('relation_type', '')
                    related_relations.append(f"{source} {rel_type}")
            
            if related_relations:
                entity_text += f"\n关系: {'; '.join(related_relations[:5])}"  # 最多包含5个关系
            
            # 生成向量嵌入
            embedding = self.embed_model.get_text_embedding(entity_text)
            
            # 准备元数据
            metadata = {
                "entity_id": f"entity_{i}",
                "entity_name": entity_name,
                "entity_type": entity_type,
                "source_document": document_name,
                "related_relations_count": len(related_relations)
            }
            
            # Redis键名
            redis_key = f"vec:{index_name}:entity_{i}"
            
            # 存储到Redis
            self.redis_client.hset(redis_key, mapping={
                "vector": np.array(embedding, dtype=np.float32).tobytes(),
                "content": entity_text,
                "metadata": json.dumps(metadata, ensure_ascii=False),
                "chunk_id": f"entity_{i}",
                "entity_type": entity_type,
                "source_document": document_name
            })
            
            stored_count += 1
            
            # 显示进度
            if stored_count % 20 == 0:
                print(f"已向量化 {stored_count}/{len(entities)} 个实体")
        
        print(f"实体向量化完成！共存储 {stored_count} 个实体到Redis索引: {index_name}")
        return stored_count

    def vectorize_knowledge_document(self, document_name: str, 
                                     knowledges_dir: Optional[str] = None,
                                     vectorize_markdown: bool = True,
                                     vectorize_entities: bool = True):
        """
        对知识图谱文档进行完整的向量化
        该方法会在前端点击"构建知识图谱"按钮后被调用
        
        Args:
            document_name: 文档名称
            knowledges_dir: 知识库根目录
            vectorize_markdown: 是否对markdown文档进行向量化
            vectorize_entities: 是否对知识图谱实体进行向量化
            
        Returns:
            字典，包含向量化结果信息
        """
        print("=" * 80)
        print(f"开始向量化知识文档: {document_name}")
        print("=" * 80)
        
        # 使用全局配置的路径（如果未指定）
        if knowledges_dir is None:
            knowledges_dir = get_path("knowledges_dir")
        
        # 工作目录
        work_dir = Path(knowledges_dir) / document_name
        if not work_dir.exists():
            raise FileNotFoundError(f"文档工作目录不存在: {work_dir}")
        
        results = {
            "document_name": document_name,
            "markdown_vectorized": False,
            "markdown_chunks": 0,
            "entities_vectorized": False,
            "entity_count": 0,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 1. 向量化markdown文档
        if vectorize_markdown:
            markdown_path = work_dir / "03_document.md"
            if markdown_path.exists():
                try:
                    chunk_count = self.vectorize_from_markdown(
                        str(markdown_path), 
                        document_name
                    )
                    results["markdown_vectorized"] = True
                    results["markdown_chunks"] = chunk_count
                    print(f"✓ Markdown文档向量化成功: {chunk_count} 个文本块")
                except Exception as e:
                    print(f"✗ Markdown文档向量化失败: {e}")
            else:
                print(f"⚠ Markdown文件不存在，跳过: {markdown_path}")
        
        # 2. 向量化知识图谱实体
        if vectorize_entities:
            kg_json_path = work_dir / "04_knowledge_graph.json"
            if kg_json_path.exists():
                try:
                    entity_count = self.vectorize_from_knowledge_graph(
                        str(kg_json_path),
                        document_name
                    )
                    results["entities_vectorized"] = True
                    results["entity_count"] = entity_count
                    print(f"✓ 知识图谱实体向量化成功: {entity_count} 个实体")
                except Exception as e:
                    print(f"✗ 知识图谱实体向量化失败: {e}")
            else:
                print(f"⚠ 知识图谱JSON文件不存在，跳过: {kg_json_path}")
        
        print("=" * 80)
        print(f"向量化完成！")
        print(f"  - Markdown文档: {'✓' if results['markdown_vectorized'] else '✗'} ({results['markdown_chunks']} 块)")
        print(f"  - 知识图谱实体: {'✓' if results['entities_vectorized'] else '✗'} ({results['entity_count']} 个)")
        print("=" * 80)
        
        return results

    def search(self, index_name: str, query: str, top_k: int = 5, 
               entity_type_filter: Optional[str] = None):
        """
        搜索相似内容
        
        Args:
            index_name: 索引名称
            query: 查询文本
            top_k: 返回结果数量
            entity_type_filter: 实体类型过滤（可选）
            
        Returns:
            搜索结果列表
        """
        print(f"正在搜索: '{query}' (索引: {index_name})")
        
        # 生成查询向量
        query_embedding = self.embed_model.get_text_embedding(query)
        query_vector = np.array(query_embedding, dtype=np.float32).tobytes()
        
        # 构建查询条件
        if entity_type_filter:
            query_filter = f"@entity_type:{entity_type_filter}"
        else:
            query_filter = "*"
        
        # 执行向量搜索
        try:
            results = self.redis_client.execute_command(
                "FT.SEARCH", index_name,
                f"{query_filter}=>[KNN {top_k} @vector $query_vector AS vector_score]",
                "PARAMS", "2", "query_vector", query_vector,
                "DIALECT", "2",
                "SORTBY", "vector_score",
                "RETURN", "5", "content", "metadata", "entity_type", "source_document", "vector_score",
                "LIMIT", "0", str(top_k)
            )
        except Exception as e:
            print(f"搜索失败: {e}")
            return []
        
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
                    'entity_type': item_dict.get('entity_type', ''),
                    'source_document': item_dict.get('source_document', ''),
                    'score': similarity_score
                })
        
        print(f"找到 {len(search_results)} 个结果")
        return search_results

    def get_stats(self, index_name: str):
        """
        获取索引统计信息
        
        Args:
            index_name: 索引名称
            
        Returns:
            统计信息字典
        """
        # 统计文本块/实体数量
        pattern = f"vec:{index_name}:*"
        keys = self.redis_client.keys(pattern)
        
        return {
            "index_name": index_name,
            "total_items": len(keys),
            "vector_dimension": self.vector_dimension
        }

    def delete_index(self, index_name: str):
        """
        删除索引及其所有数据
        
        Args:
            index_name: 索引名称
        """
        try:
            # 删除索引
            self.redis_client.execute_command("FT.DROPINDEX", index_name, "DD")
            print(f"索引 '{index_name}' 已删除")
        except Exception as e:
            print(f"删除索引失败: {e}")


def main():
    """测试函数"""
    # 初始化向量化器
    vectorizer = KnowledgeRAGVectorizer(host='localhost', port=6379)
    
    # 测试：向量化一个知识文档
    document_name = "坏死性软组织感染临床诊治急诊专家共识"
    
    try:
        results = vectorizer.vectorize_knowledge_document(
            document_name=document_name,
            vectorize_markdown=True,
            vectorize_entities=True
        )
        
        print("\n" + "=" * 80)
        print("向量化结果:")
        print(json.dumps(results, ensure_ascii=False, indent=2))
        print("=" * 80)
        
        # 测试搜索功能
        print("\n" + "=" * 80)
        print("测试搜索功能")
        print("=" * 80)
        
        # 搜索markdown内容
        index_name = f"kg_{document_name.replace(' ', '_').replace('-', '_')}"
        search_results = vectorizer.search(
            index_name=index_name,
            query="坏死性软组织感染的诊断方法",
            top_k=3
        )
        
        print("\n搜索结果:")
        for i, result in enumerate(search_results, 1):
            print(f"\n结果 {i} (相似度: {result['score']:.4f}):")
            print(f"内容: {result['content'][:200]}...")
            print(f"来源: {result['source_document']}")
        
        # 搜索实体
        entity_index_name = f"kg_entities_{document_name.replace(' ', '_').replace('-', '_')}"
        entity_results = vectorizer.search(
            index_name=entity_index_name,
            query="治疗方法",
            top_k=3,
            entity_type_filter="Treatment"
        )
        
        print("\n\n实体搜索结果:")
        for i, result in enumerate(entity_results, 1):
            print(f"\n实体 {i} (相似度: {result['score']:.4f}):")
            print(f"类型: {result['entity_type']}")
            print(f"内容: {result['content']}")
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

