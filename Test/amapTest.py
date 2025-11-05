import asyncio
import json
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

def format_route_info(route_data):
    """格式化路线信息，使其更易读"""
    try:
        data = json.loads(route_data) if isinstance(route_data, str) else route_data
        
        if 'paths' in data and len(data['paths']) > 0:
            path = data['paths'][0]
            total_distance_km = int(path['distance']) / 1000  # 转换为公里
            total_duration_hours = int(path['duration']) / 3600  # 转换为小时
            
            # 提取主要高速公路
            highways = set()
            for step in path['steps']:
                road = step.get('road', '')
                if '高速' in road or 'G' in road or road.startswith('S'):
                    highways.add(road)
            
            print("\n" + "="*60)
            print("🚗 路线规划结果")
            print("="*60)
            print(f"📍 起点: 北京")
            print(f"🎯 终点: 上海")
            print(f"📏 总距离: {total_distance_km:.1f} 公里")
            print(f"⏱️  预计时间: {total_duration_hours:.1f} 小时")
            print(f"🛣️  主要高速: {', '.join(highways)}")
            print("="*60)
            
            # 显示关键路径点
            print("\n🗺️  关键路径:")
            key_steps = [step for step in path['steps'] if any(keyword in step.get('road', '') 
                          for keyword in ['高速', '枢纽', '立交', '隧道'])]
            
            for i, step in enumerate(key_steps[:10]):  # 只显示前10个关键步骤
                instruction = step.get('instruction', '')[:50] + "..." if len(step.get('instruction', '')) > 50 else step.get('instruction', '')
                print(f"  {i+1}. {instruction}")
            
            if len(key_steps) > 10:
                print(f"  ... 还有 {len(key_steps) - 10} 个步骤")
                
    except Exception as e:
        print(f"格式化路线信息时出错: {e}")

async def main():   
    """主函数：演示如何使用MCP客户端进行路线规划"""
    
    # 初始化 LLM
    llm = ChatOpenAI(
        model="qwen2.5:14b",
        base_url="https://zjlchat.vip.cpolar.cn/v1",
        api_key="EMPTY",
        temperature=0.1,
        top_p=0.8,
        max_tokens=2000
    )
    
    try:
        # 初始化 MCP 客户端
        client = MultiServerMCPClient({
            "amap-maps": {
                "url": "https://dashscope.aliyuncs.com/api/v1/mcps/amap-maps/sse",
                "headers": {
                    "Authorization": "Bearer sk-e7b047109ea64152b127e608b7daf85e"
                },
                "transport": "sse"
            }
        })
        
        # 异步获取工具
        tools = await client.get_tools()
        print(f"✅ 成功加载 {len(tools)} 个工具")
        
        # 打印可用工具名称以便调试
        tool_names = [tool.name for tool in tools]
        print("🛠️  可用工具:", tool_names)
        
        # 创建智能体
        agent = create_react_agent(
            model=llm,
            tools=tools,
        )
        
        # 调用智能体
        print("开始路线规划查询...")
        response = await agent.ainvoke({
            "messages": [
                {"role": "user", "content": "请帮我规划从北京到上海的自驾路线，需要包含距离、时间和主要途经高速，用中文"}
            ]
        })
        
        # 查找工具返回的路线数据
        for message in response['messages']:
            if hasattr(message, 'type') and message.type == 'tool':
                print("\n📊 原始工具返回数据:")
                format_route_info(message.content)
                break
        
        # 输出AI的总结
        print("\n🤖 AI总结:")
        for message in reversed(response['messages']):
            if hasattr(message, 'content') and message.content and len(message.content.strip()) > 0:
                print(message.content)
                break
                
    except Exception as e:
        print(f"❌ 执行过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

# 运行主程序
if __name__ == "__main__":
    asyncio.run(main())