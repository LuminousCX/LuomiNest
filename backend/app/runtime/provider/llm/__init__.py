"""LuomiNest LLM 能力内核包。

结构（六边形架构，依赖只能向内）：
- ports.py：LLMProvider 协议抽象（端口）
- adapters/：各协议族实现（适配器），如 chat_completions
- adapter.py：LLMAdapter 门面（供 service 层通过 DI 使用）
- types.py：请求/响应/流事件统一类型
- capabilities.py：能力声明表
"""
from app.runtime.provider.llm.ports import LLMProvider
from app.runtime.provider.llm.types import (
    LLMRequest,
    LLMResponse,
    ProviderCapabilities,
    RouteHint,
    StreamEvent,
)

__all__ = [
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "ProviderCapabilities",
    "RouteHint",
    "StreamEvent",
]
