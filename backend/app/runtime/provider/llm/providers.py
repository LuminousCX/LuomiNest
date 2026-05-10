import re
from typing import AsyncIterator
from app.runtime.provider.base import LLMProvider
from loguru import logger
import httpx
import json


def _clean_reasoning_content(raw_reasoning: str) -> str:
    """清理推理内容，去除模型名称、重复文本等噪声

    Ollama 等本地模型可能在 reasoning 字段中返回模型标识符或元数据，
    此函数用于过滤这些非推理内容，确保只保留真正的思考过程。

    处理的场景：
      - 纯模型名重复：qwen3-vl:8bqwen3-vl:8bqwen3-vl:8b...
      - 模型名片段：vl:8bqwen3-vl:8b...
      - 行首/行尾的模型标识符
    """
    if not raw_reasoning:
        return ""

    text = raw_reasoning.strip()

    # 场景1：检测连续重复的模型名称模式（最常见的问题）
    # 匹配类似 "qwen3-vl:8b" 或 "llama-3.1-8b" 的模式重复
    model_name_pattern = r'[a-zA-Z0-9]+(?:-[a-zA-Z0-9.]+)*:[a-zA-Z0-9._-]+'

    # 检查是否整个文本主要由重复的模型名组成
    matches = re.findall(model_name_pattern, text)
    if matches:
        # 计算模型名占总文本的比例
        total_model_chars = sum(len(m) for m in matches)
        ratio = total_model_chars / len(text) if text else 0

        # 如果超过60%的字符都是模型名，认为是噪声
        if ratio > 0.6 and len(text) > 10:
            logger.debug(f"[Provider] Filtered reasoning noise: model_name_ratio={ratio:.2f}, "
                        f"text='{text[:80]}...'")
            return ""

        # 如果有多个相同的模型名重复出现（>=3次），也是噪声
        from collections import Counter
        model_counts = Counter(matches)
        most_common_model, count = model_counts.most_common(1)[0] if model_counts else ("", 0)
        if count >= 3 and len(most_common_model) >= 5:
            logger.debug(f"[Provider] Filtered repeated model name: '{most_common_model}' x{count}")
            return ""

    # 场景2：移除行首/行尾的模型名（保留中间的有效内容）
    # 行首模型名
    text = re.sub(r'^[a-zA-Z0-9_-]+:[a-zA-Z0-9._-]+\s*', '', text)
    # 行尾模型名
    text = re.sub(r'\s*[a-zA-Z0-9_-]+:[a-zA-Z0-9._-]+$', '', text)

    # 场景3：移除孤立的模型名片段（如 "vl:8b" 前后没有其他有意义的内容）
    # 如果清理后内容太短且看起来像片段，直接清空
    if len(text.strip()) < 8:
        # 检查是否还包含模型名特征
        if re.search(r':[a-zA-Z0-9._-]', text):
            logger.debug(f"[Provider] Filtered short fragment: '{text}'")
            return ""

    return text.strip()


PROVIDER_TEMPLATES = {
    "openai": {
        "id": "openai",
        "name": "OpenAI",
        "vendor": "openai_compatible",
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "default_model": "gpt-4o-mini",
        "description": "GPT-4o / o3 flagship models",
    },
    "anthropic": {
        "id": "anthropic",
        "name": "Anthropic",
        "vendor": "openai_compatible",
        "base_url": "https://api.anthropic.com/v1",
        "api_key": "",
        "default_model": "claude-sonnet-4-20250514",
        "description": "Claude Opus / Sonnet series",
    },
    "deepseek": {
        "id": "deepseek",
        "name": "DeepSeek",
        "vendor": "openai_compatible",
        "base_url": "https://api.deepseek.com",
        "api_key": "",
        "default_model": "deepseek-chat",
        "description": "DeepSeek V3 / R1 reasoning models",
    },
    "google": {
        "id": "google",
        "name": "Google Gemini",
        "vendor": "openai_compatible",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "api_key": "",
        "default_model": "gemini-2.0-flash",
        "description": "Gemini 2.0 Flash / Pro",
    },
    "mistral": {
        "id": "mistral",
        "name": "Mistral AI",
        "vendor": "openai_compatible",
        "base_url": "https://api.mistral.ai/v1",
        "api_key": "",
        "default_model": "mistral-small-latest",
        "description": "Mistral / Codestral series",
    },
    "groq": {
        "id": "groq",
        "name": "Groq",
        "vendor": "openai_compatible",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": "",
        "default_model": "llama-3.3-70b-versatile",
        "description": "LPU ultra-fast inference",
    },
    "xai": {
        "id": "xai",
        "name": "xAI",
        "vendor": "openai_compatible",
        "base_url": "https://api.x.ai/v1",
        "api_key": "",
        "default_model": "grok-3-mini-beta",
        "description": "Grok series models",
    },
    "moonshot": {
        "id": "moonshot",
        "name": "Moonshot (Kimi)",
        "vendor": "openai_compatible",
        "base_url": "https://api.moonshot.cn/v1",
        "api_key": "",
        "default_model": "moonshot-v1-8k",
        "description": "Moonshot Kimi long-context API",
    },
    "zhipu": {
        "id": "zhipu",
        "name": "ZhiPu (GLM)",
        "vendor": "openai_compatible",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key": "",
        "default_model": "glm-4-flash",
        "description": "GLM-4 series",
    },
    "dashscope": {
        "id": "dashscope",
        "name": "DashScope (Qwen)",
        "vendor": "openai_compatible",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "",
        "default_model": "qwen-plus",
        "description": "Alibaba Cloud Qwen series",
    },
    "siliconflow": {
        "id": "siliconflow",
        "name": "SiliconFlow",
        "vendor": "openai_compatible",
        "base_url": "https://api.siliconflow.cn/v1",
        "api_key": "",
        "default_model": "Qwen/Qwen2.5-7B-Instruct",
        "description": "SiliconFlow multi-model platform",
    },
    "openrouter": {
        "id": "openrouter",
        "name": "OpenRouter",
        "vendor": "openai_compatible",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": "",
        "default_model": "openai/gpt-4o-mini",
        "description": "Aggregated gateway for 200+ models",
    },
    "together": {
        "id": "together",
        "name": "Together AI",
        "vendor": "openai_compatible",
        "base_url": "https://api.together.xyz/v1",
        "api_key": "",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "description": "Open-source model cloud inference",
    },
    "fireworks": {
        "id": "fireworks",
        "name": "Fireworks AI",
        "vendor": "openai_compatible",
        "base_url": "https://api.fireworks.ai/inference/v1",
        "api_key": "",
        "default_model": "accounts/fireworks/models/llama-v3p3-70b-instruct",
        "description": "High-speed open-source inference",
    },
    "ollama": {
        "id": "ollama",
        "name": "Ollama",
        "vendor": "ollama",
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
        "default_model": "qwen3-vl:8b",
        "description": "Local Ollama inference engine",
    },
    "lmstudio": {
        "id": "lmstudio",
        "name": "LM Studio",
        "vendor": "openai_compatible",
        "base_url": "http://localhost:1234/v1",
        "api_key": "lmstudio",
        "default_model": "",
        "description": "Local LM Studio inference",
    },
    "vllm": {
        "id": "vllm",
        "name": "vLLM",
        "vendor": "openai_compatible",
        "base_url": "http://localhost:8000/v1",
        "api_key": "",
        "default_model": "",
        "description": "Local vLLM high-performance inference",
    },
    "custom": {
        "id": "custom",
        "name": "Custom",
        "vendor": "openai_compatible",
        "base_url": "",
        "api_key": "",
        "default_model": "",
        "description": "Custom OpenAI-compatible endpoint",
    },
}


class OpenAICompatibleProvider(LLMProvider):
    provider_name = "openai_compatible"

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
        default_model: str = "gpt-4o-mini",
        provider_name: str = "openai_compatible",
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.provider_name = provider_name

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
        return_raw: bool = False,
        **kwargs
    ) -> str | dict | AsyncIterator[dict]:
        """调用大模型聊天接口

        参数:
            messages: 对话消息列表
            tools: OpenAI Function Calling 格式工具定义列表
            stream: 是否使用流式响应
            return_raw: 是否返回完整 API 响应（含 tool_calls / reasoning），默认 False 仅返回文本
        """
        if stream:
            return self.chat_stream(messages, tools, **kwargs)

        async with httpx.AsyncClient(timeout=120.0) as client:
            payload = self._build_payload(messages, tools, stream=False, **kwargs)
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._build_headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            if return_raw:
                message = data.get("choices", [{}])[0].get("message", {})
                tool_calls = message.get("tool_calls", [])
                raw_reasoning = message.get("reasoning", "") or message.get("reasoning_content", "")
                # 清理推理内容
                reasoning = _clean_reasoning_content(raw_reasoning)
                return {
                    "content": message.get("content", ""),
                    "reasoning": reasoning,
                    "tool_calls": tool_calls,
                    "role": message.get("role", "assistant"),
                }
            return data["choices"][0]["message"]["content"]

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs
    ) -> AsyncIterator[dict]:
        payload = self._build_payload(messages, tools, stream=True, **kwargs)
        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._build_headers(),
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        choice = data.get("choices", [{}])[0]
                        delta = choice.get("delta", {})
                        content = delta.get("content", "")
                        raw_reasoning = delta.get("reasoning", "") or delta.get("reasoning_content", "")

                        # 清理推理内容，去除模型名称等噪声
                        reasoning = _clean_reasoning_content(raw_reasoning)

                        # 收集 tool_calls（流式响应中可能分散在多个 chunk 中）
                        tool_calls = delta.get("tool_calls")
                        result = {"content": content, "reasoning": reasoning}
                        if tool_calls:
                            result["tool_calls"] = tool_calls
                        if content or reasoning or tool_calls:
                            yield result
                    except json.JSONDecodeError:
                        continue

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers=self._build_headers(),
                json={"model": "text-embedding-3-small", "input": text},
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]

    async def list_models(self) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.base_url}/models",
                    headers=self._build_headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                return [
                    {
                        "id": m.get("id", ""),
                        "name": m.get("id", ""),
                        "owned_by": m.get("owned_by", ""),
                    }
                    for m in data.get("data", [])
                ]
        except Exception as e:
            logger.warning(f"Failed to list models from {self.provider_name}: {e}")
            return []

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _build_payload(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        stream: bool = False,
        **kwargs
    ) -> dict:
        payload = {
            "model": kwargs.get("model", self.default_model),
            "messages": messages,
            "stream": stream,
        }
        if kwargs.get("temperature") is not None:
            payload["temperature"] = kwargs["temperature"]
        if kwargs.get("max_tokens") is not None:
            payload["max_tokens"] = kwargs["max_tokens"]
        if kwargs.get("top_p") is not None:
            payload["top_p"] = kwargs["top_p"]
        if tools:
            payload["tools"] = tools
        return payload
