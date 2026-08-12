"""Everything 文件搜索适配器（Windows，调用 es.exe 命令行）。

Everything 是 voidtools 出品的 Windows 文件索引工具，es.exe 是其官方命令行客户端。
本适配器通过子进程调用 es.exe，实现秒级全盘文件搜索。

依赖：
- 用户已安装 Everything（主程序运行中）
- es.exe 位于 PATH 或 backend/data/bin/ 或 Everything 安装目录

参考：Demo/ES 目录包含 es.exe 官方 C 源码（MIT 许可）。
"""
from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from typing import Any

from loguru import logger

from app.core.ports.file_search import FileSearchResult


# es.exe 候选搜索路径（按优先级）
_ES_CANDIDATE_PATHS = [
    # 1. 项目内置目录（打包版可随附，但首期不随附）
    Path(__file__).resolve().parent.parent.parent.parent.parent / "data" / "bin" / "es.exe",
    # 2. 常见 Everything 安装目录
    Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Everything" / "es.exe",
    Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")) / "Everything" / "es.exe",
    # 3. 用户自定义目录（环境变量）
    Path(os.environ.get("EVERYTHING_HOME", "")) / "es.exe",
]


class EverythingAdapter:
    """Everything 文件搜索适配器。

    通过调用 es.exe 命令行工具实现秒级文件搜索。
    仅在 Windows 平台可用，依赖 Everything 主程序运行。

    Usage:
        adapter = EverythingAdapter()
        if adapter.available():
            results = adapter.search("report", max_results=20)
    """

    def __init__(self) -> None:
        self._es_path: str | None = None
        self._cached_available: bool | None = None

    def _find_es_executable(self) -> str | None:
        """查找 es.exe 路径。

        搜索顺序：
        1. PATH 环境变量（shutil.which）
        2. 候选路径列表（_ES_CANDIDATE_PATHS）

        Returns:
            es.exe 的绝对路径字符串，未找到返回 None。
        """
        # 1. PATH 查找
        which_result = shutil.which("es")
        if which_result:
            return which_result

        # 2. 候选路径
        for candidate in _ES_CANDIDATE_PATHS:
            if candidate.exists() and candidate.is_file():
                return str(candidate)

        return None

    def available(self) -> bool:
        """检查 es.exe 是否可用（结果缓存）。"""
        if self._cached_available is not None:
            return self._cached_available

        self._es_path = self._find_es_executable()
        self._cached_available = self._es_path is not None

        if self._cached_available:
            logger.debug(f"[EverythingAdapter] 找到 es.exe: {self._es_path}")
        else:
            logger.debug("[EverythingAdapter] 未找到 es.exe，将回退到 OsWalkAdapter")

        return self._cached_available

    def search(
        self,
        query: str,
        max_results: int = 50,
        path: str | None = None,
    ) -> list[FileSearchResult]:
        """通过 es.exe 搜索文件（同步方法，内部使用 subprocess）。

        Args:
            query: 文件名片段（支持 Everything 搜索语法：空格=AND、| =OR、双引号=精确匹配）。
            max_results: 最大返回条数（默认 50）。
            path: 可选的搜索路径限定（None 表示全盘）。

        Returns:
            FileSearchResult 列表。

        Raises:
            RuntimeError: es.exe 不可用或执行失败。
        """
        if not self.available() or self._es_path is None:
            raise RuntimeError("es.exe 不可用，请使用 OsWalkAdapter 兜底")

        # 构建命令行参数
        cmd = [self._es_path, "-n", str(max_results)]
        if path:
            cmd.extend(["-path", path])
        cmd.append(query)

        logger.info(f"[EverythingAdapter] 执行: {' '.join(cmd)}")

        try:
            # 使用 subprocess.run（同步），因为 es.exe 执行很快（通常 < 100ms）
            import subprocess
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,  # 10 秒超时
                encoding="utf-8",
                errors="replace",
            )

            if result.returncode != 0:
                logger.warning(
                    f"[EverythingAdapter] es.exe 退出码 {result.returncode}: {result.stderr[:200]}"
                )
                # 返回码 2 表示没有匹配结果，不算错误
                if result.returncode == 2:
                    return []
                raise RuntimeError(f"es.exe 执行失败: {result.stderr[:200]}")

            # 解析输出：每行一个路径
            results: list[FileSearchResult] = []
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue

                p = Path(line)
                try:
                    size = p.stat().st_size if p.is_file() else 0
                    is_dir = p.is_dir()
                except OSError:
                    size = 0
                    is_dir = False

                results.append(FileSearchResult(
                    path=str(p),
                    size=size,
                    is_dir=is_dir,
                ))

            logger.info(f"[EverythingAdapter] 返回 {len(results)} 条结果")
            return results

        except subprocess.TimeoutExpired:
            logger.error("[EverythingAdapter] es.exe 执行超时")
            raise RuntimeError("es.exe 执行超时（10 秒）")
        except Exception as e:
            logger.error(f"[EverythingAdapter] 搜索失败: {e}", exc_info=True)
            raise RuntimeError(f"Everything 搜索失败: {e}") from e
