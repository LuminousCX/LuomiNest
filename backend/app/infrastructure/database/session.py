"""Session 工厂。

提供 async 与 sync 两套 session 工厂：
- async_session_factory：运行时 FastAPI 路由使用
- sync_session_factory：模块加载阶段或同步代码路径使用

expire_on_commit=False 保证 commit 后对象仍可访问属性（避免 lazy load 触发 async 上下文错误）。
"""
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database.engine import async_engine, sync_engine


# async session 工厂
async_session_factory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# sync session 工厂
sync_session_factory = sessionmaker(
    bind=sync_engine,
    class_=Session,
    expire_on_commit=False,
)


@asynccontextmanager
async def get_async_session(
    *, auto_commit: bool = True,
) -> AsyncIterator[AsyncSession]:
    """获取 async session 的上下文管理器。

    自动管理 session 生命周期（关闭 + commit/rollback）。

    Args:
        auto_commit: True（默认）时，正常退出自动 commit、异常自动 rollback；
                     False 时由调用方显式 commit/rollback。
    """
    async with async_session_factory() as session:
        try:
            yield session
            if auto_commit:
                await session.commit()
        except Exception:
            await session.rollback()
            raise
