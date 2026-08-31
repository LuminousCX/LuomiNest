"""沙箱环境变量安全策略 — 白名单模式持久化与加载。

子进程环境变量白名单化，防止 API Key / Secret / Token 等敏感变量泄露到沙箱。
默认仅传入系统运行必需的安全变量（PATH、HOME、TEMP 等），用户可在
设置 → 隐私安全 → 沙箱环境变量 中配置额外需要传入的变量名。

策略持久化：写入 config_items 表，键名 ``sandbox_env.*``。
"""

from __future__ import annotations

import os
import sys

from loguru import logger

# config_items 存储键名
KEY_ENV_EXTRA_WHITELIST = "sandbox_env.extra_whitelist"

# ---------------------------------------------------------------------------
# 默认安全环境变量白名单
# ---------------------------------------------------------------------------
# 这些变量对子进程正常运行是必需的，且不包含任何敏感信息。
# 分为跨平台通用和 Windows 专用两部分。

_SAFE_ENV_VARS_COMMON: frozenset[str] = frozenset({
    # 基础系统
    "PATH", "HOME", "LANG", "LANGUAGE", "LC_ALL", "LC_CTYPE", "LC_MESSAGES",
    "TERM", "SHELL", "USER", "LOGNAME",
    # Python 运行时（某些工具链需要）
    "PYTHONIOENCODING",
})

_SAFE_ENV_VARS_WINDOWS: frozenset[str] = frozenset({
    # Windows 基础
    "TEMP", "TMP", "SYSTEMROOT", "WINDIR", "SYSTEMDRIVE",
    "USERNAME", "USERPROFILE", "COMPUTERNAME", "OS",
    "PROCESSOR_ARCHITECTURE", "PROCESSOR_IDENTIFIER", "NUMBER_OF_PROCESSORS",
    "COMSPEC", "PATHEXT",
    "APPDATA", "LOCALAPPDATA",
    "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432",
    "COMMONPROGRAMFILES", "COMMONPROGRAMFILES(X86)", "COMMONPROGRAMW6432",
    "PUBLIC", "PROGRAMDATA",
    "ALLUSERSPROFILE", "HOMEDRIVE", "HOMEPATH",
    # Windows 编码
    "PYTHONUTF8",
})


def _get_default_whitelist() -> set[str]:
    """获取当前平台的默认安全环境变量白名单。"""
    result = set(_SAFE_ENV_VARS_COMMON)
    if sys.platform == "win32" or os.name == "nt":
        result |= set(_SAFE_ENV_VARS_WINDOWS)
    return result


def _normalize_var_names(values: list | None) -> list[str]:
    """清洗环境变量名列表：去空、去首尾空白、大写去重。"""
    if not values:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for item in values:
        if not isinstance(item, str):
            continue
        name = item.strip().upper()
        if not name or name in seen:
            continue
        seen.add(name)
        result.append(name)
    return result


def load_env_whitelist() -> set[str]:
    """加载生效的环境变量白名单 = 默认白名单 ∪ 用户额外白名单。

    Returns:
        大写环境变量名集合。
    """
    default = _get_default_whitelist()

    try:
        from app.infrastructure.database.config_store import luominest_config_store
        extra = luominest_config_store.get(KEY_ENV_EXTRA_WHITELIST, []) or []
    except Exception as e:
        logger.warning(f"[EnvPolicy] 加载额外白名单失败，使用默认白名单: {e}")
        extra = []

    cleaned = _normalize_var_names(extra)
    return default | set(cleaned)


def save_env_extra_whitelist(extra_whitelist: list | None) -> list[str]:
    """保存用户额外环境变量白名单。

    Args:
        extra_whitelist: 用户额外放行的环境变量名列表。

    Returns:
        保存后的规范化列表。
    """
    cleaned = _normalize_var_names(extra_whitelist)

    try:
        from app.infrastructure.database.config_store import luominest_config_store
        luominest_config_store.set(KEY_ENV_EXTRA_WHITELIST, cleaned)
        logger.info(f"[EnvPolicy] 额外环境变量白名单已保存: {cleaned}")
    except Exception as e:
        logger.warning(f"[EnvPolicy] 保存额外白名单失败: {e}")

    return cleaned


def build_safe_env(workspace: str) -> dict[str, str]:
    """构建沙箱子进程的安全环境变量字典。

    只传入白名单内的环境变量，加上 SANDBOX_WORKSPACE。
    敏感变量（KEY、SECRET、TOKEN、PASSWORD 等）自动被排除。

    Args:
        workspace: 沙箱工作目录路径。

    Returns:
        安全的环境变量字典。
    """
    whitelist = load_env_whitelist()
    safe_env: dict[str, str] = {}

    for var_name in whitelist:
        # 从 os.environ 中取值（环境变量名在 Windows 上不区分大小写，
        # 但 os.environ 已经做了 case-insensitive 映射）
        value = os.environ.get(var_name)
        if value is not None:
            safe_env[var_name] = value

    # 始终注入 SANDBOX_WORKSPACE
    safe_env["SANDBOX_WORKSPACE"] = workspace

    return safe_env


# 敏感变量名的关键词模式 — 用于防御性二次校验
_SENSITIVE_PATTERNS = ("KEY", "SECRET", "TOKEN", "PASSWORD", "PASSWD",
                       "CREDENTIAL", "AUTH", "PRIVATE")


def contains_sensitive_var(name: str) -> bool:
    """检查环境变量名是否包含敏感关键词（防御性校验）。"""
    upper = name.upper()
    return any(pat in upper for pat in _SENSITIVE_PATTERNS)


__all__ = [
    "build_safe_env",
    "load_env_whitelist",
    "save_env_extra_whitelist",
    "contains_sensitive_var",
    "KEY_ENV_EXTRA_WHITELIST",
]
