from typing import AsyncIterator
from app.runtime.provider.base import LLMProvider
from app.core.config import settings
from loguru import logger
import httpx


class OpenAIProvider(LLMProvider):
    provider_name = "openai"

    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.base_url = settings.OPENAI_BASE_URL or "https://api.openai.com/v1"
        self.model = "gpt-4o-mini"

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
        **kwargs
    ) -> str | AsyncIterator[str]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "model": kwargs.get("model", self.model),
                "messages": messages,
                "stream": stream,
            }
            if tools:
                payload["tools"] = tools

            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": "text-embedding-3-small", "input": text},
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]


class OllamaProvider(LLMProvider):
    provider_name = "ollama"

    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = "qwen2.5:7b"

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
        **kwargs
    ) -> str | AsyncIterator[str]:
        async with httpx.AsyncClient(timeout=120.0) as client:
            payload = {
                "model": kwargs.get("model", self.model),
                "messages": messages,
                "stream": stream,
            }
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"]

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": text},
            )
            resp.raise_for_status()
            return resp.json()["embedding"]
