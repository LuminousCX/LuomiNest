"""平台适配器 Token 管理基础设施.

收口三个云端平台适配器（qq_official / wechat_mp / wechat_work）逐字相同的
access_token 双检缓存逻辑（`_ensure_access_token`）与 `target` 解析函数
（`_parse_target`）。各适配器只需实现 `_fetch_token()` 提供各自的
刷新 URL / payload / 失败日志。
"""

from __future__ import annotations

import asyncio
import time

from loguru import logger


def parse_target(target: str) -> tuple[str, str]:
    """解析 "type:id" 形式的消息目标，无前缀时默认 private。"""
    if ":" in target:
        t_type, t_id = target.split(":", 1)
        return t_type, t_id
    return "private", target


class AppTokenMixin:
    """云端平台适配器的 access_token 缓存 Mixin.

    子类需要：
    - 在 ``__init__`` 中初始化 ``self._access_token`` / ``self._token_expires`` /
      ``self._token_lock = asyncio.Lock()``
    - 设置 ``token_log_prefix``（token 相关日志前缀，如 "[QQOfficial]"）
    - 实现 ``_fetch_token()``：请求平台刷新接口，成功返回
      ``(token, expires_in)``，失败返回 ``None``（失败日志由子类负责）

    使用 ``_ensure_access_token()`` 获取缓存 token（过期时经双检锁自动刷新）。
    """

    token_log_prefix: str = "[AppToken]"

    _access_token: str
    _token_expires: float
    _token_lock: asyncio.Lock

    async def _fetch_token(self) -> tuple[str, int] | None:
        """向平台请求新的 access_token，返回 (token, expires_in)，失败返回 None."""
        raise NotImplementedError

    async def _refresh_access_token(self) -> bool:
        """刷新 access_token 并更新缓存；成功返回 True。"""
        try:
            result = await self._fetch_token()
        except Exception as e:
            logger.error(f"{self.token_log_prefix} Token refresh exception: {e}")
            return False
        if result is None:
            # 失败日志已由 _fetch_token 记录
            return False
        token, expires_in = result
        self._access_token = token
        self._token_expires = time.time() + expires_in - 300
        logger.info(
            f"{self.token_log_prefix} Access token refreshed, expires in {expires_in}s"
        )
        return True

    async def _ensure_access_token(self) -> str:
        if self._access_token and time.time() < self._token_expires:
            return self._access_token
        async with self._token_lock:
            if self._access_token and time.time() < self._token_expires:
                return self._access_token
            await self._refresh_access_token()
            return self._access_token
