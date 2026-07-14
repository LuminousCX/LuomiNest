"""通用工具函数——消除跨模块重复定义"""

import json
from datetime import datetime, timezone
from typing import Any

from fastapi.responses import StreamingResponse


def utc_now() -> str:
    """返回当前 UTC 时间的 ISO-8601 字符串。"""
    return datetime.now(timezone.utc).isoformat()


def utc_now_dt() -> datetime:
    """返回当前 UTC 时间的 datetime 对象（用于时间运算）。"""
    return datetime.now(timezone.utc)


def extract_llm_text(result: Any) -> str:
    """从 LLM 适配器返回值中提取纯文本（去除首尾空白）。"""
    return result.strip() if isinstance(result, str) else str(result).strip()


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


def ok(data: Any = None) -> dict:
    """统一成功响应信封。"""
    return {"error": None, "data": data}
