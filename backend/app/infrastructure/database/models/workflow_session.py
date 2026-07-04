"""WorkflowSession 模型 — 工作流会话持久化。

存储主 Agent 长任务工作流的完整会话状态，替代 engine.py 的内存 _active_sessions 字典。
plan_json 存储完整 JSON 计划（含 analysis/plan/tasks），便于历史回溯与流程图重建。
"""
from typing import Optional

from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class WorkflowSessionORM(Base):
    __tablename__ = "workflow_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_message: Mapped[str] = mapped_column(Text, default="")
    mode: Mapped[str] = mapped_column(String(16), default="standard", index=True)
    phase: Mapped[str] = mapped_column(String(32), default="analyzing")
    analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    plan_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    final_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    conversation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[str] = mapped_column(String(64), default="", index=True)
    completed_at: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_workflow_sessions_mode_created", "mode", "created_at"),
    )
