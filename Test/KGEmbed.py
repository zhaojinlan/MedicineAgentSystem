"""这个文件中有读取symptom节点然后对其进行向量化的操作"""

from langchain_community.vectorstores import Neo4jVector
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.schema import Document
from py2neo import Graph
import time

class SymptomVectorizer:
    def __init__(self, uri, user, password, model_path):
        """
        初始化向量化器
        """
        self.graph = Graph(uri, auth=(user, password))
        self.embeddings = HuggingFaceEmbeddings(model_name=model_path)
        print("已初始化症状向量化器")
    
    def extract_symptom_nodes(self):
        """
        从知识图谱中提取所有 Symptom 节点
        """
        print("正在提取 Symptom 节点...")
        
        query = """
        MATCH (s:Symptom)
        RETURN s.name AS name, s.description AS description, ID(s) AS node_id
        """
        
        result = self.graph.run(query)
        symptoms = []
        
        for record in result:
            symptoms.append({
                "node_id": record["node_id"],
                "name": record["name"],
                "description": record["description"]
            })
        
        print(f"成功提取 {len(symptoms)} 个 Symptom 节点")
        return symptoms
    
    def create_symptom_vectors(self, index_name="symptom_vectors"):
        """
        为 Symptom 节点创建向量索引
        """
        print(f"开始创建症状向量索引: {index_name}")
        
        # 提取症状节点
        symptoms = self.extract_symptom_nodes()
        
        # 转换为 LangChain Document 格式
        documents = []
        for symptom in symptoms:
            # 将名称和描述合并作为向量化的文本内容
            text_content = f"{symptom['name']}: {symptom['description']}"
            
            document = Document(
                page_content=text_content,
                metadata={
                    "node_id": symptom["node_id"],
                    "name": symptom["name"],
                    "type": "Symptom",
                    "source": "NSTI_Knowledge_Graph"
                }
            )
            documents.append(document)
        
        print(f"已创建 {len(documents)} 个文档用于向量化")
        
        # 创建向量索引
        try:
            vector_store = Neo4jVector.from_documents(
                documents=documents,
                embedding=self.embeddings,
                url="bolt://localhost:7687",
                username="neo4j",
                password="test1234",
                index_name=index_name,
                pre_delete_collection=True  # 如果索引已存在，先删除
            )
            print(f"成功创建症状向量索引: {index_name}")
            return vector_store
            
        except Exception as e:
            print(f"创建向量索引时出错: {e}")
            return None
    
    def create_enhanced_symptom_vectors(self, index_name="enhanced_symptom_vectors"):
        """
        创建增强的症状向量（包含相关疾病信息）
        """
        print(f"开始创建增强症状向量索引: {index_name}")
        
        # 查询症状及其相关疾病
        query = """
        MATCH (s:Symptom)
        OPTIONAL MATCH (d:Disease)-[:HAS_SYMPTOM]->(s)
        WITH s, COLLECT(d.name) AS related_diseases
        RETURN s.name AS name, 
               s.description AS description, 
               ID(s) AS node_id,
               related_diseases
        """
        
        result = self.graph.run(query)
        enhanced_symptoms = []
        
        for record in result:
            enhanced_symptoms.append({
                "node_id": record["node_id"],
                "name": record["name"],
                "description": record["description"],
                "related_diseases": record["related_diseases"]
            })
        
        print(f"成功提取 {len(enhanced_symptoms)} 个增强症状节点")
        
        # 转换为 Document 格式
        documents = []
        for symptom in enhanced_symptoms:
            # 构建增强的文本内容
            base_text = f"{symptom['name']}: {symptom['description']}"
            
            if symptom["related_diseases"]:
                diseases_text = " 相关疾病: " + ", ".join(symptom["related_diseases"])
                enhanced_text = base_text + diseases_text
            else:
                enhanced_text = base_text
            
            document = Document(
                page_content=enhanced_text,
                metadata={
                    "node_id": symptom["node_id"],
                    "name": symptom["name"],
                    "type": "Symptom",
                    "related_diseases": symptom["related_diseases"],
                    "source": "NSTI_Knowledge_Graph_Enhanced"
                }
            )
            documents.append(document)
        
        print(f"已创建 {len(documents)} 个增强文档用于向量化")
        
        # 创建增强向量索引
        try:
            vector_store = Neo4jVector.from_documents(
                documents=documents,
                embedding=self.embeddings,
                url="bolt://localhost:7687",
                username="neo4j",
                password="test1234",
                index_name=index_name,
                pre_delete_collection=True
            )
            print(f"成功创建增强症状向量索引: {index_name}")
            return vector_store
            
        except Exception as e:
            print(f"创建增强向量索引时出错: {e}")
            return None
    
    def search_similar_symptoms(self, query_text, vector_store, k=3):
        """
        在向量索引中搜索相似症状
        """
        print(f"搜索相似症状: '{query_text}'")
        
        try:
            results = vector_store.similarity_search(query_text, k=k)
            
            print(f"找到 {len(results)} 个相似症状:")
            for i, doc in enumerate(results):
                print(f"{i+1}. {doc.metadata['name']}")
                print(f"   描述: {doc.page_content[:100]}...")
                print(f"   相关疾病: {doc.metadata.get('related_diseases', '无')}")
                print(f"   节点ID: {doc.metadata['node_id']}")
                print("-" * 50)
                
            return results
            
        except Exception as e:
            print(f"搜索时出错: {e}")
            return []
    
    def test_vector_search(self):
        """
        测试向量搜索功能
        """
        print("开始测试向量搜索功能...")
        
        # 创建基本向量索引
        basic_vector_store = self.create_symptom_vectors("symptom_vectors_basic")
        
        if basic_vector_store:
            # 测试基本搜索
            test_queries = [
                "皮肤肿胀疼痛",
                "发热和休克",
                "皮下有气体",
                "眼部症状"
            ]
            
            for query in test_queries:
                self.search_similar_symptoms(query, basic_vector_store)
        
        # 创建增强向量索引
        enhanced_vector_store = self.create_enhanced_symptom_vectors("symptom_vectors_enhanced")
        
        if enhanced_vector_store:
            # 测试增强搜索
            enhanced_queries = [
                "感染导致的皮肤问题",
                "全身性感染症状",
                "需要紧急处理的症状"
            ]
            
            for query in enhanced_queries:
                self.search_similar_symptoms(query, enhanced_vector_store)

def main():
    """
    主函数 - 对 Symptom 节点进行向量化
    """
    # 配置信息
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "test1234"
    MODEL_PATH = r"O:\MyProject\RAG\models\m3e-base"
    
    try:
        print("=== Symptom 节点向量化程序 ===")
        
        # 创建向量化器实例
        vectorizer = SymptomVectorizer(
            uri=NEO4J_URI,
            user=NEO4J_USER,
            password=NEO4J_PASSWORD,
            model_path=MODEL_PATH
        )
        
        # 执行向量化
        start_time = time.time()
        
        # 方法1: 创建基本症状向量索引
        print("\n1. 创建基本症状向量索引...")
        basic_store = vectorizer.create_symptom_vectors("nsti_symptoms_basic")
        
        # 方法2: 创建增强症状向量索引
        print("\n2. 创建增强症状向量索引...")
        enhanced_store = vectorizer.create_enhanced_symptom_vectors("nsti_symptoms_enhanced")
        
        end_time = time.time()
        print(f"\n向量化完成，总耗时: {end_time - start_time:.2f}秒")
        
        # 测试搜索功能
        print("\n3. 测试向量搜索功能...")
        if enhanced_store:
            test_queries = [
                "皮肤出现血泡和瘀斑",
                "全身感染伴随器官衰竭",
                "局部肿胀和发热"
            ]
            
            for query in test_queries:
                print(f"\n搜索查询: '{query}'")
                vectorizer.search_similar_symptoms(query, enhanced_store, k=2)
        
        print("\n=== Symptom 节点向量化完成 ===")
        
    except Exception as e:
        print(f"程序执行出错: {e}")
        print("请检查:")
        print("1. Neo4j 数据库连接")
        print("2. 模型路径是否正确")
        print("3. 知识图谱是否已创建")

if __name__ == "__main__":
    main()