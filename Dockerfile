# ============================================================================
# 医疗多智能体系统 - 后端服务 Dockerfile
# ============================================================================

FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# 安装系统依赖
# 使用镜像源提高下载速度和稳定性（支持国内网络环境）
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list 2>/dev/null || true && \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    git \
    curl \
    wget \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 复制requirements.txt（利用Docker缓存）
COPY requirements.txt .

# 安装Python依赖
# 分步安装以提高构建效率和容错性
# 使用清华PyPI镜像加速下载
RUN pip install --upgrade pip setuptools wheel -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    pip install -i https://pypi.tuna.tsinghua.edu.cn/simple sentence-transformers transformers && \
    pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 复制项目文件
COPY Agent/ ./Agent/
COPY Construct/ ./Construct/
COPY RAG/ ./RAG/
COPY MCP/ ./MCP/
COPY backend_api.py .
COPY config.py .

# 创建必要的目录
RUN mkdir -p \
    patient_data \
    temp_uploads \
    Knowledges \
    RAG/DB/uploads \
    RAG/models

# 暴露端口
EXPOSE 8012

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8012/')" || exit 1

# 启动命令
CMD ["python", "-m", "uvicorn", "backend_api:app", "--host", "0.0.0.0", "--port", "8012"]

