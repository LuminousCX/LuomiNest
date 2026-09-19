"""SQLAlchemy 双引擎与数据库初始化。

设计要点：
- async_engine（aiosqlite）：运行时 FastAPI 路由使用
- sync_engine（sqlite3）：模块加载阶段（如 adapter import）需要同步访问时使用
- 两引擎指向同一 .db 文件，依赖 SQLite WAL 模式支持并发读写
- 每个新连接自动执行 PRAGMA（journal_mode=WAL / synchronous=NORMAL / foreign_keys=ON）
- 列迁移以 PRAGMA user_version 做版本门（SCHEMA_VERSION）：已达标直接跳过，
  避免每次启动重跑存量数据操作；配合跨进程文件锁消除双实例并发启动竞态
"""
import asyncio
import contextlib
import os
from pathlib import Path

from loguru import logger
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import settings
from app.infrastructure.database.base import Base

# 列迁移 schema 版本：_migrate_columns_sync 内新增任何列/回填/索引逻辑时必须 +1，
# 否则已达标旧库会跳过新迁移。旧库首次升级（user_version=0）会完整执行一遍并回写。
SCHEMA_VERSION = 3


@contextlib.contextmanager
def _db_init_file_lock():
    """跨进程启动单飞锁：双实例并发 init_db 时串行化（Windows msvcrt / POSIX flock）。

    后到者最多阻塞约 10s（Windows LK_LOCK 语义）后抛 OSError，由调用方 fail-fast；
    崩溃残留锁随进程句柄释放，无需处理陈旧锁。
    """
    lock_path = Path(settings.DATA_DIR) / "db_init.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.ExitStack() as stack:
        lock_file = stack.enter_context(open(lock_path, "a+"))
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            lock_file.seek(0)
            with contextlib.suppress(OSError):
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _make_sync_url(async_url: str) -> str:
    """从 async SQLite URL 派生 sync URL（去除 +aiosqlite driver 标记）。"""
    if "+aiosqlite" in async_url:
        return async_url.replace("+aiosqlite", "")
    return async_url


# SQLite 连接参数：timeout 等待写锁，check_same_thread 允许跨线程使用
_CONNECT_ARGS = {"timeout": 30, "check_same_thread": False}

# 双引擎：async 供 FastAPI 运行时，sync 供模块加载阶段同步访问
async_engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    connect_args=_CONNECT_ARGS,
    echo=False,
)

sync_engine = create_engine(
    _make_sync_url(settings.DATABASE_URL),
    connect_args=_CONNECT_ARGS,
    echo=False,
)


def _apply_sqlite_pragmas(dbapi_conn, connection_record) -> None:
    """每个新连接执行 PRAGMA。

    journal_mode=WAL 持久化于数据库文件（设一次即可保持），
    synchronous=NORMAL 与 foreign_keys=ON 为每连接生效，需在每次连接时设置。
    """
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# 在两引擎的连接池上注册 PRAGMA（async_engine 通过其内部 sync_engine 暴露 connect 事件）
event.listen(sync_engine, "connect", _apply_sqlite_pragmas)
event.listen(async_engine.sync_engine, "connect", _apply_sqlite_pragmas)


async def init_db() -> None:
    """初始化数据库：创建所有表（幂等，已存在的表不会重建）+ 列迁移。

    应在应用 lifespan 启动时调用一次。
    建表与迁移整体持有跨进程文件锁：双实例并发启动时串行执行，
    后到实例读到已升级的 user_version 后直接跳过迁移。
    """
    # 显式导入所有模型，确保 Base.metadata 注册完整（不依赖调用方的导入顺序）
    from app.infrastructure.database import models  # noqa: F401

    def _init_locked() -> None:
        with _db_init_file_lock(), sync_engine.begin() as sync_conn:
            Base.metadata.create_all(sync_conn)
            _migrate_columns_sync(sync_conn)

    await asyncio.to_thread(_init_locked)
    logger.success(f"[DB] Database initialized at {settings.DATABASE_URL}")


def _migrate_columns_sync(sync_conn) -> None:
    """为已有表添加缺失列（SQLite ALTER TABLE ADD COLUMN，幂等，带 schema 版本门）。

    另负责消息 JSON 列 → 独立消息表的存量回填（前端后端项目锐评 · 高优先级 #1）：
    1. conversation_messages / group_messages 表由 create_all 新建（含 FK + 索引）；
    2. 若旧库 conversations / groups 仍带 messages JSON 列且消息表为空 → 逐行回填；
    3. 回填成功后 DROP 旧列（SQLite 3.35+ 支持），避免双写不一致。

    user_version >= SCHEMA_VERSION 时直接返回：消除每次启动重跑存量 UPDATE 的浪费，
    以及 check-then-act 迁移在双实例并发启动下的竞态窗口。
    """
    from sqlalchemy import text, inspect

    applied = sync_conn.execute(text("PRAGMA user_version")).scalar() or 0
    if applied >= SCHEMA_VERSION:
        return

    backfill_failed = False  # 存量回填失败时不回写版本号，下次启动重试

    def _alter_safe(ddl: str, desc: str) -> None:
        """单条迁移兜底容错：双实例极端并发下列/索引已被对方添加时视为成功。"""
        try:
            sync_conn.execute(text(ddl))
            logger.info(f"[DB] Migrated: {desc}")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                logger.debug(f"[DB] Migration step already applied by concurrent startup, skipped: {desc}")
            else:
                raise

    inspector = inspect(sync_conn)

    # ── 消息独立表回填（旧库） ──
    if "conversations" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("conversations")}
        if "conversation_messages" in inspector.get_table_names() and "messages" in existing_cols:
            msg_count = sync_conn.execute(
                text("SELECT COUNT(*) FROM conversation_messages")
            ).scalar() or 0
            backfill_ok = msg_count > 0  # 已有行视为已回填（幂等）
            if msg_count == 0:
                try:
                    sync_conn.execute(
                        text(
                            """
                            INSERT INTO conversation_messages
                                (conversation_id, mid, role, content, data, created_at)
                            SELECT c.id,
                                   COALESCE(json_extract(value, '$.id'), ''),
                                   COALESCE(json_extract(value, '$.role'), ''),
                                   COALESCE(json_extract(value, '$.content'), ''),
                                   value,
                                   COALESCE(c.updated_at, '')
                            FROM conversations c, json_each(c.messages)
                            WHERE c.messages IS NOT NULL AND c.messages != '[]'
                            """
                        )
                    )
                    # 回填后按消息行重建 search_text / last_message（旧列值可能缺失/过期）
                    sync_conn.execute(
                        text(
                            """
                            UPDATE conversations SET
                              search_text = COALESCE((
                                SELECT group_concat(content, ' ')
                                FROM conversation_messages
                                WHERE conversation_id = conversations.id AND content != ''
                              ), ''),
                              last_message = (
                                SELECT substr(content, 1, 50)
                                FROM conversation_messages
                                WHERE conversation_id = conversations.id
                                ORDER BY seq DESC LIMIT 1
                              )
                            WHERE id IN (SELECT DISTINCT conversation_id FROM conversation_messages)
                            """
                        )
                    )
                    backfilled = sync_conn.execute(
                        text("SELECT COUNT(*) FROM conversation_messages")
                    ).scalar() or 0
                    backfill_ok = True
                    logger.info(f"[DB] Migrated conversations.messages JSON → conversation_messages: {backfilled} rows")
                except Exception as e:
                    backfill_failed = True
                    logger.warning(f"[DB] conversation_messages backfill skipped: {e}")
            # 仅当回填成功才移除旧列（防数据丢失：回填失败时保留 messages 列可人工恢复）
            if backfill_ok:
                try:
                    sync_conn.execute(text("ALTER TABLE conversations DROP COLUMN messages"))
                    logger.info("[DB] Migrated conversations table: dropped legacy messages column")
                except Exception as e:
                    logger.debug(f"[DB] Drop legacy messages column skipped: {e}")

    # ── 群聊消息独立表回填（旧库，机制与 conversations.messages 回填一致） ──
    if "groups" in inspector.get_table_names():
        group_cols = {c["name"] for c in inspector.get_columns("groups")}
        if "group_messages" in inspector.get_table_names() and "messages" in group_cols:
            group_msg_count = sync_conn.execute(
                text("SELECT COUNT(*) FROM group_messages")
            ).scalar() or 0
            group_backfill_ok = group_msg_count > 0  # 已有行视为已回填（幂等）
            if group_msg_count == 0:
                try:
                    sync_conn.execute(
                        text(
                            """
                            INSERT INTO group_messages
                                (group_id, mid, sender_type, content, data, created_at)
                            SELECT g.id,
                                   COALESCE(json_extract(value, '$.id'), ''),
                                   COALESCE(json_extract(value, '$.sender_type'),
                                            json_extract(value, '$.senderType'), ''),
                                   COALESCE(json_extract(value, '$.content'), ''),
                                   value,
                                   COALESCE(json_extract(value, '$.timestamp'), g.updated_at, '')
                            FROM groups g, json_each(g.messages)
                            WHERE g.messages IS NOT NULL AND g.messages != '[]'
                            """
                        )
                    )
                    group_backfilled = sync_conn.execute(
                        text("SELECT COUNT(*) FROM group_messages")
                    ).scalar() or 0
                    group_backfill_ok = True
                    logger.info(f"[DB] Migrated groups.messages JSON → group_messages: {group_backfilled} rows")
                except Exception as e:
                    backfill_failed = True
                    logger.warning(f"[DB] group_messages backfill skipped: {e}")
            # 仅当回填成功才移除旧列（防数据丢失：回填失败时保留 messages 列可人工恢复）
            if group_backfill_ok:
                try:
                    sync_conn.execute(text("ALTER TABLE groups DROP COLUMN messages"))
                    logger.info("[DB] Migrated groups table: dropped legacy groups messages column")
                except Exception as e:
                    logger.debug(f"[DB] Drop legacy groups messages column skipped: {e}")

    # conversations 表历史列兜底（存量库补齐）
    if "conversations" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("conversations")}
        if "chat_mode" not in existing_cols:
            _alter_safe(
                "ALTER TABLE conversations ADD COLUMN chat_mode VARCHAR(32) DEFAULT 'normal'",
                "conversations table: added chat_mode column",
            )
        # ULTRA 模式已移除：存量 ultra 会话归一为 standard（幂等，无命中即空操作）
        sync_conn.execute(
            text("UPDATE conversations SET chat_mode='standard' WHERE chat_mode='ultra'")
        )
        if "is_hidden" not in existing_cols:
            _alter_safe(
                "ALTER TABLE conversations ADD COLUMN is_hidden BOOLEAN DEFAULT 0",
                "conversations table: added is_hidden column",
            )
        # 对话域字段（洋葱架构 §5.2/§12.1）：domain/scene/user_key
        if "domain" not in existing_cols:
            _alter_safe(
                "ALTER TABLE conversations ADD COLUMN domain TEXT DEFAULT ''",
                "conversations table: added domain column",
            )
        if "scene" not in existing_cols:
            _alter_safe(
                "ALTER TABLE conversations ADD COLUMN scene TEXT DEFAULT 'workbench'",
                "conversations table: added scene column",
            )
        if "user_key" not in existing_cols:
            _alter_safe(
                "ALTER TABLE conversations ADD COLUMN user_key TEXT DEFAULT ''",
                "conversations table: added user_key column",
            )
        # §12.1 索引：domain / user_key 查询索引（新建库由 create_all 建立，此处兜底存量库）
        existing_indexes = {ix["name"] for ix in inspector.get_indexes("conversations")}
        if "ix_conversations_domain" not in existing_indexes:
            _alter_safe(
                "CREATE INDEX ix_conversations_domain ON conversations(domain)",
                "conversations table: added ix_conversations_domain index",
            )
        if "ix_conversations_user_key" not in existing_indexes:
            _alter_safe(
                "CREATE INDEX ix_conversations_user_key ON conversations(user_key)",
                "conversations table: added ix_conversations_user_key index",
            )
        # 会话列表主路径复合索引（审计 B5-6）：deleted_at 过滤 + updated_at 排序
        if "ix_conversations_deleted_updated" not in existing_indexes:
            _alter_safe(
                "CREATE INDEX ix_conversations_deleted_updated ON conversations(deleted_at, updated_at)",
                "conversations table: added ix_conversations_deleted_updated index",
            )
        # 冗余索引清理（审计 B5-6）：session_id 单列索引是 (session_id, created_at) 前缀
        # 的完全冗余；模型侧已删除定义，此处兜底清理存量库
        if "tool_call_records" in inspector.get_table_names():
            tcr_indexes = {ix["name"] for ix in inspector.get_indexes("tool_call_records")}
            if "ix_tool_call_records_session_id" in tcr_indexes:
                sync_conn.execute(text("DROP INDEX IF EXISTS ix_tool_call_records_session_id"))
                logger.info("[DB] Migrated tool_call_records table: dropped redundant ix_tool_call_records_session_id")

    # 记忆蒸馏游标列（memory_profiles，Phase 4 防多 worker/重启重复蒸馏）
    if "memory_profiles" in inspector.get_table_names():
        mp_cols = {c["name"] for c in inspector.get_columns("memory_profiles")}
        if "distilled_turns" not in mp_cols:
            _alter_safe(
                "ALTER TABLE memory_profiles ADD COLUMN distilled_turns INTEGER DEFAULT 0",
                "memory_profiles table: added distilled_turns column",
            )

    # SCHEMA v2：记忆事实置顶列（陪伴场景关键信息必注入）
    if "memory_facts" in inspector.get_table_names():
        mf_cols = {c["name"] for c in inspector.get_columns("memory_facts")}
        if "pinned" not in mf_cols:
            _alter_safe(
                "ALTER TABLE memory_facts ADD COLUMN pinned BOOLEAN DEFAULT 0",
                "memory_facts table: added pinned column",
            )
        # SCHEMA v3：双层记忆作用域 (global/private/group) 与群标识
        if "scope" not in mf_cols:
            _alter_safe(
                "ALTER TABLE memory_facts ADD COLUMN scope VARCHAR(32) DEFAULT 'global'",
                "memory_facts table: added scope column",
            )
        if "group_id" not in mf_cols:
            _alter_safe(
                "ALTER TABLE memory_facts ADD COLUMN group_id VARCHAR(64) DEFAULT ''",
                "memory_facts table: added group_id column",
            )
        existing_mf_indexes = {ix["name"] for ix in inspector.get_indexes("memory_facts")}
        if "ix_memory_facts_owner_scope" not in existing_mf_indexes:
            _alter_safe(
                "CREATE INDEX ix_memory_facts_owner_scope ON memory_facts(owner_key, scope, is_latest)",
                "memory_facts table: added ix_memory_facts_owner_scope index",
            )

    # providers 表添加 protocol 列（接入协议：auto | chat_completions | anthropic_messages）
    if "providers" in inspector.get_table_names():
        provider_cols = {c["name"] for c in inspector.get_columns("providers")}
        if "protocol" not in provider_cols:
            _alter_safe(
                "ALTER TABLE providers ADD COLUMN protocol VARCHAR(32) DEFAULT 'auto'",
                "providers table: added protocol column",
            )

    # tool_call_records 表补 scope/tool_type 列（tool-opt §9 决策 10：工具分层审计）
    if "tool_call_records" in inspector.get_table_names():
        tcr_cols = {c["name"] for c in inspector.get_columns("tool_call_records")}
        if "scope" not in tcr_cols:
            _alter_safe(
                "ALTER TABLE tool_call_records ADD COLUMN scope VARCHAR(64)",
                "tool_call_records table: added scope column",
            )
        if "tool_type" not in tcr_cols:
            _alter_safe(
                "ALTER TABLE tool_call_records ADD COLUMN tool_type VARCHAR(32)",
                "tool_call_records table: added tool_type column",
            )

    # skills 表（洋葱架构 §11.1）：新建库由 create_all 建表；
    # 此处兜底存量库——若历史上已存在手工建的 skills 表，补齐缺失列
    if "skills" in inspector.get_table_names():
        skill_cols = {c["name"] for c in inspector.get_columns("skills")}
        _skill_col_defs = {
            "name": "TEXT NOT NULL DEFAULT ''",
            "version": "TEXT DEFAULT '1.0.0'",
            "description": "TEXT DEFAULT ''",
            "category": "TEXT DEFAULT ''",
            "tags": "TEXT DEFAULT '[]'",
            "status": "TEXT DEFAULT 'loaded'",
            "enabled": "INTEGER DEFAULT 1",
            "source_path": "TEXT DEFAULT ''",
            "body_length": "INTEGER DEFAULT 0",
            "updated_at": "TEXT DEFAULT ''",
            "created_at": "TEXT DEFAULT ''",
        }
        for col_name, col_def in _skill_col_defs.items():
            if col_name not in skill_cols:
                _alter_safe(
                    f"ALTER TABLE skills ADD COLUMN {col_name} {col_def}",
                    f"skills table: added {col_name} column",
                )

    # ── 回写 schema 版本（全部迁移成功才到达：异常路径不回写，下次启动重试） ──
    if not backfill_failed:
        sync_conn.execute(text(f"PRAGMA user_version={int(SCHEMA_VERSION)}"))


async def dispose_db() -> None:
    """关闭双引擎连接池。应在应用 lifespan 关闭时调用。"""
    await async_engine.dispose()
    sync_engine.dispose()
    logger.info("[DB] Database engines disposed")
