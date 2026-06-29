"""LuomiNest 认证中间件。

拦截所有 /api/* 请求，验证 Bearer Token。
/health 和 / 路由不受保护。
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from loguru import logger

from app.security.auth.local_token import load_auth_token, verify_token

_EXEMPT_PATHS = {"/health", "/"}


async def luomi_auth_middleware(request: Request, call_next):
    """Bearer Token 认证中间件。"""
    path = request.url.path
    if path in _EXEMPT_PATHS or not path.startswith("/api/"):
        return await call_next(request)

    expected_token = load_auth_token()
    if not expected_token:
        logger.debug("[Auth] No auth token configured, allowing request (dev mode)")
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    provided = ""
    if auth_header.startswith("Bearer "):
        provided = auth_header[7:].strip()

    if not verify_token(provided, expected_token):
        logger.warning(f"[Auth] Rejected unauthenticated request: {request.method} {path}")
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "AUTH_FAILED", "message": "未授权，请检查认证令牌"}},
        )

    return await call_next(request)
