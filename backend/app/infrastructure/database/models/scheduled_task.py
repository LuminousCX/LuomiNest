"""ScheduledTask 模型 — 定时任务持久化。

存储 AI 创建或用户手动创建的定时任务，替代 scheduler 的 JSON 文件存储。
schedule_type 区分 cron/interval/once 三种调度类型。
created_from 区分来源：manual（用户手动）/ workflow（工作流 AI 创建）/ normal_chat（普通对话 AI 创建）。
"""
from typing import Optional

from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class ScheduledTaskORM(Base):
    __tablename__ = "scheduled_tasks"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    schedule_cron: Mapped[str] = mapped_column(String(128), default="")
    schedule_type: Mapped[str] = mapped_column(String(16), default="cron")
    action: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_from: Mapped[str] = mapped_column(String(16), default="manual", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(String(64), default="", index=True)
    last_run_at: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_scheduled_tasks_active_created", "is_active", "created_at"),
    )
