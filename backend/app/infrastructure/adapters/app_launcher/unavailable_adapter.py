"""Unavailable 适配器 -- 所有方法返回空 / False（兜底）。

当运行平台不属于 Windows / macOS / Linux 时使用，
保证 get_app_launcher_adapter() 始终返回一个符合 AppLauncherPort 的对象。
"""
from __future__ import annotations

from loguru import logger

from app.core.ports.app_launcher import AppInfo


class UnavailableAdapter:
    """空适配器 -- 平台不支持时的兜底实现。

    所有搜索返回空列表，启动返回 False，available() 返回 False。
    """

    def search_apps(self, keyword: str, limit: int = 20) -> list[AppInfo]:
        """始终返回空列表。"""
        logger.debug("[UnavailableAdapter] search_apps 调用，当前平台不支持")
        return []

    def launch(self, app_id: str) -> bool:
        """始终返回 False。"""
        logger.debug("[UnavailableAdapter] launch 调用，当前平台不支持")
        return False

    def available(self) -> bool:
        """始终返回 False。"""
        return False
