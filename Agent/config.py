"""
多智能体系统统一配置文件
包含LLM配置、Neo4j配置、MCP配置等
"""

import os

# ============================================================================
# LLM配置 - 大语言模型配置
# ============================================================================

LLM_CONFIG = {
    # 模型配置
    "model": "qwen2.5:14b",
    "base_url": "https://zjlchat.vip.cpolar.cn/v1",
    "api_key": "EMPTY",
    
    # 默认参数 - 适用于大多数节点
    "temperature": 0.1,  # 控制生成随机性，越低越确定
    "top_p": 0.8,        # 核采样参数，控制生成多样性
}

# 特定节点的LLM配置（覆盖默认配置）
LLM_NODE_CONFIGS = {
    # 医学知识查询节点使用更高的temperature，使回答更自然
    "query_node": {
        "temperature": 0.3,
        "top_p": 0.9,
    },
    
    # 可以为其他节点添加特定配置
    # "triage_node": {
    #     "temperature": 0.1,
    #     "top_p": 0.8,
    # },
}

# ============================================================================
# Neo4j配置 - 图数据库配置
# ============================================================================

NEO4J_CONFIG = {
    "uri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    "user": os.getenv("NEO4J_USER", "neo4j"),
    "password": os.getenv("NEO4J_PASS", "test1234"),
}

# ============================================================================
# MCP配置 - 模型上下文协议配置
# ============================================================================

MCP_CONFIG = {
    "servers": {
        "triage": {
            # 支持环境变量配置，Docker环境使用服务名，本地开发使用localhost
            "url": os.getenv("MCP_TRIAGE_URL", "http://localhost:8000/sse"),
            "headers": {},
            "transport": "sse"
        }
    }
}

# ============================================================================
# 工具函数
# ============================================================================

def get_llm_config(node_name: str = None) -> dict:
    """
    获取LLM配置
    
    Args:
        node_name: 节点名称，如 "query_node"。如果为None，返回默认配置
        
    Returns:
        LLM配置字典
    """
    config = LLM_CONFIG.copy()
    
    # 如果指定了节点名称，应用特定配置
    if node_name and node_name in LLM_NODE_CONFIGS:
        config.update(LLM_NODE_CONFIGS[node_name])
    
    return config

def create_llm(node_name: str = None):
    """
    创建LLM实例
    
    Args:
        node_name: 节点名称，用于获取特定配置
        
    Returns:
        ChatOpenAI实例
    """
    from langchain_openai import ChatOpenAI
    
    config = get_llm_config(node_name)
    
    return ChatOpenAI(
        model=config["model"],
        base_url=config["base_url"],
        api_key=config["api_key"],
        temperature=config["temperature"],
        top_p=config["top_p"]
    )

def get_neo4j_config() -> dict:
    """
    获取Neo4j配置
    
    Returns:
        Neo4j配置字典
    """
    return NEO4J_CONFIG.copy()

def get_mcp_config() -> dict:
    """
    获取MCP配置
    
    Returns:
        MCP配置字典
    """
    return MCP_CONFIG.copy()

# ============================================================================
# 使用示例
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("多智能体系统配置信息")
    print("=" * 60)
    
    print("\n【默认LLM配置】")
    default_config = get_llm_config()
    for key, value in default_config.items():
        print(f"  {key}: {value}")
    
    print("\n【query_node LLM配置】")
    query_config = get_llm_config("query_node")
    for key, value in query_config.items():
        print(f"  {key}: {value}")
    
    print("\n【Neo4j配置】")
    neo4j_config = get_neo4j_config()
    for key, value in neo4j_config.items():
        if key != "password":  # 不显示密码
            print(f"  {key}: {value}")
        else:
            print(f"  {key}: {'*' * len(value)}")
    
    print("\n【MCP配置】")
    mcp_config = get_mcp_config()
    for server_name, server_config in mcp_config["servers"].items():
        print(f"  {server_name}: {server_config['url']}")
    
    print("\n" + "=" * 60)
    print("配置加载成功！")
    print("=" * 60)

