"""Embedding 向量化服务配置"""

from pydantic_settings import BaseSettings


class EmbeddingServiceConfig(BaseSettings):
    model_name: str = "BAAI/bge-m3"
    model_path: str = "/models/bge-m3"
    host: str = "0.0.0.0"
    port: int = 8002

    max_length: int = 8192
    batch_size: int = 32
    embedding_dim: int = 1024  # BGE-M3 输出维度

    device: str = "cuda"

    class Config:
        env_prefix = "EMBEDDING_"
        env_file = ".env"
