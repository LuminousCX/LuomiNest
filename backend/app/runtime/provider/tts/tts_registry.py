"""TTS 引擎注册表 - 统一管理所有 TTS 引擎的注册、查询和降级选择.

参考 STT 的引擎选择机制，抽离为独立模块，便于扩展新的 TTS 引擎.
每个引擎通过 register() 注册，resolve() 按 fallback 顺序自动选择可用引擎.
"""

from loguru import logger

from app.runtime.provider.tts.ports import TTSProvider


# TTS 引擎降级顺序（auto 模式下按此顺序尝试）
# edge-tts 免费在线，作为首选兜底；sherpa-onnx 离线神经网络；local 离线系统语音
TTS_FALLBACK_ORDER = ["edge-tts", "sherpa-onnx", "local"]


class LuminousChenXiTTSRegistry:
    """TTS 引擎注册表（单例）.

    管理所有 TTS 引擎的注册、查询和降级选择.
    引擎类需继承 TTSProvider，并实现 provider_name 类属性和 is_available() 类方法.
    """

    _providers: dict[str, type[TTSProvider]] = {}

    @classmethod
    def register(cls, engine_id: str, provider_class: type[TTSProvider]) -> None:
        """注册 TTS 引擎.

        Args:
            engine_id: 引擎唯一标识（如 "edge-tts" / "sherpa-onnx" / "local"）
            provider_class: 引擎类，需继承 TTSProvider
        """
        if engine_id in cls._providers:
            logger.debug(f"[TTSRegistry] Engine [{engine_id}] already registered, skipping")
            return
        cls._providers[engine_id] = provider_class
        logger.info(f"[TTSRegistry] Registered engine: {engine_id} -> {provider_class.__name__}")

    @classmethod
    def get(cls, engine_id: str) -> type[TTSProvider] | None:
        """获取已注册的引擎类."""
        return cls._providers.get(engine_id)

    @classmethod
    def list_engines(cls) -> list[str]:
        """列出所有已注册的引擎 ID."""
        return list(cls._providers.keys())

    @classmethod
    def is_available(cls, engine_id: str) -> bool:
        """检查引擎是否可用（已注册且依赖已安装）."""
        provider_class = cls._providers.get(engine_id)
        if provider_class is None:
            return False
        is_avail = getattr(provider_class, "is_available", None)
        if callable(is_avail):
            try:
                return is_avail()
            except Exception as e:
                logger.debug(f"[TTSRegistry] is_available check failed for [{engine_id}]: {e}")
                return False
        return True

    @classmethod
    def resolve(cls, engine_id: str | None = None, **config) -> tuple[TTSProvider, str]:
        """解析并实例化 TTS 引擎，支持自动降级.

        Args:
            engine_id: 用户指定的引擎 ID，None 或 "auto" 时按降级链自动选择
            **config: 传递给引擎构造函数的配置（apiKey / model / voice / speed / baseUrl 等）

        Returns:
            (provider_instance, used_engine_id) 元组

        Raises:
            RuntimeError: 所有引擎都不可用
        """
        # 构建尝试顺序：用户指定的优先，其余按 fallback order
        if engine_id and engine_id != "auto":
            try_order = [engine_id] + [e for e in TTS_FALLBACK_ORDER if e != engine_id]
        else:
            try_order = list(TTS_FALLBACK_ORDER)

        errors: list[str] = []
        for eid in try_order:
            provider_class = cls._providers.get(eid)
            if provider_class is None:
                errors.append(f"{eid}: 未注册")
                continue

            if not cls.is_available(eid):
                errors.append(f"{eid}: 依赖未安装")
                continue

            try:
                provider = provider_class(**config)
                logger.info(f"[TTSRegistry] Resolved engine: {eid}")
                return provider, eid
            except Exception as e:
                errors.append(f"{eid}: {e}")
                logger.warning(f"[TTSRegistry] Engine [{eid}] init failed: {e}, trying next...")

        raise RuntimeError(
            f"所有 TTS 引擎均不可用: {'; '.join(errors)}. "
            f"请安装 edge-tts / sherpa-onnx / pyttsx3 中的至少一个，或配置云端引擎 API Key"
        )
