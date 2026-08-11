"""LuomiNest LLM 端口定义（L1 能力内核）。

LLMProvider 是能力内核对外暴露的唯一协议抽象（Port）：
- 内核只定义契约，不感知任何具体供应商协议细节
- 所有供应商实现（Adapter）位于 adapters/ 子包，向内实现本端口
- 依赖方向：adapters → ports（外层依赖内层，禁止反向）

LLMProvider 统一使用 LLMRequest / LLMResponse / StreamEvent，
明确接口契约，消除旧版返回类型不一致问题。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from loguru import logger

from app.runtime.provider.llm.types import LLMRequest, LLMResponse, StreamEvent


class LLMProvider(ABC):
    """LLM 供应商抽象基类（端口）。

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

    def get_context_window(self, model: str) -> int:
        """返回给定模型的上下文窗口大小（token 数）。

        默认返回 16384，子类应按模型覆盖以提供准确值。
        """
        return 16384

    def sanitize_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """清洗消息列表，确保符合 OpenAI 兼容 API 要求。

        执行以下规则：
        1. 移除 content 为空字符串或 None 的消息（保留 role=system）
        2. 确保消息列表以 user 或 system 角色开头
        3. 确保 tool 消息的 tool_call_id 配对完整
        """
        if not messages:
            return messages

        # Step 1: 移除空 content 消息（保留 system）
        cleaned: list[dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content")
            if role == "system":
                cleaned.append(msg)
            elif role == "tool":
                # tool 消息没有 content 字段要求，保留
                cleaned.append(msg)
            elif content is None or (isinstance(content, str) and content.strip() == ""):
                # 检查是否有 tool_calls（assistant 消息可能 content 为空但有 tool_calls）
                if role == "assistant" and msg.get("tool_calls"):
                    cleaned.append(msg)
                # 否则跳过空消息
                continue
            else:
                cleaned.append(msg)

        # Step 2: 确保以 user 或 system 开头
        if cleaned and cleaned[0].get("role") == "assistant":
            logger.debug("sanitize_messages: 消息列表以 assistant 开头，插入空 user 消息")
            cleaned.insert(0, {"role": "user", "content": " "})

        # Step 3: 确保 tool 消息的 tool_call_id 配对完整
        # 收集所有 assistant 消息中的 tool_call ids
        assistant_tool_call_ids: set[str] = set()
        for msg in cleaned:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    tc_id = tc.get("id")
                    if tc_id:
                        assistant_tool_call_ids.add(tc_id)

        # 收集所有 tool result 消息的 tool_call_id
        tool_result_ids: set[str] = set()
        for msg in cleaned:
            if msg.get("role") == "tool":
                tc_id = msg.get("tool_call_id")
                if tc_id:
                    tool_result_ids.add(tc_id)

        # 如果有 tool result 没有对应的 assistant tool_calls，记录警告并移除孤立 tool 消息
        orphan_ids = tool_result_ids - assistant_tool_call_ids
        if orphan_ids:
            logger.warning(f"sanitize_messages: 发现 {len(orphan_ids)} 个孤立的 tool result 消息，将移除")
            cleaned = [
                msg for msg in cleaned
                if not (msg.get("role") == "tool" and msg.get("tool_call_id") in orphan_ids)
            ]

        return cleaned

    async def aclose(self) -> None:
        """关闭 httpx 客户端等资源。子类可覆写。"""
        ...
