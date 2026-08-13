import time
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, ConfigDict
from loguru import logger

from app.api.v1.deps import get_llm_adapter
from app.runtime.provider.llm.adapter import _create_provider_from_config
from app.runtime.provider.llm.adapters.chat_completions import PROVIDER_TEMPLATES
from app.runtime.provider.llm.capabilities import get_capabilities
from app.runtime.provider.llm.model_context_data import infer_max_context_tokens
from app.infrastructure.database.repositories.provider_model_repository import ProviderModelRepository
from app.core.config import settings
from app.core.context import invalidate_context_cache
from app.core.utils import ok
from app.core.exceptions import NotFoundError, ValidationError

router = APIRouter(prefix="/models", tags=["models"])


def _load_model_config() -> dict:
    """从 config_items['model_config'] 加载模型配置。"""
    # 路由与 lifespan 共用，无法 Depends 注入，经容器取同一门面单例
    from app.core.container import container
    saved = container.lumi_config_store.get("model_config", {})
    return saved if isinstance(saved, dict) else {}


def _save_model_config(config: dict):
    """保存模型配置到 config_items['model_config']。"""
    # 路由与 lifespan 共用，无法 Depends 注入，经容器取同一门面单例
    from app.core.container import container
    try:
        container.lumi_config_store.set("model_config", config)
        logger.success("[ModelConfig] Saved to config_items['model_config']")
    except Exception as e:
        logger.error(f"[ModelConfig] Failed to save: {e}")


def apply_model_config_from_db():
    """从 DB 应用 model_config 到运行时（settings + llm_adapter.default_provider + reasoner_*）。

    替代原模块级 import-time 调用，由 lifespan 在 DB init + 迁移后显式调用。
    调用顺序需在 llm_adapter.ensure_providers_loaded() 之后，以保证 model_config 的
    default_provider 覆盖 provider 配置中的 is_default 标志（与原行为一致）。
    """
    # lifespan 上下文（非路由）无法 Depends 注入，经容器取同一门面单例
    from app.core.container import container
    adapter = container.llm_adapter

    saved = _load_model_config()
    if not saved:
        return
    if saved.get("default_provider"):
        adapter.default_provider = saved["default_provider"]
    if saved.get("default_model"):
        settings.LLM_DEFAULT_MODEL = saved["default_model"]
    if saved.get("default_temperature") is not None:
        settings.LLM_DEFAULT_TEMPERATURE = saved["default_temperature"]
    if saved.get("default_max_tokens") is not None:
        settings.LLM_DEFAULT_MAX_TOKENS = saved["default_max_tokens"]
    if saved.get("default_top_p") is not None:
        settings.LLM_DEFAULT_TOP_P = saved["default_top_p"]
    # 应用推理模型路由配置到 adapter 内存
    adapter.apply_reasoner_config(saved)
    logger.info(f"[ModelConfig] Applied saved config: provider={saved.get('default_provider')}, model={saved.get('default_model')}")


# ── 全局模型选择统一写入助手（2026-08 全局模型统一重构）──
# 所有"切换主模型"的入口（设置页模型设置 / 工作台模型下拉 / 主智能体面板）
# 都必须经此助手写入，保证：运行时镜像同步 + 持久化 + 缓存失效，三者原子完成。

def apply_global_model_selection(adapter, provider: str | None = None, model: str | None = None) -> list[str]:
    """将全局主模型选择应用到运行时镜像并持久化。

    Args:
        adapter: LLMAdapter 实例（通常为 container.llm_adapter）
        provider: 新的默认供应商（None 表示不修改）
        model: 新的默认模型（None 表示不修改）

    Returns:
        实际更新的字段列表（用于日志/响应）
    """
    updated: list[str] = []
    if provider is not None:
        adapter.default_provider = provider
        updated.append("default_provider")
    if model is not None:
        settings.LLM_DEFAULT_MODEL = model
        updated.append("default_model")
    if not updated:
        return updated

    existing = _load_model_config()
    config_to_save = dict(existing) if isinstance(existing, dict) else {}
    config_to_save["default_provider"] = adapter.default_provider
    config_to_save["default_model"] = settings.LLM_DEFAULT_MODEL
    _save_model_config(config_to_save)
    adapter.apply_reasoner_config(config_to_save)
    # 切换主模型后失效上下文缓存（与 PATCH /models/config 行为一致）
    invalidate_context_cache()
    logger.success(f"[ModelConfig] Global model selection updated: {updated}")
    return updated


def apply_global_generation_defaults(
    temperature: float | None = None,
    max_tokens: int | None = None,
    top_p: float | None = None,
) -> list[str]:
    """将全局生成参数（temperature/max_tokens/top_p）应用到运行时并持久化。"""
    updated: list[str] = []
    if temperature is not None:
        settings.LLM_DEFAULT_TEMPERATURE = temperature
        updated.append("default_temperature")
    if max_tokens is not None:
        settings.LLM_DEFAULT_MAX_TOKENS = max_tokens
        updated.append("default_max_tokens")
    if top_p is not None:
        settings.LLM_DEFAULT_TOP_P = top_p
        updated.append("default_top_p")
    if not updated:
        return updated

    existing = _load_model_config()
    config_to_save = dict(existing) if isinstance(existing, dict) else {}
    config_to_save["default_temperature"] = settings.LLM_DEFAULT_TEMPERATURE
    config_to_save["default_max_tokens"] = settings.LLM_DEFAULT_MAX_TOKENS
    config_to_save["default_top_p"] = settings.LLM_DEFAULT_TOP_P
    _save_model_config(config_to_save)
    logger.success(f"[ModelConfig] Global generation defaults updated: {updated}")
    return updated


class ProviderCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str = ""
    vendor: str = "openai_compatible"
    base_url: str = Field(alias="baseUrl", default="")
    api_key: str = Field(alias="apiKey", default="")
    default_model: str = Field(alias="defaultModel", default="")
    is_default: bool = Field(alias="isDefault", default=False)
    selected_models: list[str] = Field(alias="selectedModels", default_factory=list)
    protocol: str = "auto"


class ProviderUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = None
    vendor: str | None = None
    base_url: str | None = Field(alias="baseUrl", default=None)
    api_key: str | None = Field(alias="apiKey", default=None)
    default_model: str | None = Field(alias="defaultModel", default=None)
    is_default: bool | None = Field(alias="isDefault", default=None)
    selected_models: list[str] | None = Field(alias="selectedModels", default=None)
    protocol: str | None = None


class ProviderResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    id: str
    name: str
    vendor: str
    base_url: str = Field(alias="baseUrl")
    api_key_prefix: str = Field(alias="apiKeyPrefix", default="")
    api_key_set: bool = Field(alias="apiKeySet", default=False)
    default_model: str = Field(alias="defaultModel")
    is_default: bool = Field(alias="isDefault")
    selected_models: list[str] = Field(alias="selectedModels", default_factory=list)
    protocol: str = "auto"
    models: list[dict] = []


class ProviderTestRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    vendor: str = "openai_compatible"
    base_url: str = Field(alias="baseUrl", default="")
    api_key: str = Field(alias="apiKey", default="")
    default_model: str = Field(alias="defaultModel", default="")


class ProviderTemplateResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    id: str
    name: str
    vendor: str
    base_url: str = Field(alias="baseUrl")
    default_model: str = Field(alias="defaultModel")
    description: str


class ModelConfigUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    provider: str | None = None
    model: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(alias="maxTokens", default=None, ge=1, le=128_000)
    top_p: float | None = Field(alias="topP", default=None, ge=0.0, le=1.0)
    reasoner_provider: str | None = Field(alias="reasonerProvider", default=None)
    reasoner_model: str | None = Field(alias="reasonerModel", default=None)
    reasoner_temperature: float | None = Field(alias="reasonerTemperature", default=None, ge=0.0, le=2.0)
    reasoner_max_tokens: int | None = Field(alias="reasonerMaxTokens", default=None, ge=1, le=128_000)
    reasoner_effort: str | None = Field(alias="reasonerEffort", default=None)
    tts_provider: str | None = Field(alias="ttsProvider", default=None)
    tts_model: str | None = Field(alias="ttsModel", default=None)
    tts_voice: str | None = Field(alias="ttsVoice", default=None)
    tts_speed: float | None = Field(alias="ttsSpeed", default=None, ge=0.25, le=4.0)
    stt_provider: str | None = Field(alias="sttProvider", default=None)
    stt_model: str | None = Field(alias="sttModel", default=None)
    stt_language: str | None = Field(alias="sttLanguage", default=None)
    stt_auto_send: bool | None = Field(alias="sttAutoSend", default=None)
    stt_auto_send_delay: int | None = Field(alias="sttAutoSendDelay", default=None)
    stt_engine: str | None = Field(alias="sttEngine", default=None)
    # LLM 上下文窗口与压缩配置
    context_window_size: int | None = Field(alias="contextWindowSize", default=None, ge=0, le=1_000_000)
    compression_threshold: float | None = Field(alias="compressionThreshold", default=None, ge=0.5, le=0.95)
    compression_ratio: int | None = Field(alias="compressionRatio", default=None, ge=1, le=100)
    llm_compress_enabled: bool | None = Field(alias="llmCompressEnabled", default=None)
    summary_model: str | None = Field(alias="summaryModel", default=None)
    summary_provider: str | None = Field(alias="summaryProvider", default=None)


class ProviderModelResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    id: str
    provider_id: str = Field(alias="providerId")
    model_id: str = Field(alias="modelId")
    name: str
    enabled: bool
    max_context_tokens: int = Field(alias="maxContextTokens")


class ProviderModelUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    enabled: bool | None = None
    max_context_tokens: int | None = Field(alias="maxContextTokens", default=None, ge=0, le=2_000_000)


# ── ProviderModel 辅助函数 ──

_provider_model_repo_instance: ProviderModelRepository | None = None


def _get_provider_model_repo() -> ProviderModelRepository:
    global _provider_model_repo_instance
    if _provider_model_repo_instance is None:
        _provider_model_repo_instance = ProviderModelRepository()
    return _provider_model_repo_instance


def _persist_provider_models(provider_id: str, models: list[dict], provider_name: str = "") -> list[dict]:
    """将 /models 返回的模型列表持久化到 provider_models 表，并推断最大上下文长度。"""
    if not models:
        return []

    repo = _get_provider_model_repo()
    default_window = 0
    try:
        caps = get_capabilities(provider_name or provider_id)
        default_window = caps.default_context_window
    except Exception:
        pass

    enriched = []
    for m in models:
        model_id = m.get("id", "")
        if not model_id:
            continue
        inferred = infer_max_context_tokens(model_id, provider_name or provider_id, default_window)
        enriched.append({
            "id": model_id,
            "name": m.get("name") or model_id,
            "max_context_tokens": inferred,
        })

    try:
        saved = repo.save_models(provider_id, enriched)
        logger.success(f"[ModelConfig] Persisted {len(saved)} models for provider={provider_id}")
        return saved
    except Exception as e:
        logger.warning(f"[ModelConfig] Failed to persist models for provider={provider_id}: {e}")
        return []


def _merge_models_with_db(provider_id: str, fetched_models: list[dict]) -> list[dict]:
    """合并 provider /models 返回与 DB 中保存的模型配置，以 DB 配置覆盖 fetched 默认值。"""
    repo = _get_provider_model_repo()
    try:
        db_models = repo.get_by_provider(provider_id)
    except Exception as e:
        logger.warning(f"[ModelConfig] Failed to load DB models for {provider_id}: {e}")
        db_models = []

    if not db_models:
        return fetched_models

    db_map = {m["model_id"]: m for m in db_models}
    merged = []
    for m in fetched_models:
        model_id = m.get("id", "")
        db_entry = db_map.get(model_id)
        if db_entry:
            merged.append({
                "id": model_id,
                "name": db_entry.get("name") or m.get("name") or model_id,
                "owned_by": m.get("owned_by", ""),
                "provider": provider_id,
                "enabled": db_entry.get("enabled", True),
                "max_context_tokens": db_entry.get("max_context_tokens", 0),
            })
        else:
            merged.append({**m, "provider": provider_id, "enabled": True, "max_context_tokens": 0})

    return merged


def _build_provider_response(provider_id: str, adapter) -> ProviderResponse:
    provider = adapter.providers.get(provider_id)
    cfg = adapter.get_provider_config(provider_id) or {}
    if not provider:
        raise NotFoundError(f"Provider [{provider_id}] not found")

    # 从凭证仓储取前缀（不暴露密文/明文）
    api_key_prefix = ""
    try:
        adapter._ensure_repos()
        creds = adapter._credential_repo.list_credentials(provider_id)
        if creds:
            api_key_prefix = creds[0].get("api_key_prefix", "")
    except Exception as exc:
        logger.warning(
            "Failed to load credential prefix for provider [{}]: {}",
            provider_id,
            exc,
        )

    return ProviderResponse(
        id=provider_id,
        name=cfg.get("name", provider_id),
        vendor=cfg.get("vendor", provider.provider_name),
        base_url=getattr(provider, "base_url", ""),
        api_key_prefix=api_key_prefix,
        api_key_set=bool(api_key_prefix),
        default_model=getattr(provider, "default_model", ""),
        is_default=provider_id == adapter.default_provider,
        selected_models=cfg.get("selected_models", []),
        protocol=cfg.get("protocol") or "auto",
        models=[],
    )


@router.get("/providers/templates", response_model=list[ProviderTemplateResponse])
async def list_provider_templates():
    logger.info("[API] GET /models/providers/templates - Listing provider templates")
    result = []
    for key, tmpl in PROVIDER_TEMPLATES.items():
        result.append(ProviderTemplateResponse(
            id=tmpl["id"],
            name=tmpl["name"],
            vendor=tmpl["vendor"],
            base_url=tmpl["base_url"],
            default_model=tmpl["default_model"],
            description=tmpl["description"],
        ))
    logger.success(f"[API] GET /models/providers/templates - Success: returned {len(result)} templates")
    return result


@router.get("/providers", response_model=list[ProviderResponse])
async def list_providers(adapter=Depends(get_llm_adapter)):
    logger.info("[API] GET /models/providers - Listing all providers")
    providers_info = adapter.list_providers()
    result = []
    for p in providers_info:
        result.append(ProviderResponse(
            id=p["id"],
            name=p["name"],
            vendor=p["vendor"],
            base_url=p["base_url"],
            api_key_prefix=p.get("api_key_prefix", ""),
            api_key_set=p.get("api_key_set", False),
            default_model=p["default_model"],
            is_default=p["is_default"],
            selected_models=p.get("selected_models", []),
            protocol=p.get("protocol") or "auto",
            models=[],
        ))
    logger.success(f"[API] GET /models/providers - Success: returned {len(result)} providers")
    return result


@router.post("/providers", response_model=ProviderResponse)
async def add_provider(request: ProviderCreate, adapter=Depends(get_llm_adapter)):
    logger.info(f"[API] POST /models/providers - Adding provider: id={request.id}, vendor={request.vendor}")
    if request.id in adapter.providers:
        logger.error(f"[API] POST /models/providers - Provider already exists: {request.id}")
        raise ValidationError(f"Provider [{request.id}] already exists")

    config = {
        "id": request.id,
        "name": request.name or request.id,
        "vendor": request.vendor,
        "base_url": request.base_url.rstrip("/"),
        "api_key": request.api_key,
        "default_model": request.default_model,
        "is_default": request.is_default,
        "selected_models": request.selected_models,
        "protocol": request.protocol or "auto",
    }

    provider = _create_provider_from_config(config)
    adapter.register_provider(
        name=request.id,
        provider=provider,
        config=config,
        set_default=request.is_default,
    )
    logger.success(f"[API] POST /models/providers - Provider registered: id={request.id}, base_url={provider.base_url}")

    models = []
    try:
        models = await provider.list_models()
        logger.debug(f"[API] POST /models/providers - Fetched {len(models)} models for {request.id}")
        if models:
            _persist_provider_models(request.id, models, provider_name=request.id)
            models = _merge_models_with_db(request.id, models)
    except Exception as e:
        logger.warning(f"[API] POST /models/providers - Failed to fetch models: {e}")
        # 获取失败时仍尝试从 DB 返回已保存的模型列表
        try:
            db_models = _get_provider_model_repo().get_by_provider(request.id)
            models = [
                {
                    "id": m["model_id"],
                    "name": m.get("name") or m["model_id"],
                    "enabled": m.get("enabled", True),
                    "max_context_tokens": m.get("max_context_tokens", 0),
                }
                for m in db_models
            ]
        except Exception:
            models = []

    # 从凭证仓储取前缀（register_provider 已保存凭证）
    api_key_prefix = ""
    try:
        adapter._ensure_repos()
        creds = adapter._credential_repo.list_credentials(request.id)
        if creds:
            api_key_prefix = creds[0].get("api_key_prefix", "")
    except Exception:
        pass

    return ProviderResponse(
        id=request.id,
        name=config["name"],
        vendor=config["vendor"],
        base_url=provider.base_url,
        api_key_prefix=api_key_prefix,
        api_key_set=bool(api_key_prefix),
        default_model=provider.default_model,
        is_default=request.is_default,
        selected_models=config["selected_models"],
        protocol=config["protocol"],
        models=models,
    )


@router.patch("/providers/{provider_id}", response_model=ProviderResponse)
async def update_provider(provider_id: str, request: ProviderUpdate, adapter=Depends(get_llm_adapter)):
    logger.info(f"[API] PATCH /models/providers/{provider_id} - Updating provider")
    if provider_id not in adapter.providers:
        logger.error(f"[API] PATCH /models/providers/{provider_id} - Provider not found")
        raise NotFoundError(f"Provider [{provider_id}] not found")

    existing_cfg = adapter.get_provider_config(provider_id) or {}
    updated_cfg = dict(existing_cfg)
    updated_fields = []

    if request.name is not None:
        updated_cfg["name"] = request.name
        updated_fields.append("name")
    if request.vendor is not None:
        updated_cfg["vendor"] = request.vendor
        updated_fields.append("vendor")
    if request.base_url is not None:
        updated_cfg["base_url"] = request.base_url.rstrip("/")
        updated_fields.append("base_url")
    if request.api_key is not None:
        updated_cfg["api_key"] = request.api_key
        updated_fields.append("api_key")
    if request.default_model is not None:
        updated_cfg["default_model"] = request.default_model
        updated_fields.append("default_model")
    if request.is_default is not None:
        updated_cfg["is_default"] = request.is_default
        updated_fields.append("is_default")
    if request.selected_models is not None:
        updated_cfg["selected_models"] = request.selected_models
        updated_fields.append("selected_models")
    if request.protocol is not None:
        updated_cfg["protocol"] = request.protocol or "auto"
        updated_fields.append("protocol")

    provider = _create_provider_from_config(updated_cfg)
    set_default = request.is_default if request.is_default is not None else False
    adapter.update_provider(
        name=provider_id,
        provider=provider,
        config=updated_cfg,
        set_default=set_default,
    )
    logger.success(f"[API] PATCH /models/providers/{provider_id} - Updated fields: {updated_fields}")

    return _build_provider_response(provider_id, adapter)


@router.delete("/providers/{provider_id}")
async def remove_provider(provider_id: str, adapter=Depends(get_llm_adapter)):
    logger.info(f"[API] DELETE /models/providers/{provider_id} - Removing provider")
    if provider_id not in adapter.providers:
        logger.error(f"[API] DELETE /models/providers/{provider_id} - Provider not found")
        raise NotFoundError(f"Provider [{provider_id}] not found")

    adapter.remove_provider(provider_id)
    logger.success(f"[API] DELETE /models/providers/{provider_id} - Provider removed")
    return ok({"deleted": True, "id": provider_id})


@router.get("/providers/{provider_id}/models")
async def list_provider_models(provider_id: str, adapter=Depends(get_llm_adapter)):
    logger.info(f"[API] GET /models/providers/{provider_id}/models - Listing models")
    start_time = time.time()
    try:
        fetched = await adapter.list_models(provider_id)
        if fetched:
            _persist_provider_models(provider_id, fetched, provider_name=provider_id)
            models = _merge_models_with_db(provider_id, fetched)
        else:
            # 远端未返回模型时，回退到数据库中已保存的列表
            db_models = _get_provider_model_repo().get_by_provider(provider_id)
            models = [
                {
                    "id": m["model_id"],
                    "name": m.get("name") or m["model_id"],
                    "enabled": m.get("enabled", True),
                    "max_context_tokens": m.get("max_context_tokens", 0),
                }
                for m in db_models
            ]
        elapsed = time.time() - start_time
        logger.success(f"[API] GET /models/providers/{provider_id}/models - Success: {len(models)} models, elapsed={elapsed:.2f}s")
        return ok(models)
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[API] GET /models/providers/{provider_id}/models - Failed: elapsed={elapsed:.2f}s, error={e}")
        # 拉取失败时返回 DB 中已保存的模型，避免前端崩溃
        try:
            db_models = _get_provider_model_repo().get_by_provider(provider_id)
            models = [
                {
                    "id": m["model_id"],
                    "name": m.get("name") or m["model_id"],
                    "enabled": m.get("enabled", True),
                    "max_context_tokens": m.get("max_context_tokens", 0),
                }
                for m in db_models
            ]
            return ok(models)
        except Exception:
            raise


@router.post("/providers/test")
async def test_provider(request: ProviderTestRequest, adapter=Depends(get_llm_adapter)):
    """检测供应商 API/TOKEN 是否可用：临时构造 provider 调用 list_models，不注册到全局。"""
    logger.info(f"[API] POST /models/providers/test - Testing vendor={request.vendor}, base_url={request.base_url}")
    start_time = time.time()
    config = {
        "id": "test",
        "vendor": request.vendor,
        "base_url": request.base_url.rstrip("/"),
        "api_key": request.api_key,
        "default_model": request.default_model,
    }
    result = await adapter.test_provider(config)
    elapsed = time.time() - start_time
    if result["success"]:
        logger.success(f"[API] POST /models/providers/test - Success: {len(result['models'])} models, elapsed={elapsed:.2f}s")
    else:
        logger.warning(f"[API] POST /models/providers/test - Failed: elapsed={elapsed:.2f}s, error={result['error']}")
    return ok(result)


@router.get("/list")
async def list_all_models(adapter=Depends(get_llm_adapter)):
    logger.info("[API] GET /models/list - Listing all models")
    start_time = time.time()
    fetched = await adapter.list_models()
    if fetched:
        # 按 provider 分组持久化
        by_provider: dict[str, list[dict]] = {}
        for m in fetched:
            provider_id = m.get("provider", "")
            if not provider_id:
                continue
            by_provider.setdefault(provider_id, []).append(m)
        for provider_id, group in by_provider.items():
            try:
                _persist_provider_models(provider_id, group, provider_name=provider_id)
            except Exception as e:
                logger.warning(f"[API] GET /models/list - Failed to persist models for {provider_id}: {e}")
        # 合并 DB 配置
        merged = []
        for m in fetched:
            provider_id = m.get("provider", "")
            merged.extend(_merge_models_with_db(provider_id, [m]))
        models = merged
    else:
        # 回退到数据库中已保存的全部模型
        db_models = _get_provider_model_repo().get_all()
        models = [
            {
                "id": m["model_id"],
                "name": m.get("name") or m["model_id"],
                "provider": m["provider_id"],
                "enabled": m.get("enabled", True),
                "max_context_tokens": m.get("max_context_tokens", 0),
            }
            for m in db_models
        ]
    elapsed = time.time() - start_time
    logger.success(f"[API] GET /models/list - Success: {len(models)} models, elapsed={elapsed:.2f}s")
    return ok(models)


@router.get("/context-overrides", response_model=list[ProviderModelResponse])
async def list_context_overrides(adapter=Depends(get_llm_adapter)):
    """返回所有已保存的模型上下文覆盖配置（按模型维度）。"""
    logger.info("[API] GET /models/context-overrides - Listing context overrides")
    try:
        repo = _get_provider_model_repo()
        rows = repo.get_all()
        result = []
        for row in rows:
            # 若 DB 中 max_context_tokens 为 0，则重新推断一次作为展示默认值
            max_tokens = row.get("max_context_tokens", 0) or 0
            if max_tokens <= 0:
                max_tokens = infer_max_context_tokens(
                    row.get("model_id", ""),
                    row.get("provider_id", ""),
                )
            result.append(ProviderModelResponse(
                id=row["id"],
                provider_id=row["provider_id"],
                model_id=row["model_id"],
                name=row.get("name") or row["model_id"],
                enabled=row.get("enabled", True),
                max_context_tokens=max_tokens,
            ))
        logger.success(f"[API] GET /models/context-overrides - Success: {len(result)} overrides")
        return result
    except Exception as e:
        logger.error(f"[API] GET /models/context-overrides - Failed: {e}")
        return []


@router.patch("/context-overrides/{provider_id}/{model_id}", response_model=ProviderModelResponse)
async def update_context_override(
    provider_id: str,
    model_id: str,
    request: ProviderModelUpdate,
    adapter=Depends(get_llm_adapter),
):
    """更新指定模型的启用状态与最大上下文长度。"""
    logger.info(f"[API] PATCH /models/context-overrides/{provider_id}/{model_id} - Updating context override")
    try:
        repo = _get_provider_model_repo()
        updates: dict = {}
        if request.enabled is not None:
            updates["enabled"] = request.enabled
        if request.max_context_tokens is not None:
            updates["max_context_tokens"] = request.max_context_tokens
        updated = repo.update_by_provider_model(provider_id, model_id, updates)
        if updated is None:
            raise NotFoundError(f"Model [{provider_id}/{model_id}] not found")
        logger.success(f"[API] PATCH /models/context-overrides/{provider_id}/{model_id} - Updated: {updates}")
        return ProviderModelResponse(
            id=updated["id"],
            provider_id=updated["provider_id"],
            model_id=updated["model_id"],
            name=updated.get("name") or updated["model_id"],
            enabled=updated.get("enabled", True),
            max_context_tokens=updated.get("max_context_tokens", 0),
        )
    except NotFoundError:
        raise
    except Exception as e:
        logger.error(f"[API] PATCH /models/context-overrides/{provider_id}/{model_id} - Failed: {e}")
        raise


@router.get("/config")
async def get_model_config(adapter=Depends(get_llm_adapter)):
    logger.info("[API] GET /models/config - Getting model config")
    config = {
        "default_provider": adapter.default_provider,
        "default_model": settings.LLM_DEFAULT_MODEL,
        "default_temperature": settings.LLM_DEFAULT_TEMPERATURE,
        "default_max_tokens": settings.LLM_DEFAULT_MAX_TOKENS,
        "default_top_p": settings.LLM_DEFAULT_TOP_P,
    }
    # 返回扩展字段（reasoner_*/tts_*/stt_*），从 model_config 读取
    saved = _load_model_config()
    for field in ["reasoner_provider", "reasoner_model", "reasoner_temperature",
                   "reasoner_max_tokens", "reasoner_effort", "tts_provider",
                   "tts_model", "tts_voice", "tts_speed", "stt_provider",
                   "stt_model", "stt_language", "stt_auto_send", "stt_auto_send_delay",
                   "stt_engine", "context_window_size", "compression_threshold",
                   "compression_ratio", "llm_compress_enabled", "summary_model", "summary_provider"]:
        if field in saved:
            config[field] = saved[field]
    # 上下文配置也可从 settings 读取默认值
    for field in ["context_window_size", "compression_threshold", "compression_ratio", "llm_compress_enabled", "summary_model", "summary_provider"]:
        if field not in config:
            settings_key = {
                "context_window_size": "LLM_CONTEXT_WINDOW_SIZE",
                "compression_threshold": "LLM_COMPRESSION_THRESHOLD",
                "compression_ratio": "LLM_COMPRESSION_RATIO",
                "llm_compress_enabled": "LLM_COMPRESS_ENABLED",
                "summary_model": "LLM_SUMMARY_MODEL",
                "summary_provider": "LLM_SUMMARY_PROVIDER",
            }.get(field)
            if settings_key:
                config[field] = getattr(settings, settings_key)
    logger.success(f"[API] GET /models/config - Success: provider={config['default_provider']}, model={config['default_model']}")
    return ok(config)


@router.patch("/config")
async def update_model_config(request: ModelConfigUpdate, adapter=Depends(get_llm_adapter)):
    logger.info(f"[API] PATCH /models/config - Updating model config")
    updated_fields = []

    if request.provider is not None:
        adapter.default_provider = request.provider
        updated_fields.append("provider")
    if request.model is not None:
        settings.LLM_DEFAULT_MODEL = request.model
        updated_fields.append("model")
    if request.temperature is not None:
        settings.LLM_DEFAULT_TEMPERATURE = request.temperature
        updated_fields.append("temperature")
    if request.max_tokens is not None:
        settings.LLM_DEFAULT_MAX_TOKENS = request.max_tokens
        updated_fields.append("max_tokens")
    if request.top_p is not None:
        settings.LLM_DEFAULT_TOP_P = request.top_p
        updated_fields.append("top_p")
    if request.reasoner_provider is not None:
        updated_fields.append("reasoner_provider")
    if request.reasoner_model is not None:
        updated_fields.append("reasoner_model")
    if request.reasoner_temperature is not None:
        updated_fields.append("reasoner_temperature")
    if request.reasoner_max_tokens is not None:
        updated_fields.append("reasoner_max_tokens")
    if request.reasoner_effort is not None:
        updated_fields.append("reasoner_effort")
    if request.tts_provider is not None:
        updated_fields.append("tts_provider")
    if request.tts_model is not None:
        updated_fields.append("tts_model")
    if request.tts_voice is not None:
        updated_fields.append("tts_voice")
    if request.tts_speed is not None:
        updated_fields.append("tts_speed")
    if request.stt_provider is not None:
        updated_fields.append("stt_provider")
    if request.stt_model is not None:
        updated_fields.append("stt_model")
    if request.stt_language is not None:
        updated_fields.append("stt_language")
    if request.stt_auto_send is not None:
        updated_fields.append("stt_auto_send")
    if request.stt_auto_send_delay is not None:
        updated_fields.append("stt_auto_send_delay")
    if request.stt_engine is not None:
        updated_fields.append("stt_engine")
    # 上下文窗口与压缩配置
    if request.context_window_size is not None:
        settings.LLM_CONTEXT_WINDOW_SIZE = request.context_window_size
        updated_fields.append("context_window_size")
    if request.compression_threshold is not None:
        settings.LLM_COMPRESSION_THRESHOLD = request.compression_threshold
        updated_fields.append("compression_threshold")
    if request.compression_ratio is not None:
        settings.LLM_COMPRESSION_RATIO = request.compression_ratio
        settings.LLM_SUMMARY_TARGET_RATIO = request.compression_ratio / 100.0
        updated_fields.append("compression_ratio")
    if request.llm_compress_enabled is not None:
        settings.LLM_COMPRESS_ENABLED = request.llm_compress_enabled
        updated_fields.append("llm_compress_enabled")
    if request.summary_model is not None:
        settings.LLM_SUMMARY_MODEL = request.summary_model
        updated_fields.append("summary_model")
    if request.summary_provider is not None:
        settings.LLM_SUMMARY_PROVIDER = request.summary_provider
        updated_fields.append("summary_provider")

    existing_config = _load_model_config()
    config_to_save = {
        "default_provider": adapter.default_provider,
        "default_model": settings.LLM_DEFAULT_MODEL,
        "default_temperature": settings.LLM_DEFAULT_TEMPERATURE,
        "default_max_tokens": settings.LLM_DEFAULT_MAX_TOKENS,
        "default_top_p": settings.LLM_DEFAULT_TOP_P,
    }
    # 保存扩展配置字段
    for field in ["reasoner_provider", "reasoner_model", "reasoner_temperature",
                   "reasoner_max_tokens", "reasoner_effort", "tts_provider",
                   "tts_model", "tts_voice", "tts_speed", "stt_provider",
                   "stt_model", "stt_language", "stt_auto_send", "stt_auto_send_delay",
                   "stt_engine", "context_window_size", "compression_threshold",
                   "compression_ratio", "llm_compress_enabled", "summary_model", "summary_provider"]:
        val = getattr(request, field, None)
        if val is not None:
            config_to_save[field] = val
        elif field in existing_config:
            config_to_save[field] = existing_config[field]
    _save_model_config(config_to_save)

    # 应用 reasoner_* 到 adapter 内存（路由决策依赖）
    adapter.apply_reasoner_config(config_to_save)

    logger.success(f"[API] PATCH /models/config - Updated fields: {updated_fields}")
    invalidate_context_cache()  # 清空所有缓存（可能改了默认 provider/model）
    return {
        "error": None,
        "data": {
            "default_provider": adapter.default_provider,
            "default_model": settings.LLM_DEFAULT_MODEL,
            "default_temperature": settings.LLM_DEFAULT_TEMPERATURE,
            "default_max_tokens": settings.LLM_DEFAULT_MAX_TOKENS,
            "default_top_p": settings.LLM_DEFAULT_TOP_P,
        }
    }
