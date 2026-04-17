from fastapi import APIRouter
from pydantic import BaseModel, Field, ConfigDict
from loguru import logger

from app.runtime.provider.llm.adapter import llm_adapter, _create_provider_from_config
from app.runtime.provider.llm.providers import OpenAICompatibleProvider, PROVIDER_TEMPLATES
from app.core.exceptions import NotFoundError, ValidationError

router = APIRouter(prefix="/models", tags=["models"])


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
    return result


@router.get("/providers", response_model=list[ProviderResponse])
async def list_providers():
    providers_info = llm_adapter.list_providers()
    result = []
    for p in providers_info:
        provider_instance = llm_adapter.providers.get(p["id"])
        models = []
        if provider_instance:
            try:
                models = await provider_instance.list_models()
            except Exception:
                pass

        result.append(ProviderResponse(
            id=p["id"],
            name=p["name"],
            vendor=p["vendor"],
            base_url=p["base_url"],
            api_key_set=p["api_key_set"],
            default_model=p["default_model"],
            is_default=p["is_default"],
            models=models,
        ))
    return result


@router.post("/providers", response_model=ProviderResponse)
async def add_provider(request: ProviderCreate):
    if request.id in llm_adapter.providers:
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

    models = []
    try:
        models = await provider.list_models()
    except Exception:
        pass

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
    if provider_id not in llm_adapter.providers:
        raise NotFoundError(f"Provider [{provider_id}] not found")

    existing_cfg = llm_adapter.get_provider_config(provider_id) or {}
    updated_cfg = dict(existing_cfg)

    if request.name is not None:
        updated_cfg["name"] = request.name
    if request.vendor is not None:
        updated_cfg["vendor"] = request.vendor
    if request.base_url is not None:
        updated_cfg["base_url"] = request.base_url.rstrip("/")
    if request.api_key is not None:
        updated_cfg["api_key"] = request.api_key
    if request.default_model is not None:
        updated_cfg["default_model"] = request.default_model
    if request.is_default is not None:
        updated_cfg["is_default"] = request.is_default

    provider = _create_provider_from_config(updated_cfg)
    set_default = request.is_default if request.is_default is not None else False
    llm_adapter.update_provider(
        name=provider_id,
        provider=provider,
        config=updated_cfg,
        set_default=set_default,
    )

    return _build_provider_response(provider_id)


@router.delete("/providers/{provider_id}")
async def remove_provider(provider_id: str):
    if provider_id not in llm_adapter.providers:
        raise NotFoundError(f"Provider [{provider_id}] not found")

    llm_adapter.remove_provider(provider_id)
    return {"error": None, "data": {"deleted": True, "id": provider_id}}


@router.get("/providers/{provider_id}/models")
async def list_provider_models(provider_id: str):
    models = await llm_adapter.list_models(provider_id)
    return {"error": None, "data": models}


@router.get("/list")
async def list_all_models():
    models = await llm_adapter.list_models()
    return {"error": None, "data": models}


@router.get("/config")
async def get_model_config():
    from app.core.config import settings
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


@router.patch("/config")
async def update_model_config(request: ModelConfigUpdate):
    from app.core.config import settings
    if request.provider is not None:
        llm_adapter.default_provider = request.provider
    if request.model is not None:
        settings.LLM_DEFAULT_MODEL = request.model
    if request.temperature is not None:
        settings.LLM_DEFAULT_TEMPERATURE = request.temperature
    if request.max_tokens is not None:
        settings.LLM_DEFAULT_MAX_TOKENS = request.max_tokens
    if request.top_p is not None:
        settings.LLM_DEFAULT_TOP_P = request.top_p
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
