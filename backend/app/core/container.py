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
        if "context_service" not in self._cache:
            from app.services.context_service import ContextService
            self._cache["context_service"] = ContextService()
        return self._cache["context_service"]  # type: ignore

    @property
    def suggestion_service(self) -> "SuggestionService":
        if "suggestion_service" not in self._cache:
            from app.services.suggestion_service import SuggestionService
            self._cache["suggestion_service"] = SuggestionService()
        return self._cache["suggestion_service"]  # type: ignore

    @property
    def chat_service(self) -> "ChatService":
        if "chat_service" not in self._cache:
            from app.services.chat_service import ChatService
            self._cache["chat_service"] = ChatService(
                context=self.context_service,
                suggestions=self.suggestion_service,
            )
        return self._cache["chat_service"]  # type: ignore

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
