"""Facade 兼容层 — 保留原 store 单例名，委托 Repository，消费者零改动。

推荐导入路径（顶层，直接定义实现）：
- from app.infrastructure.database.config_store import luominest_config_store
- from app.infrastructure.database.usage_store import usage_store
- from app.infrastructure.database.conversation_store import conversation_store

仍在 facades/ 下的模块（经 json_store.py 重导出或本 __init__ 重导出）：
- from app.infrastructure.database.facades import agents_store, marketplace_stats_store, ...

本 __init__ 仍重导出全部 store 单例，便于 `from app.infrastructure.database.facades import *` 风格。
"""
from app.infrastructure.database.config_store import LumiConfigFacade, luominest_config_store
from app.infrastructure.database.conversation_store import ConversationFacade, conversation_store
from app.infrastructure.database.facades.json_store_facade import (
    JsonStoreFacade,
    agents_store,
    groups_store,
    platforms_store,
    repo_sources_store,
)
from app.infrastructure.database.facades.marketplace_stats_store import (
    MarketplaceStatsFacade,
    marketplace_stats_store,
)
from app.infrastructure.database.usage_store import UsageFacade, usage_store

__all__ = [
    # Facade 类
    "JsonStoreFacade",
    "LumiConfigFacade",
    "ConversationFacade",
    "MarketplaceStatsFacade",
    "UsageFacade",
    # 单例（与原 store 单例名一致）
    "agents_store",
    "groups_store",
    "platforms_store",
    "repo_sources_store",
    "marketplace_stats_store",
    "luominest_config_store",
    "usage_store",
    "conversation_store",
]
