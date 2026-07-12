"""ToolCallRecord 模型 — 工具调用记录持久化。

存储工作流与普通对话中工具调用的完整记录，用于：
1. 工具结果落盘：超阈值结果存数据库，LLM 上下文用占位符替换（借鉴 claude-code-src）
2. 执行审计：记录每次工具调用的参数、结果、耗时、成功状态
3. 控制台日志：前端 ConsoleView 展示工具调用历史
"""
from typing import Optional

from sqlalchemy import Boolean, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class ToolCallRecordORM(Base):
    __tablename__ = "tool_call_records"

    record_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    conversation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    tool_name: Mapped[str] = mapped_column(String(128), default="", index=True)
    arguments_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(64), default="", index=True)

    __table_args__ = (
        Index("ix_tool_call_records_session_created", "session_id", "created_at"),
    )
