#!/bin/bash
set -e

# 国内环境自动配置 HuggingFace 镜像
if [ -z "$HF_ENDPOINT" ]; then
    export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
fi
echo "[INFO] HF_ENDPOINT=$HF_ENDPOINT"

# 自动加载项目根目录的 .env 文件（如果存在）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a; source "$PROJECT_ROOT/.env"; set +a
fi

MODEL_NAME="${MODEL_NAME:-${EMBEDDING_MODEL_NAME:-BAAI/bge-m3}}"
PORT="${PORT:-8002}"
BATCH_SIZE="${BATCH_SIZE:-${EMBEDDING_BATCH_SIZE:-32}}"
MAX_LENGTH="${MAX_LENGTH:-${EMBEDDING_MAX_LENGTH:-8192}}"

echo "============================================"
echo " BGE-M3 Embedding Service"
echo "============================================"
echo "  模型:       $MODEL_NAME"
echo "  端口:       $PORT"
echo "  批处理大小: $BATCH_SIZE"
echo "  最大长度:   $MAX_LENGTH"
echo "============================================"

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --workers 1 \
    --log-level info
