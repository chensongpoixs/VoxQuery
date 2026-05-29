# 部署运维手册

## 1. 环境要求

### 1.1 硬件配置

| Profile | GPU 配置 | 显存 | 适用场景 |
|---------|---------|------|---------|
| `multi-gpu` | 4×NVIDIA RTX 4090 (24GB) | 96GB 总 | 生产环境，分布式推理 |
| `single-gpu` | 1×NVIDIA RTX 5080 (24GB) | 24GB | 开发/测试环境，全模型单卡 |

**通用要求：**

| 资源 | 最低 | 推荐 |
|------|------|------|
| CPU | 8 核 | 16 核+ |
| 内存 | 32GB | 64GB+ |
| 磁盘 | 200GB SSD | 500GB+ NVMe |
| 网络 | 千兆 | 万兆（音频流场景） |

**磁盘空间明细：**

| 数据 | 大小 | 说明 |
|------|------|------|
| 模型文件（multi-gpu） | ~57GB | Gemma-3 27B + BGE-M3 + Whisper + CosyVoice2 |
| 模型文件（single-gpu） | ~9GB | Gemma-4 E2B + BGE-M3 + Whisper + CosyVoice2 |
| Docker 镜像 | ~15GB | 8 个服务镜像（含 CUDA 基础镜像） |
| 向量数据库 | 视文档量 | 每 1000 页文档约 1-2GB |
| Redis 数据 | < 1GB | 对话历史 + 检索缓存 |
| 日志 | 10-50GB | 建议配置日志轮转 |

### 1.2 软件依赖

| 软件 | 最低版本 | 用途 |
|------|---------|------|
| Ubuntu | 22.04 LTS | 推荐操作系统（也支持 WSL2 开发） |
| NVIDIA Driver | 535.x | GPU 驱动 |
| CUDA | 12.4 | GPU 计算平台 |
| Docker | 24.0+ | 容器运行时（Docker 模式） |
| Docker Compose | 2.20+ | 容器编排（Docker 模式） |
| NVIDIA Container Toolkit | 1.14+ | Docker GPU 透传（Docker 模式） |
| Python | 3.11+ | 原生模式 + 配置工具 |
| Supervisor | 4.2+ | 进程管理（原生模式，可选） |

### 1.3 环境初始化

#### 安装 NVIDIA 驱动 + CUDA

```bash
# Ubuntu 22.04
# 1. 添加 NVIDIA 官方仓库
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt update

# 2. 安装驱动 + CUDA 12.4
sudo apt install -y cuda-toolkit-12-4 nvidia-driver-535

# 3. 重启
sudo reboot

# 4. 验证
nvidia-smi
# 应当输出 GPU 列表和驱动版本
```

#### 安装 Docker + NVIDIA Container Toolkit

```bash
# Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker

# Docker Compose（独立插件）
sudo apt install -y docker-compose-v2

# NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update
sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# 验证 GPU 透传
docker run --rm --gpus all nvidia/cuda:12.4.0-runtime-ubuntu22.04 nvidia-smi
```

#### 安装 Python 依赖（原生模式）

```bash
# 原生模式需要安装所有服务的 Python 依赖
cd aigic

pip install -r services/api-gateway/requirements.txt
pip install -r services/llm-service/requirements.txt
pip install -r services/embedding-service/requirements.txt
pip install -r services/rag-service/requirements.txt
pip install -r services/asr-service/requirements.txt
pip install -r services/tts-service/requirements.txt

# 配置工具依赖
pip install pydantic pydantic-settings pyyaml
```

---

## 2. Profile 配置系统

### 2.1 概念

Profile 是部署配置的**唯一真实来源**。一个 YAML 文件（`configs/profiles/<name>.yaml`）定义了：

```
Profile YAML
  ├── 硬件规格：GPU 数量、型号、显存
  ├── 部署模式：docker / native
  ├── 服务配置：每个服务的模型选型、GPU 分配、推理参数
  └── 模型下载：模型名称、存储路径
```

运行 `make config` 从 profile 自动生成：

| 生成文件 | 用途 |
|---------|------|
| `.env` | 环境变量（所有服务共享） |
| `docker-compose.override.yml` | GPU 设备绑定（Docker 模式） |
| `supervisord.conf` | 进程管理配置（原生模式） |
| `systemd/*.service` | systemd 单元文件（原生模式） |

### 2.2 内置 Profile

```bash
# 查看所有可用 profile
make config-list

# 输出：
#   可用的硬件 Profile:
#     multi-gpu             — 4×RTX 4090 (24GB×4) 分布式部署，适合生产环境
#     single-gpu            — 单张 RTX 5080 (24GB) 部署全部模型，适合开发测试环境
```

#### multi-gpu (4×RTX 4090)

```
GPU 0,1 ── LLM Service  (Gemma-3 27B, TP=2, AWQ)    ~22GB ×2
GPU 2   ── Embedding    (BGE-M3)                     ~6GB
GPU 3   ── ASR + TTS    (Whisper-v3 + CosyVoice2)    ~4GB + ~4GB
```

#### single-gpu (1×RTX 5080)

```
GPU 0 ── LLM (Gemma-4 E2B, INT4) + Embedding (BGE-M3)
         + ASR (Whisper-v3) + TTS (CosyVoice2)
         ── 总计 ~15.5GB / 24GB，余量安全
```

### 2.3 配置生成

```bash
# Docker 部署（默认 multi-gpu）
make config

# 等同于：
python configs/generate_config.py --profile multi-gpu --mode docker --force

# 单卡 Docker：
python configs/generate_config.py --profile single-gpu --mode docker --force

# 原生部署：
python configs/generate_config.py --profile multi-gpu --mode native --force

# 只生成到指定目录（预览模式）：
python configs/generate_config.py --profile single-gpu --output ./preview
```

### 2.4 自定义 Profile

```bash
# 1. 创建 profile 文件
cp configs/profiles/single-gpu.yaml configs/profiles/my-deploy.yaml

# 2. 编辑：修改 GPU 数量、模型路径、推理参数等
vim configs/profiles/my-deploy.yaml

# 3. 验证
python -c "
from configs.profile_loader import load_profile
spec = load_profile('my-deploy')
print(f'Profile: {spec.profile.name}, GPU: {spec.gpus.count}')
"

# 4. 生成配置
python configs/generate_config.py --profile my-deploy --force
```

---

## 3. 模型下载

### 3.1 自动下载（推荐）

```bash
# 根据当前 .env 中的 profile 下载全部模型
make download-models

# 或显式指定 profile：
bash scripts/download_models.sh --profile multi-gpu all   # ~57GB, 30-90 分钟
bash scripts/download_models.sh --profile single-gpu all   # ~9GB, 5-20 分钟
```

### 3.2 分模型下载

```bash
make download-model-llm         # Gemma-3 27B (~50GB) 或 Gemma-4 E2B (~2GB)
make download-model-embedding   # BGE-M3 (~2GB)
make download-model-whisper     # Whisper-large-v3 (~3GB)
make download-model-tts         # CosyVoice2 (~2GB)
```

### 3.3 镜像源选择

脚本自动按优先级检测最佳源：

```
1. ModelScope (modelscope.cn)   ← 国内最快，优先
2. HF Mirror   (hf-mirror.com)  ← 备选
3. HuggingFace (huggingface.co) ← 需代理
```

```bash
# 仅检测最佳镜像源（不下载）
make detect-mirror

# 手动指定
HF_ENDPOINT=https://hf-mirror.com bash scripts/download_models.sh all
```

### 3.4 模型存放位置

```
models/
├── gemma3/       # LLM: Gemma-3 27B 或 Gemma-4 E2B
├── bge-m3/       # Embedding: BGE-M3
├── whisper/      # ASR: Whisper-large-v3
└── cosyvoice2/   # TTS: CosyVoice2-0.5B
```

---

## 4. Docker 部署

### 4.1 服务拓扑

```
docker compose (kb-net bridge network)
├── redis           :6379     ← 对话历史 + 检索缓存
├── chromadb        :8004     ← 向量数据库
├── llm-service     :8001     ← GPU 0,1 (或 GPU 0)
├── embedding-svc   :8002     ← GPU 2 (或 GPU 0)
├── asr-service     :8005     ← GPU 3 (或 GPU 0)
├── tts-service     :8006     ← GPU 3 (或 GPU 0)
├── rag-service     :8003     ← CPU only
├── api-gateway     :8000     ← CPU only
└── frontend        :3000     ← CPU only
```

依赖关系（串行启动顺序）：

```
redis ──────────────┐
chromadb ───────────┤
llm-service ────────┤
embedding-service ──┼──> rag-service ──> api-gateway ──> frontend
asr-service ────────┤
tts-service ────────┘
```

### 4.2 启动时间参考

| 阶段 | 命令 | 预计时间 |
|------|------|---------|
| 镜像构建 | `make build` | 10-20 分钟（首次）/ 1-3 分钟（增量） |
| 核心服务启动 | `make start-core` | 2-3 分钟（LLM 加载模型最慢） |
| 语音服务启动 | `make start-voice` | 1-2 分钟 |
| 业务服务启动 | `make start-api` | 30 秒 |

### 4.3 一键部署

```bash
cd aigic

# Step 1: 生成配置
make config

# Step 2: 下载模型
make download-models

# Step 3: 构建镜像
make build

# Step 4: 启动全部服务
make start

# Step 5: 导入知识库
make kb-ingest

# 访问
# API 文档:  http://localhost:8000/docs
# 前端界面:  http://localhost:3000
# 健康检查:  curl http://localhost:8000/api/v1/admin/health
```

### 4.4 分阶段启动

```bash
# 适合调试场景：逐层启动，每一层确认后再继续

# 第 1 层：基础设施 + 模型推理
make start-core     # Redis + ChromaDB + LLM + Embedding
# 等待 LLM 就绪（约 2 分钟）
curl -f http://localhost:8001/health  && echo "LLM OK"
curl -f http://localhost:8002/health  && echo "Embedding OK"

# 第 2 层：语音服务
make start-voice    # ASR + TTS
curl -f http://localhost:8005/health  && echo "ASR OK"
curl -f http://localhost:8006/health  && echo "TTS OK"

# 第 3 层：业务 + 前端
make start-api      # RAG + API Gateway + Frontend
curl -f http://localhost:8000/health  && echo "API OK"
curl -f http://localhost:3000          && echo "Frontend OK"
```

### 4.5 停止 & 重启

```bash
make stop           # 停止全部（保留数据卷）
make restart        # 重启全部

# 单服务重启
docker compose restart llm-service
docker compose restart api-gateway

# 完全清除（含数据）
make clean          # docker compose down -v
```

### 4.6 查看日志

```bash
make logs           # 全部服务（tail -f）
make logs-llm       # 仅 LLM
make logs-rag       # 仅 RAG
make logs-api       # 仅 API Gateway

# 查看单容器最近日志
docker compose logs --tail=100 llm-service
```

### 4.7 状态检查

```bash
make status         # 容器运行状态（docker compose ps）
make health         # HTTP 健康检查脚本
```

---

## 5. 原生部署（Bare Metal）

### 5.1 适用场景

| 场景 | 推荐模式 |
|------|---------|
| 生产环境（稳定性优先） | Docker |
| 开发调试（热重载、断点） | 原生 |
| GPU 直通/特殊驱动 | 原生 |
| 资源受限（无 Docker） | 原生 |
| CI/CD 集成 | Docker |

### 5.2 环境准备

```bash
# 安装 Python 依赖（所有服务）
cd aigic
pip install -r services/api-gateway/requirements.txt
pip install -r services/llm-service/requirements.txt
pip install -r services/embedding-service/requirements.txt
pip install -r services/rag-service/requirements.txt
pip install -r services/asr-service/requirements.txt
pip install -r services/tts-service/requirements.txt

# 安装 Redis（如系统没有）
sudo apt install -y redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server

# 安装 ChromaDB
pip install chromadb

# 安装 Node.js（前端）
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
cd frontend && npm install && cd ..
```

### 5.3 启动流程

```bash
cd aigic

# Step 1: 生成原生部署配置
python configs/generate_config.py --profile multi-gpu --mode native --force

# Step 2: 下载模型（如未下载）
make download-models

# Step 3: 一键启动
make native-start

# 或分阶段：
make native-start-core     # Redis + LLM + Embedding
make native-start-voice    # ASR + TTS
make native-start-api      # RAG + API Gateway + Frontend

# 查看状态
make native-status
make native-health
```

### 5.4 使用 Supervisor 管理进程

```bash
# 安装 supervisor
sudo apt install -y supervisor

# 部署配置（从生成的 supervisord.conf）
sudo cp supervisord.conf /etc/supervisor/conf.d/kb-qa.conf
sudo supervisorctl reread
sudo supervisorctl update

# 常用操作
sudo supervisorctl status           # 查看所有进程
sudo supervisorctl start all         # 启动全部
sudo supervisorctl stop all          # 停止全部
sudo supervisorctl restart llm-service  # 重启单个
sudo supervisorctl tail -f api-gateway  # 查看日志
```

### 5.5 使用 Systemd 管理（生产推荐）

```bash
# 1. 生成 systemd unit 文件
python configs/generate_config.py --profile multi-gpu --mode native --force
# 输出在 systemd/ 目录下

# 2. 安装 unit 文件
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload

# 3. 启用开机自启
sudo systemctl enable llm-service embedding-service asr-service \
                      tts-service rag-service api-gateway

# 4. 启动
sudo systemctl start llm-service
# 等待 LLM 就绪后继续
sudo systemctl start embedding-service asr-service tts-service
sudo systemctl start rag-service api-gateway

# 5. 查看状态
sudo systemctl status 'kb-*'
```

---

## 6. Nginx 反向代理（生产环境）

### 6.1 HTTP 配置

```nginx
# /etc/nginx/sites-available/kb-qa
upstream api_gateway {
    server 127.0.0.1:8000;
}

upstream frontend {
    server 127.0.0.1:3000;
}

server {
    listen 80;
    server_name kb.your-company.com;

    # API 转发
    location /api/ {
        proxy_pass http://api_gateway;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 流式响应：关闭缓冲
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;

        # 文件上传限制（知识库文档）
        client_max_body_size 100M;
    }

    # WebSocket（语音流式转录）
    location /ws/ {
        proxy_pass http://api_gateway;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600s;
    }

    # 前端
    location / {
        proxy_pass http://frontend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }
}
```

### 6.2 HTTPS 配置

```bash
# 使用 Let's Encrypt
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d kb.your-company.com

# 自动续期（certbot 默认已配置 timer）
sudo certbot renew --dry-run
```

### 6.3 限流配置

```nginx
# 在 server 块中添加
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_conn_zone $binary_remote_addr zone=conn_limit:10m;

server {
    # ...
    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;
        limit_conn conn_limit 10;
        # ... proxy_pass ...
    }
}
```

---

## 7. 知识库管理

### 7.1 导入文档

```bash
# 批量导入（整个目录）
python knowledge-base/scripts/batch_import.py --input-dir /path/to/docs

# 单目录导入
make kb-ingest

# 增量更新（仅处理变更文件）
python knowledge-base/scripts/update.py --docs-dir /path/to/docs
```

**支持的文档格式：** PDF, Word (.docx), TXT, Markdown (.md)

### 7.2 自定义行业词典

```bash
# 编辑术语词典（一行一个术语）
vim knowledge-base/dicts/energy_terms.txt

# 编辑同义词映射
vim knowledge-base/dicts/synonyms.yaml
```

同义词映射格式：
```yaml
服务器:
  - 主机
  - Server
  - 计算节点
防火墙:
  - 安全网关
  - Firewall
  - FW
```

### 7.3 API 操作

```bash
# 上传单文档
curl -X POST http://localhost:8000/api/v1/knowledge/upload \
  -F "file=@操作手册.pdf"

# 语义搜索
curl "http://localhost:8000/api/v1/knowledge/search?query=服务器维护&top_k=5"

# 查看知识库统计
curl http://localhost:8000/api/v1/knowledge/stats

# 删除文档
curl -X DELETE "http://localhost:8000/api/v1/knowledge/documents?doc_id=xxx"
```

---

## 8. 运维操作

### 8.1 日常巡检清单

```bash
# 1. GPU 状态
nvidia-smi --query-gpu=index,name,memory.used,memory.total,temperature.gpu \
    --format=csv,noheader

# 2. 服务健康
curl -s http://localhost:8000/api/v1/admin/health | python -m json.tool

# 3. 磁盘使用
df -h /mnt/d/Work/AI/AGIC/aigic/models
du -sh models/*/

# 4. 内存使用
free -h

# 5. 最近错误日志
docker compose logs --tail=50 2>&1 | grep -i "error\|exception\|traceback"
```

### 8.2 故障恢复

```bash
# ---- Docker 模式 ----

# 单个服务重启（服务配置了 restart: unless-stopped，通常自动恢复）
docker compose restart llm-service

# 查看容器退出原因
docker compose ps -a
docker inspect kb-llm --format='{{.State.ExitCode}} {{.State.Error}}'

# 进入容器排查
docker compose exec api-gateway bash

# 完全重建
make clean
make build
make start

# ---- 原生模式 ----

# 手动重启单个进程
pkill -f "llm-service"
bash services/llm-service/scripts/start_vllm.sh &

# 查看进程资源
htop -p $(pgrep -d',' -f "api-gateway\|llm-service")
```

### 8.3 性能监控

```bash
# GPU 实时监控
nvidia-smi -l 1                    # 每秒刷新
nvidia-smi dmon -s pucvmet         # GPU 详细指标

# Docker 容器资源
docker stats                        # 所有容器实时

# 原生进程资源
htop

# API 延迟监控
curl -w "@curl-format.txt" -o /dev/null -s \
  -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "服务器的巡检项目有哪些？"}'

# curl-format.txt:
#   time_namelookup:  %{time_namelookup}\n
#   time_connect:     %{time_connect}\n
#   time_starttransfer: %{time_starttransfer}\n
#   time_total:       %{time_total}\n

# 压测
make benchmark
```

### 8.4 日志管理

```bash
# Docker: 配置日志轮转（docker-compose.yml 中追加）
# services.xxx.logging:
#   driver: "json-file"
#   options:
#     max-size: "50m"
#     max-file: "5"

# 原生: logrotate 配置
# /etc/logrotate.d/kb-qa
# /tmp/*.log {
#     daily
#     rotate 7
#     compress
#     missingok
#     notifempty
# }
```

### 8.5 备份与恢复

```bash
# ---------- 备份 ----------
BACKUP_DIR="./backup/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# ChromeDB 向量数据（Docker）
docker run --rm \
  -v aigic_chroma-data:/data \
  -v "$BACKUP_DIR":/backup \
  alpine tar czf /backup/chroma-backup.tar.gz -C /data .

# ChromeDB 向量数据（原生）
tar czf "$BACKUP_DIR/chroma-backup.tar.gz" -C data chroma/

# Redis 数据（Docker）
docker compose exec redis redis-cli SAVE
docker cp kb-redis:/data/dump.rdb "$BACKUP_DIR/redis-dump.rdb"

# 环境配置
cp .env docker-compose.override.yml "$BACKUP_DIR/"
cp -r knowledge-base/dicts "$BACKUP_DIR/"

echo "备份完成: $BACKUP_DIR"

# ---------- 恢复 ----------
# ChromeDB
docker run --rm \
  -v aigic_chroma-data:/data \
  -v "$BACKUP_DIR":/backup \
  alpine tar xzf /backup/chroma-backup.tar.gz -C /data

# Redis
docker compose stop redis
docker cp "$BACKUP_DIR/redis-dump.rdb" kb-redis:/data/dump.rdb
docker compose start redis

# 重建知识库索引（根据需要）
make kb-ingest
```

### 8.6 扩容与缩容

```bash
# LLM 服务水平扩展（仅在不使用张量并行时）
# 修改 docker-compose.yml 或 override，增加副本：
# services.llm-service.deploy.replicas: 2

# 调整 LLM 并发数
# .env 中修改 LLM_MAX_CONCURRENT，重启：
docker compose restart llm-service

# API Gateway 多 Worker
# .env 中修改 API_GATEWAY_WORKERS，重启：
docker compose restart api-gateway
```

---

## 9. 安全加固清单

### 9.1 必须执行

- [ ] **修改 JWT 密钥**：`.env` 中 `JWT_SECRET_KEY` 改为随机字符串
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- [ ] **修改默认密码**：生产环境不要使用默认 `admin/admin`
- [ ] **设置 `ENVIRONMENT=production`**：启用鉴权中间件
- [ ] **配置防火墙**：仅开放 80/443 端口，8000/3000 仅本机访问
  ```bash
  sudo ufw allow 80/tcp
  sudo ufw allow 443/tcp
  sudo ufw deny 8000/tcp   # API 仅本机
  sudo ufw deny 3000/tcp   # 前端仅本机
  sudo ufw enable
  ```

### 9.2 强烈建议

- [ ] **配置 HTTPS**：Nginx + Let's Encrypt（见第 6 章）
- [ ] **Redis 密码**：`.env` 中 `REDIS_PASSWORD` 设强密码
- [ ] **定期备份**：配置 cron 自动备份（见 8.5 节）
- [ ] **日志审计**：接入 ELK/Loki 集中日志收集
- [ ] **GPU 监控告警**：nvidia-smi + Prometheus + Grafana，显存 >90% 或温度 >80°C 告警
- [ ] **容器安全扫描**：`docker scout quickview` 或 Trivy

### 9.3 企业环境

- [ ] **SSO/LDAP 对接**：替换默认用户名密码认证
- [ ] **API 限流**：Nginx `limit_req` 配置（见 6.3 节）
- [ ] **网络隔离**：API 网关和后端服务部署在不同安全组
- [ ] **数据脱敏**：日志中过滤敏感字段

---

## 10. 常见问题排查

### 10.1 启动失败

| 症状 | 可能原因 | 解决 |
|------|---------|------|
| `docker compose up` 报 GPU 不可用 | NVIDIA Container Toolkit 未安装 | `sudo apt install -y nvidia-container-toolkit && sudo systemctl restart docker` |
| LLM 服务启动超时 (>2min) | 模型未下载 | 检查 `models/gemma3/` 是否有文件，运行 `make download-models` |
| `could not select device driver` | GPU 驱动不兼容 | `nvidia-smi` 检查驱动，更新到 535+ |
| 端口冲突 | 8000/3000 等端口被占用 | `lsof -i :8000` 查占用进程 |
| 显存不足 (CUDA OOM) | 模型太大或并发太多 | 降低 `LLM_MAX_CONCURRENT`、`EMBEDDING_BATCH_SIZE` 或换用 single-gpu profile |

### 10.2 运行时问题

| 症状 | 可能原因 | 排查命令 |
|------|---------|---------|
| API 返回 500 | 后端服务不可达 | `curl http://localhost:8001/health` |
| 知识库搜索无结果 | ChromaDB 未初始化 | `curl http://localhost:8004/api/v1/heartbeat` |
| 语音识别超时 | ASR 服务 OOM | `nvidia-smi` 检查显存 |
| 对话历史丢失 | Redis 数据被清除 | `docker compose exec redis redis-cli DBSIZE` |
| 流式响应中断 | Nginx 缓冲未关闭 | 确认 `proxy_buffering off` |
| 检索结果不相关 | 文档未入库或分段不当 | 检查 `KNOWLEDGE_CHUNK_SIZE` 设置，重新入库 |

### 10.3 性能问题

| 症状 | 可能原因 | 优化方向 |
|------|---------|---------|
| LLM 推理慢 (>3s) | 并发过高 | 降低 `LLM_MAX_CONCURRENT` |
| 首次检索慢 | 模型冷启动 | 预热：发送一条测试查询 |
| 语音合成慢 | GPU 被 ASR 占用 | 调整 ASR+TTS 共享 GPU 的并发策略 |
| 前端加载慢 | Next.js 首次编译 | 生产模式用 `next build && next start` |

### 10.4 调试技巧

```bash
# 进入容器内部调试
docker compose exec api-gateway bash

# 查看实时资源
watch -n 1 nvidia-smi

# 测试单服务
curl -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gemma-3-27b-it", "messages": [{"role": "user", "content": "你好"}]}'

# 抓取完整请求链路
curl -v -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "测试", "stream": true}'

# 检查容器退出日志
docker inspect kb-llm --format='{{json .State}}' | python -m json.tool
```

---

## 11. Profile 参考手册

### 11.1 完整 Profile Schema

```yaml
# Profile 元信息
profile:
  name: my-profile          # 唯一标识（用于 --profile 参数）
  description: 我的配置      # 可读描述

# 部署模式
deployment:
  mode: docker              # docker | native

# GPU 硬件配置
gpus:
  count: 4                  # GPU 数量 (1-8)
  models:                   # GPU 型号列表
    - NVIDIA RTX 4090
  memory_per_gpu_gb: 24     # 单卡显存 (GB)

# 模型存储路径
models_dir: ./models

# 项目名称
project_name: kb-qa

# 各服务详细配置
services:
  llm:
    model: google/gemma-3-27b-it    # 模型名（HuggingFace 或本地路径）
    gpu_device: [0, 1]              # GPU 索引（单值如 0，或多卡如 [0, 1]）
    tensor_parallel_size: 2          # 张量并行 GPU 数
    quantization: awq               # awq | int4 | int8 | none
    context_window: 8192            # 上下文窗口 (tokens)
    max_num_seqs: 4                 # 最大并发序列数
    gpu_memory_utilization: 0.90    # GPU 显存利用率 (0.1-1.0)
    kv_cache_dtype: fp8             # KV Cache 数据类型（auto | fp8 | fp16）

  embedding:
    model: BAAI/bge-m3
    gpu_device: 2
    batch_size: 32                  # 批处理大小
    max_length: 8192                # 最大输入长度 (tokens)

  asr:
    model: large-v3                 # Whisper 模型大小
    gpu_device: 3
    vad_threshold: 0.5              # 语音活动检测阈值
    language: zh                    # 默认语言

  tts:
    model: CosyVoice2-0.5B
    gpu_device: 3
    default_voice: default          # 默认音色
    sample_rate: 24000              # 采样率 (Hz)
```

### 11.2 Profile 验证规则

Profile 加载时自动校验：

1. **GPU 索引范围**：所有 `gpu_device` 必须在 `[0, gpus.count-1]` 范围内
2. **张量并行匹配**：`tensor_parallel_size` 必须等于 `gpu_device` 分配的数量
3. **显存警告**：如果 4 个以上服务分配到同一 GPU，发出显存不足警告
4. **必需字段**：`profile.name`、`gpus.count`、`services.*.model`、`services.*.gpu_device` 为必填

---

## 12. 性能目标

| 环节 | 目标延迟 | 优化手段 |
|------|---------|---------|
| ASR 首字 | < 200ms | faster-whisper + VAD 过滤 |
| Embedding | < 50ms | GPU 批处理 |
| 向量检索 | < 100ms | HNSW 索引 + 缓存 |
| LLM 推理（首 token） | < 1.5s | TP=2, AWQ, KV Cache FP8 |
| TTS 首包 | < 300ms | 流式分句合成 |
| 文本问答 E2E | < 3s | 检索缓存 + 并发控制 |
| 语音问答 E2E | < 5s | 全链路异步流水线 |

---

## 13. 附录：Makefile 命令速查

| 命令 | 说明 |
|------|------|
| `make config` | 从 profile 生成 .env + docker override |
| `make config-list` | 列出可用 profile |
| `make build` | 构建所有 Docker 镜像 |
| `make start` | 启动所有 Docker 服务 |
| `make stop` | 停止所有 Docker 服务 |
| `make restart` | 重启所有 Docker 服务 |
| `make start-core` | 仅启动核心服务（Redis + Chroma + LLM + Embedding） |
| `make start-voice` | 仅启动语音服务（ASR + TTS） |
| `make start-api` | 仅启动 API + RAG + 前端 |
| `make logs` | 查看全部日志 |
| `make status` | 查看容器状态 |
| `make health` | 运行 Docker 健康检查 |
| `make clean` | 停止并删除容器/卷 |
| `make download-models` | 下载全部模型 |
| `make kb-ingest` | 导入示例知识库文档 |
| `make test` | 运行全部测试 |
| `make benchmark` | 运行性能压测 |
| `make native-start` | 原生模式启动全部服务 |
| `make native-stop` | 原生模式停止全部服务 |
| `make native-status` | 原生模式进程状态 |
| `make native-health` | 原生模式健康检查 |
