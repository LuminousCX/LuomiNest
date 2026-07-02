"""Facade 兼容层 — 保留原 store 单例名，委托 Repository，消费者零改动。

导入路径不变：
- from app.infrastructure.database.json_store import agents_store  （经 json_store.py 重导出）
- from app.infrastructure.database.config_store import lumi_config_store
- from app.infrastructure.database.usage_store import usage_store
- from app.infrastructure.database.conversation_store import conversation_store

也可直接从 facades 导入：
- from app.infrastructure.database.facades import agents_store, lumi_config_store, ...
"""
from app.infrastructure.database.facades.config_store import LumiConfigFacade, lumi_config_store
from app.infrastructure.database.facades.conversation_store import ConversationFacade, conversation_store
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
from app.infrastructure.database.facades.usage_store import UsageFacade, usage_store

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
    "lumi_config_store",
    "usage_store",
    "conversation_store",
]
