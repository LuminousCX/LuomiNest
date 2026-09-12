"""全局测试夹具。

在任何 app 模块导入之前，把 LUOMINEST_DATA_DIR 指向会话级临时目录：
settings（get_settings）在模块导入期解析 DATA_DIR / DATABASE_URL，
环境变量优先级高于 .env，因此这里设置后所有 SQLite/密钥/记忆文件
均落在临时目录，绝不触碰真实 backend/data/。
"""

import atexit
import os
import shutil
import tempfile

# conftest 先于测试模块收集执行，此处的环境变量设置对全部 app.* 导入生效
_TEST_DATA_DIR = tempfile.mkdtemp(prefix="luominest-test-data-")
os.environ["LUOMINEST_DATA_DIR"] = _TEST_DATA_DIR
# .env 中若显式配置了 DATABASE_URL 会绕过 DATA_DIR 推导，统一置空强制按临时目录重算
os.environ["DATABASE_URL"] = ""

atexit.register(shutil.rmtree, _TEST_DATA_DIR, ignore_errors=True)

import asyncio  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def _init_test_db():
    """按生产路径建表一次（幂等 create_all + 列迁移），供端点/仓储测试使用临时 SQLite。

    建表后丢弃连接池：aiosqlite 连接绑定创建时的事件循环，
    后续测试各自的函数级 loop 不能复用池化连接。
    """

    async def _boot():
        from app.infrastructure.database.engine import async_engine, init_db

        await init_db()
        await async_engine.dispose()

    asyncio.run(_boot())


@pytest.fixture(autouse=True)
def _dispose_async_engine_pool():
    """每个测试结束后清空 async 引擎连接池，避免 aiosqlite 连接跨事件循环复用。"""
    yield

    async def _dispose():
        from app.infrastructure.database.engine import async_engine

        await async_engine.dispose()

    asyncio.run(_dispose())
