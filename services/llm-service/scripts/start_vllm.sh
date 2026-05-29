#!/bin/bash
# ============================================================
# vLLM 推理服务启动脚本
# Gemma-3 27B + 2×RTX 4090 张量并行 + INT8 量化
# ============================================================
set -e

# 国内环境自动配置 HuggingFace 镜像
if [ -z "$HF_ENDPOINT" ]; then
    export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
fi
echo "[INFO] HF_ENDPOINT=$HF_ENDPOINT"

MODEL_NAME="${MODEL_NAME:-google/gemma-3-27b-it}"
MODEL_PATH="${MODEL_PATH:-/models/gemma3}"
TENSOR_PARALLEL_SIZE="${TENSOR_PARALLEL_SIZE:-2}"
MAX_TOKENS="${MAX_TOKENS:-2048}"
QUANTIZATION="${QUANTIZATION:-awq}"
MAX_CONCURRENT="${MAX_CONCURRENT:-4}"
GPU_MEMORY_UTIL="${GPU_MEMORY_UTILIZATION:-0.90}"
CONTEXT_WINDOW="${CONTEXT_WINDOW:-8192}"
KV_CACHE_DTYPE="${KV_CACHE_DTYPE:-fp8}"
PORT="${PORT:-8001}"
MAX_NUM_SEQS="${MAX_NUM_SEQS:-4}"

# 检查模型文件
if [ -d "$MODEL_PATH" ] && [ -n "$(ls -A "$MODEL_PATH" 2>/dev/null)" ]; then
    echo "[INFO] 使用本地模型: $MODEL_PATH"
    MODEL_SOURCE="$MODEL_PATH"
else
    echo "[INFO] 本地模型不存在，将从 HuggingFace 下载: $MODEL_NAME"
    MODEL_SOURCE="$MODEL_NAME"
fi

echo "============================================"
echo " vLLM 推理服务启动参数"
echo "============================================"
echo "  模型:           $MODEL_SOURCE"
echo "  张量并行:       $TENSOR_PARALLEL_SIZE GPU"
echo "  量化:           $QUANTIZATION"
echo "  上下文窗口:     $CONTEXT_WINDOW tokens"
echo "  最大输出:       $MAX_TOKENS tokens"
echo "  最大并发:       $MAX_CONCURRENT"
echo "  KV Cache:       $KV_CACHE_DTYPE"
echo "  GPU 内存利用率: $GPU_MEMORY_UTIL"
echo "  HTTP 端口:      $PORT"
echo "============================================"

# 启动 vLLM OpenAI-compatible API Server
exec python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_SOURCE" \
    --tensor-parallel-size "$TENSOR_PARALLEL_SIZE" \
    --quantization "$QUANTIZATION" \
    --max-model-len "$CONTEXT_WINDOW" \
    --max-num-seqs "$MAX_NUM_SEQS" \
    --gpu-memory-utilization "$GPU_MEMORY_UTIL" \
    --kv-cache-dtype "$KV_CACHE_DTYPE" \
    --served-model-name "$(basename $MODEL_NAME)" \
    --host 0.0.0.0 \
    --port "$PORT" \
    --trust-remote-code \
    --enforce-eager
