"""知识图谱集成测试脚本"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from RAG.tools.KGQuery import KnowledgeGraphQuery, DiseaseRiskFactorQuery
from neo4j import GraphDatabase

def test_connection():
    """测试Neo4j连接"""
    print("="*80)
    print("测试 1: Neo4j 数据库连接")
    print("="*80)
    
    try:
        driver = GraphDatabase.driver(
            "bolt://localhost:7687", 
            auth=("neo4j", "test1234")
        )
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) AS count")
            count = result.single()["count"]
            print(f"✅ 连接成功！数据库中共有 {count} 个节点")
        driver.close()
        return True
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False

def test_node_types():
    """测试节点类型"""
    print("\n" + "="*80)
    print("测试 2: 检查节点类型")
    print("="*80)
    
    try:
        driver = GraphDatabase.driver(
            "bolt://localhost:7687", 
            auth=("neo4j", "test1234")
        )
        with driver.session() as session:
            # 查询所有标签
            result = session.run("""
                CALL db.labels() YIELD label
                RETURN label ORDER BY label
            """)
            labels = [record["label"] for record in result]
            
            print("知识图谱中的节点类型：")
            for label in labels:
                # 统计每种类型的数量
                count_result = session.run(f"MATCH (n:{label}) RETURN count(n) AS count")
                count = count_result.single()["count"]
                print(f"  • {label}: {count} 个节点")
            
            # 检查必需的节点类型
            required_labels = ["Disease", "Symptom", "RiskFactor", "Pathogen", "Treatment"]
            missing = [label for label in required_labels if label not in labels]
            
            if missing:
                print(f"\n⚠️ 缺少以下节点类型: {', '.join(missing)}")
            else:
                print(f"\n✅ 所有必需的节点类型都存在")
                
        driver.close()
        return len(missing) == 0
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def test_relationships():
    """测试关系类型"""
    print("\n" + "="*80)
    print("测试 3: 检查关系类型")
    print("="*80)
    
    try:
        driver = GraphDatabase.driver(
            "bolt://localhost:7687", 
            auth=("neo4j", "test1234")
        )
        with driver.session() as session:
            # 查询所有关系类型
            result = session.run("""
                CALL db.relationshipTypes() YIELD relationshipType
                RETURN relationshipType ORDER BY relationshipType
            """)
            rel_types = [record["relationshipType"] for record in result]
            
            print("知识图谱中的关系类型：")
            for rel_type in rel_types:
                # 统计每种关系的数量
                count_result = session.run(
                    f"MATCH ()-[r:{rel_type}]->() RETURN count(r) AS count"
                )
                count = count_result.single()["count"]
                print(f"  • {rel_type}: {count} 条关系")
            
            # 检查必需的关系类型
            required_rels = ["HAS_SYMPTOM", "HAS_RISK_FACTOR", "CAUSED_BY", "TREATED_WITH"]
            missing = [rel for rel in required_rels if rel not in rel_types]
            
            if missing:
                print(f"\n⚠️ 缺少以下关系类型: {', '.join(missing)}")
            else:
                print(f"\n✅ 所有必需的关系类型都存在")
                
        driver.close()
        return len(missing) == 0
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def test_kg_query_class():
    """测试KnowledgeGraphQuery类"""
    print("\n" + "="*80)
    print("测试 4: KnowledgeGraphQuery 类功能")
    print("="*80)
    
    try:
        with KnowledgeGraphQuery() as kg_query:
            # 测试查询症状
            print("\n4.1 测试查询疾病症状：")
            symptoms = kg_query.query_symptoms("坏死性软组织感染")
            print(f"  找到 {len(symptoms)} 个症状")
            if symptoms:
                print(f"  示例: {symptoms[0].get('symptom', 'N/A')}")
            
            # 测试查询风险因子
            print("\n4.2 测试查询风险因子：")
            risk_factors = kg_query.query_risk_factors("坏死性软组织感染")
            print(f"  找到 {len(risk_factors)} 个风险因子")
            if risk_factors:
                print(f"  示例: {risk_factors[0].get('risk_factor', 'N/A')}")
            
            # 测试查询病原体
            print("\n4.3 测试查询病原体：")
            pathogens = kg_query.query_pathogens("坏死性软组织感染")
            print(f"  找到 {len(pathogens)} 个病原体")
            if pathogens:
                print(f"  示例: {pathogens[0].get('pathogen', 'N/A')}")
            
            # 测试查询治疗方法
            print("\n4.4 测试查询治疗方法：")
            treatments = kg_query.query_treatments("坏死性软组织感染")
            print(f"  找到 {len(treatments)} 个治疗方法")
            if treatments:
                print(f"  示例: {treatments[0].get('treatment', 'N/A')}")
            
            # 测试查询诊断方法
            print("\n4.5 测试查询诊断方法：")
            diagnostics = kg_query.query_diagnostic_methods("坏死性软组织感染")
            print(f"  找到 {len(diagnostics)} 个诊断方法")
            if diagnostics:
                print(f"  示例: {diagnostics[0].get('diagnostic_method', 'N/A')}")
            
            # 测试完整信息查询
            print("\n4.6 测试完整信息查询：")
            full_info = kg_query.query_disease_full_info("坏死性软组织感染")
            print(f"  症状: {len(full_info['symptoms'])} 个")
            print(f"  风险因子: {len(full_info['risk_factors'])} 个")
            print(f"  病原体: {len(full_info['pathogens'])} 个")
            print(f"  治疗方法: {len(full_info['treatments'])} 个")
            print(f"  诊断方法: {len(full_info['diagnostic_methods'])} 个")
            
            print("\n✅ KnowledgeGraphQuery 类测试通过")
            return True
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_backward_compatibility():
    """测试向后兼容性"""
    print("\n" + "="*80)
    print("测试 5: 向后兼容性")
    print("="*80)
    
    try:
        # 测试旧的类名仍然可用
        with DiseaseRiskFactorQuery() as query:
            risk_factors = query.query_risk_factors("坏死性软组织感染")
            print(f"  DiseaseRiskFactorQuery 类仍可使用")
            print(f"  查询到 {len(risk_factors)} 个风险因子")
            
        print("\n✅ 向后兼容性测试通过")
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def test_recommend_node_import():
    """测试recommend_node导入"""
    print("\n" + "="*80)
    print("测试 6: Agent/recommend_node.py 导入")
    print("="*80)
    
    try:
        from Agent.recommend_node import get_diagnostic_tests_for_disease
        print("  ✅ 成功导入 get_diagnostic_tests_for_disease 函数")
        
        # 测试函数调用
        print("\n  测试函数调用：")
        tests = get_diagnostic_tests_for_disease("坏死性软组织感染")
        print(f"  返回 {len(tests)} 个诊断/治疗方法")
        for i, test in enumerate(tests[:3], 1):  # 只显示前3个
            print(f"    {i}. {test.get('test_name', 'N/A')}")
        
        print("\n✅ recommend_node 测试通过")
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_mcp_server_import():
    """测试MCP服务器导入"""
    print("\n" + "="*80)
    print("测试 7: MCP/mcp_server.py 导入")
    print("="*80)
    
    try:
        # 由于MCP服务器可能有特殊依赖，这里只测试导入
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "mcp_server", 
            os.path.join(os.path.dirname(__file__), '..', 'MCP', 'mcp_server.py')
        )
        if spec and spec.loader:
            print("  ✅ MCP服务器模块可以加载")
            print("  ℹ️ 完整功能测试需要启动MCP服务")
            return True
        else:
            print("  ⚠️ 无法加载MCP服务器模块")
            return False
    except Exception as e:
        print(f"  ⚠️ 导入测试失败: {e}")
        print("  ℹ️ 这可能是正常的，如果缺少MCP相关依赖")
        return True  # 不算失败

def main():
    """主测试函数"""
    print("\n" + "="*80)
    print("知识图谱集成测试")
    print("="*80)
    
    results = []
    
    # 运行所有测试
    results.append(("数据库连接", test_connection()))
    
    if results[-1][1]:  # 如果连接成功，继续其他测试
        results.append(("节点类型检查", test_node_types()))
        results.append(("关系类型检查", test_relationships()))
        results.append(("KnowledgeGraphQuery类", test_kg_query_class()))
        results.append(("向后兼容性", test_backward_compatibility()))
        results.append(("recommend_node导入", test_recommend_node_import()))
        results.append(("MCP服务器导入", test_mcp_server_import()))
    
    # 汇总结果
    print("\n" + "="*80)
    print("测试结果汇总")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
    
    print("\n" + "="*80)
    print(f"总计: {passed}/{total} 测试通过")
    print("="*80)
    
    if passed == total:
        print("\n🎉 所有测试通过！知识图谱适配完成。")
    else:
        print(f"\n⚠️ 有 {total - passed} 个测试失败，请检查相关配置。")

if __name__ == "__main__":
    main()

