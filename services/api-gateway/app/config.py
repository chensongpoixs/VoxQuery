"""API Gateway 配置管理"""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 服务基本信息
    project_name: str = "KB Q&A System"
    version: str = "1.0.0"
    environment: str = "development"
    log_level: str = "INFO"

    # HTTP
    host: str = "0.0.0.0"
    port: int = 8000

    # JWT
    jwt_secret_key: str = "default-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # 下游服务 URL
    llm_service_url: str = "http://llm-service:8001"
    embedding_service_url: str = "http://embedding-service:8002"
    rag_service_url: str = "http://rag-service:8003"
    asr_service_url: str = "http://asr-service:8005"
    tts_service_url: str = "http://tts-service:8006"

    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0
    conversation_ttl: int = 86400

    # LLM
    llm_model_name: str = "google/gemma-3-27b-it"
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.3
    llm_context_window: int = 8192

    # 请求限制
    max_text_length: int = 4096
    max_audio_size_mb: int = 10

    class Config:
        env_file = ".env"
