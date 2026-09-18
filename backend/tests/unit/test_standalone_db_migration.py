"""standalone→Electron 跨库迁移复制逻辑单测。

历史 bug（审计 B1-1/P0）：手抄 tables_to_copy 漏掉 conversation_messages/
group_messages/memory_* 等表，换机迁移静默丢失全部聊天消息与记忆。
本文件验证：表清单从 ORM 元数据动态生成后，消息/记忆行随会话行一同迁移；
关键表复制失败时抛 RuntimeError（拒绝标记迁移完成）；源库缺新表不阻塞旧库迁移。
"""

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from app.infrastructure.database.base import Base
from app.infrastructure.database.migration import json_to_sqlite_migrator as migrator
from app.infrastructure.database.models import (
    Conversation,
    ConversationMessage,
    MemoryFact,
    MemoryVector,
    Provider,
)


@pytest.fixture()
def dst_engine(monkeypatch, tmp_path):
    """独立目标库（替换模块级 sync_session_factory），与真实 DATA_DIR 完全隔离。"""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'dst.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    monkeypatch.setattr(migrator, "sync_session_factory", sessionmaker(bind=engine, expire_on_commit=False))
    return engine


@pytest.fixture()
def standalone_db(tmp_path):
    """按完整 ORM schema 建源库并灌入最小样例数据（providers/conversations/消息/记忆）。"""
    db_path = tmp_path / "standalone.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        session.add(Provider(id="p1", name="Test"))
        session.add(Conversation(id="c1"))
        session.add(ConversationMessage(conversation_id="c1", mid="m1", role="user", content="你好"))
        session.add(ConversationMessage(conversation_id="c1", mid="m2", role="assistant", content="你好呀"))
        session.add(MemoryFact(id="f1", owner_key="local_default", content="用户喜欢简洁回复"))
        session.add(MemoryVector(fact_id="f1", owner_key="local_default", vector=b"\x00\x01"))
        session.commit()
    engine.dispose()
    return str(db_path)


def _dst_count(engine, table: str) -> int:
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()


def test_copies_messages_and_memory_tables(dst_engine, standalone_db):
    """消息行与记忆行必须随会话行一同迁移（历史 bug 直接丢这两类）。"""
    count = migrator._copy_standalone_db(standalone_db)

    assert count == 6  # providers 1 + conversations 1 + messages 2 + facts 1 + vectors 1
    assert _dst_count(dst_engine, "providers") == 1
    assert _dst_count(dst_engine, "conversations") == 1
    assert _dst_count(dst_engine, "conversation_messages") == 2
    assert _dst_count(dst_engine, "memory_facts") == 1
    assert _dst_count(dst_engine, "memory_vectors") == 1

    with dst_engine.connect() as conn:
        contents = {
            row[0]
            for row in conn.execute(text("SELECT content FROM conversation_messages WHERE conversation_id='c1'"))
        }
    assert contents == {"你好", "你好呀"}


def test_critical_copy_failure_raises_runtime_error(dst_engine, standalone_db):
    """关键表目标侧不可写时必须硬失败（拒绝产出半成品迁移）。"""
    with dst_engine.connect() as conn:
        conn.execute(text("DROP TABLE conversation_messages"))
        conn.commit()

    with pytest.raises(RuntimeError, match="conversation_messages"):
        migrator._copy_standalone_db(standalone_db)


def test_missing_source_critical_table_warns_but_succeeds(dst_engine, standalone_db):
    """旧版本源库没有 memory_vectors 表：警告但不阻塞其余数据迁移。"""
    import sqlite3

    conn = sqlite3.connect(standalone_db)
    try:
        conn.execute("DROP TABLE memory_vectors")
        conn.commit()
    finally:
        conn.close()

    count = migrator._copy_standalone_db(standalone_db)
    assert count == 5  # 缺 vectors 后剩 providers 1 + conversations 1 + messages 2 + facts 1
    assert _dst_count(dst_engine, "conversation_messages") == 2
