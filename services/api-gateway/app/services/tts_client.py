"""TTS 服务客户端"""

import logging
import httpx
from typing import Optional, AsyncIterator
from app.config import Settings

logger = logging.getLogger(__name__)


class TTSClient:
    def __init__(self, settings: Settings):
        self.base_url = settings.tts_service_url
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def synthesize(
        self, text: str, voice_id: str = "default", speed: float = 1.0
    ) -> bytes:
        """文字转语音"""
        url = f"{self.base_url}/v1/tts"
        response = await self.http_client.post(url, json={
            "text": text,
            "voice_id": voice_id,
            "speed": speed,
            "stream": False,
        })
        response.raise_for_status()
        return response.content

    async def synthesize_stream(
        self, text: str, voice_id: str = "default", speed: float = 1.0
    ) -> AsyncIterator[bytes]:
        """流式语音合成"""
        url = f"{self.base_url}/v1/tts/stream"
        async with self.http_client.stream("POST", url, json={
            "text": text,
            "voice_id": voice_id,
            "speed": speed,
            "stream": True,
        }) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                yield chunk

    async def list_voices(self) -> list:
        """获取音色列表"""
        url = f"{self.base_url}/voices"
        response = await self.http_client.get(url)
        response.raise_for_status()
        return response.json()

    async def clone_voice(self, audio_bytes: bytes, voice_name: str, filename: str = "sample.wav") -> dict:
        """克隆音色"""
        url = f"{self.base_url}/v1/voice/clone"
        files = {"file": (filename, audio_bytes, "audio/wav")}
        params = {"voice_name": voice_name}
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
