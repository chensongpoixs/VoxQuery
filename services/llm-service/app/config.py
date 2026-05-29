"""LLM 推理服务配置"""

import os
from pydantic_settings import BaseSettings


class LLMServiceConfig(BaseSettings):
    model_name: str = "google/gemma-3-27b-it"
    model_path: str = "/models/gemma3"
    host: str = "0.0.0.0"
    port: int = 8001

    # 推理参数
    max_tokens: int = 2048
    temperature: float = 0.3
    top_p: float = 0.9
    context_window: int = 8192
    tensor_parallel_size: int = 2
    quantization: str = "awq"  # awq / gptq / squeezellm
    max_concurrent: int = 4

    # 显存优化
    gpu_memory_utilization: float = 0.90
    max_num_seqs: int = 4
    kv_cache_dtype: str = "fp8"

    # 模型认证
    hf_token: str = os.getenv("HF_TOKEN", "")

    class Config:
        env_prefix = "LLM_"
        env_file = ".env"
