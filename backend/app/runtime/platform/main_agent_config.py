import json
import os
from loguru import logger
from app.core.config import settings

_CONFIG_DIR = os.path.join(settings.DATA_DIR)
_MAIN_AGENT_CONFIG_FILE = os.path.join(_CONFIG_DIR, "main_agent.json")

_DEFAULT_MAIN_AGENT_CONFIG = {
    "provider": "",
    "model": "",
    "system_prompt": "你是 LuomiNest 的主控智能体，负责与用户通过多平台进行交互。你需要根据对话内容做出恰当的回应，保持角色一致性，并善用长期记忆了解用户偏好。",
    "temperature": 0.7,
    "max_tokens": 4096,
}


def _ensure_config_dir() -> None:
    os.makedirs(_CONFIG_DIR, exist_ok=True)


def load_luominest_main_agent_config() -> dict:
    """加载主 Agent 配置（平台路由器复用，与工作台主 Agent 共享）。"""
    _ensure_config_dir()
    if not os.path.exists(_MAIN_AGENT_CONFIG_FILE):
        return dict(_DEFAULT_MAIN_AGENT_CONFIG)
    try:
        with open(_MAIN_AGENT_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"[MainAgentConfig] Failed to load: {e}")
        return dict(_DEFAULT_MAIN_AGENT_CONFIG)


def resolve_main_agent_provider_model() -> tuple[str, str]:
    """解析主 Agent 实际使用的 provider 和 model。

    优先使用 main_agent.json 中的配置，为空则回退到 llm_adapter 默认值。
    若默认 provider 也不可用，返回空字符串而非抛异常，避免 /platforms/main_agent 接口 502。
    """
    from app.runtime.provider.llm.adapter import llm_adapter

    config = load_luominest_main_agent_config()
    provider = config.get("provider") or llm_adapter.default_provider
    model = config.get("model", "")

    # 尝试用配置的 provider 解析 model
    try:
        provider_inst = llm_adapter.get_provider(provider)
        model = model or provider_inst.default_model
        return provider, model
    except Exception:
        pass

    # 配置的 provider 不可用，尝试任意一个已注册的 provider
    for provider_info in llm_adapter.list_providers():
        fallback_provider = provider_info.get("id", "")
        if not fallback_provider:
            continue
        try:
            provider_inst = llm_adapter.get_provider(fallback_provider)
            return fallback_provider, model or provider_inst.default_model
        except Exception:
            continue

    # 所有 provider 都不可用：返回空值，让前端展示"未配置"状态
    logger.warning(
        "[MainAgentConfig] No LLM provider available. "
        "Please configure at least one provider in settings."
    )
    return "", model
