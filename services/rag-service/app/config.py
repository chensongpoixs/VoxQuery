"""RAG 检索增强服务配置"""

from pydantic_settings import BaseSettings


class RAGServiceConfig(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8003

    # 依赖服务
    embedding_service_url: str = "http://embedding-service:8002"
    chroma_host: str = "chromadb"
    chroma_port: int = 8004
    chroma_collection: str = "energy_knowledge"

    # 检索参数
    top_k: int = 5
    rerank_top_n: int = 3
    similarity_threshold: float = 0.65

    # 文档分段参数
    chunk_size: int = 512
    chunk_overlap: int = 50

    # Redis 缓存
    redis_host: str = "redis"
    redis_port: int = 6379
    retrieval_cache_ttl: int = 3600

    class Config:
        env_prefix = "RAG_"
        env_file = ".env"
