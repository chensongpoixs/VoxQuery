#!/bin/bash
# ============================================================
# 性能基准测试脚本
# 测试系统延迟和吞吐量
# ============================================================
set -e

API_URL="${API_URL:-http://localhost:8000}"
RESULTS_FILE="benchmark_results_$(date +%Y%m%d_%H%M%S).txt"

echo "============================================"
echo " 能源知识库系统 - 性能基准测试"
echo " API: $API_URL"
echo "============================================"

TEST_QUERIES=(
    "变压器的日常巡检项目有哪些？"
    "110kV的安全距离是多少？"
    "SF6断路器的额定压力是多少？"
    "倒闸操作的正确步骤是什么？"
    "变电站设备着火应该怎么处理？"
)

run_test() {
    local name="$1"
    local endpoint="$2"
    local data="$3"
    local iterations="${4:-5}"

    echo ""
    echo "--- $name ---"
    local total_time=0

    for i in $(seq 1 $iterations); do
        local start=$(date +%s%N)
        curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data" > /dev/null 2>&1
        local end=$(date +%s%N)
        local elapsed=$(( (end - start) / 1000000 ))
        total_time=$((total_time + elapsed))
        echo "  第 $i 次: ${elapsed}ms"
    done

    local avg=$((total_time / iterations))
    echo "  平均延迟: ${avg}ms"

    if [ $avg -lt 3000 ]; then
        echo "  结果: PASS (目标 < 3000ms)"
    else
        echo "  结果: FAIL (超出目标)"
    fi
}

# 1. 文本对话测试
for query in "${TEST_QUERIES[@]:0:3}"; do
    run_test "文本问答: ${query:0:30}..." \
        "/api/v1/chat" \
        "{\"message\": \"$query\", \"stream\": false}" \
        3
done

# 2. 知识检索测试
run_test "知识检索" \
    "/api/v1/knowledge/search?query=变压器维护&top_k=5" \
    "" \
    5

# 3. 健康检查延迟
run_test "健康检查" "/health" "" 10

echo ""
echo "============================================"
echo " 测试完成"
echo "============================================"
