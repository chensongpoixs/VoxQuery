#!/bin/bash
# ============================================================
# 知识库问答系统 —— 一键部署脚本
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

    # 从 profile 生成配置（默认 multi-gpu / docker）
    local profile="${HARDWARE_PROFILE:-multi-gpu}"
    local mode="${DEPLOYMENT_MODE:-docker}"

    if [ ! -f "$PROJECT_DIR/.env" ]; then
        log_info "从 profile '${profile}' 生成 .env 配置..."
        python3 "$PROJECT_DIR/configs/generate_config.py" \
            --profile "$profile" --mode "$mode" --force
    else
        log_info ".env 文件已存在，跳过生成"
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
    cat > "$PROJECT_DIR/knowledge-base/sample-docs/信息安全管理制度.md" << 'DOCEOF'
# 信息安全管理制度

## 1. 基本安全规定

### 1.1 人员要求
- 所有员工必须签署保密协议后方可接入公司网络
- 新员工入职须完成信息安全培训并通过考核
- 离职人员在最后工作日前须完成权限回收流程

### 1.2 账号与密码管理
- 密码长度不少于 12 位，须包含大小写字母、数字和特殊字符
- 账号密码每 90 天强制更换一次
- 禁止使用个人社交账号密码作为办公系统密码
- 多因素认证（MFA）对所有远程接入强制开启

## 2. 数据分类与访问控制

### 2.1 数据安全分级
| 级别 | 说明 | 访问控制 |
|------|------|---------|
| 绝密 | 核心商业机密 | 需总监级以上审批 |
| 机密 | 部门级敏感数据 | 需部门负责人审批 |
| 内部 | 公司内部使用 | 员工可访问 |
| 公开 | 可对外发布 | 无限制 |

### 2.2 第三方访问管理
1. 第三方供应商须签署保密协议
2. 访问权限按最小必要原则分配
3. 访问记录保存不少于 12 个月
4. 供应商服务期结束后 24 小时内回收所有权限

## 3. 应急响应流程

### 3.1 安全事件分级
- P1（严重）：核心系统被入侵、大规模数据泄露，15分钟响应
- P2（紧急）：单个业务系统受影响，30分钟响应
- P3（一般）：非关键系统告警，2小时响应

### 3.2 数据泄露处置
- 立即隔离受影响系统
- 通知信息安全部门和安全委员会
- 48 小时内完成初步调查报告
- 涉及个人信息泄露须按法规 72 小时内通知监管机构
DOCEOF

    cat > "$PROJECT_DIR/knowledge-base/sample-docs/服务器运维手册.md" << 'DOCEOF'
# 服务器运维手册

## 型号：Dell PowerEdge R750xs

### 主要硬件配置
| 参数 | 数值 |
|------|------|
| CPU | Intel Xeon Gold 6338N 2.2GHz ×2 |
| 内存 | 512GB DDR4 ECC |
| 存储 | 4×3.84TB NVMe SSD RAID5 |
| 网络 | 2×25GbE SFP28 + 2×1GbE RJ45 |
| 电源 | 2×800W 冗余电源 |
| GPU | NVIDIA A100 80GB ×4 |

### 日常巡检项目
1. 温度检查：CPU 温度不超过 75°C，GPU 不超过 85°C
2. 磁盘检查：阵列状态正常，无降级或重建
3. 内存检查：无 ECC 错误累计
4. 电源检查：双路供电正常，无告警灯
5. 网卡检查：链路状态正常，丢包率 < 0.001%

### 定期维护周期
- 每周：检查系统日志，清理过期文件
- 每月：检查 RAID 一致性，SMART 磁盘健康报告
- 每季度：固件版本审计，应用安全补丁
- 每年：硬件全面检测，更换到期部件

## 网络设备维护

### 型号：H3C S5560X-34S-EI 万兆交换机

### 主要技术参数
| 参数 | 数值 |
|------|------|
| 交换容量 | 2.56 Tbps |
| 转发率 | 1440 Mpps |
| 端口配置 | 24×10GbE SFP+ + 4×40GbE QSFP+ |
| MAC地址表 | 128K |
| VLAN数量 | 4094 |
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
