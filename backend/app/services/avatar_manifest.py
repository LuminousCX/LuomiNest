"""LuomiNest Avatar Manifest Manager.

聚合 builtin + imported 模型清单，提供查询/导入/删除/绑定更新等操作。

设计原则：
- manifest 是模型清单的唯一权威来源，前后端共享同一份数据
- builtin manifest 静态文件位于 backend/app/data/avatar-manifest.json
- imported 模型元数据持久化到 userData（由前端 Electron 管理）
  后端通过 API 接收前端上报的 imported 元数据，聚合后返回完整 manifest
- 不修改 avatar_manager.py 中的 EmotionStreamParser / SUPPORTED_EMOTION_IDS
  / strip_emotion_tags，仅通过 get_avatar_binding() 委托读 manifest
"""
from __future__ import annotations

import json
import asyncio
from pathlib import Path
from typing import Any
from loguru import logger

from app.core.config import settings
from app.schemas.avatar import (
    AvatarManifest,
    AvatarManifestModel,
    AvatarBinding,
    AvatarBindingUpdate,
    AvatarType,
)


# ---------------------------------------------------------------------------
# 默认路径
# ---------------------------------------------------------------------------

# builtin manifest 是只读静态资源，跟随代码包发布（开发态位于 backend/app/data/）
# 打包态不打包此文件，前端从 resources/live2d 直接加载内置模型，builtin manifest 仅用于开发态测试
_BUILTIN_MANIFEST_PATH = Path(__file__).resolve().parent.parent / "data" / "avatar-manifest.json"
# imported manifest 是用户可写数据，必须存放在 DATA_DIR 下：
# - 开发态：backend/data/avatar/imported-manifest.json
# - 打包态：userData/Data/backend/avatar/imported-manifest.json
# 注意：禁止使用 Path(__file__) 推导，打包后会落到只读的 _internal/ 目录导致写入失败
_IMPORTED_MANIFEST_PATH = Path(settings.DATA_DIR) / "avatar" / "imported-manifest.json"


# ---------------------------------------------------------------------------
# 单例 Manifest Manager
# ---------------------------------------------------------------------------

class AvatarManifestManager:
    """Avatar 模型清单管理器（线程安全单例）。

    使用 asyncio.Lock 保护内存中的 manifest 副本，避免并发写入冲突。
    builtin manifest 只读，imported manifest 可读写。
    """

    def __init__(
        self,
        builtin_path: Path = _BUILTIN_MANIFEST_PATH,
        imported_path: Path = _IMPORTED_MANIFEST_PATH,
    ) -> None:
        self._builtin_path = builtin_path
        self._imported_path = imported_path
        self._lock = asyncio.Lock()
        self._builtin_manifest: AvatarManifest = AvatarManifest(models=[])
        self._imported_manifest: AvatarManifest = AvatarManifest(models=[])
        self._binding_overrides: dict[str, AvatarBinding] = {}
        self._initialized = False

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------

    async def init(self) -> None:
        """加载 builtin + imported manifest。在 lifespan 中调用。"""
        async with self._lock:
            self._builtin_manifest = self._load_builtin()
            self._imported_manifest = self._load_imported()
            self._initialized = True
            logger.info(
                f"[AvatarManifest] Initialized: "
                f"{len(self._builtin_manifest.models)} builtin + "
                f"{len(self._imported_manifest.models)} imported models"
            )

    def _load_builtin(self) -> AvatarManifest:
        if not self._builtin_path.exists():
            # 打包态不打包 builtin manifest（前端从 resources/live2d 加载内置模型），降级为 debug 日志
            logger.debug(f"[AvatarManifest] Builtin manifest not found: {self._builtin_path}")
            return AvatarManifest(models=[])
        try:
            raw = json.loads(self._builtin_path.read_text(encoding="utf-8"))
            return AvatarManifest.model_validate(raw)
        except Exception as e:
            logger.error(f"[AvatarManifest] Failed to load builtin manifest: {e}")
            return AvatarManifest(models=[])

    def _load_imported(self) -> AvatarManifest:
        if not self._imported_path.exists():
            return AvatarManifest(models=[])
        try:
            raw = json.loads(self._imported_path.read_text(encoding="utf-8"))
            return AvatarManifest.model_validate(raw)
        except Exception as e:
            logger.warning(f"[AvatarManifest] Failed to load imported manifest: {e}")
            return AvatarManifest(models=[])

    def _persist_imported(self) -> None:
        """持久化 imported manifest 到磁盘。"""
        try:
            self._imported_path.parent.mkdir(parents=True, exist_ok=True)
            self._imported_path.write_text(
                self._imported_manifest.model_dump_json(indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.error(f"[AvatarManifest] Failed to persist imported manifest: {e}")

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    async def list_models(
        self,
        type_filter: AvatarType | None = None,
        source_filter: str | None = None,
    ) -> list[AvatarManifestModel]:
        """列出所有模型（builtin + imported），支持按 type/source 过滤。"""
        if not self._initialized:
            await self.init()
        async with self._lock:
            models: list[AvatarManifestModel] = []
            for m in list(self._builtin_manifest.models) + list(self._imported_manifest.models):
                if type_filter and m.type != type_filter:
                    continue
                if source_filter and m.source != source_filter:
                    continue
                # 应用 binding override（用户自定义的 binding）
                if m.id in self._binding_overrides:
                    m = m.model_copy(update={"binding": self._binding_overrides[m.id]})
                models.append(m)
            return models

    async def get_model(self, model_id: str) -> AvatarManifestModel | None:
        if not self._initialized:
            await self.init()
        async with self._lock:
            for m in list(self._builtin_manifest.models) + list(self._imported_manifest.models):
                if m.id == model_id:
                    if m.id in self._binding_overrides:
                        return m.model_copy(update={"binding": self._binding_overrides[m.id]})
                    return m
            return None

    async def get_binding(self, model_id: str) -> AvatarBinding | None:
        """获取模型绑定。委托给 manifest，保留向后兼容签名。"""
        model = await self.get_model(model_id)
        if not model:
            return None
        return model.binding

    async def get_full_manifest(self) -> AvatarManifest:
        """返回完整 manifest（聚合 builtin + imported）。"""
        models = await self.list_models()
        return AvatarManifest(schema_version="1.0", models=models)

    # ------------------------------------------------------------------
    # 增删改（仅 imported 可改）
    # ------------------------------------------------------------------

    async def add_imported_model(self, model: AvatarManifestModel) -> bool:
        """添加导入模型条目。"""
        if model.source != "imported":
            logger.warning(f"[AvatarManifest] Cannot add non-imported model: {model.id}")
            return False
        async with self._lock:
            existing_ids = {m.id for m in self._imported_manifest.models}
            existing_ids.update({m.id for m in self._builtin_manifest.models})
            if model.id in existing_ids:
                logger.warning(f"[AvatarManifest] Model ID already exists: {model.id}")
                return False
            self._imported_manifest.models.append(model)
            self._persist_imported()
            logger.info(f"[AvatarManifest] Imported model added: {model.id} ({model.type})")
            return True

    async def delete_model(self, model_id: str) -> bool:
        """删除导入的模型（builtin 不可删）。"""
        async with self._lock:
            for i, m in enumerate(self._imported_manifest.models):
                if m.id == model_id:
                    self._imported_manifest.models.pop(i)
                    self._binding_overrides.pop(model_id, None)
                    self._persist_imported()
                    logger.info(f"[AvatarManifest] Imported model deleted: {model_id}")
                    return True
            logger.warning(f"[AvatarManifest] Cannot delete (not found or builtin): {model_id}")
            return False

    async def update_binding(
        self,
        model_id: str,
        update: AvatarBindingUpdate,
    ) -> AvatarBinding | None:
        """更新模型绑定（builtin 通过 override 保留，imported 直接写入）。"""
        async with self._lock:
            target: AvatarManifestModel | None = None
            is_builtin = False
            for m in self._builtin_manifest.models:
                if m.id == model_id:
                    target = m
                    is_builtin = True
                    break
            if not target:
                for m in self._imported_manifest.models:
                    if m.id == model_id:
                        target = m
                        break

            if not target or not target.binding:
                return None

            current = target.binding
            if is_builtin:
                # builtin 通过 override 保留，不修改原文件
                override = self._binding_overrides.get(model_id, current.model_copy())
                if update.voice is not None:
                    override = override.model_copy(update={"voice": update.voice})
                if update.voice_lang is not None:
                    override = override.model_copy(update={"voice_lang": update.voice_lang})
                if update.expression_map is not None:
                    override = override.model_copy(update={"expression_map": update.expression_map})
                if update.default_expression is not None:
                    override = override.model_copy(update={"default_expression": update.default_expression})
                self._binding_overrides[model_id] = override
                self._persist_imported()  # 把 override 也持久化（保存在 imported-manifest.json 中扩展字段）
                logger.info(f"[AvatarManifest] Builtin binding overridden: {model_id}")
                return override
            else:
                # imported 直接修改
                if update.voice is not None:
                    current.voice = update.voice
                if update.voice_lang is not None:
                    current.voice_lang = update.voice_lang
                if update.expression_map is not None:
                    current.expression_map = update.expression_map
                if update.default_expression is not None:
                    current.default_expression = update.default_expression
                self._persist_imported()
                logger.info(f"[AvatarManifest] Imported binding updated: {model_id}")
                return current


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

avatar_manifest_manager = AvatarManifestManager()


def get_avatar_manifest_manager() -> AvatarManifestManager:
    """获取 AvatarManifestManager 全局单例。"""
    return avatar_manifest_manager


# ---------------------------------------------------------------------------
# 向后兼容：从 manifest 解析 binding（替代原 LUOMINEST_AVATAR_BINDINGS）
# ---------------------------------------------------------------------------

async def get_avatar_binding_async(model_id: str | None) -> AvatarBinding | None:
    """异步版 get_avatar_binding，从 manifest 读取。

    替代 avatar_manager.py 中同步的 get_avatar_binding()，
    后者保留作为 chat_service 等模块的快速同步回退（避免 import-time await）。
    """
    if not model_id:
        return None
    return await avatar_manifest_manager.get_binding(model_id)
