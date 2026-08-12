"""search_everything 文件搜索工具（tier=domain, platform=win，对齐 tool-opt §4.5 T6）。

通过 FileSearchPort 适配器搜索本地文件：
- 优先使用 EverythingAdapter（调用 es.exe，秒级全盘搜索）
- 不可用时回退 OsWalkAdapter（纯 Python os.walk，性能较低）

设计原则：
- 工具层只依赖 Port（FileSearchPort），不直接依赖具体适配器
- 适配器选择由工厂函数 get_file_search_adapter() 决定
- 仅在 Windows 平台注册（platform=frozenset({"win"})）

注：macOS/Linux 用户仍可继续使用 search_files（内容搜索）和 list_files（目录列表）。
"""
from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from app.core.tools.registry import ToolBase, ToolResult


class SearchEverythingTool(ToolBase):
    """秒级文件搜索（Everything / OsWalk 适配器）。"""

    # 对齐 tool-opt §4.5：tier=domain, platform=win
    tier: str = "domain"
    scope: str = "shared"
    platform: frozenset[str] = frozenset({"win"})

    def __init__(self) -> None:
        super().__init__()
        self._adapter = None  # 延迟初始化

    def _get_adapter(self):
        """延迟获取最优适配器（首次调用时初始化）。"""
        if self._adapter is None:
            from app.infrastructure.adapters.file_search import get_file_search_adapter
            self._adapter = get_file_search_adapter()
            logger.info(
                f"[SearchEverythingTool] 使用适配器: {type(self._adapter).__name__}"
            )
        return self._adapter

    @property
    def name(self) -> str:
        return "search_everything"

    @property
    def description(self) -> str:
        return (
            "秒级搜索本地文件（按文件名）。支持子串匹配和 glob 模式（*、?）。"
            "可选指定搜索路径（默认全盘）。"
            "返回匹配文件的绝对路径列表（含文件大小和类型信息）。"
            "在 Windows 上优先使用 Everything（es.exe），不可用时回退到纯 Python 遍历。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "搜索关键词（文件名片段或 glob 模式）。"
                        "示例: 'report' 匹配含 report 的文件名, '*.pdf' 匹配所有 PDF"
                    ),
                },
                "path": {
                    "type": "string",
                    "description": "搜索根路径（可选，不指定则全盘搜索）",
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大返回条数（默认 50，最大 200）",
                    "default": 50,
                },
            },
            "required": ["query"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        query = arguments.get("query", "").strip()
        if not query:
            return ToolResult.fail("缺少 query 参数")

        path = arguments.get("path") or None
        max_results = min(int(arguments.get("max_results") or 50), 200)

        adapter = self._get_adapter()

        try:
            # 适配器方法是同步的，用 asyncio.to_thread 避免阻塞事件循环
            results = await asyncio.to_thread(
                adapter.search, query=query, max_results=max_results, path=path,
            )
        except RuntimeError as e:
            return ToolResult.fail(f"搜索失败: {e}")
        except Exception as e:
            logger.error(f"[SearchEverythingTool] 搜索异常: {e}", exc_info=True)
            return ToolResult.fail(f"搜索异常: {e}")

        if not results:
            return ToolResult.ok(
                f"未找到匹配 '{query}' 的文件",
                metadata={"count": 0, "query": query},
            )

        # 格式化输出
        lines: list[str] = []
        for i, r in enumerate(results, 1):
            type_tag = "[DIR]" if r["is_dir"] else "[FILE]"
            size_str = _format_size(r["size"]) if r["size"] else ""
            lines.append(f"{i}. {type_tag} {r['path']}  {size_str}")

        output = "\n".join(lines)
        adapter_name = type(adapter).__name__
        output += f"\n\n（共 {len(results)} 条结果，适配器: {adapter_name}）"

        return ToolResult.ok(
            output,
            metadata={
                "count": len(results),
                "query": query,
                "adapter": adapter_name,
                "path": path,
            },
        )


def _format_size(size_bytes: int) -> str:
    """将字节数格式化为人类可读字符串。"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
