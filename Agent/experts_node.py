"""
多专家会诊节点 - Experts Node
使用langgraph实现多专家协作诊断，结合Redis向量库RAG进行知识检索
"""

import sys
import os
from typing import Dict, Any, List, TypedDict, Annotated
import operator
from langchain_core.messages import AnyMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import create_react_agent
import json

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入Redis RAG工具
try:
    from RAG.tools.rag import RedisVectorDB
except ImportError:
    print("警告: 无法导入RedisVectorDB，将使用模拟数据")
    RedisVectorDB = None

# ============================================================================
# 状态定义
# ============================================================================

class ExpertState(TypedDict, total=False):
    """
    专家会诊状态定义
    """
    # 输入信息
    messages: Annotated[list[AnyMessage], operator.add]
    test_results: str  # 检查结果
    patient_history: str  # 患者历史信息（从之前节点获取）
    triage_info: str  # 分诊信息
    analysis_result: Dict[str, Any]  # 之前的分析结果
    
    # RAG检索结果
    retrieved_knowledge: List[Dict[str, Any]]
    
    # 各专家诊断结果
    diagnostic_expert_opinion: str  # 诊断专家意见
    treatment_expert_opinion: str  # 治疗专家意见
    imaging_expert_opinion: str  # 影像专家意见
    
    # 最终报告
    final_report: str
    consultation_summary: str

# ============================================================================
# RAG知识检索功能
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
    
    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
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
                        'content': '模拟医学知识：根据临床指南，需要综合考虑患者症状、体征和实验室检查结果。',
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

def retrieve_medical_knowledge(query: str, top_k: int = 3) -> str:
    """
    工具函数：检索医学知识
    
    Args:
        query: 查询描述，如"坏死性软组织感染的诊断标准"
        top_k: 返回结果数量
        
    Returns:
        格式化的检索结果文本
    """
    retriever = get_knowledge_retriever()
    results = retriever.retrieve(query, top_k)
    
    if not results:
        return "未找到相关医学知识"
    
    # 格式化检索结果
    formatted_results = []
    for i, result in enumerate(results, 1):
        content = result.get('content', '')
        score = result.get('score', 0)
        formatted_results.append(
            f"[知识{i}] (相似度: {score:.2f})\n{content}"
        )
    
    return "\n\n".join(formatted_results)

# 导入配置
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import create_llm, REDIS_CONFIG

# ============================================================================
# 各专家节点定义
# ============================================================================

# 初始化大语言模型，使用统一配置
llm = create_llm()

DIAGNOSTIC_EXPERT_PROMPT = """你是一名资深诊断专家，专门负责综合分析患者的检查结果和临床表现。

【任务要求】
1. 仔细分析患者的检查结果和之前的诊断信息
2. 使用retrieve_medical_knowledge工具检索相关医学知识作为参考
3. 基于检索到的知识和临床经验，给出诊断意见

【输出格式】
请严格按照以下格式输出：

<思考>
步骤1：分析检查结果
[说明检查结果中的关键指标]

步骤2：检索医学知识
[说明检索到了哪些相关知识]

步骤3：形成诊断意见
[说明诊断的依据和推理过程]
</思考>


<结论>
## 诊断专家意见

### 检查结果分析
[详细分析各项检查指标的异常情况]

### 诊断依据
[结合临床表现和检查结果，说明诊断依据]

### 鉴别诊断
[列出需要鉴别的疾病及理由]

### 诊断结论
[给出明确的诊断结论及置信度]

【注意事项】
- 必须调用retrieve_medical_knowledge工具获取相关医学知识
- 所有结论必须有据可依
- 保持专业、客观的态度
"""

TREATMENT_EXPERT_PROMPT = """你是一名经验丰富的治疗专家，负责制定个体化治疗方案。

【任务要求】
1. 基于诊断结果和检查数据，制定治疗方案
2. 使用retrieve_medical_knowledge工具检索相关治疗指南和方案
3. 考虑患者的具体情况，给出个体化建议

【输出格式】
请严格按照以下格式输出：

<思考>
步骤1：分析诊断结果
[说明对诊断结果的理解]

步骤2：检索治疗方案
[说明检索到了哪些治疗指南]

步骤3：制定个体化方案
[说明为什么选择这个治疗方案]
</思考>

<结论>
## 治疗专家意见

### 治疗原则
[说明治疗的总体原则和目标]

### 推荐治疗方案
#### 药物治疗
[具体的药物选择、剂量、疗程]

#### 非药物治疗
[手术、物理治疗等其他治疗方式]

### 注意事项
[治疗过程中需要注意的事项]

### 预后评估
[预期治疗效果和预后情况]

【注意事项】
- 必须调用retrieve_medical_knowledge工具获取治疗指南
- 治疗方案要具体、可操作
- 考虑治疗的风险和收益
"""

IMAGING_EXPERT_PROMPT = """你是一名影像诊断专家，负责解读影像学检查结果。

【任务要求】
1. 分析影像学检查结果（如CT、MRI、X光等）
2. 使用retrieve_medical_knowledge工具检索相关影像学特征
3. 给出专业的影像学诊断意见

【输出格式】
请严格按照以下格式输出：

<思考>
步骤1：观察影像特征
[说明影像上看到的关键特征]

步骤2：检索影像学知识
[说明检索到的相关影像学特征]

步骤3：给出影像学诊断
[说明影像学诊断的依据]
</思考>

<结论>
## 影像专家意见

### 影像学表现
[详细描述影像学检查的异常发现]

### 影像学特征分析
[分析影像特征与疾病的相关性]

### 影像诊断建议
[给出影像学诊断结论]

### 进一步检查建议
[如需要，建议进行的补充检查]

【注意事项】
- 如果没有影像学检查结果，说明建议进行哪些影像检查
- 描述要准确、专业
- 必要时调用retrieve_medical_knowledge工具
"""

def diagnostic_expert_node(state: ExpertState):
    """诊断专家节点"""
    print(">>> 诊断专家正在分析...")
    
    try:
        # 创建诊断专家智能体
        agent = create_react_agent(
            model=llm,
            tools=[retrieve_medical_knowledge],
            prompt=DIAGNOSTIC_EXPERT_PROMPT
        )
        
        # 构建输入信息
        input_text = f"""
患者检查结果：
{state.get('test_results', '暂无检查结果')}

患者历史信息：
{state.get('patient_history', '暂无历史信息')}

分诊信息：
{state.get('triage_info', '暂无分诊信息')}

之前的分析结果：
{json.dumps(state.get('analysis_result', {}), ensure_ascii=False, indent=2)}

请基于以上信息进行诊断分析。
"""
        
        # 调用智能体
        response = agent.invoke({
            "messages": [HumanMessage(content=input_text)]
        })
        
        # 提取专家意见
        opinion = response["messages"][-1].content
        
        return {
            "diagnostic_expert_opinion": opinion,
            "messages": [AIMessage(content=f"诊断专家已完成分析")]
        }
        
    except Exception as e:
        print(f">>> 诊断专家分析出错: {e}")
        return {
            "diagnostic_expert_opinion": f"诊断分析出错: {str(e)}",
            "messages": [AIMessage(content=f"诊断专家分析出错")]
        }

def treatment_expert_node(state: ExpertState):
    """治疗专家节点"""
    print(">>> 治疗专家正在制定方案...")
    
    try:
        # 创建治疗专家智能体
        agent = create_react_agent(
            model=llm,
            tools=[retrieve_medical_knowledge],
            prompt=TREATMENT_EXPERT_PROMPT
        )
        
        # 构建输入信息
        input_text = f"""
诊断专家意见：
{state.get('diagnostic_expert_opinion', '暂无诊断意见')}

患者检查结果：
{state.get('test_results', '暂无检查结果')}

患者历史信息：
{state.get('patient_history', '暂无历史信息')}

之前的分析结果：
{json.dumps(state.get('analysis_result', {}), ensure_ascii=False, indent=2)}

请基于以上信息制定治疗方案。
"""
        
        # 调用智能体
        response = agent.invoke({
            "messages": [HumanMessage(content=input_text)]
        })
        
        # 提取专家意见
        opinion = response["messages"][-1].content
        
        return {
            "treatment_expert_opinion": opinion,
            "messages": [AIMessage(content=f"治疗专家已完成方案制定")]
        }
        
    except Exception as e:
        print(f">>> 治疗专家分析出错: {e}")
        return {
            "treatment_expert_opinion": f"治疗方案制定出错: {str(e)}",
            "messages": [AIMessage(content=f"治疗专家分析出错")]
        }

def imaging_expert_node(state: ExpertState):
    """影像专家节点"""
    print(">>> 影像专家正在解读...")
    
    try:
        # 创建影像专家智能体
        agent = create_react_agent(
            model=llm,
            tools=[retrieve_medical_knowledge],
            prompt=IMAGING_EXPERT_PROMPT
        )
        
        # 构建输入信息
        input_text = f"""
患者检查结果：
{state.get('test_results', '暂无检查结果')}

诊断专家意见：
{state.get('diagnostic_expert_opinion', '暂无诊断意见')}

请重点分析影像学检查部分，给出专业意见。
"""
        
        # 调用智能体
        response = agent.invoke({
            "messages": [HumanMessage(content=input_text)]
        })
        
        # 提取专家意见
        opinion = response["messages"][-1].content
        
        return {
            "imaging_expert_opinion": opinion,
            "messages": [AIMessage(content=f"影像专家已完成解读")]
        }
        
    except Exception as e:
        print(f">>> 影像专家分析出错: {e}")
        return {
            "imaging_expert_opinion": f"影像解读出错: {str(e)}",
            "messages": [AIMessage(content=f"影像专家分析出错")]
        }

def summary_node(state: ExpertState):
    """总结节点 - 整合各专家意见生成最终报告"""
    print(">>> 正在生成专家会诊报告...")
    
    try:
        # 总结提示词
        summary_prompt = """你是一名主任医师，负责整合多位专家的意见，生成最终的会诊报告。

【重要提示】
- 必须严格基于提供的患者信息撰写报告
- 不得编造或修改患者的年龄、病史等基本信息
- 所有信息必须来源于实际提供的数据

【患者信息】
{patient_info}

【专家意见】

诊断专家意见：
{diagnostic_opinion}

影像专家意见：
{imaging_opinion}

治疗专家意见：
{treatment_opinion}

【报告格式要求】
请严格按照以下格式生成会诊报告：

# 多专家会诊报告

## 一、患者基本信息与主诉
[严格根据上述患者信息总结，不得编造]

## 二、诊断专家意见
{diagnostic_opinion}

## 三、影像专家意见
{imaging_opinion}

## 四、治疗专家意见
{treatment_opinion}

## 五、综合分析与推理过程
[整合各专家意见，给出综合分析]
- 诊断确定性分析
- 治疗方案的合理性
- 各专家意见的一致性和分歧点

## 六、最终诊疗建议
### 诊断结论
[明确的诊断结论]

### 推荐治疗方案
[具体的治疗方案，包括药物、手术等]

### 随访建议
[后续随访和复查建议]

### 注意事项
[特别需要注意的事项]

## 七、预后评估
[对患者预后的评估]

---
会诊专家组
日期: {date}
"""
        
        # 准备专家意见
        diagnostic_opinion = state.get('diagnostic_expert_opinion', '暂无诊断专家意见')
        treatment_opinion = state.get('treatment_expert_opinion', '暂无治疗专家意见')
        imaging_opinion = state.get('imaging_expert_opinion', '暂无影像专家意见')
        
        # 提取患者信息
        patient_info_parts = []
        
        # 添加检查结果
        test_results = state.get('test_results', '')
        if test_results:
            patient_info_parts.append(f"检查结果：\n{test_results}")
        
        # 添加患者历史
        patient_history = state.get('patient_history', '')
        if patient_history:
            patient_info_parts.append(f"患者历史信息：\n{patient_history}")
        
        # 添加分诊信息
        triage_info = state.get('triage_info', '')
        if triage_info:
            patient_info_parts.append(f"分诊信息：\n{triage_info}")
        
        # 添加分析结果
        analysis_result = state.get('analysis_result', {})
        if analysis_result:
            patient_info_parts.append(f"前期分析结果：\n{json.dumps(analysis_result, ensure_ascii=False, indent=2)}")
        
        # 合并患者信息
        patient_info = "\n\n".join(patient_info_parts) if patient_info_parts else "暂无详细患者信息"
        
        # 获取当前日期
        from datetime import datetime
        current_date = datetime.now().strftime("%Y年%m月%d日")
        
        # 构建完整提示
        full_prompt = summary_prompt.format(
            patient_info=patient_info,
            diagnostic_opinion=diagnostic_opinion,
            imaging_opinion=imaging_opinion,
            treatment_opinion=treatment_opinion,
            date=current_date
        )
        
        # 调用LLM生成报告
        response = llm.invoke([
            {"role": "system", "content": "你是一名经验丰富的主任医师，负责撰写专业的会诊报告。你必须严格基于提供的患者实际信息，不得编造或臆测任何数据。"},
            {"role": "user", "content": full_prompt}
        ])
        
        final_report = response.content
        
        # 生成简短摘要
        summary = f"""
多专家会诊已完成。

参与专家：
- 诊断专家
- 治疗专家
- 影像专家

报告已生成，请查看详细内容。
"""
        
        return {
            "final_report": final_report,
            "consultation_summary": summary,
            "messages": [HumanMessage(content=final_report)]
        }
        
    except Exception as e:
        print(f">>> 生成报告出错: {e}")
        import traceback
        traceback.print_exc()
        error_report = f"生成会诊报告时出错: {str(e)}"
        return {
            "final_report": error_report,
            "consultation_summary": error_report,
            "messages": [HumanMessage(content=error_report)]
        }

# ============================================================================
# 构建专家会诊图
# ============================================================================

def build_experts_graph():
    """构建专家会诊工作流图"""
    
    # 创建状态图
    builder = StateGraph(ExpertState)
    
    # 添加各专家节点
    builder.add_node("diagnostic_expert", diagnostic_expert_node)
    builder.add_node("treatment_expert", treatment_expert_node)
    builder.add_node("imaging_expert", imaging_expert_node)
    builder.add_node("summary", summary_node)
    
    # 定义工作流：诊断专家 -> 影像专家和治疗专家并行 -> 总结
    builder.add_edge(START, "diagnostic_expert")
    builder.add_edge("diagnostic_expert", "imaging_expert")
    builder.add_edge("diagnostic_expert", "treatment_expert")
    builder.add_edge("imaging_expert", "summary")
    builder.add_edge("treatment_expert", "summary")
    builder.add_edge("summary", END)
    
    # 编译图
    graph = builder.compile()
    
    return graph

# 创建全局专家会诊图实例
experts_graph = build_experts_graph()

# ============================================================================
# 主节点函数 - 供flow.py调用
# ============================================================================

def experts_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    专家会诊主节点
    
    这是供flow.py调用的主要接口，用于替代原来的agen_node
    
    Args:
        state: 包含患者信息和检查结果的状态字典
        
    Returns:
        包含专家会诊报告的状态更新
    """
    print(">>> 启动多专家会诊系统...")
    
    try:
        # 从state中提取信息
        messages = state.get("messages", [])
        last_message = messages[-1] if messages else ""
        test_results = last_message.content if hasattr(last_message, 'content') else str(last_message)
        
        # 提取患者历史信息 - 改进版：包含所有对话历史
        patient_history_parts = []
        
        # 1. 初始症状描述（从第一条消息获取）
        if len(messages) >= 1:
            first_msg = messages[0]
            first_content = first_msg.content if hasattr(first_msg, 'content') else str(first_msg)
            patient_history_parts.append(f"初始症状：\n{first_content}")
        
        # 2. 分诊问题的回答（从第二条消息获取，如果存在）
        if len(messages) >= 2:
            second_msg = messages[1]
            second_content = second_msg.content if hasattr(second_msg, 'content') else str(second_msg)
            patient_history_parts.append(f"患者病史及情况：\n{second_content}")
        
        # 3. 分诊评估结果
        if state.get("triage2_result"):
            patient_history_parts.append(f"分诊评估：\n{state['triage2_result']}")
        
        # 4. 分诊问题（风险因素）
        if state.get("triage1_result"):
            patient_history_parts.append(f"风险因素评估：\n{state['triage1_result']}")
        
        # 5. 疾病分析结果
        analysis_result = state.get("analysis_result", {})
        if analysis_result and isinstance(analysis_result, dict):
            most_likely = analysis_result.get("most_likely_disease", "")
            confidence = analysis_result.get("confidence", 0)
            if most_likely:
                patient_history_parts.append(f"初步诊断：{most_likely}（置信度：{confidence}%）")
        
        # 合并患者历史信息
        patient_history = "\n\n".join(patient_history_parts)
        
        # 构建专家会诊输入
        expert_input = {
            "messages": [],
            "test_results": test_results,
            "patient_history": patient_history,
            "triage_info": state.get("triage2_result", ""),
            "analysis_result": state.get("analysis_result", {}),
            "retrieved_knowledge": [],
            "diagnostic_expert_opinion": "",
            "treatment_expert_opinion": "",
            "imaging_expert_opinion": "",
            "final_report": "",
            "consultation_summary": ""
        }
        
        # 执行专家会诊流程
        result = experts_graph.invoke(expert_input)
        
        # 返回最终报告
        final_report = result.get("final_report", "会诊报告生成失败")
        
        # ========== 结构化数据保存 ==========
        # 保存专家会诊信息
        patient_id = state.get("patient_id")
        if patient_id:
            try:
                from patient_model import patient_manager
                import re
                
                # 提取关键信息
                diagnostic_opinion = result.get("diagnostic_expert_opinion", "")
                imaging_opinion = result.get("imaging_expert_opinion", "")
                treatment_opinion = result.get("treatment_expert_opinion", "")
                
                # 从最终报告中提取诊断结论和治疗方案
                final_diagnosis = ""
                treatment_plan = ""
                prognosis = ""
                
                # 提取诊断结论
                diagnosis_match = re.search(r'### 诊断结论\s*\n\s*(.+?)(?=\n###|\n##|$)', final_report, re.DOTALL)
                if diagnosis_match:
                    final_diagnosis = diagnosis_match.group(1).strip()
                
                # 提取推荐治疗方案
                treatment_match = re.search(r'### 推荐治疗方案\s*\n\s*(.+?)(?=\n###|\n##|$)', final_report, re.DOTALL)
                if treatment_match:
                    treatment_plan = treatment_match.group(1).strip()
                
                # 提取预后评估
                prognosis_match = re.search(r'## 七、预后评估\s*\n\s*(.+?)(?=\n---|\n##|$)', final_report, re.DOTALL)
                if prognosis_match:
                    prognosis = prognosis_match.group(1).strip()
                
                # 保存专家会诊信息
                patient_manager.update_expert_consultation(
                    patient_id=patient_id,
                    diagnostic_opinion=diagnostic_opinion[:500] if len(diagnostic_opinion) > 500 else diagnostic_opinion,  # 限制长度
                    imaging_opinion=imaging_opinion[:500] if len(imaging_opinion) > 500 else imaging_opinion,
                    treatment_opinion=treatment_opinion[:500] if len(treatment_opinion) > 500 else treatment_opinion,
                    final_diagnosis=final_diagnosis,
                    treatment_plan=treatment_plan,
                    prognosis=prognosis
                )
                
                # 更新检查结果
                patient_manager.update_patient_info(
                    patient_id=patient_id,
                    test_results=test_results
                )
                
            except Exception as e:
                print(f">>> 保存专家会诊数据失败: {e}")
                import traceback
                traceback.print_exc()
        
        return {
            "messages": [HumanMessage(content=final_report)]
        }
        
    except Exception as e:
        print(f">>> 专家会诊系统出错: {e}")
        import traceback
        traceback.print_exc()
        return {
            "messages": [HumanMessage(content=f"专家会诊系统出错: {str(e)}")]
        }

# ============================================================================
# 测试代码
# ============================================================================

def test_experts_node():
    """测试专家会诊节点"""
    print("=" * 60)
    print("测试多专家会诊系统")
    print("=" * 60)
    
    # 模拟输入状态
    test_state = {
        "messages": [HumanMessage(content="""
患者检查结果：
- 血常规：白细胞 15.2×10^9/L (升高)
- CRP：156 mg/L (明显升高)
- PCT：2.8 ng/mL (升高)
- CT检查：右下肢软组织密度增高，可见气体影
- 局部皮温升高，红肿明显
        """)],
        "triage1_result": "患者主诉：右下肢疼痛、肿胀3天",
        "triage2_result": "分诊级别：I级（危重），建议科室：急诊外科",
        "combined_analysis": "初步考虑坏死性软组织感染可能",
        "analysis_result": {
            "most_likely_disease": "坏死性软组织感染",
            "confidence": 85.5
        }
    }
    
    # 执行专家会诊
    result = experts_node(test_state)
    
    # 输出结果
    print("\n" + "=" * 60)
    print("专家会诊报告")
    print("=" * 60)
    if result and "messages" in result:
        print(result["messages"][-1].content)
    else:
        print("未获得有效结果")
    print("=" * 60)

if __name__ == "__main__":
    test_experts_node()

