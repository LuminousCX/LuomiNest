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
    """
    from app.runtime.provider.llm.adapter import llm_adapter

    config = load_luominest_main_agent_config()
    provider = config.get("provider") or llm_adapter.default_provider
    try:
        provider_inst = llm_adapter.get_provider(provider)
        model = config.get("model") or provider_inst.default_model
    except Exception:
        provider = llm_adapter.default_provider
        provider_inst = llm_adapter.get_provider(provider)
        model = provider_inst.default_model
    return provider, model
