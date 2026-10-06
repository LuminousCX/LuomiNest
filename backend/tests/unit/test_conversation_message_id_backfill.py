"""conversation_messages 存量行持久 id 回填（链路审查 P1-6，SCHEMA v5）回归测试。

覆盖：
- _migrate_columns_sync：mid='' 行回填 uuid，并同步写回 data JSON 的 id 键
- data JSON 已有 id 的不一致行：复用该 id，mid 与 data.id 归一
- 正常行（mid 非空）不受影响
- 幂等：重复执行零命中，已回填 id 不变（WHERE mid='' 语义）

迁移测试自建临时引擎，不依赖 conftest 的全局临时库，不触碰真实 backend/data/。
"""
import asyncio
import json
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.infrastructure.database.base import Base
from app.infrastructure.database.engine import _migrate_columns_sync
from app.infrastructure.database.models import (  # noqa: F401 — 注册表到 Base metadata
    Conversation,
    ConversationMessage,
)


def _seed(sync_conn) -> None:
    """灌入一行会话 + 三种消息行：旧版无 id user 行 / 带 id 脏行 / 正常 assistant 行。"""
    sync_conn.execute(
        text(
            "INSERT INTO conversations (id, title, search_text, is_hidden, created_at, updated_at) "
            "VALUES ('c1', '遗留对话', '', 0, '2026-01-01T00:00:00', '2026-01-01T00:00:00')"
        )
    )
    sync_conn.execute(
        text(
            "INSERT INTO conversation_messages (conversation_id, mid, role, content, data, created_at) "
            "VALUES ('c1', '', 'user', '你好', :d1, '2026-01-01T00:00:01')"
        ),
        {"d1": json.dumps({"role": "user", "content": "你好"}, ensure_ascii=False)},
    )
    sync_conn.execute(
        text(
            "INSERT INTO conversation_messages (conversation_id, mid, role, content, data, created_at) "
            "VALUES ('c1', '', 'user', '带 id 脏行', :d2, '2026-01-01T00:00:02')"
        ),
        {"d2": json.dumps({"role": "user", "content": "带 id 脏行", "id": "legacy-id-1"}, ensure_ascii=False)},
    )
    sync_conn.execute(
        text(
            "INSERT INTO conversation_messages (conversation_id, mid, role, content, data, created_at) "
            "VALUES ('c1', 'assistant-1', 'assistant', '你好呀', :d3, '2026-01-01T00:00:03')"
        ),
        {"d3": json.dumps({"role": "assistant", "content": "你好呀", "id": "assistant-1"}, ensure_ascii=False)},
    )


def _load_rows(sync_conn):
    return sync_conn.execute(
        text("SELECT seq, mid, role, data FROM conversation_messages ORDER BY seq ASC")
    ).fetchall()


@pytest.mark.parametrize("runs", [1, 2])
def test_backfills_persistent_ids_and_idempotent(tmp_path, runs):
    """回填：无 id 行获得持久 uuid（data 同步写入同 id），带 id 脏行复用原 id；
    重复执行零命中（幂等），已回填 id 不变。"""
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'm1.db').as_posix()}")

    async def scenario():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(_seed)

        for _ in range(runs):
            async with engine.begin() as conn:
                await conn.run_sync(_migrate_columns_sync)

        def verify(sync_conn):
            rows = _load_rows(sync_conn)
            assert [r.role for r in rows] == ["user", "user", "assistant"]

            # 旧版无 id 行：mid 为合法 uuid，data JSON 写入同一 id（读路径带出）
            first_mid = rows[0].mid
            assert first_mid and first_mid != "legacy-id-1"
            uuid.UUID(first_mid)
            assert json.loads(rows[0].data)["id"] == first_mid

            # data 已有 id 的不一致行：复用原 id 归一，不另生成
            assert rows[1].mid == "legacy-id-1"
            assert json.loads(rows[1].data)["id"] == "legacy-id-1"

            # 正常行不受影响
            assert rows[2].mid == "assistant-1"
            assert json.loads(rows[2].data)["id"] == "assistant-1"

            # 重复执行后 id 稳定（幂等）
            if runs == 2:
                assert rows[0].mid == first_mid

        async with engine.begin() as conn:
            await conn.run_sync(verify)

    try:
        asyncio.run(scenario())
    finally:
        asyncio.run(engine.dispose())


def test_backfill_degrades_on_malformed_data_row(tmp_path):
    """data 列损坏（非法 JSON）的脏行：退化为仅回填 mid 列（读路径以 mid 兜底
    重建 id），其余正常行照常回填——单行脏数据不阻塞整体迁移。"""
    engine = create_async_engine(f"sqlite+aiosqlite:///{(tmp_path / 'm2.db').as_posix()}")

    async def scenario():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(_seed)
            # 破坏 data JSON（模拟异常行）
            await conn.execute(
                text("UPDATE conversation_messages SET data = 'not-json' WHERE seq = 1")
            )

        async with engine.begin() as conn:
            await conn.run_sync(_migrate_columns_sync)

        def verify(sync_conn):
            rows = _load_rows(sync_conn)
            # 脏行：mid 仍获得持久 uuid（data 保持原样，读路径兜底）
            assert rows[0].mid
            uuid.UUID(rows[0].mid)
            # 其余行正常回填
            assert rows[1].mid == "legacy-id-1"
            assert json.loads(rows[1].data)["id"] == "legacy-id-1"
            assert rows[2].mid == "assistant-1"

        async with engine.begin() as conn:
            await conn.run_sync(verify)

    try:
        asyncio.run(scenario())
    finally:
        asyncio.run(engine.dispose())
