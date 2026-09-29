"""migrate_member_tracks 脚本回归：合成库上验证改键/改号/撞行跳过/FTS 重建。"""
import importlib.util
import sqlite3
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "migrate_member_tracks.py"
_spec = importlib.util.spec_from_file_location("migrate_member_tracks", _SCRIPT)
mt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mt)


def _make_db(tmp_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.executescript(
        """
        CREATE TABLE platform_instances (id TEXT PRIMARY KEY);
        CREATE TABLE memory_profiles (
            owner_key TEXT, conversation_id TEXT DEFAULT '', name TEXT DEFAULT '',
            static_facts TEXT DEFAULT '[]', dynamic_context TEXT DEFAULT '[]',
            distilled_turns INTEGER DEFAULT 0, updated_at TEXT DEFAULT '',
            PRIMARY KEY (owner_key, conversation_id));
        CREATE TABLE memory_facts (
            id TEXT PRIMARY KEY, owner_key TEXT, conversation_id TEXT DEFAULT '',
            content TEXT DEFAULT '', category TEXT DEFAULT 'context',
            confidence REAL DEFAULT 0.8, created_at TEXT DEFAULT '',
            source TEXT DEFAULT 'conversation', source_error TEXT DEFAULT '',
            expires_at TEXT, is_latest INTEGER DEFAULT 1, supersedes_id TEXT,
            source_conversation_id TEXT DEFAULT '', source_message TEXT DEFAULT '',
            history TEXT DEFAULT '[]', pinned INTEGER DEFAULT 0,
            scope TEXT DEFAULT 'global', group_id TEXT DEFAULT '');
        CREATE TABLE memory_summaries (
            owner_key TEXT, conversation_id TEXT DEFAULT '', section TEXT,
            summary TEXT DEFAULT '', updated_at TEXT DEFAULT '',
            PRIMARY KEY (owner_key, conversation_id, section));
        CREATE TABLE memory_knowledge (
            owner_key TEXT, conversation_id TEXT DEFAULT '', content TEXT DEFAULT '',
            updated_at TEXT DEFAULT '', PRIMARY KEY (owner_key, conversation_id));
        CREATE TABLE memory_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT, owner_key TEXT,
            conversation_id TEXT DEFAULT '', date TEXT DEFAULT '',
            created_at TEXT DEFAULT '', content TEXT DEFAULT '');
        CREATE TABLE memory_vectors (
            fact_id TEXT PRIMARY KEY, owner_key TEXT, content TEXT DEFAULT '',
            category TEXT DEFAULT '', scope TEXT DEFAULT '', conversation_id TEXT DEFAULT '',
            vector BLOB NOT NULL);
        CREATE VIRTUAL TABLE memory_facts_fts USING fts5(
            content, fact_id UNINDEXED, owner_key UNINDEXED, conversation_id UNINDEXED,
            tokenize='unicode61');
        INSERT INTO platform_instances VALUES ('inst1');
        """
    )
    return conn


def _seed(conn: sqlite3.Connection) -> None:
    old = "users:qq_onebot_inst1_10001"
    new = "users:qq_onebot_10001"
    # fact id 全表唯一主键：改 owner_key 不会撞 id；可能撞的是复合主键表
    conn.executemany(
        "INSERT INTO memory_facts (id, owner_key, content, scope, group_id) VALUES (?,?,?,?,?)",
        [
            ("fact_a", old, "群友A喜欢MC", "group", "g1"),
            ("fact_b", old, "群友B在群1", "group", "g1"),
        ],
    )
    conn.execute(
        "INSERT INTO memory_profiles (owner_key, conversation_id, name) VALUES (?, 'c1', '旧档案')",
        (old,),
    )
    conn.execute(
        "INSERT INTO memory_profiles (owner_key, conversation_id, name) VALUES (?, 'c1', '新档案已存在')",
        (new,),
    )
    conn.execute(
        "INSERT INTO memory_summaries (owner_key, conversation_id, section, summary) VALUES (?, 'c1', 'x', '旧摘要')",
        (old,),
    )
    conn.execute(
        "INSERT INTO memory_daily (owner_key, content) VALUES (?, '今日动态')", (old,)
    )
    conn.execute(
        "INSERT INTO memory_vectors (fact_id, owner_key, content, vector) VALUES ('fact_a', ?, 'v', x'00')",
        (old,),
    )
    conn.execute(
        "INSERT INTO memory_facts_fts (content, fact_id, owner_key, conversation_id) VALUES ('v', 'fact_a', ?, '')",
        (old,),
    )
    conn.commit()


def test_migrate_moves_and_merges(tmp_path: Path) -> None:
    conn = _make_db(tmp_path)
    _seed(conn)
    old = "users:qq_onebot_inst1_10001"
    new = "users:qq_onebot_10001"

    assert mt.migrate(conn, apply=False) == 0  # dry-run 不改库
    assert conn.execute(
        "SELECT COUNT(*) FROM memory_facts WHERE owner_key = ?", (old,)
    ).fetchone()[0] == 2

    mt.migrate(conn, apply=True)

    # facts：fact_a 原样改键；fact_b 撞 id 改号 fact_bm 并迁入统一轨
    assert conn.execute("SELECT COUNT(*) FROM memory_facts WHERE owner_key = ?", (old,)).fetchone()[0] == 0
    rows = {
        r[0]: r[1]
        for r in conn.execute("SELECT id, content FROM memory_facts WHERE owner_key = ?", (new,))
    }
    assert rows.get("fact_a") == "群友A喜欢MC"
    assert rows.get("fact_b") == "群友B在群1"
    # 复合主键撞行：旧 profiles 行保留原位（人工复核），未覆盖新行
    assert conn.execute("SELECT name FROM memory_profiles WHERE owner_key = ?", (new,)).fetchone()[0] == "新档案已存在"
    assert conn.execute("SELECT COUNT(*) FROM memory_profiles WHERE owner_key = ?", (old,)).fetchone()[0] == 1
    # summaries 无撞行 → 正常迁入统一轨
    assert conn.execute("SELECT COUNT(*) FROM memory_summaries WHERE owner_key = ?", (old,)).fetchone()[0] == 0
    assert conn.execute("SELECT summary FROM memory_summaries WHERE owner_key = ?", (new,)).fetchone()[0] == "旧摘要"
    # daily 无复合主键 → 直接改键
    assert conn.execute("SELECT content FROM memory_daily WHERE owner_key = ?", (new,)).fetchone()[0] == "今日动态"
    # vectors 随 fact_a 改键
    assert conn.execute("SELECT owner_key FROM memory_vectors WHERE fact_id='fact_a'").fetchone()[0] == new
    # FTS 重建行指向新键
    assert conn.execute(
        "SELECT owner_key FROM memory_facts_fts WHERE fact_id='fact_a'"
    ).fetchone()[0] == new


def test_split_old_key_requires_known_instance(tmp_path: Path) -> None:
    conn = _make_db(tmp_path)
    assert mt.split_old_key("users:qq_onebot_ghost_1", []) is None
    assert mt.split_old_key("owner:main", ["inst1"]) is None
    conn.close()
