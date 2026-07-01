"""LuomiNest Provider 抽象基类。

LLMProvider 统一使用 LLMRequest / LLMResponse / StreamEvent，
明确接口契约，消除旧版返回类型不一致问题。
"""
from abc import ABC, abstractmethod
from typing import AsyncIterator

from app.runtime.provider.llm.types import LLMRequest, LLMResponse, StreamEvent


class LLMProvider(ABC):
    """LLM 供应商抽象基类。

    所有 LLM 供应商实现必须继承此类并提供 chat / chat_stream / embed / list_models 方法。
    chat 返回 LLMResponse，chat_stream 返回 StreamEvent 流，
    禁止返回 str / dict 等不一致类型。
    """

    provider_name: str = "base"

    @abstractmethod
    async def chat(self, request: LLMRequest) -> LLMResponse:
        """非流式聊天，统一返回 LLMResponse。"""
        ...

    @abstractmethod
    async def chat_stream(self, request: LLMRequest) -> AsyncIterator[StreamEvent]:
        """流式聊天，统一返回 StreamEvent 流。"""
        ...

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """文本嵌入。"""
        ...

    @abstractmethod
    async def list_models(self) -> list[dict]:
        """列出可用模型。"""
        ...

    def supports_tool_calls(self, model: str = "") -> bool:
        """是否支持工具调用。默认乐观 True，失败时由中间件降级。"""
        return True

    def supports_multimodal(self, model: str = "") -> bool:
        """是否支持多模态。默认 False。"""
        return False

    async def aclose(self) -> None:
        """关闭 httpx 客户端等资源。子类可覆写。"""
        ...


class STTProvider(ABC):
    provider_name: str = "base"

    @abstractmethod
    async def transcribe(self, audio_data: bytes, format: str = "wav") -> str:
        ...


class TTSProvider(ABC):
    provider_name: str = "base"

    @abstractmethod
    async def synthesize(self, text: str, voice: str = "default") -> bytes:
        ...


class EmbeddingProvider(ABC):
    provider_name: str = "base"

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        ...
