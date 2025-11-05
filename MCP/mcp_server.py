# mcp_nsti_service.py
from mcp.server.fastmcp import FastMCP
from neo4j import GraphDatabase
from typing import List, Dict, Any, Optional
import traceback
import os
import sys
from pathlib import Path
from langchain_community.vectorstores import Neo4jVector
from langchain_huggingface import HuggingFaceEmbeddings

# 导入全局配置
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from config import NEO4J_CONFIG, get_path

try:
    from RAG.tools.KGQuery import DiseaseRiskFactorQuery, SymptomDiseaseAnalyzer
except ModuleNotFoundError:
    # 兼容直接运行当前文件导致的包搜索路径问题
    from RAG.tools.KGQuery import DiseaseRiskFactorQuery, SymptomDiseaseAnalyzer

# ------------- Neo4j 连接配置（使用全局配置，支持环境变量覆盖） -------------
NEO4J_URI = os.getenv("NEO4J_URI", NEO4J_CONFIG["uri"])
NEO4J_USER = os.getenv("NEO4J_USER", NEO4J_CONFIG["user"])
NEO4J_PASS = os.getenv("NEO4J_PASS", NEO4J_CONFIG["password"])

# MCP 服务名
mcp = FastMCP("triage")
 
# ----------------- 工具：症状搜索并分析 -----------------
@mcp.tool()
def symptom_search_analyze(query: str, k: int = 5) -> Dict[str, Any]:
    """
    基于症状描述进行相似检索并查询相关疾病的风险因子。

    参数:
      - query: 症状描述（中文逗号/顿号分隔均可）
      - k: 返回相似症状数量（默认 5）

    返回:
      - { "query": str, "matches": [ { "symptom": str, "related_diseases": [str], "risk_factors": { disease: [ {"risk_factor": str, "description": str} ] } } ] }
    """
    try:
        # 初始化向量存储（使用全局配置）
        vector_store = Neo4jVector.from_existing_index(
            embedding=HuggingFaceEmbeddings(model_name=str(get_path("m3e_model"))),
            url=NEO4J_URI,
            username=NEO4J_USER,
            password=NEO4J_PASS,
            index_name="enhanced_symptom_vectors"
        )

        # 执行检索与分析
        with DiseaseRiskFactorQuery(neo4j_url=NEO4J_URI, username=NEO4J_USER, password=NEO4J_PASS) as risk_query_service:
            analyzer = SymptomDiseaseAnalyzer(vector_store, risk_query_service)
            results = analyzer.search_symptoms(query, k=k)

            # 结构化结果
            structured_matches: List[Dict[str, Any]] = []
            for i, result in enumerate(results, 1):
                metadata = getattr(result, 'metadata', {}) or {}
                symptom_name: str = metadata.get('name', f'未知症状_{i}')
                related_diseases: List[str] = metadata.get('related_diseases', []) or []

                disease_to_risk_list: Dict[str, List[Dict[str, str]]] = {}
                for disease in related_diseases:
                    if not disease:
                        continue
                    risk_factors = risk_query_service.query_risk_factors(disease)
                    disease_to_risk_list[disease] = [
                        {
                            "risk_factor": rf.get('risk_factor', ''),
                            "description": rf.get('risk_description', '')
                        }
                        for rf in risk_factors
                    ]

                structured_matches.append({
                    "symptom": symptom_name,
                    "related_diseases": related_diseases,
                    "risk_factors": disease_to_risk_list
                })

            return {
                "query": query,
                "k": k,
                "matches_count": len(structured_matches),
                "matches": structured_matches
            }

    except Exception as e:
        return {
            "error": str(e),
            "trace": traceback.format_exc()
        }


# @mcp.tool()
# def symptom_search_analyze(triage1_result: str, k: int = 5) -> Dict[str, Any]:


# ----------------- 工具：获取通用诊断检查方法 -----------------
@mcp.tool()
def get_common_diagnostic_methods(
    limit: int = 15,
    category_filter: Optional[str] = None
) -> Dict[str, Any]:
    """
    从知识图谱中获取通用的诊断检查方法（不限定特定疾病）。
    当针对某个疾病没有特异性诊断方法时，可以使用此工具获取通用检查建议。

    参数:
      - limit: 返回的检查方法数量上限（默认15）
      - category_filter: 可选的类别筛选（如"影像学"、"实验室检查"等）

    返回:
      - {
          "methods_count": int,
          "methods": [
            {
              "method_name": str,
              "description": str,
              "used_by_diseases": [str],  # 使用该方法的疾病列表
              "usage_count": int  # 使用该方法的疾病数量
            }
          ]
        }
    """
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
        
        with driver.session() as session:
            # 构建查询：获取所有诊断方法及其使用情况
            if category_filter:
                cypher = """
                MATCH (m)<-[:DIAGNOSED_BY]-(d)
                WHERE m.category IS NOT NULL AND m.category CONTAINS $category
                WITH m, collect(DISTINCT d.name) AS diseases
                RETURN m.name AS method_name,
                       m.description AS description,
                       m.category AS category,
                       diseases AS used_by_diseases,
                       size(diseases) AS usage_count
                ORDER BY usage_count DESC
                LIMIT $limit
                """
                result = session.run(cypher, category=category_filter, limit=limit)
            else:
                cypher = """
                MATCH (m)<-[:DIAGNOSED_BY]-(d)
                WITH m, collect(DISTINCT d.name) AS diseases
                RETURN m.name AS method_name,
                       m.description AS description,
                       coalesce(m.category, '未分类') AS category,
                       diseases AS used_by_diseases,
                       size(diseases) AS usage_count
                ORDER BY usage_count DESC
                LIMIT $limit
                """
                result = session.run(cypher, limit=limit)
            
            methods = []
            for record in result:
                methods.append({
                    "method_name": record["method_name"],
                    "description": record["description"] or "暂无描述",
                    "category": record.get("category", "未分类"),
                    "used_by_diseases": record["used_by_diseases"][:5],  # 只显示前5个疾病
                    "usage_count": record["usage_count"]
                })
        
        driver.close()
        
        return {
            "methods_count": len(methods),
            "methods": methods,
            "note": "这些是知识图谱中已有的通用诊断方法，按使用频率排序"
        }
    
    except Exception as e:
        return {
            "error": str(e),
            "trace": traceback.format_exc(),
            "methods_count": 0,
            "methods": []
        }


# ----------------- 启动 MCP 服务 -----------------
if __name__ == "__main__":
    try:
        print("启动 NSTI MCP 服务 ...")
        mcp.run(transport='sse')
    finally:
        print("已关闭 Neo4j 连接。")
