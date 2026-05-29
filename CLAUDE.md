# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

VoxQuery 是面向企业的**内部知识库问答系统 + 语音对话助手**，采用 ASR → LLM+RAG → TTS 三阶段流水线架构，完全私有化部署。支持两种硬件 profile：单卡 RTX 5080 (single-gpu) 和 4×RTX 4090 (multi-gpu)。

## 常用命令

### 配置生成（必须先执行）

```bash
make config              # 使用默认 profile (multi-gpu / docker) 生成 .env + docker-compose.override.yml
make config-list         # 列出所有可用 profile
make config-single       # 单卡 Docker 部署
make config-native       # 多卡原生部署
```

### Docker 部署

```bash
make build               # 构建所有镜像
make build-no-cache      # 无缓存构建
make start               # 启动所有服务
make stop                # 停止所有服务
make restart             # 重启所有服务
make start-core          # 启动核心服务 (Redis + ChromaDB + LLM + Embedding)
make start-voice         # 启动语音服务 (ASR + TTS)
make start-api           # 启动 API Gateway + RAG + Frontend
make logs                # 查看所有服务日志
make logs-api            # 查看 API Gateway 日志
make status              # 查看服务运行状态
make health              # 健康检查
make clean               # 停止并清理容器、卷
make clean-models        # 清理模型文件
```

### 原生部署 (Bare Metal)

```bash
make native-start        # 启动所有原生服务（通过 supervisord）
make native-start-core   # 原生启动核心服务
make native-start-voice  # 原生启动语音服务
make native-start-api    # 原生启动 API + 前端
make native-stop         # 停止所有原生服务
make native-status       # 查看原生服务状态
make native-health       # 原生健康检查
make native-logs         # 查看原生模式日志
```

### 开发

```bash
make dev-api             # 开发模式启动 API Gateway (uvicorn --reload)
make dev-frontend        # 开发模式启动前端 (npm run dev)
make lint                # 代码检查 (flake8)
make format              # 代码格式化 (black)
make kb-ingest           # 导入示例文档到知识库
make kb-update           # 增量更新知识库
```

### 测试

```bash
make test                # 运行所有测试 (pytest -v)
make test-api            # 仅 API 测试
make test-rag            # 仅 RAG 测试
make test-unit           # 仅单元测试
make benchmark           # 性能压测
```

### 模型下载（国内镜像）

```bash
make detect-mirror       # 检测最佳镜像源
make download-models     # 下载所有模型 (~57GB multi-gpu / ~9GB single-gpu)
make download-model-llm  # 仅下载 LLM 模型
```

## 架构

### 微服务拓扑

```
Frontend (Next.js :3000)
    ↓
API Gateway (FastAPI :8000)  ← 核心入口，对话路由/SSE流式/指代消解/鉴权
    ↓ ↓ ↓ ↓ ↓
    │ │ │ │ └→ TTS Service (:8006) — CosyVoice2, GPU:3
    │ │ │ └──→ ASR Service (:8005) — Whisper-large-v3, GPU:3
    │ │ └───→ RAG Service (:8003) — 检索+重排序
    │ │           ↓
    │ │       Embedding Service (:8002) — BGE-M3, GPU:2
    │ │           ↓
    │ │       ChromaDB (:8004) — 向量存储
    │ └────→ LLM Service (:8001) — Gemma-3 27B, vLLM, GPU:0,1 (TP=2)
    └─────→ Redis (:6379) — 对话历史 + 检索缓存
```

- 所有微服务通过 `kb-net` Docker bridge 网络通信
- GPU 设备绑定通过 `docker-compose.override.yml` 注入（由 `make config` 自动生成）
- 外部仅暴露端口 8000 (API) 和 3000 (Frontend)

### 配置系统

`configs/` 目录是部署配置的核心：

1. **`configs/profiles/*.yaml`** — 硬件配置声明（GPU 数量、模型名、显存分配）
2. **`configs/profile_schema.py`** — Pydantic 数据模型，包含交叉验证（GPU index 范围、TP 尺寸匹配、共享 GPU 显存警告）
3. **`configs/profile_loader.py`** — 配置生成引擎，从 YAML profile 生成：
   - `.env` — 环境变量
   - `docker-compose.override.yml` — GPU 绑定
   - `supervisord.conf` — 原生部署进程管理
4. **`configs/generate_config.py`** — CLI 入口工具

环境变量命名规范：服务配置使用 `{SERVICE}_{PARAM}` 前缀（如 `LLM_TENSOR_PARALLEL_SIZE`），GPU 分配使用 `NVIDIA_VISIBLE_DEVICES_{SERVICE}`。

### API Gateway 内部结构 (`services/api-gateway/app/`)

| 路径 | 职责 |
|------|------|
| `main.py` | FastAPI 应用工厂，lifespan 管理服务客户端生命周期 |
| `routers/chat.py` | `/api/v1/chat`, `/api/v1/chat/stream` — 文本对话（含 System Prompt 定义） |
| `routers/voice.py` | `/api/v1/voice/*` — 语音对话/识别/合成 |
| `routers/knowledge.py` | `/api/v1/knowledge/*` — 知识库搜索/上传 |
| `routers/admin.py` | `/api/v1/admin/*` — 健康检查 + JWT 认证 |
| `services/llm_client.py` | LLM 微服务 HTTP 客户端 |
| `services/rag_client.py` | RAG 微服务 HTTP 客户端 |
| `services/conversation.py` | 对话管理器（多轮历史、指代消解，基于 Redis） |
| `services/asr_client.py` | ASR 微服务 HTTP 客户端 |
| `services/tts_client.py` | TTS 微服务 HTTP 客户端 |
| `models/chat.py` | Pydantic 请求/响应模型 |
| `middleware/` | 鉴权 + 请求日志中间件 |

### 数据流（文本问答）

```
用户输入 → ConversationManager 指代消解 → RAG 语义检索
  → Embedding 向量化 → ChromaDB 相似度搜索 → Re-ranker 精排
  → LLM 推理（System Prompt + 历史 + 上下文 + 问题）
  → SSE 流式返回 → 对话历史存入 Redis
```

注意：System Prompt 定义在 `routers/chat.py` 中（`SYSTEM_PROMPT` 常量），而非外部配置文件。

### 知识库系统

- 自定义词典：`knowledge-base/dicts/energy_terms.txt`（行业术语）和 `synonyms.yaml`（同义词映射）
- 文档分块参数由环境变量控制：`KNOWLEDGE_CHUNK_SIZE=512`, `KNOWLEDGE_CHUNK_OVERLAP=50`
- RAG 检索参数：`TOP_K=5`, `RERANK_TOP_N=3`, `SIMILARITY_THRESHOLD=0.65`

### 前端 (`frontend/`)

Next.js 14 + React 18 + Tailwind CSS 3 + lucide-react。组件组织在 `src/components/` 下（Chat, Knowledge, Layout, Voice 目录），API 客户端在 `src/lib/` 中。

### 测试 (`tests/`)

pytest + 共享 fixtures（`conftest.py` 提供 `sample_documents` 和 `sample_queries`）。测试覆盖 RAG 流程和 API Gateway。

## 关键约定

- Python 代码使用 `black` 格式化、`flake8` 检查
- 部署前必须运行 `make config` 生成 `.env` 和 `docker-compose.override.yml`，这两个文件由 profile 系统自动生成，**不可手动编辑**
- 模型文件存放于 `models/` 目录（已在 `.gitignore` 中排除）
- 数据持久化：ChromaDB 卷 (`chroma-data`) + Redis 卷 (`redis-data`)
- 服务间调用均通过 HTTP（非 gRPC），SSE 用于流式响应
- 鉴权：Bearer JWT Token，开发环境默认跳过，生产环境通过 `ENVIRONMENT=production` 启用
