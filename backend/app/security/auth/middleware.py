"""LuomiNest 认证中间件。

拦截所有 /api/* 请求，根据 AUTH_MODE 选择认证方式：
- "local" 模式：Bearer Token + secrets.compare_digest（向后兼容）
- "jwt" 模式：JWT 验证（Fail-Closed）

/health 和 / 路由不受保护。
"""
from functools import lru_cache

from fastapi import Request
from fastapi.responses import JSONResponse
from loguru import logger

from app.core.config import settings
from app.security.auth.local_token import load_auth_token, verify_token as local_verify_token

# JWT 模式下无需认证的路径白名单
# 注意：refresh 必须放行，否则 access_token 过期后无法刷新（中间件会要求带有效 access_token 形成死循环）
# /docs、/redoc、/openapi.json 仅在 DEBUG 或 API_DOCS_ENABLED 时放行，生产环境默认关闭
_JWT_EXEMPT_PATHS_ALWAYS = {
    "/health",
    "/",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
}

_JWT_EXEMPT_PATHS_DOCS = {
    "/docs",
    "/redoc",
    "/openapi.json",
}

# local 模式下豁免的路径（保持向后兼容）
_LOCAL_EXEMPT_PATHS = {"/health", "/"}


@lru_cache(maxsize=1)
def _get_jwt_exempt_paths() -> set[str]:
    """根据配置返回当前 JWT 白名单（合并始终放行与文档条件放行）。

    使用 lru_cache 缓存：白名单仅依赖不可变的 DEBUG / API_DOCS_ENABLED 配置，
    进程内构造一次即可，避免认证热路径上重复计算。
    """
    if settings.DEBUG or settings.API_DOCS_ENABLED:
        return _JWT_EXEMPT_PATHS_ALWAYS | _JWT_EXEMPT_PATHS_DOCS
    return _JWT_EXEMPT_PATHS_ALWAYS


def _extract_token_from_request(request: Request) -> str | None:
    """从请求中提取 Token（支持 Header 和 Query 参数）。

    优先从 Authorization: Bearer <token> 头提取，
    若无则从 URL query 参数 ?token= 提取（WebSocket 场景）。
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if token:
            return token

    # 回退到 query 参数（WebSocket 场景）
    token = request.query_params.get("token", "")
    if token:
        return token

    return None


async def _handle_jwt_auth(request: Request, call_next):
    """JWT 模式认证处理（Fail-Closed）。"""
    path = request.url.path

    # 白名单路径直接放行
    if path in _get_jwt_exempt_paths() or not path.startswith("/api/"):
        return await call_next(request)

    token = _extract_token_from_request(request)
    if not token:
        logger.warning(f"[Auth/JWT] Rejected request without token: {request.method} {path}")
        return JSONResponse(
            status_code=401,
            content={
                "code": 1,
                "message": "未授权，缺少认证令牌",
                "error": {"code": "AUTH_FAILED", "message": "未授权，缺少认证令牌"},
                "data": None,
            },
        )

    # 验证 JWT
    from app.security.auth.jwt_handler import verify_token as jwt_verify_token, TokenError

    try:
        payload = jwt_verify_token(token)
    except TokenError as exc:
        logger.warning(f"[Auth/JWT] Token verification failed: {exc.message} | {request.method} {path}")
        return JSONResponse(
            status_code=401,
            content={
                "code": 1,
                "message": f"认证失败: {exc.message}",
                "error": {"code": "AUTH_FAILED", "message": exc.message},
                "data": None,
            },
        )

    # 将用户信息存入 request.state 供后续依赖注入使用
    request.state.user = {
        "user_id": payload.get("sub"),
        "roles": payload.get("roles", []),
        "device_id": payload.get("device_id", ""),
        "token_version": payload.get("ver", 1),
    }

    return await call_next(request)


async def _handle_local_auth(request: Request, call_next):
    """local 模式认证处理（向后兼容，行为完全不变）。"""
    path = request.url.path
    if path in _LOCAL_EXEMPT_PATHS or not path.startswith("/api/"):
        return await call_next(request)

    expected_token = load_auth_token()
    if not expected_token:
        logger.debug("[Auth] No auth token configured, allowing request (dev mode)")
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    provided = ""
    if auth_header.startswith("Bearer "):
        provided = auth_header[7:].strip()

    if not local_verify_token(provided, expected_token):
        logger.warning(f"[Auth] Rejected unauthenticated request: {request.method} {path}")
        return JSONResponse(
            status_code=401,
            content={
                "code": 1,
                "message": "未授权，请检查认证令牌",
                "error": {"code": "AUTH_FAILED", "message": "未授权，请检查认证令牌"},
                "data": None,
            },
        )

    return await call_next(request)


async def luomi_auth_middleware(request: Request, call_next):
    """双模式认证中间件。

    根据 settings.AUTH_MODE 选择认证方式：
    - "local"（默认）：Bearer Token + 常量时间比较，无 Token 时放行（向后兼容）
    - "jwt"：JWT 验证，Fail-Closed，无 Token 或验证失败返回 401
    """
    if settings.AUTH_MODE == "jwt":
        return await _handle_jwt_auth(request, call_next)
    else:
        return await _handle_local_auth(request, call_next)
