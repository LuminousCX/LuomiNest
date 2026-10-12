"""TagTranslator — 合同标签词 → LuomiNest 语义 ID 翻译器（分册 08 §15.1）。

- 内置 8→12 映射 + 可选 JSON 覆盖表（model_config.avatar_translation_override 文件路径）；
- 在役 12 语义 ID 直接透传（现役 <exp:X> 非自闭合行为不回退）；
- 映射不到 / 词表外（含幻觉词）一律落 neutral + 计数留痕，绝不报错。
"""
from __future__ import annotations

import json
import os

from loguru import logger

from app.core.tags.definitions import (
    BUILTIN_EXP_TRANSLATION,
    DEFAULT_EMOTION_ID,
    LUOMINEST_EMOTION_IDS,
)


class TagTranslator:
    """合同词翻译器：translate(word) -> (semantic_id, is_known)。"""

    def __init__(self, override_path: str | None = None):
        """
        Args:
            override_path: 可选 JSON 文件路径，覆盖内置映射表（{"smile": "happy"} 形态；
                           仅接受映射到 12 语义 ID 的条目，非法条目跳过，加载失败用内置表）。
        """
        self._override = self._load_override(override_path)
        # 计数留痕（供 V5 词表扩容评审 / 网关观测）
        self.counters: dict[str, int] = {
            "contract_translated": 0,   # 命中合同 8 词映射（含覆盖表）
            "semantic_passthrough": 0,  # 在役 12 语义 ID 透传
            "unknown_fallback": 0,      # 词表外 → neutral 兜底
        }

    @staticmethod
    def _load_override(path: str | None) -> dict[str, str]:
        if not path or not os.path.isfile(path):
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(f"[TagTranslator] 映射覆盖表加载失败（使用内置表）: path={path}, error={e}")
            return {}
        if not isinstance(data, dict):
            logger.warning(f"[TagTranslator] 映射覆盖表格式非法（需为扁平 dict）: path={path}")
            return {}
        valid_ids = set(LUOMINEST_EMOTION_IDS)
        out: dict[str, str] = {}
        for key, value in data.items():
            # 仅接受 str→12 语义 ID 的条目；其余静默跳过（绝不报错）
            if isinstance(key, str) and isinstance(value, str) and value.strip().lower() in valid_ids:
                out[key.strip().lower()] = value.strip().lower()
        return out

    def translate(self, word: str) -> tuple[str, bool]:
        """翻译情绪词，返回 (语义 ID, 是否为已知词)。

        优先级：覆盖表 → 内置 8→12 映射 → 12 语义 ID 透传 → neutral 兜底（计数）。
        输入先做大小写/空白归一（宽松容错），永不抛错。
        """
        key = (word or "").strip().lower()
        if not key:
            self.counters["unknown_fallback"] += 1
            return DEFAULT_EMOTION_ID, False
        # 1) 覆盖表 / 内置映射（合同 8 词通道）
        mapped = self._override.get(key) or BUILTIN_EXP_TRANSLATION.get(key)
        if mapped:
            self.counters["contract_translated"] += 1
            return mapped, True
        # 2) 在役 12 语义 ID 透传（现役非自闭合 <exp:X> 行为不回退）
        if key in LUOMINEST_EMOTION_IDS:
            self.counters["semantic_passthrough"] += 1
            return key, True
        # 3) 兜底：词表外（含幻觉词）一律 neutral + 计数，绝不报错
        self.counters["unknown_fallback"] += 1
        return DEFAULT_EMOTION_ID, False


# 默认翻译器缓存：按 override 路径键控（配置变更后自动重建，无需重启之外的手段）
_translator_cache: dict[str, TagTranslator] = {}


def get_default_translator() -> TagTranslator:
    """按当前 settings.AVATAR_TRANSLATION_OVERRIDE 取默认翻译器（带缓存）。"""
    from app.core.config import settings

    path = (getattr(settings, "AVATAR_TRANSLATION_OVERRIDE", "") or "").strip()
    translator = _translator_cache.get(path)
    if translator is None:
        translator = TagTranslator(override_path=path or None)
        _translator_cache.clear()
        _translator_cache[path] = translator
    return translator
