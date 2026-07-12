"""统一主 Agent 配置 Facade — 合并原重复代码。

原问题：
- runtime/platform/main_agent_config.py 和 endpoints/agent.py 各有一套
  _load/_save/_DEFAULT_MAIN_AGENT_CONFIG，读写同一 main_agent.json 文件，
  但默认 system_prompt 不同（"平台路由器" vs "Live2D 皮套"）。

解决方案：
- 统一存储到 config_items 表的 main_agent.* 命名空间（通过 lumi_config_store）
- 单一默认值（合并两个 prompt 的要点）
- 统一入口：load_luominest_main_agent_config / save_luominest_main_agent_config
"""
from loguru import logger

from app.infrastructure.database.config_store import lumi_config_store


_CONFIG_KEY = "main_agent.config"

_DEFAULT_MAIN_AGENT_CONFIG = {
    "provider": "",
    "model": "",
    "system_prompt": (
        "你是 LuomiNest 的主控智能体，负责与用户通过多平台进行交互并控制 Live2D 皮套的行为和表情。"
        "你需要根据对话内容做出恰当的情感反应，保持角色一致性，并善用长期记忆了解用户偏好。"
        "你的回答应该简洁自然，适合通过皮套形象表达。"
    ),
    "temperature": 0.7,
    "max_tokens": 4096,
}


def load_luominest_main_agent_config() -> dict:
    """加载主 Agent 配置（统一入口，供工作台与平台路由器共享）。"""
    stored = lumi_config_store.get(_CONFIG_KEY)
    if stored is None or not isinstance(stored, dict):
        return dict(_DEFAULT_MAIN_AGENT_CONFIG)
    # 合并默认值（确保新字段有默认值）
    merged = dict(_DEFAULT_MAIN_AGENT_CONFIG)
    merged.update(stored)
    return merged


def save_luominest_main_agent_config(config: dict) -> None:
    """保存主 Agent 配置（统一入口）。"""
    lumi_config_store.set(_CONFIG_KEY, config)
    logger.success("[MainAgentConfig] Saved to config_items")


def resolve_main_agent_provider_model() -> tuple[str, str]:
    """解析主 Agent 实际使用的 provider 和 model。

    优先使用 main_agent 配置中的值，为空则回退到 llm_adapter 默认值。
    若默认 provider 也不可用，返回空字符串而非抛异常，避免接口 502。
    """
    from app.runtime.provider.llm.adapter import llm_adapter

    config = load_luominest_main_agent_config()
    provider = config.get("provider") or getattr(llm_adapter, "default_provider", "")
    model = config.get("model", "")

    # 尝试用配置的 provider 解析 model
    try:
        provider_inst = llm_adapter.get_provider(provider)
        model = model or provider_inst.default_model
        return provider, model
    except Exception as e:
        logger.debug(f"[MainAgentConfig] Configured provider '{provider}' unavailable: {e}")

    # 配置的 provider 不可用，尝试任意一个已注册的 provider
    for provider_info in llm_adapter.list_providers():
        fallback_provider = provider_info.get("id", "")
        if not fallback_provider:
            continue
        try:
            provider_inst = llm_adapter.get_provider(fallback_provider)
            return fallback_provider, model or provider_inst.default_model
        except Exception as e:
            logger.debug(f"[MainAgentConfig] Fallback provider '{fallback_provider}' unavailable: {e}")
            continue

    # 所有 provider 都不可用：返回空值，让前端展示"未配置"状态
    logger.warning(
        "[MainAgentConfig] No LLM provider available. "
        "Please configure at least one provider in settings."
    )
    return "", model
