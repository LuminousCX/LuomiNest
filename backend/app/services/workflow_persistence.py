"""LuomiNest 工作流会话持久化服务。

将工作流会话和节点状态持久化到数据库，替代 engine.py 的内存 _active_sessions 字典。
支持历史回溯、流程图重建、跨重启恢复。
"""
import json
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy import Integer, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.core.utils import utc_now
from app.infrastructure.database.models.workflow_node import WorkflowNodeORM
from app.infrastructure.database.models.workflow_session import WorkflowSessionORM
from app.infrastructure.database.session import get_async_session


async def save_workflow_session(
    session_id: str,
    user_message: str,
    mode: str,
    phase: str,
    analysis: str | None = None,
    plan_json: str | None = None,
    final_result: str | None = None,
    error: str | None = None,
    conversation_id: str | None = None,
    completed_at: str | None = None,
) -> None:
    """保存或更新工作流会话（upsert）"""
    async with get_async_session() as db:
        stmt = sqlite_insert(WorkflowSessionORM).values(
            session_id=session_id,
            user_message=user_message,
            mode=mode,
            phase=phase,
            analysis=analysis,
            plan_json=plan_json,
            final_result=final_result,
            error=error,
            conversation_id=conversation_id,
            created_at=utc_now(),
            completed_at=completed_at,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["session_id"],
            set_={
                "phase": phase,
                "analysis": analysis,
                "plan_json": plan_json,
                "final_result": final_result,
                "error": error,
                "completed_at": completed_at,
            },
        )
        await db.execute(stmt)
        logger.debug(f"[WorkflowPersistence] Session {session_id} saved (phase={phase})")


async def save_workflow_nodes(
    session_id: str,
    tasks: list[dict[str, Any]],
) -> None:
    """保存工作流节点（批量 upsert）"""
    async with get_async_session() as db:
        for task in tasks:
            node_id = task.get("task_id", f"node_{task.get('title', 'unknown')}")
            stmt = sqlite_insert(WorkflowNodeORM).values(
                node_id=node_id,
                session_id=session_id,
                title=task.get("title", ""),
                description=task.get("description"),
                node_type=task.get("node_type", "tool"),
                tool_name=task.get("tool_name"),
                arguments_json=json.dumps(task.get("arguments", {}), ensure_ascii=False) if task.get("arguments") else None,
                depends_on_json=json.dumps(task.get("depends_on", []), ensure_ascii=False) if task.get("depends_on") else None,
                priority=task.get("priority", "normal"),
                status=task.get("status", "pending"),
                result=task.get("result"),
                error=task.get("error"),
                started_at=task.get("started_at"),
                completed_at=task.get("completed_at"),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["node_id"],
                set_={
                    "status": task.get("status", "pending"),
                    "result": task.get("result"),
                    "error": task.get("error"),
                    "started_at": task.get("started_at"),
                    "completed_at": task.get("completed_at"),
                },
            )
            await db.execute(stmt)
        logger.debug(f"[WorkflowPersistence] {len(tasks)} nodes saved for session {session_id}")


async def get_workflow_session(session_id: str) -> dict[str, Any] | None:
    """获取工作流会话详情（含节点）"""
    async with get_async_session() as db:
        session_result = await db.execute(
            select(WorkflowSessionORM).where(WorkflowSessionORM.session_id == session_id)
        )
        session_orm = session_result.scalar_one_or_none()
        if not session_orm:
            return None

        nodes_result = await db.execute(
            select(WorkflowNodeORM)
            .where(WorkflowNodeORM.session_id == session_id)
            .order_by(WorkflowNodeORM.node_id)
        )
        nodes = nodes_result.scalars().all()

        return {
            "session_id": session_orm.session_id,
            "user_message": session_orm.user_message,
            "mode": session_orm.mode,
            "phase": session_orm.phase,
            "analysis": session_orm.analysis,
            "plan_json": session_orm.plan_json,
            "final_result": session_orm.final_result,
            "error": session_orm.error,
            "conversation_id": session_orm.conversation_id,
            "created_at": session_orm.created_at,
            "completed_at": session_orm.completed_at,
            "nodes": [
                {
                    "node_id": n.node_id,
                    "title": n.title,
                    "description": n.description,
                    "node_type": n.node_type,
                    "tool_name": n.tool_name,
                    "arguments": json.loads(n.arguments_json) if n.arguments_json else {},
                    "depends_on": json.loads(n.depends_on_json) if n.depends_on_json else [],
                    "priority": n.priority,
                    "status": n.status,
                    "result": n.result,
                    "error": n.error,
                    "started_at": n.started_at,
                    "completed_at": n.completed_at,
                }
                for n in nodes
            ],
        }


async def list_workflow_sessions(limit: int = 20) -> list[dict[str, Any]]:
    """列出最近的工作流会话（含任务统计聚合）"""
    async with get_async_session() as db:
        result = await db.execute(
            select(WorkflowSessionORM)
            .order_by(WorkflowSessionORM.created_at.desc())
            .limit(limit)
        )
        sessions = result.scalars().all()

        if not sessions:
            return []

        # 批量聚合节点统计（一次查询代替 N+1）
        session_ids = [s.session_id for s in sessions]
        stats_result = await db.execute(
            select(
                WorkflowNodeORM.session_id,
                func.count().label("total"),
                func.sum(func.cast(WorkflowNodeORM.status == "completed", Integer)).label("completed"),
                func.sum(func.cast(WorkflowNodeORM.status == "failed", Integer)).label("failed"),
            )
            .where(WorkflowNodeORM.session_id.in_(session_ids))
            .group_by(WorkflowNodeORM.session_id)
        )
        stats_map: dict[str, dict[str, int]] = {}
        for row in stats_result:
            stats_map[row.session_id] = {
                "total": row.total,
                "completed": row.completed or 0,
                "failed": row.failed or 0,
            }

        return [
            {
                "session_id": s.session_id,
                "user_message": s.user_message[:200],
                "mode": s.mode,
                "phase": s.phase,
                "created_at": s.created_at,
                "completed_at": s.completed_at,
                "stats": stats_map.get(s.session_id, {"total": 0, "completed": 0, "failed": 0}),
            }
            for s in sessions
        ]


# 终态 phase 集合（不再运行的会话）
_TERMINAL_PHASES = frozenset({"completed", "failed"})


async def cleanup_stale_sessions() -> int:
    """将陈旧的非终态会话标记为 failed（服务重启时调用）。

    Returns:
        被清理的会话数量。
    """
    async with get_async_session() as db:
        result = await db.execute(
            select(WorkflowSessionORM).where(
                WorkflowSessionORM.phase.notin_(list(_TERMINAL_PHASES))
            )
        )
        stale_sessions = result.scalars().all()
        if not stale_sessions:
            return 0

        now = utc_now()
        for s in stale_sessions:
            s.phase = "failed"
            s.error = "服务重启，会话中断"
            s.completed_at = now

        await db.flush()
        logger.info(f"[WorkflowPersistence] Cleaned up {len(stale_sessions)} stale sessions")
        return len(stale_sessions)
