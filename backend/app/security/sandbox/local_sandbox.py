"""本地沙盒实现 — 基于 asyncio.create_subprocess_exec 的安全命令执行环境。

安全特性（参考 deer-flow local_sandbox 的进程组隔离与管道排水设计）：
1. POSIX 下以独立进程组运行（start_new_session），超时后整组 SIGKILL，
   避免只杀主进程留下残留子进程（如 ``server &`` 后台任务）
2. 有界管道排水（Bounded Pipe Drain）：后台进程继承 stdout/stderr 时，
   不会导致 communicate() 永久阻塞，且输出读取有 10 MB 上限
3. 输出路径遮蔽 + 敏感段黑名单 + 命令审计记录
"""

import asyncio
import logging
import os
import re
import signal
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
# 进程退出后等待管道排水任务完成的上限（秒）
_DRAIN_FINALIZE_TIMEOUT = 5.0
# 虚拟路径前缀
_VIRTUAL_PATH_PREFIX = "/mnt/workspace"
_VIRTUAL_SKILLS_PREFIX = "/mnt/skills"


def _build_platform_shell_command(cmd_str: str) -> tuple[str, list[str]]:
    """根据平台构建 shell 执行命令。

    Args:
        cmd_str: 要执行的 shell 命令字符串。

    Returns:
        (shell_executable, shell_args) 元组：
        - Windows: ('powershell', ['-NoProfile', '-NonInteractive', '-Command', cmd_str])
        - macOS/Linux: ('bash', ['-lc', cmd_str])
        - 兜底（Windows 且 powershell 不可用）: ('cmd', ['/c', cmd_str])
    """
    if os.name == "nt":
        # Windows: 优先 PowerShell，失败兜底 cmd
        # -NoProfile: 不加载用户配置，避免环境变量泄露或脚本干扰
        # -NonInteractive: 禁止交互式提示
        return "powershell", ["-NoProfile", "-NonInteractive", "-Command", cmd_str]
    # macOS / Linux: bash -lc（-l 加载登录 shell 配置，-c 执行命令串）
    return "bash", ["-lc", cmd_str]


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

    async def execute_command(
        self,
        cmd: str | list[str],
        timeout: int = 120,
        *,
        shell_mode: bool = False,
    ) -> CommandResult:
        """在沙盒内执行命令。

        流程：
          1. 验证命令安全性（CommandValidator）
          2. 解析为参数列表（如果不已经是 list）
          3. 执行命令：
             - shell_mode=False（默认）：使用 asyncio.create_subprocess_exec（不经过 shell）
             - shell_mode=True：通过平台 shell 执行（PowerShell / bash），支持管道/重定向
          4. POSIX 下以独立进程组运行，超时后整组 SIGKILL
          5. 有界管道排水：后台进程不会导致 communicate() 永久阻塞
          6. 输出捕获上限 10 MB + 路径遮蔽
          7. 命令执行审计记录（异步，不阻塞主流程）

        Args:
            cmd: 命令字符串或参数列表。
            timeout: 超时秒数，默认 120。
            shell_mode: 是否通过平台 shell 执行（默认 False）。
                True 时支持管道/重定向/通配符，但安全风险增加；
                校验器会自动切换到 allow_shell_meta=True 模式，
                并对管道子命令逐段做危险模式审计。

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
            cmd_parts = self._parse_cmd(cmd_str)

        # shell 模式下临时切换 allow_shell_meta，校验完毕后还原
        original_allow_shell_meta = self.validator.allow_shell_meta
        if shell_mode:
            self.validator.allow_shell_meta = True

        try:
            # 列表形式同样必须经过安全验证，防止绕过 validate_command
            try:
                self.validator.validate_command(cmd_str)
            except SandboxPermissionError as e:
                raise self._format_interception_error(e, cmd_str) from e
        finally:
            # 还原校验器状态，避免影响后续非 shell 命令
            self.validator.allow_shell_meta = original_allow_shell_meta

        if not cmd_parts:
            raise SandboxCommandError("命令解析结果为空", command=cmd_str, exit_code=-1)

        # 2. 记录命令审计（异步，失败不阻塞主流程）
        self._audit_command(cmd_str)

        # 3. 执行命令（进程组隔离）
        posix_mode = os.name != "nt"
        # start_new_session 仅 POSIX 支持（Windows 传参会抛 TypeError）
        subprocess_kwargs: dict = {}
        if posix_mode:
            subprocess_kwargs["start_new_session"] = True  # 独立进程组，便于超时后整组清理
        try:
            if shell_mode:
                # 通过平台 shell 执行：自动选择 PowerShell / bash
                shell_cmd, shell_args = _build_platform_shell_command(cmd_str)
                process = await asyncio.create_subprocess_exec(
                    shell_cmd,
                    *shell_args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(self.workspace),
                    env=self._build_env(),
                    stdin=asyncio.subprocess.DEVNULL,
                    **subprocess_kwargs,
                )
            else:
                process = await asyncio.create_subprocess_exec(
                    *cmd_parts,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(self.workspace),
                    env=self._build_env(),
                    stdin=asyncio.subprocess.DEVNULL,  # 禁止交互式输入
                    **subprocess_kwargs,
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

        # 4. 有界管道排水：分别异步读取 stdout/stderr，避免
        #    communicate() 在后台进程（如 server &）继承管道时永久阻塞。
        drain_tasks = [
            asyncio.create_task(self._drain_stream(process.stdout, _OUTPUT_CAPTURE_LIMIT)),
            asyncio.create_task(self._drain_stream(process.stderr, _OUTPUT_CAPTURE_LIMIT)),
        ]

        # 5. 等待进程结束（带超时）
        timed_out = False
        try:
            await asyncio.wait_for(process.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            timed_out = True
            self._terminate_process_group(process, posix_mode)

        # 6. 等待排水任务完成（限时，防止后台进程拖住事件循环）
        stdout_bytes, stderr_bytes = await self._finalize_drain(drain_tasks)

        # 7. 解码输出（限制大小）
        stdout = self._decode_and_truncate(stdout_bytes)
        stderr = self._decode_and_truncate(stderr_bytes)
        exit_code = process.returncode if process.returncode is not None else -1

        # 8. 路径遮蔽
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
        resolved = self._validate_path(path)

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
        resolved = self._validate_path(path)

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
        resolved = self._validate_path(path)

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
        """构建子进程环境变量（白名单模式）。

        只传入显式白名单内的安全变量 + SANDBOX_WORKSPACE，
        防止 API Key / Secret / Token 等敏感变量泄露到沙箱子进程。
        """
        from app.security.sandbox.env_policy import build_safe_env, contains_sensitive_var

        safe_env = build_safe_env(str(self.workspace))

        # 防御性二次校验：即使白名单配置有误，也确保敏感变量不会泄露
        leaked = [k for k in safe_env if contains_sensitive_var(k) and k != "SANDBOX_WORKSPACE"]
        if leaked:
            logger.warning(
                f"[Sandbox] 环境变量白名单包含疑似敏感变量，已自动过滤: {leaked}"
            )
            for k in leaked:
                del safe_env[k]

        return safe_env

    @staticmethod
    def _decode_and_truncate(data: bytes, limit: int = _OUTPUT_CAPTURE_LIMIT) -> str:
        """解码字节数据并截断到上限。"""
        if not data:
            return ""
        text = data.decode("utf-8", errors="replace")
        if len(text) > limit:
            text = text[:limit] + f"\n... [output truncated after {limit} bytes] ..."
        return text

    # ------------------------------------------------------------------
    # 安全辅助：管道排水 / 进程组终止 / 命令审计
    # ------------------------------------------------------------------

    @staticmethod
    def _format_interception_error(
        exc: SandboxPermissionError,
        cmd: str = "",
    ) -> SandboxPermissionError:
        """将权限拒绝异常格式化为统一的"命令拦截"提示。

        使用 app.security.command_policy 的统一文案（含前往设置引导），
        前端据此识别"已拦截"状态并展示引导按钮。

        Args:
            exc: 原始 SandboxPermissionError。
            cmd: 被拦截的命令（可选）。

        Returns:
            消息已格式化的新异常实例（保留 operation/path 等元数据）。
        """
        try:
            from app.security.command_policy import format_interception_message

            message = format_interception_message(
                operation=exc.operation or "",
                command=cmd or (exc.path or ""),
                default_message=exc.message,
            )
        except Exception:
            return exc

        return SandboxPermissionError(
            message=message,
            path=exc.path,
            operation=exc.operation,
        )

    def _validate_path(self, path: str) -> Path:
        """验证路径并在越界时抛出统一格式化的拦截错误。

        Args:
            path: 待验证的路径字符串。

        Returns:
            解析后的绝对 Path。

        Raises:
            SandboxPermissionError: 路径越界或命中敏感段（已格式化）。
        """
        try:
            return self.validator.validate_path(path)
        except SandboxPermissionError as e:
            raise self._format_interception_error(e, path) from e

    @staticmethod
    async def _drain_stream(stream, limit: int) -> bytes:
        """有界读取管道流，防止后台进程继承管道导致永久阻塞。

        读取直到 EOF、达到 limit 上限或流关闭为止；
        单次最多读取 limit 字节，超限即停止（剩余数据丢弃）。

        Args:
            stream: asyncio StreamReader（子进程的 stdout/stderr）。
            limit: 最大读取字节数。

        Returns:
            已读取的字节内容。
        """
        if stream is None:
            return b""
        chunks: list[bytes] = []
        total = 0
        while total < limit:
            try:
                chunk = await stream.read(min(4096, limit - total))
            except (ConnectionError, OSError, asyncio.CancelledError):
                break
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        return b"".join(chunks)

    @staticmethod
    async def _finalize_drain(drain_tasks: list[asyncio.Task]) -> tuple[bytes, bytes]:
        """限时等待排水任务完成，超时后取消任务，返回已读取内容。

        Args:
            drain_tasks: [stdout 排水任务, stderr 排水任务]。

        Returns:
            (stdout_bytes, stderr_bytes)。
        """
        try:
            await asyncio.wait_for(
                asyncio.gather(*drain_tasks, return_exceptions=True),
                timeout=_DRAIN_FINALIZE_TIMEOUT,
            )
        except asyncio.TimeoutError:
            for task in drain_tasks:
                if not task.done():
                    task.cancel()

        results: list[bytes] = []
        for task in drain_tasks:
            try:
                result = task.result()
            except (asyncio.CancelledError, Exception):
                result = b""
            results.append(result if isinstance(result, bytes) else b"")
        return results[0], results[1]

    def _terminate_process_group(self, process, posix_mode: bool) -> None:
        """终止进程（组）。

        POSIX 下向进程组发送 SIGKILL，Windows 下回退到 process.kill()。
        进程已退出时静默忽略（ProcessLookupError）。

        Args:
            process: 子进程对象。
            posix_mode: 是否为 POSIX 平台。
        """
        try:
            if posix_mode and hasattr(os, "killpg"):
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    return
                except ProcessLookupError:
                    return  # 进程组已不存在，无需处理
            process.kill()
        except ProcessLookupError:
            pass
        except Exception as e:
            logger.warning(f"[LocalSandbox] 终止进程组失败: {e}")

    def _audit_command(self, cmd: str) -> None:
        """异步记录命令执行审计，失败不阻塞主流程。

        Args:
            cmd: 命令字符串。
        """
        try:
            from app.security.audit.logger import AuditLogger

            async def _write_audit() -> None:
                try:
                    await AuditLogger.get_instance().log_command_execute(
                        user_id="system",
                        command=cmd[:200] if len(cmd) > 200 else cmd,
                        success=True,
                    )
                except Exception as e:
                    logger.debug(f"[LocalSandbox] 命令审计写入失败: {e}")

            asyncio.create_task(_write_audit())
        except Exception as e:
            logger.debug(f"[LocalSandbox] 命令审计初始化失败: {e}")
