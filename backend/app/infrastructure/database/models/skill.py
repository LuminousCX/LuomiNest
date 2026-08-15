"""Skill 模型 — CxSkill 持久化索引表（洋葱架构 §11.1 / §12.3）。

三层结构中的「持久化索引」层：
- 权威内容源：skills/{skill_id}/SKILL.md（文件系统）
- 持久化索引：本表（列表查询、启停状态、版本、路径、body_length、updated_at）
- 运行时缓存：luominest_skill_registry（内存热加载，供 prompt 注入与工具读取）

表结构以 onion-architecture.md §11.1 的 CREATE TABLE 为准。
文件为权威源：SkillLoader.load_all() 每次启动全量 upsert（§16.1 风险缓解），
表中与文件不一致的多余行由 loader 清理。
"""
from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class SkillORM(Base):
    __tablename__ = "skills"

    # kebab-case 技能 id（与 skills/{skill_id}/ 目录名一致）
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(64), default="")
    # JSON 数组（TEXT 存储，如 '["travel", "planning"]'）
    tags: Mapped[str] = mapped_column(Text, default="[]")
    # loaded | disabled | error
    status: Mapped[str] = mapped_column(String(16), default="loaded")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    source_path: Mapped[str] = mapped_column(String(512), default="")
    body_length: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[str] = mapped_column(String(64), default="")
