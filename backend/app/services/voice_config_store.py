"""语音配置存储门面 — config_items 权威源（voice-model-market.md §7.2，G3/G6 治理）。

键族（命名空间 KV，零迁移）：
- voice_config                     全局语音配置（权威源）
- voice.avatar_bindings.<model_id> 皮套模型音色绑定（替代 avatar_manager.py 硬编码）

迁移策略（幂等，voice_config._migration_meta.done 标记）：
1. 首次读取时从 model_config 的 tts*/stt* 字段回填 voice_config（已有键不覆盖）
2. avatar_manager.LUOMINEST_AVATAR_BINDINGS 硬编码作为种子数据写入
   voice.avatar_bindings.*（DB 中已存在的绑定不覆盖）
3. 前端 localStorage 降级为缓存，权威源一律以本门面为准

注意：所有 DB 访问延迟到方法调用时（避免 import 期查库导致启动崩溃，
见项目教训：platform.py/repo_source.py import 时查询会崩）。
"""
from __future__ import annotations

import threading
from typing import Any

from loguru import logger

# voice_config 默认结构（全局默认，§7.2）
DEFAULT_VOICE_CONFIG: dict[str, Any] = {
    "schema_version": 1,
    "tts": {
        "engine": "auto",
        "model": "",
        "voice": "zh-CN-XiaoxiaoNeural",
        "lang": "auto",
        "speed": 1.0,
    },
    "stt": {
        "engine": "auto",
        "model": "",
        "lang": "auto",
    },
    # 翻译管线（v0.5 决策：默认关闭，语言不匹配时通知引导开启）
    "translation": {
        "enabled": False,
        "source": "llm",  # llm | niutrans | pearktrue
    },
    "_migration_meta": {"done": False, "migrated_at": ""},
}

VOICE_CONFIG_KEY = "voice_config"
AVATAR_BINDINGS_PREFIX = "voice.avatar_bindings."


class LuomiNestVoiceConfigStore:
    """语音配置门面（线程安全内存缓存 + config_items 持久化）."""

    def __init__(self) -> None:
        self._cache: dict[str, Any] | None = None
        self._bindings_cache: dict[str, dict] | None = None
        self._lock = threading.Lock()
        self._migrated = False

    # ------------------------------------------------------------------
    # 内部：config_items 访问（懒加载，避免 import 期查库）
    # ------------------------------------------------------------------

    @staticmethod
    def _store():
        from app.infrastructure.database.config_store import lumi_config_store

        return lumi_config_store

    def _invalidate(self) -> None:
        with self._lock:
            self._cache = None
            self._bindings_cache = None

    # ------------------------------------------------------------------
    # 幂等迁移（§7.2 迁移策略）
    # ------------------------------------------------------------------

    def _ensure_migration(self) -> None:
        """首次访问时执行幂等迁移：model_config + avatar 硬编码 → 语音键族."""
        if self._migrated:
            return
        with self._lock:
            if self._migrated:
                return
            try:
                store = self._store()
                config = store.get(VOICE_CONFIG_KEY, None)
                if config is None:
                    config = dict(DEFAULT_VOICE_CONFIG)
                    # 1) model_config 的 tts*/stt* 字段回填（已有键不覆盖）
                    model_config = store.get("model_config", {}) or {}
                    tts = config.get("tts", {})
                    stt = config.get("stt", {})
                    if model_config.get("tts_provider"):
                        tts["engine"] = model_config["tts_provider"]
                    if model_config.get("tts_model"):
                        tts["model"] = model_config["tts_model"]
                    if model_config.get("tts_voice"):
                        tts["voice"] = model_config["tts_voice"]
                    if model_config.get("tts_speed"):
                        tts["speed"] = float(model_config["tts_speed"])
                    if model_config.get("stt_provider"):
                        stt["engine"] = model_config["stt_provider"]
                    if model_config.get("stt_model"):
                        stt["model"] = model_config["stt_model"]
                    if model_config.get("stt_language"):
                        stt["lang"] = model_config["stt_language"]
                    config["tts"] = tts
                    config["stt"] = stt

                meta = config.get("_migration_meta") or {}
                if not meta.get("done"):
                    meta["done"] = True
                    from datetime import datetime

                    meta["migrated_at"] = datetime.now().isoformat(timespec="seconds")
                    config["_migration_meta"] = meta
                    store.set(VOICE_CONFIG_KEY, config)
                    logger.info("[VoiceConfigStore] voice_config initialized (migrated from model_config)")

                # 2) avatar 硬编码绑定 → voice.avatar_bindings.*（DB 已有不覆盖）
                self._migrate_avatar_bindings()
                self._migrated = True
            except Exception as e:
                # 数据库未就绪等情况：跳过迁移，读取时回退默认值（不阻塞启动）
                logger.debug(f"[VoiceConfigStore] migration deferred: {e}")

    def _migrate_avatar_bindings(self) -> None:
        """avatar_manager 硬编码绑定作为种子数据入库（幂等：DB 已有不覆盖）."""
        store = self._store()
        raw = store.get_namespace(AVATAR_BINDINGS_PREFIX)
        existing = {k.removeprefix(AVATAR_BINDINGS_PREFIX) for k in raw}
        from app.services.avatar_manager import LUOMINEST_AVATAR_BINDINGS

        seeded = False
        for model_id, binding in LUOMINEST_AVATAR_BINDINGS.items():
            if model_id in existing:
                continue
            store.set(
                f"{AVATAR_BINDINGS_PREFIX}{model_id}",
                {
                    "model_id": model_id,
                    "voice": binding.voice,
                    "voice_lang": binding.voice_lang,
                    "expression_map": dict(binding.expression_map),
                    "default_expression": binding.default_expression,
                },
            )
            seeded = True
        if seeded:
            logger.info(
                f"[VoiceConfigStore] avatar bindings seeded: "
                f"db={sorted(existing)} builtin={sorted(LUOMINEST_AVATAR_BINDINGS)}"
            )

    # ------------------------------------------------------------------
    # 全局语音配置（voice_config）
    # ------------------------------------------------------------------

    def get_voice_config(self) -> dict[str, Any]:
        """读取全局语音配置（含默认值合并）."""
        self._ensure_migration()
        if self._cache is not None:
            return self._cache
        try:
            stored = self._store().get(VOICE_CONFIG_KEY, None)
        except Exception:
            stored = None
        config = stored if isinstance(stored, dict) else dict(DEFAULT_VOICE_CONFIG)
        # 与默认结构合并（新增字段向后兼容）
        merged = dict(DEFAULT_VOICE_CONFIG)
        merged.update({k: v for k, v in config.items() if not k.startswith("_")})
        self._cache = merged
        return merged

    def save_voice_config(self, patch: dict[str, Any]) -> dict[str, Any]:
        """合并式更新全局语音配置（patch 覆盖对应字段）并持久化."""
        current = self.get_voice_config()
        for section in ("tts", "stt", "translation"):
            if isinstance(patch.get(section), dict):
                sec = current.get(section) or {}
                sec.update(patch[section])
                current[section] = sec
        # 顶层标量字段（schema_version 等）直接覆盖
        for k, v in patch.items():
            if not isinstance(v, dict) and not k.startswith("_"):
                current[k] = v
        self._store().set(VOICE_CONFIG_KEY, current)
        self._invalidate()
        self.get_voice_config()  # 重建缓存
        return current

    def get_translation_config(self) -> dict[str, Any]:
        """读取翻译管线配置（§8.3：enabled 默认 False）."""
        return self.get_voice_config().get("translation") or {"enabled": False, "source": "llm"}

    # ------------------------------------------------------------------
    # 皮套音色绑定（voice.avatar_bindings.*）
    # ------------------------------------------------------------------

    def get_avatar_bindings(self) -> dict[str, dict]:
        """读取全部皮套绑定（迁移后 DB 为权威源）.

        get_namespace 返回键含完整前缀（voice.avatar_bindings.llny），
        此处 strip 前缀，对外输出 {model_id: binding}。
        """
        self._ensure_migration()
        if self._bindings_cache is not None:
            return self._bindings_cache
        try:
            raw = self._store().get_namespace(AVATAR_BINDINGS_PREFIX)
        except Exception:
            raw = {}
        bindings = {
            k.removeprefix(AVATAR_BINDINGS_PREFIX): v for k, v in raw.items()
        }
        self._bindings_cache = bindings
        return bindings

    def get_avatar_binding(self, model_id: str) -> dict | None:
        """读取单个皮套绑定."""
        return self.get_avatar_bindings().get(model_id)

    def save_avatar_binding(self, model_id: str, patch: dict[str, Any]) -> dict:
        """合并式更新皮套绑定并持久化（voice.py PUT /voice/avatar-bindings/{model_id} 后端）."""
        bindings = self.get_avatar_bindings()
        current = bindings.get(model_id) or {"model_id": model_id}
        current.update({k: v for k, v in patch.items() if k != "model_id"})
        current["model_id"] = model_id
        self._store().set(f"{AVATAR_BINDINGS_PREFIX}{model_id}", current)
        self._invalidate()
        return current


# ── 单例 ──

luominest_voice_config_store = LuomiNestVoiceConfigStore()
