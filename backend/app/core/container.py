"""LuomiNest 服务容器 —— 集中管理全局单例的生命周期与依赖关系。

设计原则（洋葱架构 + 甜甜圈共享内核）：
- 所有核心服务在此统一创建和注册，形成"共享内核"（Shared Kernel）
- API 层通过 FastAPI Depends() 获取服务实例，不再直接 import 全局单例
- 向后兼容：旧的全局单例仍然可用，但新代码应优先使用容器

迁移路径：
1. 当前阶段：容器与全局单例共存，Depends() 返回的就是全局单例本身
2. 未来阶段：逐步将全局单例迁移为容器管理的实例，最终消除模块级单例
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from app.runtime.provider.llm.adapter import LLMAdapter
    from app.runtime.provider.registry import ProviderRegistry
    from app.core.tools.registry import ToolRegistry
    from app.core.tools.orchestrator import ToolOrchestrator
    from app.services.chat_service import ChatService
    from app.services.context_service import ContextService
    from app.services.suggestion_service import SuggestionService
    from app.infrastructure.database.conversation_store import ConversationFacade
    from app.infrastructure.database.config_store import LumiConfigFacade
    from app.infrastructure.database.usage_store import UsageFacade
    from app.infrastructure.database.facades.json_store_facade import JsonStoreFacade
    from app.infrastructure.database.facades.marketplace_stats_store import MarketplaceStatsFacade
    from app.core.agents.subagent_executor import SubagentExecutor
    from app.core.scheduler.manager import LuomiSchedulerManager


class ServiceContainer:
    """服务容器 —— 懒初始化、集中管理、可测试。

    所有核心服务通过属性访问，首次访问时自动创建。
    测试时可替换任意服务实例（mock-friendly）。
    """

    def __init__(self) -> None:
        self._cache: dict[str, object] = {}
        logger.debug("[Container] ServiceContainer created")

    # ── Provider 层 ──

    @property
    def llm_adapter(self) -> "LLMAdapter":
        if "llm_adapter" not in self._cache:
            from app.runtime.provider.llm.adapter import llm_adapter
            self._cache["llm_adapter"] = llm_adapter
        return self._cache["llm_adapter"]  # type: ignore

    @property
    def provider_registry(self) -> "ProviderRegistry":
        if "provider_registry" not in self._cache:
            from app.runtime.provider.registry import provider_registry
            self._cache["provider_registry"] = provider_registry
        return self._cache["provider_registry"]  # type: ignore

    # ── Tool 层 ──

    @property
    def tool_registry(self) -> "ToolRegistry":
        if "tool_registry" not in self._cache:
            from app.core.tools import tool_registry
            self._cache["tool_registry"] = tool_registry
        return self._cache["tool_registry"]  # type: ignore

    @property
    def tool_orchestrator(self) -> "ToolOrchestrator":
        if "tool_orchestrator" not in self._cache:
            from app.core.tools.orchestrator import tool_orchestrator
            self._cache["tool_orchestrator"] = tool_orchestrator
        return self._cache["tool_orchestrator"]  # type: ignore

    # ── Service 层 ──

    @property
    def context_service(self) -> "ContextService":
        # 复用模块单例：全系统唯一 ContextService（持有 _memory_locks 等状态），
        # 避免容器与模块单例并存导致的状态分裂
        if "context_service" not in self._cache:
            from app.services.context_service import context_service
            self._cache["context_service"] = context_service
        return self._cache["context_service"]  # type: ignore

    @property
    def suggestion_service(self) -> "SuggestionService":
        # 复用模块单例：全系统唯一 SuggestionService（持有 _pending_tasks 状态）
        if "suggestion_service" not in self._cache:
            from app.services.suggestion_service import suggestion_service
            self._cache["suggestion_service"] = suggestion_service
        return self._cache["suggestion_service"]  # type: ignore

    @property
    def chat_service(self) -> "ChatService":
        # 全系统唯一 ChatService：懒创建一次并缓存，
        # 组装的 context/suggestions 即上方模块单例（同一对象）
        if "chat_service" not in self._cache:
            from app.services.chat_service import ChatService
            self._cache["chat_service"] = ChatService(
                context=self.context_service,
                suggestions=self.suggestion_service,
            )
        return self._cache["chat_service"]  # type: ignore

    # ── Agent 执行 / 调度层 ──
    # 以下属性代理既有模块单例本身，绝不新建实例

    @property
    def subagent_executor(self) -> "SubagentExecutor":
        if "subagent_executor" not in self._cache:
            from app.core.agents.subagent_executor import subagent_executor
            self._cache["subagent_executor"] = subagent_executor
        return self._cache["subagent_executor"]  # type: ignore

    @property
    def luominest_scheduler(self) -> "LuomiSchedulerManager":
        if "luominest_scheduler" not in self._cache:
            from app.core.scheduler.manager import luominest_scheduler
            self._cache["luominest_scheduler"] = luominest_scheduler
        return self._cache["luominest_scheduler"]  # type: ignore

    # ── 数据访问门面层（Facade 即端口）──
    # 以下属性直接返回既有门面单例对象本身，绝不新建实例

    @property
    def conversation_store(self) -> "ConversationFacade":
        if "conversation_store" not in self._cache:
            from app.infrastructure.database.conversation_store import conversation_store
            self._cache["conversation_store"] = conversation_store
        return self._cache["conversation_store"]  # type: ignore

    @property
    def luominest_config_store(self) -> "LumiConfigFacade":
        if "luominest_config_store" not in self._cache:
            from app.infrastructure.database.config_store import luominest_config_store
            self._cache["luominest_config_store"] = luominest_config_store
        return self._cache["luominest_config_store"]  # type: ignore

    @property
    def usage_store(self) -> "UsageFacade":
        if "usage_store" not in self._cache:
            from app.infrastructure.database.usage_store import usage_store
            self._cache["usage_store"] = usage_store
        return self._cache["usage_store"]  # type: ignore

    @property
    def agents_store(self) -> "JsonStoreFacade":
        if "agents_store" not in self._cache:
            from app.infrastructure.database.facades.json_store_facade import agents_store
            self._cache["agents_store"] = agents_store
        return self._cache["agents_store"]  # type: ignore

    @property
    def groups_store(self) -> "JsonStoreFacade":
        if "groups_store" not in self._cache:
            from app.infrastructure.database.facades.json_store_facade import groups_store
            self._cache["groups_store"] = groups_store
        return self._cache["groups_store"]  # type: ignore

    @property
    def platforms_store(self) -> "JsonStoreFacade":
        if "platforms_store" not in self._cache:
            from app.infrastructure.database.facades.json_store_facade import platforms_store
            self._cache["platforms_store"] = platforms_store
        return self._cache["platforms_store"]  # type: ignore

    @property
    def repo_sources_store(self) -> "JsonStoreFacade":
        if "repo_sources_store" not in self._cache:
            from app.infrastructure.database.facades.json_store_facade import repo_sources_store
            self._cache["repo_sources_store"] = repo_sources_store
        return self._cache["repo_sources_store"]  # type: ignore

    @property
    def marketplace_stats_store(self) -> "MarketplaceStatsFacade":
        if "marketplace_stats_store" not in self._cache:
            from app.infrastructure.database.facades.marketplace_stats_store import (
                marketplace_stats_store,
            )
            self._cache["marketplace_stats_store"] = marketplace_stats_store
        return self._cache["marketplace_stats_store"]  # type: ignore

    # ── 测试支持 ──

    def override(self, name: str, instance: object) -> None:
        """替换容器中的服务实例（用于测试或特殊场景）。"""
        self._cache[name] = instance
        logger.debug(f"[Container] Overridden: {name}")

    def reset(self) -> None:
        """清空容器缓存（下次访问时重新创建）。"""
        self._cache.clear()
        logger.debug("[Container] Cache cleared")


# ── 全局容器单例 ──
container = ServiceContainer()


# ── FastAPI Depends() 工厂 ──
# 使用方式：在路由函数参数中写 `chat_svc: ChatService = Depends(get_chat_service)`

def get_llm_adapter():
    """FastAPI 依赖：获取 LLMAdapter 实例。"""
    return container.llm_adapter


def get_provider_registry():
    """FastAPI 依赖：获取 ProviderRegistry 实例。"""
    return container.provider_registry


def get_tool_registry():
    """FastAPI 依赖：获取 ToolRegistry 实例。"""
    return container.tool_registry


def get_tool_orchestrator():
    """FastAPI 依赖：获取 ToolOrchestrator 实例。"""
    return container.tool_orchestrator


def get_chat_service():
    """FastAPI 依赖：获取 ChatService 实例。"""
    return container.chat_service


def get_context_service():
    """FastAPI 依赖：获取 ContextService 实例。"""
    return container.context_service


def get_suggestion_service():
    """FastAPI 依赖：获取 SuggestionService 实例。"""
    return container.suggestion_service


def get_conversation_store():
    """FastAPI 依赖：获取对话存储门面（全局单例本身）。"""
    return container.conversation_store


def get_lumi_config_store():
    """FastAPI 依赖：获取配置存储门面（全局单例本身）。"""
    return container.luominest_config_store


def get_usage_store():
    """FastAPI 依赖：获取用量存储门面（全局单例本身）。"""
    return container.usage_store


def get_agents_store():
    """FastAPI 依赖：获取 Agent 存储门面（全局单例本身）。"""
    return container.agents_store


def get_groups_store():
    """FastAPI 依赖：获取群组存储门面（全局单例本身）。"""
    return container.groups_store


def get_platforms_store():
    """FastAPI 依赖：获取平台实例存储门面（全局单例本身）。"""
    return container.platforms_store


def get_repo_sources_store():
    """FastAPI 依赖：获取仓库来源存储门面（全局单例本身）。"""
    return container.repo_sources_store


def get_marketplace_stats_store():
    """FastAPI 依赖：获取市场统计存储门面（全局单例本身）。"""
    return container.marketplace_stats_store


def get_subagent_executor():
    """FastAPI 依赖：获取子 Agent 执行器（全局单例本身）。"""
    return container.subagent_executor


def get_luomi_scheduler():
    """FastAPI 依赖：获取定时任务调度器管理器（全局单例本身）。"""
    return container.luominest_scheduler
