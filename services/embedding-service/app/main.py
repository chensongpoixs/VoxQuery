"""Embedding 向量化服务 —— BGE-M3 模型

部署于独立 GPU (RTX 4090, GPU 2)，支持 8192 token 长文本输入。
提供文本向量化和批量向量化 REST API。
"""

import logging
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Union
from contextlib import asynccontextmanager
from sentence_transformers import SentenceTransformer

from app.config import EmbeddingServiceConfig

logger = logging.getLogger(__name__)
config = EmbeddingServiceConfig()

# 全局模型实例
_model: SentenceTransformer = None


def get_model() -> SentenceTransformer:
    """懒加载模型"""
    global _model
    if _model is None:
        model_source = config.model_path if config.model_path else config.model_name
        logger.info(f"Loading BGE-M3 model from: {model_source}")
        _model = SentenceTransformer(
            model_source,
            device=config.device,
            trust_remote_code=True,
        )
        # 设置最大序列长度
        _model.max_seq_length = config.max_length
        logger.info(f"BGE-M3 loaded, dim={config.embedding_dim}, "
                    f"max_length={config.max_length}")
    return _model


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Embedding Service starting on port {config.port}")
    get_model()  # 预加载模型
    yield
    logger.info("Embedding Service shutting down")


app = FastAPI(
    title="KB - Embedding Service",
    version="1.0.0",
    lifespan=lifespan,
)


class EmbeddingRequest(BaseModel):
    texts: Union[str, List[str]] = Field(..., description="输入文本或文本列表")
    normalize: bool = Field(default=True, description="是否归一化向量")


class EmbeddingResponse(BaseModel):
    embeddings: List[List[float]]
    dimensions: int
    count: int


@app.get("/health")
async def health_check():
    return {"status": "healthy", "model": config.model_name}


@app.post("/v1/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(request: EmbeddingRequest):
    """文本向量化接口"""
    try:
        texts = [request.texts] if isinstance(request.texts, str) else request.texts
        if not texts:
            raise HTTPException(status_code=400, detail="输入文本为空")

        model = get_model()
        embeddings = model.encode(
            texts,
            normalize_embeddings=request.normalize,
            batch_size=config.batch_size,
            show_progress_bar=False,
        )

        return EmbeddingResponse(
            embeddings=embeddings.tolist(),
            dimensions=embeddings.shape[1],
            count=len(texts),
        )
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats():
    return {
        "model": config.model_name,
        "max_length": config.max_length,
        "batch_size": config.batch_size,
        "embedding_dim": config.embedding_dim,
        "device": config.device,
    }
