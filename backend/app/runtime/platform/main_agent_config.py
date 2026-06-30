"""主 Agent 配置 shim — 实际实现已迁移至 Facade 层。

原问题：runtime/platform/main_agent_config.py 和 endpoints/agent.py 各有一套
_load/_save/_DEFAULT_MAIN_AGENT_CONFIG 读写同一 main_agent.json，为重复代码 bug。
已统一委托 facades/main_agent_config.py，存储到 config_items 表。
"""
from app.infrastructure.database.facades.main_agent_config import (
    load_luominest_main_agent_config,
    resolve_main_agent_provider_model,
    save_luominest_main_agent_config,
)

__all__ = [
    "load_luominest_main_agent_config",
    "save_luominest_main_agent_config",
    "resolve_main_agent_provider_model",
]
