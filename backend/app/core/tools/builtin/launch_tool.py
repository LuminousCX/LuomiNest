"""应用启动工具 — 按名称搜索并启动已安装应用。

对齐 tool-system-optimization.md §4.6 T7：
- 工具名 launch_application，tier=domain，scope=shared，全平台
- 参数 name（应用名/游戏名，模糊匹配）
- 多候选时返回列表让 LLM 二次确认（参数 app_id 选择）
- 组合由 LLM 完成：search_everything 找到 exe → launch_application 启动
"""
from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from app.core.tools.registry import ToolBase, ToolResult


class LaunchApplicationTool(ToolBase):
    """按名称搜索并启动已安装的应用程序。"""

    # 对齐 tool-opt §4.6 T7：tier=domain, 全平台
    tier: str = "domain"
    scope: str = "shared"
    platform: frozenset[str] = frozenset({"win", "mac", "linux"})

    def __init__(self) -> None:
        super().__init__()
        self._adapter = None  # 延迟初始化

    def _get_adapter(self):
        """延迟获取应用启动适配器（首次调用时初始化）。"""
        if self._adapter is None:
            from app.infrastructure.adapters.app_launcher import get_app_launcher_adapter
            self._adapter = get_app_launcher_adapter()
            logger.info(
                f"[LaunchApplicationTool] 使用适配器: {type(self._adapter).__name__}"
            )
        return self._adapter

    @property
    def name(self) -> str:
        return "launch_application"

    @property
    def description(self) -> str:
        return (
            "按名称搜索已安装的应用程序并启动。"
            "支持模糊匹配（如输入 'chrome' 找到 Google Chrome）。"
            "多候选时返回候选列表。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": (
                        "应用名称或关键词（如 'chrome', 'visual studio', 'notepad'）"
                    ),
                },
                "action": {
                    "type": "string",
                    "enum": ["search", "launch"],
                    "default": "search",
                    "description": (
                        "search=仅搜索返回候选列表，launch=搜索并启动第一个匹配项"
                    ),
                },
                "app_id": {
                    "type": "string",
                    "description": (
                        "直接启动指定 app_id（跳过搜索，"
                        "用于 LLM 从候选列表中选择后直接启动）"
                    ),
                },
            },
            "required": ["name"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        app_id = (arguments.get("app_id") or "").strip()
        name = (arguments.get("name") or "").strip()
        action = (arguments.get("action") or "search").strip().lower()

        if action not in ("search", "launch"):
            action = "search"

        adapter = self._get_adapter()

        # ── 路径 1：直接按 app_id 启动 ──────────────────────────────────
        if app_id:
            try:
                result = await asyncio.to_thread(adapter.launch, app_id)
            except RuntimeError as e:
                return ToolResult.fail(f"启动失败: {e}")
            except Exception as e:
                logger.error(
                    f"[LaunchApplicationTool] 启动异常: {e}", exc_info=True
                )
                return ToolResult.fail(f"启动异常: {e}")

            return ToolResult.ok(
                f"已启动应用（app_id={app_id}）: {result}",
                metadata={"app_id": app_id, "action": "launch"},
            )

        # ── 路径 2：按名称搜索 ──────────────────────────────────────────
        if not name:
            return ToolResult.fail("缺少 name 或 app_id 参数")

        try:
            apps = await asyncio.to_thread(adapter.search_apps, name)
        except RuntimeError as e:
            return ToolResult.fail(f"搜索失败: {e}")
        except Exception as e:
            logger.error(
                f"[LaunchApplicationTool] 搜索异常: {e}", exc_info=True
            )
            return ToolResult.fail(f"搜索异常: {e}")

        if not apps:
            return ToolResult.ok(
                f"未找到匹配 '{name}' 的应用",
                metadata={"count": 0, "name": name},
            )

        # ── 单个结果 + action=launch → 自动启动 ─────────────────────────
        if action == "launch" and len(apps) == 1:
            app = apps[0]
            try:
                launch_result = await asyncio.to_thread(adapter.launch, app["app_id"])
            except RuntimeError as e:
                return ToolResult.fail(f"启动失败: {e}")
            except Exception as e:
                logger.error(
                    f"[LaunchApplicationTool] 启动异常: {e}", exc_info=True
                )
                return ToolResult.fail(f"启动异常: {e}")

            return ToolResult.ok(
                f"已启动: {app.get('display_name', app['app_id'])}",
                metadata={
                    "app_id": app["app_id"],
                    "display_name": app.get("display_name", ""),
                    "action": "launch",
                },
            )

        # ── 多个结果 / action=search → 返回候选列表 ─────────────────────
        lines: list[str] = []
        for i, app in enumerate(apps, 1):
            display = app.get("display_name", app["app_id"])
            lines.append(f"{i}. {display}  (app_id={app['app_id']})")

        output = "\n".join(lines)
        output += (
            f"\n\n（共 {len(apps)} 个候选应用。"
            "如需启动，请传入 app_id 参数选择具体应用。）"
        )

        return ToolResult.ok(
            output,
            metadata={
                "count": len(apps),
                "name": name,
                "action": action,
                "candidates": [
                    {"app_id": a["app_id"], "display_name": a.get("display_name", "")}
                    for a in apps
                ],
            },
        )
