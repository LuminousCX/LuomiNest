"""应用启动端口 -- 抽象接口定义（六边形 Ports & Adapters）。

对齐 tool-system-optimization.md ss4.6 T7：
- 按名称模糊搜索已安装应用并启动
- Windows / macOS / Linux 各自适配器实现

设计原则：
- Port 只定义接口，不感知具体平台实现
- 适配器通过 available() 自报告可用性
- 搜索返回结构化结果（name / path / icon / source）

依赖方向：外层适配器 -> 本 Port；本 Port -/> 适配器（顶层导入禁止）。
"""
from __future__ import annotations

from typing import Any, Protocol, TypedDict, runtime_checkable


class AppInfo(TypedDict, total=False):
    """应用信息。"""
    app_id: str          # 唯一标识（路径 hash 或名称）
    name: str            # 应用显示名
    path: str            # 可执行文件路径 / .app 路径
    icon: str            # 图标路径（可选）
    source: str          # 来源：start_menu / registry / applications / desktop


@runtime_checkable
class AppLauncherPort(Protocol):
    """应用启动端口协议。

    所有平台适配器（Windows / macOS / Linux）必须实现此接口。
    使用 duck-typing 的 Protocol，无需显式继承。
    """

    def search_apps(self, keyword: str, limit: int = 20) -> list[AppInfo]:
        """按关键词模糊搜索已安装应用。

        Args:
            keyword: 搜索关键词（应用名子串，case-insensitive）。
            limit: 最大返回条数（默认 20）。

        Returns:
            AppInfo 列表，按匹配度 / 名称排序。
        """
        ...

    def launch(self, app_id: str) -> bool:
        """启动指定应用。

        Args:
            app_id: 应用唯一标识，来自 search_apps 返回的 AppInfo["app_id"]。

        Returns:
            True 表示启动成功，False 表示失败。
        """
        ...

    def available(self) -> bool:
        """当前平台是否可用。"""
        ...
