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

# 支持两种变量名风格:
#   - Docker Compose 映射后的短名 (如 TENSOR_PARALLEL_SIZE)
#   - .env 文件中的 LLM_* 前缀名 (如 LLM_TENSOR_PARALLEL_SIZE)
# 自动加载项目根目录的 .env 文件（如果存在）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a; source "$PROJECT_ROOT/.env"; set +a
fi

MODEL_NAME="${MODEL_NAME:-${LLM_MODEL_NAME:-google/gemma-3-27b-it}}"
# Docker 容器内路径 /models/gemma3，原生运行时 $PROJECT_ROOT/models/gemma3
MODEL_PATH="${MODEL_PATH:-/models/gemma3}"
if [ ! -d "$MODEL_PATH" ] && [ -d "$PROJECT_ROOT/models/gemma3" ]; then
    MODEL_PATH="$PROJECT_ROOT/models/gemma3"
fi
TENSOR_PARALLEL_SIZE=1 # "${TENSOR_PARALLEL_SIZE:-${LLM_TENSOR_PARALLEL_SIZE:-2}}"
MAX_TOKENS="${MAX_TOKENS:-${LLM_MAX_TOKENS:-2048}}"
QUANTIZATION="${QUANTIZATION:-${LLM_QUANTIZATION:-awq}}"
MAX_CONCURRENT="${MAX_CONCURRENT:-${LLM_MAX_CONCURRENT:-4}}"
GPU_MEMORY_UTIL="${GPU_MEMORY_UTILIZATION:-${LLM_GPU_MEMORY_UTILIZATION:-0.90}}"
CONTEXT_WINDOW="${CONTEXT_WINDOW:-${LLM_CONTEXT_WINDOW:-8192}}"
KV_CACHE_DTYPE="${KV_CACHE_DTYPE:-${LLM_KV_CACHE_DTYPE:-fp8}}"
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
# RTX 5080 (Blackwell) / WSL 兼容性: 禁用 flashinfer, 使用 PyTorch 原生采样
QUANT_ARGS=()
if [ "$QUANTIZATION" != "none" ] && [ "$QUANTIZATION" != "int4" ] && [ "$QUANTIZATION" != "int8" ]; then
    QUANT_ARGS=(--quantization "$QUANTIZATION")
fi

export VLLM_USE_FLASHINFER_SAMPLER=0

exec python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_SOURCE" \
    --tensor-parallel-size "$TENSOR_PARALLEL_SIZE" \
    "${QUANT_ARGS[@]}" \
    --max-model-len "$CONTEXT_WINDOW" \
    --max-num-seqs "$MAX_NUM_SEQS" \
    --gpu-memory-utilization "$GPU_MEMORY_UTIL" \
    --kv-cache-dtype "$KV_CACHE_DTYPE" \
    --served-model-name "$(basename $MODEL_NAME)" \
    --host 0.0.0.0 \
    --port "$PORT" \
    --trust-remote-code \
    --enforce-eager
