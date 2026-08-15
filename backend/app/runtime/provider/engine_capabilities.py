"""引擎能力声明（EngineCapabilities）— TTS/STT 引擎统一元数据（G1/G2 治理）。

收敛原 voice.py engine_meta 硬编码与前端 stores/model.ts TTS_ENGINE_VOICES 硬编码：
- 后端 /chat/tts/engines、/voice/engines 直接输出本声明（前端仅消费接口）
- 引擎切换后音色/模型下拉按 languages + voices 过滤（级联刷新）
- Registry.resolve(lang=...) 按能力过滤引擎（语言感知，解析链 L4）

设计文档：docs/development/voice-model-market.md §5.6
"""
from __future__ import annotations

from dataclasses import dataclass, field

# TTS 语言字段取值范围（v0.5 决策：auto/zh/en/ja/ko/yue 全量纳入）
SUPPORTED_TTS_LANGUAGES: tuple[str, ...] = ("auto", "zh", "en", "ja", "ko", "yue")

# 语言显示名映射（供前端 label 与日志输出）
LANGUAGE_LABELS: dict[str, str] = {
    "auto": "自动检测",
    "zh": "中文",
    "en": "English",
    "ja": "日本語",
    "ko": "한국어",
    "yue": "粵語",
}


@dataclass
class EngineCapabilities:
    """引擎能力声明（内置引擎为类属性 CAPABILITIES，插件引擎来自 manifest）。

    Attributes:
        engine_id: 引擎唯一标识（如 "edge-tts"）
        name: 显示名称（如 "Edge TTS（在线·免费）"）
        kind: cloud（云端）/ local（本地）
        category: cloud-free / cloud-paid / local
        needs_api_key: 是否需要 API Key
        online: 是否需要网络
        languages: 支持的语言列表（不含 auto；空元组 = 不限/未知）
        voices: 音色列表（value/label/langs），空列表 = 动态枚举或自由输入
        voice_mode: voices 为空时的前端交互模式：dynamic（运行时枚举）/ input（自由输入）
        default_voice: 默认音色
        models: 可选模型列表（云引擎模型名）
        default_model: 默认模型
        supports_speed: 是否支持语速参数
        description: 引擎描述
    """

    engine_id: str
    name: str
    kind: str = "local"  # "cloud" | "local"
    category: str = "local"  # "cloud-free" | "cloud-paid" | "local"
    needs_api_key: bool = False
    online: bool = False
    languages: tuple[str, ...] = ()
    voices: list[dict] = field(default_factory=list)
    voice_mode: str = "list"  # "list" | "dynamic" | "input"
    default_voice: str = ""
    models: list[str] = field(default_factory=list)
    default_model: str = ""
    supports_speed: bool = True
    description: str = ""

    def supports_language(self, lang: str) -> bool:
        """是否支持目标语言（languages 为空视为不限）。"""
        if not lang or lang == "auto":
            return True
        return lang in self.languages

    def to_dict(self) -> dict:
        """序列化为 API 输出（/chat/tts/engines、/voice/engines 共用）。"""
        return {
            "id": self.engine_id,
            "name": self.name,
            "kind": self.kind,
            "category": self.category,
            "needs_api_key": self.needs_api_key,
            "online": self.online,
            "languages": list(self.languages),
            "voices": self.voices,
            "voice_mode": self.voice_mode,
            "default_voice": self.default_voice,
            "models": self.models,
            "default_model": self.default_model,
            "supports_speed": self.supports_speed,
            "description": self.description,
        }
