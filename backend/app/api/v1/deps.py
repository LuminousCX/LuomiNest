"""FastAPI 依赖注入入口。

认证由 app.security.auth.middleware.luomi_auth_middleware 在中间件层统一处理，
所有 /api/* 请求自动验证 Bearer Token，无需在路由层重复 Depends。

服务依赖通过 ServiceContainer 统一管理，路由层可使用 Depends() 获取服务实例：
    from app.api.v1.deps import get_chat_service, get_llm_adapter
    @router.get("/example")
    async def example(chat_svc = Depends(get_chat_service)):
        ...

迁移策略：
- 旧代码仍可直接 import 全局单例（向后兼容）
- 新代码推荐使用 Depends() 注入，便于测试和替换
"""
from app.core.container import (
    container,
    get_llm_adapter,
    get_provider_registry,
    get_tool_registry,
    get_tool_orchestrator,
    get_chat_service,
    get_context_service,
    get_suggestion_service,
    get_conversation_store,
    get_lumi_config_store,
    get_usage_store,
    get_agents_store,
    get_groups_store,
    get_platforms_store,
    get_repo_sources_store,
    get_marketplace_stats_store,
    get_subagent_executor,
    get_luomi_scheduler,
)

__all__ = [
    "container",
    "get_llm_adapter",
    "get_provider_registry",
    "get_tool_registry",
    "get_tool_orchestrator",
    "get_chat_service",
    "get_context_service",
    "get_suggestion_service",
    "get_conversation_store",
    "get_lumi_config_store",
    "get_usage_store",
    "get_agents_store",
    "get_groups_store",
    "get_platforms_store",
    "get_repo_sources_store",
    "get_marketplace_stats_store",
    "get_subagent_executor",
    "get_luomi_scheduler",
]
