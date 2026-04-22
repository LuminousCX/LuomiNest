from typing import AsyncIterator
from app.runtime.provider.base import LLMProvider
from loguru import logger
import httpx
import json


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
        "default_model": "qwen2.5:7b",
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
        **kwargs
    ) -> str | AsyncIterator[str]:
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
            return data["choices"][0]["message"]["content"]

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs
    ) -> AsyncIterator[str]:
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
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
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
