"""本地沙盒实现 — 基于 asyncio.create_subprocess_exec 的安全命令执行环境。"""

import asyncio
import logging
import os
import re
from pathlib import Path

from app.security.sandbox.command_validator import CommandValidator
from app.security.sandbox.exceptions import (
    SandboxCommandError,
    SandboxPermissionError,
    SandboxTimeoutError,
)
from app.security.sandbox.sandbox import CommandResult, Sandbox

logger = logging.getLogger(__name__)

# 输出捕获上限（10 MB）
_OUTPUT_CAPTURE_LIMIT = 10 * 1024 * 1024
# 写入文件大小上限（80 KB）
_WRITE_FILE_MAX_BYTES = 80 * 1024
# 虚拟路径前缀
_VIRTUAL_PATH_PREFIX = "/mnt/workspace"
_VIRTUAL_SKILLS_PREFIX = "/mnt/skills"


def mask_local_paths_in_output(output: str, workspace: Path) -> str:
    """将输出中的实际路径替换为虚拟路径，避免泄露主机目录结构。

    替换规则：
      - workspace 绝对路径 → /mnt/workspace/
      - skills 目录（workspace 同级的 skills/）→ /mnt/skills/

    Args:
        output: 原始输出字符串。
        workspace: 沙盒工作目录。

    Returns:
        路径已遮蔽的输出字符串。
    """
    result = output
    workspace_resolved = str(workspace.resolve())
    workspace_str = str(workspace)

    # 替换 workspace 路径（先处理 resolved 版本，再处理原始版本）
    for ws_path in (workspace_resolved, workspace_str):
        if not ws_path:
            continue
        # 使用正则确保匹配路径段边界
        pattern = re.compile(re.escape(ws_path) + r"(?=[/\\]|$)")
        result = pattern.sub(_VIRTUAL_PATH_PREFIX, result)

    # 替换 skills 目录
    skills_dir = workspace.parent / "skills"
    if skills_dir.exists():
        skills_resolved = str(skills_dir.resolve())
        skills_str = str(skills_dir)
        for sk_path in (skills_resolved, skills_str):
            if not sk_path:
                continue
            pattern = re.compile(re.escape(sk_path) + r"(?=[/\\]|$)")
            result = pattern.sub(_VIRTUAL_SKILLS_PREFIX, result)

    return result


class LocalSandbox(Sandbox):
    """本地文件系统沙盒。

    在主机进程内以子进程方式执行命令，通过 CommandValidator 实施安全策略，
    通过路径遮蔽隐藏真实目录结构。

    Args:
        workspace: 沙盒工作目录（绝对路径）。
        session_id: 会话标识符。
    """

    def __init__(self, workspace: Path, session_id: str) -> None:
        super().__init__(id=f"local:{session_id}")
        self.workspace: Path = workspace.resolve()
        self.session_id: str = session_id
        self.validator: CommandValidator = CommandValidator(workspace=self.workspace)
        self._file_lock: asyncio.Lock = asyncio.Lock()

        # 确保工作目录存在
        self.workspace.mkdir(parents=True, exist_ok=True)

    async def execute_command(self, cmd: str | list[str], timeout: int = 120) -> CommandResult:
        """在沙盒内执行命令。

        流程：
          1. 验证命令安全性（CommandValidator）
          2. 解析为参数列表（如果不已经是 list）
          3. 使用 asyncio.create_subprocess_exec 执行（不经过 shell）
          4. 超时控制（asyncio.wait_for）
          5. 输出捕获上限 10 MB
          6. 路径遮蔽

        Args:
            cmd: 命令字符串或参数列表。
            timeout: 超时秒数，默认 120。

        Returns:
            CommandResult。

        Raises:
            SandboxPermissionError: 命令被安全策略拒绝。
            SandboxTimeoutError: 命令超时。
            SandboxCommandError: 命令执行失败。
        """
        # 1. 验证命令
        if isinstance(cmd, list):
            cmd_str = " ".join(cmd)
            cmd_parts = cmd
        else:
            cmd_str = cmd
            self.validator.validate_command(cmd_str)
            cmd_parts = self._parse_cmd(cmd_str)

        if not cmd_parts:
            raise SandboxCommandError("命令解析结果为空", command=cmd_str, exit_code=-1)

        # 2. 执行命令
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace),
                env=self._build_env(),
            )
        except FileNotFoundError as e:
            raise SandboxCommandError(
                f"命令不存在: {cmd_parts[0]}",
                command=cmd_str,
                exit_code=-1,
            ) from e
        except PermissionError as e:
            raise SandboxPermissionError(
                f"无权限执行: {cmd_parts[0]}",
                operation="execute_command",
            ) from e
        except OSError as e:
            raise SandboxCommandError(
                f"执行命令失败: {e}",
                command=cmd_str,
                exit_code=-1,
            ) from e

        # 3. 等待完成（带超时）
        timed_out = False
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            timed_out = True
            # 终止进程
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()
            stdout_bytes = b""
            stderr_bytes = b""

        # 4. 解码输出（限制大小）
        stdout = self._decode_and_truncate(stdout_bytes)
        stderr = self._decode_and_truncate(stderr_bytes)
        exit_code = process.returncode if process.returncode is not None else -1

        # 5. 路径遮蔽
        stdout = mask_local_paths_in_output(stdout, self.workspace)
        stderr = mask_local_paths_in_output(stderr, self.workspace)

        result = CommandResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            timed_out=timed_out,
        )

        if timed_out:
            raise SandboxTimeoutError(
                f"命令执行超时（{timeout}秒）",
                timeout=timeout,
            )

        return result

    async def read_file(self, path: str) -> str:
        """读取沙盒内文件。

        Args:
            path: 文件路径（支持虚拟路径 /mnt/workspace/...）。

        Returns:
            文件文本内容（路径已遮蔽）。

        Raises:
            SandboxPermissionError: 路径越界。
            FileNotFoundError: 文件不存在。
        """
        resolved = self.validator.validate_path(path)

        if not resolved.exists():
            raise FileNotFoundError(f"文件不存在: {path}")
        if resolved.is_dir():
            raise IsADirectoryError(f"路径是目录而非文件: {path}")

        loop = asyncio.get_running_loop()
        content = await loop.run_in_executor(None, self._read_file_sync, resolved)

        # 路径遮蔽
        content = mask_local_paths_in_output(content, self.workspace)
        return content

    async def write_file(self, path: str, content: str) -> None:
        """向沙盒内文件写入内容（覆盖）。

        Args:
            path: 文件路径（支持虚拟路径）。
            content: 文本内容。

        Raises:
            SandboxPermissionError: 路径越界或文件过大。
        """
        resolved = self.validator.validate_path(path)

        # 文件大小限制
        content_bytes = len(content.encode("utf-8"))
        if content_bytes > _WRITE_FILE_MAX_BYTES:
            raise SandboxPermissionError(
                f"文件内容过大（{content_bytes} bytes），上限为 {_WRITE_FILE_MAX_BYTES} bytes",
                path=path,
                operation="write_file",
            )

        # 确保父目录存在
        resolved.parent.mkdir(parents=True, exist_ok=True)

        # 文件操作锁
        async with self._file_lock:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._write_file_sync, resolved, content)

    async def list_dir(self, path: str) -> list[dict]:
        """列举沙盒内目录内容。

        Args:
            path: 目录路径（支持虚拟路径）。

        Returns:
            条目列表，每个条目包含 name / type / size 字段。

        Raises:
            SandboxPermissionError: 路径越界。
            FileNotFoundError: 目录不存在。
        """
        resolved = self.validator.validate_path(path)

        if not resolved.exists():
            raise FileNotFoundError(f"目录不存在: {path}")
        if not resolved.is_dir():
            raise NotADirectoryError(f"路径不是目录: {path}")

        loop = asyncio.get_running_loop()
        entries = await loop.run_in_executor(None, self._list_dir_sync, resolved)

        # 路径遮蔽
        for entry in entries:
            entry["name"] = mask_local_paths_in_output(entry["name"], self.workspace)

        return entries

    # ------------------------------------------------------------------
    # 同步辅助方法（在线程池中执行以避免阻塞事件循环）
    # ------------------------------------------------------------------

    @staticmethod
    def _read_file_sync(path: Path) -> str:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    @staticmethod
    def _write_file_sync(path: Path, content: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    @staticmethod
    def _list_dir_sync(path: Path) -> list[dict]:
        entries: list[dict] = []
        try:
            for item in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                entry: dict = {
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                }
                try:
                    if item.is_file():
                        entry["size"] = item.stat().st_size
                except OSError:
                    entry["size"] = 0
                entries.append(entry)
        except PermissionError:
            pass  # 跳过无权限的条目
        return entries

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _parse_cmd(self, cmd: str) -> list[str]:
        """解析命令字符串为参数列表。"""
        import shlex
        try:
            posix_mode = os.name != "nt"
            parts = shlex.split(cmd, posix=posix_mode)
        except ValueError:
            parts = cmd.split()
        return parts

    def _build_env(self) -> dict[str, str]:
        """构建子进程环境变量。"""
        env = os.environ.copy()
        # 设置工作目录为环境变量，供子进程参考
        env["SANDBOX_WORKSPACE"] = str(self.workspace)
        return env

    @staticmethod
    def _decode_and_truncate(data: bytes, limit: int = _OUTPUT_CAPTURE_LIMIT) -> str:
        """解码字节数据并截断到上限。"""
        if not data:
            return ""
        text = data.decode("utf-8", errors="replace")
        if len(text) > limit:
            text = text[:limit] + f"\n... [output truncated after {limit} bytes] ..."
        return text
