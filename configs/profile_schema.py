"""
Profile 数据模型 — Pydantic 校验 YAML profile 文件。
"""
from __future__ import annotations

from typing import List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


class ProfileMeta(BaseModel):
    """Profile 元信息"""
    name: str = Field(..., description="Profile 名称，如 single-gpu / multi-gpu")
    description: str = Field("", description="Profile 描述")


class DeploymentConfig(BaseModel):
    """部署模式配置"""
    mode: str = Field(default="docker", description="部署模式: docker | native")


class GpuConfig(BaseModel):
    """GPU 硬件配置"""
    count: int = Field(..., ge=1, le=8, description="GPU 数量")
    models: List[str] = Field(default_factory=list, description="GPU 型号列表")
    memory_per_gpu_gb: int = Field(..., ge=4, description="单卡显存 (GB)")


class LlmServiceConfig(BaseModel):
    """LLM 服务配置"""
    model: str = Field(..., description="模型名称/路径")
    gpu_device: Union[int, List[int]] = Field(..., description="GPU 设备索引")
    tensor_parallel_size: int = Field(default=1, ge=1, le=8)
    quantization: str = Field(default="awq", description="量化方式: awq | int4 | int8 | none")
    context_window: int = Field(default=8192, ge=512, le=131072)
    max_num_seqs: int = Field(default=4, ge=1, le=128)
    gpu_memory_utilization: float = Field(default=0.90, ge=0.1, le=1.0)
    kv_cache_dtype: str = Field(default="auto", description="KV cache 数据类型")

    @field_validator("gpu_device", mode="before")
    @classmethod
    def coerce_gpu_device(cls, v):
        """统一处理单值和列表 — YAML 中可写 0 或 [0, 1]"""
        if isinstance(v, list):
            return [int(x) for x in v]
        return int(v)

    def _gpu_devices_list(self) -> List[int]:
        """返回规范化的 GPU 设备列表"""
        if isinstance(self.gpu_device, list):
            return self.gpu_device
        return [self.gpu_device]

    def cuda_visible_devices(self) -> str:
        return ",".join(str(d) for d in self._gpu_devices_list())


class EmbeddingServiceConfig(BaseModel):
    """Embedding 服务配置"""
    model: str = Field(..., description="模型名称/路径")
    gpu_device: int = Field(..., ge=0)
    batch_size: int = Field(default=32, ge=1, le=256)
    max_length: int = Field(default=8192, ge=128, le=32768)

    def cuda_visible_devices(self) -> str:
        return str(self.gpu_device)


class AsrServiceConfig(BaseModel):
    """ASR 语音识别服务配置"""
    model: str = Field(default="large-v3")
    gpu_device: int = Field(..., ge=0)
    vad_threshold: float = Field(default=0.5, ge=0.1, le=0.9)
    language: str = Field(default="zh")

    def cuda_visible_devices(self) -> str:
        return str(self.gpu_device)


class TtsServiceConfig(BaseModel):
    """TTS 语音合成服务配置"""
    model: str = Field(default="CosyVoice2-0.5B")
    gpu_device: int = Field(..., ge=0)
    default_voice: str = Field(default="default")
    sample_rate: int = Field(default=24000, ge=8000, le=48000)

    def cuda_visible_devices(self) -> str:
        return str(self.gpu_device)


class ServicesConfig(BaseModel):
    """所有服务配置"""
    llm: LlmServiceConfig
    embedding: EmbeddingServiceConfig
    asr: AsrServiceConfig
    tts: TtsServiceConfig


class ProfileSpec(BaseModel):
    """完整 Profile 顶层模型"""
    profile: ProfileMeta
    deployment: DeploymentConfig = Field(default_factory=DeploymentConfig)
    gpus: GpuConfig
    services: ServicesConfig
    models_dir: str = Field(default="./models", description="模型本地存储路径")
    project_name: str = Field(default="kb-qa")

    # ---------- 交叉验证 ----------

    @model_validator(mode="after")
    def validate_device_ids_in_range(self):
        """校验所有 GPU device 索引在有效范围内"""
        max_id = self.gpus.count - 1
        for svc_name, svc in [
            ("llm", self.services.llm),
            ("embedding", self.services.embedding),
            ("asr", self.services.asr),
            ("tts", self.services.tts),
        ]:
            devices = [svc.gpu_device] if isinstance(svc.gpu_device, int) else svc.gpu_device
            for d in devices:
                if d < 0 or d > max_id:
                    raise ValueError(
                        f"services.{svc_name}.gpu_device={d} 超出 GPU 范围 [0, {max_id}]"
                    )
        return self

    @model_validator(mode="after")
    def validate_tp_size_matches_devices(self):
        """张量并行尺寸必须与分配的 GPU 数量一致"""
        llm = self.services.llm
        ndev = 1 if isinstance(llm.gpu_device, int) else len(llm.gpu_device)
        if llm.tensor_parallel_size != ndev:
            raise ValueError(
                f"llm.tensor_parallel_size={llm.tensor_parallel_size} "
                f"与 gpu_device 数量 ({ndev}) 不匹配"
            )
        return self

    @model_validator(mode="after")
    def warn_shared_gpu_high_memory(self):
        """警告：共享 GPU 上模型过多可能导致显存不足"""
        # 收集每个 GPU 上的服务
        gpu_services: dict[int, list[str]] = {}
        for svc_name, svc in [
            ("llm", self.services.llm),
            ("embedding", self.services.embedding),
            ("asr", self.services.asr),
            ("tts", self.services.tts),
        ]:
            devices = [svc.gpu_device] if isinstance(svc.gpu_device, int) else svc.gpu_device
            for d in devices:
                gpu_services.setdefault(d, []).append(svc_name)

        for gpu_id, svc_list in gpu_services.items():
            if len(svc_list) >= 4:
                mb = self.gpus.memory_per_gpu_gb * 1024
                print(
                    f"[WARN] GPU {gpu_id} 承载 {len(svc_list)} 个服务 ({', '.join(svc_list)})，"
                    f"请确认总显存需求 ≤ {mb}MB"
                )
        return self

    # ---------- 便捷方法 ----------

    def get_model_list(self) -> list[dict]:
        """返回需要下载的模型列表"""
        return [
            {"name": self.services.llm.model, "dir": "gemma3", "size_gb": 50},
            {"name": self.services.embedding.model, "dir": "bge-m3", "size_gb": 2},
            {"name": self.services.asr.model, "dir": "whisper", "size_gb": 3},
            {"name": self.services.tts.model, "dir": "cosyvoice2", "size_gb": 2},
        ]

    def to_env_vars(self) -> dict[str, str]:
        """导出为环境变量字典（供 .env 文件使用）"""
        llm = self.services.llm
        emb = self.services.embedding
        asr = self.services.asr
        tts = self.services.tts

        return {
            # 全局
            "PROJECT_NAME": self.project_name,
            "DEPLOYMENT_MODE": self.deployment.mode,
            "HARDWARE_PROFILE": self.profile.name,
            "MODELS_DIR": self.models_dir,
            # LLM
            "LLM_MODEL_NAME": llm.model,
            "LLM_TENSOR_PARALLEL_SIZE": str(llm.tensor_parallel_size),
            "LLM_QUANTIZATION": llm.quantization,
            "LLM_CONTEXT_WINDOW": str(llm.context_window),
            "LLM_MAX_CONCURRENT": str(llm.max_num_seqs),
            "LLM_GPU_MEMORY_UTILIZATION": str(llm.gpu_memory_utilization),
            "LLM_KV_CACHE_DTYPE": llm.kv_cache_dtype,
            "LLM_MAX_TOKENS": "2048",
            "LLM_TEMPERATURE": "0.3",
            "LLM_TOP_P": "0.9",
            "NVIDIA_VISIBLE_DEVICES_LLM": llm.cuda_visible_devices(),
            # Embedding
            "EMBEDDING_MODEL_NAME": emb.model,
            "EMBEDDING_BATCH_SIZE": str(emb.batch_size),
            "EMBEDDING_MAX_LENGTH": str(emb.max_length),
            "NVIDIA_VISIBLE_DEVICES_EMBEDDING": emb.cuda_visible_devices(),
            # ASR
            "ASR_MODEL_NAME": asr.model,
            "ASR_LANGUAGE": asr.language,
            "ASR_VAD_THRESHOLD": str(asr.vad_threshold),
            # TTS
            "TTS_DEFAULT_VOICE": tts.default_voice,
            "TTS_SAMPLE_RATE": str(tts.sample_rate),
            "NVIDIA_VISIBLE_DEVICES_ASR_TTS": str(tts.gpu_device),
            # JWT
            "JWT_SECRET_KEY": "change-me-to-a-random-secret-key",
            "JWT_ALGORITHM": "HS256",
            "JWT_EXPIRE_MINUTES": "1440",
            # 基础设施
            "REDIS_HOST": "redis",
            "REDIS_PORT": "6379",
            "REDIS_DB": "0",
            "REDIS_PASSWORD": "",
            "CHROMA_HOST": "chromadb",
            "CHROMA_PORT": "8004",
            "CHROMA_COLLECTION_NAME": "kb_knowledge",
            # RAG
            "RAG_TOP_K": "5",
            "RAG_RERANK_TOP_N": "3",
            "RAG_SIMILARITY_THRESHOLD": "0.65",
            "RETRIEVAL_CACHE_TTL": "3600",
            "CONVERSATION_TTL": "86400",
            # 知识库
            "KNOWLEDGE_CHUNK_SIZE": "512",
            "KNOWLEDGE_CHUNK_OVERLAP": "50",
            # 日志
            "ENVIRONMENT": "development",
            "LOG_LEVEL": "INFO",
            # 模型下载
            "HF_ENDPOINT": "https://hf-mirror.com",
            "USE_MODELSCOPE": "true",
            # API
            "API_GATEWAY_HOST": "0.0.0.0",
            "API_GATEWAY_PORT": "8000",
            "API_GATEWAY_WORKERS": "4",
        }
