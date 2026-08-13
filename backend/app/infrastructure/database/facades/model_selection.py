"""全局模型选择 Facade — 软件级"主模型"唯一权威解析入口。

架构约定（2026-08 全局模型统一重构）：
- 唯一权威源：config_items['model_config'] 的 default_provider/default_model
  （设置页"模型设置"写入，启动时经 apply_model_config_from_db 同步到
  llm_adapter.default_provider 与 settings.LLM_DEFAULT_MODEL 运行时镜像）。
- 所有对话入口（工作台 / 对话页 / 平台接入 / 皮套工坊 / 桌面宠物）与
  记忆中枢统一通过本 Facade 解析主模型，不再各自维护 provider/model 副本。
- 推理模型（reasoner_*）仅由工作台专业模式（standard/ultra）按轮路由，
  不属于"主模型"，不在本 Facade 范围内。
"""
from loguru import logger


def resolve_global_provider_model() -> tuple[str, str]:
    """解析全局主模型实际使用的 provider 和 model。

    解析链（与洋葱架构"本地存储为权威源"一致）：
    1. 运行时镜像 llm_adapter.default_provider（由 model_config 同步而来）
    2. settings.LLM_DEFAULT_MODEL（由 model_config.default_model 同步而来）
    3. provider 不可用时回退到任意已注册 provider
    4. 全部不可用：返回空字符串而非抛异常，避免接口 502
    """
    from app.core.config import settings
    from app.runtime.provider.llm.adapter import llm_adapter

    provider = getattr(llm_adapter, "default_provider", "") or ""
    model = getattr(settings, "LLM_DEFAULT_MODEL", "") or ""

    try:
        provider_inst = llm_adapter.get_provider(provider)
        return provider, model or provider_inst.default_model
    except Exception as e:
        logger.debug(f"[ModelSelection] Global provider '{provider}' unavailable: {e}")

    # 配置的 provider 不可用，尝试任意已注册 provider
    for provider_info in llm_adapter.list_providers():
        fallback_provider = provider_info.get("id", "")
        if not fallback_provider:
            continue
        try:
            provider_inst = llm_adapter.get_provider(fallback_provider)
            return fallback_provider, model or provider_inst.default_model
        except Exception as e:
            logger.debug(f"[ModelSelection] Fallback provider '{fallback_provider}' unavailable: {e}")
            continue

    logger.warning(
        "[ModelSelection] No LLM provider available. "
        "Please configure at least one provider in settings."
    )
    return "", model


def get_global_generation_defaults() -> tuple[float, int]:
    """全局生成参数（temperature / max_tokens），供平台路由等场景复用。"""
    from app.core.config import settings

    return (
        getattr(settings, "LLM_DEFAULT_TEMPERATURE", 0.7),
        getattr(settings, "LLM_DEFAULT_MAX_TOKENS", 4096),
    )
