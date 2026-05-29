"""RAG 服务客户端"""

import logging
import httpx
from typing import List, Dict, Optional, Any
from app.config import Settings

logger = logging.getLogger(__name__)


class RAGClient:
    def __init__(self, settings: Settings):
        self.base_url = settings.rag_service_url
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def search(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """语义检索"""
        url = f"{self.base_url}/search"
        response = await self.http_client.post(url, json={
            "query": query,
            "top_k": top_k,
        })
        response.raise_for_status()
        return response.json()

    async def ingest_texts(
        self, texts: List[str], metadatas: Optional[List[Dict]] = None
    ) -> Dict:
        """直接入库文本"""
        url = f"{self.base_url}/ingest"
        payload = {"texts": texts}
        if metadatas:
            payload["metadatas"] = metadatas
        response = await self.http_client.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    async def ingest_file(self, filepath: str, strategy: str = "sliding_window") -> Dict:
        """文件入库"""
        url = f"{self.base_url}/ingest"
        response = await self.http_client.post(url, json={
            "filepath": filepath,
            "strategy": strategy,
        })
        response.raise_for_status()
        return response.json()

    async def ingest_directory(self, directory: str, strategy: str = "sliding_window") -> Dict:
        """目录批量入库"""
        url = f"{self.base_url}/ingest"
        response = await self.http_client.post(url, json={
            "directory": directory,
            "strategy": strategy,
        })
        response.raise_for_status()
        return response.json()

    async def delete_document(self, doc_id: str) -> Dict:
        """删除文档"""
        url = f"{self.base_url}/delete"
        response = await self.http_client.post(url, json={"doc_id": doc_id})
        response.raise_for_status()
        return response.json()

    async def get_stats(self) -> Dict:
        """获取知识库统计"""
        url = f"{self.base_url}/collection/stats"
        response = await self.http_client.get(url)
        response.raise_for_status()
        return response.json()

    async def health(self) -> bool:
        try:
            response = await self.http_client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self):
        await self.http_client.aclose()
