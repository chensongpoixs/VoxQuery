"""ASR 服务客户端"""

import logging
import httpx
from typing import Optional
from app.config import Settings

logger = logging.getLogger(__name__)


class ASRClient:
    def __init__(self, settings: Settings):
        self.base_url = settings.asr_service_url
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def transcribe(
        self, audio_bytes: bytes, filename: str = "audio.wav", language: Optional[str] = None
    ) -> dict:
        """音频转文字"""
        url = f"{self.base_url}/v1/transcribe"
        params = {}
        if language:
            params["language"] = language

        files = {"file": (filename, audio_bytes, "audio/wav")}
        response = await self.http_client.post(url, params=params, files=files)
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
