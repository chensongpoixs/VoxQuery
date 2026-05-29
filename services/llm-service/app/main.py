"""LLM 推理服务 —— 基于 vLLM OpenAI-compatible API Server

使用 vLLM 引擎部署 Gemma-3 27B，提供 OpenAI 兼容的 /v1/chat/completions 接口。
张量并行使用 2×RTX 4090 (GPU 0,1)，INT8 量化节省显存。
"""

import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.config import LLMServiceConfig

logger = logging.getLogger(__name__)
config = LLMServiceConfig()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info(f"LLM Service starting: model={config.model_name}, "
                f"tp_size={config.tensor_parallel_size}, "
                f"quantization={config.quantization}")
    yield
    logger.info("LLM Service shutting down")


app = FastAPI(
    title="Energy KB - LLM Inference Service",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "healthy", "model": config.model_name}


@app.get("/v1/models")
async def list_models():
    """列出可用模型"""
    return {
        "object": "list",
        "data": [
            {
                "id": config.model_name,
                "object": "model",
                "owned_by": "energy-kb",
            }
        ],
    }


@app.get("/stats")
async def get_stats():
    """获取推理服务统计信息"""
    return {
        "model": config.model_name,
        "tensor_parallel_size": config.tensor_parallel_size,
        "quantization": config.quantization,
        "context_window": config.context_window,
        "max_concurrent": config.max_concurrent,
        "gpu_memory_utilization": config.gpu_memory_utilization,
    }
