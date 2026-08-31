"""文件搜索端口（六边形架构 Port，对齐 tool-opt §4.5 T6）。

定义文件搜索的统一接口契约。内层只依赖 Protocol，外层提供适配器：
- EverythingAdapter（Windows，调用 es.exe 命令行）
- OsWalkAdapter（跨平台兜底，封装现有 SearchFilesTool 逻辑）

依赖方向：外层适配器 → 本 Port；本 Port ↛ 适配器（顶层导入禁止）。
"""
from __future__ import annotations

from typing import Protocol, TypedDict


class FileSearchResult(TypedDict):
    """文件搜索结果条目。"""
    path: str          # 文件绝对路径
    size: int          # 文件大小（字节），不可知时为 0
    is_dir: bool       # 是否为目录


class FileSearchPort(Protocol):
    """文件搜索端口契约。

    所有适配器（Everything / OsWalk 等）必须实现此接口。
    使用 duck-typing 的 Protocol，无需显式继承。
    """

    def search(self, query: str, max_results: int = 50, path: str | None = None) -> list[FileSearchResult]:
        """搜索文件。

        Args:
            query: 搜索关键词（文件名片段 / glob / 正则，具体语义由适配器决定）。
            max_results: 最大返回条数。
            path: 可选的搜索根路径限定（None 表示全盘 / 默认根）。

        Returns:
            FileSearchResult 列表（按相关性或修改时间排序）。
        """
        ...

    def available(self) -> bool:
        """返回适配器是否可用（依赖是否满足）。"""
        ...
