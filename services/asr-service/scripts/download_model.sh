#!/bin/bash
# 下载 Whisper-large-v3 模型（国内镜像适配）
set -e

MODEL_DIR="${MODEL_DIR:-/models/whisper}"
MODEL_NAME="large-v3"

echo "下载 Whisper-large-v3 模型到 $MODEL_DIR..."
mkdir -p "$MODEL_DIR"

# 检测并设置镜像源
if [ -z "$HF_ENDPOINT" ]; then
    export HF_ENDPOINT="https://hf-mirror.com"
fi
echo "使用 HuggingFace 镜像: $HF_ENDPOINT"

# 优先尝试 ModelScope
if curl -s --connect-timeout 3 https://modelscope.cn > /dev/null 2>&1; then
    echo "[INFO] ModelScope 可达，优先使用 modelscope.cn"
    pip install modelscope -q 2>/dev/null || true
    python3 -c "
from modelscope import snapshot_download
snapshot_download('iic/Whisper-large-v3', cache_dir='$MODEL_DIR')
" 2>/dev/null && echo "Whisper 下载完成 (ModelScope)" && exit 0
    echo "[WARN] ModelScope 下载失败，回退至 faster-whisper 自动下载"
fi

# 使用 faster-whisper 自动下载（会走 HF_ENDPOINT）
python3 -c "
from faster_whisper import WhisperModel
model = WhisperModel('$MODEL_NAME', device='cpu', compute_type='float32',
                     download_root='$MODEL_DIR')
print(f'模型已下载到: $MODEL_DIR')
"

echo "Whisper 模型下载完成"
