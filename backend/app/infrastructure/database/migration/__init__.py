"""数据库迁移包。

提供 JSON → SQLite 幂等迁移器，由 app_factory lifespan 在启动时调用。
"""
from app.infrastructure.database.migration.json_to_sqlite_migrator import (
    migrate_all_json_to_sqlite,
)

__all__ = ["migrate_all_json_to_sqlite"]
