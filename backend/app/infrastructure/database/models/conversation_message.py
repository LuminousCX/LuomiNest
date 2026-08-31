"""ConversationMessage 模型 — 对话消息独立表（替代 conversations.messages JSON 列）。

背景（前端后端项目锐评 · 高优先级 #1）：
- 旧方案把整段 messages 存为 conversations.messages JSON 列，每次追加都是
  「读全量 → append → 写全量」的写放大，search_text 每次全量重算 O(n)，
  分页也是 Python 层切片。
- 本表把每条消息拆为一行（seq 自增主键），追加消息 = 单条 INSERT，
  search_text/last_message 增量维护，分页走 SQL 层 LIMIT/OFFSET（keyset）。

设计要点：
- ``data`` JSON 列保存消息的完整原始 dict（role/content/id/versions/file_* 等
  任意字段），保证与旧 messages 列表的元素完全同构，读回时无需重建字段。
- ``mid/role/content`` 为索引列，支撑分页游标（mid → seq）与后续 FTS5
  全文索引扩展点（content 列）。
- conversation_id 声明外键 + ON DELETE CASCADE：conversations 永久删除时
  消息行由 SQLite 级联清理（engine PRAGMA foreign_keys=ON 已开启）。
"""
from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    # 全局自增序号：同时作为分页 keyset 游标（稳定、单调递增）
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 消息 id（assistant 消息为 uuid，user 消息可能为空字符串）
    mid: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    # 纯文本内容（供搜索/FTS5 扩展点；与 data 中的 content 保持一致）
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # 完整消息 dict（与旧 messages 列表元素同构）
    data: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    # 入库时间（ISO 字符串，便于审计与排序展示）
    created_at: Mapped[str] = mapped_column(String(64), default="")


# (conversation_id, seq) 复合索引：分页查询与级联删除的主路径
Index("ix_conversation_messages_conv_seq", ConversationMessage.conversation_id, ConversationMessage.seq)
# mid 索引：before_id 分页游标解析（id → seq）
Index("ix_conversation_messages_conv_mid", ConversationMessage.conversation_id, ConversationMessage.mid)
