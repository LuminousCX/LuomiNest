import asyncio
import os
import shlex
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Query
from loguru import logger
from pydantic import BaseModel

router = APIRouter(prefix="/console", tags=["console"])


# 命令白名单（允许执行的主命令）
# 安全原则：不包含可执行任意代码的解释器/下载器/容器引擎
# （python/node/curl/wget/docker/pip/redis-cli/sqlite3 已移除，如需使用请直接在系统终端操作）
ALLOWED_COMMANDS = {
    "git", "npm", "pnpm", "yarn",
    "ls", "dir", "cat", "type", "echo", "pwd", "cd", "mkdir", "md", "rmdir",
    "cp", "copy", "mv", "move", "touch", "find", "grep", "rg", "head", "tail",
    "wc", "ping", "nslookup", "ipconfig", "netstat",
    "tasklist", "systeminfo", "where", "which",
}

# 危险命令模式（即使主命令在白名单中，包含这些模式也拒绝）
DANGEROUS_PATTERNS = {
    "rm -rf /", "rm -rf ~", "rm -rf *", "rm -rf .",
    "del /f /s /q C:\\", "del /f /s /q c:\\",
    "format ", "shutdown", "reboot", ":(){:|:&};:",
    "mkfs", "dd if=", "> /dev/sda", "> /dev/hda",
    "chmod -R 777 /", "chown -R",
    # 包管理器可执行任意包/脚本的子命令
    "npm exec", "npx ", "pnpm exec", "pnpm dlx", "yarn dlx",
    # git alias 可绑定任意命令
    "git config alias",
}

# shell 元字符（exec 模式下这些字符会被当字面参数，导致命令行为异常，需在入口拦截）
SHELL_METACHARACTERS = {"|", "&", ";", ">", "<", "`"}

# 默认命令超时（秒）
DEFAULT_COMMAND_TIMEOUT = 30
# 最大命令超时（秒）
MAX_COMMAND_TIMEOUT = 120
# 最大输出长度（字符）
MAX_OUTPUT_LENGTH = 10000
# 存储上限
MAX_STORE_SIZE = 500


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


def _validate_command(command: str) -> tuple[bool, str, list[str]]:
    """验证命令是否安全：白名单 + 危险模式 + shell 元字符检查

    Returns:
        (is_valid, error_msg, parsed_parts)
        parsed_parts 为 shlex.split 解析后的参数列表（验证失败时为空列表）
    """
    if not command or not command.strip():
        return False, "命令不能为空", []

    # 检查 shell 元字符（本接口使用 create_subprocess_exec 不经过 shell，
    # 这些字符会被当字面参数导致命令行为异常，在入口直接拒绝给出清晰提示）
    found_meta = [c for c in SHELL_METACHARACTERS if c in command]
    if found_meta:
        return False, f"命令包含 shell 元字符（{' '.join(found_meta)}），本接口不支持管道和重定向", []
    if "$(" in command:
        return False, "命令包含命令替换 $(...)，本接口不支持", []

    # 检查危险模式
    for pattern in DANGEROUS_PATTERNS:
        if pattern in command:
            return False, f"命令包含危险操作: {pattern}", []

    # 解析命令
    try:
        posix_mode = os.name != "nt"
        parts = shlex.split(command, posix=posix_mode)
    except ValueError as e:
        return False, f"命令解析失败: {e}", []

    if not parts:
        return False, "命令不能为空", []

    # 提取主命令（处理路径和 .exe 后缀）
    main_cmd = os.path.basename(parts[0]).lower()
    if main_cmd.endswith(".exe"):
        main_cmd = main_cmd[:-4]

    if main_cmd not in ALLOWED_COMMANDS:
        allowed = ", ".join(sorted(ALLOWED_COMMANDS))
        return False, f"命令 '{main_cmd}' 不在白名单中。允许的命令: {allowed}", []

    return True, "", parts


async def _execute_command_async(
    parts: list[str], working_dir: str | None, timeout: int
) -> tuple[int, str, str]:
    """异步执行命令（不经过 shell），返回 (exit_code, stdout, stderr)

    使用 create_subprocess_exec 直接执行解析后的参数列表，
    避免经过 shell 导致管道/重定向/命令注入。
    """
    try:
        cwd = working_dir if working_dir and os.path.isdir(working_dir) else None

        process = await asyncio.create_subprocess_exec(
            *parts,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return -1, "", f"命令执行超时（{timeout}秒）"

        stdout = stdout_bytes.decode("utf-8", errors="replace")[:MAX_OUTPUT_LENGTH]
        stderr = stderr_bytes.decode("utf-8", errors="replace")[:MAX_OUTPUT_LENGTH]

        return process.returncode or 0, stdout, stderr
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
    """执行命令（带白名单 + 超时 + 工作目录限制）"""
    command = req.command.strip()

    # 验证命令安全性（同时获取解析后的参数列表）
    is_valid, error_msg, parts = _validate_command(command)
    if not is_valid:
        logger.warning(f"[Console] Command rejected: {command} - {error_msg}")
        return ExecuteCommandResponse(
            command_id=str(uuid.uuid4())[:8],
            status="failed",
            exit_code=-1,
            output=None,
            error=error_msg,
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

    # 执行命令（使用解析后的参数列表，不经过 shell）
    exit_code, stdout, stderr = await _execute_command_async(
        parts, req.working_dir, timeout
    )

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
