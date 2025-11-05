import asyncio
from langchain_core.prompts import prompt
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.constants import END, START
from typing import Annotated, TypedDict, Dict, Any, List
from langchain_core.messages import AnyMessage, HumanMessage
from langgraph.graph import StateGraph
from langgraph.config import get_stream_writer 
from langgraph.checkpoint.memory import InMemorySaver
import operator
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
import sys
import os
import json
import math
import numpy as np
from neo4j import GraphDatabase
import re

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入各个节点的实现
from triage_node import triage_node as triage_node_impl
from recommend_node import recommend_node as recommend_node_impl
from experts_node import experts_node
from query_node import query_node as query_node_impl

# 导入配置
from config import create_llm, get_neo4j_config

# Neo4j配置
neo4j_config = get_neo4j_config()
NEO4J_URI = neo4j_config["uri"]
NEO4J_USER = neo4j_config["user"]
NEO4J_PASS = neo4j_config["password"]

# 系统中所有可用的节点类型 - 更新为医疗相关节点
nodes = ["triage_node", "recommend_node", "agen_node", "other"]

# 初始化大语言模型，使用统一配置
llm = create_llm()

# ============================================================================
# 状态定义
# ============================================================================

class State(TypedDict, total=False):
    """
    系统状态定义类
    使用total=False允许部分字段可选
    """
    messages: Annotated[list[AnyMessage], operator.add]
    type: str
    # 患者唯一标识符（用于保存结构化数据）
    patient_id: str
    # 用于recommend_node的字段
    disease_data: Dict[str, Any]
    risk_factor_count: int
    analysis_result: Dict[str, Any]
    diagnostic_tests: List[Dict[str, Any]]
    # 用于triage_node的字段
    user_input: str
    triage1_result: str
    triage2_result: str
    combined_analysis: str
    # 新增：记录是否已经进行了分诊
    has_triaged: bool
    # 新增：记录分诊时的问题
    triage_questions: str

# ============================================================================
# Recommend Node 功能 - 风险分析节点
# ============================================================================

def recommend_node(state: State):
    """
    推荐节点 - 医学分析节点（调用独立文件中的实现）
    """
    return recommend_node_impl(state)

# ============================================================================
# Triage Node 功能 - 分诊节点
# ============================================================================

def triage_node(state: State):
    """
    分诊节点 - 并行分诊处理（调用独立文件中的实现）
    """
    return triage_node_impl(state)

# ============================================================================
# Experts Node 功能 - 多专家会诊节点
# ============================================================================

def agen_node(state: State):
    """
    多专家会诊节点（调用独立文件中的实现）
    """
    return experts_node(state)

# ============================================================================
# Other Node 功能
# ============================================================================

def other_node(state: State):
    """
    医学知识查询节点（调用独立文件中的实现）
    """
    return query_node_impl(state)

# ============================================================================
# Supervisor Node 功能 - 改进版本
# ============================================================================

def supervisor_node(state: State):
    """
    监督节点 - 医疗任务分类和路由控制中心
    """
    print(">>> 正在分析问题类型...")
    
    # 获取最后一条用户消息
    last_message = state["messages"][-1] if state["messages"] else ""
    user_input = last_message.content if hasattr(last_message, 'content') else str(last_message)
    
    # ========== 上下文感知路由逻辑 ==========
    # 检查工作流状态，确保按照正确顺序执行
    has_triaged = state.get("has_triaged", False)
    has_diagnosis = state.get("analysis_result") and bool(state.get("analysis_result"))
    
    # 如果已经分诊但还没有诊断，且输入不是明显的新症状，强制路由到recommend_node
    if has_triaged and not has_diagnosis:
        # 检查是否是新的症状描述（包含"患者"关键词）
        if not ("患者出现" in user_input or "患者主诉" in user_input or "患者症状" in user_input):
            print(f">>> 已分诊但未诊断，强制路由到 recommend_node（回答问题）")
            return {"type": "recommend_node"}
    
    # 医疗任务分类提示词 - 增强版，包含上下文感知
    prompt = """你是一个专业医疗任务分发者，负责对医生输入的内容进行分类，并将任务分给其他Agent执行。

分类规则：
1. 如果输入的是对患者症状的相关描述（如"患者出现胸痛、呼吸困难"），返回 triage_node
2. 如果输入的是患者个人情况、病史、或对之前问题的回答（如"有糖尿病、高血压"），返回 recommend_node
3. 如果输入的是推荐检查的结果（如"血常规结果显示..."、"CK水平升高"），返回 agen_node
4. 如果是医学知识查询或疾病咨询（如"什么是坏死性软组织感染？"、"LRINEC评分如何使用？"、"这种疾病有什么治疗方法？"），返回 other

注意：
- 区分"患者症状"和"疾病知识查询"：前者是具体患者的情况，后者是一般性的医学知识问题
- 只返回上述选项之一，不要添加任何解释或其他内容"""
    
    # 构建对话提示
    prompts = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_input}
    ]
    
    # 调用LLM进行问题分类
    response = llm.invoke(prompts)
    typeRes = response.content.strip()
    
    print(f">>> 分类结果: {typeRes}")
    
    # 验证分类结果是否在有效节点列表中
    if typeRes in nodes:
        return {"type": typeRes}
    else:
        print(f">>> 未知的分类结果 '{typeRes}'，路由到 other_node")
        return {"type": "other"}

# 已移除 _looks_like_answer_to_triage 函数
# 原因：LLM 的智能分类已经足够准确，不需要额外的规则判断
# 简化后的设计更可靠，减少了误判的可能性

def routing_func(state: State):
    """
    条件路由函数
    """
    if state["type"] == "triage_node":
        return "triage_node"
    elif state["type"] == "recommend_node":
        return "recommend_node"
    elif state["type"] == "agen_node":
        return "agen_node"
    elif state["type"] == END:
        return END
    else:
        return "other_node"

# ============================================================================
# 构建状态图
# ============================================================================

# 创建状态图构建器
builder = StateGraph(State)

# 添加所有节点到图中
builder.add_node("supervisor_node", supervisor_node)
builder.add_node("triage_node", triage_node)
builder.add_node("recommend_node", recommend_node)
builder.add_node("agen_node", agen_node)
builder.add_node("other_node", other_node)

# 添加图的连接关系
builder.add_edge(START, "supervisor_node")

# 添加条件边：监督节点根据分类结果路由到不同节点
builder.add_conditional_edges(
    "supervisor_node", 
    routing_func, 
    ["triage_node", "recommend_node", "agen_node", "other_node", END]
)

# 为每个工作节点添加结束边
builder.add_edge("triage_node", END)
builder.add_edge("recommend_node", END)
builder.add_edge("agen_node", END)
builder.add_edge("other_node", END)

# 构建最终的执行图
checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)

# ============================================================================
# 多轮对话和输出优化
# ============================================================================

def format_output(result_state):
    """格式化输出结果"""
    if not result_state or "messages" not in result_state:
        return "未获得有效结果"
    
    # 获取最后一条消息
    messages = result_state["messages"]
    if not messages:
        return "无回复内容"
    
    last_message = messages[-1]
    content = last_message.content if hasattr(last_message, 'content') else str(last_message)
    
    # 清理格式
    content = content.strip()
    
    # 添加分隔线
    formatted_output = "\n" + "="*60 + "\n"
    formatted_output += "医疗助手回复:\n"
    formatted_output += "="*60 + "\n"
    formatted_output += content + "\n"
    formatted_output += "="*60 + "\n"
    
    return formatted_output

def multi_round_chat():
    """多轮对话主函数"""
    print("\n" + "="*60)
    print("欢迎使用医疗多智能体系统")
    print("="*60)
    print("系统功能:")
    print("- 症状分诊 (输入: 患者出现...)")
    print("- 医学分析 (输入: 患者病史/回答问题)") 
    print("- 检查结果分析 (输入: 检查结果)")
    print("- 医学知识查询 (输入: 什么是...? 如何...?)")
    print("- 输入 '退出' 或 'quit' 结束对话")
    print("="*60)
    
    # 配置执行参数 - 每个会话使用唯一的thread_id
    import uuid
    thread_id = str(uuid.uuid4())
    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }
    
    conversation_count = 0
    
    while True:
        try:
            # 获取用户输入
            if conversation_count == 0:
                user_input = input("\n请输入患者情况: ").strip()
            else:
                user_input = input("\n请继续回答问题或输入新的患者情况 (输入'退出'结束): ").strip()
            
            if user_input.lower() in ['退出', 'quit', 'exit']:
                print("\n感谢使用医疗多智能体系统，再见！")
                break
            
            if not user_input:
                print("输入不能为空，请重新输入。")
                continue
            
            conversation_count += 1
            
            print(f"\n>>> 处理第 {conversation_count} 轮对话...")
            
            # 准备输入状态 - 只添加新消息
            # checkpointer会自动从上一轮状态中恢复其他字段
            input_data = {
                "messages": [HumanMessage(content=user_input)]
            }
            
            # 如果是第一轮对话，需要初始化所有字段
            if conversation_count == 1:
                input_data.update({
                    "patient_id": thread_id,  # 使用thread_id作为患者ID
                    "type": "",
                    "disease_data": {},
                    "risk_factor_count": 0,
                    "analysis_result": {},
                    "diagnostic_tests": [],
                    "user_input": "",
                    "triage1_result": "",
                    "triage2_result": "",
                    "combined_analysis": "",
                    "has_triaged": False,
                    "triage_questions": ""
                })
                print(f">>> 新建患者记录，患者ID: {thread_id}")
            
            # 执行图推理
            result_state = graph.invoke(input_data, config)
            
            # 格式化输出
            formatted_output = format_output(result_state)
            print(formatted_output)
            
        except KeyboardInterrupt:
            print("\n\n用户中断对话，再见！")
            break
        except Exception as e:
            print(f"\n处理过程中出现错误: {e}")
            import traceback
            traceback.print_exc()
            print("请重新输入您的问题。")

# ============================================================================
# 测试代码
# ============================================================================

if __name__ == "__main__":
    # 直接启动多轮对话
    multi_round_chat()