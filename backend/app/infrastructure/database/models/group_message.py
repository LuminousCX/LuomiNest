"""GroupMessage 模型 — 群聊消息独立表（替代 groups.messages JSON 列）。

背景（前端后端项目锐评 · 高优先级 #1）：
- 旧方案把整段消息存为 groups.messages JSON 列，每追加一条消息都要
  「读全量 → append → 序列化整个历史 → 写全量」，写放大随群聊历史线性增长。
- 本表把每条消息拆为一行（seq 自增主键），追加消息 = 单条 INSERT，
  最近上下文/历史读取走 SQL 层 ORDER BY seq。

设计要点（与 conversation_messages 同款）：
- ``data`` JSON 列保存消息的完整原始 dict（sender_id / sender_type /
  sender_name / content / role / timestamp 等任意字段），保证与旧 messages
  列表的元素完全同构，读回时无需重建字段（存量消息存在 camelCase 与
  snake_case 两种键风格，原样保留不归一）。
- ``mid / sender_type / content`` 为索引列，支撑游标解析与后续 FTS5
  全文索引扩展点（content 列）。
- group_id 声明外键 + ON DELETE CASCADE：群组删除时消息行由 SQLite
  级联清理（engine PRAGMA foreign_keys=ON 已开启；回填 INSERT...SELECT
  仅从 groups 行取数，不会产生孤儿行挡外键）。
"""
from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class GroupMessage(Base):
    __tablename__ = "group_messages"

    # 全局自增序号：同时作为分页/最近上下文读取的 keyset 游标（稳定、单调递增）
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 消息 id（uuid）
    mid: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    # 发送者类型（user | agent），等效 conversation_messages 的 role 列
    sender_type: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    # 纯文本内容（供搜索/FTS5 扩展点；与 data 中的 content 保持一致）
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # 完整消息 dict（与旧 messages 列表元素同构）
    data: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    # 消息时间戳（ISO 字符串，取自消息自身的 timestamp 字段，便于审计与排序展示）
    created_at: Mapped[str] = mapped_column(String(64), default="")


# (group_id, seq) 复合索引：历史/最近上下文查询与级联删除的主路径
Index("ix_group_messages_group_seq", GroupMessage.group_id, GroupMessage.seq)
# mid 索引：按消息 id 定位游标（id → seq）
Index("ix_group_messages_group_mid", GroupMessage.group_id, GroupMessage.mid)
