#!/bin/bash
# ============================================================
# 原生部署健康检查脚本
# ============================================================
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0

check() {
    local name="$1"
    local url="$2"
    local expect="${3:-200}"

    if [ -z "$url" ]; then
        if pgrep -f "$name" > /dev/null 2>&1; then
            echo -e "  ${GREEN}●${NC} $name (进程存在)"
            PASS=$((PASS + 1))
        else
            echo -e "  ${RED}○${NC} $name (进程不存在)"
            FAIL=$((FAIL + 1))
        fi
        return
    fi

    local code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "$url" 2>/dev/null || echo "000")
    if [ "$code" = "$expect" ] || [ "$code" = "200" ]; then
        echo -e "  ${GREEN}●${NC} $name ($url -> $code)"
        PASS=$((PASS + 1))
    else
        echo -e "  ${RED}○${NC} $name ($url -> $code, expected $expect)"
        FAIL=$((FAIL + 1))
    fi
}

echo "============================================"
echo " 知识库问答系统 — 原生模式健康检查"
echo "============================================"
echo ""

# 进程检查
echo "进程状态:"
check "redis-server"
check "chromadb" "http://localhost:8004/api/v1/heartbeat"
check "llm-service" "http://localhost:8001/health"
check "embedding-service" "http://localhost:8002/health"
check "asr-service" "http://localhost:8005/health"
check "tts-service" "http://localhost:8006/health"
check "rag-service" "http://localhost:8003/health"
check "api-gateway" "http://localhost:8000/health"

echo ""
echo "============================================"
echo -e " 结果: ${GREEN}${PASS} 通过${NC}, ${RED}${FAIL} 失败${NC}"
echo "============================================"

# GPU 状态
if command -v nvidia-smi &>/dev/null; then
    echo ""
    echo "GPU 状态:"
    nvidia-smi --query-gpu=index,name,memory.used,memory.total,temperature.gpu \
        --format=csv,noheader 2>/dev/null | while read -r line; do
        echo "  $line"
    done
fi

exit $FAIL
