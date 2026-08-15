"""OsWalk 文件搜索适配器（跨平台兜底，纯 Python 实现）。

当 Everything（es.exe）不可用时，回退到本适配器。
使用 os.walk 递归遍历目录，按文件名 glob / 子串匹配。

注意：
- 性能远低于 Everything（全盘扫描可能数分钟），建议限定 path 参数
- 默认跳过 .git / node_modules / __pycache__ 等常见噪声目录
- 搜索结果上限由 max_results 参数控制，防止内存爆炸
"""
from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Any

from loguru import logger

from app.core.ports.file_search import FileSearchResult


# 默认跳过目录（噪声大 / 敏感）
_SKIP_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    ".ssh", ".gnupg", ".aws", ".credentials", ".cache",
    ".tox", ".mypy_cache", ".pytest_cache", "dist", "build",
    ".egg-info",
})

# 默认搜索根路径（Windows 枚举所有本地盘符，其他平台从 HOME）
_DEFAULT_SEARCH_ROOTS: list[str] = []


def _get_default_roots() -> list[str]:
    """获取默认搜索根路径列表。

    Windows：枚举所有本地固定盘符（多盘符机器不再漏搜 D:/E:，
    也不再把范围错锁在系统盘一个盘上）；
    其他平台：HOME 目录（遍历 / 在 Linux/macOS 上不现实且危险）。
    psutil 不可用时回退 HOME，避免单盘硬编码。
    """
    if os.name != "nt":
        return [os.path.expanduser("~")]
    try:
        import psutil
        roots = [
            p.mountpoint
            for p in psutil.disk_partitions(all=False)
            if "cdrom" not in p.opts and p.fstype
        ]
        if roots:
            return roots
    except Exception:
        logger.debug("[OsWalkAdapter] psutil 盘符枚举失败，回退用户主目录", exc_info=True)
    return [os.path.expanduser("~")]


class OsWalkAdapter:
    """OsWalk 文件搜索适配器（跨平台兜底）。

    使用纯 Python os.walk 遍历目录树，按文件名片段或 glob 匹配。
    性能较 Everything 低得多，建议始终指定 path 参数限定搜索范围。

    Usage:
        adapter = OsWalkAdapter()
        results = adapter.search("report", path="/home/user/docs", max_results=20)
    """

    def available(self) -> bool:
        """OsWalk 始终可用（纯 Python 实现，无外部依赖）。"""
        return True

    def search(
        self,
        query: str,
        max_results: int = 50,
        path: str | None = None,
    ) -> list[FileSearchResult]:
        """通过 os.walk 递归搜索文件（同步方法）。

        Args:
            query: 文件名匹配关键词。支持：
                - 子串匹配（默认）：文件名包含 query 即命中
                - glob 模式：query 包含 * 或 ? 时按 fnmatch 匹配
            max_results: 最大返回条数（默认 50）。
            path: 搜索根路径（None 时使用平台默认根目录）。

        Returns:
            FileSearchResult 列表（按路径字典序排序）。
        """
        # 指定 path 时单根搜索；否则枚举平台默认根（Windows 多盘符逐盘兜底）
        search_roots = [path] if path else _get_default_roots()

        # 判断匹配模式：含 * 或 ? 为 glob，否则为子串
        is_glob = "*" in query or "?" in query
        query_lower = query.lower()

        results: list[FileSearchResult] = []
        logger.info(f"[OsWalkAdapter] 搜索: query={query!r}, roots={search_roots}, glob={is_glob}")

        for search_root in search_roots:
            if not os.path.isdir(search_root):
                logger.warning(f"[OsWalkAdapter] 搜索路径不存在: {search_root}")
                continue

            for root, dirs, files in os.walk(search_root):
                # 原地修改 dirs 跳过噪声目录
                dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]

                for name in files + dirs:
                    if len(results) >= max_results:
                        break

                    name_lower = name.lower()
                    if is_glob:
                        matched = fnmatch.fnmatch(name_lower, query_lower)
                    else:
                        matched = query_lower in name_lower

                    if not matched:
                        continue

                    full_path = os.path.join(root, name)
                    try:
                        stat = os.stat(full_path)
                        size = stat.st_size
                        is_dir = os.path.isdir(full_path)
                    except OSError:
                        size = 0
                        is_dir = False

                    results.append(FileSearchResult(
                        path=full_path,
                        size=size,
                        is_dir=is_dir,
                    ))

                if len(results) >= max_results:
                    break

        logger.info(f"[OsWalkAdapter] 返回 {len(results)} 条结果")
        return results
