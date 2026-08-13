"""统一主 Agent 配置 Facade — 合并原重复代码。

原问题：
- runtime/platform/main_agent_config.py 和 endpoints/agent.py 各有一套
  _load/_save/_DEFAULT_MAIN_AGENT_CONFIG，读写同一 main_agent.json 文件，
  但默认 system_prompt 不同（"平台路由器" vs "Live2D 皮套"）。

解决方案：
- 统一存储到 config_items 表的 main_agent.* 命名空间（通过 lumi_config_store）
- 单一默认值（合并两个 prompt 的要点）
- 统一入口：load_luominest_main_agent_config / save_luominest_main_agent_config

2026-08 全局模型统一重构：
- 主 Agent 不再拥有独立的 provider/model —— 模型选择统一走全局主模型
  （config_items['model_config']），见 model_selection.resolve_global_provider_model。
- 本配置仅保留"人设"字段：system_prompt / color / avatar；
  temperature/max_tokens 统一读全局生成参数（get_global_generation_defaults）。
- 存量数据中残留的 provider/model/temperature/max_tokens 字段不再被读取，
  由启动迁移幂等清理。
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
    """加载主 Agent 人设配置（system_prompt / color / avatar）。

    注意：返回 dict 中的 provider/model/temperature/max_tokens 为历史遗留字段，
    仅为兼容旧调用方保留默认值，不再作为模型选择的权威来源。
    """
    stored = lumi_config_store.get(_CONFIG_KEY)
    if stored is None or not isinstance(stored, dict):
        return dict(_DEFAULT_MAIN_AGENT_CONFIG)
    # 合并默认值（确保新字段有默认值）
    merged = dict(_DEFAULT_MAIN_AGENT_CONFIG)
    merged.update(stored)
    return merged


def save_luominest_main_agent_config(config: dict) -> None:
    """保存主 Agent 人设配置（统一入口）。"""
    lumi_config_store.set(_CONFIG_KEY, config)
    logger.success("[MainAgentConfig] Saved to config_items")


def resolve_main_agent_provider_model() -> tuple[str, str]:
    """解析主 Agent 实际使用的 provider 和 model。

    2026-08 全局模型统一后：主 Agent 不再有独立模型，直接委托全局主模型
    （config_items['model_config'] → 运行时镜像 llm_adapter.default_provider /
    settings.LLM_DEFAULT_MODEL）。保留本函数签名以兼容平台路由等既有调用方。
    """
    from app.infrastructure.database.facades.model_selection import resolve_global_provider_model

    return resolve_global_provider_model()
