#!/bin/bash
# ============================================================
# 原生部署启动脚本
# 从 supervisord.conf 启动所有服务
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "${BLUE}[STEP]${NC} $1"; }

# ---------- 参数解析 ----------
MODE="${1:-all}"

# ---------- Supervisord 检查 ----------
SUPERVISORD_CONF="${SUPERVISORD_CONF:-$PROJECT_DIR/supervisord.conf}"

use_supervisord() {
    if command -v supervisord &>/dev/null && [ -f "$SUPERVISORD_CONF" ]; then
        return 0
    fi
    return 1
}

# ---------- 进程管理辅助函数 ----------
start_proc() {
    local name="$1"; shift
    if pgrep -f "$name" > /dev/null 2>&1; then
        log_warn "$name 已在运行中"
        return 0
    fi
    log_info "启动 $name ..."
    nohup "$@" > "/tmp/${name//\//-}.log" 2>&1 &
    echo $! > "/tmp/${name//\//-}.pid"
    sleep 2
}

stop_proc() {
    local name="$1"
    local pid_file="/tmp/${name//\//-}.pid"
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            log_info "停止 $name (PID: $pid) ..."
            kill "$pid" 2>/dev/null || true
            sleep 2
            kill -9 "$pid" 2>/dev/null || true
        fi
        rm -f "$pid_file"
    fi
    # 也尝试 pkill
    pkill -f "$name" 2>/dev/null || true
}

# ---------- 启动函数 ----------
start_core() {
    log_step "启动基础设施 + 核心推理服务..."

    # Redis
    if ! pgrep -f "redis-server" > /dev/null 2>&1; then
        log_info "启动 Redis ..."
        redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru \
            --daemonize yes --dir /tmp
    else
        log_warn "Redis 已在运行"
    fi

    # LLM
    start_proc "llm-service" bash "$PROJECT_DIR/services/llm-service/scripts/start_vllm.sh"

    # Embedding
    start_proc "embedding-service" python "$PROJECT_DIR/services/embedding-service/app/main.py"

    log_info "等待核心服务就绪 (~60s)..."
    sleep 10
}

start_voice() {
    log_step "启动语音服务..."
    start_proc "asr-service" python "$PROJECT_DIR/services/asr-service/app/main.py"
    start_proc "tts-service" python "$PROJECT_DIR/services/tts-service/app/main.py"
    sleep 5
}

start_api() {
    log_step "启动业务服务 + 前端..."
    start_proc "rag-service" python "$PROJECT_DIR/services/rag-service/app/main.py"
    sleep 3
    start_proc "api-gateway" uvicorn services.api-gateway.app.main:app --host 0.0.0.0 --port 8000
    sleep 2
    start_proc "frontend" bash -c "cd $PROJECT_DIR/frontend && npm run dev"
}

# ---------- 状态检查 ----------
show_status() {
    echo ""
    echo "============================================"
    echo " 服务运行状态"
    echo "============================================"

    local services=(
        "redis-server:Redis"
        "llm-service:LLM"
        "embedding-service:Embedding"
        "asr-service:ASR"
        "tts-service:TTS"
        "rag-service:RAG"
        "api-gateway:API Gateway"
        "next:Frontend"
    )

    for svc in "${services[@]}"; do
        local proc="${svc%%:*}"
        local label="${svc##*:}"
        if pgrep -f "$proc" > /dev/null 2>&1; then
            echo -e "  ${GREEN}●${NC} $label"
        else
            echo -e "  ${RED}○${NC} $label (未运行)"
        fi
    done
    echo ""
}

# ---------- 主流程 ----------
case "$MODE" in
    all)
        log_info "============================================"
        log_info " 知识库问答系统 — 原生模式启动（全部服务）"
        log_info "============================================"

        # 加载环境变量
        if [ -f "$PROJECT_DIR/.env" ]; then
            set -a; source "$PROJECT_DIR/.env"; set +a
        fi

        # 创建必要目录
        mkdir -p "$PROJECT_DIR/models"/{gemma3,bge-m3,whisper,cosyvoice2}

        start_core
        start_voice
        start_api
        show_status

        log_info "============================================"
        log_info " 系统启动完成！"
        log_info " API 文档: http://localhost:8000/docs"
        log_info " 前端界面: http://localhost:3000"
        log_info "============================================"
        ;;
    core)
        start_core
        show_status
        ;;
    voice)
        start_voice
        show_status
        ;;
    api)
        start_api
        show_status
        ;;
    status)
        show_status
        ;;
    *)
        echo "用法: $0 {all|core|voice|api|status}"
        echo ""
        echo "  all    - 启动所有服务（默认）"
        echo "  core   - 仅启动核心服务（LLM + Embedding + Redis）"
        echo "  voice  - 仅启动语音服务（ASR + TTS）"
        echo "  api    - 仅启动 API + 前端"
        echo "  status - 查看服务状态"
        ;;
esac
