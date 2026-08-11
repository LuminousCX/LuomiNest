"""LLM 指令拦截守卫 — 检测并标注 LLM 输出中的可执行命令。

扫描 LLM 响应中的代码块（```bash、```shell、```cmd 等），
提取 shell 命令并使用现有的 command_policy 白名单/黑名单机制进行校验。

用途：
1. 非流式响应：在返回前扫描并标注被拦截的命令
2. 流式响应：累积完整文本后扫描（在 stream_chat 的完成阶段）
3. 前端收到标注后可展示警告提示

设计原则：
- 不修改 LLM 原始输出内容（仅在末尾附加安全提示）
- 白名单内的命令不标注（减少噪音）
- 黑名单/危险模式的命令明确标注并引导用户到设置页
"""
from __future__ import annotations

import re
from loguru import logger

# 匹配 Markdown 代码块中的 shell 命令
_CODE_BLOCK_RE = re.compile(
    r"```(?:bash|sh|shell|cmd|powershell|zsh|terminal)?\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)

# 匹配行内代码中看起来像命令的文本（以 $ 或 > 开头）
_INLINE_CMD_RE = re.compile(r"^[>$]\s+(.+)$", re.MULTILINE)

# 注释行和空行跳过
_COMMENT_RE = re.compile(r"^\s*(#|//|REM|::)")


def _extract_shell_commands(text: str) -> list[str]:
    """从 LLM 文本输出中提取 shell 命令。

    扫描 Markdown 代码块和行内命令提示符（$ / >）前缀的行。

    Returns:
        去重后的命令列表。
    """
    commands: list[str] = []
    seen: set[str] = set()

    # 1. 代码块中的命令
    for match in _CODE_BLOCK_RE.finditer(text):
        block = match.group(1)
        for line in block.strip().splitlines():
            line = line.strip()
            if not line or _COMMENT_RE.match(line):
                continue
            # 移除常见的提示符前缀
            for prefix in ("$ ", "> ", ">> ", "# ", "PS> ", "PS > "):
                if line.startswith(prefix):
                    line = line[len(prefix):].strip()
                    break
            if line and line not in seen:
                seen.add(line)
                commands.append(line)

    # 2. 行内命令提示符
    for match in _INLINE_CMD_RE.finditer(text):
        cmd = match.group(1).strip()
        if cmd and cmd not in seen and not _COMMENT_RE.match(cmd):
            seen.add(cmd)
            commands.append(cmd)

    return commands


def _check_command_safety(cmd: str) -> tuple[bool, str]:
    """使用 command_policy 白名单/黑名单校验命令（含复合命令拆分）。

    对 ``a && b``、``a || b``、``a; b`` 等复合命令逐段校验，
    任一段不安全即整体拒绝。同时检测 Shell 元字符（管道/重定向等）。

    Returns:
        (is_safe, reason) — is_safe=True 表示命令在白名单内。
    """
    from app.security.command_policy import (
        get_effective_whitelist,
        get_effective_blacklist,
        format_interception_message,
    )
    from app.security.sandbox.command_validator import (
        _split_compound_command,
        _SHELL_METACHARACTERS,
        _WINDOWS_SEPARATORS,
    )

    import os

    if not cmd or not cmd.strip():
        return True, ""

    # 1. Shell 元字符检测（管道/重定向/命令注入等）
    found_meta: list[str] = []
    for ch in _SHELL_METACHARACTERS:
        if ch in cmd:
            found_meta.append(ch)
    if os.name == "nt":
        for sep in _WINDOWS_SEPARATORS:
            if sep in cmd:
                found_meta.append(sep)
    if found_meta:
        chars = " ".join(sorted(set(found_meta)))
        return False, (
            f"命令包含 Shell 元字符（{chars}），安全策略不允许管道和重定向。"
            f"可在 设置 → 隐私安全 → 命令安全 中调整。"
        )

    # 2. 复合命令拆分逐段校验（处理 &&、||、;）
    sub_commands = _split_compound_command(cmd)

    whitelist = get_effective_whitelist()
    blacklist = get_effective_blacklist()

    for sub_cmd in sub_commands:
        parts = sub_cmd.split()
        if not parts:
            continue

        main_cmd = os.path.basename(parts[0]).lower()
        if main_cmd.endswith(".exe"):
            main_cmd = main_cmd[:-4]

        # 黑名单优先
        if main_cmd in blacklist:
            return False, format_interception_message("command_blacklist", sub_cmd)

        # 白名单检查
        if main_cmd not in whitelist:
            return False, format_interception_message("command_whitelist", sub_cmd)

    return True, ""


def scan_and_annotate(text: str) -> str:
    """扫描 LLM 输出文本，对不安全命令附加安全提示。

    仅对不在白名单内或命中黑名单的命令进行标注。
    白名单内的安全命令不产生任何标注。

    Args:
        text: LLM 的原始文本输出。

    Returns:
        标注后的文本（如无不安全命令则原样返回）。
    """
    if not text:
        return text

    commands = _extract_shell_commands(text)
    if not commands:
        return text

    blocked: list[tuple[str, str]] = []  # (command, reason)
    for cmd in commands:
        is_safe, reason = _check_command_safety(cmd)
        if not is_safe:
            blocked.append((cmd, reason))

    if not blocked:
        return text

    # 在文本末尾附加安全提示
    warning_lines = ["\n---\n⚠️ **安全提示：以下命令被安全策略拦截**\n"]
    for cmd, reason in blocked[:5]:  # 最多显示 5 条
        warning_lines.append(f"- `{cmd[:80]}`: {reason}")
    if len(blocked) > 5:
        warning_lines.append(f"- ...（还有 {len(blocked) - 5} 条被拦截）")
    warning_lines.append("\n可前往 **设置 → 隐私安全 → 命令安全** 调整白名单/黑名单。")

    return text + "\n".join(warning_lines)


def validate_tool_command(tool_name: str, arguments: dict) -> str | None:
    """校验工具调用中的命令参数（CLI 工具的前置检查）。

    这是对 CliTool 内部 CommandValidator 的补充层，
    在工具执行前做快速白名单/黑名单检查。

    Args:
        tool_name: 工具名称。
        arguments: 工具参数。

    Returns:
        None 表示通过，字符串表示拦截原因。
    """
    if tool_name not in ("cli", "execute_command"):
        return None

    cmd = arguments.get("command", "").strip()
    if not cmd:
        return None

    is_safe, reason = _check_command_safety(cmd)
    if not is_safe:
        logger.warning(f"[CommandGuard] 工具命令被拦截: tool={tool_name}, cmd={cmd[:80]}")
        return reason

    return None


__all__ = [
    "scan_and_annotate",
    "validate_tool_command",
    "_extract_shell_commands",
]
