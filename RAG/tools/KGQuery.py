"""这个文件是一个搜索示例，用于根据症状查询相关疾病、风险因子、病原体、治疗方法等信息"""

import sys
from pathlib import Path
from langchain_community.vectorstores import Neo4jVector
from langchain_huggingface import HuggingFaceEmbeddings
from neo4j import GraphDatabase
from typing import List, Dict, Optional
import logging

# 导入全局配置
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
from config import NEO4J_CONFIG, get_path

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KnowledgeGraphQuery:
    """知识图谱查询类 - 增强版"""
    
    def __init__(self, neo4j_url: Optional[str] = None, 
                 username: Optional[str] = None, 
                 password: Optional[str] = None):
        # 使用全局配置（如果未指定）
        self.neo4j_url = neo4j_url or NEO4J_CONFIG["uri"]
        self.username = username or NEO4J_CONFIG["user"]
        self.password = password or NEO4J_CONFIG["password"]
        self._driver = None
    
    def get_driver(self):
        """获取Neo4j驱动连接（单例模式）"""
        if self._driver is None:
            try:
                self._driver = GraphDatabase.driver(
                    self.neo4j_url, 
                    auth=(self.username, self.password)
                )
                logger.info("Neo4j连接已建立")
            except Exception as e:
                logger.error(f"无法连接到Neo4j: {e}")
                raise
        return self._driver
    
    def close_connection(self):
        """关闭数据库连接"""
        if self._driver:
            self._driver.close()
            self._driver = None
            logger.info("Neo4j连接已关闭")
    
    def query_disease_by_symptom(self, symptom_name: str) -> List[Dict]:
        """根据症状查询相关疾病"""
        if not symptom_name or not isinstance(symptom_name, str):
            logger.warning(f"无效的症状名称: {symptom_name}")
            return []
        
        driver = self.get_driver()
        try:
            with driver.session() as session:
                cypher = """
                MATCH (d:Disease)-[r:HAS_SYMPTOM]->(s:Symptom)
                WHERE s.name CONTAINS $symptom_name OR $symptom_name CONTAINS s.name
                RETURN DISTINCT d.name AS disease, 
                       d.description AS disease_description,
                       collect(DISTINCT s.name) AS symptoms
                """
                result = session.run(cypher, symptom_name=symptom_name.strip())
                diseases = [record.data() for record in result]
                logger.info(f"根据症状 '{symptom_name}' 找到 {len(diseases)} 个相关疾病")
                return diseases
        except Exception as e:
            logger.error(f"查询症状 '{symptom_name}' 相关疾病时出错: {e}")
            return []
    
    def query_risk_factors(self, disease_name: str) -> List[Dict]:
        """查询指定疾病的风险因子"""
        if not disease_name or not isinstance(disease_name, str):
            logger.warning(f"无效的疾病名称: {disease_name}")
            return []
        
        driver = self.get_driver()
        try:
            with driver.session() as session:
                cypher = """
                MATCH (d)-[r:HAS_RISK_FACTOR]->(rf:RiskFactor)
                WHERE d.name CONTAINS $disease_name OR $disease_name CONTAINS d.name
                RETURN DISTINCT d.name AS disease, 
                       rf.name AS risk_factor, 
                       rf.description AS risk_description
                """
                result = session.run(cypher, disease_name=disease_name.strip())
                risk_factors = [record.data() for record in result]
                logger.info(f"查询疾病 '{disease_name}' 找到 {len(risk_factors)} 个风险因子")
                return risk_factors
        except Exception as e:
            logger.error(f"查询疾病 '{disease_name}' 的风险因子时出错: {e}")
            return []
    
    def query_symptoms(self, disease_name: str) -> List[Dict]:
        """查询指定疾病的症状"""
        if not disease_name or not isinstance(disease_name, str):
            logger.warning(f"无效的疾病名称: {disease_name}")
            return []
        
        driver = self.get_driver()
        try:
            with driver.session() as session:
                cypher = """
                MATCH (d)-[r:HAS_SYMPTOM]->(s:Symptom)
                WHERE d.name CONTAINS $disease_name OR $disease_name CONTAINS d.name
                RETURN DISTINCT d.name AS disease, 
                       s.name AS symptom, 
                       s.description AS symptom_description,
                       r.description AS relation_description
                """
                result = session.run(cypher, disease_name=disease_name.strip())
                symptoms = [record.data() for record in result]
                logger.info(f"查询疾病 '{disease_name}' 找到 {len(symptoms)} 个症状")
                return symptoms
        except Exception as e:
            logger.error(f"查询疾病 '{disease_name}' 的症状时出错: {e}")
            return []
    
    def query_pathogens(self, disease_name: str) -> List[Dict]:
        """查询导致指定疾病的病原体"""
        if not disease_name or not isinstance(disease_name, str):
            logger.warning(f"无效的疾病名称: {disease_name}")
            return []
        
        driver = self.get_driver()
        try:
            with driver.session() as session:
                cypher = """
                MATCH (d)-[r:CAUSED_BY]->(p:Pathogen)
                WHERE d.name CONTAINS $disease_name OR $disease_name CONTAINS d.name
                RETURN DISTINCT d.name AS disease, 
                       p.name AS pathogen, 
                       p.description AS pathogen_description,
                       r.description AS relation_description
                """
                result = session.run(cypher, disease_name=disease_name.strip())
                pathogens = [record.data() for record in result]
                logger.info(f"查询疾病 '{disease_name}' 找到 {len(pathogens)} 个病原体")
                return pathogens
        except Exception as e:
            logger.error(f"查询疾病 '{disease_name}' 的病原体时出错: {e}")
            return []
    
    def query_treatments(self, disease_name: str) -> List[Dict]:
        """查询指定疾病的治疗方法"""
        if not disease_name or not isinstance(disease_name, str):
            logger.warning(f"无效的疾病名称: {disease_name}")
            return []
        
        driver = self.get_driver()
        try:
            with driver.session() as session:
                cypher = """
                MATCH (d)-[r:TREATED_WITH]->(t:Treatment)
                WHERE d.name CONTAINS $disease_name OR $disease_name CONTAINS d.name
                RETURN DISTINCT d.name AS disease, 
                       t.name AS treatment, 
                       t.description AS treatment_description,
                       r.description AS relation_description
                """
                result = session.run(cypher, disease_name=disease_name.strip())
                treatments = [record.data() for record in result]
                logger.info(f"查询疾病 '{disease_name}' 找到 {len(treatments)} 个治疗方法")
                return treatments
        except Exception as e:
            logger.error(f"查询疾病 '{disease_name}' 的治疗方法时出错: {e}")
            return []
    
    def query_diagnostic_methods(self, disease_name: str) -> List[Dict]:
        """查询指定疾病的诊断方法"""
        if not disease_name or not isinstance(disease_name, str):
            logger.warning(f"无效的疾病名称: {disease_name}")
            return []
        
        driver = self.get_driver()
        try:
            with driver.session() as session:
                cypher = """
                MATCH (d)-[r:DIAGNOSED_BY]->(m)
                WHERE d.name CONTAINS $disease_name OR $disease_name CONTAINS d.name
                RETURN DISTINCT d.name AS disease, 
                       m.name AS diagnostic_method, 
                       m.description AS method_description,
                       r.description AS relation_description
                """
                result = session.run(cypher, disease_name=disease_name.strip())
                methods = [record.data() for record in result]
                logger.info(f"查询疾病 '{disease_name}' 找到 {len(methods)} 个诊断方法")
                return methods
        except Exception as e:
            logger.error(f"查询疾病 '{disease_name}' 的诊断方法时出错: {e}")
            return []
    
    def query_disease_full_info(self, disease_name: str) -> Dict:
        """查询疾病的完整信息（症状、风险因子、病原体、治疗方法、诊断方法）"""
        return {
            'disease_name': disease_name,
            'symptoms': self.query_symptoms(disease_name),
            'risk_factors': self.query_risk_factors(disease_name),
            'pathogens': self.query_pathogens(disease_name),
            'treatments': self.query_treatments(disease_name),
            'diagnostic_methods': self.query_diagnostic_methods(disease_name)
        }
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_connection()


# 为了保持向后兼容，保留旧的类名作为别名
class DiseaseRiskFactorQuery(KnowledgeGraphQuery):
    """疾病风险因子查询类（向后兼容）"""
    pass


class SymptomDiseaseAnalyzer:
    """症状疾病分析器 - 增强版"""
    
    def __init__(self, vector_store, kg_query_service):
        self.vector_store = vector_store
        self.kg_query_service = kg_query_service
    
    def search_symptoms(self, query: str, k: int = 5) -> List:
        """搜索相关症状"""
        try:
            # 使用 similarity_search_with_score 获取相似度分数
            results_with_scores = self.vector_store.similarity_search_with_score(query, k=k)
            logger.info(f"搜索查询 '{query}' 返回 {len(results_with_scores)} 个结果")
            
            # 打印相似度分数
            print(f"\n📊 相似度分数详情:")
            for i, (result, score) in enumerate(results_with_scores, 1):
                metadata = getattr(result, 'metadata', {})
                name = metadata.get('name', f'结果_{i}')
                print(f"  {i}. {name} (相似度: {score:.4f})")
            
            # 只返回结果，不包含分数
            results = [result for result, score in results_with_scores]
            return results
        except Exception as e:
            logger.error(f"搜索症状时出错: {e}")
            return []
    
    def analyze_symptom_results(self, results: List) -> None:
        """分析症状搜索结果 - 显示完整疾病信息"""
        if not results:
            print("❌ 未找到相关症状信息")
            return
        
        print("\n" + "="*80)
        print("🔍 相关疾病及其详细信息")
        print("="*80)
        
        # 收集所有相关的疾病名称
        all_diseases = set()
        for result in results:
            metadata = getattr(result, 'metadata', {})
            related_diseases = metadata.get('related_diseases', [])
            all_diseases.update(related_diseases)
        
        if not all_diseases:
            # 如果metadata中没有related_diseases，尝试从图谱中直接查询
            print("\n⚠️ 未从metadata中找到相关疾病，尝试从症状直接查询...")
            for result in results:
                metadata = getattr(result, 'metadata', {})
                symptom_name = metadata.get('name', '')
                if symptom_name:
                    diseases = self.kg_query_service.query_disease_by_symptom(symptom_name)
                    for disease in diseases:
                        all_diseases.add(disease['disease'])
        
        if not all_diseases:
            print("❌ 未找到相关疾病信息")
            return
        
        # 为每个疾病查询完整信息
        for i, disease_name in enumerate(sorted(all_diseases), 1):
            self._display_disease_full_info(disease_name, i)
    
    def _display_disease_full_info(self, disease_name: str, index: int) -> None:
        """显示疾病的完整信息"""
        print(f"\n{'='*80}")
        print(f"🏥 疾病 {index}: {disease_name}")
        print(f"{'='*80}")
        
        # 获取完整信息
        full_info = self.kg_query_service.query_disease_full_info(disease_name)
        
        # 显示症状
        symptoms = full_info['symptoms']
        if symptoms:
            print(f"\n📋 症状 ({len(symptoms)}个):")
            for symptom in symptoms:
                print(f"  • {symptom['symptom']}")
                if symptom.get('symptom_description'):
                    print(f"    描述: {symptom['symptom_description']}")
                if symptom.get('relation_description'):
                    print(f"    关联: {symptom['relation_description']}")
        else:
            print(f"\n📋 症状: 暂无数据")
        
        # 显示风险因子
        risk_factors = full_info['risk_factors']
        if risk_factors:
            print(f"\n⚠️ 风险因子 ({len(risk_factors)}个):")
            for rf in risk_factors:
                print(f"  • {rf['risk_factor']}")
                if rf.get('risk_description'):
                    print(f"    描述: {rf['risk_description']}")
        else:
            print(f"\n⚠️ 风险因子: 暂无数据")
        
        # 显示病原体
        pathogens = full_info['pathogens']
        if pathogens:
            print(f"\n🦠 病原体 ({len(pathogens)}个):")
            for pathogen in pathogens:
                print(f"  • {pathogen['pathogen']}")
                if pathogen.get('pathogen_description'):
                    print(f"    描述: {pathogen['pathogen_description']}")
                if pathogen.get('relation_description'):
                    print(f"    关联: {pathogen['relation_description']}")
        else:
            print(f"\n🦠 病原体: 暂无数据")
        
        # 显示治疗方法
        treatments = full_info['treatments']
        if treatments:
            print(f"\n💊 治疗方法 ({len(treatments)}个):")
            for treatment in treatments:
                print(f"  • {treatment['treatment']}")
                if treatment.get('treatment_description'):
                    print(f"    描述: {treatment['treatment_description']}")
                if treatment.get('relation_description'):
                    print(f"    关联: {treatment['relation_description']}")
        else:
            print(f"\n💊 治疗方法: 暂无数据")
        
        # 显示诊断方法
        diagnostic_methods = full_info['diagnostic_methods']
        if diagnostic_methods:
            print(f"\n🔬 诊断方法 ({len(diagnostic_methods)}个):")
            for method in diagnostic_methods:
                print(f"  • {method['diagnostic_method']}")
                if method.get('method_description'):
                    print(f"    描述: {method['method_description']}")
                if method.get('relation_description'):
                    print(f"    关联: {method['relation_description']}")
        else:
            print(f"\n🔬 诊断方法: 暂无数据")


def main():
    """主函数"""
    try:
        # 初始化向量存储（使用全局配置）
        print("正在初始化向量存储...")
        vector_store = Neo4jVector.from_existing_index(
            embedding=HuggingFaceEmbeddings(model_name=str(get_path("m3e_model"))),
            url=NEO4J_CONFIG["uri"],
            username=NEO4J_CONFIG["user"],
            password=NEO4J_CONFIG["password"],
            index_name="symptom_vectors"  # 根据您的实际索引名称调整
        )
        
        # 使用上下文管理器确保连接正确关闭
        with KnowledgeGraphQuery() as kg_query:
            # 创建分析器
            analyzer = SymptomDiseaseAnalyzer(vector_store, kg_query)
            
            # 执行搜索和分析
            query = "发热，皮肤红肿，疼痛"
            print(f"\n正在搜索症状: {query}")
            
            results = analyzer.search_symptoms(query, k=5)
            analyzer.analyze_symptom_results(results)
            
            print("\n" + "="*80)
            print("✅ 查询完成")
            print("="*80)
            
    except Exception as e:
        logger.error(f"程序执行出错: {e}")
        print(f"\n❌ 程序执行出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
