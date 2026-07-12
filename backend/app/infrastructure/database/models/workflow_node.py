"""WorkflowNode 模型 — 工作流节点持久化。

存储工作流会话中每个子任务（节点）的执行状态与结果。
node_type 用于前端流程图渲染分类（input/agent/tool/condition/output）。
depends_on_json 存储 JSON 数组，记录节点间依赖关系。
"""
from typing import Optional

from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class WorkflowNodeORM(Base):
    __tablename__ = "workflow_nodes"

    node_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(256), default="")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    node_type: Mapped[str] = mapped_column(String(32), default="tool")
    tool_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    arguments_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    depends_on_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    completed_at: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_workflow_nodes_session_status", "session_id", "status"),
    )
