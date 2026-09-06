"""LuomiNest CLI 工具。

为主 Agent 提供命令行执行能力，通过安全沙盒执行命令。

安全策略：
1. 沙盒白名单验证：仅允许 ALLOWED_COMMANDS 中的命令
2. 超时控制：默认 30 秒，可通过参数调整（上限 120 秒）
3. 输出截断：stdout/stderr 合计超过 20000 字符时截断
4. 执行记录同步到控制台页面，executed_by 标记为 "ai_tool"
"""
import uuid
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from app.core.tools.registry import ToolBase, ToolResult
from app.core.utils import utc_now_dt

# 沙盒异常类型
from app.security.sandbox import (
    SandboxCommandError,
    SandboxPermissionError,
    SandboxProvider,
    SandboxTimeoutError,
)

# 输出截断阈值
_MAX_OUTPUT_CHARS = 20000
# 默认与最大超时（秒）
_DEFAULT_TIMEOUT = 30
_MAX_TIMEOUT = 120
# CLI 工具专用沙盒会话 ID
_CLI_SESSION_ID = "__cli_tool__"


def _get_cli_sandbox():
    """获取 CLI 工具专用沙盒实例（带白名单配置 + 用户策略）。

    复用 console.py 的 ALLOWED_COMMANDS 白名单，首次获取时配置，
    并每次加载用户自定义白名单扩展/黑名单（支持运行时热更新）。
    """
    from app.api.v1.endpoints.console import ALLOWED_COMMANDS
    from app.security.command_policy import load_command_policy

    provider = SandboxProvider.get_instance()
    sandbox = provider.acquire(_CLI_SESSION_ID)

    # 配置白名单模式（仅首次需要）
    if not sandbox.validator.whitelist_mode:
        sandbox.validator.whitelist_mode = True
        sandbox.validator.set_base_whitelist(ALLOWED_COMMANDS)

    # 应用用户策略（每次获取都重新同步，保证热更新生效）
    policy = load_command_policy()
    sandbox.validator.apply_user_policy(
        extra_whitelist=policy["extra_whitelist"],
        blacklist=policy["blacklist"],
    )

    return sandbox


def _record_command(
    command: str,
    exit_code: int,
    stdout: str,
    stderr: str,
    duration_ms: int,
    status: str,
) -> None:
    """将命令执行记录同步到控制台页面的 _command_store。

    executed_by 设为 "ai_tool" 以区分用户手动执行。
    """
    try:
        from app.api.v1.endpoints.console import CommandRecord, _add_command

        now = utc_now_dt()
        record = CommandRecord(
            id=str(uuid.uuid4())[:8],
            command=command,
            description=f"AI 工具调用执行: {command[:50]}",
            status=status,
            exit_code=exit_code,
            executed_by="ai_tool",
            started_at=(
                datetime.fromtimestamp(
                    now.timestamp() - duration_ms / 1000, tz=timezone.utc
                ).isoformat()
            ),
            finished_at=now.isoformat(),
            duration_ms=duration_ms,
            output=stdout if stdout else None,
            error=stderr if stderr else None,
        )
        _add_command(record)
    except Exception as e:
        logger.warning(f"[CliTool] 同步命令记录到控制台失败: {e}")


class CliTool(ToolBase):
    """命令行执行工具（通过安全沙盒）"""

    @property
    def name(self) -> str:
        return "cli"

    @property
    def description(self) -> str:
        return (
            "在安全沙盒环境中执行命令行命令。支持 git、npm、ls、cat 等常用系统命令。"
            "危险命令（如 rm -rf /、format、shutdown）会被拦截。"
            "输出超过 20000 字符会被截断。"
            "执行记录会同步到控制台页面。"
            "\n\n"
            "**shell 模式**：当需要管道（|）、重定向（>）、通配符（*）等 shell 语法时，"
            "设置 use_shell=true。shell 模式下命令会经过平台 shell（Windows: PowerShell，"
            "macOS/Linux: bash），安全风险更高，请仅在必要时开启。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的命令行指令",
                },
                "timeout": {
                    "type": "integer",
                    "description": f"超时秒数（可选，默认 {_DEFAULT_TIMEOUT}，上限 {_MAX_TIMEOUT}）",
                    "default": _DEFAULT_TIMEOUT,
                },
                "use_shell": {
                    "type": "boolean",
                    "description": (
                        "是否通过平台 shell 执行（默认 false）。"
                        "当命令需要管道/重定向/通配符时设置为 true。"
                        "开启后命令经过 PowerShell（Windows）或 bash（macOS/Linux）。"
                    ),
                    "default": False,
                },
            },
            "required": ["command"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        command = arguments.get("command", "").strip()
        if not command:
            return ToolResult.fail("缺少 command 参数")

        timeout = arguments.get("timeout") or _DEFAULT_TIMEOUT
        timeout = min(max(int(timeout), 1), _MAX_TIMEOUT)
        use_shell = bool(arguments.get("use_shell", False))

        logger.info(
            f"[CliTool] 执行命令: {command[:100]} (timeout={timeout}s, shell={use_shell})"
        )

        # 获取沙盒实例
        try:
            sandbox = _get_cli_sandbox()
        except Exception as e:
            logger.error(f"[CliTool] 沙盒初始化失败: {e}")
            return ToolResult.fail(f"沙盒初始化失败: {e}")

        # 通过沙盒执行命令
        started_at = datetime.now(timezone.utc)
        try:
            result = await sandbox.execute_command(
                command, timeout=timeout, shell_mode=use_shell
            )
            exit_code = result.exit_code
            stdout = result.stdout or ""
            stderr = result.stderr or ""
        except SandboxPermissionError as e:
            duration_ms = int(
                (datetime.now(timezone.utc) - started_at).total_seconds() * 1000
            )
            _record_command(command, -1, "", e.message, duration_ms, "failed")
            logger.warning(f"[CliTool] 命令被沙盒拒绝: {e.message}")
            return ToolResult.fail(f"命令被沙盒拒绝: {e.message}")
        except SandboxTimeoutError as e:
            duration_ms = int(
                (datetime.now(timezone.utc) - started_at).total_seconds() * 1000
            )
            _record_command(command, -1, "", e.message, duration_ms, "failed")
            return ToolResult.fail(f"命令执行超时: {e.message}")
        except SandboxCommandError as e:
            duration_ms = int(
                (datetime.now(timezone.utc) - started_at).total_seconds() * 1000
            )
            _record_command(command, -1, "", e.message, duration_ms, "failed")
            return ToolResult.fail(f"命令执行错误: {e.message}")
        except Exception as e:
            duration_ms = int(
                (datetime.now(timezone.utc) - started_at).total_seconds() * 1000
            )
            _record_command(command, -1, "", str(e), duration_ms, "failed")
            return ToolResult.fail(f"命令执行异常: {e}")

        finished_at = datetime.now(timezone.utc)
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)

        # 组装输出
        parts: list[str] = []
        if stdout:
            parts.append(f"[stdout]\n{stdout}")
        if stderr:
            parts.append(f"[stderr]\n{stderr}")
        parts.append(f"[exit_code] {exit_code}")

        output = "\n".join(parts)

        # 截断过长输出
        if len(output) > _MAX_OUTPUT_CHARS:
            output = output[:_MAX_OUTPUT_CHARS] + f"\n...(输出已截断，共 {len(output)} 字符)"

        status = "success" if exit_code == 0 else "failed"

        # 同步命令记录到控制台
        _record_command(command, exit_code, stdout, stderr, duration_ms, status)

        if exit_code == 0:
            return ToolResult.ok(output, metadata={"exit_code": exit_code, "duration_ms": duration_ms})
        return ToolResult(
            success=False,
            output=output,
            error=f"命令退出码非零: {exit_code}",
            metadata={"exit_code": exit_code, "duration_ms": duration_ms},
        )
