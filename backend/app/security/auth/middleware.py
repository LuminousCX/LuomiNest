"""LuomiNest 认证中间件。

拦截所有 /api/* 请求，根据 AUTH_MODE 选择认证方式：
- "local" 模式：Bearer Token + secrets.compare_digest（向后兼容）
- "jwt" 模式：JWT 验证（Fail-Closed），并比对 DB token_version 实现登出/吊销

/health 和 / 路由不受保护。
"""
import time
from functools import lru_cache

from fastapi import HTTPException, Request
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

# token_version 短 TTL 进程内缓存（user_id → (version, monotonic 时间戳)）。
# 认证热路径不能每请求查库；代价是登出/改密吊销后旧 token 最多再用 TTL 秒。
_TOKEN_VERSION_CACHE: dict[str, tuple[int, float]] = {}
_TOKEN_VERSION_CACHE_TTL = 10.0
_TOKEN_VERSION_CACHE_MAX = 1024


async def load_user_token_version(user_id: str, *, use_cache: bool = True) -> int | None:
    """查询用户当前 token_version（用于 JWT 吊销比对）；用户不存在返回 None。

    HTTP 中间件热路径走缓存；WS 握手等低频路径可传 use_cache=False 直查。
    """
    if use_cache:
        now = time.monotonic()
        cached = _TOKEN_VERSION_CACHE.get(user_id)
        if cached is not None and now - cached[1] < _TOKEN_VERSION_CACHE_TTL:
            return cached[0]

    from sqlalchemy import select

    from app.infrastructure.database.models.user import User
    from app.infrastructure.database.session import async_session_factory

    async with async_session_factory() as session:
        result = await session.execute(
            select(User.token_version).where(User.id == user_id)
        )
        row = result.scalar_one_or_none()

    if row is None:
        return None
    if len(_TOKEN_VERSION_CACHE) >= _TOKEN_VERSION_CACHE_MAX:
        _TOKEN_VERSION_CACHE.clear()  # 防膨胀兜底：单用户桌面应用实际远达不到上限
    _TOKEN_VERSION_CACHE[user_id] = (int(row), time.monotonic())
    return int(row)


def invalidate_token_version_cache(user_id: str) -> None:
    """登出/改密吊销后清除缓存，令版本比对立即生效（不留 TTL 残留窗口）。"""
    _TOKEN_VERSION_CACHE.pop(user_id, None)


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
    """从请求中提取 Token（仅 Authorization 头）。

    历史实现回退 ?token= query 参数（WebSocket 场景的兜底扩散到了全部 /api），
    令牌会随之进入请求日志、浏览器历史与代理日志。WS 握手由 ws_auth.py 在
    其自己的 query 通道校验，HTTP 侧不再接受 query 传令牌。
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
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

    # 验证 JWT（expected_type 默认 "access"：refresh token 不能当 access token 用）
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

    # 比对 DB token_version：登出/改密吊销后旧 token 立即失效
    # （get_current_user 的兜底仅覆盖注入该依赖的端点，其余端点靠此处拦截）
    user_id = payload.get("sub") or ""
    token_version = int(payload.get("ver", 1) or 1)
    current_version = await load_user_token_version(user_id)
    if current_version is None or token_version != current_version:
        # 缓存可能滞后于刚发生的登出/重新登录（版本单调递增、缓存滞后偏低会误拒新 token），
        # 不匹配时绕过缓存直查 DB 复核一次（仅罕见路径多一次查询）
        current_version = await load_user_token_version(user_id, use_cache=False)
    if current_version is None:
        logger.warning(f"[Auth/JWT] Unknown user, rejecting: {user_id} | {request.method} {path}")
        return _auth_failed_response(f"认证失败: 用户 {user_id} 不存在")
    if token_version != current_version:
        logger.warning(f"[Auth/JWT] Stale token_version, rejecting: {user_id} | {request.method} {path}")
        return _auth_failed_response("认证失败: 令牌已失效，请重新登录")

    # 将用户信息存入 request.state 供后续依赖注入使用
    request.state.user = {
        "user_id": payload.get("sub"),
        "roles": payload.get("roles", []),
        "device_id": payload.get("device_id", ""),
        "token_version": payload.get("ver", 1),
    }

    return await call_next(request)


def _auth_failed_response(message: str) -> JSONResponse:
    """构造统一信封的 401 响应。"""
    return JSONResponse(
        status_code=401,
        content={
            "code": 1,
            "message": message,
            "error": {"code": "AUTH_FAILED", "message": message},
            "data": None,
        },
    )


async def _handle_local_auth(request: Request, call_next):
    """local 模式认证处理（Fail-Closed）。

    与 ws_auth.py 保持一致：无 token 时拒绝请求，
    防止 token 文件丢失/不可读时 API 静默开放。
    """
    path = request.url.path
    if path in _LOCAL_EXEMPT_PATHS or not path.startswith("/api/"):
        return await call_next(request)

    expected_token = load_auth_token()
    if not expected_token:
        logger.warning(
            f"[Auth/Local] No auth token available, rejecting request (fail-closed): "
            f"{request.method} {path}"
        )
        return JSONResponse(
            status_code=401,
            content={
                "code": 1,
                "message": "服务器未配置认证令牌，请检查后端启动日志",
                "error": {"code": "AUTH_FAILED", "message": "服务器认证未配置"},
                "data": None,
            },
        )

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
    """三通道认证中间件。

    认证顺序：
    1. 内部服务认证：X-LuomiNest-Internal-Token（INTERNAL_AUTH_TOKEN 配置时启用，
       供可信内部服务调用，可选 X-LuomiNest-Owner-User-Id 代理用户）
    2. 根据 settings.AUTH_MODE 选择：
       - "local"（默认）：Bearer Token + 常量时间比较，Fail-Closed
       - "jwt"：JWT 验证，Fail-Closed，无 Token 或验证失败返回 401
    """
    # ── 内部服务认证 ──
    from app.security.auth.internal_auth import InternalAuth

    try:
        internal_user = await InternalAuth.from_settings().verify(request)
    except HTTPException as exc:
        # verify 抛出 401（token 无效/未配置），转统一信封
        detail = exc.detail if isinstance(exc.detail, str) else "内部认证失败"
        logger.warning(f"[Auth/Internal] Rejected: {request.method} {request.url.path}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": 1,
                "message": detail,
                "error": {"code": "AUTH_FAILED", "message": detail},
                "data": None,
            },
        )
    if internal_user is not None:
        request.state.user = internal_user
        return await call_next(request)

    # ── 常规认证（local / jwt）──
    if settings.AUTH_MODE == "jwt":
        return await _handle_jwt_auth(request, call_next)
    else:
        return await _handle_local_auth(request, call_next)
