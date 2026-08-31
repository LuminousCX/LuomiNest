"""内部服务认证模块 — 用于 Java 后端等可信内部调用。

提供基于共享 Token 的内部服务间认证，使用 ``secrets.compare_digest``
进行常量时间比较以防止时序攻击。

Header 约定：
- ``X-LuomiNest-Internal-Token``: 内部认证令牌
- ``X-LuomiNest-Owner-User-Id``: 代理用户 ID（可选，系统级调用时省略）
"""

from __future__ import annotations

import secrets

from fastapi import Request
from loguru import logger

from app.core.exceptions import AuthenticationError

# ── Header 常量 ──────────────────────────────────────────────────────────────

INTERNAL_TOKEN_HEADER = "X-LuomiNest-Internal-Token"
"""内部认证 Token Header 名称。"""

OWNER_USER_ID_HEADER = "X-LuomiNest-Owner-User-Id"
"""代理用户 ID Header 名称（可选）。"""


class InternalAuth:
    """内部认证管理器。

    用于验证来自 Java 后端等可信内部服务的请求。
    Token 通过 ``INTERNAL_AUTH_TOKEN`` 配置项设置，
    留空则禁用内部认证通道。
    """

    def __init__(self, token: str | None = None) -> None:
        self._token = token

    @classmethod
    def from_settings(cls) -> InternalAuth:
        """从应用配置创建实例。"""
        from app.core.config import settings

        return cls(token=settings.INTERNAL_AUTH_TOKEN or None)

    def is_configured(self) -> bool:
        """是否已配置内部认证 Token。"""
        return self._token is not None and len(self._token) > 0

    async def verify(self, request: Request) -> dict | None:
        """验证内部认证 Token。

        根据请求 Header 判断是否为内部调用：

        - **无 Token Header** → 返回 ``None``（不是内部请求，交由后续认证处理）
        - **有 Token Header 且验证通过** → 返回用户信息 dict
        - **有 Token Header 但验证失败** → 抛出 ``HTTPException(401)``

        Args:
            request: FastAPI 请求对象。

        Returns:
            验证通过时返回包含 ``user_id``、``is_internal``、``roles`` 的字典；
            非内部请求返回 ``None``。
        """
        token = request.headers.get(INTERNAL_TOKEN_HEADER)
        if token is None:
            return None  # 不是内部请求

        if not self.is_configured():
            logger.warning(
                "[InternalAuth] Request with internal token header but token not configured"
            )
            raise AuthenticationError("Internal authentication not configured")

        if not secrets.compare_digest(token, self._token):
            logger.warning(
                "[InternalAuth] Invalid internal token presented"
            )
            raise AuthenticationError("Invalid internal token", code="AUTH_INVALID_TOKEN")

        # 内部认证通过，检查是否有代理用户（系统级调用时省略此 Header）
        owner_user_id = request.headers.get(OWNER_USER_ID_HEADER)

        logger.info(
            f"[InternalAuth] Internal request authenticated"
            f"{f' on behalf of user {owner_user_id}' if owner_user_id else ' (system-level)'}"
        )

        return {
            "user_id": owner_user_id,  # 可能为 None（系统级调用）
            "is_internal": True,
            "roles": ["internal"],
        }
