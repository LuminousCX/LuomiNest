"""文件工具路径安全策略 — 工作空间限制 + 敏感路径拦截。

为 AI Agent 的文件操作工具（ReadFile/WriteFile/ListFiles/SearchFiles）提供
路径校验，确保：
1. 文件操作限制在允许的根目录内（默认 DATA_DIR/sandbox）
2. 阻止访问 .ssh、.env、credentials 等敏感路径
3. 阻止路径遍历（../）逃逸出允许目录

复用 command_validator.py 中的敏感路径段黑名单，保持策略一致。
"""

from __future__ import annotations

import os
from pathlib import Path

from loguru import logger

from app.security.sandbox.command_validator import _SENSITIVE_PATH_SEGMENTS


# config_items 存储键名 — 用户可配置的额外允许目录
KEY_FILE_ALLOWED_DIRS = "file_tools.allowed_dirs"


def _get_default_allowed_roots() -> list[Path]:
    """获取默认的允许文件操作根目录列表。"""
    from app.core.config import settings
    sandbox_root = Path(settings.DATA_DIR) / "sandbox"
    sandbox_root.mkdir(parents=True, exist_ok=True)
    return [sandbox_root.resolve()]


def _load_extra_allowed_dirs() -> list[Path]:
    """加载用户配置的额外允许目录。"""
    try:
        from app.infrastructure.database.config_store import lumi_config_store
        dirs = lumi_config_store.get(KEY_FILE_ALLOWED_DIRS, []) or []
    except Exception:
        return []

    result: list[Path] = []
    for d in dirs:
        if not isinstance(d, str):
            continue
        d = d.strip()
        if not d:
            continue
        try:
            p = Path(d).resolve()
            if p.is_dir():
                result.append(p)
            else:
                logger.warning(f"[FilePathPolicy] 额外目录不存在或不是目录: {d}")
        except Exception:
            logger.warning(f"[FilePathPolicy] 无效目录路径: {d}")
    return result


def get_allowed_roots() -> list[Path]:
    """获取所有允许的文件操作根目录。"""
    roots = _get_default_allowed_roots()
    roots.extend(_load_extra_allowed_dirs())
    return roots


def save_extra_allowed_dirs(dirs: list | None) -> list[str]:
    """保存用户配置的额外允许目录。

    Args:
        dirs: 目录路径列表。

    Returns:
        保存后的规范化列表。
    """
    if not dirs:
        cleaned: list[str] = []
    else:
        seen: set[str] = set()
        cleaned = []
        for d in dirs:
            if not isinstance(d, str):
                continue
            d = d.strip()
            if not d or d in seen:
                continue
            seen.add(d)
            cleaned.append(d)

    try:
        from app.infrastructure.database.config_store import lumi_config_store
        lumi_config_store.set(KEY_FILE_ALLOWED_DIRS, cleaned)
        logger.info(f"[FilePathPolicy] 额外允许目录已保存: {cleaned}")
    except Exception as e:
        logger.warning(f"[FilePathPolicy] 保存额外允许目录失败: {e}")

    return cleaned


class FilePathError(Exception):
    """文件路径校验失败。"""

    def __init__(self, message: str, path: str = ""):
        self.path = path
        super().__init__(message)


def validate_file_path(
    path: str,
    *,
    must_exist: bool = True,
    is_dir: bool = False,
) -> Path:
    """校验文件路径的安全策略。

    执行三层校验：
    1. 路径解析（处理相对路径、符号链接）
    2. 工作空间包含性检查（路径必须在允许的根目录下）
    3. 敏感路径段黑名单（.ssh、.env、credentials 等）

    Args:
        path: 原始路径字符串（支持绝对或相对路径）。
        must_exist: 路径是否必须存在。
        is_dir: 是否期望路径为目录。

    Returns:
        解析后的绝对 Path 对象。

    Raises:
        FilePathError: 路径校验失败。
    """
    if not path or not path.strip():
        raise FilePathError("路径不能为空")

    # 1. 解析为绝对路径
    raw = Path(path.strip())
    if raw.is_absolute():
        resolved = raw.resolve()
    else:
        # 相对路径：相对于默认沙箱工作空间
        from app.core.config import settings
        workspace = Path(settings.DATA_DIR) / "sandbox"
        resolved = (workspace / raw).resolve()

    # 2. 工作空间包含性检查
    allowed_roots = get_allowed_roots()
    within_any = False
    for root in allowed_roots:
        try:
            resolved.relative_to(root)
            within_any = True
            break
        except ValueError:
            continue

    if not within_any:
        allowed_str = ", ".join(str(r) for r in allowed_roots)
        raise FilePathError(
            f"路径越界: {resolved} 不在允许的目录内 ({allowed_str})",
            path=str(resolved),
        )

    # 3. 敏感路径段黑名单
    normalized = str(resolved).replace("\\", "/")
    segments = [s for s in normalized.split("/") if s]
    for segment in segments:
        if segment.lower() in _SENSITIVE_PATH_SEGMENTS:
            raise FilePathError(
                f"路径命中敏感段黑名单: {segment}",
                path=str(resolved),
            )

    # 4. 存在性和类型检查
    if must_exist:
        if not resolved.exists():
            raise FilePathError(f"路径不存在: {path}", path=str(resolved))
        if is_dir and not resolved.is_dir():
            raise FilePathError(f"路径不是目录: {path}", path=str(resolved))
        if not is_dir and resolved.is_dir():
            raise FilePathError(f"路径是目录而非文件: {path}", path=str(resolved))

    return resolved


__all__ = [
    "validate_file_path",
    "FilePathError",
    "get_allowed_roots",
    "save_extra_allowed_dirs",
    "KEY_FILE_ALLOWED_DIRS",
]
