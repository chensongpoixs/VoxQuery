#!/bin/bash
# ============================================================
# 能源行业知识库问答系统 —— 一键部署脚本
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ========== 依赖检查 ==========
check_dependencies() {
    log_info "检查系统依赖..."

    if ! command -v docker &>/dev/null; then
        log_error "Docker 未安装"
        exit 1
    fi

    if ! docker compose version &>/dev/null; then
        log_error "Docker Compose 未安装"
        exit 1
    fi

    if ! command -v nvidia-smi &>/dev/null; then
        log_warn "NVIDIA 驱动未检测到，GPU 功能不可用"
    else
        nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    fi

    log_info "依赖检查通过"
}

# ========== 环境初始化 ==========
init_environment() {
    log_info "初始化环境..."

    if [ ! -f "$PROJECT_DIR/.env" ]; then
        cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
        log_info ".env 文件已创建，请根据需要修改配置"
    else
        log_info ".env 文件已存在"
    fi

    # 创建必要目录
    mkdir -p "$PROJECT_DIR/models"/{gemma3,bge-m3,whisper,cosyvoice2}
    mkdir -p "$PROJECT_DIR/knowledge-base/sample-docs"

    log_info "环境初始化完成"
}

# ========== 模型下载 ==========
download_models() {
    log_info "开始下载模型（使用国内镜像源）..."
    log_info "镜像优先级: ModelScope > HF Mirror > HuggingFace"
    bash "$PROJECT_DIR/scripts/download_models.sh" all
}

# ========== 构建 & 启动 ==========
build_and_start() {
    log_info "构建服务镜像..."
    cd "$PROJECT_DIR"
    docker compose build

    log_info "启动核心服务..."
    docker compose up -d redis chromadb llm-service embedding-service
    log_info "等待核心服务就绪（约 2 分钟）..."
    sleep 30

    log_info "启动 RAG 服务..."
    docker compose up -d rag-service
    sleep 10

    log_info "启动语音服务..."
    docker compose up -d asr-service tts-service
    sleep 10

    log_info "启动 API Gateway 和前端..."
    docker compose up -d api-gateway frontend

    log_info "============================================"
    log_info " 系统部署完成！"
    log_info " API 文档: http://localhost:8000/docs"
    log_info " 前端界面: http://localhost:3000"
    log_info "============================================"
}

# ========== 导入示例数据 ==========
import_sample_data() {
    log_info "创建示例文档..."
    cat > "$PROJECT_DIR/knowledge-base/sample-docs/安全操作规程.md" << 'DOCEOF'
# 变电站安全操作规程

## 1. 基本安全规定

### 1.1 人员要求
- 所有进入变电站人员必须持有有效电工证
- 作业人员必须佩戴安全帽、绝缘鞋、工作服
- 特种作业人员需持相应特种作业操作证

### 1.2 安全距离
- 10kV及以下：安全距离不小于 0.7m
- 35kV：安全距离不小于 1.0m
- 110kV：安全距离不小于 1.5m
- 220kV：安全距离不小于 3.0m

## 2. 倒闸操作流程

### 2.1 操作前准备
1. 填写操作票，经值班负责人审核签字
2. 检查操作设备状态，确认设备编号
3. 准备绝缘手套、绝缘靴、验电器等安全工器具
4. 操作人员两人一组，一人操作一人监护

### 2.2 操作步骤
1. 断开负荷侧断路器
2. 断开电源侧断路器
3. 拉开负荷侧隔离开关
4. 拉开电源侧隔离开关
5. 验电确认无电压
6. 挂接地线

## 3. 紧急情况处理

### 3.1 设备着火
- 立即切断电源
- 使用干粉灭火器或CO2灭火器
- 禁止使用水或泡沫灭火器
- 报告调度中心和上级领导

### 3.2 人员触电
- 立即切断电源
- 使触电者脱离电源
- 实施心肺复苏（CPR）
- 拨打急救电话 120
DOCEOF

    cat > "$PROJECT_DIR/knowledge-base/sample-docs/设备维护手册.md" << 'DOCEOF'
# 变压器维护手册

## 型号：SZ11-50000/110

### 主要技术参数
| 参数 | 数值 |
|------|------|
| 额定容量 | 50000 kVA |
| 额定电压 | 110/10.5 kV |
| 额定电流 | 262/2749 A |
| 冷却方式 | ONAN/ONAF |
| 联结组别 | YNd11 |
| 短路阻抗 | 10.5% |

### 日常巡检项目
1. 油温检查：上层油温不超过 85°C
2. 油位检查：油位应在油标刻度范围内
3. 声响检查：变压器运行声音应均匀无异常
4. 渗漏检查：各密封处无渗漏油现象
5. 套管检查：套管无裂纹、放电痕迹

### 定期维护周期
- 每月：清洁变压器外表，检查冷却装置
- 每季度：检查瓦斯继电器，取油样试验
- 每年：预防性试验，包括绝缘电阻、直流电阻、变比测试
- 每5年：大修，吊芯检查，更换密封件

## SF6断路器维护

### 型号：LW36-126/3150-40

### 主要技术参数
| 参数 | 数值 |
|------|------|
| 额定电压 | 126 kV |
| 额定电流 | 3150 A |
| 额定短路开断电流 | 40 kA |
| SF6气体额定压力 | 0.6 MPa |
| 报警压力 | 0.52 MPa |
| 闭锁压力 | 0.5 MPa |
DOCEOF

    log_info "导入示例文档到知识库..."
    sleep 5
    curl -s -X POST http://localhost:8003/ingest \
        -H "Content-Type: application/json" \
        -d '{"directory": "/app/knowledge-base/sample-docs"}' \
        || log_warn "RAG 服务可能未就绪，请稍后手动导入：make kb-ingest"

    log_info "示例数据导入完成"
}

# ========== 主流程 ==========
case "${1:-all}" in
    check)
        check_dependencies
        ;;
    init)
        init_environment
        ;;
    download-models)
        download_models
        ;;
    build)
        build_and_start
        ;;
    sample)
        import_sample_data
        ;;
    all)
        check_dependencies
        init_environment
        build_and_start
        import_sample_data
        ;;
    *)
        echo "用法: $0 {check|init|download-models|build|sample|all}"
        echo ""
        echo "  check            - 检查系统依赖"
        echo "  init             - 初始化环境配置"
        echo "  download-models  - 下载模型文件"
        echo "  build            - 构建并启动所有服务"
        echo "  sample           - 导入示例数据"
        echo "  all              - 执行全部流程（默认）"
        ;;
esac
