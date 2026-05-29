"""RAG 检索增强生成服务

提供文档检索、知识库管理接口。
依赖 Embedding 服务（向量化）和 ChromaDB（向量存储）。
"""

import logging
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from contextlib import asynccontextmanager

from app.config import RAGServiceConfig
from app.retrieval.retriever import SemanticRetriever
from app.indexing.pipeline import IndexingPipeline
from app.models.schemas import (
    SearchRequest, SearchResponse, SearchResult,
    IngestRequest, IngestResponse, DeleteRequest, CollectionStats,
)

logger = logging.getLogger(__name__)
config = RAGServiceConfig()

# 全局实例
_retriever: Optional[SemanticRetriever] = None
_pipeline: Optional[IndexingPipeline] = None


def get_retriever() -> SemanticRetriever:
    global _retriever
    if _retriever is None:
        _retriever = SemanticRetriever(config)
    return _retriever


def get_pipeline() -> IndexingPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = IndexingPipeline(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
        )
    return _pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"RAG Service starting on port {config.port}")
    # 预初始化
    get_retriever()
    get_pipeline()
    # 加载同义词
    get_retriever().synonym_mapper.load_from_file("/app/dicts/synonyms.yaml")
    yield


app = FastAPI(
    title="KB - RAG Service",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "collection": config.chroma_collection}


# ========== 检索接口 ==========

@app.post("/search", response_model=SearchResponse)
async def search_documents(request: SearchRequest):
    """语义检索文档"""
    retriever = get_retriever()
    results = await retriever.retrieve(
        query=request.query,
        top_k=request.top_k,
        use_cache=request.use_cache,
    )

    return SearchResponse(
        query=request.query,
        results=[
            SearchResult(
                id=r.get("id", ""),
                text=r.get("text", ""),
                metadata=r.get("metadata", {}),
                score=round(r.get("score", 0.0), 4),
            )
            for r in results
        ],
        count=len(results),
    )


# ========== 知识库管理接口 ==========

@app.post("/ingest", response_model=IngestResponse)
async def ingest_documents(request: IngestRequest):
    """文档入库"""
    retriever = get_retriever()
    pipeline = get_pipeline()
    chunks = []
    errors = []

    # 方式 1：直接传入文本
    if request.texts:
        for i, text in enumerate(request.texts):
            metadata = {}
            if request.metadatas and i < len(request.metadatas):
                metadata = request.metadatas[i]
            chunks.append({"text": text, "metadata": metadata})

    # 方式 2：处理单个文件
    elif request.filepath:
        try:
            chunks = pipeline.process_file(request.filepath, request.strategy)
        except Exception as e:
            errors.append(f"File error: {e}")

    # 方式 3：处理整个目录
    elif request.directory:
        try:
            chunks = pipeline.process_directory(request.directory, request.strategy)
        except Exception as e:
            errors.append(f"Directory error: {e}")

    else:
        raise HTTPException(status_code=400, detail="No input provided")

    # 向量化并入库
    added = 0
    if chunks:
        try:
            added = await retriever.add_documents(chunks)
        except Exception as e:
            errors.append(f"Ingest error: {e}")

    return IngestResponse(
        status="success" if added > 0 else "warning",
        documents_added=added,
        chunks_created=len(chunks),
        errors=errors,
    )


@app.post("/delete", response_model=dict)
async def delete_document(request: DeleteRequest):
    """删除文档"""
    retriever = get_retriever()
    count = await retriever.delete_documents(request.doc_id)
    return {"status": "success", "deleted_chunks": count}


@app.get("/collection/stats", response_model=CollectionStats)
async def collection_stats():
    """获取知识库统计信息"""
    retriever = get_retriever()
    stats = retriever.get_collection_stats()
    return CollectionStats(**stats)


@app.get("/synonyms/count")
async def synonym_count():
    """获取同义词映射统计"""
    retriever = get_retriever()
    return {"synonym_groups": retriever.synonym_mapper.get_synonym_count()}
