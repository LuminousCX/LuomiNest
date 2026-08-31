"""WorkflowTemplate ORM 模型 — 工作流模板持久化。

存储可复用的工作流计划模板，支持：
- plan_json：JSON 序列化的执行计划，可含 {{param}} 占位符
- parameters_schema：JSON Schema 声明占位符列表、默认值与类型
- auto_approve：免审批直接执行标志
- 可绑定定时任务自动执行

表名: workflow_templates
"""
from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class WorkflowTemplateORM(Base):
    __tablename__ = "workflow_templates"

    template_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    plan_json: Mapped[str] = mapped_column(Text, default="{}")              # JSON 序列化的 WorkflowPlanJSON
    parameters_schema: Mapped[str] = mapped_column(Text, default="{}")      # JSON Schema: {{param}} 占位符列表 + 默认值/类型
    auto_approve: Mapped[int] = mapped_column(Integer, default=0)           # 1=免审批直接执行
    created_from: Mapped[str] = mapped_column(String(16), default="user")   # 'user' / 'ai'
    source_session_id: Mapped[str] = mapped_column(String(64), default="")  # 来源会话 ID
    created_at: Mapped[str] = mapped_column(String(64), default="", index=True)
    updated_at: Mapped[str] = mapped_column(String(64), default="")

    __table_args__ = (
        Index("ix_workflow_templates_updated", "updated_at"),
    )
