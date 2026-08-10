import asyncio
import threading
import time
from typing import AsyncIterator

from loguru import logger

from app.core.config import settings
from app.core.context import invalidate_context_cache
from app.core.exceptions import ProviderError
from app.security.prompt_security import sanitize_user_input
from app.runtime.provider.llm.providers import (
    OpenAICompatibleProvider,
    PROVIDER_TEMPLATES,
)
from app.runtime.provider.llm.types import LLMRequest, ProviderCapabilities, RouteHint
from app.runtime.provider.llm.capabilities import get_capabilities as _get_capabilities
from app.runtime.provider.registry import provider_registry


# ── 注册默认 Provider 实现 ──
# 所有已知 vendor 均使用 OpenAICompatibleProvider；
# 未来新增非兼容 Provider（如原生 Anthropic SDK）时，只需 register 新类即可。
provider_registry.register(
    "openai_compatible",
    OpenAICompatibleProvider,
    aliases=list(PROVIDER_TEMPLATES.keys()),
)


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
            default_model = "qwen3-vl:8b"
        provider_name = "ollama"
    else:
        if not base_url:
            base_url = "https://api.openai.com/v1"
        if not default_model:
            default_model = "gpt-4o-mini"

    # 通过 ProviderRegistry 查找实现类（支持未来扩展非 OpenAI 兼容的 Provider）
    provider_cls = provider_registry.get(vendor) or OpenAICompatibleProvider

    logger.debug(f"[Adapter] Creating provider: name={provider_name}, base_url={base_url}, model={default_model}, class={provider_cls.__name__}")
    return provider_cls(
        api_key=api_key,
        base_url=base_url,
        default_model=default_model,
        provider_name=provider_name,
    )


class LLMAdapter:
    def __init__(self):
        logger.info("[Adapter] Initializing LLMAdapter (lazy load mode)...")
        self.providers: dict[str, OpenAICompatibleProvider] = {}
        self._provider_configs: dict[str, dict] = {}
        self.default_provider = settings.LLM_DEFAULT_PROVIDER
        self._loaded = False
        # NOTE: 此处使用 threading.Lock 而非 asyncio.Lock，原因：
        # 1. ensure_providers_loaded() 是同步方法，被大量同步方法调用（get_provider, register_provider 等）
        # 2. get_provider() 在代码库中被 25+ 处同步代码调用（chat endpoints, platform_router, memory_engine 等）
        # 3. 转换为 asyncio.Lock 需要级联修改数十个文件的所有调用链
        # 4. 该锁仅保护一次性初始化（_loaded 标志），初始化完成后无竞争，threading.Lock 在此场景完全适用
        self._lock = threading.Lock()
        # Repository 懒加载（避免 import 时触达 DB）
        self._provider_repo = None
        self._credential_repo = None
        # 推理模型路由配置（从 model_config 加载）
        self._reasoner_provider: str = ""
        self._reasoner_model: str = ""
        self._reasoner_temperature: float | None = None
        self._reasoner_max_tokens: int | None = None
        self._reasoner_effort: str = ""
        logger.info(f"[Adapter] LLMAdapter created, default={self.default_provider} (providers will load on first access)")

    def _ensure_repos(self):
        """懒加载 Repository（避免 import 时触达 DB）。"""
        if self._provider_repo is None:
            from app.infrastructure.database.repositories import ProviderRepository, ProviderCredentialRepository
            self._provider_repo = ProviderRepository()
            self._credential_repo = ProviderCredentialRepository()

    def ensure_providers_loaded(self):
        """懒加载 provider 配置。

        首次调用时从 ProviderRepository 加载已保存的 providers（含解密 api_key）。
        后续调用无副作用。用 threading.Lock + _loaded 标志保证线程安全且只加载一次。
        在 lifespan 中显式调用一次；各访问方法也会兜底调用以防遗漏。
        """
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            logger.info("[Adapter] Loading providers (first access)...")
            self._ensure_repos()
            self._init_providers()
            self._loaded = True
            logger.success(f"[Adapter] Providers loaded: {len(self.providers)} providers, default={self.default_provider}")

    def _init_providers(self):
        """从 repo 加载 providers；无数据时走 fallback_chain 模板。

        fallback 供应商仅存在于内存，不写入 DB；通过 dismissed 列表防止重建。
        """
        saved = self._provider_repo.get_all_ordered()
        if saved:
            logger.info(f"[Adapter] Loading {len(saved)} saved providers from repo...")
            for cfg in saved:
                try:
                    provider_id = cfg.get("id", "")
                    if not provider_id:
                        continue
                    # 取活跃凭证（解密 api_key），注入 cfg 供 _create_provider_from_config 使用
                    credential = self._credential_repo.get_active_credential(provider_id)
                    cfg_with_key = dict(cfg)
                    cfg_with_key["api_key"] = credential.get("api_key", "") if credential else ""
                    provider = _create_provider_from_config(cfg_with_key)
                    self.providers[provider_id] = provider
                    self._provider_configs[provider_id] = cfg
                    if cfg.get("is_default"):
                        self.default_provider = provider_id
                    logger.success(f"[Adapter] Loaded provider: {provider_id} ({cfg.get('name', provider_id)})")
                except Exception as e:
                    logger.warning(f"[Adapter] Failed to load provider [{cfg.get('id')}]: {e}")
        else:
            logger.info("[Adapter] No saved providers, loading from fallback chain...")
            dismissed = self._get_dismissed_providers()
            fallback_chain = settings.LLM_FALLBACK_CHAIN.split(",")
            for name in fallback_chain:
                name = name.strip()
                if name in dismissed:
                    logger.info(f"[Adapter] Skipping dismissed fallback provider: {name}")
                    continue
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

    def _get_dismissed_providers(self) -> list[str]:
        """从 config_items 读取用户已主动删除的默认供应商列表。"""
        # NOTE: 延迟 import —— config_store 会触发 DB 引擎初始化，不能在模块顶层加载
        from app.infrastructure.database.config_store import lumi_config_store
        dismissed = lumi_config_store.get("providers.dismissed_defaults")
        return dismissed if isinstance(dismissed, list) else []

    def _add_dismissed_provider(self, name: str):
        """记录用户已主动删除的默认供应商。"""
        from app.infrastructure.database.config_store import lumi_config_store
        dismissed = self._get_dismissed_providers()
        if name not in dismissed:
            dismissed.append(name)
            lumi_config_store.set("providers.dismissed_defaults", dismissed)
            logger.info(f"[Adapter] Added dismissed provider: {name}")

    def _remove_dismissed_provider(self, name: str):
        """用户重新手动添加同名供应商时，从 dismissed 列表移除。"""
        from app.infrastructure.database.config_store import lumi_config_store
        dismissed = self._get_dismissed_providers()
        if name in dismissed:
            dismissed.remove(name)
            lumi_config_store.set("providers.dismissed_defaults", dismissed)
            logger.info(f"[Adapter] Removed dismissed provider: {name}")

    def register_provider(self, name: str, provider: OpenAICompatibleProvider, config: dict, set_default: bool = False):
        self.ensure_providers_loaded()
        logger.info(f"[Adapter] Registering provider: {name}")
        self._ensure_repos()

        # 拆分元信息与凭证（api_key 不进 provider 表）
        api_key = config.get("api_key", "")
        meta = {k: v for k, v in config.items() if k != "api_key"}
        self._provider_repo.save(name, meta)

        if api_key:
            self._credential_repo.save_credential(name, api_key)

        # 用户手动添加同名供应商时，从 dismissed 列表移除（防止 fallback 重建冲突）
        self._remove_dismissed_provider(name)
        self.providers[name] = provider
        self._provider_configs[name] = config
        if set_default:
            self.default_provider = name
            logger.info(f"[Adapter] Set default provider to: {name}")
        logger.success(f"[Adapter] Provider registered: {name}")

        # 注册变更后失效该 provider 的上下文缓存
        invalidate_context_cache(provider=name)

    def update_provider(self, name: str, provider: OpenAICompatibleProvider, config: dict, set_default: bool = False):
        self.ensure_providers_loaded()
        logger.info(f"[Adapter] Updating provider: {name}")
        self._ensure_repos()

        api_key = config.get("api_key", "")
        meta = {k: v for k, v in config.items() if k != "api_key"}
        self._provider_repo.save(name, meta)

        # api_key 为空字符串时不更新凭证（保留旧 key）
        if api_key:
            self._credential_repo.save_credential(name, api_key)

        self.providers[name] = provider
        self._provider_configs[name] = config
        if set_default:
            self.default_provider = name
            logger.info(f"[Adapter] Set default provider to: {name}")
        logger.success(f"[Adapter] Provider updated: {name}")

        # 配置变更后失效该 provider 的上下文缓存
        invalidate_context_cache(provider=name)

    def remove_provider(self, name: str):
        self.ensure_providers_loaded()
        logger.info(f"[Adapter] Removing provider: {name}")
        self._ensure_repos()

        self._provider_repo.delete(name)
        self._credential_repo.delete_by_provider(name)

        if name in self.providers:
            del self.providers[name]
        if name in self._provider_configs:
            del self._provider_configs[name]
        if self.default_provider == name:
            remaining = list(self.providers.keys())
            if remaining:
                self.default_provider = remaining[0]
            elif settings.LLM_DEFAULT_PROVIDER in self.providers:
                self.default_provider = settings.LLM_DEFAULT_PROVIDER
            else:
                self.default_provider = ""
            logger.info(f"[Adapter] Default provider changed to: {self.default_provider}")
        # 若删除的是 fallback chain 中的默认供应商，记录到 dismissed 列表防止重建
        fallback_chain = [n.strip() for n in settings.LLM_FALLBACK_CHAIN.split(",")]
        if name in fallback_chain:
            self._add_dismissed_provider(name)
        logger.success(f"[Adapter] Provider removed: {name}")

        # provider 删除后失效相关上下文缓存
        invalidate_context_cache(provider=name)

    def get_provider(self, name: str | None = None) -> OpenAICompatibleProvider:
        self.ensure_providers_loaded()
        provider_name = name or self.default_provider
        provider = self.providers.get(provider_name)
        if not provider:
            logger.error(f"[Adapter] Provider not found: {provider_name}")
            raise ProviderError(f"Provider [{provider_name}] not found", provider=provider_name)
        return provider

    def get_provider_config(self, name: str) -> dict | None:
        self.ensure_providers_loaded()
        self._ensure_repos()
        # 优先从 repo 取（持久化数据），fallback chain 模板回退到内存
        cfg = self._provider_repo.get(name)
        if cfg is None:
            return self._provider_configs.get(name)
        return cfg

    def supports_tool_calls(self, provider_name: str | None = None, model: str = "") -> bool:
        try:
            provider = self.get_provider(provider_name)
            return provider.supports_tool_calls(model)
        except ProviderError:
            return False

    def get_capabilities(
        self,
        provider_name: str | None = None,
        model: str | None = None,
    ) -> ProviderCapabilities:
        """获取当前或指定 provider 的能力声明。

        优先使用 provider 实例的 get_capabilities（含运行时探测结果），
        provider 不存在时回退到 capabilities 模块的静态查询。
        """
        name = provider_name or self.default_provider
        try:
            provider = self.get_provider(name)
            return provider.get_capabilities(model)
        except ProviderError:
            return _get_capabilities(name, model)

    def get_reasoner_provider(self) -> tuple[str, str, float | None, int | None, str] | None:
        """返回 (provider_name, model, temperature, max_tokens, effort)，未配置返回 None。"""
        if not self._reasoner_provider:
            return None
        return (
            self._reasoner_provider,
            self._reasoner_model,
            self._reasoner_temperature,
            self._reasoner_max_tokens,
            self._reasoner_effort,
        )

    def apply_reasoner_config(self, config: dict):
        """从 model_config 应用 reasoner_* 到内存。"""
        self._reasoner_provider = config.get("reasoner_provider", "") or ""
        self._reasoner_model = config.get("reasoner_model", "") or ""
        self._reasoner_temperature = config.get("reasoner_temperature")
        self._reasoner_max_tokens = config.get("reasoner_max_tokens")
        self._reasoner_effort = config.get("reasoner_effort", "") or ""

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
        provider_name: str | None = None,
        return_raw: bool = False,
        route_hint: RouteHint = RouteHint.CHAT,
        **kwargs
    ) -> str | dict | AsyncIterator[dict]:
        # 路由决策：未显式指定 provider_name 时按 route_hint 选择
        actual_provider_name = provider_name
        actual_model = kwargs.get("model")
        if not provider_name:
            if route_hint == RouteHint.REASONER and self._reasoner_provider:
                actual_provider_name = self._reasoner_provider
                actual_model = actual_model or self._reasoner_model
                kwargs.setdefault("temperature", self._reasoner_temperature)
                kwargs.setdefault("max_tokens", self._reasoner_max_tokens)
                if self._reasoner_effort:
                    kwargs.setdefault("reasoning_effort", self._reasoner_effort)
            else:
                # CHAT 和 AGENT 都走主模型（推理模型通常不支持工具调用）
                actual_provider_name = self.default_provider

        provider = self.get_provider(actual_provider_name)
        model = actual_model or provider.default_model
        logger.info(f"[LLM] Chat request: provider={actual_provider_name}, model={model}, messages={len(messages)}, route={route_hint.value}")

        # Prompt 注入防护：净化 user 消息中的伪造系统级标签与守卫标记
        messages = self._sanitize_messages(messages)

        # 构建 LLMRequest（统一参数传递）
        request = LLMRequest(
            messages=messages,
            tools=tools,
            model=model,
            temperature=kwargs.get("temperature"),
            max_tokens=kwargs.get("max_tokens"),
            top_p=kwargs.get("top_p"),
            stream=stream,
            return_raw=return_raw,
            extra={k: v for k, v in kwargs.items() if k not in ("model", "temperature", "max_tokens", "top_p")},
        )

        start_time = time.time()
        try:
            response = await provider.chat(request)
            elapsed = time.time() - start_time
            logger.success(
                f"[LLM] Chat response: provider={actual_provider_name}, elapsed={elapsed:.2f}s, "
                f"content_len={len(response.content)}, reasoning_len={len(response.reasoning)}"
            )
            # 向后兼容：return_raw=True 返回 dict，否则返回 str
            if return_raw:
                return response.to_dict()
            return response.content
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[LLM] Chat failed: provider={actual_provider_name}, elapsed={elapsed:.2f}s, error={e}")
            return await self._fallback_chat(messages, tools, stream, return_raw=return_raw, route_hint=route_hint, **kwargs)

    async def _fallback_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
        return_raw: bool = False,
        route_hint: RouteHint = RouteHint.CHAT,
        **kwargs
    ) -> str | dict | AsyncIterator[dict]:
        self.ensure_providers_loaded()
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
                model = kwargs.get("model") or provider.default_model
                request = LLMRequest(
                    messages=messages,
                    tools=tools,
                    model=model,
                    temperature=kwargs.get("temperature"),
                    max_tokens=kwargs.get("max_tokens"),
                    top_p=kwargs.get("top_p"),
                    stream=stream,
                    return_raw=return_raw,
                    extra={k: v for k, v in kwargs.items() if k not in ("model", "temperature", "max_tokens", "top_p")},
                )
                start_time = time.time()
                response = await provider.chat(request)
                elapsed = time.time() - start_time
                logger.success(f"[LLM] Fallback success: provider={name}, elapsed={elapsed:.2f}s")
                if return_raw:
                    return response.to_dict()
                return response.content
            except Exception as e:
                last_error = e
                logger.warning(f"[LLM] Fallback provider [{name}] failed: {e}")
                continue

        logger.error(f"[LLM] All providers failed in fallback")
        raise ProviderError(
            f"All LLM providers failed. Last error: {last_error}",
            code="LLM_ALL_PROVIDERS_FAILED",
            status_code=502,
        )

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        provider_name: str | None = None,
        route_hint: RouteHint = RouteHint.CHAT,
        **kwargs
    ) -> AsyncIterator:
        # 路由决策：未显式指定 provider_name 时按 route_hint 选择
        actual_provider_name = provider_name
        actual_model = kwargs.get("model")
        if not provider_name:
            if route_hint == RouteHint.REASONER and self._reasoner_provider:
                actual_provider_name = self._reasoner_provider
                actual_model = actual_model or self._reasoner_model
                kwargs.setdefault("temperature", self._reasoner_temperature)
                kwargs.setdefault("max_tokens", self._reasoner_max_tokens)
                if self._reasoner_effort:
                    kwargs.setdefault("reasoning_effort", self._reasoner_effort)
            else:
                actual_provider_name = self.default_provider

        provider = self.get_provider(actual_provider_name)
        model = actual_model or provider.default_model
        logger.info(f"[LLM] Stream request: provider={actual_provider_name}, model={model}, messages={len(messages)}, route={route_hint.value}")

        # Prompt 注入防护：净化 user 消息中的伪造系统级标签与守卫标记
        messages = self._sanitize_messages(messages)

        request = LLMRequest(
            messages=messages,
            tools=tools,
            model=model,
            temperature=kwargs.get("temperature"),
            max_tokens=kwargs.get("max_tokens"),
            top_p=kwargs.get("top_p"),
            stream=True,
            extra={k: v for k, v in kwargs.items() if k not in ("model", "temperature", "max_tokens", "top_p")},
        )

        chunk_count = 0
        start_time = time.time()
        try:
            async for chunk in provider.chat_stream(request):
                chunk_count += 1
                yield chunk
            elapsed = time.time() - start_time
            logger.success(f"[LLM] Stream completed: provider={actual_provider_name}, chunks={chunk_count}, elapsed={elapsed:.2f}s")
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[LLM] Stream failed: provider={actual_provider_name}, elapsed={elapsed:.2f}s, error={e}")
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
        self.ensure_providers_loaded()
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
        self.ensure_providers_loaded()
        self._ensure_repos()
        result = []
        for name, provider in self.providers.items():
            cfg = self._provider_configs.get(name, {})
            # 从凭证仓储取前缀（不暴露密文/明文）
            try:
                creds = self._credential_repo.list_credentials(name)
                api_key_prefix = creds[0].get("api_key_prefix", "") if creds else ""
            except Exception:
                api_key_prefix = ""
            result.append({
                "id": name,
                "name": cfg.get("name", name),
                "vendor": cfg.get("vendor", provider.provider_name),
                "is_default": name == self.default_provider,
                "base_url": getattr(provider, "base_url", ""),
                "api_key_prefix": api_key_prefix,
                "api_key_set": bool(api_key_prefix),
                "default_model": getattr(provider, "default_model", ""),
                "selected_models": cfg.get("selected_models", []),
            })
        return result

    async def test_provider(self, config: dict) -> dict:
        """临时构造 provider 并调用 list_models 检测 API/TOKEN 是否可用，不注册到全局。"""
        logger.info(f"[Adapter] Testing provider: {config.get('id', 'unknown')}, base_url={config.get('base_url')}")
        try:
            provider = _create_provider_from_config(config)
            models = await provider.list_models()
            logger.success(f"[Adapter] Test success: {len(models)} models fetched")
            return {
                "success": True,
                "models": models,
                "error": None,
            }
        except Exception as e:
            logger.warning(f"[Adapter] Test failed: {type(e).__name__}")
            return {
                "success": False,
                "models": [],
                "error": "Provider 测试失败，请检查配置或网络",
            }

    async def aclose(self):
        """关闭所有 provider 的 httpx client。"""
        for provider in self.providers.values():
            try:
                await provider.aclose()
            except Exception as e:
                logger.warning(f"[Adapter] Failed to close provider: {e}")
        self.providers.clear()
        self._provider_configs.clear()
        self._loaded = False
        logger.info("[Adapter] All providers closed")

    @staticmethod
    def _sanitize_messages(messages: list[dict]) -> list[dict]:
        """对 user 角色消息做 Prompt 注入净化。

        只处理 role == "user" 的字符串内容消息：
        - 中和伪造的守卫块边界标记（防 break-out）
        - 转义系统级标签（<system>/<memory> 等，渲染为纯文本）
        - 清理控制字符

        system 角色消息是可信框架区，tool 消息是沙盒工具返回，均不处理，
        避免破坏系统提示词结构与工具回传的 JSON 内容。

        Args:
            messages: 原始消息列表。

        Returns:
            净化后的消息列表（新列表，不修改原消息对象）。
        """
        sanitized: list[dict] = []
        for msg in messages:
            if msg.get("role") == "user" and isinstance(msg.get("content"), str):
                try:
                    safe_content = sanitize_user_input(msg["content"])
                    if safe_content != msg["content"]:
                        msg = {**msg, "content": safe_content}
                except Exception as e:
                    logger.debug(f"[Adapter] 用户消息净化跳过: {e}")
            sanitized.append(msg)
        return sanitized


llm_adapter = LLMAdapter()
