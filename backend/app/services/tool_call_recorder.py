"""LuomiNest 工具调用记录服务。

记录工作流与普通对话中工具调用的完整记录，用于：
1. 工具结果落盘：超阈值结果存数据库，LLM 上下文用占位符替换（借鉴 claude-code-src）
2. 执行审计：记录每次工具调用的参数、结果、耗时、成功状态
3. 控制台日志：前端 ConsoleView 展示工具调用历史
"""
import json
import uuid
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.core.utils import utc_now
from app.infrastructure.database.models.tool_call_record import ToolCallRecordORM
from app.infrastructure.database.session import get_async_session

# 工具结果落盘阈值（超过此长度则存数据库并用占位符替换）
LUMINOUS_PERSIST_THRESHOLD = 2000

# 占位符模板
_PERSISTED_OUTPUT_TEMPLATE = '<luminous-persisted-output id="{record_id}"/>'


def should_persist(result_text: str) -> bool:
    """判断工具结果是否需要落盘"""
    return len(result_text) > LUMINOUS_PERSIST_THRESHOLD


def build_placeholder(record_id: str) -> str:
    """生成占位符字符串"""
    return _PERSISTED_OUTPUT_TEMPLATE.format(record_id=record_id)


async def record_tool_call(
    session_id: str | None,
    tool_name: str,
    arguments: dict[str, Any],
    result: Any,
    success: bool,
    duration_ms: int = 0,
    conversation_id: str | None = None,
    scope: str | None = None,
    tool_type: str | None = None,
) -> str:
    """记录工具调用，返回 record_id

    如果结果超过阈值，返回占位符；否则返回原始结果文本。
    """
    record_id = f"tcr_{uuid.uuid4().hex[:12]}"

    # 序列化结果
    if isinstance(result, str):
        result_text = result
    elif isinstance(result, dict):
        result_text = json.dumps(result, ensure_ascii=False)
    else:
        result_text = str(result)

    arguments_json = json.dumps(arguments, ensure_ascii=False) if arguments else None
    result_json = result_text if len(result_text) <= 50000 else result_text[:50000]

    async with get_async_session() as db:
        stmt = sqlite_insert(ToolCallRecordORM).values(
            record_id=record_id,
            session_id=session_id,
            conversation_id=conversation_id,
            tool_name=tool_name,
            arguments_json=arguments_json,
            result_json=result_json,
            success=success,
            duration_ms=duration_ms,
            created_at=utc_now(),
            scope=scope,
            tool_type=tool_type,
        )
        await db.execute(stmt)

    logger.debug(
        f"[ToolCallRecorder] Recorded: id={record_id}, tool={tool_name}, "
        f"success={success}, duration={duration_ms}ms"
    )

    # 超阈值则返回占位符
    if should_persist(result_text):
        return build_placeholder(record_id)
    return result_text


async def get_tool_call_record(record_id: str) -> dict[str, Any] | None:
    """获取工具调用记录"""
    async with get_async_session() as db:
        result = await db.execute(
            select(ToolCallRecordORM).where(ToolCallRecordORM.record_id == record_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            return None

        return {
            "record_id": record.record_id,
            "session_id": record.session_id,
            "conversation_id": record.conversation_id,
            "tool_name": record.tool_name,
            "arguments": json.loads(record.arguments_json) if record.arguments_json else {},
            "result": record.result_json,
            "success": record.success,
            "duration_ms": record.duration_ms,
            "created_at": record.created_at,
        }


async def list_tool_call_records(
    session_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """列出工具调用记录"""
    async with get_async_session() as db:
        query = select(ToolCallRecordORM).order_by(
            ToolCallRecordORM.created_at.desc()
        ).limit(limit)
        if session_id:
            query = query.where(ToolCallRecordORM.session_id == session_id)

        result = await db.execute(query)
        records = result.scalars().all()
        return [
            {
                "record_id": r.record_id,
                "session_id": r.session_id,
                "tool_name": r.tool_name,
                "success": r.success,
                "duration_ms": r.duration_ms,
                "created_at": r.created_at,
                "result_preview": (r.result_json or "")[:200],
            }
            for r in records
        ]
