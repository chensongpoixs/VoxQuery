# 部署运维手册

## 1. 环境要求

### 1.1 硬件
- 4×NVIDIA RTX 4090 (24GB)
- CPU: 16核+
- 内存: 64GB+
- 磁盘: 200GB+（含模型文件 ~80GB）

### 1.2 软件
- Ubuntu 22.04 LTS
- NVIDIA Driver 535+
- Docker 24+
- Docker Compose 2.20+
- CUDA 12.4
- NVIDIA Container Toolkit

### 1.3 环境检查
```bash
# 检查 GPU
nvidia-smi
# 检查 Docker GPU 支持
docker run --rm --gpus all nvidia/cuda:12.4.0-runtime-ubuntu22.04 nvidia-smi
```

## 2. 快速部署

### 2.1 一键部署
```bash
cd aigic
bash scripts/setup.sh all
```

此命令会依次：
1. 检查系统依赖
2. 创建 .env 配置文件
3. 构建所有服务镜像
4. 启动所有服务
5. 导入示例数据

### 2.2 分步部署
```bash
# Step 1: 环境初始化
make setup
make init-dirs

# Step 2: 下载模型（需 HuggingFace Token）
export HF_TOKEN=your_token_here
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

### 2.3 检查状态
```bash
make status      # 查看容器状态
make health      # 运行健康检查
make logs        # 查看日志
```

## 3. 配置说明

### 3.1 关键环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_MODEL_NAME` | google/gemma-3-27b-it | LLM 模型 |
| `LLM_CONTEXT_WINDOW` | 8192 | 上下文窗口（受显存限制） |
| `LLM_MAX_CONCURRENT` | 4 | 最大并发推理数 |
| `EMBEDDING_BATCH_SIZE` | 32 | 批量向量化大小 |
| `RAG_TOP_K` | 5 | 检索召回数 |
| `RAG_SIMILARITY_THRESHOLD` | 0.65 | 相似度阈值 |
| `KNOWLEDGE_CHUNK_SIZE` | 512 | 文档分段大小 |
| `CONVERSATION_TTL` | 86400 | 对话历史 TTL（秒） |

### 3.2 GPU 分配修改
如需调整 GPU 分配，修改 `.env`：
```bash
NVIDIA_VISIBLE_DEVICES_LLM=0,1
NVIDIA_VISIBLE_DEVICES_EMBEDDING=2
NVIDIA_VISIBLE_DEVICES_ASR_TTS=3
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
编辑 `knowledge-base/dicts/energy_terms.txt` 添加行业术语。
编辑 `knowledge-base/dicts/synonyms.yaml` 添加同义词映射。

## 5. 运维操作

### 5.1 常用命令
```bash
make logs-llm          # 查看 LLM 服务日志
make restart-api       # 重启 API Gateway
make build-rag         # 重新构建 RAG 服务
docker compose exec api-gateway bash  # 进入 API 容器
```

### 5.2 故障恢复
```bash
# 服务异常自动重启（已配置 restart: unless-stopped）
# 手动重启单个服务
docker compose restart llm-service

# 完全重建
make clean
make build
make start
```

### 5.3 性能监控
```bash
# 查看 GPU 使用
nvidia-smi -l 1

# 查看容器资源
docker stats

# 运行压测
make benchmark
```

### 5.4 备份
```bash
# 备份 ChromaDB 数据
docker run --rm -v aigic_chroma-data:/data -v $(pwd)/backup:/backup \
  alpine tar czf /backup/chroma-backup.tar.gz -C /data .

# 备份 Redis 数据
docker compose exec redis redis-cli SAVE
```

## 6. 生产环境注意事项

1. **修改默认密码**：`.env` 中的 `JWT_SECRET_KEY` 和 Redis 密码
2. **启用鉴权**：设置 `ENVIRONMENT=production`
3. **配置 HTTPS**：前置 Nginx 反向代理
4. **日志收集**：配置 Docker 日志驱动或 ELK
5. **监控告警**：配置 GPU 显存、温度监控
6. **定期备份**：ChromaDB 和 Redis 数据
