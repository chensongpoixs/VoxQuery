"""ASR 语音识别服务配置"""

from pydantic_settings import BaseSettings


class ASRServiceConfig(BaseSettings):
    model_name: str = "large-v3"
    model_path: str = "/models/whisper"
    host: str = "0.0.0.0"
    port: int = 8005

    default_language: str = "zh"  # 默认中文，auto = 自动检测
    vad_threshold: float = 0.5
    beam_size: int = 5

    # 计算设备
    device: str = "cuda"
    compute_type: str = "float16"

    class Config:
        env_prefix = "ASR_"
        env_file = ".env"
