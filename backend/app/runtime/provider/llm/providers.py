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

_RETRIABLE_STATUS_CODES = {429, 500, 502, 503, 529}
_MAX_RETRIES = 2
_RETRY_BASE_DELAY = 1.0
_TOOL_CALL_ARGUMENTS_MAX_LEN = 100_000


class LLMResponse:
    __slots__ = ("content", "tool_calls", "finish_reason", "usage")

    def __init__(
        self,
        content: str | None = None,
        tool_calls: list[dict] | None = None,
        finish_reason: str = "stop",
        usage: dict | None = None,
    ):
        self.content = content or ""
        self.tool_calls = tool_calls
        self.finish_reason = finish_reason
        self.usage = usage

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
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=30.0, read=120.0, write=60.0, pool=30.0),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
                headers=self._build_headers(),
            )
        return self._client

    async def _close_client(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
        **kwargs
    ) -> LLMResponse:
        if stream:
            return await self._chat_via_stream(messages, tools, **kwargs)

        payload = self._build_payload(messages, tools, stream=False, **kwargs)
        last_error = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                client = self._get_client()
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                return self._parse_response(data)
            except Exception as e:
                last_error = e
                retriable, reason = _classify_error(e)
                if not retriable or attempt >= _MAX_RETRIES:
                    break
                import asyncio
                delay = _RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(f"[Provider] Retrying ({reason}): attempt {attempt + 1}/{_MAX_RETRIES}, delay={delay}s")
                await asyncio.sleep(delay)
        raise last_error

    async def _chat_via_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs
    ) -> LLMResponse:
        chunks: list[str] = []
        tool_calls_map: dict[int, dict] = {}
        tool_name_first_seen: dict[int, str] = {}

        async for event in self.chat_stream(messages, tools, **kwargs):
            if event.type == "content":
                chunks.append(event.data.get("content", ""))
            elif event.type == "tool_call_delta":
                idx = event.data.get("index", 0)
                if idx not in tool_calls_map:
                    tool_calls_map[idx] = {
                        "id": "",
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                    }
                tc = tool_calls_map[idx]
                if event.data.get("tool_call_id"):
                    tc["id"] = event.data["tool_call_id"]
                fn = tc["function"]
                if event.data.get("function_name"):
                    fn_name = event.data["function_name"]
                    if idx not in tool_name_first_seen:
                        tool_name_first_seen[idx] = fn_name
                        fn["name"] = fn_name
                    else:
                        if fn_name != tool_name_first_seen[idx]:
                            fn["name"] = fn_name
                        if not fn["name"]:
                            fn["name"] = fn_name
                if event.data.get("function_arguments"):
                    fn["arguments"] += event.data["function_arguments"]
            elif event.type == "usage":
                pass

        content = "".join(chunks)
        tool_calls = None
        if tool_calls_map:
            for idx in tool_calls_map:
                tc = tool_calls_map[idx]
                args = tc["function"]["arguments"]
                if args:
                    try:
                        json.loads(args)
                    except json.JSONDecodeError:
                        tc["function"]["arguments"] = _repair_tool_call_arguments(
                            args, tc["function"]["name"] or "unknown"
                        )
            tool_calls = list(tool_calls_map.values())

        return LLMResponse(content=content, tool_calls=tool_calls, finish_reason="stop")

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs
    ) -> AsyncIterator[StreamEvent]:
        payload = self._build_payload(messages, tools, stream=True, **kwargs)
        client = self._get_client()

        last_error = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    json=payload,
                ) as resp:
                    resp.raise_for_status()
                    tool_name_first_seen: dict[int, str] = {}

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

                            content = delta.get("content", "")
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
        client = self._get_client()
        resp = await client.post(
            f"{self.base_url}/embeddings",
            json={"model": "text-embedding-3-small", "input": text},
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]

    async def list_models(self) -> list[dict]:
        try:
            client = self._get_client()
            resp = await client.get(f"{self.base_url}/models")
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
