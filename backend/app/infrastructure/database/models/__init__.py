"""ORM 模型包。

导入所有模型以注册到 Base.metadata，使 create_all 能创建全部表。
"""
from app.infrastructure.database.models.agent import Agent
from app.infrastructure.database.models.config_item import ConfigItem
from app.infrastructure.database.models.conversation import Conversation
from app.infrastructure.database.models.group import Group
from app.infrastructure.database.models.marketplace_stat import MarketplaceStat
from app.infrastructure.database.models.migration_meta import MigrationMeta
from app.infrastructure.database.models.platform_instance import PlatformInstance
from app.infrastructure.database.models.provider import Provider
from app.infrastructure.database.models.provider_credential import ProviderCredential
from app.infrastructure.database.models.repo_source import RepoSource
from app.infrastructure.database.models.usage_record import UsageRecord

__all__ = [
    "Agent",
    "ConfigItem",
    "Conversation",
    "Group",
    "MarketplaceStat",
    "MigrationMeta",
    "PlatformInstance",
    "Provider",
    "ProviderCredential",
    "RepoSource",
    "UsageRecord",
]
