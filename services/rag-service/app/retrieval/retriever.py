"""语义检索核心模块

检索流程：
1. Query 向量化（调用 Embedding 服务）
2. 同义词查询扩展
3. 向量相似度检索（ChromaDB）
4. 相似度阈值过滤
5. 返回 Top-K 文档片段
"""

import logging
import hashlib
import json
from typing import List, Dict, Optional, Any
import httpx
import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import RAGServiceConfig
from app.retrieval.synonym import SynonymMapper
from app.retrieval.reranker import Reranker

logger = logging.getLogger(__name__)


class SemanticRetriever:
    """语义检索器"""

    def __init__(self, config: RAGServiceConfig):
        self.config = config
        self.synonym_mapper = SynonymMapper()
        self.reranker = Reranker()

        # 初始化 ChromaDB 客户端
        self.chroma_client = chromadb.HttpClient(
            host=config.chroma_host,
            port=config.chroma_port,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self._get_or_create_collection()

        # HTTP 客户端（连接 Embedding 服务）
        self.http_client = httpx.AsyncClient(timeout=30.0)

        # 检索缓存
        self.cache: Dict[str, List[Dict]] = {}
        self._init_redis()

    def _init_redis(self):
        """初始化 Redis 连接"""
        try:
            import redis
            self.redis = redis.Redis(
                host=self.config.redis_host,
                port=self.config.redis_port,
                decode_responses=True,
                socket_connect_timeout=3,
            )
            self.redis.ping()
            logger.info("Redis connected for retrieval cache")
        except Exception as e:
            logger.warning(f"Redis unavailable, using in-memory cache: {e}")
            self.redis = None

    def _get_or_create_collection(self):
        """获取或创建 ChromaDB 集合"""
        try:
            collection = self.chroma_client.get_collection(
                name=self.config.chroma_collection,
            )
            logger.info(f"Collection '{self.config.chroma_collection}' loaded: "
                        f"{collection.count()} documents")
        except Exception:
            collection = self.chroma_client.create_collection(
                name=self.config.chroma_collection,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(f"Collection '{self.config.chroma_collection}' created")
        return collection

    async def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """调用 Embedding 服务获取向量"""
        url = f"{self.config.embedding_service_url}/v1/embeddings"
        response = await self.http_client.post(url, json={
            "texts": texts,
            "normalize": True,
        })
        response.raise_for_status()
        data = response.json()
        return data["embeddings"]

    def _cache_key(self, query: str) -> str:
        return hashlib.md5(query.encode()).hexdigest()

    async def _cached_retrieve(self, query: str) -> Optional[List[Dict]]:
        """尝试从缓存获取检索结果"""
        key = self._cache_key(query)

        # 先查 Redis
        if self.redis:
            try:
                cached = self.redis.get(f"retrieval:{key}")
                if cached:
                    return json.loads(cached)
            except Exception:
                pass

        # 再查内存缓存
        return self.cache.get(key)

    async def _cache_store(self, query: str, results: List[Dict]):
        """缓存检索结果"""
        key = self._cache_key(query)

        # 存 Redis
        if self.redis:
            try:
                self.redis.setex(
                    f"retrieval:{key}",
                    self.config.retrieval_cache_ttl,
                    json.dumps(results, ensure_ascii=False),
                )
            except Exception:
                pass

        # 存内存缓存（LRU 简单实现）
        if len(self.cache) > 1000:
            self.cache.pop(next(iter(self.cache)))
        self.cache[key] = results

    async def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """执行语义检索

        Args:
            query: 用户查询文本
            top_k: 返回文档数量
            use_cache: 是否使用缓存

        Returns:
            检索结果列表 [{"text": ..., "metadata": ..., "score": ...}, ...]
        """
        top_k = top_k or self.config.top_k

        # 1. 检查缓存
        if use_cache:
            cached = await self._cached_retrieve(query)
            if cached:
                logger.info(f"Cache hit for query: {query[:50]}...")
                return cached[:top_k]

        # 2. 查询扩展（同义词）
        expanded_queries = self.synonym_mapper.expand_query(query)
        logger.debug(f"Query expanded to {len(expanded_queries)} variants")

        # 3. 获取查询向量
        query_embeddings = await self._get_embeddings(expanded_queries)

        # 4. 多路向量检索
        all_results = []
        seen_ids = set()

        for i, q_embedding in enumerate(query_embeddings):
            results = self.collection.query(
                query_embeddings=[q_embedding],
                n_results=top_k * 2,  # 多召回一些给 reranker
                include=["documents", "metadatas", "distances"],
            )

            for j in range(len(results["ids"][0])):
                doc_id = results["ids"][0][j]
                if doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    # 距离转换为相似度（cosine distance → similarity）
                    distance = results["distances"][0][j]
                    similarity = 1.0 - distance
                    all_results.append({
                        "id": doc_id,
                        "text": results["documents"][0][j],
                        "metadata": results["metadatas"][0][j] or {},
                        "score": similarity,
                    })

        # 5. 相似度过滤
        filtered = [
            r for r in all_results
            if r["score"] >= self.config.similarity_threshold
        ]

        # 6. 重排序
        if len(filtered) > top_k:
            filtered = self.reranker.rerank(query, filtered, top_n=self.config.rerank_top_n)

        # 7. 取 Top-K
        final_results = filtered[:top_k]

        # 8. 缓存结果
        await self._cache_store(query, final_results)

        logger.info(f"Retrieval: query='{query[:50]}...' -> "
                    f"{len(all_results)} candidates, "
                    f"{len(final_results)} results after filtering")
        return final_results

    async def add_documents(self, documents: List[Dict]) -> int:
        """添加文档到向量数据库

        Args:
            documents: [{"text": ..., "metadata": {...}}, ...]

        Returns:
            添加的文档数
        """
        if not documents:
            return 0

        texts = [doc["text"] for doc in documents]
        metadatas = [doc.get("metadata", {}) for doc in documents]
        ids = [f"doc_{hashlib.md5(doc['text'].encode()).hexdigest()[:16]}"
               for doc in documents]

        embeddings = await self._get_embeddings(texts)

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        logger.info(f"Added {len(documents)} documents to collection")
        return len(documents)

    async def delete_documents(self, doc_id: str) -> int:
        """删除指定文档的所有分段"""
        results = self.collection.get(
            where={"doc_id": doc_id},
            include=["metadatas"],
        )
        if results["ids"]:
            self.collection.delete(ids=results["ids"])
            count = len(results["ids"])
            logger.info(f"Deleted {count} chunks for doc_id={doc_id}")
            return count
        return 0

    def get_collection_stats(self) -> Dict:
        """获取集合统计信息"""
        return {
            "name": self.config.chroma_collection,
            "document_count": self.collection.count(),
        }
