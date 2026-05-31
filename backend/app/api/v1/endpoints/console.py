import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Query
from loguru import logger
from pydantic import BaseModel

router = APIRouter(prefix="/console", tags=["console"])


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


_command_store: list[CommandRecord] = []
_log_store: list[SystemLogEntry] = []


def _init_demo_data() -> None:
    now = datetime.now(timezone.utc)

    demo_commands = [
        CommandRecord(
            id=str(uuid.uuid4())[:8],
            command="ollama pull deepseek-r1:7b",
            description="拉取 DeepSeek-R1 7B 模型到本地 Ollama",
            status="success",
            exit_code=0,
            executed_by="Agent-小助手",
            started_at=datetime(2026, 5, 31, 10, 2, 15, tzinfo=timezone.utc).isoformat(),
            finished_at=datetime(2026, 5, 31, 10, 5, 42, tzinfo=timezone.utc).isoformat(),
            duration_ms=207000,
            output="success",
            rollback_command="ollama rm deepseek-r1:7b",
        ),
        CommandRecord(
            id=str(uuid.uuid4())[:8],
            command="pip install luominest-plugin-weather==2.1.0",
            description="安装天气插件 v2.1.0",
            status="failed",
            exit_code=1,
            executed_by="Agent-小助手",
            started_at=datetime(2026, 5, 31, 10, 8, 0, tzinfo=timezone.utc).isoformat(),
            finished_at=datetime(2026, 5, 31, 10, 8, 3, tzinfo=timezone.utc).isoformat(),
            duration_ms=3000,
            output=None,
            error="Package 'luominest-plugin-weather' not found on PyPI",
            rollback_command="pip uninstall luominest-plugin-weather -y",
        ),
        CommandRecord(
            id=str(uuid.uuid4())[:8],
            command="luominest agent create --name 代码审查员 --model deepseek-chat",
            description="创建代码审查 Agent",
            status="success",
            exit_code=0,
            executed_by="System",
            started_at=datetime(2026, 5, 31, 10, 12, 30, tzinfo=timezone.utc).isoformat(),
            finished_at=datetime(2026, 5, 31, 10, 12, 31, tzinfo=timezone.utc).isoformat(),
            duration_ms=1200,
            output="Agent '代码审查员' created with id: agt_coder01",
            rollback_command="luominest agent delete agt_coder01",
        ),
        CommandRecord(
            id=str(uuid.uuid4())[:8],
            command="redis-cli SET session:active_agent '小助手'",
            description="设置当前活跃 Agent 为小助手",
            status="success",
            exit_code=0,
            executed_by="Agent-小助手",
            started_at=datetime(2026, 5, 31, 10, 15, 0, tzinfo=timezone.utc).isoformat(),
            finished_at=datetime(2026, 5, 31, 10, 15, 0, tzinfo=timezone.utc).isoformat(),
            duration_ms=15,
            output="OK",
            rollback_command="redis-cli DEL session:active_agent",
        ),
        CommandRecord(
            id=str(uuid.uuid4())[:8],
            command="luominest memory export --format markdown --output ./exports/memory.md",
            description="导出长期记忆为 Markdown 文件",
            status="success",
            exit_code=0,
            executed_by="Agent-翻译官",
            started_at=datetime(2026, 5, 31, 10, 20, 10, tzinfo=timezone.utc).isoformat(),
            finished_at=datetime(2026, 5, 31, 10, 20, 12, tzinfo=timezone.utc).isoformat(),
            duration_ms=2000,
            output="Exported 45 memory entries to ./exports/memory.md",
            rollback_command="rm ./exports/memory.md",
        ),
    ]
    _command_store.extend(demo_commands)

    demo_logs = [
        SystemLogEntry(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime(2026, 5, 31, 10, 0, 0, tzinfo=timezone.utc).isoformat(),
            level="info",
            source="backend",
            message="[LuomiNest] Starting application...",
            module="app_factory",
        ),
        SystemLogEntry(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime(2026, 5, 31, 10, 0, 1, tzinfo=timezone.utc).isoformat(),
            level="info",
            source="backend",
            message="[LuomiNest] Environment: Development",
            module="app_factory",
        ),
        SystemLogEntry(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime(2026, 5, 31, 10, 0, 2, tzinfo=timezone.utc).isoformat(),
            level="success",
            source="backend",
            message="[AppFactory] FastAPI application created successfully",
            module="app_factory",
        ),
        SystemLogEntry(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime(2026, 5, 31, 10, 0, 3, tzinfo=timezone.utc).isoformat(),
            level="info",
            source="backend",
            message="[HTTP] --> GET /api/v1/system/health (id=140234567890)",
            module="middleware",
        ),
        SystemLogEntry(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime(2026, 5, 31, 10, 0, 3, tzinfo=timezone.utc).isoformat(),
            level="success",
            source="backend",
            message="[HTTP] <-- GET /api/v1/system/health 200 (12.3ms)",
            module="middleware",
        ),
        SystemLogEntry(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime(2026, 5, 31, 10, 0, 5, tzinfo=timezone.utc).isoformat(),
            level="info",
            source="backend",
            message="Memory engine initialized successfully",
            module="memory_engine",
        ),
        SystemLogEntry(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime(2026, 5, 31, 10, 2, 15, tzinfo=timezone.utc).isoformat(),
            level="info",
            source="backend",
            message="Agent '小助手' executing command: ollama pull deepseek-r1:7b",
            module="agent_orchestrator",
        ),
        SystemLogEntry(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime(2026, 5, 31, 10, 5, 42, tzinfo=timezone.utc).isoformat(),
            level="success",
            source="backend",
            message="Command 'ollama pull deepseek-r1:7b' completed (exit_code=0, duration=207s)",
            module="agent_orchestrator",
        ),
        SystemLogEntry(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime(2026, 5, 31, 10, 8, 3, tzinfo=timezone.utc).isoformat(),
            level="error",
            source="backend",
            message="Command 'pip install luominest-plugin-weather==2.1.0' failed: Package not found on PyPI",
            module="agent_orchestrator",
        ),
        SystemLogEntry(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime(2026, 5, 31, 10, 10, 0, tzinfo=timezone.utc).isoformat(),
            level="warn",
            source="backend",
            message="HomeAssistant connection timeout, retrying in 5s...",
            module="home_assistant",
        ),
        SystemLogEntry(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime(2026, 5, 31, 10, 10, 5, tzinfo=timezone.utc).isoformat(),
            level="success",
            source="backend",
            message="HomeAssistant reconnected successfully",
            module="home_assistant",
        ),
        SystemLogEntry(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime(2026, 5, 31, 10, 12, 31, tzinfo=timezone.utc).isoformat(),
            level="info",
            source="backend",
            message="Agent '代码审查员' created (id=agt_coder01)",
            module="agent_service",
        ),
        SystemLogEntry(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime(2026, 5, 31, 10, 15, 0, tzinfo=timezone.utc).isoformat(),
            level="info",
            source="frontend",
            message="WebSocket connection established to /ws/chat",
            module="ws_manager",
        ),
        SystemLogEntry(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime(2026, 5, 31, 10, 15, 1, tzinfo=timezone.utc).isoformat(),
            level="info",
            source="frontend",
            message="Live2D model 'Hiyori' loaded successfully",
            module="live2d_loader",
        ),
        SystemLogEntry(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime(2026, 5, 31, 10, 18, 0, tzinfo=timezone.utc).isoformat(),
            level="warn",
            source="frontend",
            message="TTS engine slow response (latency: 850ms > threshold 500ms)",
            module="tts_engine",
        ),
        SystemLogEntry(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime(2026, 5, 31, 10, 20, 12, tzinfo=timezone.utc).isoformat(),
            level="info",
            source="backend",
            message="Memory export completed: 45 entries -> ./exports/memory.md",
            module="markdown_exporter",
        ),
        SystemLogEntry(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime(2026, 5, 31, 10, 25, 0, tzinfo=timezone.utc).isoformat(),
            level="info",
            source="frontend",
            message="User switched to dark theme",
            module="theme_store",
        ),
        SystemLogEntry(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime(2026, 5, 31, 10, 30, 0, tzinfo=timezone.utc).isoformat(),
            level="error",
            source="frontend",
            message="Plugin 'weather-v2' load failed: missing dependency 'requests>=2.28'",
            module="plugin_loader",
        ),
    ]
    _log_store.extend(demo_logs)


_init_demo_data()


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
    _command_store.insert(0, record)
    logger.info(f"[Console] Command recorded: {record.command} (status={record.status})")
    return record


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
    return entries[offset : offset + limit]


@router.post("/logs/upload", response_model=LogUploadResponse)
async def upload_logs(req: LogUploadRequest):
    upload_id = str(uuid.uuid4())[:12]
    received = len(req.logs)
    logger.info(
        f"[Console] Logs uploaded: upload_id={upload_id}, "
        f"count={received}, source={req.uploaded_by}"
    )
    return LogUploadResponse(
        upload_id=upload_id,
        received_count=received,
        status="accepted",
    )
