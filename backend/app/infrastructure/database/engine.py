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
    """初始化数据库：创建所有表（幂等，已存在的表不会重建）。

    应在应用 lifespan 启动时调用一次。
    """
    # 显式导入所有模型，确保 Base.metadata 注册完整（不依赖调用方的导入顺序）
    from app.infrastructure.database import models  # noqa: F401
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.success(f"[DB] Database initialized at {settings.DATABASE_URL}")


async def dispose_db() -> None:
    """关闭双引擎连接池。应在应用 lifespan 关闭时调用。"""
    await async_engine.dispose()
    sync_engine.dispose()
    logger.info("[DB] Database engines disposed")
