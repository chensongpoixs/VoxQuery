# 系统架构设计文档

## 1. 概述

能源行业内部知识库问答系统 + 语音对话助手，采用 ASR → LLM+RAG → TTS 三阶段流水线架构。

### 1.1 设计原则
- **数据不出企业**：完全私有化部署，所有数据、模型都在企业内部服务器
- **模块解耦**：各服务独立部署、独立扩容
- **GPU 资源高效利用**：4×RTX 4090 精确分配
- **故障隔离**：单服务故障不影响整体可用性

### 1.2 技术栈

| 层次 | 技术选型 | 说明 |
|------|---------|------|
| 语音识别 | Whisper-large-v3 | OpenAI 开源，中英混合，流式解码 |
| 语言模型 | Gemma-3 27B + vLLM | Google 开源，2×GPU 张量并行 |
| 向量化 | BGE-M3 | BAAI 开源，8192 token |
| 向量数据库 | ChromaDB | 轻量级，适合私有化 |
| 语音合成 | CosyVoice2 | 阿里通义开源，零样本克隆 |
| API 网关 | FastAPI | 异步高性能 Python 框架 |
| 前端 | Next.js 14 | React 服务端组件 |
| 容器编排 | Docker Compose | GPU 绑定，服务互联 |
| 缓存 | Redis | 对话历史 + 检索缓存 |

## 2. 系统架构

### 2.1 整体架构图

```
┌──────────────────────────────────────────────┐
│                用户交互层                      │
│    Web UI (Next.js) │ API (第三方集成)        │
└────────────────────┬─────────────────────────┘
                     │ HTTP/WebSocket/SSE
┌────────────────────▼─────────────────────────┐
│              API Gateway (FastAPI)            │
│  • 对话管理  • 路由调度  • 流式响应  • 鉴权    │
└──┬────────┬────────┬────────┬────────────────┘
   │        │        │        │
┌──▼──┐ ┌──▼──┐ ┌──▼──┐ ┌──▼──┐
│ ASR │ │ RAG │ │ LLM │ │ TTS │
│GPU:3│ │     │ │GPU: │ │GPU:3│
│     │ │     │ │0,1  │ │     │
└─────┘ └──┬──┘ └─────┘ └─────┘
           │
  ┌────────▼────────┐  ┌────────────────┐
  │ ChromaDB        │  │ BGE-M3 (GPU:2) │
  │ (Vector Store)  │  │ (Embedding)    │
  └─────────────────┘  └────────────────┘
```

### 2.2 GPU 分配方案

| GPU | 服务 | 模型 | 显存占用 |
|-----|------|------|---------|
| GPU 0,1 | LLM Service | Gemma-3 27B (TP=2) | ~22GB × 2 |
| GPU 2 | Embedding Service | BGE-M3 | ~6GB |
| GPU 3 | ASR + TTS | Whisper-v3 + CosyVoice2 | ~4GB + ~4GB |

## 3. 数据流

### 3.1 文本对话流程

```
用户输入文本
  → API Gateway 接收
  → ConversationManager 指代消解
  → RAG Service 语义检索
    → Embedding Service 向量化查询
    → ChromaDB 向量相似度搜索
    → Re-ranker 精排
    → 返回 Top-K 文档片段
  → LLM Service 推理生成
    → System Prompt + 历史 + 文档上下文 + 用户问题
    → Gemma-3 27B 生成回答
  → 流式返回（SSE）逐字展示
  → 保存对话历史到 Redis
```

### 3.2 语音对话流程

```
音频输入（Web/移动端）
  → ASR Service (Whisper-large-v3)
    → 语音活动检测 (VAD)
    → 流式转录
  → 文本（同文本对话流程）
  → TTS Service (CosyVoice2)
    → 文字转语音
    → 返回音频流
  → 音频播放
```

## 4. 服务接口

### 4.1 API Gateway (Port 8000)
- `POST /api/v1/chat` - 文本对话（非流式）
- `POST /api/v1/chat/stream` - 文本对话（SSE 流式）
- `POST /api/v1/voice/chat` - 语音对话
- `POST /api/v1/voice/transcribe` - 仅语音识别
- `POST /api/v1/voice/synthesize` - 仅语音合成
- `POST /api/v1/knowledge/search` - 知识库搜索
- `POST /api/v1/knowledge/upload` - 文档上传
- `GET /api/v1/conversations` - 对话列表
- `GET /api/v1/admin/health` - 全局健康检查

### 4.2 LLM Service (Port 8001)
- `POST /v1/chat/completions` - OpenAI 兼容推理
- `GET /health` - 健康检查

### 4.3 Embedding Service (Port 8002)
- `POST /v1/embeddings` - 文本向量化
- `GET /health` - 健康检查

### 4.4 RAG Service (Port 8003)
- `POST /search` - 语义检索
- `POST /ingest` - 文档入库
- `POST /delete` - 文档删除
- `GET /collection/stats` - 统计信息

### 4.5 ASR Service (Port 8005)
- `POST /v1/transcribe` - 音频转录
- `WS /ws/transcribe` - 流式转录

### 4.6 TTS Service (Port 8006)
- `POST /v1/tts` - 语音合成
- `POST /v1/tts/stream` - 流式合成
- `POST /v1/voice/clone` - 音色克隆

## 5. 部署架构

```
Server (4×RTX 4090)
├── Docker Engine
│   ├── redis (内存缓存)
│   ├── chromadb (向量存储)
│   ├── llm-service (GPU 0,1)
│   ├── embedding-service (GPU 2)
│   ├── asr-service (GPU 3)
│   ├── tts-service (GPU 3)
│   ├── rag-service
│   ├── api-gateway
│   └── frontend
```

所有服务通过 `energy-net` Docker 网络通信，外部仅暴露 API Gateway (8000) 和前端 (3000)。
