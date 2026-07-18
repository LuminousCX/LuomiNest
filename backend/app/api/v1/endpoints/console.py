import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Query
from loguru import logger
from pydantic import BaseModel

from app.security.sandbox import (
    SandboxCommandError,
    SandboxPermissionError,
    SandboxProvider,
    SandboxTimeoutError,
)
from app.security.sandbox.local_sandbox import LocalSandbox

router = APIRouter(prefix="/console", tags=["console"])


# 命令白名单（允许执行的主命令）
# 安全原则：不包含可执行任意代码的解释器/下载器/容器引擎
# （python/node/curl/wget/docker/pip/redis-cli/sqlite3 已移除，如需使用请直接在系统终端操作）
# 白名单由沙盒 CommandValidator 执行，替代原有的手动检查
ALLOWED_COMMANDS = {
    "git", "npm", "pnpm", "yarn",
    "ls", "dir", "cat", "type", "echo", "pwd", "cd", "mkdir", "md", "rmdir",
    "cp", "copy", "mv", "move", "touch", "find", "grep", "rg", "head", "tail",
    "wc", "ping", "nslookup", "ipconfig", "netstat",
    "tasklist", "systeminfo", "where", "which",
}

# 默认命令超时（秒）
DEFAULT_COMMAND_TIMEOUT = 30
# 最大命令超时（秒）
MAX_COMMAND_TIMEOUT = 120
# 最大输出长度（字符）— 用于 API 响应截断（沙盒本身有更大的捕获限制）
MAX_OUTPUT_LENGTH = 10000
# 存储上限
MAX_STORE_SIZE = 500
# 控制台专用沙盒会话 ID
_CONSOLE_SESSION_ID = "__console__"


class CommandRecord(BaseModel):
    id: str
    command: str
    description: str
    status: str
    exit_code: int | None = None
    executed_by: str
    started_at: str
    finished_at: str | None = None
    duration_ms: int | None = None
    output: str | None = None
    error: str | None = None
    rollback_command: str | None = None


class SystemLogEntry(BaseModel):
    id: str
    timestamp: str
    level: str
    source: str
    message: str
    module: str | None = None
    extra: dict | None = None


class LogUploadRequest(BaseModel):
    logs: list[SystemLogEntry]
    uploaded_by: str = "frontend"
    session_id: str | None = None


class LogUploadResponse(BaseModel):
    upload_id: str
    received_count: int
    status: str


class ExecuteCommandRequest(BaseModel):
    command: str
    description: str = ""
    executed_by: str = "user"
    working_dir: str | None = None
    timeout: int | None = None


class ExecuteCommandResponse(BaseModel):
    command_id: str
    status: str
    exit_code: int | None
    output: str | None
    error: str | None
    duration_ms: int


# 存储初始为空，不再使用 demo 数据
_command_store: list[CommandRecord] = []
_log_store: list[SystemLogEntry] = []


def _add_log(entry: SystemLogEntry) -> None:
    """添加日志条目，超过上限时删除最旧的"""
    _log_store.append(entry)
    if len(_log_store) > MAX_STORE_SIZE:
        _log_store.pop(0)


def _add_command(record: CommandRecord) -> None:
    """添加命令记录到头部，超过上限时删除最旧的"""
    _command_store.insert(0, record)
    if len(_command_store) > MAX_STORE_SIZE:
        _command_store.pop()


class ConsoleLogHandler:
    """loguru handler，把后端日志实时写入 _log_store。

    支持解析 platform_logger 通过 logger.bind() 传入的结构化字段
    （source / adapter_type / event / instance_id），使控制台页面
    能以统一格式展示平台事件与一般后端日志。
    """

    def __call__(self, message) -> None:
        try:
            record = message.record
            level = record["level"].name.lower()
            # 映射 loguru 级别到 console 级别
            if level in ("trace", "debug"):
                level = "info"
            elif level == "warning":
                level = "warn"
            elif level == "critical":
                level = "error"

            extra = record.get("extra", {}) or {}
            message_text = record["message"]

            # 识别平台日志：platform_logger 通过 bind 注入 source=platform
            if extra.get("source") == "platform":
                adapter_type = extra.get("adapter_type", "")
                event = extra.get("event", "")
                instance_id = extra.get("instance_id", "")
                module = f"platform:{adapter_type}" if adapter_type else "platform"
                # 组装带事件标识的可读消息
                if event:
                    display_msg = f"[{event}] {message_text}"
                else:
                    display_msg = message_text
                entry_extra = {"adapter_type": adapter_type, "event": event, "instance_id": instance_id}
            else:
                module = record.get("module") or record.get("name") or "unknown"
                display_msg = message_text
                entry_extra = dict(extra) if extra else None

            entry = SystemLogEntry(
                id=str(uuid.uuid4())[:8],
                timestamp=datetime.fromtimestamp(
                    record["time"].timestamp(), tz=timezone.utc
                ).isoformat(),
                level=level,
                source="backend",
                message=display_msg,
                module=module,
                extra=entry_extra,
            )
            _add_log(entry)
        except Exception:
            # 防止日志 handler 自身出错导致崩溃
            pass


# 注册 loguru handler，捕获 INFO 及以上级别的日志
_console_handler = ConsoleLogHandler()
logger.add(_console_handler, level="INFO", format="{message}")


def _get_console_sandbox() -> LocalSandbox:
    """获取控制台专用沙盒实例（带白名单配置）。

    使用固定的 console session，首次获取时配置 CommandValidator 白名单模式。
    """
    provider = SandboxProvider.get_instance()
    sandbox = provider.acquire(_CONSOLE_SESSION_ID)

    # 配置白名单模式（仅首次需要）
    if not sandbox.validator.whitelist_mode:
        sandbox.validator.whitelist_mode = True
        sandbox.validator.allowed_commands = ALLOWED_COMMANDS

    return sandbox


async def _execute_command_via_sandbox(
    sandbox: LocalSandbox, command: str, timeout: int
) -> tuple[int, str, str]:
    """通过沙盒执行命令，返回 (exit_code, stdout, stderr)。

    沙盒负责命令验证（白名单 + 危险模式 + shell 元字符）、
    超时控制和输出路径遮蔽。
    """
    try:
        result = await sandbox.execute_command(command, timeout=timeout)
        return result.exit_code, result.stdout, result.stderr
    except SandboxPermissionError as e:
        return -1, "", e.message
    except SandboxTimeoutError as e:
        return -1, "", e.message
    except SandboxCommandError as e:
        return -1, "", e.message
    except Exception as e:
        return -1, "", str(e)


@router.get("/commands", response_model=list[CommandRecord])
async def get_command_records(
    status: str | None = Query(None, description="Filter by status: success, failed, running"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    records = _command_store
    if status:
        records = [r for r in records if r.status == status]
    return records[offset : offset + limit]


@router.post("/commands", response_model=CommandRecord)
async def create_command_record(record: CommandRecord):
    """手动记录一条命令记录（不执行，仅记录）"""
    _add_command(record)
    logger.info(f"[Console] Command recorded: {record.command} (status={record.status})")
    return record


@router.post("/execute", response_model=ExecuteCommandResponse)
async def execute_command(req: ExecuteCommandRequest):
    """执行命令（通过沙盒，带白名单 + 超时 + 路径遮蔽）"""
    command = req.command.strip()

    if not command:
        return ExecuteCommandResponse(
            command_id=str(uuid.uuid4())[:8],
            status="failed",
            exit_code=-1,
            output=None,
            error="命令不能为空",
            duration_ms=0,
        )

    # 获取沙盒实例（内置 CommandValidator 白名单验证）
    try:
        sandbox = _get_console_sandbox()
    except Exception as e:
        logger.error(f"[Console] 沙盒初始化失败: {e}")
        return ExecuteCommandResponse(
            command_id=str(uuid.uuid4())[:8],
            status="failed",
            exit_code=-1,
            output=None,
            error=f"沙盒初始化失败: {e}",
            duration_ms=0,
        )

    command_id = str(uuid.uuid4())[:8]
    started_at = datetime.now(timezone.utc)
    timeout = min(req.timeout or DEFAULT_COMMAND_TIMEOUT, MAX_COMMAND_TIMEOUT)

    logger.info(
        f"[Console] Executing command: {command} (id={command_id}, timeout={timeout}s)"
    )

    # 记录开始状态
    record = CommandRecord(
        id=command_id,
        command=command,
        description=req.description or f"执行命令: {command[:50]}",
        status="running",
        executed_by=req.executed_by,
        started_at=started_at.isoformat(),
    )
    _add_command(record)

    # 通过沙盒执行命令（验证 + 执行 + 路径遮蔽一体化）
    exit_code, stdout, stderr = await _execute_command_via_sandbox(
        sandbox, command, timeout
    )

    # API 响应截断（沙盒捕获上限更大，这里限制返回给前端的长度）
    if stdout and len(stdout) > MAX_OUTPUT_LENGTH:
        stdout = stdout[:MAX_OUTPUT_LENGTH] + "\n... [truncated]"
    if stderr and len(stderr) > MAX_OUTPUT_LENGTH:
        stderr = stderr[:MAX_OUTPUT_LENGTH] + "\n... [truncated]"

    finished_at = datetime.now(timezone.utc)
    duration_ms = int((finished_at - started_at).total_seconds() * 1000)
    status = "success" if exit_code == 0 else "failed"

    # 更新记录
    record.status = status
    record.exit_code = exit_code
    record.finished_at = finished_at.isoformat()
    record.duration_ms = duration_ms
    record.output = stdout if stdout else None
    record.error = stderr if stderr else None

    if status == "success":
        logger.success(
            f"[Console] Command completed: {command} (exit={exit_code}, duration={duration_ms}ms)"
        )
    else:
        logger.error(
            f"[Console] Command failed: {command} (exit={exit_code}, duration={duration_ms}ms)"
        )

    return ExecuteCommandResponse(
        command_id=command_id,
        status=status,
        exit_code=exit_code,
        output=stdout if stdout else None,
        error=stderr if stderr else None,
        duration_ms=duration_ms,
    )


@router.delete("/commands")
async def clear_command_records():
    """清空命令记录"""
    count = len(_command_store)
    _command_store.clear()
    logger.info(f"[Console] Cleared {count} command records")
    return {"status": "ok", "cleared": count}


@router.get("/logs", response_model=list[SystemLogEntry])
async def get_system_logs(
    source: str | None = Query(None, description="Filter by source: frontend, backend"),
    level: str | None = Query(None, description="Filter by level: info, warn, error, success"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    entries = _log_store
    if source:
        entries = [e for e in entries if e.source == source]
    if level:
        entries = [e for e in entries if e.level == level]
    # 返回最新的日志（倒序）
    result = list(reversed(entries))
    return result[offset : offset + limit]


@router.post("/logs/upload", response_model=LogUploadResponse)
async def upload_logs(req: LogUploadRequest):
    """接收前端上传的日志并存入存储"""
    upload_id = str(uuid.uuid4())[:12]
    received = len(req.logs)

    for log_entry in req.logs:
        _add_log(log_entry)

    logger.info(
        f"[Console] Logs uploaded: upload_id={upload_id}, "
        f"count={received}, source={req.uploaded_by}"
    )
    return LogUploadResponse(
        upload_id=upload_id,
        received_count=received,
        status="accepted",
    )


@router.delete("/logs")
async def clear_system_logs():
    """清空系统日志"""
    count = len(_log_store)
    _log_store.clear()
    logger.info(f"[Console] Cleared {count} log entries")
    return {"status": "ok", "cleared": count}
