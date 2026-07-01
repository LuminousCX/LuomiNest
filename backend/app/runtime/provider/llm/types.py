"""LuomiNest LLM 类型定义。

集中定义 LLM 请求/响应/事件数据类与路由提示枚举，
供 LLMProvider、LLMAdapter、ToolOrchestrator、中间件链共用，
避免循环依赖。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RouteHint(str, Enum):
    """路由提示：后端根据场景自动选择主模型或推理模型。

    - CHAT：日常对话 / 快速响应 / 简单 Q&A → 主模型
    - REASONER：复杂推理 / 代码生成 / 深度分析 → 推理模型（未配置则回退主模型）
    - AGENT：Agent 任务 / 工具调用 → 主模型（推理模型通常不支持工具调用）
    """
    CHAT = "chat"
    REASONER = "reasoner"
    AGENT = "agent"


@dataclass
class LLMRequest:
    """LLM 请求统一数据类。

    所有 LLM 调用（chat / chat_stream）均通过此对象传递参数，
    中间件可在 before_model 钩子中修改。
    """
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None = None
    model: str = ""
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    stream: bool = False
    return_raw: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def to_kwargs(self) -> dict[str, Any]:
        """转换为 provider 可用的 kwargs（过滤 None 值）。"""
        kwargs: dict[str, Any] = {"model": self.model}
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        if self.max_tokens is not None:
            kwargs["max_tokens"] = self.max_tokens
        if self.top_p is not None:
            kwargs["top_p"] = self.top_p
        kwargs.update(self.extra)
        return kwargs


@dataclass
class LLMResponse:
    """LLM 非流式响应统一数据类。

    content: 文本内容
    reasoning: 推理内容（已清理）
    tool_calls: OpenAI Function Calling 格式工具调用列表
    finish_reason: 停止原因（stop / tool_calls / length 等）
    usage: token 用量统计
    raw: 原始 API 响应（供需要完整数据的场景使用）
    """
    content: str = ""
    reasoning: str = ""
    tool_calls: list[dict[str, Any]] | None = None
    finish_reason: str = "stop"
    usage: dict[str, Any] | None = None
    raw: dict[str, Any] | None = None

    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)

    def to_dict(self) -> dict[str, Any]:
        """转换为旧版 dict 格式（向后兼容 LLMAdapter.chat 的 return_raw=True 场景）。"""
        return {
            "content": self.content,
            "reasoning": self.reasoning,
            "tool_calls": self.tool_calls or [],
            "role": "assistant",
        }


class StreamEvent:
    """LLM 流式事件。

    type: content / reasoning / tool_call_delta / finish_reason / usage / done
    data: 事件数据字典
    """
    __slots__ = ("type", "data")

    def __init__(self, event_type: str, data: dict[str, Any] | None = None):
        self.type = event_type
        self.data = data or {}

    def __repr__(self) -> str:
        return f"StreamEvent(type={self.type!r}, data_keys={list(self.data.keys())})"
