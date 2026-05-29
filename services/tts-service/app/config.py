"""TTS 语音合成服务配置"""

from pydantic_settings import BaseSettings


class TTSServiceConfig(BaseSettings):
    model_name: str = "CosyVoice2"
    model_path: str = "/models/cosyvoice2"
    host: str = "0.0.0.0"
    port: int = 8006

    default_voice: str = "default"       # 默认音色 ID
    sample_rate: int = 24000             # 采样率
    device: str = "cuda"

    class Config:
        env_prefix = "TTS_"
        env_file = ".env"
