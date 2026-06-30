"""用量存储 shim — 实际实现已迁移至 Facade 层。

保留导入兼容性：
`from app.infrastructure.database.usage_store import usage_store` 零改动。

底层委托 UsageRepository + usage_records 表（SQLite），替代原 usage_records.json。
- get_summary() 用 SQL GROUP BY（替代 Python 全表扫描）
- trim(max_records) 用 SQL DELETE（替代直接访问 _records 的 hack）
"""
from app.infrastructure.database.facades.usage_store import UsageFacade, usage_store

__all__ = ["UsageFacade", "usage_store"]
