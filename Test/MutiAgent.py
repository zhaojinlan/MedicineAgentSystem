"""
多智能体系统 - 基于LangGraph的客服助手系统
==============================================

这个文件实现了一个多智能体系统，包含以下功能：
1. 问题分类和路由（supervisor）
2. 旅游路线规划（travel）
3. 笑话生成（joke）
4. 查询操作（query）
5. 其他问题处理（other）

系统使用LangGraph框架构建状态图，通过条件路由将用户问题分发给相应的智能体处理。
"""

import asyncio
from nt import system
from langchain_core.prompts import prompt
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.constants import END, START
from typing import Annotated, TypedDict
from langchain_core.messages import AnyMessage, HumanMessage
from langgraph.graph import StateGraph
from langgraph.config import get_stream_writer 
from langgraph.checkpoint.memory import InMemorySaver
import operator  # 添加这个重要导入

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from RedisRAG import RedisVectorDB

# 系统中所有可用的节点类型
nodes = ["supervisor", "joke", "query", "travel", "other"]

# 初始化大语言模型，使用通义千问2.5模型
llm = ChatOpenAI(
    model="qwen2.5:14b",
    base_url="https://zjlchat.vip.cpolar.cn/v1",
    api_key="EMPTY",
    temperature=0.1,  # 较低的温度值，确保回答更加稳定
    top_p=0.8        # 核采样参数，控制生成的多样性
)

class State(TypedDict):
    """
    系统状态定义类
    
    Attributes:
        messages: 消息列表，使用operator.add进行累积操作
        type: 当前处理的任务类型，用于路由决策
    """
    messages: Annotated[list[AnyMessage], operator.add]  # 消息列表，支持累积添加
    type: str  # 任务类型标识

def other_node(state: State):
    """
    其他问题处理节点
    
    当用户的问题不属于旅游、笑话、查询等特定类别时，
    由该节点处理，返回通用提示信息。
    
    Args:
        state: 当前系统状态
        
    Returns:
        dict: 包含回复消息和节点类型的字典
    """
    print(">>>other_node")
    writer = get_stream_writer()
    writer({"node": ">>>other_node"})
    return {"messages": [HumanMessage(content="我暂时无法实现")], "type": "other"}

def supervisor_node(state: State):
    """
    监督节点 - 问题分类和路由控制中心
    
    这是整个多智能体系统的核心节点，负责：
    1. 分析用户问题内容
    2. 根据问题类型进行分类
    3. 将任务路由到相应的专业智能体
    4. 监控任务完成状态
    
    Args:
        state: 当前系统状态
        
    Returns:
        dict: 包含分类结果或结束标志的字典
    """
    print(">>>supervisor_node")
    writer = get_stream_writer()
    writer({"node": ">>>supervisor_node"})
    
    # 问题分类提示词，指导LLM进行准确的分类
    prompt = """你是一个专业的客服助手，负责对用户的问题进行分类，并将任务分给其他Agent执行。
    如果用户的问题是和旅游路线规划相关的，那就返回 travel。
    如果用户的问题是希望讲一个笑话，那就返回 joke。
    如果用户的问题是需要查询信息，那就返回 query。
    如果是其他的问题，返回 other
    除了这几个选项外，不要返回任何其他的内容。"""
    
    # 获取最后一条用户消息
    last_message = state["messages"][-1] if state["messages"] else ""
    
    # 构建对话提示
    prompts = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": last_message.content if hasattr(last_message, 'content') else str(last_message)}
    ]
    
    # 检查是否已经有处理结果，如果有则直接结束流程
    if "type" in state and state["type"]:
        writer({"supervisor_step": f"已获得分类结果：{state['type']}智能体处理结果"})
        return {"type": END}
    else:
        # 调用LLM进行问题分类
        response = llm.invoke(prompts)
        typeRes = response.content
        writer({"supervisor_step": f"问题分类结果：{typeRes}"})
        
        # 验证分类结果是否在有效节点列表中
        if typeRes in nodes:
            return {"type": typeRes}
        else:
            return {"type": "other"}  # 默认路由到其他节点

def travel_node(state: State):
    """
    旅游路线规划节点
    
    专门处理旅游相关的用户请求，包括：
    1. 路线规划
    2. 景点推荐
    3. 交通方式选择
    4. 地图导航等功能
    
    该节点集成了高德地图API，能够提供实时的路线规划和导航服务。
    
    Args:
        state: 当前系统状态
        
    Returns:
        dict: 包含规划结果和节点类型的字典
    """
    print(">>>travel_node")
    writer = get_stream_writer()
    writer({"node": ">>>travel_node"})

    # 旅游规划师系统提示词
    systemprompt="你是一个旅游规划师，根据用户的要求规划一条旅游路线。请用中文回答"
    prompts = [
        {"role": "system", "content": systemprompt},
        {"role": "user", "content": state["messages"][0]},
    ]    

    # 初始化高德地图MCP客户端，用于获取地图相关工具
    client = MultiServerMCPClient({
            "amap-maps": {
                "url": "https://dashscope.aliyuncs.com/api/v1/mcps/amap-maps/sse",
                "headers": {
                    "Authorization": "Bearer sk-e7b047109ea64152b127e608b7daf85e"
                },
                "transport": "sse"
            }
        })

    # 异步获取地图工具集
    tools = asyncio.run(client.get_tools()) 
    
    # 创建ReAct智能体，集成地图工具
    agent = create_react_agent(
        model=llm,
        tools=tools,
    )
    
    # 调用智能体处理旅游规划请求
    response=agent.invoke({"messages":prompts})
    writer({"travel_result":response["messages"][-1].content})
    return {"messages": [HumanMessage(content=response["messages"][-1].content)], "type": "travel"}

def joke_node(state: State):
    """
    笑话生成节点
    
    专门负责生成各种类型的笑话，包括：
    1. 日常生活中的幽默故事
    2. 轻松搞笑的对话
    3. 符合用户要求的特定主题笑话
    
    限制笑话长度不超过100字，确保内容简洁有趣。
    
    Args:
        state: 当前系统状态
        
    Returns:
        dict: 包含生成的笑话内容和节点类型的字典
    """
    print(">>>joke_node")
    writer = get_stream_writer()
    writer({"node": ">>>joke_node"})
    
    # 笑话大师系统提示词，限制输出长度
    systemprompt="你是一个笑话大师，根据用户的要求写一个不超过一百字的笑话"
    prompts = [
        {"role": "system", "content": systemprompt},
        {"role": "user", "content": state["messages"][0]},
    ]    
    
    # 调用LLM生成笑话
    response=llm.invoke(prompts)
    writer({"joke_result":response.content})
    return {"messages":[HumanMessage(content=response.content)],"type":"joke"}

def query_node(state: State):
    """
    查询操作节点
    
    专门处理用户的信息查询请求，包括：
    1. 知识问答
    2. 信息检索
    3. 数据查询
    4. 事实核查等功能
    
    该节点集成了Redis向量数据库，能够进行相似性搜索和知识库查询。
    
    Args:
        state: 当前系统状态
        
    Returns:
        dict: 包含查询结果和节点类型的字典
    """
    print(">>>query_node")
    writer = get_stream_writer()
    writer({"node": ">>>query_node"})
    
    # 初始化Redis向量数据库
    print("DEBUG: 调用writer - 正在连接向量数据库...")
    writer({"query_step": "正在连接向量数据库..."})
    vector_db = RedisVectorDB(
        host='localhost',
        port=6379,
        password=None,
        embedding_model_path=r"O:\MyProject\RAG\models\m3e-base"
    )
    
    # 使用现有索引（假设您已经创建了索引）
    index_name = "documents"
    print("DEBUG: 调用writer - 向量数据库连接完成")
    writer({"query_step": "向量数据库连接完成，使用现有索引"})
    
    # 获取用户查询内容
    user_query = state["messages"][0].content if hasattr(state["messages"][0], 'content') else str(state["messages"][0])
    
    # 在向量数据库中搜索相似内容
    writer({"query_step": f"正在搜索相关文档: {user_query}"})
    search_results = vector_db.search_similar(index_name, user_query, top_k=3)
    
    # 构建上下文信息
    context_info = ""
    if search_results:
        writer({"query_step": f"找到 {len(search_results)} 个相关文档"})
        context_info = "基于知识库检索到的相关信息：\n"
        for i, result in enumerate(search_results, 1):
            context_info += f"{i}. {result['text']}\n"
            context_info += f"   相似度: {result['score']:.4f}\n"
            if result['metadata']:
                context_info += f"   元数据: {result['metadata']}\n"
        context_info += "\n"
    else:
        writer({"query_step": "未找到相关文档，将基于通用知识回答"})
    
    # 构建增强的查询提示词
    systemprompt = f"""你是一个专业的查询助手，能够基于提供的信息和你的知识为用户提供准确、详细的回答。

{context_info}

请根据以上信息（如果有的话）和你的知识来回答用户的问题。如果提供的信息与问题相关，请优先使用这些信息。请用中文回答，确保回答准确、详细且有用。"""
    
    prompts = [
        {"role": "system", "content": systemprompt},
        {"role": "user", "content": user_query},
    ]    
    
    # 调用LLM进行查询处理
    writer({"query_step": "正在生成回答..."})
    response = llm.invoke(prompts)
    
    # 记录查询结果
    writer({"query_result": response.content})
    return {"messages": [HumanMessage(content=response.content)], "type": "query"}

def routing_func(state: State):
    """
    条件路由函数
    
    根据supervisor节点的分类结果，决定下一步应该执行哪个节点。
    这是整个多智能体系统的路由控制逻辑。
    
    Args:
        state: 当前系统状态，包含type字段用于路由决策
        
    Returns:
        str: 下一个要执行的节点名称，或END表示流程结束
        
    Note:
        - 查询操作统一使用 "query" 类型
        - 所有未知类型都会路由到other_node
    """
    if state["type"] == "travel":
        return "travel_node"
    elif state["type"] == "joke":
        return "joke_node"
    elif state["type"] == "query":  # 查询操作路由
        return "query_node"  # 返回的节点名称
    elif state["type"] == END:
        return END
    else:
        return "other_node"
    
# ============================================================================
# 构建状态图 - 多智能体系统架构定义
# ============================================================================

# 创建状态图构建器
builder = StateGraph(State)

# 添加所有节点到图中
builder.add_node("supervisor_node", supervisor_node)  # 监督节点：问题分类和路由
builder.add_node("travel_node", travel_node)          # 旅游节点：路线规划
builder.add_node("joke_node", joke_node)              # 笑话节点：笑话生成
builder.add_node("query_node", query_node)            # 查询节点：信息查询
builder.add_node("other_node", other_node)            # 其他节点：通用处理

# 添加图的连接关系
builder.add_edge(START, "supervisor_node")  # 从开始节点连接到监督节点

# 添加条件边：监督节点根据分类结果路由到不同节点
builder.add_conditional_edges(
    "supervisor_node", 
    routing_func, 
    ["travel_node", "joke_node", "query_node", "other_node", END]  # 所有可能的目标节点
)

# 为每个工作节点添加结束边：完成任务后直接结束流程
builder.add_edge("travel_node", END)
builder.add_edge("joke_node", END)
builder.add_edge("query_node", END)
builder.add_edge("other_node", END) 

# 构建最终的执行图
checkpointer = InMemorySaver()  # 内存检查点保存器，用于状态持久化
graph = builder.compile(checkpointer=checkpointer)  # 编译生成可执行的状态图

# ============================================================================
# 测试代码 - 多智能体系统运行示例
# ============================================================================

if __name__ == "__main__":
    # 配置执行参数
    config = {
        "configurable": {  # 可配置参数
            "thread_id": "1"  # 线程ID，用于区分不同的对话会话
        }
    }
    
    # 流式执行示例 - 可以看到所有中间步骤和writer输出
    print("=== 多智能体系统测试：查询测试 ===")
    
    # 使用debug模式来查看详细的执行过程
    for chunk in graph.stream(
        {"messages": [HumanMessage(content="帮我查询人工智能和神经网络是什么")]},
        config,
        stream_mode="debug"
    ):
        print("DEBUG CHUNK:", chunk)

    # 直接调用示例（已注释）
    # res = graph.invoke(
    #     {"messages": ["帮我查询人工智能和神经网络是什么"]},  # 用户请求
    #     config,
    #     stream_mode="values"  # 流式模式
    # )
    # print(f"系统回复：{res['messages'][-1].content}")
