from app.core.config import settings
from app.core.exceptions import ProviderError
from app.runtime.provider.llm.providers import OpenAIProvider, OllamaProvider
from loguru import logger


PROVIDER_REGISTRY = {
    "openai": OpenAIProvider,
    "ollama": OllamaProvider,
}


class LLMAdapter:
    def __init__(self):
        fallback_chain = settings.LLM_FALLBACK_CHAIN.split(",")
        self.providers = {}
        for name in fallback_chain:
            name = name.strip()
            if name in PROVIDER_REGISTRY:
                self.providers[name] = PROVIDER_REGISTRY[name]()
        self.default_provider = settings.LLM_DEFAULT_PROVIDER

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
        **kwargs
    ) -> str:
        provider_names = list(self.providers.keys())
        if self.default_provider in self.providers:
            provider_names = [self.default_provider] + [n for n in provider_names if n != self.default_provider]

        last_error = None
        for name in provider_names:
            try:
                provider = self.providers[name]
                result = await provider.chat(messages, tools, stream, **kwargs)
                logger.debug(f"LLM response from [{name}]")
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"LLM provider [{name}] failed: {e}")
                continue

        raise ProviderError(f"All LLM providers failed. Last error: {last_error}")

    async def embed(self, text: str) -> list[float]:
        provider = self.providers.get(self.default_provider)
        if provider:
            return await provider.embed(text)
        raise ProviderError("No available embedding provider")
