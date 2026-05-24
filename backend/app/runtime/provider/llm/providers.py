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
                        f"text_length={len(text)}")
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
            logger.debug(f"[Provider] Filtered short fragment: length={len(text)}")
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

_RETRIABLE_STATUS_CODES = {429, 500, 502, 503, 529}
_MAX_RETRIES = 2
_RETRY_BASE_DELAY = 1.0
_TOOL_CALL_ARGUMENTS_MAX_LEN = 100_000


class LLMResponse:
    __slots__ = ("content", "tool_calls", "finish_reason", "usage", "tool_results")

    def __init__(
        self,
        content: str | None = None,
        tool_calls: list[dict] | None = None,
        finish_reason: str = "stop",
        usage: dict | None = None,
        tool_results: list[dict] | None = None,
    ):
        self.content = content or ""
        self.tool_calls = tool_calls
        self.finish_reason = finish_reason
        self.usage = usage
        self.tool_results = tool_results

    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


class StreamEvent:
    __slots__ = ("type", "data")

    def __init__(self, event_type: str, data: dict | None = None):
        self.type = event_type
        self.data = data or {}


def _repair_tool_call_arguments(raw_args: str, tool_name: str = "?") -> str:
    if not raw_args or not raw_args.strip():
        return "{}"
    if len(raw_args) > _TOOL_CALL_ARGUMENTS_MAX_LEN:
        return "{}"
    text = raw_args.strip()
    if text in ("None", "null", "undefined"):
        return "{}"
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass
    try:
        return json.dumps(json.loads(text, strict=False))
    except json.JSONDecodeError:
        pass
    cleaned = text.rstrip()
    if cleaned.endswith(","):
        cleaned = cleaned[:-1]
    depth = 0
    for ch in cleaned:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
    if depth > 0:
        cleaned += "}" * depth
    elif depth < 0:
        for _ in range(-depth):
            idx = cleaned.rfind("}")
            if idx >= 0:
                cleaned = cleaned[:idx] + cleaned[idx + 1:]
    try:
        json.loads(cleaned)
        return cleaned
    except json.JSONDecodeError:
        pass
    logger.warning(f"[Provider] Failed to repair tool arguments for '{tool_name}', falling back to empty JSON")
    return "{}"


def _classify_error(exc: Exception) -> tuple[bool, str]:
    msg = str(exc).lower()
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status in (401, 403):
        return False, "auth"
    if status == 402:
        return False, "billing"
    if status == 404:
        return False, "model_not_found"
    if status in _RETRIABLE_STATUS_CODES:
        return True, "transient"
    if "rate_limit" in msg or "too many requests" in msg or "429" in msg:
        return True, "rate_limit"
    if "timeout" in msg or "timed out" in msg:
        return True, "timeout"
    if "connection" in msg or "connect" in msg:
        return True, "connection"
    return False, "unknown"


_MODEL_CAPABILITIES = {
    "gpt-4o": {"tool_calls": True, "multimodal": True},
    "gpt-4o-mini": {"tool_calls": True, "multimodal": True},
    "gpt-4-turbo": {"tool_calls": True, "multimodal": True},
    "gpt-4-": {"tool_calls": True, "multimodal": False},
    "o1": {"tool_calls": True, "multimodal": True},
    "o3-mini": {"tool_calls": True, "multimodal": False},
    "o3": {"tool_calls": True, "multimodal": False},
    "deepseek-chat": {"tool_calls": True, "multimodal": False},
    "deepseek-reasoner": {"tool_calls": False, "multimodal": False},
    "gemini": {"tool_calls": True, "multimodal": True},
    "mistral": {"tool_calls": True, "multimodal": False},
    "codestral": {"tool_calls": False, "multimodal": False},
    "llama-3.3-70b": {"tool_calls": True, "multimodal": False},
    "llama-3.1-": {"tool_calls": True, "multimodal": False},
    "grok": {"tool_calls": True, "multimodal": False},
    "moonshot-v1": {"tool_calls": True, "multimodal": False},
    "glm-4": {"tool_calls": True, "multimodal": True},
    "qwen-plus": {"tool_calls": True, "multimodal": False},
    "qwen-turbo": {"tool_calls": True, "multimodal": False},
    "qwen-max": {"tool_calls": True, "multimodal": False},
    "qwen2.5": {"tool_calls": True, "multimodal": False},
    "qwen3": {"tool_calls": True, "multimodal": False},
    "qwen2-vl": {"tool_calls": True, "multimodal": True},
    "qwen3-vl": {"tool_calls": True, "multimodal": True},
}


class OpenAICompatibleProvider(LLMProvider):
    provider_name = "openai_compatible"

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
        default_model: str = "gpt-4o-mini",
        provider_name: str = "openai_compatible",
        force_enable_tool_calls: bool | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.provider_name = provider_name
        self.force_enable_tool_calls = force_enable_tool_calls

    def _lookup_capability(self, model: str, cap_key: str) -> bool | None:
        if not model:
            return None
        model_lower = model.lower()
        for key, caps in _MODEL_CAPABILITIES.items():
            if key in model_lower:
                return caps.get(cap_key)
        return None

    def supports_tool_calls(self, model: str = "") -> bool:
        if self.force_enable_tool_calls is not None:
            return self.force_enable_tool_calls
        result = self._lookup_capability(model or self.default_model, "tool_calls")
        if result is not None:
            return result
        if self.provider_name == "ollama":
            return False
        return True

    def supports_multimodal(self, model: str = "") -> bool:
        result = self._lookup_capability(model or self.default_model, "multimodal")
        if result is not None:
            return result
        return False

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
            return await self._chat_via_stream(messages, tools, **kwargs)

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

    async def _chat_via_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs
    ) -> AsyncIterator[dict]:
        payload = self._build_payload(messages, tools, stream=True, **kwargs)
        collected_tool_calls: dict[int, dict] = {}
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
                        content = delta.get("content") or ""
                        raw_reasoning = delta.get("reasoning") or delta.get("reasoning_content") or ""

                        reasoning = _clean_reasoning_content(raw_reasoning)

                        tool_calls_delta = delta.get("tool_calls")
                        if tool_calls_delta:
                            for tc in tool_calls_delta:
                                idx = tc.get("index", 0)
                                if idx not in collected_tool_calls:
                                    collected_tool_calls[idx] = {"id": "", "name": "", "arguments": ""}
                                if tc.get("id"):
                                    collected_tool_calls[idx]["id"] = tc["id"]
                                fn = tc.get("function", {})
                                if fn.get("name"):
                                    collected_tool_calls[idx]["name"] = fn["name"]
                                if fn.get("arguments"):
                                    collected_tool_calls[idx]["arguments"] += fn["arguments"]

                        result = {"content": content, "reasoning": reasoning}
                        if content or reasoning:
                            yield result
                    except json.JSONDecodeError:
                        continue

        if collected_tool_calls:
            merged = []
            for idx in sorted(collected_tool_calls.keys()):
                entry = collected_tool_calls[idx]
                merged.append({
                    "id": entry["id"] or f"call_{idx}",
                    "type": "function",
                    "function": {
                        "name": entry["name"],
                        "arguments": entry["arguments"],
                    }
                })
            yield {"content": "", "reasoning": "", "tool_calls_complete": merged}

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs
    ) -> AsyncIterator[StreamEvent]:
        payload = self._build_payload(messages, tools, stream=True, **kwargs)

        last_error = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
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
                                yield StreamEvent("done")
                                return
                            try:
                                data = json.loads(data_str)
                                choice = data.get("choices", [{}])[0]
                                delta = choice.get("delta", {})
                                finish_reason = choice.get("finish_reason")

                                content = delta.get("content") or ""
                                if content:
                                    yield StreamEvent("content", {"content": content})

                                tc_deltas = delta.get("tool_calls")
                                if tc_deltas:
                                    for tc_delta in tc_deltas:
                                        idx = tc_delta.get("index", 0)
                                        event_data: dict = {"index": idx}
                                        if tc_delta.get("id"):
                                            event_data["tool_call_id"] = tc_delta["id"]
                                        fn = tc_delta.get("function", {})
                                        if fn.get("name"):
                                            event_data["function_name"] = fn["name"]
                                        if fn.get("arguments"):
                                            event_data["function_arguments"] = fn["arguments"]
                                        yield StreamEvent("tool_call_delta", event_data)

                                if finish_reason:
                                    yield StreamEvent("finish_reason", {"finish_reason": finish_reason})

                                usage = data.get("usage")
                                if usage:
                                    yield StreamEvent("usage", {"usage": usage})
                            except json.JSONDecodeError:
                                continue
                return
            except Exception as e:
                last_error = e
                retriable, reason = _classify_error(e)
                if not retriable or attempt >= _MAX_RETRIES:
                    break
                import asyncio
                delay = _RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(f"[Provider] Stream retry ({reason}): attempt {attempt + 1}/{_MAX_RETRIES}, delay={delay}s")
                await asyncio.sleep(delay)

        raise last_error

    async def embed(self, text: str) -> list[float]:
        embed_model = self.default_model if "embed" in self.default_model.lower() else "text-embedding-3-small"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers=self._build_headers(),
                json={"model": embed_model, "input": text},
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]

    async def list_models(self) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
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
            payload["tool_choice"] = "auto"
        return payload

    @staticmethod
    def _parse_response(data: dict) -> LLMResponse:
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content") or ""
        tool_calls = message.get("tool_calls")
        finish_reason = choice.get("finish_reason", "stop")
        usage = data.get("usage")

        parsed_tool_calls = None
        if tool_calls:
            parsed_tool_calls = []
            for tc in tool_calls:
                args = tc.get("function", {}).get("arguments", "{}")
                try:
                    json.loads(args)
                except json.JSONDecodeError:
                    tool_name = tc.get("function", {}).get("name", "unknown")
                    args = _repair_tool_call_arguments(args, tool_name)
                parsed_tool_calls.append({
                    "id": tc.get("id", ""),
                    "type": tc.get("type", "function"),
                    "function": {
                        "name": tc.get("function", {}).get("name", ""),
                        "arguments": args,
                    },
                })

        return LLMResponse(
            content=content,
            tool_calls=parsed_tool_calls,
            finish_reason=finish_reason,
            usage=usage,
        )
