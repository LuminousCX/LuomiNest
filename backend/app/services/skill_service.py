"""CxSkill 业务服务层 — LuomiNest 技能系统的对外门面。

封装 SkillLoader 与 SkillRegistry 的复杂调用，向上为 API/ContextService 提供
简洁的业务接口：列表/详情/启禁用/重载/Prompt 注入。

设计原则：
- 单例模式：全局 luominest_skill_service，避免多次实例化导致的状态不一致
- 轻量委托：本层不持有运行时数据，仅做参数校验与转发
- 持久化禁用偏好：使用 luominest_config_store（SQLite config_items 表）保存用户禁用的 skill_id，重启后自动恢复
- 错误透明：异常抛出给调用方，由 API 层统一包装为 ApiResponse
"""
from __future__ import annotations

import os
from typing import Any

from loguru import logger

from app.infrastructure.database.config_store import luominest_config_store
from app.runtime.plugin.skill.loader import luominest_skill_loader
from app.runtime.plugin.skill.registry import luominest_skill_registry


# DB 存储 key（config_items 为唯一权威源）
_DB_KEY = "skills.disabled_ids"

# 遗留 JSON 文件（DATA_DIR/store/）—— 收敛后仅在迁移时读取一次，不再写入，也不删除文件本身
_LEGACY_JSON_FILENAME = "cx_skill_disabled.json"
# 遗留 JSON 文件（JsonStore 格式）中禁用 id 列表所在字段名
_LEGACY_JSON_FIELD = "disabled_ids"
# _migration_meta 标记源名：与 json_to_sqlite_migrator 共用同一标记，谁先执行谁标记，避免重复合并
_MIGRATION_SOURCE = "skill_disabled"


def _normalize_disabled_ids(value: Any) -> list[str]:
    """将 config_items 中的值规范化为 list[str]。

    兼容两种历史形状：
    - list：运行时直接写入（CxSkillService._persist_disabled）
    - dict：旧版迁移器写入的整个 JSON 文件内容（{"disabled_ids": [...]}）
    """
    if isinstance(value, list):
        return [str(i) for i in value]
    if isinstance(value, dict):
        raw = value.get(_LEGACY_JSON_FIELD, [])
        return [str(i) for i in raw] if isinstance(raw, list) else []
    return []


class CxSkillService:
    """技能业务服务层 — 全局单例 luominest_skill_service。

    提供技能管理的业务接口，封装加载器/注册表的细节，对外只暴露稳定的业务语义。
    """

    # ------------------------------------------------------------------
    # 初始化与生命周期
    # ------------------------------------------------------------------

    async def init(self) -> int:
        """初始化技能系统 — 恢复禁用偏好并加载所有技能。

        在 app_factory lifespan 中调用，CxPlugin 加载完成之后执行。

        Returns:
            成功加载的技能数量
        """
        # 幂等合并遗留 JSON 数据到 config_items（_migration_meta 标记保护，重跑不重复合并）
        self._merge_legacy_json()

        # 恢复用户的禁用偏好（config_items 唯一权威源）
        disabled_ids = _normalize_disabled_ids(luominest_config_store.get(_DB_KEY))
        if disabled_ids:
            luominest_skill_registry.set_disabled_ids(disabled_ids)
            logger.info(f"[CxSkillService] Restored {len(disabled_ids)} disabled skill id(s)")

        # 扫描并加载所有技能
        count = await luominest_skill_loader.load_all()
        logger.info(f"[CxSkillService] Initialized: {count} skill(s) loaded")
        return count

    # ------------------------------------------------------------------
    # 查询接口
    # ------------------------------------------------------------------

    def list_skills(self, active_only: bool = False) -> list[dict[str, Any]]:
        """列出所有技能的元数据（不含 body 全文）。"""
        skills = luominest_skill_registry.list_skills(active_only=active_only)
        return [s.to_dict() for s in skills]

    def get_skill(self, skill_id: str) -> dict[str, Any] | None:
        """获取单个技能详情（含 body 全文）。"""
        skill = luominest_skill_registry.get(skill_id)
        if skill is None:
            return None
        return skill.to_detail_dict()

    def get_stats(self) -> dict[str, Any]:
        """返回技能系统统计信息。"""
        return luominest_skill_registry.stats()

    # ------------------------------------------------------------------
    # 启用/禁用（带持久化）
    # ------------------------------------------------------------------

    def enable_skill(self, skill_id: str) -> bool:
        """启用技能。返回是否操作成功（skill 是否存在）。"""
        ok = luominest_skill_registry.enable(skill_id)
        if ok:
            self._persist_disabled()
        return ok

    def disable_skill(self, skill_id: str) -> bool:
        """禁用技能。返回是否操作成功（skill 是否存在）。"""
        ok = luominest_skill_registry.disable(skill_id)
        if ok:
            self._persist_disabled()
        return ok

    def _persist_disabled(self) -> None:
        """将当前禁用列表持久化到 config_items（唯一权威源）。"""
        disabled_ids = luominest_skill_registry.get_disabled_ids()
        luominest_config_store.set(_DB_KEY, disabled_ids)

    def _merge_legacy_json(self) -> None:
        """幂等合并遗留 JSON 文件（cx_skill_disabled.json）到 config_items。

        参照 json_to_sqlite_migrator 的 _migration_meta 标记模式：
        - 已标记迁移 → 直接跳过（重跑不重复合并）
        - JSON 文件不存在 → 仅记录标记
        - JSON 文件存在 → 与 config_items 现有值取并集合并，不覆盖
        遗留 JSON 文件是用户数据：仅迁移时读取，不删除文件本身。
        """
        from app.core.config import settings
        from app.infrastructure.database.migration.json_to_sqlite_migrator import (
            _is_migrated,
            _mark_migrated,
            _read_json_file,
        )

        try:
            if _is_migrated(_MIGRATION_SOURCE):
                return

            path = os.path.join(settings.DATA_DIR, "store", _LEGACY_JSON_FILENAME)
            data = _read_json_file(path)
            legacy_ids: list[str] = []
            if isinstance(data, dict):
                raw = data.get(_LEGACY_JSON_FIELD, [])
                if isinstance(raw, list):
                    legacy_ids = [str(i) for i in raw]

            if legacy_ids:
                existing = _normalize_disabled_ids(luominest_config_store.get(_DB_KEY))
                merged = existing + [i for i in legacy_ids if i not in existing]
                luominest_config_store.set(_DB_KEY, merged)
                logger.info(
                    f"[CxSkillService] Merged legacy JSON into config_items: "
                    f"{len(merged)} disabled skill id(s)"
                )

            _mark_migrated(_MIGRATION_SOURCE, len(legacy_ids))
        except Exception as e:
            logger.warning(f"[CxSkillService] Legacy JSON merge skipped: {e}")

    # ------------------------------------------------------------------
    # 重载
    # ------------------------------------------------------------------

    async def reload_skill(self, skill_id: str) -> bool:
        """重载单个技能（用于 SKILL.md 修改后热更新）。"""
        ok = await luominest_skill_loader.reload_single(skill_id)
        if ok:
            logger.info(f"[CxSkillService] Reloaded skill: {skill_id}")
        return ok

    async def reload_all(self) -> int:
        """重载所有技能。"""
        count = await luominest_skill_loader.reload_all()
        logger.info(f"[CxSkillService] Reloaded all skills: {count} loaded")
        return count

    # ------------------------------------------------------------------
    # Prompt 注入
    # ------------------------------------------------------------------

    def get_skills_index_prompt(self) -> str:
        """获取技能索引 prompt（始终注入，仅 id/name/description）。

        供 ContextService.build_system_prompt 使用，让 AI 知道当前有哪些技能可用，
        从而在用户询问"你能做什么"时能列出能力。
        """
        return luominest_skill_registry.build_skills_index_prompt()

    def get_skills_prompt_for_injection(self, context: str = "", max_skills: int = 5) -> str:
        """获取技能注入 prompt（按上下文匹配，含 body）。

        供 ContextService 在用户消息匹配到技能时注入完整指令体。

        Args:
            context: 用户最近消息文本，用于匹配 trigger_keywords
            max_skills: 最多注入的技能数量

        Returns:
            <available_skills> 块字符串，无匹配时返回空字符串
        """
        return luominest_skill_registry.build_skills_prompt(context=context, max_skills=max_skills)

    def build_selected_skills_prompt(self, skill_ids: list[str]) -> str:
        """构建用户显式选择技能的 prompt 块（含 body）。

        供 ContextService 在用户主动勾选技能时注入完整指令体，优先于关键词自动匹配。

        Args:
            skill_ids: 用户选择的技能 ID 列表

        Returns:
            <available_skills> 块字符串，无有效技能时返回空字符串
        """
        return luominest_skill_registry.build_selected_skills_prompt(skill_ids)

    # ------------------------------------------------------------------
    # 卸载（用于热重载/卸载场景）
    # ------------------------------------------------------------------

    async def unload_skill(self, skill_id: str) -> bool:
        """卸载技能（不删除文件，仅从注册表移除）。"""
        return await luominest_skill_loader.unload_single(skill_id)

    # ------------------------------------------------------------------
    # 写入与删除（供 skill-creator 元技能 / API 调用）
    # ------------------------------------------------------------------

    def validate_skill_id(self, skill_id: str) -> None:
        """校验 skill_id 合法性（委托给 loader，统一错误信息）。"""
        luominest_skill_loader.validate_skill_id(skill_id)

    def validate_skill_md_content(self, content: str, expected_id: str) -> dict[str, Any]:
        """校验 SKILL.md 内容合法性，返回 frontmatter。"""
        return luominest_skill_loader.validate_skill_md_content(content, expected_id)

    async def write_skill(self, skill_id: str, content: str, *, overwrite: bool = True) -> dict[str, Any]:
        """写入 SKILL.md（新建或更新），写后立即加载。

        Args:
            skill_id: 技能 id（kebab-case）
            content: SKILL.md 完整文本
            overwrite: 已存在时是否覆盖，默认 True

        Returns:
            操作结果字典，含 skill_id / path / created / loaded 字段

        Raises:
            ValueError: skill_id 或内容校验失败，或已存在且 overwrite=False
        """
        self.validate_skill_id(skill_id)
        self.validate_skill_md_content(content, skill_id)

        skill_dir = os.path.join(luominest_skill_loader._skill_dir, skill_id)
        skill_md_path = os.path.join(skill_dir, "SKILL.md")
        created = not os.path.isfile(skill_md_path)

        if not created and not overwrite:
            raise ValueError(f"技能已存在: {skill_id}（overwrite=False）")

        loaded = await luominest_skill_loader.write_and_load(skill_id, content)
        logger.info(
            f"[CxSkillService] Wrote skill: {skill_id} (created={created}, loaded={loaded})"
        )
        return {
            "skill_id": skill_id,
            "path": skill_md_path,
            "created": created,
            "loaded": loaded,
        }

    async def delete_skill(self, skill_id: str) -> dict[str, Any]:
        """删除技能（含目录与注册表）。

        Args:
            skill_id: 技能 id

        Returns:
            操作结果字典，含 skill_id / deleted / unloaded 字段

        Raises:
            ValueError: skill_id 校验失败
        """
        self.validate_skill_id(skill_id)
        result = await luominest_skill_loader.delete_and_unload(skill_id)
        logger.info(f"[CxSkillService] Deleted skill: {skill_id} (ok={result})")
        return {
            "skill_id": skill_id,
            "deleted": result,
        }

    async def get_skill_raw_content(self, skill_id: str) -> str | None:
        """获取 SKILL.md 原始文本内容（供编辑接口使用）。

        若 skill 不存在返回 None。
        """
        skill = luominest_skill_registry.get(skill_id)
        if skill is None:
            return None
        if not skill.source_path or not os.path.isfile(skill.source_path):
            return None
        with open(skill.source_path, encoding="utf-8") as f:
            return f.read()


# 全局单例
luominest_skill_service = CxSkillService()
