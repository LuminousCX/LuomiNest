"""命令安全策略 — 用户自定义白名单/黑名单的持久化与统一入口。

控制台沙盒（用户手动执行、AI 工具 cli / console.execute）共用同一套
CommandValidator 白名单模式。本模块提供：
1. 默认白名单（与 console.py ALLOWED_COMMANDS 对齐的安全命令集）
2. 用户自定义白名单（额外放行的命令）
3. 用户自定义黑名单（即使在白名单内也强制拒绝，优先级最高）
4. 统一拦截错误格式化（含拦截原因 + 前往设置引导）

策略持久化：写入 config_items 表（通过 luominest_config_store），键名前缀
``command_policy.*``，支持运行时热更新，无需重启。
"""

from __future__ import annotations

from loguru import logger

# config_items 存储键名
KEY_EXTRA_WHITELIST = "command_policy.extra_whitelist"
KEY_BLACKLIST = "command_policy.blacklist"


# 默认白名单（允许执行的主命令）
# 安全原则：不包含可执行任意代码的解释器/下载器/容器引擎
# （python/node/curl/wget/docker/pip/redis-cli/sqlite3 已移除）
DEFAULT_ALLOWED_COMMANDS: frozenset[str] = frozenset({
    "git", "npm", "pnpm", "yarn",
    "ls", "dir", "cat", "type", "echo", "pwd", "cd", "mkdir", "md", "rmdir",
    "cp", "copy", "mv", "move", "touch", "find", "grep", "rg", "head", "tail",
    "wc", "ping", "nslookup", "ipconfig", "netstat",
    "tasklist", "systeminfo", "where", "which",
})

# 拦截原因枚举（对应 CommandValidator 的 operation 与前端展示）
INTERCEPTION_REASONS: dict[str, str] = {
    "command_whitelist": "命令不在白名单内",
    "command_blacklist": "命令命中黑名单",
    "dangerous_command": "命令匹配危险模式",
    "shell_metacharacter": "包含禁止的 Shell 元字符",
    "sensitive_path": "涉及敏感路径",
    "path_traversal": "检测到路径遍历",
    "path_validation": "路径越界",
    "validate_command": "命令格式不合法",
}


def _normalize_command_list(values: list | None) -> list[str]:
    """清洗命令列表：去空、去首尾空白、小写去重。"""
    if not values:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for item in values:
        if not isinstance(item, str):
            continue
        name = item.strip().lower()
        if not name or name in seen:
            continue
        seen.add(name)
        result.append(name)
    return result


def load_command_policy() -> dict:
    """加载用户命令安全策略。

    Returns:
        {"extra_whitelist": [...], "blacklist": [...]}，均为小写清洗后的列表。
    """
    try:
        from app.infrastructure.database.config_store import luominest_config_store

        extra = luominest_config_store.get(KEY_EXTRA_WHITELIST, []) or []
        blacklist = luominest_config_store.get(KEY_BLACKLIST, []) or []
    except Exception as e:
        logger.warning(f"[CommandPolicy] 加载策略失败，使用空策略: {e}")
        return {"extra_whitelist": [], "blacklist": []}

    return {
        "extra_whitelist": _normalize_command_list(extra),
        "blacklist": _normalize_command_list(blacklist),
    }


def save_command_policy(extra_whitelist: list | None, blacklist: list | None) -> dict:
    """保存用户命令安全策略并返回规范化结果。

    Args:
        extra_whitelist: 用户额外放行的命令列表。
        blacklist: 用户强制拒绝的命令列表。

    Returns:
        保存后的规范化策略。
    """
    cleaned_extra = _normalize_command_list(extra_whitelist)
    cleaned_blacklist = _normalize_command_list(blacklist)

    # 黑名单与默认白名单重叠时，以黑名单为准（黑名单优先级最高），
    # 防止用户误把安全命令加入黑名单后又困惑为何无法执行。
    try:
        from app.infrastructure.database.config_store import luominest_config_store

        luominest_config_store.set(KEY_EXTRA_WHITELIST, cleaned_extra)
        luominest_config_store.set(KEY_BLACKLIST, cleaned_blacklist)
        logger.info(
            f"[CommandPolicy] 策略已保存: extra_whitelist={cleaned_extra}, "
            f"blacklist={cleaned_blacklist}"
        )
    except Exception as e:
        logger.warning(f"[CommandPolicy] 保存策略失败: {e}")

    return {"extra_whitelist": cleaned_extra, "blacklist": cleaned_blacklist}


def get_effective_whitelist() -> set[str]:
    """获取生效的命令白名单 = 默认白名单 ∪ 用户额外白名单。"""
    policy = load_command_policy()
    return set(DEFAULT_ALLOWED_COMMANDS) | set(policy["extra_whitelist"])


def get_effective_blacklist() -> set[str]:
    """获取生效的命令黑名单 = 用户黑名单。"""
    return set(load_command_policy()["blacklist"])


def format_interception_message(
    operation: str,
    command: str = "",
    default_message: str = "",
) -> str:
    """格式化命令拦截错误消息（供沙盒异常与工具错误使用）。

    统一格式：``命令已被安全策略拦截（原因）。可在 设置 → 隐私安全 → 命令安全 中调整。``
    前端据此识别"已拦截"状态并展示引导按钮。

    Args:
        operation: CommandValidator 的 operation 标识。
        command: 被拦截的命令（可选，用于展示）。
        default_message: 原始错误消息（未映射到已知原因时使用）。

    Returns:
        格式化后的拦截提示。
    """
    reason = INTERCEPTION_REASONS.get(operation, operation or "未知安全规则")
    cmd_part = f"（命令: {command[:80]}）" if command else ""
    return (
        f"命令已被安全策略拦截：{reason}{cmd_part}。"
        f"可在 设置 → 隐私安全 → 命令安全 中调整白名单/黑名单。"
    ) if not default_message else (
        f"命令已被安全策略拦截：{default_message}。"
        f"可在 设置 → 隐私安全 → 命令安全 中调整白名单/黑名单。"
    )


def is_interception_message(text: str) -> bool:
    """判断错误文本是否为命令拦截消息（供前端识别）。"""
    return "命令已被安全策略拦截" in (text or "")


__all__ = [
    "DEFAULT_ALLOWED_COMMANDS",
    "load_command_policy",
    "save_command_policy",
    "get_effective_whitelist",
    "get_effective_blacklist",
    "format_interception_message",
    "is_interception_message",
    "INTERCEPTION_REASONS",
]
