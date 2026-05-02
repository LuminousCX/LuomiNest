import time
import json
import os
from fastapi import APIRouter
from pydantic import BaseModel, Field, ConfigDict
from loguru import logger

from app.runtime.provider.llm.adapter import llm_adapter, _create_provider_from_config
from app.runtime.provider.llm.providers import PROVIDER_TEMPLATES
from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError

router = APIRouter(prefix="/models", tags=["models"])

MODEL_CONFIG_FILE = os.path.join(settings.DATA_DIR, "model_config.json")


def _load_model_config() -> dict:
    if not os.path.exists(MODEL_CONFIG_FILE):
        return {}
    try:
        with open(MODEL_CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"[ModelConfig] Failed to load: {e}")
        return {}


def _save_model_config(config: dict):
    os.makedirs(os.path.dirname(MODEL_CONFIG_FILE), exist_ok=True)
    try:
        with open(MODEL_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        logger.success(f"[ModelConfig] Saved to {MODEL_CONFIG_FILE}")
    except Exception as e:
        logger.error(f"[ModelConfig] Failed to save: {e}")


def _apply_model_config():
    saved = _load_model_config()
    if not saved:
        return
    if saved.get("default_provider"):
        llm_adapter.default_provider = saved["default_provider"]
    if saved.get("default_model"):
        settings.LLM_DEFAULT_MODEL = saved["default_model"]
    if saved.get("default_temperature") is not None:
        settings.LLM_DEFAULT_TEMPERATURE = saved["default_temperature"]
    if saved.get("default_max_tokens") is not None:
        settings.LLM_DEFAULT_MAX_TOKENS = saved["default_max_tokens"]
    if saved.get("default_top_p") is not None:
        settings.LLM_DEFAULT_TOP_P = saved["default_top_p"]
    logger.info(f"[ModelConfig] Applied saved config: provider={saved.get('default_provider')}, model={saved.get('default_model')}")


_apply_model_config()


class ProviderCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str = ""
    vendor: str = "openai_compatible"
    base_url: str = Field(alias="baseUrl", default="")
    api_key: str = Field(alias="apiKey", default="")
    default_model: str = Field(alias="defaultModel", default="")
    is_default: bool = Field(alias="isDefault", default=False)


class ProviderUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = None
    vendor: str | None = None
    base_url: str | None = Field(alias="baseUrl", default=None)
    api_key: str | None = Field(alias="apiKey", default=None)
    default_model: str | None = Field(alias="defaultModel", default=None)
    is_default: bool | None = Field(alias="isDefault", default=None)


class ProviderResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    id: str
    name: str
    vendor: str
    base_url: str = Field(alias="baseUrl")
    api_key_set: bool = Field(alias="apiKeySet")
    default_model: str = Field(alias="defaultModel")
    is_default: bool = Field(alias="isDefault")
    models: list[dict] = []


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
    temperature: float | None = None
    max_tokens: int | None = Field(alias="maxTokens", default=None)
    top_p: float | None = Field(alias="topP", default=None)
    reasoner_provider: str | None = Field(alias="reasonerProvider", default=None)
    reasoner_model: str | None = Field(alias="reasonerModel", default=None)
    reasoner_temperature: float | None = Field(alias="reasonerTemperature", default=None)
    reasoner_max_tokens: int | None = Field(alias="reasonerMaxTokens", default=None)
    reasoner_effort: str | None = Field(alias="reasonerEffort", default=None)
    tts_provider: str | None = Field(alias="ttsProvider", default=None)
    tts_model: str | None = Field(alias="ttsModel", default=None)
    tts_voice: str | None = Field(alias="ttsVoice", default=None)
    tts_speed: float | None = Field(alias="ttsSpeed", default=None)
    stt_provider: str | None = Field(alias="sttProvider", default=None)
    stt_model: str | None = Field(alias="sttModel", default=None)
    stt_language: str | None = Field(alias="sttLanguage", default=None)
    stt_auto_send: bool | None = Field(alias="sttAutoSend", default=None)
    stt_auto_send_delay: int | None = Field(alias="sttAutoSendDelay", default=None)


def _build_provider_response(provider_id: str) -> ProviderResponse:
    provider = llm_adapter.providers.get(provider_id)
    cfg = llm_adapter.get_provider_config(provider_id) or {}
    if not provider:
        raise NotFoundError(f"Provider [{provider_id}] not found")

    api_key = getattr(provider, "api_key", "")
    return ProviderResponse(
        id=provider_id,
        name=cfg.get("name", provider_id),
        vendor=cfg.get("vendor", provider.provider_name),
        base_url=getattr(provider, "base_url", ""),
        api_key_set=bool(api_key and api_key not in ("ollama", "lmstudio", "")),
        default_model=getattr(provider, "default_model", ""),
        is_default=provider_id == llm_adapter.default_provider,
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
async def list_providers():
    logger.info("[API] GET /models/providers - Listing all providers")
    providers_info = llm_adapter.list_providers()
    result = []
    for p in providers_info:
        result.append(ProviderResponse(
            id=p["id"],
            name=p["name"],
            vendor=p["vendor"],
            base_url=p["base_url"],
            api_key_set=p["api_key_set"],
            default_model=p["default_model"],
            is_default=p["is_default"],
            models=[],
        ))
    logger.success(f"[API] GET /models/providers - Success: returned {len(result)} providers")
    return result


@router.post("/providers", response_model=ProviderResponse)
async def add_provider(request: ProviderCreate):
    logger.info(f"[API] POST /models/providers - Adding provider: id={request.id}, vendor={request.vendor}")
    if request.id in llm_adapter.providers:
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
    }

    provider = _create_provider_from_config(config)
    llm_adapter.register_provider(
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
    except Exception as e:
        logger.warning(f"[API] POST /models/providers - Failed to fetch models: {e}")

    return ProviderResponse(
        id=request.id,
        name=config["name"],
        vendor=config["vendor"],
        base_url=provider.base_url,
        api_key_set=bool(config["api_key"] and config["api_key"] not in ("ollama", "lmstudio", "")),
        default_model=provider.default_model,
        is_default=request.is_default,
        models=models,
    )


@router.patch("/providers/{provider_id}", response_model=ProviderResponse)
async def update_provider(provider_id: str, request: ProviderUpdate):
    logger.info(f"[API] PATCH /models/providers/{provider_id} - Updating provider")
    if provider_id not in llm_adapter.providers:
        logger.error(f"[API] PATCH /models/providers/{provider_id} - Provider not found")
        raise NotFoundError(f"Provider [{provider_id}] not found")

    existing_cfg = llm_adapter.get_provider_config(provider_id) or {}
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

    provider = _create_provider_from_config(updated_cfg)
    set_default = request.is_default if request.is_default is not None else False
    llm_adapter.update_provider(
        name=provider_id,
        provider=provider,
        config=updated_cfg,
        set_default=set_default,
    )
    logger.success(f"[API] PATCH /models/providers/{provider_id} - Updated fields: {updated_fields}")

    return _build_provider_response(provider_id)


@router.delete("/providers/{provider_id}")
async def remove_provider(provider_id: str):
    logger.info(f"[API] DELETE /models/providers/{provider_id} - Removing provider")
    if provider_id not in llm_adapter.providers:
        logger.error(f"[API] DELETE /models/providers/{provider_id} - Provider not found")
        raise NotFoundError(f"Provider [{provider_id}] not found")

    llm_adapter.remove_provider(provider_id)
    logger.success(f"[API] DELETE /models/providers/{provider_id} - Provider removed")
    return {"error": None, "data": {"deleted": True, "id": provider_id}}


@router.get("/providers/{provider_id}/models")
async def list_provider_models(provider_id: str):
    logger.info(f"[API] GET /models/providers/{provider_id}/models - Listing models")
    start_time = time.time()
    try:
        models = await llm_adapter.list_models(provider_id)
        elapsed = time.time() - start_time
        logger.success(f"[API] GET /models/providers/{provider_id}/models - Success: {len(models)} models, elapsed={elapsed:.2f}s")
        return {"error": None, "data": models}
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[API] GET /models/providers/{provider_id}/models - Failed: elapsed={elapsed:.2f}s, error={e}")
        raise


@router.get("/list")
async def list_all_models():
    logger.info("[API] GET /models/list - Listing all models")
    start_time = time.time()
    models = await llm_adapter.list_models()
    elapsed = time.time() - start_time
    logger.success(f"[API] GET /models/list - Success: {len(models)} models, elapsed={elapsed:.2f}s")
    return {"error": None, "data": models}


@router.get("/config")
async def get_model_config():
    logger.info("[API] GET /models/config - Getting model config")
    config = {
        "default_provider": llm_adapter.default_provider,
        "default_model": settings.LLM_DEFAULT_MODEL,
        "default_temperature": settings.LLM_DEFAULT_TEMPERATURE,
        "default_max_tokens": settings.LLM_DEFAULT_MAX_TOKENS,
        "default_top_p": settings.LLM_DEFAULT_TOP_P,
    }
    logger.success(f"[API] GET /models/config - Success: provider={config['default_provider']}, model={config['default_model']}")
    return {"error": None, "data": config}


@router.patch("/config")
async def update_model_config(request: ModelConfigUpdate):
    logger.info(f"[API] PATCH /models/config - Updating model config")
    updated_fields = []

    if request.provider is not None:
        llm_adapter.default_provider = request.provider
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

    _save_model_config({
        "default_provider": llm_adapter.default_provider,
        "default_model": settings.LLM_DEFAULT_MODEL,
        "default_temperature": settings.LLM_DEFAULT_TEMPERATURE,
        "default_max_tokens": settings.LLM_DEFAULT_MAX_TOKENS,
        "default_top_p": settings.LLM_DEFAULT_TOP_P,
    })

    logger.success(f"[API] PATCH /models/config - Updated fields: {updated_fields}")
    return {
        "error": None,
        "data": {
            "default_provider": llm_adapter.default_provider,
            "default_model": settings.LLM_DEFAULT_MODEL,
            "default_temperature": settings.LLM_DEFAULT_TEMPERATURE,
            "default_max_tokens": settings.LLM_DEFAULT_MAX_TOKENS,
            "default_top_p": settings.LLM_DEFAULT_TOP_P,
        }
    }
