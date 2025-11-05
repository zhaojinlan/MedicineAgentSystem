"""
医学知识查询节点 - Query Node
用于处理医生对疾病、症状、治疗等医学知识的查询
使用Redis向量数据库进行知识检索，并通过智能体生成专业回答
"""

import sys
import os
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入配置
from config import create_llm, REDIS_CONFIG

# 导入Redis RAG工具
try:
    from RAG.tools.rag import RedisVectorDB
except ImportError:
    print("警告: 无法导入RedisVectorDB，将使用模拟数据")
    RedisVectorDB = None

# ============================================================================
# 初始化LLM
# ============================================================================

# 使用统一配置，query_node使用更高的temperature
llm = create_llm(node_name="query_node")

# ============================================================================
# Redis向量数据库检索功能
# ============================================================================

class MedicalKnowledgeRetriever:
    """医学知识检索器 - 从Redis向量库检索相关医学知识"""
    
    def __init__(self):
        """初始化知识检索器"""
        self.vector_db = None
        self.index_name = "medical_docs"
        self._initialize_db()
    
    def _initialize_db(self):
        """初始化向量数据库连接"""
        try:
            if RedisVectorDB:
                # 使用全局配置而非硬编码
                self.vector_db = RedisVectorDB(
                    host=REDIS_CONFIG['host'], 
                    port=REDIS_CONFIG['port'],
                    password=REDIS_CONFIG.get('password')
                )
                print(f">>> Redis向量数据库连接成功 ({REDIS_CONFIG['host']}:{REDIS_CONFIG['port']})")
            else:
                print(">>> 警告: Redis向量数据库不可用，使用模拟模式")
        except Exception as e:
            print(f">>> 警告: 初始化向量数据库失败: {e}")
            self.vector_db = None
    
    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        检索相关医学知识
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            
        Returns:
            检索结果列表
        """
        try:
            if self.vector_db:
                results = self.vector_db.search(self.index_name, query, top_k)
                print(f">>> 成功检索到 {len(results)} 条相关医学知识")
                return results
            else:
                # 模拟数据
                return [
                    {
                        'content': '模拟医学知识：根据临床指南，需要综合考虑患者症状、体征和实验室检查结果进行诊断。',
                        'score': 0.85,
                        'metadata': {'source': 'mock'}
                    }
                ]
        except Exception as e:
            print(f">>> 检索知识时出错: {e}")
            return []

# 全局知识检索器实例
_knowledge_retriever = None

def get_knowledge_retriever():
    """获取全局知识检索器实例"""
    global _knowledge_retriever
    if _knowledge_retriever is None:
        _knowledge_retriever = MedicalKnowledgeRetriever()
    return _knowledge_retriever

def search_medical_knowledge(query: str, top_k: int = 5) -> str:
    """
    工具函数：检索医学知识
    
    Args:
        query: 查询描述，如"什么是坏死性软组织感染？"
        top_k: 返回结果数量
        
    Returns:
        格式化的检索结果文本
    """
    print(f">>> 正在检索: '{query}'")
    
    retriever = get_knowledge_retriever()
    results = retriever.retrieve(query, top_k)
    
    if not results:
        return "未找到相关医学知识，请尝试使用其他关键词。"
    
    # 格式化检索结果
    formatted_results = []
    for i, result in enumerate(results, 1):
        content = result.get('content', '')
        score = result.get('score', 0)
        # 限制每条内容的长度，避免过长
        if len(content) > 800:
            content = content[:800] + "..."
        formatted_results.append(
            f"[参考资料{i}] (相关度: {score:.2f})\n{content}"
        )
    
    return "\n\n".join(formatted_results)

# ============================================================================
# 医学知识查询智能体
# ============================================================================

MEDICAL_QUERY_PROMPT = """你是一名专业的医学知识顾问，负责回答医生关于疾病、症状、诊断、治疗等医学问题。

【工作流程】
1. 理解医生的问题
2. 使用 search_medical_knowledge 工具检索相关医学知识
3. 基于检索到的知识，用专业且易懂的语言回答问题

【回答要求】
- 必须调用 search_medical_knowledge 工具获取最新的医学知识
- 回答要准确、专业，引用检索到的资料
- 如果检索结果不足，明确说明并建议查阅更多资料
- 保持客观，避免给出诊断性结论（除非是知识性解释）
- 使用中文回答

【输出格式】
请严格按照以下格式输出：

<思考>
步骤1：理解问题
[分析用户问题的关键点]

步骤2：检索医学知识
[说明检索了什么，找到了哪些相关资料]

步骤3：组织答案
[说明如何基于检索结果组织回答]
</思考>

<结论>
## 问题理解
[简要复述医生的问题]

## 相关医学知识
[基于检索结果，总结关键信息]

## 详细解答
[详细回答问题，引用具体的医学知识]

## 补充说明
[如有必要，提供额外的注意事项或建议]

【注意事项】
- 这是医学知识查询，不是患者诊断
- 如果问题超出知识库范围，诚实说明
- 鼓励医生查阅最新的临床指南
"""

class MedicalQueryAgent:
    """医学知识查询智能体"""
    
    def __init__(self):
        """初始化智能体"""
        # 创建ReAct智能体
        self.agent = create_react_agent(
            model=llm,
            tools=[search_medical_knowledge],
            prompt=MEDICAL_QUERY_PROMPT
        )
    
    def query(self, question: str) -> str:
        """
        处理医学知识查询
        
        Args:
            question: 医生的问题
            
        Returns:
            智能体的回答
        """
        try:
            print(f">>> 医学知识查询智能体正在处理问题...")
            
            # 调用智能体
            response = self.agent.invoke({
                "messages": [HumanMessage(content=question)]
            })
            
            # 提取回答
            if response and "messages" in response:
                last_message = response["messages"][-1]
                answer = last_message.content if hasattr(last_message, 'content') else str(last_message)
                return answer
            else:
                return "抱歉，无法生成回答。"
                
        except Exception as e:
            print(f">>> 查询处理出错: {e}")
            import traceback
            traceback.print_exc()
            return f"处理查询时出现错误: {str(e)}"

# 全局智能体实例
_medical_query_agent = None

def get_medical_query_agent():
    """获取全局医学查询智能体实例"""
    global _medical_query_agent
    if _medical_query_agent is None:
        _medical_query_agent = MedicalQueryAgent()
    return _medical_query_agent

# ============================================================================
# 供 flow.py 调用的主节点函数
# ============================================================================

def query_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    医学知识查询节点 - 供flow.py调用的主接口
    
    Args:
        state: 包含messages等字段的状态字典
        
    Returns:
        包含回答的状态更新
    """
    print(">>> 医学知识查询节点启动...")
    
    try:
        # 提取用户问题
        messages = state.get("messages", [])
        last_message = messages[-1] if messages else ""
        question = last_message.content if hasattr(last_message, 'content') else str(last_message)
        
        # 获取智能体
        agent = get_medical_query_agent()
        
        # 处理查询
        answer = agent.query(question)
        
        # 返回结果
        return {
            "messages": [HumanMessage(content=answer)]
        }
        
    except Exception as e:
        print(f">>> 医学知识查询节点出错: {e}")
        import traceback
        traceback.print_exc()
        return {
            "messages": [HumanMessage(content=f"查询处理出错: {str(e)}\n请重新提问或咨询专业医疗人员。")]
        }

# ============================================================================
# 测试代码
# ============================================================================

def test_query_node():
    """测试医学知识查询节点"""
    print("=" * 60)
    print("测试医学知识查询节点")
    print("=" * 60)
    
    # 测试问题
    test_questions = [
        "什么是坏死性软组织感染？",
        "坏死性软组织感染的主要症状有哪些？",
        "LRINEC评分是什么？如何使用？",
        "坏死性软组织感染的治疗方法有哪些？"
    ]
    
    for question in test_questions:
        print(f"\n问题: {question}")
        print("-" * 60)
        
        # 模拟state
        state = {
            "messages": [HumanMessage(content=question)]
        }
        
        # 调用节点
        result = query_node(state)
        
        # 输出结果
        if result and "messages" in result:
            print(result["messages"][-1].content)
        else:
            print("未获得回答")
        
        print("=" * 60)

if __name__ == "__main__":
    # 运行测试
    test_query_node()

