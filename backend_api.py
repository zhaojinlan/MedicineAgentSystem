"""
医疗多智能体系统 - FastAPI 后端服务
提供患者管理和AI对话接口
"""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uuid
import sys
import os
from pathlib import Path
import json
import asyncio
import shutil

# 添加Agent目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'Agent'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'Construct'))

# 导入全局配置
from config import get_path, PATHS

from Agent.patient_model import patient_manager, PatientData
from Agent.flow import graph
from langchain_core.messages import HumanMessage

# 导入知识图谱工作流
try:
    from Construct.knowledge_workflow import KnowledgeWorkflow
except ImportError:
    KnowledgeWorkflow = None
    print("警告：无法导入 KnowledgeWorkflow，知识图谱功能将不可用")

# 导入症状向量化工具
try:
    from Construct.symptom_vectorizer import SymptomVectorizer
except ImportError:
    SymptomVectorizer = None
    print("警告：无法导入 SymptomVectorizer，症状向量化功能将不可用")

# 导入知识图谱RAG向量化工具
try:
    from Construct.knowledge_rag_vectorizer import KnowledgeRAGVectorizer
except ImportError:
    KnowledgeRAGVectorizer = None
    print("警告：无法导入 KnowledgeRAGVectorizer，RAG向量化功能将不可用")

# 导入数据一致性管理器
try:
    from Construct.knowledge_data_manager import get_data_manager
    from config import NEO4J_CONFIG, REDIS_CONFIG
    
    # 使用全局配置而非硬编码
    data_manager = get_data_manager(
        redis_host=REDIS_CONFIG['host'],
        redis_port=REDIS_CONFIG['port'],
        redis_password=REDIS_CONFIG['password'],
        neo4j_uri=NEO4J_CONFIG['uri'],
        neo4j_user=NEO4J_CONFIG['user'],
        neo4j_password=NEO4J_CONFIG['password']
    )
except ImportError as e:
    data_manager = None
    print(f"警告：无法导入数据管理器，数据一致性功能将不可用: {e}")
except Exception as e:
    data_manager = None
    print(f"警告：数据管理器初始化失败: {e}")

# 创建FastAPI应用
app = FastAPI(title="医疗多智能体系统API", version="1.0.0")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该指定具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# 请求/响应模型
# ============================================================================

class CreatePatientRequest(BaseModel):
    """创建患者请求"""
    patient_name: str
    patient_age: int
    patient_gender: Optional[str] = "男"
    initial_symptoms: Optional[str] = None


class UpdatePatientRequest(BaseModel):
    """更新患者请求"""
    patient_name: Optional[str] = None
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    initial_symptoms: Optional[str] = None
    patient_history: Optional[str] = None
    test_results: Optional[str] = None


class ChatRequest(BaseModel):
    """对话请求"""
    patient_id: str
    message: str


class ChatResponse(BaseModel):
    """对话响应"""
    response: str
    patient_data: Dict[str, Any]


class SubmitTestResultsRequest(BaseModel):
    """提交检查结果请求"""
    submitted_tests: List[Dict[str, Any]]  # 每个检查包含test_name、test_description、result


class ExtractEntitiesRequest(BaseModel):
    """实体抽取请求"""
    document_name: str


class BuildGraphRequest(BaseModel):
    """构建知识图谱请求"""
    document_name: str
    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]


# ============================================================================
# 患者管理接口
# ============================================================================

@app.get("/")
async def root():
    """根路径"""
    return {"message": "医疗多智能体系统API", "version": "1.0.0"}


@app.get("/api/patients", response_model=List[Dict[str, Any]])
async def get_all_patients():
    """获取所有患者列表"""
    try:
        patient_dir = Path("patient_data")
        if not patient_dir.exists():
            return []
        
        patients = []
        for file_path in patient_dir.glob("*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    patient_data = json.load(f)
                    # 只返回基本信息用于列表显示
                    patients.append({
                        "patient_id": patient_data.get("patient_id"),
                        "patient_name": patient_data.get("patient_name", "未命名患者"),
                        "patient_age": patient_data.get("patient_age"),
                        "patient_gender": patient_data.get("patient_gender", "男"),
                        "created_at": patient_data.get("created_at"),
                        "updated_at": patient_data.get("updated_at"),
                        "initial_symptoms": patient_data.get("initial_symptoms", "")[:50] + "..." if patient_data.get("initial_symptoms") else ""
                    })
            except Exception as e:
                print(f"读取患者文件失败 {file_path}: {e}")
                continue
        
        # 按更新时间降序排列
        patients.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return patients
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取患者列表失败: {str(e)}")


@app.get("/api/patients/{patient_id}", response_model=Dict[str, Any])
async def get_patient(patient_id: str):
    """获取单个患者的完整信息"""
    try:
        patient_data = patient_manager.load_patient_data(patient_id)
        if patient_data is None:
            raise HTTPException(status_code=404, detail="患者不存在")
        
        return patient_data.model_dump(exclude_none=False)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取患者信息失败: {str(e)}")


@app.post("/api/patients", response_model=Dict[str, Any])
async def create_patient(request: CreatePatientRequest):
    """创建新患者"""
    try:
        # 生成新的患者ID（同时作为thread_id使用）
        patient_id = str(uuid.uuid4())
        
        # 创建患者数据
        patient_data = PatientData(
            patient_id=patient_id,
            patient_name=request.patient_name,
            patient_age=request.patient_age,
            patient_gender=request.patient_gender,
            initial_symptoms=request.initial_symptoms
        )
        
        # 保存患者数据
        patient_manager.save_patient_data(patient_data)
        
        result_dict = patient_data.model_dump(exclude_none=False)
        print(f">>> 新建患者: {request.patient_name}, ID: {patient_id}, 性别: {request.patient_gender}")
        
        return result_dict
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建患者失败: {str(e)}")


@app.put("/api/patients/{patient_id}", response_model=Dict[str, Any])
async def update_patient(patient_id: str, request: UpdatePatientRequest):
    """更新患者信息"""
    try:
        patient_data = patient_manager.load_patient_data(patient_id)
        if patient_data is None:
            raise HTTPException(status_code=404, detail="患者不存在")
        
        # 更新字段
        update_fields = request.model_dump(exclude_none=True)
        for key, value in update_fields.items():
            setattr(patient_data, key, value)
        
        # 保存更新
        patient_manager.save_patient_data(patient_data)
        
        return patient_data.model_dump(exclude_none=False)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新患者失败: {str(e)}")


@app.delete("/api/patients/{patient_id}")
async def delete_patient(patient_id: str):
    """删除患者"""
    try:
        file_path = patient_manager.get_patient_file_path(patient_id)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="患者不存在")
        
        file_path.unlink()
        return {"message": "患者已删除", "patient_id": patient_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除患者失败: {str(e)}")


@app.post("/api/patients/{patient_id}/submit-tests", response_model=Dict[str, Any])
async def submit_test_results(patient_id: str, request: SubmitTestResultsRequest):
    """提交检查结果"""
    try:
        # 验证患者是否存在
        patient_data = patient_manager.load_patient_data(patient_id)
        if patient_data is None:
            raise HTTPException(status_code=404, detail="患者不存在")
        
        # 验证是否有诊断信息
        if patient_data.diagnosis_info is None:
            raise HTTPException(status_code=400, detail="患者尚未进行诊断分析，无法提交检查结果")
        
        # 验证提交的检查数据完整性
        for test in request.submitted_tests:
            if 'test_name' not in test or 'result' not in test:
                raise HTTPException(
                    status_code=400, 
                    detail=f"检查数据不完整，缺少必要字段: {test}"
                )
            if not test['result'] or not test['result'].strip():
                raise HTTPException(
                    status_code=400, 
                    detail=f"检查项目 {test['test_name']} 的结果不能为空"
                )
        
        # 提交检查结果
        updated_patient = patient_manager.submit_test_results(
            patient_id=patient_id,
            submitted_tests=request.submitted_tests
        )
        
        print(f">>> 成功提交 {len(request.submitted_tests)} 项检查结果")
        return updated_patient.model_dump(exclude_none=False)
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"提交检查结果失败: {str(e)}")


# ============================================================================
# AI对话接口
# ============================================================================

@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_ai(request: ChatRequest):
    """与AI进行对话（同步版本，用于兼容）"""
    try:
        # 验证患者是否存在
        patient_data = patient_manager.load_patient_data(request.patient_id)
        if patient_data is None:
            raise HTTPException(status_code=404, detail="患者不存在")
        
        # 使用patient_id作为thread_id
        config = {
            "configurable": {
                "thread_id": request.patient_id  # 直接使用patient_id作为thread_id
            }
        }
        
        # 准备输入
        input_data = {
            "messages": [HumanMessage(content=request.message)],
            "patient_id": request.patient_id
        }
        
        # 如果是首次对话，初始化所有字段
        if not patient_data.conversation_history:
            input_data.update({
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
            print(f">>> 首次对话，初始化状态，thread_id: {request.patient_id}")
        
        # 执行对话 - 在线程池中运行避免阻塞事件循环
        from concurrent.futures import ThreadPoolExecutor
        loop = asyncio.get_event_loop()
        
        def run_graph_sync():
            """在线程池中运行同步的graph.invoke()"""
            return graph.invoke(input_data, config)
        
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = loop.run_in_executor(executor, run_graph_sync)
            result_state = await future
        
        # 提取AI回复
        messages = result_state.get("messages", [])
        if messages:
            last_message = messages[-1]
            full_content = last_message.content if hasattr(last_message, 'content') else str(last_message)
            
            # 提取所有 <结论> 标签内容，移除 <思考> 标签
            import re
            conclusion_matches = re.findall(r'<结论>(.*?)</结论>', full_content, re.DOTALL)
            if conclusion_matches:
                # 合并所有结论
                ai_response = '\n\n'.join([c.strip() for c in conclusion_matches])
            else:
                ai_response = re.sub(r'<思考>.*?</思考>', '', full_content, flags=re.DOTALL)
                ai_response = re.sub(r'<think>.*?</think>', '', ai_response, flags=re.DOTALL)
                ai_response = ai_response.strip() or full_content
        else:
            ai_response = "系统无回复"
        
        # 保存对话历史
        patient_manager.add_conversation(request.patient_id, "user", request.message)
        patient_manager.add_conversation(request.patient_id, "assistant", ai_response)
        
        # 重新加载患者数据
        updated_patient_data = patient_manager.load_patient_data(request.patient_id)
        
        return ChatResponse(
            response=ai_response,
            patient_data=updated_patient_data.model_dump(exclude_none=False)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"对话处理失败: {str(e)}")


@app.post("/api/chat/stream")
async def chat_with_ai_stream(request: ChatRequest):
    """与AI进行对话（流式输出版本，支持思考过程展示）"""
    
    async def event_generator():
        try:
            # 验证患者是否存在
            patient_data = patient_manager.load_patient_data(request.patient_id)
            if patient_data is None:
                yield f"data: {json.dumps({'error': '患者不存在'}, ensure_ascii=False)}\n\n"
                return
            
            # 发送开始事件
            yield f"data: {json.dumps({'type': 'start', 'message': '开始处理...'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)  # 确保消息被发送
            
            # 使用patient_id作为thread_id
            config = {
                "configurable": {
                    "thread_id": request.patient_id
                }
            }
            
            # 准备输入
            input_data = {
                "messages": [HumanMessage(content=request.message)],
                "patient_id": request.patient_id
            }
            
            # 如果是首次对话，初始化所有字段
            if not patient_data.conversation_history:
                input_data.update({
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
            
            # 使用stream方法执行对话，获取中间步骤和思考过程
            thinking_steps = []
            thinking_content = ""
            current_node = None
            step_counter = 0
            
            # 发送思考过程开始
            yield f"data: {json.dumps({'type': 'thinking_start', 'message': '正在分析...'}, ensure_ascii=False)}\n\n"
            
            try:
                # 使用stream获取执行过程 - 在线程池中运行以避免阻塞事件循环
                import re
                from concurrent.futures import ThreadPoolExecutor
                import threading
                
                # 在单独的线程中运行同步的graph操作
                def run_graph_stream():
                    """在新线程中运行graph.stream()"""
                    chunks = []
                    for chunk in graph.stream(input_data, config):
                        chunks.append(chunk)
                    return chunks
                
                # 使用线程池执行同步操作
                loop = asyncio.get_event_loop()
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = loop.run_in_executor(executor, run_graph_stream)
                    chunks = await future
                
                # 处理收集到的chunks
                for chunk in chunks:
                    # chunk的格式: {node_name: state_dict}
                    for node_name, state_data in chunk.items():
                        if node_name != "__end__":
                            # 节点显示名称
                            node_display_names = {
                                "router": "🔀 路由分析",
                                "triage_node": "🏥 分诊评估",
                                "recommend_node": "💊 诊断建议",
                                "agen_node": "👨‍⚕️ 专家会诊",
                                "query_node": "📚 知识查询"
                            }
                            display_name = node_display_names.get(node_name, f"⚙️ {node_name}")
                            
                            # 提取该节点的所有思考内容（处理多个智能体的情况）
                            all_thinking = []
                            
                            # 方法1：从 messages 中提取
                            messages = state_data.get("messages", [])
                            if messages:
                                for msg in messages:
                                    msg_content = msg.content if hasattr(msg, 'content') else str(msg)
                                    # 提取思考过程
                                    think_matches = re.findall(r'<思考>(.*?)</思考>', msg_content, re.DOTALL)
                                    if not think_matches:
                                        think_matches = re.findall(r'<think>(.*?)</think>', msg_content, re.DOTALL)
                                    
                                    if think_matches:
                                        all_thinking.extend(think_matches)
                            
                            # 方法2：从 triage_node 的特殊字段提取
                            if node_name == "triage_node":
                                # triage1_result 和 triage2_result
                                triage1 = state_data.get("triage1_result", "")
                                triage2 = state_data.get("triage2_result", "")
                                
                                for result in [triage1, triage2]:
                                    if result:
                                        think_matches = re.findall(r'<思考>(.*?)</思考>', result, re.DOTALL)
                                        if think_matches:
                                            all_thinking.extend(think_matches)
                            
                            # 合并所有思考内容
                            if all_thinking:
                                step_thinking = "\n\n---\n\n".join([t.strip() for t in all_thinking])
                            else:
                                step_thinking = ""
                            
                            step_counter += 1
                            thinking_steps.append({
                                "node": node_name,
                                "display_name": display_name,
                                "content": step_thinking,
                                "timestamp": str(loop.time())
                            })
                            
                            # 流式输出思考过程（分段发送）
                            if step_thinking:
                                # 先发送节点信息
                                yield f"data: {json.dumps({'type': 'thinking_step_start', 'node': node_name, 'display_name': display_name}, ensure_ascii=False)}\n\n"
                                await asyncio.sleep(0.05)
                                
                                # 分段发送思考内容
                                chunk_size = 50
                                for i in range(0, len(step_thinking), chunk_size):
                                    chunk_text = step_thinking[i:i+chunk_size]
                                    yield f"data: {json.dumps({'type': 'thinking_chunk', 'node': node_name, 'content': chunk_text}, ensure_ascii=False)}\n\n"
                                    await asyncio.sleep(0.02)
                                
                                # 发送节点完成
                                yield f"data: {json.dumps({'type': 'thinking_step_end', 'node': node_name}, ensure_ascii=False)}\n\n"
                            else:
                                # 如果没有思考内容，直接发送节点信息
                                yield f"data: {json.dumps({'type': 'thinking_step', 'node': node_name, 'display_name': display_name, 'content': ''}, ensure_ascii=False)}\n\n"
                            
                            await asyncio.sleep(0.1)
                
                # 执行完整的invoke获取最终结果 - 同样在线程池中运行
                def run_graph_invoke():
                    """在新线程中运行graph.invoke()"""
                    return graph.invoke(input_data, config)
                
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = loop.run_in_executor(executor, run_graph_invoke)
                    result_state = await future
                
                # 提取AI回复
                messages = result_state.get("messages", [])
                if messages:
                    last_message = messages[-1]
                    full_content = last_message.content if hasattr(last_message, 'content') else str(last_message)
                    
                    # 提取并清理回复内容
                    import re
                    
                    # 1. 提取所有 <结论> 标签内容
                    conclusion_matches = re.findall(r'<结论>(.*?)</结论>', full_content, re.DOTALL)
                    if conclusion_matches:
                        # 合并所有结论（用分隔线分开）
                        ai_response = '\n\n'.join([c.strip() for c in conclusion_matches])
                    else:
                        # 2. 移除所有思考标签
                        ai_response = re.sub(r'<思考>.*?</思考>', '', full_content, flags=re.DOTALL)
                        ai_response = re.sub(r'<think>.*?</think>', '', ai_response, flags=re.DOTALL)
                        ai_response = ai_response.strip()
                        
                        if not ai_response:
                            ai_response = full_content  # 如果没有标签，使用完整内容
                else:
                    ai_response = "系统无回复"
                
                # 发送思考过程结束
                yield f"data: {json.dumps({'type': 'thinking_end', 'steps': thinking_steps}, ensure_ascii=False)}\n\n"
                
                # 流式发送AI回复（逐字输出）
                yield f"data: {json.dumps({'type': 'response_start'}, ensure_ascii=False)}\n\n"
                
                # 将回复分段发送（更小的块，更流畅的效果）
                chunk_size = 5  # 每次发送5个字符
                for i in range(0, len(ai_response), chunk_size):
                    chunk_text = ai_response[i:i+chunk_size]
                    yield f"data: {json.dumps({'type': 'response_chunk', 'content': chunk_text}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.03)  # 打字效果
                
                yield f"data: {json.dumps({'type': 'response_end'}, ensure_ascii=False)}\n\n"
                
                # 保存对话历史
                patient_manager.add_conversation(request.patient_id, "user", request.message)
                patient_manager.add_conversation(request.patient_id, "assistant", ai_response)
                
                # 发送完成事件
                yield f"data: {json.dumps({'type': 'done', 'response': ai_response}, ensure_ascii=False)}\n\n"
                
            except Exception as e:
                print(f">>> 流式处理错误: {e}")
                import traceback
                traceback.print_exc()
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        
        except Exception as e:
            print(f">>> 事件生成器错误: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ============================================================================
# WebSocket支持（可选，用于实时对话）
# ============================================================================

@app.websocket("/ws/chat/{patient_id}")
async def websocket_chat(websocket: WebSocket, patient_id: str):
    """WebSocket实时对话"""
    await websocket.accept()
    
    try:
        # 验证患者是否存在
        patient_data = patient_manager.load_patient_data(patient_id)
        if patient_data is None:
            await websocket.send_json({"error": "患者不存在"})
            await websocket.close()
            return
        
        while True:
            # 接收消息
            data = await websocket.receive_text()
            message_data = json.loads(data)
            user_message = message_data.get("message", "")
            
            if not user_message:
                continue
            
            # 处理对话（与HTTP接口相同的逻辑）
            config = {
                "configurable": {
                    "thread_id": patient_id
                }
            }
            
            input_data = {
                "messages": [HumanMessage(content=user_message)],
                "patient_id": patient_id
            }
            
            # 执行对话 - 在线程池中运行避免阻塞事件循环
            from concurrent.futures import ThreadPoolExecutor
            loop = asyncio.get_event_loop()
            
            def run_graph_sync():
                """在线程池中运行同步的graph.invoke()"""
                return graph.invoke(input_data, config)
            
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = loop.run_in_executor(executor, run_graph_sync)
                result_state = await future
            
            # 提取AI回复
            messages = result_state.get("messages", [])
            if messages:
                last_message = messages[-1]
                ai_response = last_message.content if hasattr(last_message, 'content') else str(last_message)
            else:
                ai_response = "系统无回复"
            
            # 保存对话历史
            patient_manager.add_conversation(patient_id, "user", user_message)
            patient_manager.add_conversation(patient_id, "assistant", ai_response)
            
            # 发送回复
            await websocket.send_json({
                "response": ai_response,
                "timestamp": patient_manager.load_patient_data(patient_id).updated_at
            })
            
    except WebSocketDisconnect:
        print(f"WebSocket断开连接: {patient_id}")
    except Exception as e:
        print(f"WebSocket错误: {e}")
        await websocket.send_json({"error": str(e)})
        await websocket.close()


# ============================================================================
# 知识图谱构建接口
# ============================================================================

@app.post("/api/knowledge/upload")
async def upload_knowledge_document(file: UploadFile = File(...)):
    """
    上传医学文献并进行初步处理
    步骤1：上传PDF -> 转换为HTML -> 清洗HTML
    """
    try:
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="只支持PDF文件")
        
        # 检查KnowledgeWorkflow是否可用
        if KnowledgeWorkflow is None:
            raise HTTPException(status_code=500, detail="知识图谱工作流未初始化")
        
        # 创建工作流实例
        workflow = KnowledgeWorkflow()
        
        # 获取文件名（不含扩展名）
        doc_name = Path(file.filename).stem
        
        # 创建临时文件保存上传的PDF
        temp_dir = Path("temp_uploads")
        temp_dir.mkdir(exist_ok=True)
        temp_pdf_path = temp_dir / file.filename
        
        # 保存上传的文件
        with open(temp_pdf_path, 'wb') as f:
            content = await file.read()
            f.write(content)
        
        print(f">>> 接收到文件: {file.filename}, 大小: {len(content)} bytes")
        
        # 创建工作目录
        work_dir = get_path("knowledges_dir") / doc_name
        work_dir.mkdir(parents=True, exist_ok=True)
        
        # 步骤1: 使用docling扫描文献
        html_raw = workflow._step1_docling_scan(temp_pdf_path, work_dir)
        if not html_raw:
            raise HTTPException(status_code=500, detail="PDF解析失败")
        
        # 步骤2: 清洗HTML
        html_cleaned = workflow._step2_clean_html(html_raw, work_dir)
        if not html_cleaned:
            raise HTTPException(status_code=500, detail="HTML清洗失败")
        
        # 步骤3: 转换为markdown（用于后续的实体抽取）
        markdown_content = workflow._step3_convert_to_markdown(html_cleaned, work_dir)
        if not markdown_content:
            raise HTTPException(status_code=500, detail="Markdown转换失败")
        
        # 删除临时文件
        temp_pdf_path.unlink()
        
        print(f">>> 文档处理完成: {doc_name}")
        
        return {
            "message": "文件上传成功",
            "document_name": doc_name,
            "html_raw": html_raw,
            "html_cleaned": html_cleaned,
            "work_dir": str(work_dir)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"文件处理失败: {str(e)}")


@app.post("/api/knowledge/extract")
async def extract_entities(request: ExtractEntitiesRequest):
    """
    实体抽取
    步骤4：从markdown中抽取实体和关系
    """
    try:
        # 检查KnowledgeWorkflow是否可用
        if KnowledgeWorkflow is None:
            raise HTTPException(status_code=500, detail="知识图谱工作流未初始化")
        
        # 工作目录
        work_dir = get_path("knowledges_dir") / request.document_name
        if not work_dir.exists():
            raise HTTPException(status_code=404, detail="文档工作目录不存在")
        
        # 读取markdown文件
        markdown_path = work_dir / "03_document.md"
        if not markdown_path.exists():
            raise HTTPException(status_code=404, detail="Markdown文件不存在")
        
        with open(markdown_path, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
        
        # 创建工作流实例
        workflow = KnowledgeWorkflow()
        
        # 步骤4: 实体抽取
        print(f">>> 开始实体抽取: {request.document_name}")
        knowledge_graph = workflow._step4_entity_extraction(markdown_content, work_dir)
        
        if not knowledge_graph:
            raise HTTPException(status_code=500, detail="实体抽取失败")
        
        print(f">>> 实体抽取完成: {len(knowledge_graph['entities'])} 个实体, {len(knowledge_graph['relationships'])} 个关系")
        
        return {
            "message": "实体抽取完成",
            "entities": knowledge_graph['entities'],
            "relationships": knowledge_graph['relationships'],
            "metadata": knowledge_graph.get('metadata', {})
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"实体抽取失败: {str(e)}")


@app.post("/api/knowledge/build")
async def build_knowledge_graph(request: BuildGraphRequest):
    """
    构建知识图谱
    步骤5：将编辑后的实体和关系导入Neo4j
    """
    try:
        # 检查KnowledgeWorkflow是否可用
        if KnowledgeWorkflow is None:
            raise HTTPException(status_code=500, detail="知识图谱工作流未初始化")
        
        # 工作目录
        work_dir = get_path("knowledges_dir") / request.document_name
        if not work_dir.exists():
            raise HTTPException(status_code=404, detail="文档工作目录不存在")
        
        # 更新知识图谱JSON（保存用户编辑后的版本）
        from datetime import datetime
        
        entity_type_counts = {}
        for entity in request.entities:
            entity_type = entity['entity_type']
            entity_type_counts[entity_type] = entity_type_counts.get(entity_type, 0) + 1
        
        knowledge_graph = {
            "entities": request.entities,
            "relationships": request.relationships,
            "metadata": {
                "extraction_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "entity_count": len(request.entities),
                "relationship_count": len(request.relationships),
                "entity_type_counts": entity_type_counts,
                "edited": True
            }
        }
        
        # 保存更新后的JSON
        json_path = work_dir / "04_knowledge_graph.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(knowledge_graph, f, ensure_ascii=False, indent=2)
        
        # 创建工作流实例
        workflow = KnowledgeWorkflow()
        
        # 步骤5: 导入Neo4j
        print(f">>> 开始构建知识图谱: {request.document_name}")
        success = workflow._step5_import_to_neo4j(knowledge_graph, work_dir)
        
        if not success:
            print(">>> 警告: Neo4j导入失败，但JSON已保存")
        
        # 步骤6: 对Symptom节点进行向量化（仅在Neo4j导入成功时）
        symptom_vectorize_success = False
        if success and SymptomVectorizer is not None:
            try:
                print(f">>> 开始对 {request.document_name} 的Symptom节点进行向量化...")
                
                # 从全局配置获取参数
                from config import NEO4J_CONFIG
                
                # 创建向量化器实例
                vectorizer = SymptomVectorizer(
                    uri=NEO4J_CONFIG["uri"],
                    user=NEO4J_CONFIG["user"],
                    password=NEO4J_CONFIG["password"],
                    model_path=str(get_path("m3e_model"))
                )
                
                # 为当前文档创建唯一的索引名称
                doc_name_safe = request.document_name.replace(' ', '_').replace('-', '_')
                index_name = f"symptom_vectors_{doc_name_safe}"
                
                # 创建症状向量索引（只处理当前文档相关的症状节点）
                vector_store = vectorizer.create_enhanced_symptom_vectors(
                    index_name=index_name,
                    document_name=request.document_name
                )
                
                if vector_store:
                    symptom_vectorize_success = True
                    print(f">>> Symptom节点向量化完成，索引名: {index_name}")
                else:
                    print(f">>> Symptom节点向量化失败")
                    
            except Exception as e:
                print(f">>> Symptom节点向量化出错: {e}")
                import traceback
                traceback.print_exc()
        
        # 步骤7: 使用Redis进行RAG向量化（知识图谱文档和实体）
        rag_vectorize_success = False
        rag_results = {}
        if KnowledgeRAGVectorizer is not None:
            try:
                print(f">>> 开始对 {request.document_name} 进行RAG向量化...")
                
                # 创建RAG向量化器实例
                rag_vectorizer = KnowledgeRAGVectorizer(
                    host='localhost',
                    port=6379,
                    password=None
                )
                
                # 执行向量化（只向量化markdown文档，实体已在Neo4j中）
                rag_results = rag_vectorizer.vectorize_knowledge_document(
                    document_name=request.document_name,
                    vectorize_markdown=True,   # 向量化markdown文档用于语义检索
                    vectorize_entities=False   # 实体在Neo4j中，无需重复向量化
                )
                
                if rag_results.get('markdown_vectorized') or rag_results.get('entities_vectorized'):
                    rag_vectorize_success = True
                    print(f">>> RAG向量化完成")
                    print(f"    - Markdown文档: {rag_results.get('markdown_chunks', 0)} 个文本块")
                    print(f"    - 知识图谱实体: {rag_results.get('entity_count', 0)} 个实体")
                else:
                    print(f">>> RAG向量化失败")
                    
            except Exception as e:
                print(f">>> RAG向量化出错: {e}")
                import traceback
                traceback.print_exc()
        
        print(f">>> 知识图谱构建完成: {request.document_name}")
        
        # 步骤8: 注册到数据管理器
        if data_manager is not None:
            try:
                # 收集所有Redis索引
                redis_indices = []
                if rag_vectorize_success and rag_results.get('markdown_vectorized'):
                    doc_name_safe = request.document_name.replace(' ', '_').replace('-', '_')
                    redis_indices.append(f"kg_{doc_name_safe}")
                
                if symptom_vectorize_success:
                    doc_name_safe = request.document_name.replace(' ', '_').replace('-', '_')
                    redis_indices.append(f"symptom_vectors_{doc_name_safe}")
                
                # 注册文档
                data_manager.register_document(
                    document_name=request.document_name,
                    redis_indices=redis_indices,
                    neo4j_labels=None,  # 自动检测
                    entity_count=len(request.entities),
                    relationship_count=len(request.relationships)
                )
                print(f">>> 已注册到数据管理器")
                
            except Exception as e:
                print(f">>> 注册到数据管理器失败: {e}")
        
        return {
            "message": "知识图谱构建完成" + 
                      (" (含症状向量化)" if symptom_vectorize_success else "") + 
                      (" (含RAG向量化)" if rag_vectorize_success else ""),
            "neo4j_imported": success,
            "symptom_vectorized": symptom_vectorize_success,
            "rag_vectorized": rag_vectorize_success,
            "rag_results": rag_results,
            "entity_count": len(request.entities),
            "relationship_count": len(request.relationships)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"知识图谱构建失败: {str(e)}")


@app.get("/api/knowledge/export/{document_name}")
async def export_knowledge_graph(document_name: str):
    """导出知识图谱JSON文件"""
    try:
        work_dir = get_path("knowledges_dir") / document_name
        json_path = work_dir / "04_knowledge_graph.json"
        
        if not json_path.exists():
            raise HTTPException(status_code=404, detail="知识图谱文件不存在")
        
        return FileResponse(
            path=json_path,
            filename=f"{document_name}_knowledge_graph.json",
            media_type="application/json"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@app.get("/api/knowledge/list")
async def list_knowledge_documents():
    """列出所有已处理的文档"""
    try:
        knowledges_dir = get_path("knowledges_dir")
        if not knowledges_dir.exists():
            return {"documents": []}
        
        documents = []
        for dir_path in knowledges_dir.iterdir():
            if dir_path.is_dir():
                # 检查是否有知识图谱JSON
                json_path = dir_path / "04_knowledge_graph.json"
                has_graph = json_path.exists()
                
                # 读取metadata
                metadata = {}
                if has_graph:
                    try:
                        with open(json_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            metadata = data.get('metadata', {})
                    except:
                        pass
                
                documents.append({
                    "name": dir_path.name,
                    "path": str(dir_path),
                    "has_graph": has_graph,
                    "metadata": metadata
                })
        
        return {"documents": documents}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文档列表失败: {str(e)}")


@app.get("/api/knowledge/load/{document_name}")
async def load_knowledge_document(document_name: str):
    """加载已存在文档的详细信息"""
    try:
        work_dir = get_path("knowledges_dir") / document_name
        if not work_dir.exists():
            raise HTTPException(status_code=404, detail="文档不存在")
        
        # 读取HTML文件
        raw_html_path = work_dir / "01_raw.html"
        cleaned_html_path = work_dir / "02_cleaned.html"
        json_path = work_dir / "04_knowledge_graph.json"
        
        html_raw = ""
        html_cleaned = ""
        entities = []
        relationships = []
        
        if raw_html_path.exists():
            with open(raw_html_path, 'r', encoding='utf-8') as f:
                html_raw = f.read()
        
        if cleaned_html_path.exists():
            with open(cleaned_html_path, 'r', encoding='utf-8') as f:
                html_cleaned = f.read()
        
        has_knowledge_graph = False
        if json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                entities = data.get('entities', [])
                relationships = data.get('relationships', [])
                has_knowledge_graph = True
        
        return {
            "document_name": document_name,
            "html_raw": html_raw,
            "html_cleaned": html_cleaned,
            "entities": entities,
            "relationships": relationships,
            "has_knowledge_graph": has_knowledge_graph
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载文档失败: {str(e)}")


@app.delete("/api/knowledge/delete/{document_name}")
async def delete_knowledge_document(
    document_name: str,
    delete_files: bool = True,
    delete_redis: bool = True,
    delete_neo4j: bool = True
):
    """
    删除知识文档及其所有相关资源
    
    Args:
        document_name: 文档名称
        delete_files: 是否删除文件夹（默认true）
        delete_redis: 是否删除Redis索引（默认true）
        delete_neo4j: 是否删除Neo4j节点（默认true）
    """
    try:
        if data_manager is None:
            raise HTTPException(status_code=500, detail="数据管理器未初始化")
        
        print(f">>> 收到删除请求: {document_name}")
        print(f"    - 删除文件: {delete_files}")
        print(f"    - 删除Redis: {delete_redis}")
        print(f"    - 删除Neo4j: {delete_neo4j}")
        
        # 执行删除
        result = data_manager.delete_document(
            document_name=document_name,
            delete_files=delete_files,
            delete_redis=delete_redis,
            delete_neo4j=delete_neo4j,
            dry_run=False
        )
        
        if result['errors']:
            return {
                "success": False,
                "message": f"删除过程中遇到 {len(result['errors'])} 个错误",
                "result": result
            }
        else:
            return {
                "success": True,
                "message": "文档删除成功",
                "result": result
            }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"删除文档失败: {str(e)}")


@app.post("/api/knowledge/sync-metadata")
async def sync_metadata():
    """同步元数据（扫描所有文档并更新元数据）"""
    try:
        if data_manager is None:
            raise HTTPException(status_code=500, detail="数据管理器未初始化")
        
        data_manager.sync_metadata()
        stats = data_manager.get_storage_stats()
        
        return {
            "success": True,
            "message": "元数据同步完成",
            "stats": stats
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步元数据失败: {str(e)}")


@app.get("/api/knowledge/stats")
async def get_storage_stats():
    """获取存储统计信息"""
    try:
        if data_manager is None:
            raise HTTPException(status_code=500, detail="数据管理器未初始化")
        
        stats = data_manager.get_storage_stats()
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@app.post("/api/knowledge/cleanup-orphaned")
async def cleanup_orphaned_resources(dry_run: bool = True):
    """
    清理孤立资源
    
    Args:
        dry_run: 是否为预演模式（默认true，只检测不删除）
    """
    try:
        if data_manager is None:
            raise HTTPException(status_code=500, detail="数据管理器未初始化")
        
        print(f">>> 开始清理孤立资源（{'预演' if dry_run else '实际删除'}）...")
        
        result = data_manager.cleanup_orphaned_resources(dry_run=dry_run)
        
        message = "孤立资源检测完成" if dry_run else "孤立资源清理完成"
        
        return {
            "success": True,
            "message": message,
            "result": result
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"清理孤立资源失败: {str(e)}")


# ============================================================================
# 启动服务
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    from pathlib import Path
    
    # 获取项目根目录（避免硬编码路径）
    project_root = str(Path(__file__).parent.resolve())
    
    # 使用8012端口，避免与MCP服务器(8000)和其他服务冲突
    # 启用热重载：代码修改后自动重启，无需手动重启
    uvicorn.run(
        "backend_api:app",  # 使用字符串形式以支持热重载
        host="0.0.0.0",
        port=8012,
        reload=True,  # 🔥 启用热重载
        reload_dirs=[project_root],  # 监控整个项目目录
        reload_includes=["*.py"],  # 监控Python文件
        log_level="info"  # 日志级别
    )

