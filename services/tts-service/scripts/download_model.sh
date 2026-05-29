#!/bin/bash
# 下载 CosyVoice2 模型（国内镜像适配）
set -e

MODEL_DIR="${MODEL_DIR:-/models/cosyvoice2}"

echo "下载 CosyVoice2 模型到 $MODEL_DIR..."
mkdir -p "$MODEL_DIR"

# CosyVoice2-0.5B 模型（推荐用于消费级 GPU）
MODELSCOPE_REPO="iic/CosyVoice2-0.5B"

# 方式1: ModelScope（国内推荐）
if command -v git &>/dev/null && [ -z "$(ls -A "$MODEL_DIR" 2>/dev/null)" ]; then
    echo "[INFO] 从 ModelScope 克隆 CosyVoice2-0.5B..."
    if git clone "https://www.modelscope.cn/$MODELSCOPE_REPO.git" "$MODEL_DIR" 2>/dev/null; then
        echo "CosyVoice2 下载完成 (ModelScope)"
        exit 0
    fi
    echo "[WARN] Git 克隆失败，尝试 modelscope CLI..."
fi

# 方式2: modelscope Python SDK
if [ -z "$(ls -A "$MODEL_DIR" 2>/dev/null)" ]; then
    pip install modelscope -q 2>/dev/null || true
    python3 -c "
from modelscope import snapshot_download
snapshot_download('$MODELSCOPE_REPO', cache_dir='$MODEL_DIR')
print('CosyVoice2 下载完成 (ModelScope SDK)')
" 2>/dev/null || {
        echo "[WARN] 自动下载失败，请手动下载:"
        echo "  git clone https://www.modelscope.cn/$MODELSCOPE_REPO.git $MODEL_DIR"
        echo "  或访问: https://www.modelscope.cn/models/$MODELSCOPE_REPO"
    }
fi

echo "CosyVoice2 模型目录: $MODEL_DIR"
ls -la "$MODEL_DIR" 2>/dev/null || echo "(空目录，请手动下载模型)"
