"""应用启动适配器工厂 -- 按运行平台选择实现。

优先级：
- Windows: WindowsAdapter（注册表 App Paths + 开始菜单 .lnk）
- macOS: MacOSAdapter（/Applications 目录）
- Linux: LinuxAdapter（.desktop 文件 + which）
- 兜底: UnavailableAdapter（所有方法返回空 / False）

使用延迟导入：只在确定平台后才 import 对应适配器，
避免在不相关平台触发不必要的模块加载。
"""
from __future__ import annotations

import sys

from loguru import logger

from app.core.ports.app_launcher import AppLauncherPort


def get_app_launcher_adapter() -> AppLauncherPort:
    """获取当前平台的应用启动适配器。

    Returns:
        符合 AppLauncherPort 协议的适配器实例。
    """
    if sys.platform == "win32":
        from app.infrastructure.adapters.app_launcher.windows_adapter import WindowsAdapter
        logger.debug("[AppLauncher] 选择适配器: WindowsAdapter")
        return WindowsAdapter()

    elif sys.platform == "darwin":
        from app.infrastructure.adapters.app_launcher.macos_adapter import MacOSAdapter
        logger.debug("[AppLauncher] 选择适配器: MacOSAdapter")
        return MacOSAdapter()

    elif sys.platform.startswith("linux"):
        from app.infrastructure.adapters.app_launcher.linux_adapter import LinuxAdapter
        logger.debug("[AppLauncher] 选择适配器: LinuxAdapter")
        return LinuxAdapter()

    else:
        from app.infrastructure.adapters.app_launcher.unavailable_adapter import UnavailableAdapter
        logger.debug(f"[AppLauncher] 未识别平台 {sys.platform}，使用 UnavailableAdapter")
        return UnavailableAdapter()
