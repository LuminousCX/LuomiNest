"""已知模型上下文窗口长度（假数据/知识库）。

当供应商 /models 接口返回模型列表时，后端使用本模块推断每个模型的最大上下文长度；
未命中的模型回退到 provider 级 capabilities.default_context_window。

数据主要参考各厂商官方文档与社区汇总，覆盖常见商业/开源模型；
本地模型（Ollama 等）因 num_ctx 可配置，仅给出保守默认值。
"""

from __future__ import annotations


# 模型 ID 子串 -> 最大上下文 tokens（支持部分匹配，区分大小写取最长相等子串）
MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    # OpenAI
    "gpt-4.1-mini": 1_000_000,
    "gpt-4.1-nano": 1_000_000,
    "gpt-4.1": 1_000_000,
    "gpt-4.5-preview": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4o": 128_000,
    "gpt-4-turbo": 128_000,
    "gpt-4-0125-preview": 128_000,
    "gpt-4-1106-preview": 128_000,
    "gpt-4": 8_192,
    "gpt-3.5-turbo": 16_384,
    "o3-mini": 200_000,
    "o3": 200_000,
    "o1-mini": 128_000,
    "o1": 200_000,
    "o4-mini": 200_000,
    # Anthropic Claude
    "claude-opus-4-20250514": 200_000,
    "claude-sonnet-4-20250514": 200_000,
    "claude-opus-4": 200_000,
    "claude-sonnet-4": 200_000,
    "claude-3-5-sonnet": 200_000,
    "claude-3-5-haiku": 200_000,
    "claude-3-haiku": 200_000,
    "claude-3-opus": 200_000,
    "claude-3-sonnet": 200_000,
    # DeepSeek
    "deepseek-chat": 64_000,
    "deepseek-reasoner": 64_000,
    "deepseek-coder": 64_000,
    "deepseek-v3": 64_000,
    "deepseek-r1": 64_000,
    # Google Gemini
    "gemini-2.5-pro": 1_000_000,
    "gemini-2.5-flash": 1_000_000,
    "gemini-2.0-flash": 1_000_000,
    "gemini-2.0-flash-lite": 1_000_000,
    "gemini-2.0-pro": 2_000_000,
    "gemini-1.5-pro": 2_000_000,
    "gemini-1.5-flash": 1_000_000,
    "gemini-1.5-flash-8b": 1_000_000,
    # Moonshot / Kimi
    "moonshot-v1-8k": 8_192,
    "moonshot-v1-32k": 32_768,
    "moonshot-v1-128k": 131_072,
    "moonshot-v1-1m": 1_000_000,
    "kimi-k2": 256_000,
    "kimi-k2-0711-preview": 256_000,
    "kimi-k1.5": 256_000,
    # Zhipu GLM
    "glm-4-flash": 128_000,
    "glm-4-plus": 128_000,
    "glm-4-long": 1_000_000,
    "glm-4-air": 128_000,
    "glm-4": 128_000,
    "glm-5": 128_000,
    # Alibaba Qwen
    "qwen-plus": 131_072,
    "qwen-turbo": 131_072,
    "qwen-max": 32_768,
    "qwen-long": 10_000_000,
    "qwen2.5": 131_072,
    "qwen2.5-72b-instruct": 131_072,
    "qwen2.5-32b-instruct": 131_072,
    "qwen2.5-14b-instruct": 131_072,
    "qwen2.5-7b-instruct": 131_072,
    "qwen3": 131_072,
    "qwen3-235b-a22b": 128_000,
    "qwen3-30b-a3b": 128_000,
    "qwen3-4b": 128_000,
    "qwen3-0.6b": 32_768,
    "qwen-coder-plus": 131_072,
    "qwen-coder-turbo": 131_072,
    # Baichuan
    "baichuan": 32_768,
    # 360
    "360gpt": 8_192,
    # StepFun
    "step-2": 32_768,
    "step-1": 8_192,
    "step-1v": 32_768,
    "step-1-flash": 8_192,
    # MiniMax
    "minimax-text-01": 1_000_000,
    "abab6.5": 8_192,
    "abab6": 8_192,
    # xAI Grok
    "grok-3": 1_000_000,
    "grok-2": 131_072,
    "grok-2-mini": 131_072,
    "grok-1.5": 131_072,
    # Mistral
    "mistral-large": 128_000,
    "mistral-small": 128_000,
    "mistral-medium": 32_768,
    "codestral": 32_768,
    "pixtral": 128_000,
    # Cohere
    "command-r-plus": 128_000,
    "command-r": 128_000,
    # AI21
    "jamba": 256_000,
    # Nvidia NIM
    "llama-3.1-405b": 128_000,
    "llama-3.1-70b": 128_000,
    "llama-3.1-8b": 128_000,
    "llama-3.1-nemotron": 128_000,
    "mistralai/mixtral-8x22b": 65_536,
    # Together / Fireworks / HuggingFace
    "llama-3.3-70b": 128_000,
    "llama-3.3": 128_000,
    "llama-3.2": 128_000,
    "llama-3.1": 128_000,
    "mixtral-8x7b": 32_768,
    "mixtral-8x22b": 65_536,
    # Fireworks specific
    "accounts/fireworks/models/llama-v3p3-70b-instruct": 131_072,
    "accounts/fireworks/models/llama-v3p3-8b-instruct": 131_072,
    "accounts/fireworks/models/llama-v3-70b-instruct": 8_192,
    # OpenRouter / Aggregators（按模型名前缀推断）
    "openai/gpt-4o": 128_000,
    "openai/gpt-4.1": 1_000_000,
    "openai/gpt-4.5-preview": 128_000,
    "anthropic/claude-3.5-sonnet": 200_000,
    "anthropic/claude-opus-4": 200_000,
    "anthropic/claude-sonnet-4": 200_000,
    "google/gemini-2.0-flash": 1_000_000,
    "google/gemini-2.5-pro": 1_000_000,
    "meta-llama/llama-3.3-70b": 128_000,
    "meta-llama/llama-4-maverick": 256_000,
    "meta-llama/llama-4-scout": 128_000,
    "deepseek/deepseek-chat": 64_000,
    "deepseek/deepseek-r1": 64_000,
    "qwen/qwen2.5": 131_072,
    "qwen/qwen3": 128_000,
    "nvidia/llama-3.3-70b-instruct": 128_000,
    "x-ai/grok-3": 131_072,
    # Local / Ollama 保守默认（num_ctx 可配置）
    "qwen2.5:7b": 32_768,
    "qwen2.5:14b": 32_768,
    "qwen2.5:32b": 32_768,
    "qwen3": 32_768,
    "llama3.1:8b": 128_000,
    "llama3.2:3b": 128_000,
    "llama3.3:70b": 128_000,
    "llama4-maverick": 256_000,
    "llama4-scout": 128_000,
    "mistral:7b": 32_768,
    "mistral-small:24b": 128_000,
    "deepseek-r1": 64_000,
    "gemma2:9b": 8_192,
    "gemma2:27b": 8_192,
    "gemma3:4b": 128_000,
    "gemma3:12b": 128_000,
    "gemma3:27b": 128_000,
    "phi3": 4_096,
    "phi4": 16_384,
    "phi4-mini": 128_000,
    "tinyllama": 2_048,
    "command-a": 256_000,
    "aya-expanse:8b": 8_192,
    "aya-expanse:32b": 128_000,
    # 小米
    "mimo-v2": 32_768,
    # 百度
    "ernie-4.0": 8_192,
    "ernie-3.5": 8_192,
    "ernie-speed": 131_072,
    # 字节豆包
    "doubao-pro-32k": 32_768,
    "doubao-pro-128k": 131_072,
    "doubao-lite-32k": 32_768,
    "doubao-lite-128k": 131_072,
    "doubao-vision": 131_072,
    # 书生
    "internlm": 32_768,
    # Yi
    "yi-large": 32_768,
    "yi-medium": 16_384,
    # 讯飞星火
    "spark": 8_192,
    # 腾讯混元
    "hunyuan": 32_768,
}


def infer_max_context_tokens(model_id: str, provider_name: str, default_context_window: int = 0) -> int:
    """根据模型 ID 推断最大上下文长度。

    匹配策略：优先精确匹配；否则取最长公共前缀匹配。
    未命中时回退 provider 级默认；再未命中返回 default_context_window。
    """
    if not model_id:
        return default_context_window or 16_384

    # 1) 精确匹配
    if model_id in MODEL_CONTEXT_WINDOWS:
        return MODEL_CONTEXT_WINDOWS[model_id]

    # 2) 忽略大小写精确匹配
    lower_model_id = model_id.lower()
    for key, value in MODEL_CONTEXT_WINDOWS.items():
        if key.lower() == lower_model_id:
            return value

    # 3) 最长前缀匹配
    best_match: str | None = None
    for key in MODEL_CONTEXT_WINDOWS:
        if lower_model_id.startswith(key.lower()):
            if best_match is None or len(key) > len(best_match):
                best_match = key

    if best_match is not None:
        return MODEL_CONTEXT_WINDOWS[best_match]

    # 4) 按 provider 能力表兜底
    if default_context_window > 0:
        return default_context_window

    # 5) 通用兜底
    return 16_384
