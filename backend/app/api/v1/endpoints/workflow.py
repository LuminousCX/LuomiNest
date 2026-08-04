"""LuomiNest 工作流引擎 REST API。

提供长任务工作流的提交、查询、取消和计划确认接口：
- POST   /workflow/submit          提交长任务（非流式）
- POST   /workflow/submit/stream   提交长任务（SSE 流式）
- GET    /workflow/sessions        列出活跃会话
- GET    /workflow/sessions/{id}   获取会话详情
- POST   /workflow/sessions/{id}/cancel  取消会话
- POST   /workflow/sessions/{id}/confirm 确认执行计划
- POST   /workflow/sessions/{id}/reject  拒绝执行计划
- GET    /workflow/tools           列出已注册的内部工具
"""
from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from app.core.exceptions import LuomiNestError
from app.core.utils import ok, sse_response, sse_data
from app.core.workflow import (
    WorkflowMode,
    WorkflowPhase,
    internal_tool_registry,
    workflow_engine,
)

router = APIRouter(prefix="/workflow", tags=["workflow"])


class WorkflowSubmitRequest(BaseModel):
    """工作流提交请求"""
    message: str = Field(..., description="用户的长任务请求")
    provider: str | None = Field(None, description="LLM provider（可选）")
    model: str | None = Field(None, description="LLM model（可选）")
    mode: WorkflowMode = Field(
        WorkflowMode.STANDARD,
        description="工作流执行模式：standard(标准)/ultra(超长)",
    )
    conversation_id: str | None = Field(None, description="关联对话 ID（可选）")


class PlanConfirmationRequest(BaseModel):
    """计划确认/拒绝请求"""
    feedback: str = Field("", description="用户反馈（可选）")


@router.post("/submit")
async def submit_workflow(req: WorkflowSubmitRequest):
    """提交长任务到工作流引擎（非流式）

    返回完整的执行结果，适合不需要实时进度的场景。
    """
    try:
        session = await workflow_engine.submit(
            user_message=req.message,
            provider=req.provider,
            model=req.model,
            mode=req.mode,
            conversation_id=req.conversation_id,
        )
        return session.to_dict()
    except LuomiNestError:
        raise
    except Exception as e:
        logger.error("[WorkflowAPI] Submit failed: {}", str(e), exc_info=True)
        raise LuomiNestError(
            "工作流执行失败，请稍后重试",
            code="WORKFLOW_SUBMIT_FAILED",
            status_code=500,
        )


@router.post("/submit/stream")
async def submit_workflow_stream(req: WorkflowSubmitRequest):
    """提交长任务到工作流引擎（SSE 流式）

    返回 Server-Sent Events 流，实时推送执行进度。
    """
    async def _event_stream():
        try:
            async for event in workflow_engine.submit_stream(
                user_message=req.message,
                provider=req.provider,
                model=req.model,
                mode=req.mode,
                conversation_id=req.conversation_id,
            ):
                yield sse_data(event)
        except Exception as e:
            logger.error("[WorkflowAPI] Stream failed: {}", str(e), exc_info=True)
            error_event = {"type": "error", "data": {"message": "工作流执行失败，请稍后重试"}}
            yield sse_data(error_event)

    return sse_response(
        _event_stream(),
    )


@router.get("/sessions")
async def list_sessions():
    """列出所有活跃的工作流会话"""
    sessions = workflow_engine.list_active_sessions()
    return [s.to_dict() for s in sessions]


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """获取指定工作流会话详情"""
    session = workflow_engine.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
    return session.to_dict()


@router.post("/sessions/{session_id}/cancel")
async def cancel_session(session_id: str):
    """取消工作流会话"""
    success = await workflow_engine.cancel_session(session_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"会话 {session_id} 不存在或已完成",
        )
    return ok({"session_id": session_id})


@router.post("/sessions/{session_id}/confirm")
async def confirm_session(session_id: str, req: PlanConfirmationRequest):
    """确认执行工作流计划

    用户在 plan_pending_confirmation 阶段确认后调用此端点，
    工作流将继续执行子任务。
    """
    success = workflow_engine.confirm_session(session_id, req.feedback)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"会话 {session_id} 不存在或不在等待确认状态",
        )
    return ok({"session_id": session_id})


@router.post("/sessions/{session_id}/reject")
async def reject_session(session_id: str, req: PlanConfirmationRequest):
    """拒绝执行工作流计划

    用户在 plan_pending_confirmation 阶段拒绝后调用此端点，
    工作流将终止并返回拒绝原因。
    """
    success = workflow_engine.reject_session(session_id, req.feedback)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"会话 {session_id} 不存在或不在等待确认状态",
        )
    return ok({"session_id": session_id})


@router.get("/tools")
async def list_internal_tools():
    """列出所有已注册的内部模块接口"""
    return {
        "tools": [t.to_dict() for t in internal_tool_registry.list_tools()],
        "modules": internal_tool_registry.get_module_summary(),
    }


# ─── 数据库持久化会话端点 ───


@router.get("/db/sessions")
async def list_db_sessions(limit: int = 20):
    """列出数据库中的工作流会话（历史记录）"""
    from app.services.workflow_persistence import list_workflow_sessions
    sessions = await list_workflow_sessions(limit=limit)
    return {"sessions": sessions, "count": len(sessions)}


@router.get("/db/sessions/{session_id}")
async def get_db_session(session_id: str):
    """获取数据库中的工作流会话详情（含节点）"""
    from app.services.workflow_persistence import get_workflow_session
    session = await get_workflow_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
    return session


# ─── 工具调用记录端点（控制台日志展示） ───


@router.get("/tool-records")
async def list_tool_records(limit: int = 50, session_id: str | None = None):
    """列出工具调用记录（审计日志）

    供前端 ConsoleView 工作流日志 Tab 展示工具调用历史。
    """
    from app.services.tool_call_recorder import list_tool_call_records
    records = await list_tool_call_records(session_id=session_id, limit=limit)
    return {"records": records, "count": len(records)}


@router.get("/tool-records/{record_id}")
async def get_tool_record(record_id: str):
    """获取工具调用记录详情（含完整参数与结果）"""
    from app.services.tool_call_recorder import get_tool_call_record
    record = await get_tool_call_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"记录 {record_id} 不存在")
    return record
