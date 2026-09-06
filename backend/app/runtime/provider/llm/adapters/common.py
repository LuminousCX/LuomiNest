"""LuomiNest LLM 协议适配器公共实现（L1 适配器层）。

收口 chat_completions / anthropic_messages 两个协议适配器之间的重复代码：
- 重试常量与错误分类（classify_error，关键词取两版超集，含 Anthropic 的 "overloaded"）
- 推理内容清理（clean_reasoning_content，含 debug 日志分支）
- 流式 tool_calls 合并（merge_tool_calls）
- httpx 客户端生命周期与多模态能力查询（ProviderClientMixin）

设计原则：只收口"逐字重复或语义为两者超集"的实现；
协议差异（鉴权头、payload 构建、SSE 事件映射、流式重试循环）
仍由各适配器自持，禁止为去重而扭曲流式主链路。
"""
import re
from collections import Counter

import httpx
from loguru import logger

from app.runtime.provider.llm.types import StreamEvent


# ──────────────────────────────────────────────────────────────
# 错误分类与重试
# ──────────────────────────────────────────────────────────────

RETRIABLE_STATUS_CODES = {429, 500, 502, 503, 529}
MAX_RETRIES = 2
RETRY_BASE_DELAY = 1.0


def classify_error(exc: Exception) -> tuple[bool, str]:
    """将异常分类为可重试/不可重试，并返回原因标签。

    关键词集合为 chat_completions / anthropic_messages 两版的超集
    （含 Anthropic 特有的 "overloaded"）。
    """
    msg = str(exc).lower()
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status in (401, 403):
        return False, "auth"
    if status == 402:
        return False, "billing"
    if status == 404:
        return False, "model_not_found"
    if status in RETRIABLE_STATUS_CODES:
        return True, "transient"
    if "rate_limit" in msg or "too many requests" in msg or "429" in msg or "overloaded" in msg:
        return True, "rate_limit"
    if "timeout" in msg or "timed out" in msg:
        return True, "timeout"
    if "connection" in msg or "connect" in msg:
        return True, "connection"
    return False, "unknown"


# ──────────────────────────────────────────────────────────────
# 推理内容清理
# ──────────────────────────────────────────────────────────────

def clean_reasoning_content(raw_reasoning: str) -> str:
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
# 流式 tool_calls 合并
# ──────────────────────────────────────────────────────────────

def merge_tool_calls(collected: dict[int, dict]) -> StreamEvent:
    """合并流式累积的 tool_calls 为完整列表，发射 tool_calls_complete 事件。

    输出为 OpenAI function calling 格式（两协议适配器共用的统一中间表示）。
    """
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


# ──────────────────────────────────────────────────────────────
# 协议适配器公共 mixin
# ──────────────────────────────────────────────────────────────

class ProviderClientMixin:
    """协议适配器公共 mixin：httpx 客户端生命周期 + 多模态能力查询。

    依赖宿主类提供的属性/方法（在宿主 __init__ 中初始化）：
    - self._client: httpx.AsyncClient | None（懒加载的连接池客户端）
    - self.default_model: str
    - self.get_capabilities(model) -> ProviderCapabilities
    """

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

    def supports_multimodal(self, model: str = "") -> bool:
        """是否支持多模态（视觉）。从能力表查询。"""
        actual_model = model or self.default_model
        caps = self.get_capabilities(actual_model)
        return caps.supports_vision
