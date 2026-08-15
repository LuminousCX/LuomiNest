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
    def capabilities(cls, engine_id: str) -> dict | None:
        """输出引擎能力声明（CAPABILITIES 类属性 → dict），未注册返回 None."""
        provider_class = cls._providers.get(engine_id)
        if provider_class is None:
            return None
        caps = getattr(provider_class, "CAPABILITIES", None)
        return caps.to_dict() if caps is not None else None

    @classmethod
    def list_capabilities(cls) -> list[dict]:
        """聚合全部引擎能力声明 + 可用状态（G1：/chat/tts/engines 数据源）."""
        result: list[dict] = []
        for engine_id in cls._providers:
            info = cls.capabilities(engine_id)
            if info is None:
                info = {"id": engine_id, "name": engine_id, "category": "unknown"}
            info["available"] = cls.is_available(engine_id)
            result.append(info)
        return result

    @classmethod
    def resolve(
        cls,
        engine_id: str | None = None,
        lang: str | None = None,
        **config,
    ) -> tuple[TTSProvider, str]:
        """解析并实例化 TTS 引擎，支持自动降级与语言过滤（G2）.

        Args:
            engine_id: 用户指定的引擎 ID，None 或 "auto" 时按降级链自动选择
            lang: 目标语言（zh/en/ja/ko/yue）；指定时按 CAPABILITIES.languages 过滤
                  （languages 为空的引擎视为不限语言，不过滤）
            **config: 传递给引擎构造函数的配置（apiKey / model / voice / speed / baseUrl 等）

        Returns:
            (provider_instance, used_engine_id) 元组

        Raises:
            RuntimeError: 所有引擎都不可用（或指定语言无可用引擎）
        """

        def _lang_ok(eid: str) -> bool:
            """语言能力协商：languages 为空 = 不限."""
            if not lang or lang == "auto":
                return True
            provider_class = cls._providers.get(eid)
            if provider_class is None:
                return False
            caps = getattr(provider_class, "CAPABILITIES", None)
            if caps is None:
                return True
            return caps.supports_language(lang)

        # 构建尝试顺序：用户指定的优先，其余按 fallback order
        if engine_id and engine_id != "auto":
            try_order = [engine_id] + [e for e in TTS_FALLBACK_ORDER if e != engine_id]
        else:
            try_order = list(TTS_FALLBACK_ORDER)

        # 指定语言且显式指定引擎时：仍尊重用户选择，但记录告警（不强制降级）
        if lang and lang != "auto" and engine_id and engine_id != "auto" and not _lang_ok(engine_id):
            logger.warning(
                f"[TTSRegistry] Engine [{engine_id}] may not support lang [{lang}] "
                f"(user explicitly requested, respecting choice)"
            )

        errors: list[str] = []
        for eid in try_order:
            provider_class = cls._providers.get(eid)
            if provider_class is None:
                errors.append(f"{eid}: 未注册")
                continue

            if not cls.is_available(eid):
                errors.append(f"{eid}: 依赖未安装")
                continue

            # auto 模式下按语言过滤候选（显式指定的引擎不过滤，交给用户）
            if not (engine_id and engine_id != "auto") and not _lang_ok(eid):
                errors.append(f"{eid}: 不支持语言 {lang}")
                continue

            try:
                provider = provider_class(**config)
                logger.info(f"[TTSRegistry] Resolved engine: {eid} (lang={lang or 'auto'})")
                return provider, eid
            except Exception as e:
                errors.append(f"{eid}: {e}")
                logger.warning(f"[TTSRegistry] Engine [{eid}] init failed: {e}, trying next...")

        raise RuntimeError(
            f"所有 TTS 引擎均不可用: {'; '.join(errors)}. "
            f"请安装 edge-tts / sherpa-onnx / pyttsx3 中的至少一个，或配置云端引擎 API Key"
        )
