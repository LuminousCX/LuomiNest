"""LuomiNest 浏览器自动化客户端（兼容门面，已废弃）。

原实现位于 services 层并被 core 工具直接引用，构成分层倒置；
现已迁移至核心端口 app.core.ports.browser_automation（六边形架构）。
本文件仅保留再导出以兼容潜在旧引用，新代码请直接使用核心端口；
确认无外部引用后可整体移除。
"""
from app.core.ports.browser_automation import (  # noqa: F401
    execute_browser_action,
    register_browser_executor,
)

__all__ = ["execute_browser_action", "register_browser_executor"]
