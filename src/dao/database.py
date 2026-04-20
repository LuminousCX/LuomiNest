"""数据库管理器。

提供统一的数据库引擎、会话工厂和表初始化。
支持 SQLAlchemy ORM 表和 FTS5 虚拟表的自动创建。
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from src.model.base import DeclarativeBaseModel
from src.model.agent import AgentModel
from src.model.chunk import ChunkModel
from src.model.conversation import ConversationModel, MessageModel
from src.model.embedding import EmbeddingModel
from src.model.entity import EntityModel
from src.utils.logger import get_logger

logger = get_logger()

_FTS5_CREATE_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    content,
    chunk_type,
    content='chunks',
    content_rowid='id'
);
"""

_FTS5_TRIGGER_INSERT = """
CREATE TRIGGER IF NOT EXISTS chunks_fts_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, content, chunk_type)
    VALUES (new.id, new.content, new.chunk_type);
END;
"""

_FTS5_TRIGGER_DELETE = """
CREATE TRIGGER IF NOT EXISTS chunks_fts_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, content, chunk_type)
    VALUES('delete', old.id, old.content, old.chunk_type);
END;
"""

_FTS5_TRIGGER_UPDATE = """
CREATE TRIGGER IF NOT EXISTS chunks_fts_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, content, chunk_type)
    VALUES('delete', old.id, old.content, old.chunk_type);
    INSERT INTO chunks_fts(rowid, content, chunk_type)
    VALUES (new.id, new.content, new.chunk_type);
END;
"""

_AGENT_CONSTRAINTS_MIGRATION = """
ALTER TABLE agent ADD COLUMN constraints TEXT NOT NULL DEFAULT '';
"""


class DatabaseManager:
    """数据库管理器。

    统一管理 SQLAlchemy 引擎、会话工厂和表初始化。
    支持 FTS5 全文搜索虚拟表和触发器的自动创建。

    Attributes:
        engine: SQLAlchemy 引擎。
        session_factory: Session 工厂。
    """

    def __init__(self, db_path: str) -> None:
        """初始化数据库管理器。

        Args:
            db_path: SQLite 数据库文件路径。
        """
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

        self.engine = create_engine(
            f"sqlite:///{db_path}",
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            connect_args={"check_same_thread": False},
        )
        self._setup_wal_mode()
        self.session_factory = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
        )

        self._create_tables()
        self._create_fts5()
        self._migrate_constraints()

        logger.info(f"DatabaseManager 初始化完成，数据库: {db_path}")

    def _setup_wal_mode(self) -> None:
        """配置 SQLite WAL 模式和性能 PRAGMA。"""
        @event.listens_for(self.engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=-64000")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.execute("PRAGMA mmap_size=268435456")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    def _create_tables(self) -> None:
        """创建所有 ORM 表。"""
        DeclarativeBaseModel.metadata.create_all(self.engine)
        logger.debug("ORM 表创建/验证完成")

    def _create_fts5(self) -> None:
        """创建 FTS5 虚拟表和同步触发器。"""
        with self.engine.begin() as conn:
            conn.execute(text(_FTS5_CREATE_SQL))
            conn.execute(text(_FTS5_TRIGGER_INSERT))
            conn.execute(text(_FTS5_TRIGGER_DELETE))
            conn.execute(text(_FTS5_TRIGGER_UPDATE))
        logger.debug("FTS5 虚拟表和触发器创建/验证完成")

    def _migrate_constraints(self) -> None:
        """为已有 Agent 表添加 constraints 字段。"""
        with self.engine.begin() as conn:
            try:
                conn.execute(text(_AGENT_CONSTRAINTS_MIGRATION))
                logger.debug("Agent 表 constraints 字段迁移完成")
            except Exception:
                logger.debug("Agent 表 constraints 字段已存在，跳过迁移")

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """获取数据库会话上下文管理器。

        Yields:
            SQLAlchemy Session 实例。
        """
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
