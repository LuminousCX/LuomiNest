"""LuomiNest LLM 适配器子包。

汇集各协议族的适配器（均向内实现 ports.py 的 LLMProvider 端口）：
- chat_completions：OpenAI /chat/completions 兼容协议（覆盖 32 个预置供应商模板）

未来新增非兼容协议（如原生 Anthropic Messages、Responses API）时，
在此子包新增适配器模块，并通过 ProviderRegistry 注册即可。
"""
from app.runtime.provider.llm.adapters.chat_completions import OpenAICompatibleProvider

__all__ = ["OpenAICompatibleProvider"]
