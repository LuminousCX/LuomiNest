"""配置存储 shim — 实际实现已迁移至 Facade 层。

保留导入兼容性：
`from app.infrastructure.database.config_store import lumi_config_store` 零改动。

底层委托 ConfigRepository + config_items 表（SQLite），替代原 user_config.json。
敏感字段（api_key/secret_key）自动 AES 加解密，fnmatch 模式判定。
"""
from app.infrastructure.database.facades.config_store import LumiConfigFacade, lumi_config_store

__all__ = ["LumiConfigFacade", "lumi_config_store"]
