from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent 
from langgraph.checkpoint.memory import InMemorySaver
from qwen_agent.llm import get_chat_model
from neo4j import GraphDatabase
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
import datetime
import math
import numpy as np
import re
import json
import os
import asyncio
import concurrent.futures
from typing import Dict, Any, List, TypedDict, Optional

# 导入配置
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import create_llm, get_neo4j_config, get_mcp_config

# Neo4j配置
neo4j_config = get_neo4j_config()
NEO4J_URI = neo4j_config["uri"]
NEO4J_USER = neo4j_config["user"]
NEO4J_PASS = neo4j_config["password"]

# 定义状态类型
class MedicalState(TypedDict):
    messages: List[Dict[str, Any]]
    disease_data: Dict[str, Any]
    risk_factor_count: int
    analysis_result: Dict[str, Any]
    diagnostic_tests: List[Dict[str, Any]]

# 创建 LangChain 兼容的模型，使用统一配置
model = create_llm()

def analyze_disease_probability(disease_data: Dict[str, float], risk_factor_count: int) -> Dict[str, Any]:
    """
    分析疾病概率并返回最可能的疾病
    
    Args:
        disease_data: 字典，包含疾病名称和得分 {疾病名称: 得分}
        risk_factor_count: 整数，风险因素总数
    """
    try:
        # 确保disease_data是字典格式
        if isinstance(disease_data, str):
            disease_data = json.loads(disease_data)
        
        # 提取疾病名称和得分
        disease_names = list(disease_data.keys())
        disease_scores = list(disease_data.values())
        
        # 计算softmax概率
        exp_scores = [math.exp(score) for score in disease_scores]
        sum_exp_scores = sum(exp_scores)
        probabilities = [exp_score / sum_exp_scores for exp_score in exp_scores]
        
        # 找到最高概率的疾病
        max_prob_index = np.argmax(probabilities)
        most_likely_disease = disease_names[max_prob_index]
        confidence = probabilities[max_prob_index]
        
        # 构建结果
        result = {
            "most_likely_disease": most_likely_disease,
            "confidence": round(confidence * 100, 2),
            "disease_details": {},
            "risk_factor_count": risk_factor_count
        }
        
        # 为每个疾病添加详细信息
        for i, disease in enumerate(disease_names):
            result["disease_details"][disease] = {
                "score": disease_scores[i],
                "probability": round(probabilities[i] * 100, 2)
            }
        
        print(f"\n=== 工具调用结果 ===")
        print(f"最可能的疾病: {result['most_likely_disease']}")
        print(f"置信度: {result['confidence']}%")
        print(f"疾病详情: {json.dumps(result['disease_details'], indent=2, ensure_ascii=False)}")
        print("===================\n")
        
        return result
    except Exception as e:
        print(f"工具执行错误: {e}")
        return {"error": str(e)}

def get_diagnostic_tests_for_disease(disease_name: str) -> List[Dict[str, str]]:
    """
    根据疾病名称从Neo4j数据库获取相关的诊断方法
    
    Args:
        disease_name: 疾病名称
        
    Returns:
        诊断方法列表
    """
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
        
        # 查询诊断方法 - 支持模糊匹配
        diagnostic_query = """
        MATCH (d)-[r:DIAGNOSED_BY]->(m)
        WHERE d.name CONTAINS $disease_name OR $disease_name CONTAINS d.name
        RETURN DISTINCT m.name AS method_name, 
               m.description AS method_description,
               'diagnostic' AS method_type
        """
        
        methods = []
        
        with driver.session() as session:
            # 获取诊断方法
            diagnostic_result = session.run(diagnostic_query, disease_name=disease_name)
            for record in diagnostic_result:
                methods.append({
                    "test_name": record['method_name'],
                    "test_description": record["method_description"] or "暂无描述"
                })
        
        driver.close()
        
        # 如果没有找到任何方法，返回提示信息
        if not methods:
            return [
                {"test_name": "暂无诊断方法", "test_description": f"知识图谱中未找到疾病 '{disease_name}' 的诊断方法"},
                {"test_name": "建议", "test_description": "请咨询专业医生获取诊断建议"}
            ]
        
        return methods
        
    except Exception as e:
        print(f"获取检查方法错误: {e}")
        import traceback
        traceback.print_exc()
        # 返回错误提示
        return [
            {"test_name": "查询出错", "test_description": f"无法连接到知识图谱: {str(e)}"},
            {"test_name": "建议", "test_description": "请检查Neo4j数据库连接"}
        ]

# 修改后的提示词，明确指示工具使用
MEDICAL_ANALYSIS_PROMPT = """
你是一名医学症状对比分析师。你的任务是根据患者的回答，与给定的疾病及其风险因素列表进行逐一比对，并严格遵循以下规则进行计算。

【任务步骤】

1. 疾病可能性得分计算：针对每个疾病下的每一个风险因素问题，根据患者的回答进行判断。
   - 回答为"是"或症状存在：该疾病可能性+1
   - 回答为"否"或症状不存在：该疾病可能性+0
   - 患者的回答中未提及该因素：该疾病可能性+0

2. 风险因素总数计算：统计所有疾病下列出的不重复的风险因素总数量。即使同一因素出现在不同疾病中，也只计一次。

3. 初步输出：首先输出每种疾病的名称及其得分，以及不重复的风险因素总数。请严格使用"疾病名称:得分"的格式，并使用阿拉伯数字。最终输出格式为："疾病名称1:得分, 疾病名称2:得分, ..., 风险因素总数:总数"

4. 使用分析工具：在得到初步分析结果后，必须调用analyze_disease_probability工具来进一步计算各疾病的概率分布和最可能的疾病诊断。

【重要指令】
在完成初步分析后，你必须调用analyze_disease_probability工具，传入两个参数：
- disease_data: 包含疾病名称和得分的字典，例如 {"支气管哮喘急性发作": 1, "坏死性软组织感染": 2}
- risk_factor_count: 风险因素总数，例如 7

【示例分析过程】
给定疾病范围：
【可能疾病1】支气管哮喘急性发作
- 吸烟：患者是否有吸烟病史？
- 过敏原吸入：患者是否存在接触尘螨、花粉、宠物皮屑等过敏原的情况？
- 呼吸道感染：患者近期是否出现过呼吸道感染？

【可能疾病2】坏死性软组织感染
- 皮肤软组织损伤：患者是否有皮肤或软组织的创伤或挤压伤历史？
- 慢性肝病：患者是否有慢性肝病史？
- 糖尿病：患者是否存在糖尿病？
- 高龄：患者年龄是否≥60岁？

患者回答：有吸烟史、没有过敏现象、没有呼吸道感染、年龄66岁、有糖尿病、没有皮肤损伤。

分析过程：
- 支气管哮喘急性发作：吸烟(是→+1)，过敏原吸入(否→+0)，呼吸道感染(否→+0)。得分：1
- 坏死性软组织感染：皮肤损伤(否→+0)，慢性肝病(未提及→+0)，糖尿病(是→+1)，高龄(是→+1)。得分：2
- 风险因素总数：总共有【吸烟、过敏原吸入、呼吸道感染、皮肤损伤、慢性肝病、糖尿病、高龄】7个不重复因素。总数：7

初步输出：支气管哮喘急性发作:1, 坏死性软组织感染:2, 风险因素总数:7

然后调用analyze_disease_probability工具进行深入分析。

请按照上述步骤完成分析，并在初步分析后务必调用工具进行概率计算。

最后使用get_diagnostic_tests_for_disease工具获取疾病的推荐检查。

【重要】关于推荐检查的fallback策略及智能筛选：

步骤1：优先获取特异性检查
- 首先调用get_diagnostic_tests_for_disease工具获取特定疾病的诊断方法
- 如果返回结果包含"暂无诊断方法"、"知识图谱中未找到"等提示，进入步骤2

步骤2：获取通用检查库
- 调用get_common_diagnostic_methods工具（limit=15）获取知识图谱中的通用检查方法
- 该工具会返回按使用频率排序的通用诊断方法列表

步骤3：智能筛选与推理（关键步骤）
你必须根据以下因素进行深入推理，筛选出最合适的检查项目：

a) 患者症状匹配度
   - 分析患者的主要症状（如头痛、皮肤红肿、呼吸困难等）
   - 筛选与症状相关的检查（例如：头痛→头部CT/MRI，皮肤问题→皮肤活检）
   - 排除明显不相关的检查（例如：头痛患者不需要脚部X光）

b) 疾病特征相关性
   - 考虑最可能疾病的病理特征和累及系统
   - 例如：感染性疾病→血常规、CRP、血培养
   - 例如：代谢性疾病→血生化、尿常规
   
c) 检查的临床意义
   - 优先推荐能明确诊断或排除疾病的关键检查
   - 考虑检查的紧急性和必要性
   - 排除仅用于其他疾病的专科检查

d) 检查的普适性和可行性
   - 优先推荐基础且普适的检查（如血常规、基础影像学）
   - 考虑急诊场景的可行性

筛选原则（必须遵守）：
❌ 禁止：推荐与患者症状完全不相关的部位检查
   例如：头痛患者 → 不推荐脚部X光、腹部超声
   例如：皮肤感染 → 不推荐心电图、肺功能检查

✓ 应该：从通用检查中选择3-6个最相关的检查
✓ 应该：明确说明为什么选择这些检查
✓ 应该：按重要性排序推荐检查

工具使用示例：
场景：头痛患者，可能疾病"罕见脑部疾病X"
1. 调用get_diagnostic_tests_for_disease("罕见脑部疾病X") → 返回"暂无诊断方法"
2. 调用get_common_diagnostic_methods(limit=15) → 返回15个通用检查
   包括：头部CT、血常规、心电图、腹部B超、脚部X光、皮肤活检等
3. 智能筛选推理：
   - 患者主诉：头痛
   - 累及系统：神经系统
   - 相关检查：头部CT（直接相关）、血常规（排除感染）
   - 不相关检查：脚部X光（与头痛无关）、腹部B超（与症状无关）
4. 最终推荐：头部CT、血常规、脑电图（3-4个高度相关的检查）

【输出格式要求】
请严格按照以下格式输出：

<思考>
步骤1：比对风险因素
[说明比对了哪些风险因素，患者符合哪些]

步骤2：计算疾病得分
[列出每个疾病的得分和计算依据]

步骤3：调用分析工具
[说明调用了analyze_disease_probability工具，获得了什么结果]

步骤4：获取推荐检查
[说明先调用了get_diagnostic_tests_for_disease工具，获得了什么]
[如果返回"暂无诊断方法"，说明：]
  a) 调用了get_common_diagnostic_methods获取通用检查库
  b) 展示筛选推理过程：
     - 患者主要症状是什么
     - 疾病累及哪些系统/部位
     - 从通用检查中筛选出哪些相关检查
     - 排除了哪些不相关的检查，为什么排除
     - 最终选择的3-6个检查及选择理由
</思考>

<结论>
【诊断分析】
最可能疾病：[疾病名称]
置信度：[百分比]

【疾病概率分布】
[列出各疾病的概率]

【推荐检查项目】
[如果有特异性检查，直接列出]
[如果使用通用检查fallback，需要：]
  1. 说明"由于知识图谱中暂无该疾病的特异性诊断方法，以下是经过智能筛选的通用检查建议"
  2. 列出3-6个经过筛选的检查项目
  3. 对每个检查简要说明推荐理由（与患者症状/疾病的相关性）
  
示例格式（fallback场景）：
由于知识图谱中暂无该疾病的特异性诊断方法，以下是经过智能筛选的通用检查建议：

1. **头部CT扫描**
   - 推荐理由：患者主诉头痛，需要评估颅内结构是否异常
   
2. **血常规检查**
   - 推荐理由：评估是否存在感染或血液系统异常
   
3. **脑电图(EEG)**
   - 推荐理由：评估脑部电活动，排除神经系统功能异常

（已排除不相关检查：脚部X光、腹部超声等与头痛无关的检查）
</结论>
"""

class MedicalAnalysisNode:
    """医学分析节点"""
    
    def __init__(self, mcp_tools: Optional[List] = None):
        """
        初始化医学分析节点
        
        Args:
            mcp_tools: MCP服务提供的工具列表（可选）
        """
        # 基础工具
        base_tools = [analyze_disease_probability, get_diagnostic_tests_for_disease]
        
        # 如果提供了MCP工具，添加到工具列表
        # MCP工具中包含get_common_diagnostic_methods
        all_tools = base_tools + (mcp_tools or [])
        
        self.agent = create_react_agent(
            model=model,
            tools=all_tools,
            prompt=MEDICAL_ANALYSIS_PROMPT
        )
    
    def __call__(self, state: MedicalState) -> MedicalState:
        """
        执行医学分析
        
        Args:
            state: 包含消息和状态数据的字典
            
        Returns:
            更新后的状态
        """
        try:
            print("=== 开始医学分析 ===")
            
            # 调用智能体进行分析
            response = self.agent.invoke({
                "messages": state["messages"]
            })
            
            # 从响应中提取分析结果
            analysis_result = self._extract_analysis_result(response)
            if analysis_result:
                state["analysis_result"] = analysis_result
                
                # 生成格式化的结论消息
                from langchain_core.messages import AIMessage
                most_likely_disease = analysis_result.get("most_likely_disease", "未知")
                confidence = analysis_result.get("confidence", 0)
                disease_details = analysis_result.get("disease_details", {})
                
                # 构建结论文本
                conclusion_text = f"""<结论>
【诊断分析】
最可能疾病：{most_likely_disease}
置信度：{confidence}%

【疾病概率分布】
"""
                for disease, details in disease_details.items():
                    prob = details.get('probability', 0)
                    conclusion_text += f"- {disease}: {prob}%\n"
                
                conclusion_text += "\n【推荐检查项目】\n"
                # 获取推荐检查
                tests = get_diagnostic_tests_for_disease(most_likely_disease)
                for test in tests:
                    test_name = test.get('test_name', '')
                    test_desc = test.get('test_description', '')
                    conclusion_text += f"- {test_name}: {test_desc}\n"
                
                conclusion_text += "</结论>"
                
                # 将格式化的消息添加到状态
                # 保留原始agent响应作为思考过程，添加格式化结论
                original_messages = response["messages"]
                if original_messages and hasattr(original_messages[-1], 'content'):
                    # 将最后一条消息的内容与结论合并
                    original_content = original_messages[-1].content
                    combined_content = f"{original_content}\n\n{conclusion_text}"
                    original_messages[-1] = AIMessage(content=combined_content)
                
                state["messages"] = original_messages
            else:
                # 如果没有提取到结果，保留原始响应
                state["messages"] = response["messages"]
            
            print("=== 医学分析完成 ===")
            return state
            
        except Exception as e:
            print(f"医学分析节点执行错误: {e}")
            import traceback
            traceback.print_exc()
            # 添加错误信息到状态
            from langchain_core.messages import AIMessage
            state["messages"].append(AIMessage(
                content=f"<结论>\n分析过程中出现错误: {str(e)}\n</结论>"
            ))
            return state
    
    def _extract_analysis_result(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """从响应中提取分析结果"""
        try:
            print(">>> 开始提取分析结果...")
            messages = response.get("messages", [])
            
            # 方法1：查找ToolMessage类型的消息
            for i, msg in enumerate(messages):
                msg_type = type(msg).__name__
                print(f">>> 消息 {i}: 类型={msg_type}")
                
                # 检查是否是ToolMessage
                if msg_type == 'ToolMessage':
                    try:
                        # ToolMessage的content可能包含JSON结果
                        content = msg.content if hasattr(msg, 'content') else str(msg)
                        print(f">>> ToolMessage内容: {content[:200]}...")
                        
                        # 尝试解析JSON
                        import json
                        if isinstance(content, str):
                            result = json.loads(content)
                            if 'most_likely_disease' in result:
                                print(f">>> 成功提取结果: {result}")
                                return result
                    except Exception as e:
                        print(f">>> 解析ToolMessage失败: {e}")
                
                # 检查additional_kwargs中的tool_calls
                if hasattr(msg, 'additional_kwargs'):
                    tool_calls = msg.additional_kwargs.get('tool_calls', [])
                    if tool_calls:
                        print(f">>> 找到tool_calls: {len(tool_calls)}")
            
            # 方法2：从最后的消息内容中使用正则提取
            if messages:
                last_message = messages[-1]
                if hasattr(last_message, 'content'):
                    content = str(last_message.content)
                    print(f">>> 尝试从最后消息提取，内容长度: {len(content)}")
                    
                    # 查找工具调用结果的文本描述
                    import re
                    # 匹配 "最可能疾病：xxx" 和 "置信度：xx%"
                    disease_match = re.search(r'最可能.*?疾病[:：]\s*([^\n]+)', content)
                    confidence_match = re.search(r'置信度[:：]\s*(\d+\.?\d*)%', content)
                    
                    if disease_match and confidence_match:
                        most_likely_disease = disease_match.group(1).strip()
                        confidence = float(confidence_match.group(1))
                        print(f">>> 从文本提取: 疾病={most_likely_disease}, 置信度={confidence}")
                        
                        # 提取疾病概率分布
                        disease_details = {}
                        prob_matches = re.findall(r'([^:\n]+):\s*(\d+\.?\d*)%', content)
                        for disease_name, prob in prob_matches:
                            disease_name = disease_name.strip()
                            if disease_name and not any(k in disease_name for k in ['置信度', '步骤']):
                                disease_details[disease_name] = {
                                    'probability': float(prob),
                                    'score': 0
                                }
                        
                        return {
                            'most_likely_disease': most_likely_disease,
                            'confidence': confidence,
                            'disease_details': disease_details
                        }
            
            print(">>> 未能提取到分析结果")
                
        except Exception as e:
            print(f">>> 提取分析结果错误: {e}")
            import traceback
            traceback.print_exc()
        
        return {}

# ============================================================================
# MCP客户端初始化
# ============================================================================

async def initialize_mcp_client():
    """异步初始化MCP客户端"""
    mcp_config = get_mcp_config()
    client = MultiServerMCPClient(mcp_config["servers"])
    tools = await client.get_tools()
    return client, tools

# 全局缓存MCP客户端和工具
_mcp_client = None
_mcp_tools = None
_medical_analysis_node = None

def get_or_create_medical_analysis_node():
    """获取或创建medical_analysis_node（懒加载，包含MCP工具）"""
    global _mcp_client, _mcp_tools, _medical_analysis_node
    
    if _medical_analysis_node is None:
        # 尝试初始化MCP客户端
        if _mcp_client is None or _mcp_tools is None:
            try:
                loop = asyncio.get_running_loop()
                # 检测到运行中的循环，在新线程中初始化MCP客户端
                print(">>> 检测到运行中的事件循环，将在新线程中初始化MCP客户端...")
                
                def init_mcp_in_thread():
                    """在新线程中初始化MCP客户端"""
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(initialize_mcp_client())
                    finally:
                        try:
                            pending = asyncio.all_tasks(new_loop)
                            for task in pending:
                                task.cancel()
                            new_loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                        except:
                            pass
                        finally:
                            new_loop.close()
                
                # 使用线程池执行
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(init_mcp_in_thread)
                    try:
                        _mcp_client, _mcp_tools = future.result(timeout=30)
                        print(f">>> MCP客户端初始化成功，获得 {len(_mcp_tools)} 个工具")
                    except Exception as e:
                        print(f">>> 警告: MCP客户端初始化失败: {e}")
                        _mcp_client = None
                        _mcp_tools = []
                        
            except RuntimeError:
                # 没有运行中的循环，直接创建新循环初始化
                print(">>> 未检测到运行中的事件循环，创建新循环初始化MCP客户端...")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    _mcp_client, _mcp_tools = loop.run_until_complete(initialize_mcp_client())
                    print(f">>> MCP客户端初始化成功，获得 {len(_mcp_tools)} 个工具")
                except Exception as e:
                    print(f">>> 警告: MCP客户端初始化失败: {e}")
                    _mcp_client = None
                    _mcp_tools = []
                finally:
                    try:
                        pending = asyncio.all_tasks(loop)
                        for task in pending:
                            task.cancel()
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    except:
                        pass
                    finally:
                        loop.close()
                        asyncio.set_event_loop(None)
        
        # 创建medical_analysis_node实例，传入MCP工具
        _medical_analysis_node = MedicalAnalysisNode(mcp_tools=_mcp_tools)
        print(f">>> Medical Analysis Node 初始化完成，工具数: {len(_mcp_tools or []) + 2}")
    
    return _medical_analysis_node

# 创建节点实例（懒加载）
medical_analysis_node = None  # 将在首次使用时初始化

# 使用示例
def create_medical_analysis_graph() -> StateGraph:
    """创建医学分析图"""
    
    # 创建图
    workflow = StateGraph(MedicalState)
    
    # 添加节点
    workflow.add_node("medical_analysis", medical_analysis_node)
    
    # 设置入口点
    workflow.set_entry_point("medical_analysis")
    
    # 添加边
    workflow.add_edge("medical_analysis", END)
    
    # 编译图
    graph = workflow.compile()
    
    return graph

# 测试函数
def test_medical_analysis_node():
    """测试医学分析节点"""
    
    # 创建测试状态
    test_state = {
        "messages": [
            {   
                "role": "user", 
                "content": """
【可能疾病1】支气管哮喘急性发作
- 吸烟：患者是否有吸烟病史？
- 过敏原吸入：患者是否存在接触尘螨、花粉、宠物皮屑等过敏原的情况？
- 呼吸道感染：患者近期是否出现过呼吸道感染？

【可能疾病2】坏死性软组织感染
- 皮肤软组织损伤：患者是否有皮肤或软组织的创伤或挤压伤历史？
- 慢性肝病：患者是否有慢性肝病史？
- 糖尿病：患者是否存在糖尿病？
- 高龄：患者年龄是否≥60岁？

患者回答：有吸烟史、没有过敏现象、没有呼吸道感染、年龄66岁、有糖尿病、没有皮肤损伤
"""
            }
        ],
        "disease_data": {},
        "risk_factor_count": 0,
        "analysis_result": {},
        "diagnostic_tests": []
    }
    
    # 执行节点
    print("开始测试医学分析节点...")
    node = get_or_create_medical_analysis_node()
    result_state = node(test_state)
    
    # 输出结果
    print("\n=== 分析结果 ===")
    if "analysis_result" in result_state and result_state["analysis_result"]:
        print(f"分析结果: {json.dumps(result_state['analysis_result'], indent=2, ensure_ascii=False)}")
    
    # 输出最后的消息
    if result_state["messages"]:
        last_msg = result_state["messages"][-1]
        if hasattr(last_msg, 'content'):
            print(f"\n最终回复: {last_msg.content}")
        else:
            print(f"\n最终回复: {last_msg}")

# ============================================================================
# 供 flow.py 调用的适配函数
# ============================================================================

def recommend_node(state):
    """
    推荐节点 - 供flow.py调用的适配函数
    
    Args:
        state: 包含messages等字段的状态字典
        
    Returns:
        更新后的状态字典
    """
    from langchain_core.messages import HumanMessage
    
    try:
        # 获取或创建medical_analysis_node实例（包含MCP工具）
        node = get_or_create_medical_analysis_node()
        result_state = node(state)
        
        # ========== 结构化数据保存 ==========
        # 提取分析结果并保存
        analysis_result = result_state.get("analysis_result", {})
        patient_id = state.get("patient_id")
        
        if patient_id and analysis_result:
            try:
                from patient_model import patient_manager
                
                # 提取关键信息
                most_likely_disease = analysis_result.get("most_likely_disease", "")
                confidence = analysis_result.get("confidence", 0)
                disease_details = analysis_result.get("disease_details", {})
                
                # 获取最可能疾病的推荐检查
                recommended_tests = []
                if most_likely_disease:
                    # 调用get_diagnostic_tests_for_disease获取检查方法
                    tests = get_diagnostic_tests_for_disease(most_likely_disease)
                    recommended_tests = tests
                
                # 保存诊断信息
                patient_manager.update_diagnosis_info(
                    patient_id=patient_id,
                    most_likely_disease=most_likely_disease,
                    confidence=confidence,
                    disease_details=disease_details,
                    recommended_tests=recommended_tests
                )
                
                # 更新患者病史（只保存对风险问题的回答，即最后一条用户消息）
                messages = state.get("messages", [])
                # 查找最后一条用户消息
                last_user_message = None
                for msg in reversed(messages):
                    if hasattr(msg, 'type') and msg.type == 'human':
                        last_user_message = msg.content if hasattr(msg, 'content') else str(msg)
                        break
                    elif isinstance(msg, dict) and msg.get('role') == 'user':
                        last_user_message = msg.get('content', '')
                        break
                
                if last_user_message:
                    # 只保存最后一条用户回答（对风险问题的回答）
                    patient_manager.update_patient_info(
                        patient_id=patient_id,
                        patient_history=last_user_message
                    )
                    print(f">>> 已更新患者病史（风险问题回答）: {last_user_message[:50]}...")
                
            except Exception as e:
                print(f">>> 保存诊断数据失败: {e}")
        
        # 确保返回的格式符合flow.py的要求
        return result_state
        
    except Exception as e:
        print(f"推荐节点分析出错: {e}")
        import traceback
        traceback.print_exc()
        return {
            "messages": [HumanMessage(content=f"分析过程中出现错误: {str(e)}")]
        }

if __name__ == "__main__":
    # 测试节点
    test_medical_analysis_node()
    
    # 也可以创建完整的图进行测试
    print("\n=== 创建完整图 ===")
    graph = create_medical_analysis_graph()
    
    # 使用图进行推理
    test_input = {
        "messages": [
            {   
                "role": "user", 
                "content": """
【可能疾病1】支气管哮喘急性发作
- 吸烟：患者是否有吸烟病史？
- 过敏原吸入：患者是否存在接触尘螨、花粉、宠物皮屑等过敏原的情况？
- 呼吸道感染：患者近期是否出现过呼吸道感染？

【可能疾病2】坏死性软组织感染
- 皮肤软组织损伤：患者是否有皮肤或软组织的创伤或挤压伤历史？
- 慢性肝病：患者是否有慢性肝病史？
- 糖尿病：患者是否存在糖尿病？
- 高龄：患者年龄是否≥60岁？

患者回答：有吸烟史、没有过敏现象、没有呼吸道感染、年龄66岁、有糖尿病、没有皮肤损伤
"""
            }
        ]
    }
    
    print("使用图进行推理...")
    final_state = graph.invoke(test_input)
    print("推理完成!")