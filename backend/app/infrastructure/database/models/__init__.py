"""ORM 模型包。

导入所有模型以注册到 Base.metadata，使 create_all 能创建全部表。
"""
from app.infrastructure.database.models.agent import Agent
from app.infrastructure.database.models.audit_log import AuditLog
from app.infrastructure.database.models.config_item import ConfigItem
from app.infrastructure.database.models.conversation import Conversation
from app.infrastructure.database.models.group import Group
from app.infrastructure.database.models.marketplace_stat import MarketplaceStat
from app.infrastructure.database.models.migration_meta import MigrationMeta
from app.infrastructure.database.models.platform_instance import PlatformInstance
from app.infrastructure.database.models.provider import Provider
from app.infrastructure.database.models.provider_credential import ProviderCredential
from app.infrastructure.database.models.repo_source import RepoSource
from app.infrastructure.database.models.scheduled_task import ScheduledTaskORM
from app.infrastructure.database.models.tool_call_record import ToolCallRecordORM
from app.infrastructure.database.models.usage_record import UsageRecord
from app.infrastructure.database.models.user import User
from app.infrastructure.database.models.workflow_node import WorkflowNodeORM
from app.infrastructure.database.models.workflow_session import WorkflowSessionORM

__all__ = [
    "Agent",
    "AuditLog",
    "ConfigItem",
    "Conversation",
    "Group",
    "MarketplaceStat",
    "MigrationMeta",
    "PlatformInstance",
    "Provider",
    "ProviderCredential",
    "RepoSource",
    "ScheduledTaskORM",
    "ToolCallRecordORM",
    "UsageRecord",
    "User",
    "WorkflowNodeORM",
    "WorkflowSessionORM",
]
