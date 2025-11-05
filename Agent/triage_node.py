import asyncio
from typing import TypedDict
from langchain_core.messages import AnyMessage, HumanMessage
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import InMemorySaver
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from langchain_mcp_adapters.client import MultiServerMCPClient

# 定义状态
class ParallelState(TypedDict):
    user_input: str
    triage1_result: str
    triage2_result: str
    combined_analysis: str

class ParallelTriageNode:
    """并行分诊节点 - 封装两个智能体作为一个可重用节点"""
    
    def __init__(self, llm, mcp_client, mcp_tools):
        """
        初始化并行分诊节点
        
        Args:
            llm: 语言模型实例
            mcp_client: MCP客户端
            mcp_tools: MCP工具
        """
        self.llm = llm
        self.client = mcp_client
        self.tools = mcp_tools
        
        # 创建第一个智能体（医学顾问）
        self.triage1_agent = create_react_agent(
            model=llm,
            tools=mcp_tools,
        )
        
        # 第二个智能体的提示词
        self.triage_prompt = """【系统角色与核心指令】
你是一名专业的急诊分诊AI助手。你的任务是：仅根据用户输入的一段患者症状描述，进行一次性、非诊断性的分诊评估。你必须直接输出结构化的分诊建议，包含分诊级别和建议科室，全程不得向用户提问或要求更多信息。

【分析逻辑与判断标准】
你将遵循以下步骤进行内部分析：

信息提取与风险评估：
迅速扫描症状描述，识别所有危重指征。

关键危重指征（Ⅰ级/Ⅱ级）包括但不限于：
生命威胁：心跳呼吸骤停、窒息、严重呼吸困难、昏迷、无反应、大动脉活动性出血。
严重症状：剧烈胸痛并放射至左臂/后背、突发偏瘫/口眼歪斜/言语不清、严重过敏反应（喉头水肿、休克）、抽搐持续状态、剧烈头痛伴呕吐/意识改变。
高危情况：休克表现（面色苍白、湿冷、脉搏微弱）、严重创伤（多发伤、高位脊髓损伤）、体温＞41℃或＜35℃。

确定分诊级别：
根据上述危重指征，遵循"就高不就低"原则，将患者归入最高匹配的级别。

Ⅰ级（濒危）：存在任何一项生命威胁指征。
Ⅱ级（危重）：存在任何一项严重症状或高危情况指征，但暂无即刻的生命停止风险。
Ⅲ级（紧急）：病情稳定但可能恶化。例如：高热伴寒战、中度腹痛、肾绞痛、哮喘发作（用药后可部分缓解）、开放性骨折但出血已控制。
Ⅳ级（次紧急）：病情稳定，急性发作。例如：轻度发热、呕吐腹泻无脱水、扭伤、皮疹、尿路感染。
Ⅴ级（非紧急）：慢性问题或轻微症状。例如：慢性病复查、轻微感冒、健康咨询。

推荐就诊科室：
基于症状的主要部位和性质进行判断。

急诊内科：发热、感染、腹痛、呕吐腹泻、胸痛、呼吸困难、头晕、头痛、意识问题、中毒等。
急诊外科：各类外伤、撞击伤、切割伤、烧伤、动物咬伤、急性腹痛（怀疑阑尾炎、肠梗阻、穿孔等）。
急诊骨科：骨折、脱位、扭伤、拉伤、背部或肢体急性疼痛与活动受限。
神经内科/急诊神经科：突发头痛、眩晕、抽搐、偏瘫、麻木、言语不清、面瘫。
其他：根据具体情况，也可能建议儿科急诊（儿童患者）、心血管内科（疑似心绞痛）、皮肤科（主要问题为皮疹）等。

【输出模板】
你必须严格使用以下格式输出：

<思考>
步骤1：症状识别
[列出识别到的关键症状]

步骤2：危重指征判断
[说明是否存在危重指征，如何判断的]

步骤3：分诊级别确定
[解释为什么选择这个级别]

步骤4：科室推荐
[说明推荐科室的理由]
</思考>

<结论>
分诊级别： [填写对应的罗马数字级别，后跟中文说明]
建议科室： [填写最优先的1-2个科室]
核心依据： [用简短的1-2句话说明为何定为此级别和科室，引用输入中的关键症状]
</结论>"""
    
    async def __call__(self, state: ParallelState) -> ParallelState:
        """
        执行并行分诊节点
        
        Args:
            state: 包含用户输入的状态
            
        Returns:
            更新后的状态，包含两个智能体的结果和合并分析
        """
        user_input = state["user_input"]
        
        # 并行执行两个智能体
        triage1_result, triage2_result = await asyncio.gather(
            self._run_triage1(user_input),
            self._run_triage2(user_input)
        )
        
        # 合并结果
        combined_analysis = self._combine_results(triage1_result, triage2_result)
        
        return {
            "triage1_result": triage1_result,
            "triage2_result": triage2_result,
            "combined_analysis": combined_analysis
        }
    
    async def _run_triage1(self, user_input: str) -> str:
        """运行第一个智能体：医学顾问，负责风险因素确认问诊"""
        
        response = await self.triage1_agent.ainvoke({
            "messages": [
                {"role":"system","content":"""
你是一个专业的医学顾问。请严格遵循以下流程进行问诊：

【流程说明】
1. 风险因素获取：根据医生对患者描述的症状，使用工具获取相关的医学风险因素
2. 针对性提问：基于获得的风险因素，生成具体的问诊问题

【输出格式要求】
请严格按照以下模板输出：

<思考>
步骤1：使用工具获取风险因素
[说明调用了什么工具，获取了哪些疾病的风险因素]

步骤2：分析风险因素
[列出关键的风险因素]

步骤3：生成问诊问题
[说明为什么选择这些问题]
</思考>

<结论>
【可能疾病1】
【风险因素的名称】：针对的提问
【风险因素的名称】：针对的提问

【可能疾病2】
【风险因素的名称】：针对的提问
【风险因素的名称】：针对的提问
</结论>

---
**格式规范：**
- 每个问题必须以对应的风险的名称开头
- 每个问题必须使用"患者是否有[风险因素]病史？"或"患者是否存在[风险因素]？"的句式
                 
 

【注意事项】
- 仅基于工具获取的风险因素生成问题
- 不得引入外部医学知识或主观推断
- 保持问题简洁专业，聚焦于病史和风险因素确认
- 使用中文进行提问，表述清晰易懂
- 先输出一遍使用工具后得到的结果，再进行问题的提出                
                """},
                {"role": "user", "content": user_input}
            ]
        })
        
        return response["messages"][-1].content
    
    async def _run_triage2(self, user_input: str) -> str:
        """运行第二个智能体：急诊分诊，负责分诊评估"""
        
        prompt = [
            {"role": "system", "content": self.triage_prompt},
            {"role": "user", "content": user_input},
        ]
        
        response = await self.llm.ainvoke(prompt)
        return response.content
    
    def _combine_results(self, triage1_result: str, triage2_result: str) -> str:
        """合并两个智能体的分析结果"""
        
        combined = f"""


{triage2_result}

{triage1_result}

"""
        
        return combined


# 使用示例和工具函数
async def initialize_mcp_client():
    """异步初始化 MCP 客户端"""
    client = MultiServerMCPClient({
        "triage": {
            "url": "http://localhost:8000/sse",
            "headers": {},
            "transport": "sse"
        }
    })
    
    # 获取工具
    tools = await client.get_tools()
    print(f"成功加载 {len(tools)} 个工具")
    return client, tools

# 导入配置
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import create_llm

# 使用示例
async def main():
    """使用示例"""
    # 初始化组件
    llm = create_llm()
    client, tools = await initialize_mcp_client()
    
    # 创建并行分诊节点
    parallel_triage_node = ParallelTriageNode(llm, client, tools)
    
    # 准备输入
    user_input = "皮肤红肿，呼吸急促"
    initial_state = {
        "user_input": user_input,
        "triage1_result": "",
        "triage2_result": "", 
        "combined_analysis": ""
    }
    
    # 执行节点
    print("开始并行分析...")
    final_state = await parallel_triage_node(initial_state)
    
    # 输出结果
    print("\n" + "="*50)
    print("最终分析结果:")
    print("="*50)
    print(final_state["combined_analysis"])
    
    return final_state

# 运行主程序
# ============================================================================
# 供 flow.py 调用的适配函数
# ============================================================================

# 全局缓存MCP客户端和工具
_mcp_client = None
_mcp_tools = None
_llm = None

def get_or_create_components():
    """获取或创建MCP客户端和LLM（同步版本）- 改进的事件循环处理"""
    global _mcp_client, _mcp_tools, _llm
    
    if _mcp_client is None or _mcp_tools is None or _llm is None:
        _llm = create_llm()
        
        # 尝试获取当前运行的事件循环
        try:
            loop = asyncio.get_running_loop()
            # 检测到运行中的循环，在新线程中初始化MCP客户端
            print(">>> 检测到运行中的事件循环，将在新线程中初始化MCP客户端...")
            
            import concurrent.futures
            
            def init_mcp_in_thread():
                """在新线程中初始化MCP客户端"""
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(initialize_mcp_client())
                finally:
                    # 清理事件循环
                    try:
                        pending = asyncio.all_tasks(new_loop)
                        for task in pending:
                            task.cancel()
                        new_loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    except Exception:
                        pass
                    finally:
                        new_loop.close()
            
            # 使用线程池执行
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(init_mcp_in_thread)
                try:
                    _mcp_client, _mcp_tools = future.result(timeout=30)
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
            except Exception as e:
                print(f">>> 警告: MCP客户端初始化失败: {e}")
                _mcp_client = None
                _mcp_tools = []
            finally:
                # 清理事件循环
                try:
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception:
                    pass
                finally:
                    loop.close()
                    asyncio.set_event_loop(None)
    
    return _llm, _mcp_client, _mcp_tools

def triage_node(state):
    """
    分诊节点 - 供flow.py调用的适配函数
    
    Args:
        state: 包含messages等字段的状态字典
        
    Returns:
        更新后的状态字典
    """
    from langchain_core.messages import HumanMessage
    import re
    
    try:
        # 获取组件
        llm, client, tools = get_or_create_components()
        
        # 创建并行分诊节点
        parallel_triage = ParallelTriageNode(llm, client, tools)
        
        # 提取用户输入
        user_input = state.get("user_input", "")
        if not user_input and state.get("messages"):
            last_msg = state["messages"][-1]
            user_input = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
        
        # 准备ParallelState
        parallel_state = {
            "user_input": user_input,
            "triage1_result": "",
            "triage2_result": "",
            "combined_analysis": ""
        }
        
        # 执行分诊（同步版本）- 改进的异步处理
        try:
            # 尝试获取当前运行的事件循环
            try:
                loop = asyncio.get_running_loop()
                # 检测到运行中的事件循环，在线程池中执行避免嵌套
                import concurrent.futures
                
                def run_in_new_thread():
                    """在新线程中创建独立的事件循环运行异步代码"""
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(parallel_triage(parallel_state))
                    finally:
                        # 清理事件循环
                        try:
                            # 取消所有未完成的任务
                            pending = asyncio.all_tasks(new_loop)
                            for task in pending:
                                task.cancel()
                            # 等待所有任务取消
                            new_loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                        except Exception as e:
                            print(f">>> 清理事件循环时出错: {e}")
                        finally:
                            new_loop.close()
                
                # 使用线程池执行，避免阻塞主事件循环
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(run_in_new_thread)
                    result_state = future.result(timeout=180)  # 超时设置为180秒
                    
            except RuntimeError:
                # 没有运行中的循环，直接创建新循环执行（例如在命令行直接调用时）
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result_state = loop.run_until_complete(parallel_triage(parallel_state))
                finally:
                    # 清理事件循环
                    try:
                        pending = asyncio.all_tasks(loop)
                        for task in pending:
                            task.cancel()
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    except Exception as e:
                        print(f">>> 清理事件循环时出错: {e}")
                    finally:
                        loop.close()
                        asyncio.set_event_loop(None)  # 重置事件循环
                        
        except concurrent.futures.TimeoutError:
            print(">>> 分诊处理超时")
            raise Exception("分诊处理超时，请稍后重试")
        except Exception as e:
            print(f">>> 执行分诊时出错: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        # 提取问题部分
        triage1_result = result_state.get("triage1_result", "")
        pattern = r'【可能疾病\d+】.*?(?=【可能疾病\d+】|$)'
        matches = re.findall(pattern, triage1_result, re.DOTALL)
        triage_questions = "\n".join(matches) if matches else triage1_result
        
        # ========== 结构化数据保存 ==========
        # 从triage2_result中提取分诊级别和建议科室
        triage2_result = result_state.get("triage2_result", "")
        triage_level = ""
        recommended_department = ""
        triage_basis = ""
        
        # 解析分诊结果
        if triage2_result:
            # 提取分诊级别
            level_match = re.search(r'分诊级别[：:]\s*(.+)', triage2_result)
            if level_match:
                triage_level = level_match.group(1).strip()
            
            # 提取建议科室
            dept_match = re.search(r'建议科室[：:]\s*(.+)', triage2_result)
            if dept_match:
                recommended_department = dept_match.group(1).strip()
            
            # 提取核心依据
            basis_match = re.search(r'核心依据[：:]\s*(.+)', triage2_result)
            if basis_match:
                triage_basis = basis_match.group(1).strip()
        
        # 保存结构化数据（如果有patient_id）
        patient_id = state.get("patient_id")
        if patient_id and triage_level:
            try:
                from patient_model import patient_manager
                patient_manager.update_triage_info(
                    patient_id=patient_id,
                    triage_level=triage_level,
                    recommended_department=recommended_department,
                    triage_basis=triage_basis,
                    triage_questions=triage_questions
                )
                patient_manager.update_patient_info(
                    patient_id=patient_id,
                    initial_symptoms=user_input
                )
            except Exception as e:
                print(f">>> 保存分诊数据失败: {e}")
        
        # 返回更新的状态
        return {
            "messages": [HumanMessage(content=result_state.get("combined_analysis", ""))],
            "triage1_result": result_state.get("triage1_result", ""),
            "triage2_result": result_state.get("triage2_result", ""),
            "combined_analysis": result_state.get("combined_analysis", ""),
            "has_triaged": True,
            "triage_questions": triage_questions
        }
        
    except Exception as e:
        print(f"分诊过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return {
            "messages": [HumanMessage(content=f"分诊过程中出现错误: {str(e)}")]
        }

if __name__ == "__main__":
    result = asyncio.run(main())

 


    
"""
# 在其他文件中这样使用 ParallelTriageNode

from your_module import ParallelTriageNode, ParallelState, initialize_mcp_client, create_llm
from langgraph.graph import StateGraph, END

async def create_medical_workflow():
    "创建医疗工作流图"
    
    # 初始化组件
    llm = create_llm()
    client, tools = await initialize_mcp_client()
    
    # 创建并行分诊节点实例
    parallel_triage = ParallelTriageNode(llm, client, tools)
    
    # 构建工作流图
    workflow = StateGraph(ParallelState)
    
    # 添加并行分诊节点
    workflow.add_node("parallel_triage", parallel_triage)
    
    # 设置工作流
    workflow.set_entry_point("parallel_triage")
    workflow.add_edge("parallel_triage", END)
    
    return workflow.compile()

# 使用工作流
async def use_workflow():
    graph = await create_medical_workflow()
    
    result = await graph.ainvoke({
        "user_input": "患者头痛、恶心",
        "triage1_result": "",
        "triage2_result": "",
        "combined_analysis": ""
    })
    
    return result

"""