"""SQLAlchemy 双引擎与数据库初始化。

设计要点：
- async_engine（aiosqlite）：运行时 FastAPI 路由使用
- sync_engine（sqlite3）：模块加载阶段（如 adapter import）需要同步访问时使用
- 两引擎指向同一 .db 文件，依赖 SQLite WAL 模式支持并发读写
- 每个新连接自动执行 PRAGMA（journal_mode=WAL / synchronous=NORMAL / foreign_keys=ON）
"""
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from loguru import logger

from app.core.config import settings
from app.infrastructure.database.base import Base


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
    """
    # 显式导入所有模型，确保 Base.metadata 注册完整（不依赖调用方的导入顺序）
    from app.infrastructure.database import models  # noqa: F401
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 列迁移：create_all 不会为已有表添加新列，需手动 ALTER TABLE
        await _migrate_columns(conn)
    logger.success(f"[DB] Database initialized at {settings.DATABASE_URL}")


async def _migrate_columns(conn) -> None:
    """为已有表添加缺失列（SQLite ALTER TABLE ADD COLUMN，幂等）。

    另负责 messages JSON 列 → conversation_messages 独立表的存量回填
    （前端后端项目锐评 · 高优先级 #1）：
    1. conversation_messages 表由 create_all 新建（含 FK + 索引）；
    2. 若旧库 conversations 仍带 messages JSON 列且消息表为空 → 逐行回填；
    3. 回填成功后 DROP 旧列（SQLite 3.35+ 支持），避免双写不一致。
    """
    from sqlalchemy import text, inspect

    def _do_migrate(sync_conn):
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
                        logger.warning(f"[DB] conversation_messages backfill skipped: {e}")
                # 仅当回填成功才移除旧列（防数据丢失：回填失败时保留 messages 列可人工恢复）
                if backfill_ok:
                    try:
                        sync_conn.execute(text("ALTER TABLE conversations DROP COLUMN messages"))
                        logger.info("[DB] Migrated conversations table: dropped legacy messages column")
                    except Exception as e:
                        logger.debug(f"[DB] Drop legacy messages column skipped: {e}")

        # conversations 表历史列兜底（存量库补齐）
        if "conversations" in inspector.get_table_names():
            existing_cols = {c["name"] for c in inspector.get_columns("conversations")}
            if "chat_mode" not in existing_cols:
                sync_conn.execute(
                    text("ALTER TABLE conversations ADD COLUMN chat_mode VARCHAR(32) DEFAULT 'normal'")
                )
                logger.info("[DB] Migrated conversations table: added chat_mode column")
            if "is_hidden" not in existing_cols:
                sync_conn.execute(
                    text("ALTER TABLE conversations ADD COLUMN is_hidden BOOLEAN DEFAULT 0")
                )
                logger.info("[DB] Migrated conversations table: added is_hidden column")
            # 对话域字段（洋葱架构 §5.2/§12.1）：domain/scene/user_key
            if "domain" not in existing_cols:
                sync_conn.execute(
                    text("ALTER TABLE conversations ADD COLUMN domain TEXT DEFAULT ''")
                )
                logger.info("[DB] Migrated conversations table: added domain column")
            if "scene" not in existing_cols:
                sync_conn.execute(
                    text("ALTER TABLE conversations ADD COLUMN scene TEXT DEFAULT 'workbench'")
                )
                logger.info("[DB] Migrated conversations table: added scene column")
            if "user_key" not in existing_cols:
                sync_conn.execute(
                    text("ALTER TABLE conversations ADD COLUMN user_key TEXT DEFAULT ''")
                )
                logger.info("[DB] Migrated conversations table: added user_key column")
            # §12.1 索引：domain / user_key 查询索引（新建库由 create_all 建立，此处兜底存量库）
            existing_indexes = {ix["name"] for ix in inspector.get_indexes("conversations")}
            if "ix_conversations_domain" not in existing_indexes:
                sync_conn.execute(
                    text("CREATE INDEX ix_conversations_domain ON conversations(domain)")
                )
                logger.info("[DB] Migrated conversations table: added ix_conversations_domain index")
            if "ix_conversations_user_key" not in existing_indexes:
                sync_conn.execute(
                    text("CREATE INDEX ix_conversations_user_key ON conversations(user_key)")
                )
                logger.info("[DB] Migrated conversations table: added ix_conversations_user_key index")

        # providers 表添加 protocol 列（接入协议：auto | chat_completions | anthropic_messages）
        if "providers" in inspector.get_table_names():
            provider_cols = {c["name"] for c in inspector.get_columns("providers")}
            if "protocol" not in provider_cols:
                sync_conn.execute(
                    text("ALTER TABLE providers ADD COLUMN protocol VARCHAR(32) DEFAULT 'auto'")
                )
                logger.info("[DB] Migrated providers table: added protocol column")

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
                    sync_conn.execute(
                        text(f"ALTER TABLE skills ADD COLUMN {col_name} {col_def}")
                    )
                    logger.info(f"[DB] Migrated skills table: added {col_name} column")

    await conn.run_sync(_do_migrate)


async def dispose_db() -> None:
    """关闭双引擎连接池。应在应用 lifespan 关闭时调用。"""
    await async_engine.dispose()
    sync_engine.dispose()
    logger.info("[DB] Database engines disposed")
