"""
工作流配置文件
此文件已废弃，请使用项目根目录的 config.py
为了保持兼容性，此文件将继续从全局配置导入
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 从全局配置导入
from config import (
    NEO4J_CONFIG,
    LLM_CONFIG,
    PROCESSING_CONFIG,
    get_path
)

# 输出目录配置（为了兼容性）
OUTPUT_CONFIG = {
    "base_dir": str(get_path("knowledges_dir"))
}

