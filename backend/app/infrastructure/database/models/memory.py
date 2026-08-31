"""记忆系统 + 向量索引的 ORM 模型（SQLite 单库）。

背景（前端后端项目锐评 · 高优先级 #2/#3）：
- 旧实现把记忆（memory.json / knowledge.md / daily/*.md）与向量
  （vectors.npz + vectors_meta.json）全部放在 SQLite 之外的文件体系里：
  无事务、不随 DB 一起备份、append_daily 每次读-改-写整文件、
  向量每次全量重写 npz。
- 重构后全部入同一个 luominest.db：单库 = 单备份单元，写操作单事务，
  append_daily 退化为单行 INSERT，向量按行存 BLOB、增量写。

隔离模型（洋葱架构 §8.5.2 双轨，用户强调"主人记忆 vs 平台用户记忆"区分）：
- ``owner_key`` 为行级隔离键：
  - 主人轨道  ``owner:{agent_key}``（agents/{key} 目录）
  - 平台用户轨 ``users:{user_key}``（users/{user_key} 目录，私聊/群聊提取的记忆）
  - 测试/临时目录 ``tmp:{sha1}``（独立 SQLite 文件，互不串扰）
- ``conversation_id`` 空串表示 Agent/主人级（全局）记忆；
  非空表示对话级记忆（facts/summaries/daily 的会话级隔离）。
"""
from typing import Optional

from sqlalchemy import BLOB, Float, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class MemoryProfile(Base):
    """记忆档案（每 owner_key + conversation_id 一行）。"""

    __tablename__ = "memory_profiles"

    owner_key: Mapped[str] = mapped_column(String(160), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(64), primary_key=True, default="")
    name: Mapped[str] = mapped_column(String(256), default="")
    # 静态事实 / 动态上下文（JSON 列表，对应 ProfileData.static_facts / dynamic_context）
    static_facts: Mapped[list] = mapped_column(JSON, default=list)
    dynamic_context: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[str] = mapped_column(String(64), default="")


class MemoryFact(Base):
    """记忆事实（对应 FactItem，一行一条；历史版本归档存 history JSON）。"""

    __tablename__ = "memory_facts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_key: Mapped[str] = mapped_column(String(160), nullable=False)
    conversation_id: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(32), default="context")
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    created_at: Mapped[str] = mapped_column(String(64), default="")
    source: Mapped[str] = mapped_column(String(32), default="conversation")
    source_error: Mapped[str] = mapped_column(String(64), default="")
    expires_at: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_latest: Mapped[int] = mapped_column(Integer, default=1)
    supersedes_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_conversation_id: Mapped[str] = mapped_column(String(64), default="")
    source_message: Mapped[str] = mapped_column(Text, default="")
    # 版本归档（ArchivedFact 列表的 JSON 序列化）
    history: Mapped[list] = mapped_column(JSON, default=list)


Index(
    "ix_memory_facts_owner_conv",
    MemoryFact.owner_key,
    MemoryFact.conversation_id,
    MemoryFact.is_latest,
)


class MemorySummary(Base):
    """记忆摘要分区（对应 SummaryData 的五个 section）。"""

    __tablename__ = "memory_summaries"

    owner_key: Mapped[str] = mapped_column(String(160), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(64), primary_key=True, default="")
    section: Mapped[str] = mapped_column(String(32), primary_key=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="")


class MemoryKnowledge(Base):
    """知识库（每 owner_key + conversation_id 一行；knowledge.md 的 SQLite 视图）。"""

    __tablename__ = "memory_knowledge"

    owner_key: Mapped[str] = mapped_column(String(160), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(64), primary_key=True, default="")
    content: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="")


class MemoryDaily(Base):
    """每日记录（行式追加：append_daily 退化为单行 INSERT，替代读-改-写整文件）。"""

    __tablename__ = "memory_daily"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_key: Mapped[str] = mapped_column(String(160), nullable=False)
    conversation_id: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    date: Mapped[str] = mapped_column(String(16), default="", nullable=False)  # YYYY-MM-DD
    created_at: Mapped[str] = mapped_column(String(64), default="")  # 当日 HH:MM 或完整时间
    content: Mapped[str] = mapped_column(Text, default="")


Index("ix_memory_daily_owner_date", MemoryDaily.owner_key, MemoryDaily.conversation_id, MemoryDaily.date)


class MemoryVector(Base):
    """向量索引（SQLite BLOB 按行存储，替代 vectors.npz 全量重写）。"""

    __tablename__ = "memory_vectors"

    fact_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_key: Mapped[str] = mapped_column(String(160), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(32), default="")
    scope: Mapped[str] = mapped_column(String(32), default="")
    conversation_id: Mapped[str] = mapped_column(String(64), default="")
    # float32 向量的原始字节（np.ndarray.tobytes()）
    vector: Mapped[bytes] = mapped_column(BLOB, nullable=False)


Index(
    "ix_memory_vectors_owner",
    MemoryVector.owner_key,
    MemoryVector.category,
    MemoryVector.scope,
    MemoryVector.conversation_id,
)
