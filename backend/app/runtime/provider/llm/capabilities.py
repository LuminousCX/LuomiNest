"""LuomiNest Provider 能力声明中心。

集中定义每个 Provider 的能力矩阵，支持：
- 按 provider_name 查询默认能力
- 按 model 名称进行能力覆盖（MODEL_CAPABILITY_OVERRIDES）
- 运行时降级/恢复某项能力（runtime_disable / runtime_enable）

设计原则：
1. 静态声明为主（PROVIDER_CAPABILITIES），运行时降级为辅
2. 不可变 dataclass 实例 + dataclasses.replace 实现覆盖，避免副作用
3. 向后兼容：旧代码仍可调用 provider.supports_tool_calls() 等方法
"""
from __future__ import annotations

from dataclasses import replace
from loguru import logger

from app.runtime.provider.llm.types import ProviderCapabilities


# ──────────────────────────────────────────────────────────────
# 每个 provider 的默认能力
# ──────────────────────────────────────────────────────────────

PROVIDER_CAPABILITIES: dict[str, ProviderCapabilities] = {
    "openai": ProviderCapabilities(
        supports_tool_calls=True,
        supports_streaming=True,
        supports_vision=True,
        supports_response_format=True,
        supports_prompt_caching=True,
        supports_stream_options=True,
        default_context_window=128_000,
    ),
    "anthropic": ProviderCapabilities(
        supports_tool_calls=True,
        supports_streaming=True,
        supports_vision=True,
        supports_prompt_caching=True,
        supports_thinking=True,
        thinking_style="anthropic",
        default_context_window=200_000,
    ),
    "deepseek": ProviderCapabilities(
        supports_tool_calls=True,
        supports_streaming=True,
        supports_thinking=True,
        thinking_style="deepseek",
        default_context_window=64_000,
    ),
    "google": ProviderCapabilities(
        supports_tool_calls=True,
        supports_streaming=True,
        supports_vision=True,
        default_context_window=1_000_000,
    ),
    "dashscope": ProviderCapabilities(
        supports_tool_calls=True,
        supports_streaming=True,
        supports_vision=True,
        supports_thinking=True,
        thinking_style="dashscope",
        default_context_window=131_072,
    ),
    "moonshot": ProviderCapabilities(
        supports_tool_calls=True,
        supports_streaming=True,
        default_context_window=128_000,
    ),
    "zhipu": ProviderCapabilities(
        supports_tool_calls=True,
        supports_streaming=True,
        supports_vision=True,
        default_context_window=128_000,
    ),
    "mistral": ProviderCapabilities(
        supports_tool_calls=True,
        supports_streaming=True,
        default_context_window=128_000,
    ),
    "groq": ProviderCapabilities(
        supports_tool_calls=True,
        supports_streaming=True,
        default_context_window=8_192,
    ),
    "xai": ProviderCapabilities(
        supports_tool_calls=True,
        supports_streaming=True,
        supports_vision=True,
        default_context_window=131_072,
    ),
    "siliconflow": ProviderCapabilities(
        supports_tool_calls=True,
        supports_streaming=True,
        default_context_window=32_768,
    ),
    "openrouter": ProviderCapabilities(
        supports_tool_calls=True,
        supports_streaming=True,
        default_context_window=128_000,
    ),
    "minimax": ProviderCapabilities(
        supports_tool_calls=True,
        supports_streaming=True,
        supports_thinking=True,
        thinking_style="minimax",
        default_context_window=1_000_000,
    ),
    "ollama": ProviderCapabilities(
        supports_tool_calls=False,
        supports_streaming=True,
        default_context_window=4_096,
        known_unsupported_models=["llama2", "mistral-old"],
    ),
    "lmstudio": ProviderCapabilities(
        supports_tool_calls=False,
        supports_streaming=True,
        default_context_window=4_096,
    ),
    "vllm": ProviderCapabilities(
        supports_tool_calls=False,
        supports_streaming=True,
        default_context_window=4_096,
    ),
    "together": ProviderCapabilities(
        supports_tool_calls=True,
        supports_streaming=True,
        default_context_window=8_192,
    ),
    "fireworks": ProviderCapabilities(
        supports_tool_calls=True,
        supports_streaming=True,
        default_context_window=32_768,
    ),
    "nous": ProviderCapabilities(
        supports_tool_calls=False,
        supports_streaming=True,
        default_context_window=4_096,
    ),
    "nvidia": ProviderCapabilities(
        supports_tool_calls=True,
        supports_streaming=True,
        default_context_window=8_192,
    ),
    "stepfun": ProviderCapabilities(
        supports_tool_calls=True,
        supports_streaming=True,
        default_context_window=8_192,
    ),
    "huggingface": ProviderCapabilities(
        supports_tool_calls=False,
        supports_streaming=True,
        default_context_window=8_192,
    ),
    "arcee": ProviderCapabilities(
        supports_tool_calls=False,
        supports_streaming=True,
        default_context_window=4_096,
    ),
    "gmi": ProviderCapabilities(
        supports_tool_calls=False,
        supports_streaming=True,
        default_context_window=4_096,
    ),
    "vercel": ProviderCapabilities(
        supports_tool_calls=True,
        supports_streaming=True,
        default_context_window=128_000,
    ),
    "custom": ProviderCapabilities(
        supports_tool_calls=True,
        supports_streaming=True,
        default_context_window=16_384,
    ),
}


# ──────────────────────────────────────────────────────────────
# 模型级覆盖（特定模型的能力覆盖）
# ──────────────────────────────────────────────────────────────

MODEL_CAPABILITY_OVERRIDES: dict[str, dict] = {
    # 示例（按需补充）：
    # "gpt-4o": {"supports_vision": True},
    # "o1-mini": {"supports_tool_calls": False},
}


# ──────────────────────────────────────────────────────────────
# 运行时降级记录（某 provider 的某能力在运行时被禁用）
# ──────────────────────────────────────────────────────────────

# provider_name -> set of capability field names that are runtime-disabled
_runtime_disabled: dict[str, set[str]] = {}


# ──────────────────────────────────────────────────────────────
# 公共查询 / 操作接口
# ──────────────────────────────────────────────────────────────

def get_capabilities(
    provider_name: str,
    model: str | None = None,
) -> ProviderCapabilities:
    """获取 provider 的能力声明，支持模型级覆盖与运行时降级。

    优先级（从低到高）：
      1. PROVIDER_CAPABILITIES 中的默认值（或全默认 ProviderCapabilities）
      2. MODEL_CAPABILITY_OVERRIDES 中针对特定模型的覆盖
      3. _runtime_disabled 中运行时降级的能力
    """
    caps = PROVIDER_CAPABILITIES.get(provider_name, ProviderCapabilities())

    # 应用模型级覆盖
    if model and model in MODEL_CAPABILITY_OVERRIDES:
        overrides = MODEL_CAPABILITY_OVERRIDES[model]
        caps = replace(caps, **overrides)

    # 应用运行时降级
    disabled = _runtime_disabled.get(provider_name)
    if disabled:
        disable_kwargs = {field: False for field in disabled if hasattr(caps, field)}
        if disable_kwargs:
            caps = replace(caps, **disable_kwargs)

    return caps


def runtime_disable_capability(provider_name: str, capability: str) -> None:
    """运行时降级某 provider 的某能力。

    典型场景：调用某 provider 的 tool_calls 失败后，动态禁用该能力，
    后续请求将回退到不使用工具调用的路径。
    """
    if provider_name not in _runtime_disabled:
        _runtime_disabled[provider_name] = set()
    _runtime_disabled[provider_name].add(capability)
    logger.info(
        f"[Capabilities] Runtime disabled '{capability}' for provider '{provider_name}'"
    )


def runtime_enable_capability(provider_name: str, capability: str) -> None:
    """恢复某 provider 的某能力（撤销运行时降级）。"""
    disabled = _runtime_disabled.get(provider_name)
    if disabled and capability in disabled:
        disabled.discard(capability)
        if not disabled:
            del _runtime_disabled[provider_name]
        logger.info(
            f"[Capabilities] Runtime re-enabled '{capability}' for provider '{provider_name}'"
        )
