# API 接口规范

## 基础信息

- Base URL: `http://localhost:8000`
- 文档: `http://localhost:8000/docs` (Swagger UI)
- 鉴权: Bearer Token (开发环境跳过)
- Content-Type: `application/json`

## 1. 对话接口

### 1.1 文本对话（非流式）

```
POST /api/v1/chat
```

**请求体:**
```json
{
  "message": "变压器的日常巡检项目有哪些？",
  "conversation_id": null,
  "use_rag": true,
  "stream": false
}
```

**响应:**
```json
{
  "id": "uuid",
  "message": "日常巡检包括：\n1. 油温检查...",
  "conversation_id": "abc123def456",
  "sources": [
    {
      "text": "文档片段...",
      "score": 0.95,
      "source": "变压器维护手册.md"
    }
  ],
  "is_fallback": false,
  "timestamp": "2024-01-01T00:00:00"
}
```

### 1.2 文本对话（流式 SSE）

```
POST /api/v1/chat/stream
```

请求体同上，响应为 SSE 事件流：
```
data: {"token": "日常", "conv_id": "abc123"}
data: {"token": "巡检", "conv_id": "abc123"}
data: {"token": "", "conv_id": "abc123", "done": true, "sources": [...]}
```

### 1.3 对话历史

```
GET /api/v1/conversations
GET /api/v1/conversations/{conv_id}
DELETE /api/v1/conversations/{conv_id}
```

## 2. 语音接口

### 2.1 语音对话

```
POST /api/v1/voice/chat
Content-Type: multipart/form-data

audio: <音频文件>
voice_id: "default"
conversation_id: "abc123"
```

返回: `audio/wav` 音频文件

### 2.2 语音识别

```
POST /api/v1/voice/transcribe
Content-Type: multipart/form-data

audio: <音频文件>
language: "zh" (可选)
```

**响应:**
```json
{
  "text": "变压器的巡检项目有哪些",
  "language": "zh",
  "segments": [{"start": 0.0, "end": 2.5, "text": "..."}],
  "duration_seconds": 2.5
}
```

### 2.3 语音合成

```
POST /api/v1/voice/synthesize

text: "回答文本"
voice_id: "default"
speed: 1.0
```

返回: `audio/wav` 音频文件

### 2.4 音色列表

```
GET /api/v1/voice/voices
```

### 2.5 音色克隆

```
POST /api/v1/voice/clone
Content-Type: multipart/form-data

audio: <参考音频>
voice_name: "我的音色"
```

## 3. 知识库接口

### 3.1 语义搜索

```
POST /api/v1/knowledge/search

query: "变压器维护"
top_k: 5
```

### 3.2 文档上传

```
POST /api/v1/knowledge/upload
Content-Type: multipart/form-data

file: <文档文件 (.txt/.md/.pdf/.docx)>
strategy: "sliding_window"
```

### 3.3 批量导入

```
POST /api/v1/knowledge/import-directory

directory: "/app/knowledge-base/sample-docs"
strategy: "sliding_window"
```

### 3.4 文档删除

```
DELETE /api/v1/knowledge/documents/{doc_id}
```

### 3.5 知识库统计

```
GET /api/v1/knowledge/stats
```

## 4. 管理接口

### 4.1 全局健康检查

```
GET /api/v1/admin/health
```

**响应:**
```json
{
  "status": "healthy",
  "services": {
    "api_gateway": "healthy",
    "llm_service": "healthy",
    "rag_service": "healthy",
    "asr_service": "healthy",
    "tts_service": "healthy"
  },
  "version": "1.0.0"
}
```

### 4.2 获取 Token

```
POST /api/v1/admin/auth/token

username: "admin"
password: "admin"
```

## 5. 错误码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |
| 503 | 下游服务不可用 |
