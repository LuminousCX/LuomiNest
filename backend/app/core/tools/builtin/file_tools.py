"""LuomiNest 文件操作工具集。

提供主 Agent 操作本地文件系统的能力：
- ReadFileTool：读取文件内容（含大小限制与编码处理）
- WriteFileTool：写入文件（支持覆盖与追加）
- ListFilesTool：列出目录树（限制深度避免过大输出）
- SearchFilesTool：递归搜索文件内容（正则匹配）

安全策略：
1. 读取/列表输出超过阈值时截断
2. 写入前自动创建父目录
3. 搜索结果数量有上限，避免内存爆炸
"""
import os
import re
from typing import Any

from loguru import logger

from app.core.tools.registry import ToolBase, ToolResult
from app.security.sandbox.file_path_policy import FilePathError, validate_file_path

# 输出截断阈值
_MAX_READ_BYTES = 50000
_MAX_LIST_ENTRIES = 500
_MAX_SEARCH_RESULTS = 100
_MAX_SEARCH_FILE_SIZE = 1024 * 1024  # 1MB，超过则跳过


class ReadFileTool(ToolBase):
    """读取文件内容"""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return (
            "读取本地文件内容。支持指定编码（默认 utf-8）。"
            f"单次最多读取 {_MAX_READ_BYTES} 字节，超出部分截断。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径（绝对或相对）"},
                "encoding": {"type": "string", "description": "文件编码", "default": "utf-8"},
            },
            "required": ["path"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        path = arguments.get("path", "").strip()
        if not path:
            return ToolResult.fail("缺少 path 参数")

        encoding = arguments.get("encoding") or "utf-8"

        try:
            resolved = validate_file_path(path, must_exist=True, is_dir=False)
        except FilePathError as e:
            return ToolResult.fail(str(e))

        try:
            size = os.path.getsize(resolved)
            with open(resolved, "r", encoding=encoding, errors="replace") as f:
                content = f.read(_MAX_READ_BYTES)
            truncated = size > _MAX_READ_BYTES or len(content) >= _MAX_READ_BYTES
            if truncated:
                content += f"\n...(文件已截断，总大小 {size} 字节)"
            return ToolResult.ok(content, metadata={"size": size, "truncated": truncated})
        except Exception as e:
            return ToolResult.fail(f"读取文件失败: {e}")


class WriteFileTool(ToolBase):
    """写入文件内容"""

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return (
            "写入内容到本地文件。默认覆盖原文件，设置 append=true 可追加。"
            "父目录不存在时会自动创建。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "content": {"type": "string", "description": "要写入的内容"},
                "append": {"type": "boolean", "description": "是否追加模式", "default": False},
                "encoding": {"type": "string", "description": "文件编码", "default": "utf-8"},
            },
            "required": ["path", "content"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        path = arguments.get("path", "").strip()
        if not path:
            return ToolResult.fail("缺少 path 参数")
        content = arguments.get("content", "")
        if content is None:
            return ToolResult.fail("缺少 content 参数")
        append = bool(arguments.get("append", False))
        encoding = arguments.get("encoding") or "utf-8"

        try:
            resolved = validate_file_path(path, must_exist=False)
        except FilePathError as e:
            return ToolResult.fail(str(e))

        try:
            parent = resolved.parent
            if parent and not parent.exists():
                os.makedirs(parent, exist_ok=True)

            mode = "a" if append else "w"
            with open(resolved, mode, encoding=encoding) as f:
                f.write(content)

            written = len(content)
            logger.info(f"[WriteFileTool] 写入 {written} 字符到 {resolved} (append={append})")
            return ToolResult.ok(
                f"已{'追加' if append else '写入'} {written} 字符到 {resolved}",
                metadata={"bytes": written, "append": append},
            )
        except Exception as e:
            return ToolResult.fail(f"写入文件失败: {e}")


class ListFilesTool(ToolBase):
    """列出目录文件树"""

    @property
    def name(self) -> str:
        return "list_files"

    @property
    def description(self) -> str:
        return (
            f"列出指定目录下的文件树（默认深度 2）。"
            f"最多返回 {_MAX_LIST_ENTRIES} 个条目，超出截断。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "目录路径"},
                "max_depth": {"type": "integer", "description": "最大递归深度", "default": 2},
            },
            "required": ["path"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        path = arguments.get("path", "").strip()
        if not path:
            return ToolResult.fail("缺少 path 参数")
        max_depth = int(arguments.get("max_depth") or 2)
        max_depth = max(1, min(max_depth, 5))

        try:
            resolved = validate_file_path(path, must_exist=True, is_dir=True)
        except FilePathError as e:
            return ToolResult.fail(str(e))

        entries: list[str] = []
        truncated = False

        def _walk(current: str, depth: int, prefix: str) -> None:
            nonlocal truncated
            if truncated or depth > max_depth:
                return
            try:
                items = sorted(os.listdir(current))
            except PermissionError:
                entries.append(f"{prefix}(无访问权限)")
                return
            except Exception as e:
                entries.append(f"{prefix}(读取失败: {e})")
                return

            for item in items:
                if len(entries) >= _MAX_LIST_ENTRIES:
                    entries.append(f"...(已截断，超过 {_MAX_LIST_ENTRIES} 个条目)")
                    truncated = True
                    return
                full = os.path.join(current, item)
                is_dir = os.path.isdir(full)
                marker = "/" if is_dir else ""
                entries.append(f"{prefix}{item}{marker}")
                if is_dir and depth < max_depth:
                    _walk(full, depth + 1, prefix + "  ")

        _walk(str(resolved), 1, "")

        output = "\n".join(entries)
        return ToolResult.ok(
            output,
            metadata={"count": len(entries), "truncated": truncated, "max_depth": max_depth},
        )


class SearchFilesTool(ToolBase):
    """递归搜索文件内容"""

    @property
    def name(self) -> str:
        return "search_files"

    @property
    def description(self) -> str:
        return (
            f"在指定目录下递归搜索文件内容（正则匹配）。"
            f"最多返回 {_MAX_SEARCH_RESULTS} 个匹配项，单文件超过 1MB 跳过。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "搜索根目录"},
                "pattern": {"type": "string", "description": "正则表达式"},
                "file_pattern": {
                    "type": "string",
                    "description": "文件名 glob 过滤（可选，如 *.py）",
                },
            },
            "required": ["path", "pattern"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        path = arguments.get("path", "").strip()
        if not path:
            return ToolResult.fail("缺少 path 参数")
        pattern_str = arguments.get("pattern", "").strip()
        if not pattern_str:
            return ToolResult.fail("缺少 pattern 参数")
        file_pattern = arguments.get("file_pattern") or None

        try:
            resolved = validate_file_path(path, must_exist=True, is_dir=True)
        except FilePathError as e:
            return ToolResult.fail(str(e))

        try:
            regex = re.compile(pattern_str, re.IGNORECASE)
        except re.error as e:
            return ToolResult.fail(f"正则表达式无效: {e}")

        if file_pattern:
            try:
                file_regex = re.compile(
                    "^" + re.escape(file_pattern).replace("\\*", ".*").replace("\\?", ".") + "$"
                )
            except re.error:
                file_regex = None
        else:
            file_regex = None

        matches: list[str] = []
        truncated = False
        search_root = str(resolved)

        for root, dirs, files in os.walk(search_root):
            if truncated:
                break
            # 跳过常见忽略目录和敏感目录
            dirs[:] = [d for d in dirs if d not in {
                ".git", "node_modules", "__pycache__", ".venv", "venv",
                ".ssh", ".gnupg", ".aws", ".credentials",
            }]
            for fname in files:
                if len(matches) >= _MAX_SEARCH_RESULTS:
                    truncated = True
                    break
                if file_regex and not file_regex.match(fname):
                    continue
                full = os.path.join(root, fname)
                try:
                    if os.path.getsize(full) > _MAX_SEARCH_FILE_SIZE:
                        continue
                    with open(full, "r", encoding="utf-8", errors="replace") as f:
                        for line_no, line in enumerate(f, 1):
                            if regex.search(line):
                                rel = os.path.relpath(full, search_root)
                                matches.append(f"{rel}:{line_no}: {line.rstrip()[:200]}")
                                if len(matches) >= _MAX_SEARCH_RESULTS:
                                    truncated = True
                                    break
                except (PermissionError, OSError):
                    continue
                except Exception as e:
                    logger.debug(f"[SearchFilesTool] 跳过文件 {full}: {e}")

        if not matches:
            return ToolResult.ok("未找到匹配项", metadata={"count": 0})

        output = "\n".join(matches)
        if truncated:
            output += f"\n...(结果已截断，超过 {_MAX_SEARCH_RESULTS} 个匹配项)"
        return ToolResult.ok(
            output,
            metadata={"count": len(matches), "truncated": truncated},
        )
