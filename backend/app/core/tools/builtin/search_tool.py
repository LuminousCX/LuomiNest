"""文件搜索工具。

使用 Python os.walk 实现文件夹递归搜索，支持文件名 glob 匹配和内容 grep。
不依赖 Everything SDK，纯 Python 实现，跨平台。
"""
from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path
from typing import Any

from loguru import logger

from ..registry import ToolBase, ToolResult

# 单次搜索最大返回条目数
MAX_SEARCH_RESULTS = 200
# 单次遍历最大文件数（防止遍历超大目录树）
MAX_VISITED_FILES = 5000
# 内容搜索时单文件最大读取字节数
MAX_GREP_FILE_BYTES = 256 * 1024  # 256KB
# 默认搜索深度限制
DEFAULT_MAX_DEPTH = 5


class SearchFilesTool(ToolBase):
    """递归搜索文件夹中的文件。

    支持两种模式：
    1. 按文件名 glob 模式搜索（如 *.py、test_*.ts）
    2. 按文件内容正则搜索（grep 模式）

    使用 os.walk 实现，跨平台，不依赖外部 SDK。
    """

    @property
    def name(self) -> str:
        return "search_files"

    @property
    def description(self) -> str:
        return (
            "Recursively search files in a directory using os.walk. "
            "Supports two modes: (1) filename glob pattern match (e.g. '*.py', 'test_*.ts'), "
            "(2) file content regex search (grep mode). "
            "Cross-platform, pure Python implementation. "
            "Returns matching file paths (and matching lines for content search)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Root directory to search in. Must be an existing directory.",
                },
                "pattern": {
                    "type": "string",
                    "description": (
                        "Filename glob pattern to match (e.g. '*.py', '*.ts', 'test_*'). "
                        "If content_pattern is provided, this filters which files to grep. "
                        "If only pattern is given, returns matching file paths."
                    ),
                    "default": "*",
                },
                "content_pattern": {
                    "type": "string",
                    "description": (
                        "Optional regex pattern to search within file contents (grep mode). "
                        "When provided, the tool reads each file matching 'pattern' and "
                        "returns lines that match this regex."
                    ),
                },
                "max_depth": {
                    "type": "integer",
                    "description": f"Maximum directory depth to traverse. Defaults to {DEFAULT_MAX_DEPTH}.",
                    "default": DEFAULT_MAX_DEPTH,
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "Whether content search is case-sensitive. Defaults to false.",
                    "default": False,
                },
            },
            "required": ["path"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        path_str = (arguments.get("path") or "").strip()
        pattern = arguments.get("pattern") or "*"
        content_pattern = arguments.get("content_pattern") or ""
        max_depth = max(1, int(arguments.get("max_depth") or DEFAULT_MAX_DEPTH))
        case_sensitive = bool(arguments.get("case_sensitive"))

        if not path_str:
            return ToolResult(success=False, error="path is required")

        root = Path(path_str).expanduser()
        if not root.exists():
            return ToolResult(success=False, error=f"Path not found: {root}")
        if not root.is_dir():
            return ToolResult(success=False, error=f"Not a directory: {root}")

        # 编译内容正则
        content_regex: re.Pattern[str] | None = None
        if content_pattern:
            try:
                flags = 0 if case_sensitive else re.IGNORECASE
                content_regex = re.compile(content_pattern, flags)
            except re.error as e:
                return ToolResult(success=False, error=f"Invalid content_pattern regex: {e}")

        logger.info(
            f"[SearchFilesTool] Searching in {root}, pattern={pattern!r}, "
            f"content_pattern={content_pattern!r}, max_depth={max_depth}"
        )

        try:
            results = await self._walk_and_search(
                str(root), pattern, content_regex, max_depth, case_sensitive
            )
        except Exception as e:
            logger.error(f"[SearchFilesTool] Search failed: {e}", exc_info=True)
            return ToolResult(success=False, error=f"Search failed: {e}")

        if not results:
            return ToolResult(
                success=True,
                output=f"No matches found in {root}",
                metadata={
                    "root": str(root),
                    "pattern": pattern,
                    "content_pattern": content_pattern,
                    "match_count": 0,
                },
            )

        output = "\n".join(results)
        return ToolResult(
            success=True,
            output=output,
            metadata={
                "root": str(root),
                "pattern": pattern,
                "content_pattern": content_pattern,
                "match_count": len(results),
                "truncated": len(results) >= MAX_SEARCH_RESULTS,
            },
        )

    async def _walk_and_search(
        self,
        root: str,
        pattern: str,
        content_regex: re.Pattern[str] | None,
        max_depth: int,
        case_sensitive: bool,
    ) -> list[str]:
        """执行 os.walk 遍历和搜索。"""
        results: list[str] = []
        visited = 0
        truncated = False

        for dirpath, dirnames, filenames in os.walk(root):
            # 计算当前深度
            rel_depth = os.path.relpath(dirpath, root)
            depth = 0 if rel_depth == "." else rel_depth.count(os.sep) + 1

            # 超过最大深度，跳过子目录
            if depth >= max_depth:
                dirnames[:] = []
                if depth > max_depth:
                    continue

            # 跳过常见无关目录（node_modules、.git、__pycache__ 等）
            dirnames[:] = [
                d for d in dirnames
                if d not in {".git", "node_modules", "__pycache__", ".venv", "venv", ".idea", ".vscode", "dist", "build"}
            ]

            for filename in filenames:
                if visited >= MAX_VISITED_FILES:
                    truncated = True
                    break
                visited += 1

                # 文件名匹配
                if not fnmatch.fnmatch(filename, pattern):
                    continue

                full_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(full_path, root)

                # 仅文件名匹配模式
                if content_regex is None:
                    if len(results) >= MAX_SEARCH_RESULTS:
                        truncated = True
                        break
                    try:
                        size = os.path.getsize(full_path)
                        results.append(f"[file] {rel_path} ({size} bytes)")
                    except OSError:
                        results.append(f"[file] {rel_path}")
                    continue

                # 内容搜索模式
                file_results = self._grep_file(full_path, rel_path, content_regex)
                if file_results:
                    if len(results) + len(file_results) >= MAX_SEARCH_RESULTS:
                        remaining = MAX_SEARCH_RESULTS - len(results)
                        results.extend(file_results[:remaining])
                        truncated = True
                        break
                    results.extend(file_results)

            if truncated:
                break

        if truncated and len(results) >= MAX_SEARCH_RESULTS:
            results.append(f"... (truncated at {MAX_SEARCH_RESULTS} matches)")

        return results

    def _grep_file(
        self,
        full_path: str,
        rel_path: str,
        regex: re.Pattern[str],
    ) -> list[str]:
        """在单个文件中执行 grep 搜索。"""
        try:
            size = os.path.getsize(full_path)
            if size > MAX_GREP_FILE_BYTES:
                return []
        except OSError:
            return []

        # 检测二进制文件
        try:
            with open(full_path, "rb") as f:
                head = f.read(1024)
            if b"\x00" in head:
                return []
        except OSError:
            return []

        matches: list[str] = []
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                for line_no, line in enumerate(f, start=1):
                    if len(matches) >= 20:
                        matches.append(f"  ... (more matches in {rel_path})")
                        break
                    if regex.search(line):
                        stripped = line.rstrip("\n\r")
                        if len(stripped) > 200:
                            stripped = stripped[:200] + "..."
                        matches.append(f"{rel_path}:{line_no}: {stripped}")
        except OSError:
            return []

        return matches
