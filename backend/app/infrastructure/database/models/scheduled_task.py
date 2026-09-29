"""ScheduledTask 模型 — 定时任务持久化。

存储 AI 创建或用户手动创建的定时任务，替代 scheduler 的 JSON 文件存储。
schedule_type 为遗留列（历史数据兼容），新数据以 trigger_type 为准区分 date/cron/interval：
- date：run_at 存 ISO 执行时间，schedule_cron 恒为空串（消除旧实现 "* * * * *" 幻象 cron）
- cron：schedule_cron 存五段 cron 表达式
- interval：interval_seconds 存间隔秒数
created_from 区分创建渠道：manual（用户手动）/ workflow（工作流 AI 创建）/ normal_chat（普通对话 AI 创建）。
origin_* 三列记录任务结果投递目标（P0-1 闭环）：web_conversation（origin_ref=conv_id）、
platform（origin_ref=instance_id:session_id）、api（无投递目标，结果仅留在任务记录）。
"""
from typing import Optional

from sqlalchemy import Boolean, Index, Integer, String, Text
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
    # ── P0-1 触发信息列（与遗留 schedule_type/schedule_cron 双轨，trigger_type 为权威） ──
    trigger_type: Mapped[str] = mapped_column(String(16), default="", index=True)
    run_at: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    interval_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # ── P0-1 结果投递来源 ──
    origin_kind: Mapped[str] = mapped_column(String(16), default="")
    origin_ref: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    origin_target: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    __table_args__ = (
        Index("ix_scheduled_tasks_active_created", "is_active", "created_at"),
    )
