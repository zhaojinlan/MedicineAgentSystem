"""
知识图谱数据一致性管理器
负责管理文献文件夹、Redis向量索引、Neo4j图谱之间的数据一致性
提供统一的CRUD接口，确保删除、更新等操作在三个存储系统中同步执行
"""

import json
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import redis
from py2neo import Graph
import logging

# 导入全局配置
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
from config import get_path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class KnowledgeDataManager:
    """知识图谱数据一致性管理器"""
    
    def __init__(
        self,
        knowledges_dir: Optional[str] = None,
        redis_host: str = 'localhost',
        redis_port: int = 6379,
        redis_password: Optional[str] = None,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "test1234"
    ):
        """
        初始化数据管理器
        
        Args:
            knowledges_dir: 知识库根目录（None时使用全局配置）
            redis_host: Redis主机
            redis_port: Redis端口
            redis_password: Redis密码
            neo4j_uri: Neo4j地址
            neo4j_user: Neo4j用户名
            neo4j_password: Neo4j密码
        """
        # 使用全局配置的路径（如果未指定）
        if knowledges_dir is None:
            self.knowledges_dir = get_path("knowledges_dir")
        else:
            self.knowledges_dir = Path(knowledges_dir)
        self.knowledges_dir.mkdir(exist_ok=True)
        
        # 元数据文件
        self.metadata_file = self.knowledges_dir / "_metadata.json"
        self.metadata = self._load_metadata()
        
        # Redis连接
        try:
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password,
                decode_responses=True
            )
            self.redis_client.ping()
            self.redis_available = True
            logger.info("✓ Redis连接成功")
        except Exception as e:
            self.redis_available = False
            logger.warning(f"⚠ Redis连接失败: {e}")
        
        # Neo4j连接
        try:
            self.neo4j_graph = Graph(neo4j_uri, auth=(neo4j_user, neo4j_password))
            self.neo4j_graph.run("RETURN 1")  # 测试连接
            self.neo4j_available = True
            logger.info("✓ Neo4j连接成功")
        except Exception as e:
            self.neo4j_available = False
            logger.warning(f"⚠ Neo4j连接失败: {e}")
    
    def _load_metadata(self) -> Dict:
        """加载元数据"""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _save_metadata(self):
        """保存元数据"""
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)
    
    def register_document(
        self,
        document_name: str,
        redis_indices: Optional[List[str]] = None,
        neo4j_labels: Optional[List[str]] = None,
        entity_count: int = 0,
        relationship_count: int = 0
    ) -> Dict:
        """
        注册新文档到元数据
        
        Args:
            document_name: 文档名称
            redis_indices: Redis索引列表
            neo4j_labels: Neo4j标签列表
            entity_count: 实体数量
            relationship_count: 关系数量
            
        Returns:
            文档元数据
        """
        # 自动检测Redis索引
        if redis_indices is None:
            redis_indices = self._detect_redis_indices(document_name)
        
        # 自动检测Neo4j标签
        if neo4j_labels is None:
            neo4j_labels = self._detect_neo4j_labels(document_name)
        
        metadata = {
            "document_name": document_name,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "file_path": str(self.knowledges_dir / document_name),
            "redis_indices": redis_indices,
            "neo4j_labels": neo4j_labels,
            "entity_count": entity_count,
            "relationship_count": relationship_count,
            "status": "active"
        }
        
        self.metadata[document_name] = metadata
        self._save_metadata()
        
        logger.info(f"✓ 已注册文档: {document_name}")
        return metadata
    
    def _detect_redis_indices(self, document_name: str) -> List[str]:
        """自动检测文档相关的Redis索引"""
        if not self.redis_available:
            return []
        
        doc_name_safe = document_name.replace(' ', '_').replace('-', '_')
        expected_indices = [
            f"kg_{doc_name_safe}",  # markdown文档索引
            f"kg_entities_{doc_name_safe}",  # 实体索引（如果存在）
            f"symptom_vectors_{doc_name_safe}"  # 症状向量索引
        ]
        
        found_indices = []
        try:
            all_indices = self.redis_client.execute_command("FT._LIST")
            for idx in all_indices:
                idx_name = idx.decode() if isinstance(idx, bytes) else idx
                if idx_name in expected_indices:
                    found_indices.append(idx_name)
        except Exception as e:
            logger.error(f"检测Redis索引失败: {e}")
        
        return found_indices
    
    def _detect_neo4j_labels(self, document_name: str) -> List[str]:
        """自动检测文档相关的Neo4j标签"""
        if not self.neo4j_available:
            return []
        
        # 查询与该文档相关的节点标签（只有Disease有SOURCE_FROM关系）
        # 同时查询Disease相关的其他节点类型
        query = """
        MATCH (d:Disease)-[:SOURCE_FROM]->(source:LiteratureSource {name: $doc_name})
        OPTIONAL MATCH (d)-[r]-(n)
        WHERE NOT n:LiteratureSource
        RETURN DISTINCT labels(d) as disease_labels, collect(DISTINCT labels(n)) as related_labels
        """
        
        labels_set = set()
        try:
            result = self.neo4j_graph.run(query, doc_name=document_name)
            for record in result:
                if record['disease_labels']:
                    labels_set.update(record['disease_labels'])
                if record['related_labels']:
                    for label_list in record['related_labels']:
                        if label_list:
                            labels_set.update(label_list)
        except Exception as e:
            logger.error(f"检测Neo4j标签失败: {e}")
        
        return list(labels_set)
    
    def get_document_info(self, document_name: str) -> Optional[Dict]:
        """
        获取文档信息
        
        Args:
            document_name: 文档名称
            
        Returns:
            文档元数据，不存在返回None
        """
        return self.metadata.get(document_name)
    
    def list_all_documents(self) -> List[Dict]:
        """
        列出所有文档
        
        Returns:
            文档元数据列表
        """
        return list(self.metadata.values())
    
    def delete_document(
        self,
        document_name: str,
        delete_files: bool = True,
        delete_redis: bool = True,
        delete_neo4j: bool = True,
        dry_run: bool = False
    ) -> Dict:
        """
        删除文档及其所有相关资源
        
        Args:
            document_name: 文档名称
            delete_files: 是否删除文件夹
            delete_redis: 是否删除Redis索引
            delete_neo4j: 是否删除Neo4j节点
            dry_run: 是否为预演模式（不实际删除）
            
        Returns:
            删除结果
        """
        result = {
            "document_name": document_name,
            "files_deleted": False,
            "redis_deleted": [],
            "neo4j_deleted": False,
            "errors": [],
            "dry_run": dry_run
        }
        
        # 获取文档元数据
        doc_meta = self.metadata.get(document_name)
        if not doc_meta:
            # 尝试自动检测
            logger.warning(f"文档未在元数据中注册，尝试自动检测: {document_name}")
            doc_meta = self.register_document(document_name)
        
        logger.info(f"{'[预演] ' if dry_run else ''}开始删除文档: {document_name}")
        logger.info(f"  - 文件夹: {delete_files}")
        logger.info(f"  - Redis索引: {delete_redis}")
        logger.info(f"  - Neo4j节点: {delete_neo4j}")
        
        # 1. 删除文件夹
        if delete_files:
            file_path = Path(doc_meta['file_path'])
            if file_path.exists():
                try:
                    if not dry_run:
                        shutil.rmtree(file_path)
                    result['files_deleted'] = True
                    logger.info(f"  ✓ {'[预演] ' if dry_run else ''}已删除文件夹: {file_path}")
                except Exception as e:
                    error_msg = f"删除文件夹失败: {e}"
                    result['errors'].append(error_msg)
                    logger.error(f"  ✗ {error_msg}")
            else:
                logger.warning(f"  ⚠ 文件夹不存在: {file_path}")
        
        # 2. 删除Redis索引（但保留症状向量索引）
        if delete_redis and self.redis_available:
            redis_indices = doc_meta.get('redis_indices', [])
            for index_name in redis_indices:
                # 跳过症状向量索引，不删除
                if 'symptom_vectors_' in index_name:
                    logger.info(f"  ⊙ {'[预演] ' if dry_run else ''}保留症状向量索引（不删除）: {index_name}")
                    continue
                
                try:
                    if not dry_run:
                        self.redis_client.execute_command("FT.DROPINDEX", index_name, "DD")
                    result['redis_deleted'].append(index_name)
                    logger.info(f"  ✓ {'[预演] ' if dry_run else ''}已删除Redis索引: {index_name}")
                except Exception as e:
                    error_msg = f"删除Redis索引失败 {index_name}: {e}"
                    result['errors'].append(error_msg)
                    logger.error(f"  ✗ {error_msg}")
        
        # 3. 删除Neo4j节点（但保留Symptom症状节点）
        if delete_neo4j and self.neo4j_available:
            try:
                # 删除与该文档相关的所有节点和关系，但保留Symptom节点
                # 注意：现在只有Disease节点有SOURCE_FROM关系指向文献源
                # 步骤1: 找到与文献相关的Disease节点及其关联的其他节点
                # 步骤2: 删除Disease节点与Symptom的关系（保留Symptom节点本身）
                # 步骤3: 删除Disease节点及其关联的非Symptom节点
                # 步骤4: 删除文献源节点
                
                if not dry_run:
                    # 统计将要删除的关系和节点
                    count_query = """
                    MATCH (d:Disease)-[:SOURCE_FROM]->(source:LiteratureSource {name: $doc_name})
                    OPTIONAL MATCH (d)-[sr]-(s:Symptom)
                    OPTIONAL MATCH (d)-[r]-(n)
                    WHERE NOT n:LiteratureSource AND NOT n:Symptom
                    RETURN count(DISTINCT d) as disease_count,
                           count(DISTINCT sr) as symptom_relations,
                           count(DISTINCT n) as other_nodes
                    """
                    count_result = self.neo4j_graph.run(count_query, doc_name=document_name).data()
                    stats = count_result[0] if count_result else {}
                    
                    # 删除Disease与Symptom之间的关系（但保留Symptom节点）
                    delete_symptom_relations_query = """
                    MATCH (d:Disease)-[:SOURCE_FROM]->(source:LiteratureSource {name: $doc_name})
                    MATCH (d)-[r]-(s:Symptom)
                    DELETE r
                    """
                    self.neo4j_graph.run(delete_symptom_relations_query, doc_name=document_name)
                    
                    # 删除Disease节点及其关联的非Symptom节点（但不删除Symptom节点）
                    delete_disease_query = """
                    MATCH (d:Disease)-[:SOURCE_FROM]->(source:LiteratureSource {name: $doc_name})
                    OPTIONAL MATCH (d)-[r]-(n)
                    WHERE NOT n:Symptom AND NOT n:LiteratureSource
                    DETACH DELETE d, n
                    """
                    self.neo4j_graph.run(delete_disease_query, doc_name=document_name)
                    
                    # 删除文献源节点本身
                    source_query = """
                    MATCH (source:LiteratureSource {name: $doc_name})
                    DETACH DELETE source
                    """
                    self.neo4j_graph.run(source_query, doc_name=document_name)
                    
                    result['neo4j_deleted'] = True
                    logger.info(f"  ✓ 已删除Neo4j节点（保留Symptom节点）:")
                    logger.info(f"    - 删除Disease节点: {stats.get('disease_count', 0)} 个")
                    logger.info(f"    - 解除症状关联: {stats.get('symptom_relations', 0)} 个")
                    logger.info(f"    - 删除其他关联节点: {stats.get('other_nodes', 0)} 个")
                    logger.info(f"    - 删除文献源: 1 个")
                else:
                    # 预演模式：只查询不删除
                    count_query = """
                    MATCH (d:Disease)-[:SOURCE_FROM]->(source:LiteratureSource {name: $doc_name})
                    OPTIONAL MATCH (d)-[sr]-(s:Symptom)
                    OPTIONAL MATCH (d)-[r]-(n)
                    WHERE NOT n:LiteratureSource AND NOT n:Symptom
                    RETURN count(DISTINCT d) as disease_count,
                           count(DISTINCT sr) as symptom_relations,
                           count(DISTINCT n) as other_nodes
                    """
                    count_result = self.neo4j_graph.run(count_query, doc_name=document_name).data()
                    if count_result:
                        stats = count_result[0]
                        result['neo4j_deleted'] = True
                        logger.info(f"  ✓ [预演] 将删除Neo4j节点（保留Symptom节点）:")
                        logger.info(f"    - 将删除Disease节点: {stats.get('disease_count', 0)} 个")
                        logger.info(f"    - 将解除症状关联: {stats.get('symptom_relations', 0)} 个")
                        logger.info(f"    - 将删除其他关联节点: {stats.get('other_nodes', 0)} 个")
                        logger.info(f"    - 将删除文献源: 1 个")
                    
            except Exception as e:
                error_msg = f"删除Neo4j节点失败: {e}"
                result['errors'].append(error_msg)
                logger.error(f"  ✗ {error_msg}")
        
        # 4. 从元数据中删除
        if not dry_run and document_name in self.metadata:
            del self.metadata[document_name]
            self._save_metadata()
            logger.info(f"  ✓ 已从元数据中删除")
        
        # 总结
        if result['errors']:
            logger.warning(f"{'[预演] ' if dry_run else ''}删除完成，但有 {len(result['errors'])} 个错误")
        else:
            logger.info(f"{'[预演] ' if dry_run else ''}✓ 删除成功: {document_name}")
        
        return result
    
    def update_document_metadata(
        self,
        document_name: str,
        **kwargs
    ) -> Dict:
        """
        更新文档元数据
        
        Args:
            document_name: 文档名称
            **kwargs: 要更新的字段
            
        Returns:
            更新后的元数据
        """
        if document_name not in self.metadata:
            raise ValueError(f"文档不存在: {document_name}")
        
        # 更新字段
        self.metadata[document_name].update(kwargs)
        self.metadata[document_name]['updated_at'] = datetime.now().isoformat()
        
        self._save_metadata()
        logger.info(f"✓ 已更新文档元数据: {document_name}")
        
        return self.metadata[document_name]
    
    def sync_metadata(self, document_name: Optional[str] = None):
        """
        同步元数据（重新检测所有资源）
        
        Args:
            document_name: 指定文档名称，None则同步所有文档
        """
        if document_name:
            documents = [document_name]
        else:
            # 扫描文件夹
            documents = [d.name for d in self.knowledges_dir.iterdir() 
                        if d.is_dir() and not d.name.startswith('_')]
        
        logger.info(f"开始同步元数据，共 {len(documents)} 个文档")
        
        for doc_name in documents:
            try:
                # 检查知识图谱文件是否存在
                kg_file = self.knowledges_dir / doc_name / "04_knowledge_graph.json"
                if kg_file.exists():
                    with open(kg_file, 'r', encoding='utf-8') as f:
                        kg_data = json.load(f)
                    
                    entity_count = len(kg_data.get('entities', []))
                    relationship_count = len(kg_data.get('relationships', []))
                else:
                    entity_count = 0
                    relationship_count = 0
                
                # 注册或更新
                self.register_document(
                    document_name=doc_name,
                    entity_count=entity_count,
                    relationship_count=relationship_count
                )
                
                logger.info(f"  ✓ 同步: {doc_name}")
                
            except Exception as e:
                logger.error(f"  ✗ 同步失败 {doc_name}: {e}")
        
        logger.info(f"✓ 元数据同步完成")
    
    def get_storage_stats(self) -> Dict:
        """
        获取存储统计信息
        
        Returns:
            统计信息
        """
        stats = {
            "total_documents": len(self.metadata),
            "redis_available": self.redis_available,
            "neo4j_available": self.neo4j_available,
            "documents": []
        }
        
        for doc_name, doc_meta in self.metadata.items():
            doc_stats = {
                "name": doc_name,
                "entity_count": doc_meta.get('entity_count', 0),
                "relationship_count": doc_meta.get('relationship_count', 0),
                "redis_indices": len(doc_meta.get('redis_indices', [])),
                "created_at": doc_meta.get('created_at', '')
            }
            stats['documents'].append(doc_stats)
        
        return stats
    
    def cleanup_orphaned_resources(self, dry_run: bool = True) -> Dict:
        """
        清理孤立资源（存在于Redis/Neo4j但元数据中没有的）
        
        Args:
            dry_run: 是否为预演模式
            
        Returns:
            清理结果
        """
        result = {
            "orphaned_redis_indices": [],
            "orphaned_neo4j_docs": [],
            "cleaned": False,
            "dry_run": dry_run
        }
        
        registered_docs = set(self.metadata.keys())
        
        # 检查Redis
        if self.redis_available:
            try:
                all_indices = self.redis_client.execute_command("FT._LIST")
                for idx in all_indices:
                    idx_name = idx.decode() if isinstance(idx, bytes) else idx
                    
                    # 检查是否为知识图谱相关索引
                    if idx_name.startswith('kg_') or idx_name.startswith('symptom_vectors_'):
                        # 跳过症状向量索引，即使是孤立的也不删除
                        if 'symptom_vectors_' in idx_name:
                            logger.info(f"跳过症状向量索引（保护资源）: {idx_name}")
                            continue
                        
                        # 提取文档名
                        doc_name = None
                        for reg_doc in registered_docs:
                            doc_safe = reg_doc.replace(' ', '_').replace('-', '_')
                            if doc_safe in idx_name:
                                doc_name = reg_doc
                                break
                        
                        if not doc_name:
                            result['orphaned_redis_indices'].append(idx_name)
                            logger.warning(f"发现孤立Redis索引: {idx_name}")
                            
                            if not dry_run:
                                self.redis_client.execute_command("FT.DROPINDEX", idx_name, "DD")
                                logger.info(f"  ✓ 已删除孤立索引: {idx_name}")
                                
            except Exception as e:
                logger.error(f"检查Redis孤立资源失败: {e}")
        
        # 检查Neo4j
        if self.neo4j_available:
            try:
                # 查询所有LiteratureSource节点
                query = "MATCH (source:LiteratureSource) RETURN source.name as name"
                results = self.neo4j_graph.run(query).data()
                
                for record in results:
                    doc_name = record['name']
                    if doc_name not in registered_docs:
                        result['orphaned_neo4j_docs'].append(doc_name)
                        logger.warning(f"发现孤立Neo4j文献: {doc_name}")
                        
                        if not dry_run:
                            # 只有Disease节点有SOURCE_FROM关系，需要删除Disease及其关联节点
                            delete_query = """
                            MATCH (source:LiteratureSource {name: $doc_name})
                            OPTIONAL MATCH (d:Disease)-[:SOURCE_FROM]->(source)
                            OPTIONAL MATCH (d)-[r]-(n)
                            WHERE NOT n:Symptom AND NOT n:LiteratureSource
                            DETACH DELETE d, n, source
                            """
                            self.neo4j_graph.run(delete_query, doc_name=doc_name)
                            logger.info(f"  ✓ 已删除孤立文献: {doc_name}")
                            
            except Exception as e:
                logger.error(f"检查Neo4j孤立资源失败: {e}")
        
        result['cleaned'] = not dry_run
        return result


# 单例实例
_manager_instance = None

def get_data_manager(**kwargs) -> KnowledgeDataManager:
    """获取数据管理器单例"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = KnowledgeDataManager(**kwargs)
    return _manager_instance


if __name__ == "__main__":
    # 测试代码
    manager = KnowledgeDataManager()
    
    # 同步元数据
    print("\n" + "=" * 80)
    print("同步元数据...")
    manager.sync_metadata()
    
    # 显示统计
    print("\n" + "=" * 80)
    print("存储统计:")
    stats = manager.get_storage_stats()
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    
    # 检查孤立资源
    print("\n" + "=" * 80)
    print("检查孤立资源（预演模式）...")
    orphaned = manager.cleanup_orphaned_resources(dry_run=True)
    print(json.dumps(orphaned, ensure_ascii=False, indent=2))

