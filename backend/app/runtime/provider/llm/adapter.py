import json
import os
import time
from typing import AsyncIterator
from app.core.config import settings
from app.core.exceptions import ProviderError
from app.runtime.provider.llm.providers import (
    OpenAICompatibleProvider,
    LLMResponse,
    StreamEvent,
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
        logger.debug(f"[Adapter] Provider config file not found: {CONFIG_FILE}")
        return []
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            logger.debug(f"[Adapter] Loaded {len(data)} saved providers from {CONFIG_FILE}")
            return data
    except Exception as e:
        logger.warning(f"[Adapter] Failed to load provider config: {e}")
        return []


def _save_providers_config(providers_data: list[dict]):
    _ensure_config_dir()
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(providers_data, f, ensure_ascii=False, indent=2)
        logger.success(f"[Adapter] Saved {len(providers_data)} providers to {CONFIG_FILE}")
    except Exception as e:
        logger.error(f"[Adapter] Failed to save provider config: {e}")


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

    logger.debug(f"[Adapter] Creating provider: name={provider_name}, base_url={base_url}, model={default_model}")
    return OpenAICompatibleProvider(
        api_key=api_key,
        base_url=base_url,
        default_model=default_model,
        provider_name=provider_name,
    )


class LLMAdapter:
    def __init__(self):
        logger.info("[Adapter] Initializing LLMAdapter...")
        self.providers: dict[str, OpenAICompatibleProvider] = {}
        self._provider_configs: dict[str, dict] = {}
        self.default_provider = settings.LLM_DEFAULT_PROVIDER
        self._init_providers()
        logger.success(f"[Adapter] LLMAdapter initialized with {len(self.providers)} providers, default={self.default_provider}")

    def _init_providers(self):
        saved = _load_saved_providers()
        if saved:
            logger.info(f"[Adapter] Loading {len(saved)} saved providers...")
            for cfg in saved:
                try:
                    provider = _create_provider_from_config(cfg)
                    self.providers[cfg["id"]] = provider
                    self._provider_configs[cfg["id"]] = cfg
                    if cfg.get("is_default"):
                        self.default_provider = cfg["id"]
                    logger.success(f"[Adapter] Loaded provider: {cfg['id']} ({cfg.get('name', cfg['id'])})")
                except Exception as e:
                    logger.warning(f"[Adapter] Failed to load provider [{cfg.get('id')}]: {e}")
        else:
            logger.info("[Adapter] No saved providers, loading from fallback chain...")
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
                        logger.success(f"[Adapter] Loaded provider from template: {name}")
                    except Exception as e:
                        logger.warning(f"[Adapter] Failed to load provider [{name}]: {e}")

    def _persist(self):
        configs = list(self._provider_configs.values())
        _save_providers_config(configs)

    def register_provider(self, name: str, provider: OpenAICompatibleProvider, config: dict, set_default: bool = False):
        logger.info(f"[Adapter] Registering provider: {name}")
        self.providers[name] = provider
        self._provider_configs[name] = config
        if set_default:
            self.default_provider = name
            logger.info(f"[Adapter] Set default provider to: {name}")
        self._persist()
        logger.success(f"[Adapter] Provider registered: {name}")

    def update_provider(self, name: str, provider: OpenAICompatibleProvider, config: dict, set_default: bool = False):
        logger.info(f"[Adapter] Updating provider: {name}")
        self.providers[name] = provider
        self._provider_configs[name] = config
        if set_default:
            self.default_provider = name
            logger.info(f"[Adapter] Set default provider to: {name}")
        self._persist()
        logger.success(f"[Adapter] Provider updated: {name}")

    def remove_provider(self, name: str):
        logger.info(f"[Adapter] Removing provider: {name}")
        if name in self.providers:
            del self.providers[name]
        if name in self._provider_configs:
            del self._provider_configs[name]
        if self.default_provider == name:
            remaining = list(self.providers.keys())
            self.default_provider = remaining[0] if remaining else settings.LLM_DEFAULT_PROVIDER
            logger.info(f"[Adapter] Default provider changed to: {self.default_provider}")
        self._persist()
        logger.success(f"[Adapter] Provider removed: {name}")

    def get_provider(self, name: str | None = None) -> OpenAICompatibleProvider:
        provider_name = name or self.default_provider
        provider = self.providers.get(provider_name)
        if not provider:
            logger.error(f"[Adapter] Provider not found: {provider_name}")
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
    ) -> LLMResponse:
        provider = self.get_provider(provider_name)
        actual_provider = provider_name or self.default_provider
        model = kwargs.get("model") or provider.default_model
        logger.info(f"[LLM] Chat request: provider={actual_provider}, model={model}, messages={len(messages)}, tools={len(tools) if tools else 0}")

        start_time = time.time()
        try:
            result = await provider.chat(messages, tools, stream, **kwargs)
            elapsed = time.time() - start_time
            if isinstance(result, LLMResponse):
                tc_count = len(result.tool_calls) if result.tool_calls else 0
                logger.success(f"[LLM] Chat response: provider={actual_provider}, elapsed={elapsed:.2f}s, content_len={len(result.content)}, tool_calls={tc_count}")
            else:
                logger.info(f"[LLM] Chat stream started: provider={actual_provider}")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[LLM] Chat failed: provider={actual_provider}, elapsed={elapsed:.2f}s, error={e}")
            if provider_name:
                raise ProviderError(f"Provider [{provider_name}] failed: {e}", provider=provider_name)
            return await self._fallback_chat(messages, tools, stream, **kwargs)

    async def _fallback_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
        **kwargs
    ) -> LLMResponse:
        logger.warning("[LLM] Starting fallback chat...")
        provider_names = list(self.providers.keys())
        if self.default_provider in self.providers:
            provider_names = [self.default_provider] + [
                n for n in provider_names if n != self.default_provider
            ]

        last_error = None
        for name in provider_names:
            try:
                provider = self.providers[name]
                start_time = time.time()
                result = await provider.chat(messages, tools, stream, **kwargs)
                elapsed = time.time() - start_time
                logger.success(f"[LLM] Fallback success: provider={name}, elapsed={elapsed:.2f}s")
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"[LLM] Fallback provider [{name}] failed: {e}")
                continue

        logger.error(f"[LLM] All providers failed in fallback")
        raise ProviderError(f"All LLM providers failed. Last error: {last_error}")

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        provider_name: str | None = None,
        **kwargs
    ) -> AsyncIterator[StreamEvent]:
        provider = self.get_provider(provider_name)
        actual_provider = provider_name or self.default_provider
        model = kwargs.get("model") or provider.default_model
        logger.info(f"[LLM] Stream request: provider={actual_provider}, model={model}, messages={len(messages)}, tools={len(tools) if tools else 0}")

        chunk_count = 0
        start_time = time.time()
        try:
            async for event in provider.chat_stream(messages, tools, **kwargs):
                chunk_count += 1
                yield event
            elapsed = time.time() - start_time
            logger.success(f"[LLM] Stream completed: provider={actual_provider}, chunks={chunk_count}, elapsed={elapsed:.2f}s")
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[LLM] Stream failed: provider={actual_provider}, elapsed={elapsed:.2f}s, error={e}")
            raise

    async def embed(self, text: str, provider_name: str | None = None) -> list[float]:
        provider = self.get_provider(provider_name)
        actual_provider = provider_name or self.default_provider
        logger.info(f"[LLM] Embed request: provider={actual_provider}, text_len={len(text)}")
        start_time = time.time()
        result = await provider.embed(text)
        elapsed = time.time() - start_time
        logger.success(f"[LLM] Embed response: provider={actual_provider}, elapsed={elapsed:.2f}s, dim={len(result)}")
        return result

    async def list_models(self, provider_name: str | None = None) -> list[dict]:
        if provider_name:
            provider = self.get_provider(provider_name)
            logger.debug(f"[Adapter] Listing models for provider: {provider_name}")
            models = await provider.list_models()
            logger.debug(f"[Adapter] Found {len(models)} models for {provider_name}")
            return models

        logger.debug("[Adapter] Listing models for all providers")
        all_models = []
        for name, provider in self.providers.items():
            try:
                models = await provider.list_models()
                for m in models:
                    m["provider"] = name
                all_models.extend(models)
                logger.debug(f"[Adapter] Provider {name}: {len(models)} models")
            except Exception as e:
                logger.warning(f"[Adapter] Failed to list models for {name}: {e}")
        logger.debug(f"[Adapter] Total models: {len(all_models)}")
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
