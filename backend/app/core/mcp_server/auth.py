"""P0-3 传输安全：/mcp Bearer Token 鉴权。

背景：/mcp 挂载的 MCP 子应用此前完全裸奔（auth 中间件只拦 /api/*），
白名单含 memory_add/forget 等写记忆工具，局域网可达即可读写用户记忆。

实现：
- token 首次访问时用 secrets.token_urlsafe(32) 生成，持久化到 config_items
  键 mcp_server.token（经 ConfigRepository 的 fnmatch 加密模式落库加密）；
- BearerAuthMiddleware 是薄 ASGI 中间件，包裹挂载的 MCP 子应用：
  每个请求校验 Authorization: Bearer <token>，缺失/不匹配返回 401 JSON；
- MCP_SERVER_AUTH=false 可整体关闭鉴权（仅限明确知晓风险的场景）；
- token 短 TTL 进程内缓存，热路径不查库；重置后立即生效。

外部接入（mcp-remote）：
    npx mcp-remote http://127.0.0.1:18000/mcp \\
        --header "Authorization: Bearer ${LUOMINEST_MCP_TOKEN}"

注意：任何日志路径都不得打印 token 明文。
"""
from __future__ import annotations

import secrets
import time
from typing import Any

from loguru import logger

from app.core.config import settings

# token 在 config_items 中的存储键（见 ConfigRepository.ENCRYPTED_PATTERNS，落库自动加密）
TOKEN_CONFIG_KEY = "mcp_server.token"

# token 短 TTL 进程内缓存：(token, monotonic 时间戳)。与 auth/middleware.py 的
# token_version 缓存同一模式：热路径不查库，重置时显式刷新，TTL 兜底跨处修改。
_TOKEN_CACHE: tuple[str, float] | None = None
_TOKEN_CACHE_TTL = 10.0


def _get_store():
    """懒加载 config_store（避免模块导入期触碰 DB 会话工厂）。"""
    from app.infrastructure.database.config_store import luominest_config_store
    return luominest_config_store


def get_mcp_token(*, create: bool = False) -> str | None:
    """读取 MCP 访问 token；create=True 时首次访问自动生成并持久化。

    Returns:
        token 明文；store 不可用且未生成时返回 None（调用方 fail-closed）。
    """
    global _TOKEN_CACHE
    now = time.monotonic()
    cached = _TOKEN_CACHE
    if cached is not None and now - cached[1] < _TOKEN_CACHE_TTL:
        return cached[0]

    token = _get_store().get(TOKEN_CONFIG_KEY)
    if not (isinstance(token, str) and token):
        if not create:
            return None
        token = secrets.token_urlsafe(32)
        _get_store().set(TOKEN_CONFIG_KEY, token)
        logger.info("[McpAuth] 已生成新的 MCP 访问 token（存储于 config_items: mcp_server.token）")

    _TOKEN_CACHE = (token, now)
    return token


def reset_mcp_token() -> str:
    """重置 MCP 访问 token 并立即生效（旧 token 即刻失效）。"""
    global _TOKEN_CACHE
    token = secrets.token_urlsafe(32)
    _get_store().set(TOKEN_CONFIG_KEY, token)
    _TOKEN_CACHE = (token, time.monotonic())
    logger.info("[McpAPI] MCP 访问 token 已重置")  # 只记事件，不落 token 明文
    return token


def _extract_bearer_token(scope: dict[str, Any]) -> str:
    """从 ASGI scope 提取 Authorization: Bearer <token>（缺失/格式不符返回空串）。"""
    for raw_key, raw_value in scope.get("headers") or []:
        if raw_key.lower() == b"authorization":
            value = raw_value.decode("latin-1").strip()
            if value[:7].lower() == "bearer ":
                return value[7:].strip()
            return ""
    return ""


async def _send_401(send: Any, message: str) -> None:
    """发送统一信封的 401 JSON 响应（纯 ASGI，不经 Starlette Request）。"""
    body = (
        '{"code":1,"message":"%s",'
        '"error":{"code":"AUTH_FAILED","message":"%s"},"data":null}'
        % (message, message)
    ).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": 401,
        "headers": [
            (b"content-type", b"application/json; charset=utf-8"),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"www-authenticate", b"Bearer"),
        ],
    })
    await send({"type": "http.response.body", "body": body})


class BearerAuthMiddleware:
    """包裹挂载的 MCP 子应用的薄 ASGI 中间件（P0-3）。

    - 每个 HTTP 请求校验 Authorization: Bearer <token>；缺失/不匹配 → 401 JSON；
    - MCP_SERVER_AUTH=false 时整体放行（开关在 settings，调用期读取便于测试）；
    - 期望 token 缺失时 fail-closed（拒绝请求），与 /api 鉴权策略一致；
    - WebSocket 升级（scope type != http）不在本层处理：streamable_http_app
      仅使用 HTTP POST/GET/DELETE。
    """

    def __init__(self, app: Any, enabled: bool | None = None) -> None:
        self.app = app
        # enabled=None 表示按 settings.MCP_SERVER_AUTH 动态判定（测试可显式覆盖）
        self._enabled_override = enabled

    def _auth_enabled(self) -> bool:
        if self._enabled_override is not None:
            return self._enabled_override
        return bool(settings.MCP_SERVER_AUTH)

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http" or not self._auth_enabled():
            await self.app(scope, receive, send)
            return

        provided = _extract_bearer_token(scope)
        try:
            expected = get_mcp_token(create=True)
        except Exception:
            # store 异常（DB 不可用等）→ fail-closed，绝不静默放行
            logger.exception("[McpAuth] 读取/生成 MCP token 失败，拒绝请求（fail-closed）")
            await _send_401(send, "服务器 MCP 访问令牌暂不可用，请稍后重试")
            return
        if not expected:
            # 生成失败（store 异常等）→ fail-closed，绝不静默放行
            logger.error("[McpAuth] MCP token 不可用，拒绝请求（fail-closed）")
            await _send_401(send, "服务器未配置 MCP 访问令牌，请检查后端日志")
            return
        if not provided or not secrets.compare_digest(provided, expected):
            logger.warning(
                f"[McpAuth] 拒绝未授权请求: {scope.get('method', '')} {scope.get('path', '')}"
            )
            await _send_401(send, "未授权：缺少或错误的 MCP Bearer Token")
            return

        await self.app(scope, receive, send)
