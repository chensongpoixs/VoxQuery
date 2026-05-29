#!/bin/bash
# ============================================================
# 原生部署停止脚本
# ============================================================
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

stop_proc() {
    local name="$1"
    local label="${2:-$name}"
    local pid_file="/tmp/${name//\//-}.pid"

    # 先尝试从 PID 文件停止
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            log_info "停止 $label (PID: $pid) ..."
            kill "$pid" 2>/dev/null || true
            sleep 2
            # 如果还活着，强制终止
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null || true
                log_info "$label 已强制终止"
            fi
        fi
        rm -f "$pid_file"
    fi

    # 回退：使用 pkill 清理残留
    pkill -f "$name" 2>/dev/null && log_info "$label 残留进程已清理" || true
}

log_info "============================================"
log_info " 知识库问答系统 — 原生模式停止"
log_info "============================================"

# 按依赖顺序反向停止
stop_proc "frontend" "Frontend"
stop_proc "api-gateway" "API Gateway"
stop_proc "rag-service" "RAG Service"
stop_proc "tts-service" "TTS Service"
stop_proc "asr-service" "ASR Service"
stop_proc "embedding-service" "Embedding Service"
stop_proc "llm-service" "LLM Service"

# Redis: 使用 redis-cli 优雅关闭
if pgrep -f "redis-server" > /dev/null 2>&1; then
    if command -v redis-cli &>/dev/null; then
        log_info "停止 Redis ..."
        redis-cli SHUTDOWN 2>/dev/null || true
    else
        stop_proc "redis-server" "Redis"
    fi
fi

# ChromaDB
pkill -f "chroma" 2>/dev/null || true

# 清理 PID 文件
rm -f /tmp/*.pid 2>/dev/null || true

log_info "所有服务已停止"
