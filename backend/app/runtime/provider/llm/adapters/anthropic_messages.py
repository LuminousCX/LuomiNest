"""LuomiNest Anthropic Messages 协议适配器（L1 适配器层）。

AnthropicMessagesProvider：Anthropic 原生 Messages API（POST /v1/messages）实现，
用于修复内置 anthropic 供应商直连 api.anthropic.com 时误走 OpenAI 兼容协议
（POST /chat/completions → 404）的真实缺陷（onion §4.1.1 缺陷 1）。

本模块是六边形架构中的适配器：向内实现 ports.py 的 LLMProvider 端口，
向外对接 Anthropic 原生协议；重试常量/错误分类/推理清洗/tool_calls 合并
等逐字重复的实现收口于 common.py（共享），协议差异部分自持。

协议要点：
1. 鉴权头为 x-api-key（非 Authorization: Bearer），必须携带 anthropic-version
2. body 的 max_tokens 为必填字段（Anthropic 强制），未指定时使用合理默认
3. system 提示词为顶层字段，需从 messages 中提取
4. messages 必须 user/assistant 严格交替（相邻同角色合并为一条）
5. 工具：tools 使用 input_schema（对应 OpenAI 的 parameters），
   assistant 工具调用为 tool_use 内容块，工具结果为 user 角色的 tool_result 块
6. chat 统一返回 LLMResponse，chat_stream 统一返回与 chat_completions
   完全一致的 StreamEvent 事件协议（上游 stream_processor/coalescer 不感知协议差异）
"""
import asyncio
import json
import uuid
from typing import Any, AsyncIterator

import httpx
from loguru import logger

from app.core.exceptions import ProviderError
from app.runtime.provider.llm.adapters.common import (
    MAX_RETRIES,
    RETRY_BASE_DELAY,
    ProviderClientMixin,
    classify_error,
    clean_reasoning_content,
    merge_tool_calls,
)
from app.runtime.provider.llm.ports import LLMProvider
from app.runtime.provider.llm.types import LLMRequest, LLMResponse, ProviderCapabilities, StreamEvent
from app.runtime.provider.llm.capabilities import get_capabilities as _get_capabilities


# ──────────────────────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────────────────────

ANTHROPIC_API_VERSION = "2023-06-01"

# Anthropic 强制要求 max_tokens；上游未指定时使用该默认值
DEFAULT_MAX_TOKENS = 8192

# Anthropic temperature 取值范围为 [0, 1]，超出时截断
_MAX_TEMPERATURE = 1.0

# stop_reason（Anthropic）→ finish_reason（OpenAI 风格统一中间表示）
_STOP_REASON_MAP: dict[str, str] = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "max_tokens": "length",
    "tool_use": "tool_calls",
    "pause_turn": "stop",
    "refusal": "content_filter",
    "model_context_window_exceeded": "length",
}


def _map_stop_reason(stop_reason: str | None) -> str:
    """将 Anthropic stop_reason 映射为统一 finish_reason，未知值原样透传。"""
    if not stop_reason:
        return "stop"
    return _STOP_REASON_MAP.get(stop_reason, stop_reason)


# ──────────────────────────────────────────────────────────────
# usage 归一化
# ──────────────────────────────────────────────────────────────

def _normalize_usage(usage: dict[str, Any] | None) -> dict[str, Any] | None:
    """将 Anthropic usage（input_tokens/output_tokens）归一化为
    OpenAI 风格键（prompt_tokens/completion_tokens/total_tokens），
    保证上游 usage_tracker 等消费方无需感知协议差异；同时保留原始键。
    """
    if not usage:
        return None
    prompt_tokens = (
        usage.get("input_tokens")
        or usage.get("prompt_tokens")
        or 0
    )
    completion_tokens = (
        usage.get("output_tokens")
        or usage.get("completion_tokens")
        or 0
    )
    normalized = dict(usage)
    normalized["prompt_tokens"] = prompt_tokens
    normalized["completion_tokens"] = completion_tokens
    normalized["total_tokens"] = usage.get("total_tokens") or (prompt_tokens + completion_tokens)
    return normalized


# ──────────────────────────────────────────────────────────────
# OpenAI 格式消息 ⇄ Anthropic 格式转换
# ──────────────────────────────────────────────────────────────

def _extract_text_from_content(content: Any) -> str:
    """从 OpenAI 风格 content（str 或块列表）中提取纯文本。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                if part.get("type") == "text" and part.get("text"):
                    parts.append(str(part["text"]))
                elif part.get("type") == "image_url":
                    parts.append("[image]")
        return "\n".join(parts)
    return str(content)


def _convert_image_part(part: dict) -> dict | None:
    """OpenAI image_url 块 → Anthropic image 块（支持 data: base64 与 http(s) URL）。"""
    image_url = (part.get("image_url") or {}).get("url", "")
    if not image_url:
        return None
    if image_url.startswith("data:"):
        # data:image/png;base64,xxxx
        try:
            header, _, b64data = image_url.partition(",")
            media_type = header.split(";")[0][len("data:"):] or "image/png"
            return {
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": b64data},
            }
        except Exception:
            logger.warning("[AnthropicProvider] Failed to parse data: image url, skipped")
            return None
    if image_url.startswith(("http://", "https://")):
        return {
            "type": "image",
            "source": {"type": "url", "url": image_url},
        }
    return None


def _user_content_blocks(msg: dict) -> list[dict]:
    """OpenAI user 消息 → Anthropic content 块列表。"""
    content = msg.get("content")
    blocks: list[dict] = []
    if isinstance(content, str):
        if content.strip() or content == " ":
            blocks.append({"type": "text", "text": content})
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, str):
                if part:
                    blocks.append({"type": "text", "text": part})
                continue
            if not isinstance(part, dict):
                continue
            ptype = part.get("type")
            if ptype == "text":
                text = part.get("text", "")
                if text:
                    blocks.append({"type": "text", "text": text})
            elif ptype == "image_url":
                image_block = _convert_image_part(part)
                if image_block:
                    blocks.append(image_block)
    return blocks


def _parse_tool_arguments(arguments: Any) -> dict:
    """tool_calls.function.arguments（JSON 字符串）→ dict，解析失败返回 {}。"""
    if isinstance(arguments, dict):
        return arguments
    if not arguments:
        return {}
    try:
        parsed = json.loads(arguments)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        logger.warning("[AnthropicProvider] Failed to parse tool arguments as JSON, using {}")
        return {}


def _assistant_content_blocks(msg: dict) -> list[dict]:
    """OpenAI assistant 消息 → Anthropic content 块列表（text + tool_use）。"""
    blocks: list[dict] = []
    text = _extract_text_from_content(msg.get("content"))
    if text.strip():
        blocks.append({"type": "text", "text": text})
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function") or {}
        name = fn.get("name", "")
        if not name:
            continue
        tool_use_id = tc.get("id") or f"toolu_{uuid.uuid4().hex[:24]}"
        blocks.append({
            "type": "tool_use",
            "id": tool_use_id,
            "name": name,
            "input": _parse_tool_arguments(fn.get("arguments")),
        })
    return blocks


def _tool_result_blocks(msg: dict) -> list[dict]:
    """OpenAI tool 消息 → user 角色的 tool_result 块。"""
    tool_use_id = msg.get("tool_call_id") or ""
    content = msg.get("content")
    if isinstance(content, (dict, list)):
        result_content = json.dumps(content, ensure_ascii=False)
    elif content is None:
        result_content = ""
    else:
        result_content = str(content)
    return [{
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": result_content,
    }]


def convert_messages_to_anthropic(
    messages: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """OpenAI 格式 messages → (system 顶层文本, Anthropic messages 列表)。

    规则：
    1. system 消息提取为顶层 system 字段（多条以空行拼接）
    2. tool_calls ⇄ tool_use 内容块；tool 消息 → user 角色 tool_result 块
    3. user/assistant 严格交替：相邻同角色消息合并为一条（内容块拼接）
    4. 孤立的 tool_result（无对应 tool_use）移除，避免 Anthropic 400
    5. tool_use 缺少后续 tool_result 时补占位结果，满足 Anthropic 强校验
    6. 确保首条消息为 user 角色
    """
    system_parts: list[str] = []
    raw_converted: list[dict[str, Any]] = []

    for msg in messages:
        role = msg.get("role", "")
        if role == "system":
            text = _extract_text_from_content(msg.get("content"))
            if text.strip():
                system_parts.append(text.strip())
        elif role == "user":
            blocks = _user_content_blocks(msg)
            if blocks:
                raw_converted.append({"role": "user", "content": blocks})
        elif role == "assistant":
            blocks = _assistant_content_blocks(msg)
            if blocks:
                raw_converted.append({"role": "assistant", "content": blocks})
        elif role == "tool":
            blocks = _tool_result_blocks(msg)
            if blocks:
                raw_converted.append({"role": "user", "content": blocks})
        # 其他未知角色：忽略

    # ── 合并相邻同角色消息（保证 user/assistant 严格交替）──
    merged: list[dict[str, Any]] = []
    for item in raw_converted:
        if merged and merged[-1]["role"] == item["role"]:
            merged[-1]["content"].extend(item["content"])
        else:
            merged.append({"role": item["role"], "content": list(item["content"])})

    # ── 移除孤立 tool_result（没有对应 tool_use 会被 Anthropic 拒绝）──
    known_tool_use_ids: set[str] = set()
    for item in merged:
        if item["role"] == "assistant":
            for block in item["content"]:
                if block.get("type") == "tool_use" and block.get("id"):
                    known_tool_use_ids.add(block["id"])

    for item in merged:
        if item["role"] != "user":
            continue
        kept = [
            block for block in item["content"]
            if not (
                block.get("type") == "tool_result"
                and block.get("tool_use_id") not in known_tool_use_ids
            )
        ]
        item["content"] = kept

    # ── 为缺少 tool_result 的 tool_use 补占位结果（Anthropic 强校验）──
    for i, item in enumerate(merged):
        if item["role"] != "assistant":
            continue
        tool_use_ids = [
            block["id"] for block in item["content"]
            if block.get("type") == "tool_use" and block.get("id")
        ]
        if not tool_use_ids:
            continue
        next_item = merged[i + 1] if i + 1 < len(merged) else None
        answered_ids: set[str] = set()
        if next_item is not None and next_item["role"] == "user":
            answered_ids = {
                block.get("tool_use_id")
                for block in next_item["content"]
                if block.get("type") == "tool_result"
            }
        missing = [tid for tid in tool_use_ids if tid not in answered_ids]
        if not missing:
            continue
        placeholder_blocks = [
            {"type": "tool_result", "tool_use_id": tid, "content": "(工具未返回结果)"}
            for tid in missing
        ]
        if next_item is not None and next_item["role"] == "user":
            next_item["content"] = placeholder_blocks + next_item["content"]
        else:
            merged.insert(i + 1, {"role": "user", "content": placeholder_blocks})

    # ── 移除内容块为空的消息 ──
    merged = [item for item in merged if item["content"]]

    # ── 确保首条消息为 user ──
    if merged and merged[0]["role"] != "user":
        logger.debug("[AnthropicProvider] messages 以 assistant 开头，插入占位 user 消息")
        merged.insert(0, {"role": "user", "content": [{"type": "text", "text": " "}]})
    if not merged:
        merged = [{"role": "user", "content": [{"type": "text", "text": " "}]}]

    return "\n\n".join(system_parts), merged


def convert_tools_to_anthropic(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """OpenAI function calling tools → Anthropic tools（input_schema 格式）。"""
    if not tools:
        return []
    converted: list[dict[str, Any]] = []
    for tool in tools:
        fn = tool.get("function") if tool.get("type", "function") == "function" else None
        if fn is None:
            # 已是 anthropic 风格（含 input_schema）则原样透传
            if tool.get("name") and tool.get("input_schema"):
                converted.append(tool)
            continue
        name = fn.get("name", "")
        if not name:
            continue
        entry: dict[str, Any] = {
            "name": name,
            "input_schema": fn.get("parameters") or {"type": "object", "properties": {}},
        }
        if fn.get("description"):
            entry["description"] = fn["description"]
        converted.append(entry)
    return converted


def tool_use_blocks_to_openai_tool_calls(content_blocks: list[dict]) -> list[dict[str, Any]]:
    """Anthropic tool_use 内容块 → OpenAI tool_calls 格式（统一中间表示）。"""
    tool_calls: list[dict[str, Any]] = []
    for block in content_blocks:
        if block.get("type") != "tool_use":
            continue
        tool_calls.append({
            "id": block.get("id") or f"call_{len(tool_calls)}",
            "type": "function",
            "function": {
                "name": block.get("name", ""),
                "arguments": json.dumps(block.get("input") or {}, ensure_ascii=False),
            },
        })
    return tool_calls


# ──────────────────────────────────────────────────────────────
# AnthropicMessagesProvider 实现
# ──────────────────────────────────────────────────────────────

class AnthropicMessagesProvider(ProviderClientMixin, LLMProvider):
    """Anthropic 原生 Messages API 供应商实现。

    通过 base_url / api_key / default_model 区分不同接入点
    （官方直连或 Anthropic 协议兼容网关）。
    """

    provider_name = "anthropic_messages"

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.anthropic.com/v1",
        default_model: str = "claude-sonnet-4-20250514",
        provider_name: str = "anthropic_messages",
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.provider_name = provider_name
        # 复用 httpx 客户端连接池
        self._client: httpx.AsyncClient | None = None
        # 运行时能力探测：记录已知不支持工具调用的模型
        self._unsupported_tool_models: set[str] = set()

    # ── 基础属性 ──

    @property
    def api_base(self) -> str:
        """API 根地址：base_url 已含 /v1 时直接使用，否则补 /v1。"""
        if self.base_url.endswith("/v1"):
            return self.base_url
        return f"{self.base_url}/v1"

    # ── 能力声明 ──

    def supports_tool_calls(self, model: str = "") -> bool:
        """是否支持工具调用（能力表查询，默认乐观 True）。"""
        actual_model = model or self.default_model
        if actual_model in self._unsupported_tool_models:
            return False
        caps = self.get_capabilities(actual_model)
        return caps.supports_tool_calls

    def get_capabilities(self, model: str | None = None) -> ProviderCapabilities:
        """获取当前 provider 的能力声明（以 provider_name 为 key 查能力表）。"""
        return _get_capabilities(self.provider_name, model)

    def get_context_window(self, model: str) -> int:
        """返回给定模型的上下文窗口大小，从能力表获取。"""
        caps = self.get_capabilities(model)
        return caps.default_context_window

    def mark_unsupported_tool_calls(self, model: str) -> None:
        """运行时探测：记录不支持工具调用的模型。"""
        if model:
            self._unsupported_tool_models.add(model)
            logger.debug(f"[AnthropicProvider] {self.provider_name} marked model '{model}' as tool-call unsupported")

    # ── 请求构建 ──

    def _build_headers(self) -> dict[str, str]:
        """Anthropic 原生鉴权头：x-api-key + anthropic-version。"""
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": ANTHROPIC_API_VERSION,
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def _build_payload(self, request: LLMRequest, stream: bool) -> dict[str, Any]:
        """构建 /v1/messages 请求体。"""
        system_text, anthropic_messages = convert_messages_to_anthropic(request.messages)
        payload: dict[str, Any] = {
            "model": request.model or self.default_model,
            # Anthropic 强制要求 max_tokens
            "max_tokens": request.max_tokens or DEFAULT_MAX_TOKENS,
            "messages": anthropic_messages,
            "stream": stream,
        }
        if system_text:
            payload["system"] = system_text
        if request.temperature is not None:
            # Anthropic temperature 范围 [0, 1]，越界截断
            payload["temperature"] = max(0.0, min(float(request.temperature), _MAX_TEMPERATURE))
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        tools = convert_tools_to_anthropic(request.tools)
        if tools:
            payload["tools"] = tools
        return payload

    # ── 响应解析 ──

    @staticmethod
    def _parse_message_response(data: dict[str, Any]) -> LLMResponse:
        """解析非流式 /v1/messages 响应为 LLMResponse。"""
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        content_blocks = data.get("content") or []
        for block in content_blocks:
            btype = block.get("type")
            if btype == "text":
                content_parts.append(block.get("text", ""))
            elif btype == "thinking":
                reasoning_parts.append(block.get("thinking", ""))
            # tool_use / redacted_thinking 等由下方统一处理 / 忽略

        tool_calls = tool_use_blocks_to_openai_tool_calls(content_blocks)
        raw_reasoning = "\n".join(p for p in reasoning_parts if p)
        return LLMResponse(
            content="".join(content_parts),
            reasoning=clean_reasoning_content(raw_reasoning),
            tool_calls=tool_calls or None,
            finish_reason=_map_stop_reason(data.get("stop_reason")),
            usage=_normalize_usage(data.get("usage")),
            raw=data,
        )

    async def _map_stream_events(
        self,
        lines: AsyncIterator[str],
        enable_reasoning: bool,
    ) -> AsyncIterator[StreamEvent]:
        """将 Anthropic SSE 行流映射为统一 StreamEvent 流（与 chat_completions 事件时序一致）。

        映射规则：
        - message_start                       → 记录 input usage（不发射事件）
        - content_block_start(tool_use)       → tool_call_delta（携带 id/name）
        - content_block_delta(text_delta)     → content
        - content_block_delta(thinking_delta) → reasoning
        - content_block_delta(input_json_delta) → tool_call_delta（arguments 累积）
        - message_delta(stop_reason/usage)    → finish_reason + usage
        - message_stop                        → done，随后 tool_calls_complete
        - error                               → 抛出 ProviderError
        - ping / content_block_stop 等        → 忽略

        流未收到 message_stop 即结束时（与 chat_completions 无 [DONE] 的分支一致），
        仅补发 tool_calls_complete，不发射 done。
        """
        collected_tool_calls: dict[int, dict] = {}
        input_usage: dict[str, Any] = {}

        async for line in lines:
            if not line.startswith("data:"):
                continue
            data_str = line[len("data:"):].strip()
            if not data_str:
                continue
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            event_type = data.get("type", "")

            if event_type == "message_start":
                message = data.get("message") or {}
                input_usage = dict(message.get("usage") or {})
                continue

            if event_type == "content_block_start":
                block = data.get("content_block") or {}
                if block.get("type") == "tool_use":
                    idx = len(collected_tool_calls)
                    collected_tool_calls[idx] = {
                        "id": block.get("id", ""),
                        "name": block.get("name", ""),
                        "arguments": "",
                    }
                    event_data: dict[str, Any] = {"index": idx}
                    if block.get("id"):
                        event_data["tool_call_id"] = block["id"]
                    if block.get("name"):
                        event_data["function_name"] = block["name"]
                    yield StreamEvent("tool_call_delta", event_data)
                continue

            if event_type == "content_block_delta":
                delta = data.get("delta") or {}
                delta_type = delta.get("type")
                if delta_type == "text_delta":
                    text = delta.get("text") or ""
                    if text:
                        yield StreamEvent("content", {"content": text})
                elif delta_type == "thinking_delta" and enable_reasoning:
                    raw_reasoning = delta.get("thinking") or ""
                    if raw_reasoning:
                        reasoning = clean_reasoning_content(raw_reasoning)
                        if reasoning:
                            yield StreamEvent("reasoning", {"reasoning": reasoning})
                elif delta_type == "input_json_delta":
                    partial = delta.get("partial_json") or ""
                    # 定位当前活跃的 tool_use 块（最后一个注册的 tool call）
                    if collected_tool_calls and partial:
                        idx = max(collected_tool_calls.keys())
                        collected_tool_calls[idx]["arguments"] += partial
                        yield StreamEvent(
                            "tool_call_delta",
                            {"index": idx, "function_arguments": partial},
                        )
                # signature_delta 等其他 delta 类型忽略
                continue

            if event_type == "message_delta":
                delta = data.get("delta") or {}
                stop_reason = delta.get("stop_reason")
                if stop_reason:
                    yield StreamEvent(
                        "finish_reason",
                        {"finish_reason": _map_stop_reason(stop_reason)},
                    )
                usage = data.get("usage")
                if usage or input_usage:
                    merged_usage = {**input_usage, **(usage or {})}
                    normalized = _normalize_usage(merged_usage)
                    if normalized:
                        yield StreamEvent("usage", {"usage": normalized})
                continue

            if event_type == "message_stop":
                # 与 chat_completions 的 [DONE] 时序一致：先 done，再 tool_calls_complete
                yield StreamEvent("done")
                if collected_tool_calls:
                    yield merge_tool_calls(collected_tool_calls)
                return

            if event_type == "error":
                error = data.get("error") or {}
                raise ProviderError(
                    f"Anthropic stream error: {error.get('type', 'unknown')}: "
                    f"{error.get('message', '')}",
                    provider=self.provider_name,
                )

            # ping / content_block_stop 等其他事件忽略

        # 流正常结束（未收到 message_stop），仅合并 tool_calls
        if collected_tool_calls:
            yield merge_tool_calls(collected_tool_calls)

    # ── 非流式聊天 ──

    async def chat(self, request: LLMRequest) -> LLMResponse:
        """非流式聊天，统一返回 LLMResponse。

        实现：
        1. 消息/工具格式转换（OpenAI → Anthropic）
        2. POST {base}/messages（stream=False）
        3. 解析 content 块（text/thinking/tool_use），返回 LLMResponse
        """
        payload = self._build_payload(request, stream=False)
        client = httpx.AsyncClient(timeout=120.0) if self._client is None else self.client
        try:
            resp = await client.post(
                f"{self.api_base}/messages",
                headers=self._build_headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        finally:
            if self._client is None:
                await client.aclose()
        return self._parse_message_response(data)

    # ── 流式聊天 ──

    async def chat_stream(self, request: LLMRequest) -> AsyncIterator[StreamEvent]:
        """流式聊天，统一返回 StreamEvent 流（事件协议与 chat_completions 完全一致）。

        带重试机制（MAX_RETRIES=2，仅对可重试错误生效），
        SSE 事件映射见 _map_stream_events。
        """
        payload = self._build_payload(request, stream=True)
        enable_reasoning = request.extra.get("enable_reasoning", True)

        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                client = httpx.AsyncClient(timeout=180.0) if self._client is None else self.client
                client_owned = self._client is None
                try:
                    async with client.stream(
                        "POST",
                        f"{self.api_base}/messages",
                        headers=self._build_headers(),
                        json=payload,
                    ) as resp:
                        resp.raise_for_status()
                        async for event in self._map_stream_events(resp.aiter_lines(), enable_reasoning):
                            yield event
                    return
                finally:
                    if client_owned:
                        await client.aclose()
            except Exception as e:
                last_error = e
                retriable, reason = classify_error(e)
                if not retriable or attempt >= MAX_RETRIES:
                    break
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    f"[AnthropicProvider] Stream retry ({reason}): attempt {attempt + 1}/{MAX_RETRIES}, delay={delay}s"
                )
                await asyncio.sleep(delay)

        raise last_error

    # ── 嵌入 ──

    async def embed(self, text: str) -> list[float]:
        """Anthropic 不提供嵌入 API，明确抛出 ProviderError。

        调用方（如记忆向量索引）应改用具备嵌入能力的供应商或本地嵌入。
        """
        raise ProviderError(
            "Anthropic 协议不提供嵌入（embeddings）能力，请在模型设置中选择支持嵌入的供应商",
            provider=self.provider_name,
            code="PROVIDER_EMBED_NOT_SUPPORTED",
            status_code=400,
        )

    # ── 模型列表 ──

    async def list_models(self) -> list[dict]:
        """GET {base}/models（Anthropic 原生模型列表接口）。"""
        client = httpx.AsyncClient(timeout=30.0) if self._client is None else self.client
        try:
            resp = await client.get(
                f"{self.api_base}/models",
                headers=self._build_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            return [
                {
                    "id": m.get("id", ""),
                    "name": m.get("display_name") or m.get("id", ""),
                    "owned_by": "anthropic",
                }
                for m in data.get("data", [])
            ]
        except Exception as e:
            logger.warning(f"[AnthropicProvider] Failed to list models from {self.provider_name}: {e}")
            return []
        finally:
            if self._client is None:
                await client.aclose()
