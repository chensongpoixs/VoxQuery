"""知识库管理路由"""

import logging
from fastapi import APIRouter, Request, UploadFile, File, Depends, HTTPException
from app.services.rag_client import RAGClient
from app.middleware.auth import verify_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


@router.post("/search")
async def search_knowledge(
    query: str,
    top_k: int = 5,
    req: Request = None,
    _: bool = Depends(verify_token),
):
    """知识库语义搜索"""
    rag_client: RAGClient = req.app.state.rag_client
    result = await rag_client.search(query, top_k)
    return result


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    strategy: str = "sliding_window",
    req: Request = None,
    _: bool = Depends(verify_token),
):
    """上传文档到知识库"""
    import tempfile
    import os

    rag_client: RAGClient = req.app.state.rag_client

    # 保存上传文件
    suffix = os.path.splitext(file.filename or "upload.txt")[1] or ".txt"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = await rag_client.ingest_file(tmp_path, strategy)
        return {
            "status": result.get("status", "success"),
            "filename": file.filename,
            "chunks_created": result.get("chunks_created", 0),
            "documents_added": result.get("documents_added", 0),
        }
    finally:
        os.unlink(tmp_path)


@router.post("/import-directory")
async def import_directory(
    directory: str = "/app/knowledge-base/sample-docs",
    strategy: str = "sliding_window",
    req: Request = None,
    _: bool = Depends(verify_token),
):
    """批量导入目录文档"""
    rag_client: RAGClient = req.app.state.rag_client
    result = await rag_client.ingest_directory(directory, strategy)
    return result


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    req: Request,
    _: bool = Depends(verify_token),
):
    """删除知识库文档"""
    rag_client: RAGClient = req.app.state.rag_client
    return await rag_client.delete_document(doc_id)


@router.get("/stats")
async def knowledge_stats(
    req: Request,
    _: bool = Depends(verify_token),
):
    """知识库统计信息"""
    rag_client: RAGClient = req.app.state.rag_client
    return await rag_client.get_stats()
