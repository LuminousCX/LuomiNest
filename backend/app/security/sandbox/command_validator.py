"""命令安全验证器 — 路径白名单、危险命令检测、Shell 元字符拦截。

核心安全组件，在命令执行前进行多层校验，阻止危险操作进入沙盒。
"""

import os
import re
import shlex
from pathlib import Path

from app.security.sandbox.exceptions import SandboxPermissionError


# ---------------------------------------------------------------------------
# 危险命令模式（跨平台）
# ---------------------------------------------------------------------------

# POSIX 危险命令
_DANGEROUS_PATTERNS_POSIX: list[re.Pattern[str]] = [
    re.compile(r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*|(-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*))\s+(/|~|\*)", re.IGNORECASE),
    re.compile(r"\bformat\b", re.IGNORECASE),
    re.compile(r"\b(fdisk|mkfs)\b", re.IGNORECASE),
    re.compile(r"\b(shutdown|reboot|halt|poweroff)\b", re.IGNORECASE),
    re.compile(r"\bchmod\s+777\b", re.IGNORECASE),
    re.compile(r"\bcurl\b.*\|\s*(ba)?sh\b", re.IGNORECASE),
    re.compile(r"\bwget\b.*\|\s*(ba)?sh\b", re.IGNORECASE),
    re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", re.IGNORECASE),  # fork bomb
    re.compile(r">\s*/dev/sd[a-z]", re.IGNORECASE),
    re.compile(r">\s*/dev/hd[a-z]", re.IGNORECASE),
    re.compile(r"\bdd\s+if=", re.IGNORECASE),
]

# Windows 危险命令
_DANGEROUS_PATTERNS_WINDOWS: list[re.Pattern[str]] = [
    re.compile(r"\bdel\s+(/f\s+)?(/s\s+)?(/q\s+)?[A-Za-z]:\\", re.IGNORECASE),
    re.compile(r"\brd\s+/s\s+/q\b", re.IGNORECASE),
    re.compile(r"\bformat\b", re.IGNORECASE),
    re.compile(r"\bshutdown\b", re.IGNORECASE),
    re.compile(r"\breboot\b", re.IGNORECASE),
]

# 默认黑名单命令（basename 匹配）
_DEFAULT_BLACKLIST_CMDS: set[str] = {
    "format", "shutdown", "reboot", "halt", "poweroff", "mkfs", "fdisk",
}

# Shell 元字符
_SHELL_METACHARACTERS: set[str] = {"|", ">", "<", "`", ";"}

# Windows 命令分隔符
_WINDOWS_SEPARATORS: set[str] = {"&", "&&"}


class CommandValidator:
    """命令安全验证器。

    对即将在沙盒内执行的命令进行多层安全检查：
      1. 路径遍历检测（.. 段）
      2. 路径白名单（绝对路径必须在允许范围内）
      3. 危险命令正则匹配
      4. Shell 元字符拦截（可配置允许）
      5. 命令黑名单/白名单

    Args:
        workspace: 沙盒工作目录（路径白名单的默认根）。
        allowed_dirs: 额外的允许目录列表（与 workspace 并列）。
        allow_shell_meta: 是否允许 Shell 元字符（管道、重定向等），默认 False。
        whitelist_mode: 是否启用命令白名单模式（默认 False，使用黑名单模式）。
        allowed_commands: 白名单模式下的允许命令集合。
    """

    def __init__(
        self,
        workspace: Path,
        allowed_dirs: list[Path] | None = None,
        *,
        allow_shell_meta: bool = False,
        whitelist_mode: bool = False,
        allowed_commands: set[str] | None = None,
    ) -> None:
        self.workspace = workspace.resolve()
        self.allowed_dirs: list[Path] = [d.resolve() for d in (allowed_dirs or [])]
        self.allow_shell_meta = allow_shell_meta
        self.whitelist_mode = whitelist_mode
        self.allowed_commands: set[str] = allowed_commands or set()

        # 所有允许的路径（workspace + allowed_dirs）
        self._allowed_roots: list[Path] = [self.workspace] + self.allowed_dirs

        # 根据操作系统选择危险模式
        self._dangerous_patterns: list[re.Pattern[str]] = list(_DANGEROUS_PATTERNS_POSIX)
        if os.name == "nt":
            self._dangerous_patterns.extend(_DANGEROUS_PATTERNS_WINDOWS)

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def validate_command(self, cmd: str) -> None:
        """验证命令是否安全，不安全则抛出 SandboxPermissionError。

        Args:
            cmd: 待验证的命令字符串。

        Raises:
            SandboxPermissionError: 命令被安全策略拒绝。
        """
        if not cmd or not cmd.strip():
            raise SandboxPermissionError("命令不能为空", operation="validate_command")

        cmd_stripped = cmd.strip()

        # 1. Shell 元字符检测
        if not self.allow_shell_meta:
            self._check_shell_metacharacters(cmd_stripped)

        # 2. 危险命令正则检测
        self._check_dangerous_patterns(cmd_stripped)

        # 3. 解析命令并检查命令黑白名单
        parts = self._parse_command(cmd_stripped)
        if not parts:
            raise SandboxPermissionError("命令解析结果为空", operation="validate_command")

        self._check_command_allowlist(parts)

        # 4. 路径遍历检测（扫描所有参数）
        self._check_path_traversal(parts)

        # 5. 绝对路径白名单检测
        self._check_absolute_paths(parts)

    def validate_path(self, path: str) -> Path:
        """验证路径是否在允许范围内，返回解析后的绝对路径。

        支持虚拟路径前缀 /mnt/workspace/ 和 /mnt/skills/。

        Args:
            path: 待验证的路径字符串。

        Returns:
            解析后的绝对 Path 对象。

        Raises:
            SandboxPermissionError: 路径越界或包含遍历。
        """
        resolved = self._resolve_path(path)
        self._ensure_within_roots(resolved)
        return resolved

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _resolve_path(self, path: str) -> Path:
        """将路径字符串解析为绝对 Path，处理虚拟路径前缀。"""
        # 处理虚拟路径前缀
        normalized = path.replace("\\", "/")
        if normalized.startswith("/mnt/workspace/"):
            relative = normalized[len("/mnt/workspace/"):]
            resolved = (self.workspace / relative).resolve()
        elif normalized == "/mnt/workspace":
            resolved = self.workspace
        elif normalized.startswith("/mnt/skills/"):
            # 技能目录：workspace 下的 skills 子目录（如果存在）
            skills_dir = self.workspace.parent / "skills"
            relative = normalized[len("/mnt/skills/"):]
            resolved = (skills_dir / relative).resolve()
        elif normalized == "/mnt/skills":
            resolved = (self.workspace.parent / "skills").resolve()
        else:
            raw = Path(path)
            resolved = raw.resolve() if raw.is_absolute() else (self.workspace / raw).resolve()

        return resolved

    def _ensure_within_roots(self, resolved: Path) -> None:
        """确保 resolved 路径在至少一个允许根目录之下。"""
        for root in self._allowed_roots:
            try:
                resolved.relative_to(root)
                return  # 在某个根之下，合法
            except ValueError:
                continue

        # 也允许 skills 目录（如果存在）
        skills_dir = self.workspace.parent / "skills"
        if skills_dir.exists():
            try:
                resolved.relative_to(skills_dir)
                return
            except ValueError:
                pass

        allowed = ", ".join(str(r) for r in self._allowed_roots)
        raise SandboxPermissionError(
            f"路径越界: {resolved} 不在允许范围内 ({allowed})",
            path=str(resolved),
            operation="path_validation",
        )

    def _check_shell_metacharacters(self, cmd: str) -> None:
        """检测 Shell 元字符。"""
        found: list[str] = []
        for ch in _SHELL_METACHARACTERS:
            if ch in cmd:
                found.append(ch)
        # Windows 命令分隔符
        if os.name == "nt":
            for sep in _WINDOWS_SEPARATORS:
                if sep in cmd:
                    found.append(sep)
        if found:
            chars = " ".join(sorted(set(found)))
            raise SandboxPermissionError(
                f"命令包含 Shell 元字符（{chars}），沙盒默认不允许管道和重定向",
                operation="shell_metacharacter",
            )

    def _check_dangerous_patterns(self, cmd: str) -> None:
        """检测危险命令正则模式。"""
        for pattern in self._dangerous_patterns:
            if pattern.search(cmd):
                raise SandboxPermissionError(
                    f"命令匹配危险模式: {pattern.pattern}",
                    operation="dangerous_command",
                )

    def _parse_command(self, cmd: str) -> list[str]:
        """解析命令字符串为参数列表。"""
        try:
            posix_mode = os.name != "nt"
            parts = shlex.split(cmd, posix=posix_mode)
        except ValueError:
            # 解析失败时回退到简单 split
            parts = cmd.split()
        return parts

    def _check_command_allowlist(self, parts: list[str]) -> None:
        """检查命令黑白名单。"""
        # 提取主命令 basename（处理路径和 .exe 后缀）
        main_cmd = os.path.basename(parts[0]).lower()
        if main_cmd.endswith(".exe"):
            main_cmd = main_cmd[:-4]

        if self.whitelist_mode:
            if main_cmd not in self.allowed_commands:
                allowed = ", ".join(sorted(self.allowed_commands)) if self.allowed_commands else "(无)"
                raise SandboxPermissionError(
                    f"命令 '{main_cmd}' 不在白名单中。允许的命令: {allowed}",
                    operation="command_whitelist",
                )
        else:
            # 黑名单模式
            if main_cmd in _DEFAULT_BLACKLIST_CMDS:
                raise SandboxPermissionError(
                    f"命令 '{main_cmd}' 在黑名单中，禁止执行",
                    operation="command_blacklist",
                )
            # 特殊检测：rm 带 -rf 参数
            if main_cmd == "rm" and len(parts) > 1:
                flags = " ".join(p for p in parts[1:] if p.startswith("-"))
                if "r" in flags and "f" in flags:
                    raise SandboxPermissionError(
                        "禁止执行 rm -rf（递归强制删除）",
                        operation="command_blacklist",
                    )
            # Windows: del /f /s /q
            if main_cmd == "del" and len(parts) > 1:
                flags = " ".join(parts[1:]).lower()
                if "/f" in flags and "/s" in flags and "/q" in flags:
                    raise SandboxPermissionError(
                        "禁止执行 del /f /s /q（强制递归删除）",
                        operation="command_blacklist",
                    )

    def _check_path_traversal(self, parts: list[str]) -> None:
        """扫描参数中的路径遍历（.. 段）。"""
        for part in parts[1:]:  # 跳过主命令本身
            normalized = part.replace("\\", "/")
            segments = normalized.split("/")
            if ".." in segments:
                raise SandboxPermissionError(
                    f"检测到路径遍历: {part}",
                    path=part,
                    operation="path_traversal",
                )

    def _check_absolute_paths(self, parts: list[str]) -> None:
        """检查参数中的绝对路径是否在白名单范围内。"""
        for part in parts[1:]:
            p = Path(part)
            if p.is_absolute():
                resolved = p.resolve()
                self._ensure_within_roots(resolved)
