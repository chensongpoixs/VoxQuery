# 部署运维手册

## 1. 环境要求

### 1.1 硬件

| Profile | GPU | 显存 | 用途 |
|---------|-----|------|------|
| `multi-gpu` | 4×NVIDIA RTX 4090 (24GB) | 96GB 总 | 生产环境，分布式推理 |
| `single-gpu` | 1×NVIDIA RTX 5080 (24GB) | 24GB | 开发测试环境，全模型单卡运行 |

通用要求：CPU 16核+ / 内存 64GB+ / 磁盘 200GB+

### 1.2 软件
- Ubuntu 22.04 LTS
- NVIDIA Driver 535+ + CUDA 12.4
- Docker 24+ + Docker Compose 2.20+ (Docker 模式)
- Python 3.11+ (原生模式)
- NVIDIA Container Toolkit (Docker 模式)

### 1.3 环境检查
```bash
# 检查 GPU
nvidia-smi
# 检查 Docker GPU 支持
docker run --rm --gpus all nvidia/cuda:12.4.0-runtime-ubuntu22.04 nvidia-smi
```

## 2. 快速部署

### 2.1 Profile 配置

项目采用 **Profile 驱动的配置系统**，所有部署参数从 YAML profile 文件集中管理。

```bash
# 查看可用 profile
make config-list

# 输出:
#   可用的硬件 Profile:
#     multi-gpu             — 4×RTX 4090 (24GB×4) 分布式部署
#       GPU: 4×NVIDIA RTX 4090, LLM: google/gemma-3-27b-it
#     single-gpu            — 单张 RTX 5080 (24GB) 部署全部模型
#       GPU: 1×NVIDIA RTX 5080, LLM: google/gemma-4-e2b-it
```

### 2.2 一键部署 (Docker)

```bash
cd aigic

# 1. 生成部署配置（multi-gpu profile + docker 模式）
make config

# 或指定 profile:
python configs/generate_config.py --profile single-gpu --mode docker --force

# 2. 下载模型
make download-models

# 3. 构建并启动
make build
make start

# 4. 导入示例数据
make kb-ingest
```

### 2.3 分步部署 (Docker)
```bash
# Step 1: 生成配置
python configs/generate_config.py --profile multi-gpu --mode docker --force

# Step 2: 下载模型
make download-models

# Step 3: 构建镜像
make build

# Step 4: 分阶段启动
make start-core     # Redis + ChromaDB + LLM + Embedding
# 等待 LLM 服务就绪（约 2 分钟）
make start-voice    # ASR + TTS
make start-api      # RAG + API Gateway + Frontend

# Step 5: 导入知识库
make kb-ingest
```

### 2.4 原生部署 (Bare Metal)

无需 Docker，直接通过进程管理运行所有服务。

```bash
cd aigic

# 1. 生成原生部署配置
python configs/generate_config.py --profile multi-gpu --mode native --force

# 2. 下载模型
make download-models

# 3. 一键启动
make native-start

# 或者分阶段启动:
make native-start-core    # 基础设施 + LLM + Embedding
make native-start-voice   # ASR + TTS
make native-start-api     # RAG + API Gateway + Frontend

# 4. 检查状态
make native-status
make native-health
```

### 2.5 检查状态
```bash
make status       # Docker 容器状态
make health       # Docker 健康检查
make native-status   # 原生模式进程状态
make native-health   # 原生模式健康检查
```

## 3. 配置说明

### 3.1 Profile 系统

Profile 是部署配置的**唯一真实来源**。`configs/profiles/<name>.yaml` 定义：

- GPU 硬件规格（数量、型号、显存）
- 每个服务的模型选型和 GPU 分配
- 推理参数（张量并行、量化、上下文窗口等）

运行 `make config` 从 profile 自动生成：
- `.env` — 环境变量文件
- `docker-compose.override.yml` — Docker GPU 绑定配置
- `supervisord.conf` — 原生部署进程管理配置

### 3.2 关键环境变量

`.env` 文件由 profile 自动生成，关键变量包括：

| 变量 | 说明 | Profile 来源 |
|------|------|-------------|
| `DEPLOYMENT_MODE` | 部署模式 (docker/native) | deployment.mode |
| `HARDWARE_PROFILE` | 硬件配置名称 | profile.name |
| `LLM_MODEL_NAME` | LLM 模型 | services.llm.model |
| `LLM_TENSOR_PARALLEL_SIZE` | 张量并行 GPU 数 | services.llm.tensor_parallel_size |
| `LLM_QUANTIZATION` | 量化方式 | services.llm.quantization |
| `LLM_CONTEXT_WINDOW` | 上下文窗口 | services.llm.context_window |
| `NVIDIA_VISIBLE_DEVICES_LLM` | LLM GPU 设备 | services.llm.gpu_device |
| `EMBEDDING_MODEL_NAME` | Embedding 模型 | services.embedding.model |
| `NVIDIA_VISIBLE_DEVICES_EMBEDDING` | Embedding GPU | services.embedding.gpu_device |
| `NVIDIA_VISIBLE_DEVICES_ASR_TTS` | 语音 GPU | services.tts.gpu_device |
| `RAG_TOP_K` | 检索召回数 | 默认 5 |
| `RAG_SIMILARITY_THRESHOLD` | 相似度阈值 | 默认 0.65 |

### 3.3 Profile 切换

```bash
# 切换到单卡配置
python configs/generate_config.py --profile single-gpu --mode docker --force

# 切换回多卡配置
python configs/generate_config.py --profile multi-gpu --mode docker --force
```

### 3.4 自定义 Profile

创建 `configs/profiles/custom.yaml`：

```yaml
profile:
  name: custom
  description: 自定义配置

deployment:
  mode: docker

gpus:
  count: 2
  models: [NVIDIA RTX 4090, NVIDIA RTX 4090]
  memory_per_gpu_gb: 24

services:
  llm:
    model: google/gemma-3-27b-it
    gpu_device: [0, 1]
    tensor_parallel_size: 2
    quantization: awq
    context_window: 8192
    max_num_seqs: 4
    gpu_memory_utilization: 0.90
    kv_cache_dtype: fp8

  embedding:
    model: BAAI/bge-m3
    gpu_device: 0
    batch_size: 32
    max_length: 8192

  asr:
    model: large-v3
    gpu_device: 0
    vad_threshold: 0.5
    language: zh

  tts:
    model: CosyVoice2-0.5B
    gpu_device: 0
    default_voice: default
    sample_rate: 24000
```

使用自定义 profile：
```bash
python configs/generate_config.py --profile custom --force
```

## 4. 知识库管理

### 4.1 导入文档
```bash
# 批量导入
python knowledge-base/scripts/batch_import.py --input-dir /path/to/docs

# 单文件导入
python knowledge-base/scripts/ingest.py --docs-dir /path/to/doc

# 增量更新
python knowledge-base/scripts/update.py --docs-dir /path/to/docs
```

### 4.2 自定义行业词典
编辑 `knowledge-base/dicts/` 目录下的术语文件和同义词映射。

## 5. 运维操作

### 5.1 Docker 模式
```bash
make logs-llm          # 查看 LLM 服务日志
make restart-api       # 重启 API Gateway
make build-rag         # 重新构建 RAG 服务
docker compose exec api-gateway bash  # 进入 API 容器
```

### 5.2 原生模式
```bash
make native-logs       # 查看所有服务日志
make native-status     # 查看进程状态
bash scripts/native/health_check.sh  # 健康检查
bash scripts/native/stop_all.sh      # 停止所有服务
```

### 5.3 故障恢复
```bash
# Docker 模式 - 服务异常自动重启（已配置 restart: unless-stopped）
docker compose restart llm-service

# 原生模式 - 手动重启单个进程
pkill -f "llm-service" && bash services/llm-service/scripts/start_vllm.sh &

# 完全重建
make clean && make build && make start
```

### 5.4 性能监控
```bash
# 查看 GPU 使用
nvidia-smi -l 1

# Docker 容器资源
docker stats

# 原生模式进程资源
htop -p $(pgrep -d',' -f "api-gateway|llm-service")

# 运行压测
make benchmark
```

### 5.5 备份
```bash
# Docker 模式: 备份 ChromaDB 数据
docker run --rm -v aigic_chroma-data:/data -v $(pwd)/backup:/backup \
  alpine tar czf /backup/chroma-backup.tar.gz -C /data .

# Docker 模式: 备份 Redis 数据
docker compose exec redis redis-cli SAVE

# 原生模式: 直接备份数据目录
tar czf backup/chroma-backup.tar.gz -C data chroma/
```

## 6. 模型下载

```bash
# 根据 profile 下载全部模型
make download-models

# 或指定 profile:
bash scripts/download_models.sh --profile single-gpu all   # ~9GB
bash scripts/download_models.sh --profile multi-gpu all    # ~57GB

# 单独下载
make download-model-llm        # LLM
make download-model-embedding   # Embedding
make download-model-whisper     # ASR
make download-model-tts         # TTS
```

| Profile | LLM 模型 | 大小 |
|---------|---------|------|
| `single-gpu` | Gemma-4 E2B (INT4) | ~2GB |
| `multi-gpu` | Gemma-3 27B (AWQ) | ~50GB |

## 7. 生产环境注意事项

1. **修改默认密码**：`.env` 中的 `JWT_SECRET_KEY` 和 Redis 密码
2. **启用鉴权**：设置 `ENVIRONMENT=production`
3. **配置 HTTPS**：前置 Nginx 反向代理
4. **日志收集**：配置 Docker 日志驱动或 ELK
5. **监控告警**：配置 GPU 显存、温度监控
6. **定期备份**：ChromaDB 和 Redis 数据
7. **原生模式用 supervisord**：生产环境建议安装 supervisord 管理进程生命周期
   ```bash
   sudo apt install supervisor
   sudo cp supervisord.conf /etc/supervisor/conf.d/kb-qa.conf
   sudo supervisorctl reread && sudo supervisorctl update
   ```
