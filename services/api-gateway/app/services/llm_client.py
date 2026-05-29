"""LLM 服务客户端 —— 封装对 vLLM API 的调用"""

import logging
import httpx
from typing import List, Dict, Optional, AsyncIterator, Any
from app.config import Settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, settings: Settings):
        self.base_url = settings.llm_service_url
        self.model_name = settings.llm_model_name
        self.max_tokens = settings.llm_max_tokens
        self.temperature = settings.llm_temperature
        self.http_client = httpx.AsyncClient(timeout=60.0)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """调用 LLM 对话（非流式）"""
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": kwargs.get("model", self.model_name),
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
            "stream": False,
        }

        response = await self.http_client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        return {
            "content": data["choices"][0]["message"]["content"],
            "usage": data.get("usage", {}),
            "model": data.get("model", ""),
        }

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> AsyncIterator[str]:
        """调用 LLM 对话（流式），逐 token 返回"""
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": kwargs.get("model", self.model_name),
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
            "stream": True,
        }

        async with self.http_client.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        import json
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except Exception:
                        continue

    async def health(self) -> bool:
        try:
            response = await self.http_client.get(f"{self.base_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self):
        await self.http_client.aclose()
