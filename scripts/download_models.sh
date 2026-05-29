#!/bin/bash
# ============================================================
# 模型下载脚本 —— 国内镜像源适配版
#
# 镜像源优先级:
#   1. ModelScope (modelscope.cn)  —— 阿里云，速度最快
#   2. HF Mirror (hf-mirror.com)    —— HuggingFace 镜像
#   3. HuggingFace (huggingface.co) —— 原始站（需代理）
#
# 用法:
#   bash scripts/download_models.sh all          # 下载所有模型
#   bash scripts/download_models.sh embedding    # 仅下载 BGE-M3
#   bash scripts/download_models.sh llm          # 仅下载 Gemma-3
#   bash scripts/download_models.sh asr          # 仅下载 Whisper
#   bash scripts/download_models.sh tts          # 仅下载 CosyVoice2
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
MODELS_DIR="${MODELS_DIR:-$PROJECT_DIR/models}"

# 加载 .env 配置
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a; source "$PROJECT_DIR/.env"; set +a
fi

# ---------- 镜像源配置 ----------
HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export HF_ENDPOINT

# 检测网络连通性，自动选择最佳源
detect_best_source() {
    echo "[INFO] 检测网络连通性..."

    if curl -s --connect-timeout 3 https://modelscope.cn > /dev/null 2>&1; then
        echo "[INFO] ModelScope 可达，优先使用 modelscope.cn"
        USE_MODELSCOPE=true
    elif curl -s --connect-timeout 3 https://hf-mirror.com > /dev/null 2>&1; then
        echo "[INFO] HF Mirror 可达，使用 hf-mirror.com"
        USE_MODELSCOPE=false
    else
        echo "[WARN] 国内镜像均不可达，尝试直连 HuggingFace"
        USE_MODELSCOPE=false
        unset HF_ENDPOINT
    fi
}

# ---------- 模型下载函数 ----------

download_bge_m3() {
    local target_dir="$MODELS_DIR/bge-m3"
    echo "============================================"
    echo " 下载 BGE-M3 Embedding 模型 (~2GB)"
    echo "============================================"

    if [ -n "$(ls -A "$target_dir" 2>/dev/null)" ]; then
        echo "[SKIP] BGE-M3 已存在: $target_dir"
        return 0
    fi

    mkdir -p "$target_dir"

    if [ "${USE_MODELSCOPE:-false}" = "true" ]; then
        echo "[INFO] 从 ModelScope 下载..."
        pip install modelscope -q 2>/dev/null || true
        python3 -c "
from modelscope import snapshot_download
snapshot_download('BAAI/bge-m3', cache_dir='$target_dir')
print('BGE-M3 下载完成')
" || {
            echo "[WARN] ModelScope 下载失败，回退至 HF Mirror"
            HF_ENDPOINT=https://hf-mirror.com huggingface-cli download BAAI/bge-m3 --local-dir "$target_dir"
        }
    else
        echo "[INFO] 从 HF Mirror 下载..."
        huggingface-cli download BAAI/bge-m3 --local-dir "$target_dir"
    fi

    echo "[OK] BGE-M3 下载完成"
}

download_gemma3() {
    local target_dir="$MODELS_DIR/gemma3"
    echo "============================================"
    echo " 下载 Gemma-3 27B 模型 (~50GB)"
    echo "  注意: 请预留至少 60GB 磁盘空间"
    echo "============================================"

    if [ -f "$target_dir/config.json" ] 2>/dev/null; then
        echo "[SKIP] Gemma-3 已存在: $target_dir"
        return 0
    fi

    mkdir -p "$target_dir"

    # 检查磁盘空间
    local available_gb=$(df -BG "$MODELS_DIR" 2>/dev/null | tail -1 | awk '{print $4}' | sed 's/G//' || echo "0")
    if [ "${available_gb:-0}" -lt 60 ]; then
        echo "[WARN] 可用磁盘空间不足 60GB，当前可用: ${available_gb}GB"
        echo "       是否继续? (y/N)"
        read -r confirm
        [ "$confirm" != "y" ] && return 1
    fi

    if [ "${USE_MODELSCOPE:-false}" = "true" ]; then
        echo "[INFO] 从 ModelScope 下载 (使用 modelscope CLI)..."
        pip install modelscope -q 2>/dev/null || true
        python3 -c "
from modelscope import snapshot_download
# Gemma-3 27B 在 ModelScope 上的路径
snapshot_download('LLM-Research/gemma-3-27b-it', cache_dir='$target_dir')
print('Gemma-3 下载完成')
" || {
            echo "[WARN] ModelScope 下载失败，回退至 HF Mirror"
            HF_ENDPOINT=https://hf-mirror.com huggingface-cli download google/gemma-3-27b-it --local-dir "$target_dir"
        }
    else
        echo "[INFO] 从 HF Mirror 下载 (约需 30-60 分钟)..."
        huggingface-cli download google/gemma-3-27b-it --local-dir "$target_dir"
    fi

    echo "[OK] Gemma-3 下载完成"
}

download_whisper() {
    local target_dir="$MODELS_DIR/whisper"
    echo "============================================"
    echo " 下载 Whisper-large-v3 模型 (~3GB)"
    echo "============================================"

    if [ -d "$target_dir/models--Systran--faster-whisper-large-v3" ] 2>/dev/null || \
       [ -n "$(ls -A "$target_dir" 2>/dev/null)" ]; then
        echo "[SKIP] Whisper 已存在: $target_dir"
        return 0
    fi

    mkdir -p "$target_dir"

    if [ "${USE_MODELSCOPE:-false}" = "true" ]; then
        echo "[INFO] 从 ModelScope 下载..."
        pip install modelscope -q 2>/dev/null || true
        python3 -c "
from modelscope import snapshot_download
snapshot_download('iic/Whisper-large-v3', cache_dir='$target_dir')
print('Whisper 下载完成')
" || {
            echo "[WARN] ModelScope 下载失败，回退至 HF Mirror"
            python3 -c "
from faster_whisper import WhisperModel
model = WhisperModel('large-v3', device='cpu', compute_type='float32', download_root='$target_dir')
print('Whisper 下载完成')
"
        }
    else
        echo "[INFO] 从 HF Mirror 下载..."
        python3 -c "
from faster_whisper import WhisperModel
model = WhisperModel('large-v3', device='cpu', compute_type='float32', download_root='$target_dir')
print('Whisper 下载完成')
"
    fi

    echo "[OK] Whisper-large-v3 下载完成"
}

download_cosyvoice2() {
    local target_dir="$MODELS_DIR/cosyvoice2"
    echo "============================================"
    echo " 下载 CosyVoice2 模型 (~2GB)"
    echo "============================================"

    if [ -n "$(ls -A "$target_dir" 2>/dev/null)" ]; then
        echo "[SKIP] CosyVoice2 已存在: $target_dir"
        return 0
    fi

    mkdir -p "$target_dir"

    if [ "${USE_MODELSCOPE:-false}" = "true" ]; then
        echo "[INFO] 从 ModelScope 下载..."
        pip install modelscope -q 2>/dev/null || true
        python3 -c "
from modelscope import snapshot_download
snapshot_download('iic/CosyVoice2-0.5B', cache_dir='$target_dir')
print('CosyVoice2 下载完成')
" || {
            echo "[WARN] ModelScope 下载失败"
            echo "请手动下载: git clone https://www.modelscope.cn/iic/CosyVoice2-0.5B.git $target_dir"
        }
    else
        echo "[INFO] ModelScope 不可达，请手动下载 CosyVoice2:"
        echo "  git clone https://www.modelscope.cn/iic/CosyVoice2-0.5B.git $target_dir"
    fi

    echo "[OK] CosyVoice2 下载完成"
}

download_all() {
    echo "============================================"
    echo " 能源智库 —— 全部模型下载"
    echo " 预计总大小: ~57GB"
    echo " 预计时间: 30-90 分钟（取决于网络速度）"
    echo "============================================"
    echo ""

    detect_best_source

    download_bge_m3      # ~2GB,  2-5 分钟
    download_whisper     # ~3GB,  3-8 分钟
    download_cosyvoice2  # ~2GB,  2-5 分钟
    download_gemma3      # ~50GB, 30-60 分钟

    echo ""
    echo "============================================"
    echo " 所有模型下载完成！"
    echo " 存放路径: $MODELS_DIR"
    echo "============================================"

    # 显示磁盘使用
    echo ""
    echo "模型文件大小:"
    du -sh "$MODELS_DIR"/*/ 2>/dev/null || true
}

# ---------- 主入口 ----------
case "${1:-all}" in
    all)
        download_all
        ;;
    embedding)
        detect_best_source
        download_bge_m3
        ;;
    llm)
        detect_best_source
        download_gemma3
        ;;
    asr)
        detect_best_source
        download_whisper
        ;;
    tts)
        detect_best_source
        download_cosyvoice2
        ;;
    detect)
        detect_best_source
        ;;
    *)
        echo "用法: $0 {all|embedding|llm|asr|tts|detect}"
        echo ""
        echo "  all       - 下载所有模型 (~57GB)"
        echo "  embedding - 下载 BGE-M3 (~2GB)"
        echo "  llm       - 下载 Gemma-3 27B (~50GB)"
        echo "  asr       - 下载 Whisper-large-v3 (~3GB)"
        echo "  tts       - 下载 CosyVoice2 (~2GB)"
        echo "  detect    - 仅检测最佳镜像源"
        echo ""
        echo "国内镜像源:"
        echo "  ModelScope: https://modelscope.cn"
        echo "  HF Mirror:  https://hf-mirror.com"
        ;;
esac
