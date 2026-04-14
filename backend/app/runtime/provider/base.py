from abc import ABC, abstractmethod
from typing import AsyncIterator


class LLMProvider(ABC):
    provider_name: str = "base"

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
        **kwargs
    ) -> str | AsyncIterator[str]:
        pass

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        pass


class STTProvider(ABC):
    provider_name: str = "base"

    @abstractmethod
    async def transcribe(self, audio_data: bytes, format: str = "wav") -> str:
        pass


class TTSProvider(ABC):
    provider_name: str = "base"

    @abstractmethod
    async def synthesize(self, text: str, voice: str = "default") -> bytes:
        pass


class EmbeddingProvider(ABC):
    provider_name: str = "base"

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        pass