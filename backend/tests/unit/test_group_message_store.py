"""群聊消息拆表（groups.messages JSON 列 → group_messages 独立表）回归测试。

覆盖：
- engine._migrate_columns_sync 存量回填：行数幂等（重复启动不重复导入）、
  回填失败保留旧列、成功后 DROP 旧列
- GroupRepository 消息读写：追加走新表（单行 INSERT）、读取与拆表前
  同构（camelCase/snake_case 键风格原样保留）、limit 取最新 N 条
- GroupChatManager._build_recent_context 兼容两种键风格

迁移测试自建临时引擎（不依赖 conftest 的全局临时库）；
仓储测试 patch 掉模块内 session 工厂，均不触碰真实 backend/data/。
"""
import asyncio
import json

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.database.base import Base
from app.infrastructure.database.engine import _migrate_columns_sync
from app.infrastructure.database.repositories.group_repository import GroupRepository

# 模拟旧库 groups.messages JSON（camelCase 与 snake_case 键风格混存，与存量一致）
LEGACY_MESSAGES = [
    {"id": "m1", "sender_id": "user", "sender_type": "user", "content": "早", "timestamp": "2026-01-01T00:00:01"},
    {"id": "m2", "senderId": "a1", "senderName": "洛米", "senderType": "agent", "content": "早呀",
     "timestamp": "2026-01-01T00:00:02", "role": "管家"},
    {"id": "m3", "sender_id": "user", "sender_type": "user", "content": "在吗", "timestamp": ""},
    {"id": "m4", "sender_id": "user", "sender_type": "user", "content": "无时间戳"},
]
LEGACY_UPDATED_AT = "2026-01-01T00:00:05"


def _seed_groups(sync_conn) -> None:
    """建群组行（不含 messages 列，新模型 schema）。"""
    sync_conn.execute(
        text("INSERT INTO groups (id, name, description, type, members, created_at, updated_at) "
             "VALUES ('g-legacy', '遗留群', '', 'mixed', '[]', '2026-01-01T00:00:00', :updated)"),
        {"updated": LEGACY_UPDATED_AT},
    )
    sync_conn.execute(
        text("INSERT INTO groups (id, name, description, type, members, created_at, updated_at) "
             "VALUES ('g-empty', '空群', '', 'mixed', '[]', '2026-01-01T00:00:00', '2026-01-01T00:00:00')"),
    )


def _readd_legacy_column(sync_conn) -> None:
    """补出旧版 messages JSON 列并写入 legacy 数据（模拟旧库，或 DROP 失败后旧列仍在的库）。"""
    sync_conn.execute(text("ALTER TABLE groups ADD COLUMN messages JSON"))
    sync_conn.execute(
        text("UPDATE groups SET messages = :msgs WHERE id = 'g-legacy'"),
        {"msgs": json.dumps(LEGACY_MESSAGES, ensure_ascii=False)},
    )


def _group_columns(sync_conn) -> set:
    return {c["name"] for c in inspect(sync_conn).get_columns("groups")}


def test_backfill_imports_and_drops_legacy_column(tmp_path):
    """回填：legacy JSON 逐行导入新表（字段/顺序/键风格保持），成功后 DROP 旧列。"""
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'm1.db').as_posix()}")

    async def scenario():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(_seed_groups)
            await conn.run_sync(_readd_legacy_column)

        async with engine.begin() as conn:
            await conn.run_sync(_migrate_columns_sync)

        def verify(sync_conn):
            rows = sync_conn.execute(
                text("SELECT seq, group_id, mid, sender_type, content, data, created_at "
                     "FROM group_messages ORDER BY seq ASC")
            ).fetchall()
            # 消息逐行导入，顺序与旧 JSON 数组一致
            assert [r.mid for r in rows] == ["m1", "m2", "m3", "m4"]
            assert all(r.group_id == "g-legacy" for r in rows)
            assert [r.sender_type for r in rows] == ["user", "agent", "user", "user"]
            assert [r.content for r in rows] == ["早", "早呀", "在吗", "无时间戳"]
            # data 列与旧消息 dict 完全同构（键风格原样保留）
            for r, legacy in zip(rows, LEGACY_MESSAGES):
                assert json.loads(r.data) == legacy
            # created_at 取消息自身 timestamp；键缺失时回退群组 updated_at
            assert rows[0].created_at == "2026-01-01T00:00:01"
            assert rows[1].created_at == "2026-01-01T00:00:02"
            assert rows[2].created_at == ""
            assert rows[3].created_at == LEGACY_UPDATED_AT
            # 回填成功后旧列已 DROP；空消息群组不产生行
            assert "messages" not in _group_columns(sync_conn)
            assert sync_conn.execute(text("SELECT COUNT(*) FROM group_messages")).scalar() == 4

        async with engine.begin() as conn:
            await conn.run_sync(verify)

    try:
        asyncio.run(scenario())
    finally:
        asyncio.run(engine.dispose())


def test_backfill_idempotent_on_rerun(tmp_path):
    """幂等：消息表已有行 → 不重复导入（即使旧列仍存在，模拟 DROP 失败的库）。

    版本门语义下迁移重跑只发生在未来版本号变更时，故二次迁移前重置 user_version
    模拟"新版本再次触发迁移"。
    """
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'm2.db').as_posix()}")

    async def scenario():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(_seed_groups)
            await conn.run_sync(_readd_legacy_column)
        async with engine.begin() as conn:
            await conn.run_sync(_migrate_columns_sync)

        # 模拟旧 SQLite（<3.35）DROP 失败：旧列仍在且带着同样的 legacy 数据
        async with engine.begin() as conn:
            await conn.run_sync(_readd_legacy_column)

        # 重置版本号：模拟未来 schema 版本变更重新触发迁移
        async with engine.begin() as conn:
            await conn.exec_driver_sql("PRAGMA user_version=0")

        async with engine.begin() as conn:
            await conn.run_sync(_migrate_columns_sync)

        def verify(sync_conn):
            count = sync_conn.execute(text("SELECT COUNT(*) FROM group_messages")).scalar()
            assert count == 4  # 不重复导入
            assert "messages" not in _group_columns(sync_conn)

        async with engine.begin() as conn:
            await conn.run_sync(verify)

    try:
        asyncio.run(scenario())
    finally:
        asyncio.run(engine.dispose())


def test_backfill_failure_keeps_legacy_column(tmp_path):
    """安全：回填失败（此处以缺列的消息表触发）时保留旧 messages 列，数据不丢。"""
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'm3.db').as_posix()}")

    async def scenario():
        # 先手工建一张缺列的 group_messages 占位（create_all 跳过已存在表）→ 回填 INSERT 必然失败
        async with engine.begin() as conn:
            await conn.exec_driver_sql(
                "CREATE TABLE group_messages (seq INTEGER PRIMARY KEY AUTOINCREMENT, group_id VARCHAR(64) NOT NULL)"
            )
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(_seed_groups)
            await conn.run_sync(_readd_legacy_column)

        async with engine.begin() as conn:
            await conn.run_sync(_migrate_columns_sync)

        def verify(sync_conn):
            # 回填失败：旧列保留，可人工恢复；消息表无脏数据
            assert "messages" in _group_columns(sync_conn)
            count = sync_conn.execute(text("SELECT COUNT(*) FROM group_messages")).scalar()
            assert count == 0

        async with engine.begin() as conn:
            await conn.run_sync(verify)

    try:
        asyncio.run(scenario())
    finally:
        asyncio.run(engine.dispose())


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """GroupRepository + 指向临时库的 session 工厂（不触碰全局临时库/真实库）。

    BaseRepository 的继承方法（delete/update/mutate 等）引用 base 模块内的
    工厂名，需与 group_repository 模块内名称一并 patch。
    """
    engine = create_engine(f"sqlite:///{(tmp_path / 'repo.db').as_posix()}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(
        "app.infrastructure.database.repositories.group_repository.sync_session_factory", factory
    )
    monkeypatch.setattr(
        "app.infrastructure.database.repositories.base.sync_session_factory", factory
    )
    yield GroupRepository()
    engine.dispose()


def test_append_message_writes_new_table(repo):
    """新消息写入走 group_messages 独立表（模型已无 messages 列可写）。"""
    repo.save("g1", {"name": "测试群", "members": [], "messages": [], "created_at": "t0", "updated_at": "t0"})
    assert repo.append_message("g1", {"id": "m1", "sender_id": "user", "sender_type": "user",
                                      "content": "你好", "timestamp": "2026-01-01T00:00:01"}) is True
    assert repo.append_message("g1", {"id": "m2", "senderId": "a1", "senderType": "agent", "senderName": "洛米",
                                      "content": "你好呀", "timestamp": "2026-01-01T00:00:02", "role": "管家"}) is True
    # 群组不存在 → 不写入
    assert repo.append_message("nope", {"id": "mx", "content": "x"}) is False


def test_read_back_matches_pre_split_behavior(repo):
    """读取行为与拆表前一致：get/get_all 返回同构 messages，键风格原样保留。"""
    legacy = [
        {"id": "m1", "sender_id": "user", "sender_type": "user", "content": "早", "timestamp": "2026-01-01T00:00:01"},
        {"id": "m2", "senderId": "a1", "senderName": "洛米", "senderType": "agent", "content": "早呀",
         "timestamp": "2026-01-01T00:00:02", "role": "管家"},
    ]
    repo.save("g1", {"name": "测试群", "members": [{"agent_id": "a1", "type": "agent"}],
                     "messages": legacy, "created_at": "t0", "updated_at": "t1"})

    g = repo.get("g1")
    assert g["messages"] == legacy  # 与旧 JSON 列读回的元素完全同构、保序

    all_groups = repo.get_all()
    assert len(all_groups) == 1
    assert all_groups[0]["messages"] == legacy

    # 空群组读回空列表（而非缺键）
    repo.save("g2", {"name": "空群", "members": []})
    assert repo.get("g2")["messages"] == []


def test_get_messages_limit_returns_latest_window(repo):
    """limit 语义：取最新 N 条，仍按时间正序返回（供近期上下文构建）。"""
    repo.save("g1", {"name": "群", "members": []})
    for i in range(5):
        repo.append_message("g1", {"id": f"m{i}", "sender_id": "user", "sender_type": "user",
                                   "content": f"msg{i}", "timestamp": f"2026-01-01T00:00:0{i}"})
    recent = repo.get_messages("g1", limit=3)
    assert [m["id"] for m in recent] == ["m2", "m3", "m4"]
    assert [m["content"] for m in recent] == ["msg2", "msg3", "msg4"]


def test_save_round_trip_and_metadata_only_save(repo):
    """save 携带 messages 键为全量替换（整体回写语义）；不携带则不触碰消息行。"""
    repo.save("g1", {"name": "群", "members": [], "messages": [{"id": "m1", "content": "a"}]})
    # 成员变更（冷路径）：整组回写，消息行重建但内容不变
    repo.save("g1", {"name": "群2", "members": [{"agent_id": "a1"}],
                     "messages": [{"id": "m1", "content": "a"}, {"id": "m2", "content": "b"}]})
    assert [m["id"] for m in repo.get("g1")["messages"]] == ["m1", "m2"]

    # 元数据-only 保存：不携带 messages 键 → 消息行不被误清
    meta_only = dict(repo.get("g1"))
    meta_only.pop("messages")
    meta_only["name"] = "群3"
    repo.save("g1", meta_only)
    assert [m["id"] for m in repo.get("g1")["messages"]] == ["m1", "m2"]
    assert repo.get("g1")["name"] == "群3"


def test_append_updates_group_timestamp(repo):
    """追加消息时群组 updated_at 取消息时间戳（与拆表前 group['updated_at']=now 语义一致）。"""
    repo.save("g1", {"name": "群", "members": [], "updated_at": "old"})
    repo.append_message("g1", {"id": "m1", "sender_id": "user", "sender_type": "user",
                               "content": "hi", "timestamp": "2026-01-01T00:09:00"})
    assert repo.get_meta("g1")["updated_at"] == "2026-01-01T00:09:00"


def test_group_delete_cascades_messages(repo):
    """群组删除 → 消息行由 FK ON DELETE CASCADE 级联清理（不留孤儿行）。"""
    repo.save("g1", {"name": "群", "members": []})
    repo.append_message("g1", {"id": "m1", "sender_id": "user", "sender_type": "user",
                               "content": "hi", "timestamp": "t"})
    assert repo.delete("g1") is True
    assert repo.get_messages("g1") == []


def test_build_recent_context_compat_styles():
    """近期上下文构建：camelCase 与 snake_case 消息格式均兼容（拆表前行为）。"""
    from app.domains.social.group_chat import GroupChatManager

    messages = [
        {"id": "m1", "sender_id": "user", "sender_type": "user", "content": "早"},
        {"id": "m2", "senderId": "a1", "senderName": "洛米", "senderType": "agent", "content": "早呀"},
        {"id": "m3", "sender_type": "agent", "content": "无名字"},
    ]
    ctx = GroupChatManager._build_recent_context(messages)
    assert ctx == "用户: 早\n洛米: 早呀\nAgent: 无名字"
    assert GroupChatManager._build_recent_context([]) == ""
    # 只取最近 N 条
    ctx2 = GroupChatManager._build_recent_context(messages, max_messages=2)
    assert ctx2 == "洛米: 早呀\nAgent: 无名字"
