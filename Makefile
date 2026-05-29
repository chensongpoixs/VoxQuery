.PHONY: help setup build start stop restart logs clean test lint

# 默认目标
help: ## 显示帮助信息
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ========== 环境初始化 ==========

setup: ## 初始化环境（复制 .env 文件）
	@test -f .env || cp .env.example .env
	@echo "环境初始化完成，请检查 .env 文件中的配置"

init-dirs: ## 创建必要的目录
	mkdir -p models/gemma3 models/bge-m3 models/whisper models/cosyvoice2

# ========== Docker 操作 ==========

build: ## 构建所有服务镜像
	docker compose build

build-no-cache: ## 无缓存构建所有服务镜像
	docker compose build --no-cache

build-llm: ## 仅构建 LLM 服务
	docker compose build llm-service

build-embedding: ## 仅构建 Embedding 服务
	docker compose build embedding-service

build-rag: ## 仅构建 RAG 服务
	docker compose build rag-service

start: ## 启动所有服务
	docker compose up -d

start-verbose: ## 启动所有服务（前台输出日志）
	docker compose up

stop: ## 停止所有服务
	docker compose down

restart: stop start ## 重启所有服务

restart-api: ## 仅重启 API Gateway
	docker compose restart api-gateway

# ========== 分服务启动 ==========

start-core: ## 启动核心服务（LLM + Embedding + Redis + ChromaDB）
	docker compose up -d redis chromadb llm-service embedding-service

start-voice: ## 启动语音服务（ASR + TTS）
	docker compose up -d asr-service tts-service

start-api: ## 启动 API 和前端
	docker compose up -d api-gateway rag-service frontend

# ========== 日志 ==========

logs: ## 查看所有服务日志
	docker compose logs -f

logs-api: ## 查看 API Gateway 日志
	docker compose logs -f api-gateway

logs-llm: ## 查看 LLM 服务日志
	docker compose logs -f llm-service

logs-rag: ## 查看 RAG 服务日志
	docker compose logs -f rag-service

# ========== 状态 & 健康检查 ==========

status: ## 查看服务运行状态
	docker compose ps

health: ## 运行健康检查脚本
	bash scripts/health_check.sh

# ========== 测试 ==========

test: ## 运行所有测试
	python -m pytest tests/ -v

test-api: ## 运行 API 测试
	python -m pytest services/api-gateway/tests/ -v

test-rag: ## 运行 RAG 测试
	python -m pytest services/rag-service/tests/ -v

test-unit: ## 运行单元测试
	python -m pytest tests/ -v -m unit

# ========== 知识库 ==========

kb-ingest: ## 导入示例文档到知识库
	python knowledge-base/scripts/ingest.py --docs-dir knowledge-base/sample-docs

kb-update: ## 增量更新知识库
	python knowledge-base/scripts/update.py

kb-batch-import: ## 批量导入文档
	python knowledge-base/scripts/batch_import.py --input-dir $(DIR)

# ========== 清理 ==========

clean: ## 停止并清理容器、卷
	docker compose down -v

clean-models: ## 清理下载的模型文件（释放磁盘空间）
	rm -rf models/*

clean-all: clean clean-models ## 清理所有数据（包括模型）

# ========== 开发工具 ==========

lint: ## 代码格式检查
	python -m flake8 services/ knowledge-base/ scripts/ tests/

format: ## 代码格式化
	python -m black services/ knowledge-base/ scripts/ tests/

dev-api: ## 本地开发模式启动 API Gateway
	cd services/api-gateway && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## 本地开发模式启动前端
	cd frontend && npm run dev

# ========== 性能测试 ==========

benchmark: ## 运行性能基准测试
	bash scripts/benchmark.sh

# ========== 模型下载（国内镜像） ==========

download-models: ## 下载所有模型（自动选择国内镜像源）
	bash scripts/download_models.sh all

download-model-llm: ## 仅下载 LLM 模型
	bash scripts/download_models.sh llm

download-model-embedding: ## 仅下载 Embedding 模型
	bash scripts/download_models.sh embedding

download-model-whisper: ## 仅下载 Whisper 模型
	bash scripts/download_models.sh asr

download-model-tts: ## 仅下载 CosyVoice2 模型
	bash scripts/download_models.sh tts

detect-mirror: ## 检测最佳模型下载镜像源
	bash scripts/download_models.sh detect
