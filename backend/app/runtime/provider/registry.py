"""LuomiNest Provider 注册表。

管理所有可用的 LLM Provider，支持按名称/别名查找、注册/注销，
提供全局单例 provider_registry 供运行时使用。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from app.runtime.provider.llm.ports import LLMProvider


class ProviderRegistry:
    """Provider 注册表 - 管理所有可用的 LLM Provider。

    支持：
    - 按规范名称注册/注销 Provider 类
    - 别名映射（如 "openai" -> "openai_compatible"）
    - 按名称（含别名）查找 Provider 类
    - 列出所有已注册的 Provider
    """

    def __init__(self) -> None:
        self._providers: dict[str, type[LLMProvider]] = {}  # name -> provider class
        self._aliases: dict[str, str] = {}  # alias -> canonical name

    def register(
        self,
        name: str,
        provider_cls: type[LLMProvider],
        aliases: list[str] | None = None,
    ) -> None:
        """注册一个 Provider。

        Args:
            name: Provider 规范名称（如 "openai_compatible"）
            provider_cls: Provider 类（必须是 LLMProvider 子类）
            aliases: 可选别名列表（如 ["openai", "gpt"]）
        """
        if name in self._providers:
            logger.warning(f"Provider '{name}' 已注册，将被覆盖")

        self._providers[name] = provider_cls
        logger.debug(f"已注册 Provider: {name} -> {provider_cls.__name__}")

        if aliases:
            for alias in aliases:
                if alias in self._aliases:
                    old_target = self._aliases[alias]
                    if old_target != name:
                        logger.warning(
                            f"别名 '{alias}' 已从 '{old_target}' 重新映射到 '{name}'"
                        )
                self._aliases[alias] = name
                logger.debug(f"已注册别名: {alias} -> {name}")

    def unregister(self, name: str) -> None:
        """注销一个 Provider。

        同时移除所有指向该 Provider 的别名。

        Args:
            name: Provider 规范名称
        """
        if name not in self._providers:
            logger.warning(f"Provider '{name}' 未注册，无法注销")
            return

        del self._providers[name]

        # 清理指向该 name 的别名
        aliases_to_remove = [
            alias for alias, target in self._aliases.items() if target == name
        ]
        for alias in aliases_to_remove:
            del self._aliases[alias]

        logger.debug(f"已注销 Provider: {name}（移除 {len(aliases_to_remove)} 个别名）")

    def get(self, name: str) -> type[LLMProvider] | None:
        """按名称获取 Provider 类（支持别名解析）。

        Args:
            name: Provider 名称或别名

        Returns:
            Provider 类，未找到则返回 None
        """
        canonical = self.resolve_name(name)
        return self._providers.get(canonical)

    def list_providers(self) -> list[str]:
        """列出所有已注册的 Provider 规范名称。"""
        return list(self._providers.keys())

    def resolve_name(self, name: str) -> str:
        """解析名称（含别名），返回规范名称。

        Args:
            name: Provider 名称或别名

        Returns:
            规范名称（若为别名则返回映射目标，否则原样返回）
        """
        return self._aliases.get(name, name)

    def is_registered(self, name: str) -> bool:
        """检查 Provider 是否已注册（支持别名）。

        Args:
            name: Provider 名称或别名

        Returns:
            是否已注册
        """
        canonical = self.resolve_name(name)
        return canonical in self._providers


# 全局单例
provider_registry = ProviderRegistry()
