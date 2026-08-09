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
    # 覆盖系统关键文件的写入（防御性命令增强）
    re.compile(r">\s*/etc/(shadow|passwd|sudoers|hosts|crond|crontab)\b", re.IGNORECASE),
    re.compile(r">\s*/root/\S*\.(bashrc|zshrc|profile)\b", re.IGNORECASE),
    # 读取凭据文件
    re.compile(r"\b(cat|tac|less|more|head|tail|vim|vi|nano|sed|awk|grep|cp|scp)\s+.*(/etc/(shadow|passwd)|(id_rsa|id_ecdsa|id_ed25519|authorized_keys|\.netrc|\.ssh/))", re.IGNORECASE),
    # base64 解码后执行（常见混淆载荷通道）
    re.compile(r"base64\s+-d.*\|\s*(ba)?sh\b", re.IGNORECASE),
    # 命令替换执行下载器
    re.compile(r"\$\(\s*(curl|wget)\b", re.IGNORECASE),
    re.compile(r"`\s*(curl|wget)\b", re.IGNORECASE),
    # 动态链接劫持
    re.compile(r"(LD_PRELOAD|LD_LIBRARY_PATH)\s*=", re.IGNORECASE),
    # /dev/tcp 内建网络
    re.compile(r"/dev/tcp/", re.IGNORECASE),
    # 内核模块
    re.compile(r"\b(insmod|rmmod|modprobe)\b", re.IGNORECASE),
    # 权限提升
    re.compile(r"\b(sudo|pkexec|setuid)\b", re.IGNORECASE),
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
    # 系统/内核操作
    "init", "systemctl", "kexec", "grub-install",
    # 权限提升与逃逸（参考 odysseus 工具门禁思路）
    "sudo", "su", "pkexec",
    # 进程强杀
    "killall", "pkill",
    # 网络后门
    "nc", "ncat", "socat", "telnet",
}

# 敏感路径段黑名单：即使位于允许根目录内，命中这些路径段的访问也被拒绝。
# 参考 odysseus tool_execution 的敏感路径防护（.ssh/.gnupg/.gitconfig/.env/.netrc 等）。
_SENSITIVE_PATH_SEGMENTS: frozenset[str] = frozenset({
    # 凭据与密钥
    ".ssh", ".gnupg", ".gnu_pg", ".netrc", ".pgpass", ".npmrc", ".pypirc",
    "authorized_keys", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
    "known_hosts", "secring", "secretring", ".secret", ".credentials",
    # 环境与配置
    ".env", ".gitconfig", ".git-credentials", ".git-credential",
    ".bashrc", ".zshrc", ".profile", ".bash_profile", ".bash_history",
    ".zsh_history", "shadow", "passwd", "sudoers", "history",
    # Windows 凭据
    "SAM", "SYSTEM", "SECURITY", "NTUSER.DAT", "ntuser.dat",
    # 云凭证
    "credentials.json", ".aws", "aws_credentials",
})

# Shell 元字符
_SHELL_METACHARACTERS: set[str] = {"|", ">", "<", "`", ";"}

# Windows 命令分隔符
_WINDOWS_SEPARATORS: set[str] = {"&", "&&"}

# 复合命令分隔符（用于 allow_shell_meta 模式下拆分子命令逐段审计）
_COMPOUND_SEPARATORS: tuple[str, ...] = ("&&", "||", ";")


def _split_compound_command(cmd: str) -> list[str]:
    """按复合分隔符拆分命令（引号感知），返回子命令列表。

    仅对 ``allow_shell_meta=True`` 的场景有意义：即使允许管道/重定向，
    也要把 ``a && b`` / ``a; b`` 拆开逐段做危险模式审计。

    Args:
        cmd: 原始命令字符串。

    Returns:
        子命令列表（未闭合引号时整条返回，fail-closed）。
    """
    parts: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escaped = False
    i = 0
    while i < len(cmd):
        ch = cmd[i]
        if escaped:
            current.append(ch)
            escaped = False
            i += 1
            continue
        if ch == "\\" and quote != "'":
            escaped = True
            current.append(ch)
            i += 1
            continue
        if ch in ("'", '"'):
            if quote is None:
                quote = ch
            elif quote == ch:
                quote = None
            current.append(ch)
            i += 1
            continue
        if quote is None:
            matched = None
            for sep in _COMPOUND_SEPARATORS:
                if cmd.startswith(sep, i):
                    matched = sep
                    break
            if matched:
                part = "".join(current).strip()
                if part:
                    parts.append(part)
                current = []
                i += len(matched)
                continue
        current.append(ch)
        i += 1

    if quote is not None or escaped:
        # 未闭合引号/悬挂反斜杠：无法安全拆分，整条返回（fail-closed）
        return [cmd.strip()]

    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


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

        # 1. Shell 元字符检测（默认禁止管道/重定向/命令替换）
        if not self.allow_shell_meta:
            self._check_shell_metacharacters(cmd_stripped)

        # 2. 危险命令正则检测：整条命令先扫一遍，
        #    若允许 shell 元字符，再按复合分隔符拆分逐段审计（最严重者胜出）
        self._check_dangerous_patterns(cmd_stripped)
        if self.allow_shell_meta:
            for sub_cmd in _split_compound_command(cmd_stripped):
                if sub_cmd:
                    self._check_dangerous_patterns(sub_cmd)

        # 3. 解析命令并检查命令黑白名单
        parts = self._parse_command(cmd_stripped)
        if not parts:
            raise SandboxPermissionError("命令解析结果为空", operation="validate_command")

        self._check_command_allowlist(parts)

        # 4. 路径遍历检测（扫描所有参数）
        self._check_path_traversal(parts)

        # 5. 绝对路径白名单 + 敏感段检测（含虚拟路径 /mnt/workspace/...）
        self._check_absolute_paths(parts)
        self._check_virtual_paths(parts)

    def validate_path(self, path: str) -> Path:
        """验证路径是否在允许范围内，返回解析后的绝对路径。

        支持虚拟路径前缀 /mnt/workspace/ 和 /mnt/skills/。
        同时执行敏感路径段黑名单检查（.ssh/.env/id_rsa 等即使在工作区内也拒绝）。

        Args:
            path: 待验证的路径字符串。

        Returns:
            解析后的绝对 Path 对象。

        Raises:
            SandboxPermissionError: 路径越界、包含遍历或命中敏感路径段。
        """
        resolved = self._resolve_path(path)
        self._ensure_within_roots(resolved)
        self._check_sensitive_path_segments(resolved)
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

    def _check_sensitive_path_segments(self, resolved: Path) -> None:
        """检查路径中的敏感路径段黑名单。

        即使路径位于允许根目录内（如 workspace 中恰好存在 .env / .ssh 目录），
        命中敏感段的访问一律拒绝，防止 LLM 生成的命令读取宿主机凭据或窃取工作区密钥。

        Args:
            resolved: 已解析的绝对路径。

        Raises:
            SandboxPermissionError: 命中敏感路径段。
        """
        normalized = str(resolved).replace("\\", "/")
        segments = [s for s in normalized.split("/") if s]
        for segment in segments:
            if segment.lower() in _SENSITIVE_PATH_SEGMENTS:
                raise SandboxPermissionError(
                    f"路径命中敏感段黑名单: {segment}",
                    path=str(resolved),
                    operation="sensitive_path",
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
        """检查参数中的绝对路径是否在白名单范围内且未命中敏感段。"""
        for part in parts[1:]:
            p = Path(part)
            if p.is_absolute():
                resolved = p.resolve()
                self._ensure_within_roots(resolved)
                self._check_sensitive_path_segments(resolved)

    def _check_virtual_paths(self, parts: list[str]) -> None:
        """检查参数中的虚拟路径（/mnt/workspace/...、/mnt/skills/...）敏感段。

        Windows 下 ``/mnt/workspace/.env`` 不是绝对路径（无盘符），
        无法被 _check_absolute_paths 覆盖，需单独对虚拟路径段做敏感检查，
        防止 ``cat /mnt/workspace/.env`` 式命令读取工作区内密钥文件。
        """
        for part in parts[1:]:
            normalized = part.replace("\\", "/")
            if not (normalized.startswith("/mnt/workspace/") or normalized.startswith("/mnt/skills/")):
                continue
            # 取虚拟路径后的相对段做敏感段检测（与 _check_sensitive_path_segments 同规则）
            for segment in normalized.split("/"):
                if segment and segment.lower() in _SENSITIVE_PATH_SEGMENTS:
                    raise SandboxPermissionError(
                        f"路径命中敏感段黑名单: {segment}",
                        path=part,
                        operation="sensitive_path",
                    )
