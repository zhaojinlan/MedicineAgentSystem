# 医疗多智能体系统 - Docker部署指南（Windows版）

本文档详细说明如何在Windows环境下使用Docker部署医疗多智能体系统。

> **注意**：本文档专为Windows环境编写。Linux/Mac用户请参考相应命令调整。

## 目录

- [部署场景](#部署场景)
- [前置要求](#前置要求)
- [Windows环境准备](#windows环境准备)
- [场景1：完整部署（推荐首次部署）](#场景1完整部署推荐首次部署)
- [场景2：应用部署（连接已有数据库）](#场景2应用部署连接已有数据库)
- [配置说明](#配置说明)
- [Windows特殊注意事项](#windows特殊注意事项)
- [常见问题](#常见问题)
- [服务管理](#服务管理)

---

## 部署场景

本系统提供两种Docker部署方案：

### 场景1：完整部署（Full Deployment）
- **包含服务**：Redis、Neo4j、MCP、Backend、Frontend
- **适用场景**：首次部署、开发测试环境、独立完整系统
- **配置文件**：`docker-compose.full.yml`

### 场景2：应用部署（App-Only Deployment）
- **包含服务**：MCP、Backend、Frontend
- **适用场景**：已有Redis和Neo4j实例、生产环境、资源共享
- **配置文件**：`docker-compose.app.yml`

---

## 前置要求

### 1. 操作系统要求

- **Windows 10/11 专业版、企业版或教育版**（支持Hyper-V）
- 或 **Windows 10/11 家庭版**（使用WSL 2后端）
- 建议启用WSL 2以获得更好的性能

### 2. Docker Desktop for Windows

下载并安装 Docker Desktop：
- 下载地址：https://www.docker.com/products/docker-desktop
- 版本要求：Docker Desktop >= 4.0
- 包含：Docker Engine >= 20.10 和 Docker Compose >= 2.0

**安装后验证：**
```powershell
# 打开PowerShell或命令提示符
docker --version
docker-compose --version
```

预期输出示例：
```
Docker version 24.0.x, build xxxxx
Docker Compose version v2.x.x
```

### 3. 系统资源配置

**Docker Desktop资源设置：**
1. 打开Docker Desktop
2. 进入 Settings → Resources
3. 配置资源（根据部署场景）：

   - **完整部署**：
     - CPU: 4核心或更多
     - Memory: 8GB 或更多
     - Swap: 2GB
     - Disk: 50GB 可用空间

   - **应用部署**：
     - CPU: 2核心或更多
     - Memory: 4GB 或更多
     - Swap: 1GB
     - Disk: 30GB 可用空间

### 4. 网络要求

- 能够访问外部LLM服务（如配置的 qwen2.5 服务）
- 首次构建需要下载Docker镜像和Python依赖（约2-5GB）
- 如需下载m3e-base模型，还需约1GB流量

### 5. 端口占用检查

在部署前检查所需端口是否被占用：

```powershell
# 完整部署 - 检查所有端口
netstat -an | findstr "80 6379 7474 7687 8000 8012"

# 应用部署 - 检查应用端口
netstat -an | findstr "80 8000 8012"
```

如有端口被占用，可以：
- 关闭占用端口的程序
- 或在 `.env` 文件中修改端口配置

---

## Windows环境准备

### 启用WSL 2（推荐）

WSL 2提供更好的Docker性能，强烈推荐启用：

1. **以管理员身份运行PowerShell**，执行：
   ```powershell
   wsl --install
   ```

2. **重启电脑**

3. **设置Docker使用WSL 2**：
   - 打开Docker Desktop
   - Settings → General
   - 勾选 "Use the WSL 2 based engine"

### 配置Docker Desktop

1. **确保Docker Desktop正在运行**
   - 查看系统托盘，确认Docker图标显示且运行中
   - 如未运行，从开始菜单启动"Docker Desktop"

2. **配置文件共享**（如需要）
   - Settings → Resources → File Sharing
   - 添加项目所在驱动器（如 `O:\`）

3. **配置镜像加速**（可选，加速镜像下载）
   - Settings → Docker Engine
   - 添加国内镜像源（如需要）：
   ```json
   {
     "registry-mirrors": [
       "https://docker.mirrors.ustc.edu.cn",
       "https://hub-mirror.c.163.com"
     ]
   }
   ```

### PowerShell vs 命令提示符

本文档中的命令在 **PowerShell**、**命令提示符(CMD)** 或 **Windows Terminal** 中均可运行。推荐使用 **Windows Terminal** 以获得更好体验。

---

## 场景1：完整部署（推荐首次部署）

### 步骤1：准备配置文件

**在PowerShell中：**
```powershell
# 复制环境变量模板
Copy-Item env.example .env

# 编辑配置文件（可选，默认配置已可用）
notepad .env
```

**在命令提示符(CMD)中：**
```cmd
# 复制环境变量模板
copy env.example .env

# 编辑配置文件（可选，默认配置已可用）
notepad .env
```

> **提示**：如果不创建 `.env` 文件，系统将使用 `docker-compose.full.yml` 中定义的默认值。

### 步骤2：启动所有服务

在项目根目录（包含 `docker-compose.full.yml` 的目录）下执行：

```powershell
# 构建并启动所有服务
docker-compose -f docker-compose.full.yml up -d

# 查看启动日志（实时跟踪）
docker-compose -f docker-compose.full.yml logs -f
```

> **说明**：
> - `-d` 参数表示后台运行
> - 首次运行需要构建镜像，耗时约10-20分钟
> - 按 `Ctrl + C` 可退出日志查看（不会停止服务）

### 步骤3：等待服务就绪

服务启动需要一定时间，特别是首次启动：

```bash
# 检查服务健康状态
docker-compose -f docker-compose.full.yml ps

# 等待所有服务变为 healthy 状态（约2-3分钟）
```

预期输出示例：
```
NAME                IMAGE                    STATUS
medical-redis       redis:8.2-alpine         Up (healthy)
medical-neo4j       neo4j:5.23              Up (healthy)
medical-mcp         medical-mcp:latest       Up (healthy)
medical-backend     medical-backend:latest   Up (healthy)
medical-frontend    medical-frontend:latest  Up (healthy)
```

### 步骤4：访问服务

使用浏览器访问以下地址：

- **前端界面**：http://localhost
- **后端API文档**：http://localhost:8012/docs（Swagger UI）
- **Neo4j浏览器**：http://localhost:7474
  - 用户名：`neo4j`
  - 密码：`test1234`（或您在.env中设置的密码）

### 步骤5：验证部署

**使用浏览器测试（推荐）：**
- 前端：http://localhost
- 后端API文档：http://localhost:8012/docs
- Neo4j浏览器：http://localhost:7474

**使用PowerShell测试（可选）：**
```powershell
# 测试后端API
Invoke-WebRequest -Uri http://localhost:8012/ -UseBasicParsing

# 测试MCP服务
Invoke-WebRequest -Uri http://localhost:8000/ -UseBasicParsing

# 测试Redis连接
docker exec medical-redis redis-cli ping
# 应返回：PONG

# 测试Neo4j连接
docker exec medical-neo4j cypher-shell -u neo4j -p test1234 "RETURN 1"
# 应返回：1
```

**使用命令提示符测试（可选）：**
```cmd
# 如果安装了curl
curl http://localhost:8012/
curl http://localhost:8000/

# 测试数据库连接
docker exec medical-redis redis-cli ping
docker exec medical-neo4j cypher-shell -u neo4j -p test1234 "RETURN 1"
```

---

## 场景2：应用部署（连接已有数据库）

### 前提条件

确保您已有运行中的Redis和Neo4j实例，并且：
1. 知道它们的连接地址和端口
2. 有正确的认证凭据
3. 网络可达（如果在Docker中，确保网络配置正确）

### 步骤1：配置连接信息

**复制并编辑配置文件：**

PowerShell：
```powershell
Copy-Item env.example .env
notepad .env
```

命令提示符：
```cmd
copy env.example .env
notepad .env
```

**重要配置项（Windows环境）：**

```ini
# ============================================================================
# Windows环境下连接外部数据库的配置示例
# ============================================================================

# 场景1：Redis和Neo4j在Windows宿主机上（Docker Desktop外部）
# 使用 host.docker.internal 访问宿主机
NEO4J_URI=bolt://host.docker.internal:7687
REDIS_HOST=host.docker.internal
REDIS_PORT=6379

# 场景2：Redis和Neo4j在另一个Docker Compose中
# 使用容器名（需要在同一网络）
NEO4J_URI=bolt://neo4j:7687
REDIS_HOST=redis

# 场景3：Redis和Neo4j在同一WSL2实例中
# 使用 WSL2 的 IP 地址（可通过 wsl hostname -I 查看）
NEO4J_URI=bolt://172.x.x.x:7687
REDIS_HOST=172.x.x.x

# 场景4：Redis和Neo4j在局域网其他机器
NEO4J_URI=bolt://192.168.1.xxx:7687
REDIS_HOST=192.168.1.xxx

# 认证信息
NEO4J_USER=neo4j
NEO4J_PASSWORD=你的Neo4j密码
REDIS_PASSWORD=你的Redis密码（如果设置了密码）
REDIS_DB=0
```

> **Windows特别提示**：
> - `host.docker.internal` 是Docker Desktop提供的特殊域名，指向Windows宿主机
> - 如果Redis/Neo4j在WSL2中运行，需要使用WSL2的IP地址，不是localhost
> - 查看WSL2 IP：在WSL2中运行 `ip addr show eth0`

### 步骤2：测试数据库连接

在启动应用前，建议先测试数据库连接：

**Windows环境测试方法：**

1. **测试Neo4j连接**：

   访问 Neo4j Browser：http://localhost:7474
   - 如果能打开并登录，说明Neo4j可访问

   或使用Docker测试：
   ```powershell
   docker exec -it <你的neo4j容器名> cypher-shell -u neo4j -p test1234 "RETURN 1"
   ```

2. **测试Redis连接**：

   ```powershell
   # 如果Redis在本机（安装了Redis客户端）
   redis-cli ping

   # 或使用Docker测试
   docker run --rm redis:8.2-alpine redis-cli -h host.docker.internal -p 6379 ping
   ```

3. **确认数据库可访问**：
   
   如果上述测试成功，说明配置正确，可以继续部署应用。

### 步骤3：启动应用服务

```bash
# 构建并启动应用服务
docker-compose -f docker-compose.app.yml up -d

# 查看启动日志
docker-compose -f docker-compose.app.yml logs -f
```

### 步骤4：验证连接

```bash
# 检查服务状态
docker-compose -f docker-compose.app.yml ps

# 查看后端日志，确认数据库连接成功
docker-compose -f docker-compose.app.yml logs backend | grep -i "connect"
```

### 步骤5：访问服务

- **前端界面**：http://localhost
- **后端API文档**：http://localhost:8012/docs

---

## 配置说明

### 环境变量详解

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `NEO4J_URI` | `bolt://neo4j:7687` | Neo4j连接地址 |
| `NEO4J_USER` | `neo4j` | Neo4j用户名 |
| `NEO4J_PASSWORD` | `test1234` | Neo4j密码 |
| `REDIS_HOST` | `redis` | Redis主机地址 |
| `REDIS_PORT` | `6379` | Redis端口 |
| `REDIS_PASSWORD` | `` | Redis密码（可选） |
| `LLM_MODEL` | `qwen2.5:14b` | LLM模型名称 |
| `LLM_BASE_URL` | `https://...` | LLM服务地址 |
| `BACKEND_PORT` | `8012` | 后端服务端口 |
| `FRONTEND_PORT` | `80` | 前端服务端口 |

### 端口映射

| 服务 | 容器端口 | 宿主机端口（默认） | 说明 |
|------|---------|-------------------|------|
| Frontend | 80 | 80 | Web前端界面 |
| Backend | 8012 | 8012 | API服务 |
| MCP | 8000 | 8000 | MCP服务 |
| Neo4j HTTP | 7474 | 7474 | Neo4j Web界面 |
| Neo4j Bolt | 7687 | 7687 | Neo4j数据库连接 |
| Redis | 6379 | 6379 | Redis数据库 |

**修改端口映射：**

在 `.env` 文件中修改：
```ini
FRONTEND_PORT=8080
BACKEND_PORT=8013
```

### 数据持久化

完整部署模式下，以下数据会持久化存储：

- **Neo4j数据**：`neo4j_data` volume
- **Redis数据**：`redis_data` volume
- **患者数据**：`./patient_data` 目录
- **知识库数据**：`./Knowledges` 目录
- **上传文件**：`./temp_uploads` 目录
- **RAG数据库**：`./RAG/DB` 目录
- **模型文件**：`./RAG/models` 目录

**查看数据卷：**

PowerShell:
```powershell
docker volume ls | Select-String medical
```

命令提示符:
```cmd
docker volume ls | findstr medical
```

**备份数据卷：**

PowerShell:
```powershell
# 备份Neo4j数据
docker run --rm -v medical_neo4j_data:/data -v ${PWD}:/backup ubuntu tar czf /backup/neo4j_backup.tar.gz /data

# 备份Redis数据
docker run --rm -v medical_redis_data:/data -v ${PWD}:/backup ubuntu tar czf /backup/redis_backup.tar.gz /data
```

命令提示符:
```cmd
# 备份Neo4j数据（需要在项目目录下执行）
docker run --rm -v medical_neo4j_data:/data -v %cd%:/backup ubuntu tar czf /backup/neo4j_backup.tar.gz /data

# 备份Redis数据
docker run --rm -v medical_redis_data:/data -v %cd%:/backup ubuntu tar czf /backup/redis_backup.tar.gz /data
```

---

## Windows特殊注意事项

### 1. 路径处理

Windows使用反斜杠 `\` 作为路径分隔符，但Docker Compose配置文件中使用正斜杠 `/`：

```yaml
# docker-compose配置中的路径（正确）
volumes:
  - ./patient_data:/app/patient_data
  - ./RAG/models:/app/RAG/models
```

在Windows命令行中操作文件：
```powershell
# PowerShell中复制文件
Copy-Item env.example .env

# CMD中复制文件
copy env.example .env
```

### 2. 行尾符问题（CRLF vs LF）

Windows使用CRLF作为行尾符，但Docker容器内是Linux环境，使用LF。这可能导致脚本执行问题。

**解决方法**：
- 如果使用Git，配置自动转换：
  ```powershell
  git config --global core.autocrlf true
  ```

### 3. WSL 2与Docker Desktop

**推荐配置**：
1. 启用WSL 2
2. Docker Desktop使用WSL 2引擎
3. 项目文件放在WSL 2文件系统中（如 `/home/user/project`）以获得最佳性能

**性能对比**：
- WSL 2文件系统：I/O性能接近原生Linux
- Windows文件系统（C:\、D:\等）：I/O性能较慢

**访问WSL 2文件系统**：
```powershell
# 在Windows资源管理器中访问
\\wsl$\Ubuntu\home\your-username\
```

### 4. host.docker.internal的使用

`host.docker.internal` 是Docker Desktop for Windows提供的特殊DNS名称，指向宿主机。

**使用场景**：
- 容器需要访问Windows宿主机上的服务（如Neo4j、Redis）
- 容器需要访问宿主机上的其他应用

```ini
# .env配置示例
NEO4J_URI=bolt://host.docker.internal:7687
REDIS_HOST=host.docker.internal
```

**注意**：Linux环境下没有 `host.docker.internal`，需要使用其他方法。

### 5. 防火墙配置

Windows防火墙可能阻止Docker容器访问宿主机服务。

**解决方法**：
1. 打开"Windows Defender 防火墙"
2. 点击"高级设置"
3. 创建入站规则，允许特定端口（如7687、6379）

或使用PowerShell（以管理员身份运行）：
```powershell
# 允许Neo4j端口
New-NetFirewallRule -DisplayName "Neo4j Bolt" -Direction Inbound -LocalPort 7687 -Protocol TCP -Action Allow

# 允许Redis端口
New-NetFirewallRule -DisplayName "Redis" -Direction Inbound -LocalPort 6379 -Protocol TCP -Action Allow
```

### 6. Docker Desktop资源限制

定期检查和调整Docker Desktop资源分配：

```
Docker Desktop → Settings → Resources
- CPU: 根据需要调整
- Memory: 建议至少4GB（完整部署需8GB）
- Disk image size: 建议至少50GB
```

**查看资源使用情况**：
```powershell
docker stats
```

### 7. 权限问题

容器内创建的文件可能在Windows上显示权限问题。

**解决方法**：
- 在Windows上正常操作，权限问题不影响使用
- 如需修改权限，在容器内操作：
  ```powershell
  docker exec -it medical-backend bash
  chmod -R 755 /app/patient_data
  ```

### 8. 模型文件下载

首次启动需要下载m3e-base模型（约1GB），可能较慢。

**加速方法**：
1. **使用镜像源**（在Dockerfile中已配置）
2. **预先下载模型**：
   ```powershell
   # 创建模型目录
   mkdir -p RAG\models\m3e-base
   
   # 手动下载模型文件到该目录
   # 然后在docker-compose中挂载
   ```

### 9. 数据卷位置

Docker Desktop的数据卷存储在：
```
C:\Users\<用户名>\AppData\Local\Docker\wsl\data\ext4.vhdx
```

**查看数据卷大小**：
```powershell
docker system df
```

**清理未使用的数据卷**：
```powershell
docker volume prune
```

### 10. 常用Windows快捷操作

**快速重启Docker Desktop**：
```powershell
# 方法1：通过系统托盘右键"Restart"

# 方法2：使用命令（需要管理员权限）
net stop com.docker.service
net start com.docker.service
```

**查看Docker Desktop日志**：
```
Docker Desktop → Troubleshoot → Show logs
```

---

## 常见问题

### 1. 服务启动失败

**问题**：服务无法启动或不断重启

**解决方法**：
```powershell
# 查看服务日志
docker-compose -f docker-compose.full.yml logs <服务名>

# 查看实时日志
docker-compose -f docker-compose.full.yml logs -f <服务名>
```

**常见原因**：
1. **端口被占用**：修改 `.env` 中的端口配置
   ```powershell
   # 检查端口占用（PowerShell）
   Get-NetTCPConnection -LocalPort 80,6379,7474,7687,8000,8012 -State Listen
   ```

2. **数据库连接失败**：检查网络和认证信息

3. **内存不足**：增加Docker Desktop内存限制
   - Docker Desktop → Settings → Resources → Memory

4. **Docker Desktop未启动**：
   - 查看系统托盘，确认Docker正在运行

### 2. Neo4j连接超时

**问题**：应用无法连接到Neo4j

**解决方法**：

PowerShell:
```powershell
# 1. 检查Neo4j是否启动
docker ps | Select-String neo4j

# 2. 检查Neo4j健康状态
docker exec medical-neo4j cypher-shell -u neo4j -p test1234 "RETURN 1"

# 3. 确认网络配置
docker network inspect medical-network

# 4. 检查Neo4j容器日志
docker logs medical-neo4j --tail 50
```

命令提示符:
```cmd
# 1. 检查Neo4j是否启动
docker ps | findstr neo4j

# 2. 检查Neo4j健康状态
docker exec medical-neo4j cypher-shell -u neo4j -p test1234 "RETURN 1"
```

**Windows特定配置**：
- 应用部署模式，Windows宿主机上的Neo4j：`bolt://host.docker.internal:7687`
- 完整部署模式，Docker容器内的Neo4j：`bolt://neo4j:7687`

### 3. 模型文件下载缓慢

**问题**：首次启动时下载m3e-base模型很慢

**解决方法**：
```bash
# 方案1：提前下载模型到本地
mkdir -p RAG/models
# 手动下载模型到 RAG/models/m3e-base/

# 方案2：使用镜像源
# 在 Dockerfile 中添加：
ENV HF_ENDPOINT=https://hf-mirror.com
```

### 4. Docker构建时网络连接失败

**问题**：构建镜像时出现 `Unable to connect to deb.debian.org` 或类似网络错误

```
E: Failed to fetch http://deb.debian.org/debian/pool/...
E: Unable to fetch some archives, maybe run apt-get update or try with --fix-missing?
```

**原因**：
- 网络连接问题
- DNS解析问题
- 防火墙阻止
- Docker网络配置问题

**Windows环境解决方法**：

**方法1：检查网络连接（最常见）**
```powershell
# 测试能否访问Debian源
Test-NetConnection deb.debian.org -Port 80

# 测试DNS解析
nslookup deb.debian.org
```

如果无法连接，检查：
- 网络是否正常
- 防火墙是否阻止Docker
- 代理设置是否正确

**方法2：配置Docker使用代理（如果有代理）**

在 Docker Desktop 中配置：
1. Docker Desktop → Settings → Resources → Proxies
2. 启用 Manual proxy configuration
3. 输入HTTP/HTTPS代理地址

**方法3：使用国内镜像源（推荐）**

修改 `Dockerfile.mcp`，在 `RUN apt-get update` 之前添加：

```dockerfile
# 使用清华大学镜像源
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources || \
    sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list
```

完整修改示例：
```dockerfile
# 在 apt-get update 之前添加
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources || \
    sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list && \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    curl \
    wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
```

同样修改 `Dockerfile` 文件。

**方法4：重启Docker Desktop**

有时候重启Docker可以解决网络问题：
```powershell
# 通过系统托盘重启Docker Desktop
# 或使用命令（管理员权限）
net stop com.docker.service
net start com.docker.service
```

**方法5：等待并重试**

如果是临时网络问题，等待几分钟后重试：
```powershell
# 清理失败的构建缓存
docker builder prune

# 重新构建
docker-compose -f docker-compose.full.yml up -d --build
```

### 5. 前端无法访问后端

**问题**：前端页面加载，但无法调用API

**解决方法**：

PowerShell:
```powershell
# 1. 检查后端服务状态
docker-compose -f docker-compose.full.yml ps backend

# 2. 测试后端API
Invoke-WebRequest -Uri http://localhost:8012/ -UseBasicParsing

# 3. 检查nginx配置
docker exec medical-frontend cat /etc/nginx/conf.d/default.conf

# 4. 查看nginx日志
docker logs medical-frontend
```

命令提示符:
```cmd
# 1. 检查后端服务状态
docker-compose -f docker-compose.full.yml ps backend

# 2. 检查nginx配置
docker exec medical-frontend cat /etc/nginx/conf.d/default.conf

# 3. 查看nginx日志
docker logs medical-frontend
```

### 5. 数据库密码错误

**问题**：应用报告数据库认证失败

**解决方法**：
```bash
# 1. 确认 .env 中的密码配置正确

# 2. 完整部署模式：
# Neo4j首次启动后不能通过环境变量更改密码
# 如需更改密码，先删除数据卷：
docker-compose -f docker-compose.full.yml down -v
docker-compose -f docker-compose.full.yml up -d

# 3. 应用部署模式：
# 确保使用正确的外部数据库密码
```

### 6. 应用部署模式下服务无法访问外部数据库

**问题**：MCP或Backend无法连接到宿主机上的数据库

**Windows解决方法**：

1. **使用 host.docker.internal（推荐）**
   ```ini
   # .env 配置
   NEO4J_URI=bolt://host.docker.internal:7687
   REDIS_HOST=host.docker.internal
   ```

2. **检查防火墙设置**
   ```powershell
   # 以管理员身份运行PowerShell
   # 允许Neo4j端口
   New-NetFirewallRule -DisplayName "Neo4j Bolt" -Direction Inbound -LocalPort 7687 -Protocol TCP -Action Allow
   
   # 允许Redis端口
   New-NetFirewallRule -DisplayName "Redis" -Direction Inbound -LocalPort 6379 -Protocol TCP -Action Allow
   ```

3. **检查数据库是否监听正确的地址**
   ```powershell
   # 检查端口监听
   netstat -an | findstr "7687 6379"
   ```
   
   确保数据库监听 `0.0.0.0` 或 `127.0.0.1`，而不仅仅是 `localhost`

4. **测试连接**
   ```powershell
   # 从容器内测试连接
   docker run --rm redis:8.2-alpine redis-cli -h host.docker.internal -p 6379 ping
   ```

---

## 服务管理

### 启动服务

```bash
# 完整部署
docker-compose -f docker-compose.full.yml up -d

# 应用部署
docker-compose -f docker-compose.app.yml up -d

# 只启动特定服务
docker-compose -f docker-compose.full.yml up -d backend frontend
```

### 停止服务

```bash
# 停止所有服务
docker-compose -f docker-compose.full.yml down

# 停止并删除数据卷（警告：会删除所有数据）
docker-compose -f docker-compose.full.yml down -v

# 只停止特定服务
docker-compose -f docker-compose.full.yml stop backend
```

### 重启服务

```bash
# 重启所有服务
docker-compose -f docker-compose.full.yml restart

# 重启特定服务
docker-compose -f docker-compose.full.yml restart backend
```

### 查看日志

```bash
# 查看所有服务日志
docker-compose -f docker-compose.full.yml logs

# 实时跟踪日志
docker-compose -f docker-compose.full.yml logs -f

# 查看特定服务日志
docker-compose -f docker-compose.full.yml logs backend

# 查看最近100行日志
docker-compose -f docker-compose.full.yml logs --tail=100 backend
```

### 进入容器

```bash
# 进入后端容器
docker exec -it medical-backend bash

# 进入Neo4j容器
docker exec -it medical-neo4j bash

# 进入Redis容器并使用redis-cli
docker exec -it medical-redis redis-cli
```

### 更新服务

```bash
# 重新构建并启动
docker-compose -f docker-compose.full.yml up -d --build

# 只重新构建特定服务
docker-compose -f docker-compose.full.yml build backend
docker-compose -f docker-compose.full.yml up -d backend
```

### 清理资源

```bash
# 清理未使用的镜像
docker image prune -a

# 清理未使用的容器
docker container prune

# 清理未使用的数据卷
docker volume prune

# 清理所有未使用的资源
docker system prune -a --volumes
```

---

## 生产环境建议

1. **使用应用部署模式**：将数据库与应用分离
2. **配置外部数据卷**：避免数据丢失
3. **启用HTTPS**：使用反向代理（如Nginx、Traefik）
4. **资源限制**：在docker-compose中添加资源限制
5. **日志管理**：配置日志驱动和轮转
6. **监控告警**：使用Prometheus、Grafana等监控工具
7. **定期备份**：备份数据库和重要数据
8. **安全加固**：
   - 修改默认密码
   - 限制网络访问
   - 使用防火墙规则
   - 定期更新镜像

---

## 支持与反馈

如遇到问题或有改进建议，请：
1. 查看本文档的"常见问题"部分
2. 检查服务日志获取详细错误信息
3. 确认配置文件正确
4. 验证网络和端口配置

---

**祝部署顺利！**

