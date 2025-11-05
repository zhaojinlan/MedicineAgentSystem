"""
项目全局配置管理
使用相对路径和环境变量，避免硬编码绝对路径
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件（如果存在）
load_dotenv()

# ============================================================================
# 项目路径配置
# ============================================================================

# 项目根目录（自动获取）
PROJECT_ROOT = Path(__file__).parent.resolve()

# 核心目录
PATHS = {
    # 知识库存储目录
    "knowledges_dir": PROJECT_ROOT / "Knowledges",
    
    # RAG相关目录
    "rag_root": PROJECT_ROOT / "RAG",
    "rag_db": PROJECT_ROOT / "RAG" / "DB",
    "rag_uploads": PROJECT_ROOT / "RAG" / "DB" / "uploads",
    
    # 模型目录
    "models_dir": PROJECT_ROOT / "RAG" / "models",
    "m3e_model": PROJECT_ROOT / "RAG" / "models" / "m3e-base",
    
    # 数据目录
    "patient_data": PROJECT_ROOT / "patient_data",
    "cmee_data": PROJECT_ROOT / "CMeEE-V2",
    
    # 临时上传目录
    "temp_uploads": PROJECT_ROOT / "temp_uploads",
}

# 支持环境变量覆盖路径
for key in PATHS.keys():
    env_key = f"PROJECT_{key.upper()}"
    if env_key in os.environ:
        PATHS[key] = Path(os.environ[env_key])

# ============================================================================
# Neo4j 数据库配置
# ============================================================================

NEO4J_CONFIG = {
    "uri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    "user": os.getenv("NEO4J_USER", "neo4j"),
    "password": os.getenv("NEO4J_PASSWORD", "test1234"),
}

# ============================================================================
# Redis 配置
# ============================================================================

REDIS_CONFIG = {
    "host": os.getenv("REDIS_HOST", "localhost"),
    "port": int(os.getenv("REDIS_PORT", "6379")),
    "password": os.getenv("REDIS_PASSWORD", None),
    "db": int(os.getenv("REDIS_DB", "0")),
}

# ============================================================================
# LLM 配置
# ============================================================================

LLM_CONFIG = {
    # 模型配置
    "model": os.getenv("LLM_MODEL", "qwen2.5:14b"),
    "base_url": os.getenv("LLM_BASE_URL", "https://zjlchat.vip.cpolar.cn/v1"),
    "api_key": os.getenv("LLM_API_KEY", "EMPTY"),
    
    # 默认参数
    "temperature": float(os.getenv("LLM_TEMPERATURE", "0.1")),
    "top_p": float(os.getenv("LLM_TOP_P", "0.8")),
}

# 特定节点的LLM配置（覆盖默认配置）
LLM_NODE_CONFIGS = {
    "query_node": {
        "temperature": 0.3,
        "top_p": 0.9,
    },
}

# ============================================================================
# MCP 配置
# ============================================================================

MCP_CONFIG = {
    "servers": {
        "triage": {
            "url": os.getenv("MCP_TRIAGE_URL", "http://localhost:8000/sse"),
            "headers": {},
            "transport": "sse"
        }
    }
}

# ============================================================================
# 文档处理配置
# ============================================================================

PROCESSING_CONFIG = {
    # 文本分块大小
    "chunk_size": int(os.getenv("CHUNK_SIZE", "2000")),
    # 文本分块重叠
    "chunk_overlap": int(os.getenv("CHUNK_OVERLAP", "200")),
    # LLM请求间隔（秒）
    "request_interval": float(os.getenv("REQUEST_INTERVAL", "1")),
}

# ============================================================================
# 工具函数
# ============================================================================

def get_path(key: str) -> Path:
    """
    获取配置的路径
    
    Args:
        key: 路径键名，如 'knowledges_dir', 'm3e_model' 等
        
    Returns:
        Path对象
        
    Raises:
        KeyError: 如果key不存在
    """
    if key not in PATHS:
        raise KeyError(f"未知的路径配置: {key}。可用的配置: {list(PATHS.keys())}")
    
    path = PATHS[key]
    
    # 自动创建目录（如果需要且不存在）
    if key.endswith('_dir') or key in ['temp_uploads', 'rag_uploads', 'patient_data']:
        path.mkdir(parents=True, exist_ok=True)
    
    return path


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


def get_redis_config() -> dict:
    """
    获取Redis配置
    
    Returns:
        Redis配置字典
    """
    return REDIS_CONFIG.copy()


def get_mcp_config() -> dict:
    """
    获取MCP配置
    
    Returns:
        MCP配置字典
    """
    return MCP_CONFIG.copy()


def ensure_directories():
    """确保所有必要的目录存在"""
    for key, path in PATHS.items():
        if key.endswith('_dir') or key in ['temp_uploads', 'rag_uploads', 'patient_data']:
            path.mkdir(parents=True, exist_ok=True)
            

# ============================================================================
# 初始化
# ============================================================================

# 程序启动时确保目录存在
ensure_directories()

# ============================================================================
# 使用示例和测试
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("项目全局配置信息")
    print("=" * 70)
    
    print(f"\n【项目根目录】")
    print(f"  {PROJECT_ROOT}")
    
    print(f"\n【路径配置】")
    for key, path in PATHS.items():
        exists = "✓" if path.exists() else "✗"
        print(f"  [{exists}] {key:20} -> {path}")
    
    print(f"\n【Neo4j配置】")
    for key, value in NEO4J_CONFIG.items():
        if key == "password":
            print(f"  {key:20} -> {'*' * len(value)}")
        else:
            print(f"  {key:20} -> {value}")
    
    print(f"\n【Redis配置】")
    for key, value in REDIS_CONFIG.items():
        if key == "password" and value:
            print(f"  {key:20} -> {'*' * len(value)}")
        else:
            print(f"  {key:20} -> {value}")
    
    print(f"\n【LLM默认配置】")
    for key, value in LLM_CONFIG.items():
        if key == "api_key":
            print(f"  {key:20} -> {value if value == 'EMPTY' else '***'}")
        else:
            print(f"  {key:20} -> {value}")
    
    print(f"\n【LLM节点配置】")
    for node_name, node_config in LLM_NODE_CONFIGS.items():
        print(f"  {node_name}:")
        for key, value in node_config.items():
            print(f"    {key:18} -> {value}")
    
    print(f"\n【文档处理配置】")
    for key, value in PROCESSING_CONFIG.items():
        print(f"  {key:20} -> {value}")
    
    print("\n" + "=" * 70)
    print("配置加载成功！")
    print("=" * 70)
    
    # 测试路径获取
    print("\n【测试路径获取】")
    try:
        knowledges_dir = get_path("knowledges_dir")
        print(f"  ✓ get_path('knowledges_dir') -> {knowledges_dir}")
        
        model_path = get_path("m3e_model")
        print(f"  ✓ get_path('m3e_model') -> {model_path}")
    except Exception as e:
        print(f"  ✗ 错误: {e}")

