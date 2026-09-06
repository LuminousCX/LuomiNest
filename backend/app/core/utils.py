"""通用工具函数——消除跨模块重复定义"""

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any

from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger


def utc_now() -> str:
    """返回当前 UTC 时间的 ISO-8601 字符串。"""
    return datetime.now(timezone.utc).isoformat()


def utc_now_dt() -> datetime:
    """返回当前 UTC 时间的 datetime 对象（用于时间运算）。"""
    return datetime.now(timezone.utc)


def extract_llm_text(result: Any) -> str:
    """从 LLM 适配器返回值中提取纯文本。

    超集语义（收口自 platform_router._extract_assistant_text、
    a2a_tool、workflow/context_manager 的手写提取逻辑）：
    - str 直接返回（不裁剪）
    - dict：优先 content 字段，其次 choices[0].message.content，再次 text 字段
    - 带 content 属性的对象：取 str(result.content)
    - 其他类型 str()；空值返回 ""
    """
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        content = result.get("content")
        if isinstance(content, str):
            return content
        choices = result.get("choices")
        if choices and isinstance(choices, list):
            first = choices[0]
            if isinstance(first, dict):
                msg = first.get("message", {})
                if isinstance(msg, dict) and msg.get("content"):
                    return msg["content"]
        text = result.get("text")
        if isinstance(text, str) and text:
            return text
        return str(result) if result else ""
    if result is None:
        return ""
    if hasattr(result, "content"):
        return str(result.content)
    return str(result) if result else ""


def extract_text_from_content(content: Any) -> str:
    """从 OpenAI 多模态 content 格式中提取纯文本。"""
    if isinstance(content, list):
        return " ".join(
            p.get("text", "")
            for p in content
            if isinstance(p, dict) and p.get("type") == "text"
        )
    return str(content) if content else ""


def extract_image_urls_from_content(content: Any) -> list[str]:
    """从 OpenAI 多模态 content 格式中提取图片 URL。"""
    if isinstance(content, list):
        return [
            p.get("image_url", {}).get("url", "")
            for p in content
            if isinstance(p, dict) and p.get("type") == "image_url"
        ]
    return []


# ── LLM JSON 解析（收口自 workflow/engine、memory/extractor、
#    plugin_config_assistant、skill_improvement_service 的重复实现）──

# ```json ... ``` / ``` ... ``` 围栏内的 {..} 片段（原 memory/extractor 实现）
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
# 嵌在普通文本中的 {...} 片段：首个 { 到最后一个 }（原 workflow/engine 兜底正则的泛化）
_JSON_SPAN_RE = re.compile(r"\{[\s\S]*\}")


def _repair_truncated_json(text: str) -> str | None:
    """尝试修复因 token 限制截断的不完整 JSON。

    当 LLM 输出因 finish_reason=length 被截断时，JSON 可能不完整。
    策略：跟踪字符串上下文和括号栈，记录所有"安全截断点"（逗号后或闭合括号后），
    从后往前尝试每个截断点，补全未闭合的括号后解析。

    Returns:
        修复后的 JSON 字符串（已验证可解析），或 None（无法修复）
    """
    text = text.strip()
    if not text:
        return None

    # 定位第一个 { 开始位置
    start = text.find("{")
    if start == -1:
        return None
    text = text[start:]

    in_string = False
    escape = False
    stack: list[str] = []
    # 记录 (截断位置, 当时的栈状态快照)
    safe_cuts: list[tuple[int, list[str]]] = []

    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in "{[":
            stack.append(ch)
        elif ch == "}":
            if stack and stack[-1] == "{":
                stack.pop()
                if not stack:
                    safe_cuts.append((i + 1, []))
        elif ch == "]":
            if stack and stack[-1] == "[":
                stack.pop()
                if stack:
                    safe_cuts.append((i + 1, list(stack)))
        elif ch == ",":
            safe_cuts.append((i + 1, list(stack)))

    # 如果栈为空，JSON 可能已经完整
    if not stack:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return text
        except json.JSONDecodeError as e:
            logger.debug("Initial JSON parse failed, will try safe-cut repair: {}", e)

    # 从后往前尝试每个安全截断点
    for cut_pos, cut_stack in reversed(safe_cuts):
        if cut_stack:
            # 仍有未闭合的括号，需截断并补全
            repaired = text[:cut_pos].rstrip()
            if repaired.endswith(","):
                repaired = repaired[:-1]
            for opener in reversed(cut_stack):
                repaired += "]" if opener == "[" else "}"
        else:
            # 栈为空，截断点处是完整 JSON
            repaired = text[:cut_pos]

        try:
            parsed = json.loads(repaired)
            if isinstance(parsed, dict):
                return repaired
        except json.JSONDecodeError:
            continue

    return None


def parse_llm_json(text: str, require_keys: tuple[str, ...] = ()) -> dict | None:
    """从 LLM 响应中解析 JSON 对象，全部候选失败返回 None。

    收口自四份重复实现的超集语义（只增不减）：
    1. 候选提取：markdown 代码围栏（```json / ```，find 切片 + 正则两种）、
       嵌在文本中的 {...} 片段、整段文本
    2. 截断修复兜底：LLM 因 finish_reason=length 输出被截断时按括号栈补全
       （_repair_truncated_json，原 workflow/engine 专属能力）

    Args:
        text: LLM 原始响应文本
        require_keys: 要求结果必须包含的键（如工作流计划的 "tasks"）；
            候选解析成功但缺少这些键时继续尝试下一候选，全部失败返回 None
    """
    if not isinstance(text, str):
        return None

    # 候选构造（原 plugin_config_assistant / skill_improvement_service 逐字逻辑：
    # 围栏切片候选插入队首，整段文本兜底）
    candidates: list[str] = [text]
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end > start:
            candidates.insert(0, text[start:end].strip())
    elif "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end > start:
            candidates.insert(0, text[start:end].strip())
    # 围栏内 {..} 正则候选（原 memory/extractor 逻辑）
    candidates.extend(m.group(1).strip() for m in _JSON_FENCE_RE.finditer(text))
    # 纯文本中的 {...} 片段候选（原 workflow/engine 的 tasks 片段正则泛化）
    span = _JSON_SPAN_RE.search(text)
    if span:
        candidates.append(span.group(0))

    def _accepts(data: Any) -> bool:
        return isinstance(data, dict) and all(k in data for k in require_keys)

    for cand in candidates:
        try:
            parsed = json.loads(cand)
        except json.JSONDecodeError:
            # 直接解析失败 → 截断修复兜底（原 workflow/engine 专属策略）
            repaired = _repair_truncated_json(cand)
            if repaired:
                try:
                    parsed = json.loads(repaired)
                except json.JSONDecodeError:
                    continue
                if _accepts(parsed):
                    if require_keys:
                        logger.warning("[utils] LLM JSON repaired from truncated output")
                    return parsed
            continue
        if _accepts(parsed):
            return parsed

    logger.warning(
        f"[utils] Failed to parse LLM JSON response, raw: {text[:200]}"
    )
    return None


class AsyncKeyLocks:
    """按 key 的异步锁集合。

    收口各处手写的 ``dict[str, asyncio.Lock]`` + 双检创建模式
    （platform_router / context_service / agent_orchestrator / workflow engine）。
    """

    def __init__(self) -> None:
        # 兼容历史调用点以 None 等非常规值作 key（如 context_service 的 agent_id=None）
        self._locks: dict[Any, asyncio.Lock] = {}
        self._guard = asyncio.Lock()

    async def get(self, key: Any) -> asyncio.Lock:
        """取 key 对应的锁，不存在则创建（双检；asyncio 单线程下创建原子）。"""
        if key in self._locks:
            return self._locks[key]
        async with self._guard:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            return self._locks[key]

    def discard(self, key: Any) -> None:
        """移除 key 对应的锁（存在则删，不存在静默返回）。"""
        self._locks.pop(key, None)


_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def sse_response(generator: Any, **kwargs: Any) -> StreamingResponse:
    """创建标准 SSE StreamingResponse（统一 headers 和 media_type）。"""
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
        **kwargs,
    )


def sse_data(event: Any) -> str:
    """格式化 SSE 数据行（支持 dict 和 Pydantic model）。"""
    if hasattr(event, "model_dump_json"):
        return f"data: {event.model_dump_json()}\n\n"
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


async def require_store(store: Any, key: str, label: str = "Entity") -> dict:
    """从 store 获取记录，不存在则抛出 NotFoundError。"""
    from app.core.exceptions import NotFoundError
    obj = await store.get_async(key)
    if not obj:
        raise NotFoundError(f"{label} {key} not found")
    return obj


def to_camel_case(data: dict) -> dict:
    """将字典的 snake_case 键转换为 camelCase。"""
    out = {}
    for k, v in data.items():
        parts = k.split("_")
        camel = parts[0] + "".join(p.capitalize() for p in parts[1:])
        if isinstance(v, dict):
            v = to_camel_case(v)
        elif isinstance(v, list):
            v = [to_camel_case(i) if isinstance(i, dict) else i for i in v]
        out[camel] = v
    return out


def require_value(value: Any, label: str, key: str) -> Any:
    """检查值是否存在，不存在则抛出 NotFoundError。"""
    from app.core.exceptions import NotFoundError
    if not value:
        raise NotFoundError(f"{label} {key} not found")
    return value


def ok(data: Any = None, message: str = "ok") -> dict:
    """统一成功响应信封。

    格式: {"code": 0, "message": "...", "error": None, "data": ...}
    - code: 0 表示成功（数字状态码，满足"API 响应必须包含错误码"硬性规则）
    - message: 用户可读消息
    - error: None 表示无错误（与历史格式兼容，前端 response.data 仍可取到数据）
    - data: 业务数据负载
    """
    return {"code": 0, "message": message, "error": None, "data": data}


def fail(
    message: str,
    err_code: str = "INTERNAL_ERROR",
    status_code: int = 500,
    data: Any = None,
) -> JSONResponse:
    """统一失败响应信封。

    格式: {"code": 1, "message": "...", "error": {"code": "...", "message": "..."}, "data": null}
    - code: 非 0 表示失败
    - message: 顶层用户可读消息（与 error.message 保持一致）
    - error: 包含字符串错误码 err_code 和详细 message（前端 extractErrorMessage 解析 error.code）
    - data: 失败时通常为 None
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "code": 1,
            "message": message,
            "error": {"code": err_code, "message": message},
            "data": data,
        },
    )
