"""LuomiNest LLM 供应商实现。

OpenAICompatibleProvider：统一的 OpenAI 兼容 API 供应商实现，
支持 27 个预置模板（PROVIDER_TEMPLATES）。

设计原则：
1. 单一实现类，所有供应商共用，通过 base_url / api_key / default_model 区分
2. httpx 客户端复用（每个 provider 实例持有独立 AsyncClient）
3. chat 统一返回 LLMResponse，chat_stream 统一返回 StreamEvent 流
4. 能力探测乐观默认，不硬编码模型能力表
5. 重试机制仅对可重试错误（429/500/502/503/529/timeout/connection）生效
"""
import asyncio
import json
import re
from collections import Counter
from typing import AsyncIterator

import httpx
from loguru import logger

from app.runtime.provider.base import LLMProvider
from app.runtime.provider.llm.types import LLMRequest, LLMResponse, StreamEvent


# ──────────────────────────────────────────────────────────────
# 推理内容清理
# ──────────────────────────────────────────────────────────────

def _clean_reasoning_content(raw_reasoning: str) -> str:
    """清理推理内容，去除模型名称、重复文本等噪声。

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
    model_name_pattern = r'[a-zA-Z0-9]+(?:-[a-zA-Z0-9.]+)*:[a-zA-Z0-9._-]+'
    matches = re.findall(model_name_pattern, text)
    if matches:
        total_model_chars = sum(len(m) for m in matches)
        ratio = total_model_chars / len(text) if text else 0
        if ratio > 0.6 and len(text) > 10:
            logger.debug(
                f"[Provider] Filtered reasoning noise: model_name_ratio={ratio:.2f}, "
                f"text_length={len(text)}"
            )
            return ""
        model_counts = Counter(matches)
        most_common_model, count = model_counts.most_common(1)[0] if model_counts else ("", 0)
        if count >= 3 and len(most_common_model) >= 5:
            logger.debug(f"[Provider] Filtered repeated model name: '{most_common_model}' x{count}")
            return ""

    # 场景2：移除行首/行尾的模型名
    text = re.sub(r'^[a-zA-Z0-9_-]+:[a-zA-Z0-9._-]+\s*', '', text)
    text = re.sub(r'\s*[a-zA-Z0-9_-]+:[a-zA-Z0-9._-]+$', '', text)

    # 场景3：移除孤立的模型名片段
    if len(text.strip()) < 8:
        if re.search(r':[a-zA-Z0-9._-]', text):
            logger.debug(f"[Provider] Filtered short fragment: length={len(text)}")
            return ""

    return text.strip()


# ──────────────────────────────────────────────────────────────
# 供应商模板（27 个预置）
# ──────────────────────────────────────────────────────────────

PROVIDER_TEMPLATES: dict[str, dict] = {
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
    "nous": {
        "id": "nous",
        "name": "Nous Research",
        "vendor": "openai_compatible",
        "base_url": "https://inference-api.nousresearch.com/v1",
        "api_key": "",
        "default_model": "deephermes-3-llama-3-8b-preview:free",
        "description": "Nous Research Hermes series models",
    },
    "nvidia": {
        "id": "nvidia",
        "name": "NVIDIA NIM",
        "vendor": "openai_compatible",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "api_key": "",
        "default_model": "meta/llama-3.1-70b-instruct",
        "description": "NVIDIA NIM cloud inference",
    },
    "stepfun": {
        "id": "stepfun",
        "name": "StepFun",
        "vendor": "openai_compatible",
        "base_url": "https://api.stepfun.ai/step_plan/v1",
        "api_key": "",
        "default_model": "step-2-16k",
        "description": "StepFun step series models",
    },
    "huggingface": {
        "id": "huggingface",
        "name": "HuggingFace",
        "vendor": "openai_compatible",
        "base_url": "https://api-inference.huggingface.co/v1",
        "api_key": "",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct",
        "description": "HuggingFace Inference API aggregator",
    },
    "arcee": {
        "id": "arcee",
        "name": "Arcee AI",
        "vendor": "openai_compatible",
        "base_url": "https://api.arcee.ai/api/v1",
        "api_key": "",
        "default_model": "arcee-blitz",
        "description": "Arcee AI model fusion platform",
    },
    "gmi": {
        "id": "gmi",
        "name": "GMI",
        "vendor": "openai_compatible",
        "base_url": "https://api.gmi-serving.com/v1",
        "api_key": "",
        "default_model": "gmi-cloud-1",
        "description": "GMI serving cloud inference",
    },
    "minimax": {
        "id": "minimax",
        "name": "MiniMax",
        "vendor": "openai_compatible",
        "base_url": "https://api.minimax.chat/v1",
        "api_key": "",
        "default_model": "MiniMax-Text-01",
        "description": "MiniMax text models",
    },
    "vercel": {
        "id": "vercel",
        "name": "Vercel AI",
        "vendor": "openai_compatible",
        "base_url": "https://sdk.vercel.ai/api/v1",
        "api_key": "",
        "default_model": "openai/gpt-4o-mini",
        "description": "Vercel AI gateway aggregator",
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


# ──────────────────────────────────────────────────────────────
# 错误分类与重试
# ──────────────────────────────────────────────────────────────

_RETRIABLE_STATUS_CODES = {429, 500, 502, 503, 529}
_MAX_RETRIES = 2
_RETRY_BASE_DELAY = 1.0


def _classify_error(exc: Exception) -> tuple[bool, str]:
    """将异常分类为可重试/不可重试，并返回原因标签。"""
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


# ──────────────────────────────────────────────────────────────
# OpenAICompatibleProvider 实现
# ──────────────────────────────────────────────────────────────

class OpenAICompatibleProvider(LLMProvider):
    """OpenAI 兼容 API 供应商实现。

    所有 27 个预置模板均使用此类的同一实现，
    通过 base_url / api_key / default_model 区分不同供应商。
    """

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
        # 复用 httpx 客户端连接池
        self._client: httpx.AsyncClient | None = None
        # 运行时能力探测：记录已知不支持工具调用的模型
        self._unsupported_tool_models: set[str] = set()

    @property
    def client(self) -> httpx.AsyncClient:
        """懒加载 httpx 客户端（复用连接池）。"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client

    async def aclose(self) -> None:
        """关闭 httpx 客户端。"""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def supports_tool_calls(self, model: str = "") -> bool:
        """是否支持工具调用。

        优先使用 force_enable_tool_calls 强制开关；
        其次检查运行时探测结果（_unsupported_tool_models）；
        默认乐观 True（首次失败时记录并降级）。
        """
        if self.force_enable_tool_calls is not None:
            return self.force_enable_tool_calls
        actual_model = model or self.default_model
        if actual_model in self._unsupported_tool_models:
            return False
        return True

    def supports_multimodal(self, model: str = "") -> bool:
        """是否支持多模态。乐观默认 False，由调用方按需覆盖。"""
        return False

    def mark_unsupported_tool_calls(self, model: str) -> None:
        """运行时探测：记录不支持工具调用的模型。"""
        if model:
            self._unsupported_tool_models.add(model)
            logger.debug(f"[Provider] {self.provider_name} marked model '{model}' as tool-call unsupported")

    # ── 非流式聊天 ──

    async def chat(self, request: LLMRequest) -> LLMResponse:
        """非流式聊天，统一返回 LLMResponse。

        实现：
        1. 构建 payload（含 tools / temperature / max_tokens / top_p）
        2. POST /chat/completions（stream=False）
        3. 解析 choices[0].message，提取 content / reasoning / tool_calls
        4. 返回 LLMResponse
        """
        payload = self._build_payload(request, stream=False)
        client = httpx.AsyncClient(timeout=120.0) if self._client is None else self.client
        try:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._build_headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        finally:
            if self._client is None:
                await client.aclose()

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "") or ""
        raw_reasoning = message.get("reasoning", "") or message.get("reasoning_content", "")
        reasoning = _clean_reasoning_content(raw_reasoning)
        tool_calls = message.get("tool_calls")
        finish_reason = choice.get("finish_reason", "stop")
        usage = data.get("usage")

        return LLMResponse(
            content=content,
            reasoning=reasoning,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
            raw=data,
        )

    # ── 流式聊天 ──

    async def chat_stream(self, request: LLMRequest) -> AsyncIterator[StreamEvent]:
        """流式聊天，统一返回 StreamEvent 流。

        实现：
        1. 构建 payload（stream=True）
        2. 带重试机制（_MAX_RETRIES=2，仅对可重试错误生效）
        3. 逐行解析 SSE data，发射 content / reasoning / tool_call_delta / finish_reason / usage / done 事件
        4. 流结束后合并 tool_calls（如有）
        """
        payload = self._build_payload(request, stream=True)
        enable_reasoning = request.extra.get("enable_reasoning", True)

        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                collected_tool_calls: dict[int, dict] = {}
                client = httpx.AsyncClient(timeout=180.0) if self._client is None else self.client
                client_owned = self._client is None
                try:
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
                                # 流结束前合并 tool_calls
                                if collected_tool_calls:
                                    yield self._merge_tool_calls(collected_tool_calls)
                                return
                            try:
                                data = json.loads(data_str)
                                choice = data.get("choices", [{}])[0]
                                delta = choice.get("delta", {})
                                finish_reason = choice.get("finish_reason")

                                content = delta.get("content") or ""
                                if content:
                                    yield StreamEvent("content", {"content": content})

                                if enable_reasoning:
                                    raw_reasoning = delta.get("reasoning") or delta.get("reasoning_content") or ""
                                    if raw_reasoning:
                                        reasoning = _clean_reasoning_content(raw_reasoning)
                                        if reasoning:
                                            yield StreamEvent("reasoning", {"reasoning": reasoning})

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
                                        # 累积合并 tool_calls
                                        if idx not in collected_tool_calls:
                                            collected_tool_calls[idx] = {"id": "", "name": "", "arguments": ""}
                                        if event_data.get("tool_call_id"):
                                            collected_tool_calls[idx]["id"] = event_data["tool_call_id"]
                                        if event_data.get("function_name"):
                                            collected_tool_calls[idx]["name"] = event_data["function_name"]
                                        if event_data.get("function_arguments"):
                                            collected_tool_calls[idx]["arguments"] += event_data["function_arguments"]
                                        yield StreamEvent("tool_call_delta", event_data)

                                if finish_reason:
                                    yield StreamEvent("finish_reason", {"finish_reason": finish_reason})

                                usage = data.get("usage")
                                if usage:
                                    yield StreamEvent("usage", {"usage": usage})
                            except json.JSONDecodeError:
                                continue
                    # 流正常结束（未收到 [DONE]），合并 tool_calls
                    if collected_tool_calls:
                        yield self._merge_tool_calls(collected_tool_calls)
                    return
                finally:
                    if client_owned:
                        await client.aclose()
            except Exception as e:
                last_error = e
                retriable, reason = _classify_error(e)
                if not retriable or attempt >= _MAX_RETRIES:
                    break
                delay = _RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    f"[Provider] Stream retry ({reason}): attempt {attempt + 1}/{_MAX_RETRIES}, delay={delay}s"
                )
                await asyncio.sleep(delay)

        raise last_error

    @staticmethod
    def _merge_tool_calls(collected: dict[int, dict]) -> StreamEvent:
        """合并流式累积的 tool_calls 为完整列表，发射 tool_calls_complete 事件。"""
        merged = []
        for idx in sorted(collected.keys()):
            entry = collected[idx]
            merged.append({
                "id": entry["id"] or f"call_{idx}",
                "type": "function",
                "function": {
                    "name": entry["name"],
                    "arguments": entry["arguments"],
                },
            })
        return StreamEvent("tool_calls_complete", {"tool_calls": merged})

    # ── 嵌入 ──

    async def embed(self, text: str) -> list[float]:
        embed_model = self.default_model if "embed" in self.default_model.lower() else "text-embedding-3-small"
        client = httpx.AsyncClient(timeout=30.0) if self._client is None else self.client
        try:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers=self._build_headers(),
                json={"model": embed_model, "input": text},
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]
        finally:
            if self._client is None:
                await client.aclose()

    # ── 模型列表 ──

    async def list_models(self) -> list[dict]:
        client = httpx.AsyncClient(timeout=30.0) if self._client is None else self.client
        try:
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
            logger.warning(f"[Provider] Failed to list models from {self.provider_name}: {e}")
            return []
        finally:
            if self._client is None:
                await client.aclose()

    # ── 内部辅助 ──

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _build_payload(self, request: LLMRequest, stream: bool = False) -> dict:
        payload = {
            "model": request.model or self.default_model,
            "messages": request.messages,
            "stream": stream,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.tools:
            payload["tools"] = request.tools
            payload["tool_choice"] = "auto"
        return payload
