"""API 速率限制中间件 — 基于 slowapi 的请求限流。

使用内存存储（单机桌面场景），为关键 API 端点提供速率限制：
- LLM 聊天补全：防止 API 配额耗尽
- 命令执行：防止 DoS
- 认证接口：防止暴力破解
- TTS/STT：防止资源滥用

限流粒度：基于客户端 IP（桌面场景下通常为 127.0.0.1，
但通过网络访问时按来源 IP 区分）。
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse
from loguru import logger


def _key_func(request: Request) -> str:
    """提取客户端标识用于限流分组。

    优先使用 Authorization header 中的 token hash（区分不同用户），
    回退到客户端 IP。
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:].strip()
        if token:
            # 使用 token 前 16 字符作为标识（避免记录完整 token）
            return f"token:{token[:16]}"
    return get_remote_address(request)


# 全局限流器实例（内存存储，重启后重置）
limiter = Limiter(
    key_func=_key_func,
    storage_uri="memory://",
    strategy="fixed-window",
)


# ---------------------------------------------------------------------------
# 预定义限流策略
# ---------------------------------------------------------------------------

# LLM 聊天补全：每分钟 30 次（防止 API 配额耗尽）
RATE_CHAT = "30/minute"

# 命令执行：每分钟 20 次
RATE_CONSOLE = "20/minute"

# 认证接口（登录/注册）：每分钟 10 次（防暴力破解）
RATE_AUTH = "10/minute"

# TTS/STT：每分钟 30 次
RATE_TTS = "30/minute"

# 文件上传：每分钟 20 次
RATE_UPLOAD = "20/minute"

# 通用 API：每分钟 120 次（兜底限流）
RATE_DEFAULT = "120/minute"


# ---------------------------------------------------------------------------
# 异常处理器（在 app_factory.py 中注册）
# ---------------------------------------------------------------------------

async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """slowapi 限流异常处理器，返回统一格式 429 响应。"""
    logger.warning(
        f"[RateLimit] {request.method} {request.url.path} 被限流: "
        f"{exc.detail} | client={_key_func(request)}"
    )
    return JSONResponse(
        status_code=429,
        content={
            "code": 1,
            "message": f"请求过于频繁，请稍后再试 ({exc.detail})",
            "error": {"code": "RATE_LIMITED", "message": exc.detail},
            "data": None,
        },
    )


__all__ = [
    "limiter",
    "rate_limit_exceeded_handler",
    "RATE_CHAT",
    "RATE_CONSOLE",
    "RATE_AUTH",
    "RATE_TTS",
    "RATE_UPLOAD",
    "RATE_DEFAULT",
]
