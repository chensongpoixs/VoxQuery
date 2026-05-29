#!/bin/bash
# ============================================================
# 系统健康检查脚本
# 检查所有服务的健康状态
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

check_url() {
    local name="$1"
    local url="$2"
    if curl -sf -o /dev/null "$url" 2>/dev/null; then
        echo -e "  ${GREEN}[OK]${NC} $name"
        return 0
    else
        echo -e "  ${RED}[FAIL]${NC} $name"
        return 1
    fi
}

echo "============================================"
echo " 知识库系统 - 健康检查"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"

ALL_HEALTHY=0

echo ""
echo "基础设施:"
check_url "Redis     " "http://localhost:6379" || ((ALL_HEALTHY++))
check_url "ChromaDB  " "http://localhost:8004/api/v1/heartbeat" || ((ALL_HEALTHY++))

echo ""
echo "推理服务:"
check_url "LLM       " "http://localhost:8001/health" || ((ALL_HEALTHY++))
check_url "Embedding " "http://localhost:8002/health" || ((ALL_HEALTHY++))

echo ""
echo "语音服务:"
check_url "ASR       " "http://localhost:8005/health" || ((ALL_HEALTHY++))
check_url "TTS       " "http://localhost:8006/health" || ((ALL_HEALTHY++))

echo ""
echo "业务服务:"
check_url "RAG       " "http://localhost:8003/health" || ((ALL_HEALTHY++))
check_url "API Gateway" "http://localhost:8000/health" || ((ALL_HEALTHY++))

echo ""
echo "前端:"
check_url "Frontend  " "http://localhost:3000" || ((ALL_HEALTHY++))

echo ""
if [ $ALL_HEALTHY -eq 0 ]; then
    echo -e "${GREEN}所有服务运行正常！${NC}"
    echo ""
    echo "  API 文档: http://localhost:8000/docs"
    echo "  前端界面: http://localhost:3000"
    exit 0
else
    echo -e "${RED}$ALL_HEALTHY 个服务异常${NC}"
    exit 1
fi
