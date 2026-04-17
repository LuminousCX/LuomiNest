import json
import os
from typing import AsyncIterator
from app.core.config import settings
from app.core.exceptions import ProviderError
from app.runtime.provider.llm.providers import (
    OpenAICompatibleProvider,
    PROVIDER_TEMPLATES,
)
from loguru import logger


CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))), "data")
CONFIG_FILE = os.path.join(CONFIG_DIR, "providers.json")


def _ensure_config_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)


def _load_saved_providers() -> list[dict]:
    _ensure_config_dir()
    if not os.path.exists(CONFIG_FILE):
        return []
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load provider config: {e}")
        return []


def _save_providers_config(providers_data: list[dict]):
    _ensure_config_dir()
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(providers_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save provider config: {e}")


def _create_provider_from_config(config: dict) -> OpenAICompatibleProvider:
    vendor = config.get("vendor", "openai_compatible")
    base_url = config.get("base_url", "").rstrip("/")
    api_key = config.get("api_key", "")
    default_model = config.get("default_model", "")
    provider_name = config.get("id", vendor)

    if vendor == "ollama":
        if not base_url:
            base_url = "http://localhost:11434/v1"
        elif not base_url.endswith("/v1"):
            base_url = base_url + "/v1"
        if not api_key:
            api_key = "ollama"
        if not default_model:
            default_model = "qwen2.5:7b"
        provider_name = "ollama"
    else:
        if not base_url:
            base_url = "https://api.openai.com/v1"
        if not default_model:
            default_model = "gpt-4o-mini"

    return OpenAICompatibleProvider(
        api_key=api_key,
        base_url=base_url,
        default_model=default_model,
        provider_name=provider_name,
    )


class LLMAdapter:
    def __init__(self):
        self.providers: dict[str, OpenAICompatibleProvider] = {}
        self._provider_configs: dict[str, dict] = {}
        self.default_provider = settings.LLM_DEFAULT_PROVIDER
        self._init_providers()

    def _init_providers(self):
        saved = _load_saved_providers()
        if saved:
            for cfg in saved:
                try:
                    provider = _create_provider_from_config(cfg)
                    self.providers[cfg["id"]] = provider
                    self._provider_configs[cfg["id"]] = cfg
                    if cfg.get("is_default"):
                        self.default_provider = cfg["id"]
                    logger.info(f"Initialized LLM provider: {cfg['id']}")
                except Exception as e:
                    logger.warning(f"Failed to initialize provider [{cfg.get('id')}]: {e}")
        else:
            fallback_chain = settings.LLM_FALLBACK_CHAIN.split(",")
            for name in fallback_chain:
                name = name.strip()
                template = PROVIDER_TEMPLATES.get(name)
                if template:
                    try:
                        cfg = dict(template)
                        provider = _create_provider_from_config(cfg)
                        self.providers[name] = provider
                        self._provider_configs[name] = cfg
                        logger.info(f"Initialized LLM provider from template: {name}")
                    except Exception as e:
                        logger.warning(f"Failed to initialize provider [{name}]: {e}")

    def _persist(self):
        configs = list(self._provider_configs.values())
        _save_providers_config(configs)

    def register_provider(self, name: str, provider: OpenAICompatibleProvider, config: dict, set_default: bool = False):
        self.providers[name] = provider
        self._provider_configs[name] = config
        if set_default:
            self.default_provider = name
        self._persist()
        logger.info(f"Registered LLM provider: {name}")

    def update_provider(self, name: str, provider: OpenAICompatibleProvider, config: dict, set_default: bool = False):
        self.providers[name] = provider
        self._provider_configs[name] = config
        if set_default:
            self.default_provider = name
        self._persist()
        logger.info(f"Updated LLM provider: {name}")

    def remove_provider(self, name: str):
        if name in self.providers:
            del self.providers[name]
        if name in self._provider_configs:
            del self._provider_configs[name]
        if self.default_provider == name:
            remaining = list(self.providers.keys())
            self.default_provider = remaining[0] if remaining else settings.LLM_DEFAULT_PROVIDER
        self._persist()
        logger.info(f"Removed LLM provider: {name}")

    def get_provider(self, name: str | None = None) -> OpenAICompatibleProvider:
        provider_name = name or self.default_provider
        provider = self.providers.get(provider_name)
        if not provider:
            raise ProviderError(f"Provider [{provider_name}] not found", provider=provider_name)
        return provider

    def get_provider_config(self, name: str) -> dict | None:
        return self._provider_configs.get(name)

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
        provider_name: str | None = None,
        **kwargs
    ) -> str | AsyncIterator[str]:
        provider = self.get_provider(provider_name)
        try:
            result = await provider.chat(messages, tools, stream, **kwargs)
            logger.debug(f"LLM response from [{provider.provider_name}]")
            return result
        except Exception as e:
            if provider_name:
                raise ProviderError(f"Provider [{provider_name}] failed: {e}", provider=provider_name)
            return await self._fallback_chat(messages, tools, stream, **kwargs)

    async def _fallback_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
        **kwargs
    ) -> str | AsyncIterator[str]:
        provider_names = list(self.providers.keys())
        if self.default_provider in self.providers:
            provider_names = [self.default_provider] + [
                n for n in provider_names if n != self.default_provider
            ]

        last_error = None
        for name in provider_names:
            try:
                provider = self.providers[name]
                result = await provider.chat(messages, tools, stream, **kwargs)
                logger.debug(f"LLM response from [{name}] (fallback)")
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"LLM provider [{name}] failed: {e}")
                continue

        raise ProviderError(f"All LLM providers failed. Last error: {last_error}")

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        provider_name: str | None = None,
        **kwargs
    ) -> AsyncIterator[str]:
        provider = self.get_provider(provider_name)
        async for chunk in provider.chat_stream(messages, tools, **kwargs):
            yield chunk

    async def embed(self, text: str, provider_name: str | None = None) -> list[float]:
        provider = self.get_provider(provider_name)
        return await provider.embed(text)

    async def list_models(self, provider_name: str | None = None) -> list[dict]:
        if provider_name:
            provider = self.get_provider(provider_name)
            return await provider.list_models()

        all_models = []
        for name, provider in self.providers.items():
            models = await provider.list_models()
            for m in models:
                m["provider"] = name
            all_models.extend(models)
        return all_models

    def list_providers(self) -> list[dict]:
        result = []
        for name, provider in self.providers.items():
            cfg = self._provider_configs.get(name, {})
            api_key = getattr(provider, "api_key", "")
            result.append({
                "id": name,
                "name": cfg.get("name", name),
                "vendor": cfg.get("vendor", provider.provider_name),
                "is_default": name == self.default_provider,
                "base_url": getattr(provider, "base_url", ""),
                "api_key_set": bool(api_key and api_key not in ("ollama", "lmstudio", "")),
                "default_model": getattr(provider, "default_model", ""),
            })
        return result


llm_adapter = LLMAdapter()
