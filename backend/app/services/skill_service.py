"""CxSkill 业务服务层 — LuomiNest 技能系统的对外门面。

封装 SkillLoader 与 SkillRegistry 的复杂调用，向上为 API/ContextService 提供
简洁的业务接口：列表/详情/启禁用/重载/Prompt 注入。

设计原则：
- 单例模式：全局 cx_skill_service，避免多次实例化导致的状态不一致
- 轻量委托：本层不持有运行时数据，仅做参数校验与转发
- 持久化禁用偏好：使用 JsonStore 保存用户禁用的 skill_id，重启后自动恢复
- 错误透明：异常抛出给调用方，由 API 层统一包装为 ApiResponse
"""
from __future__ import annotations

from typing import Any

from loguru import logger

from app.infrastructure.database.json_store import JsonStore
from app.runtime.plugin.skill.loader import cx_skill_loader
from app.runtime.plugin.skill.registry import cx_skill_registry


# 禁用偏好持久化（id 列表）
_disabled_store = JsonStore("cx_skill_disabled.json")


class CxSkillService:
    """技能业务服务层 — 全局单例 cx_skill_service。

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
        # 恢复用户的禁用偏好
        disabled_ids = _disabled_store.get("disabled_ids", [])
        if isinstance(disabled_ids, list) and disabled_ids:
            cx_skill_registry.set_disabled_ids([str(i) for i in disabled_ids])
            logger.info(f"[CxSkillService] Restored {len(disabled_ids)} disabled skill id(s)")

        # 扫描并加载所有技能
        count = await cx_skill_loader.load_all()
        logger.info(f"[CxSkillService] Initialized: {count} skill(s) loaded")
        return count

    # ------------------------------------------------------------------
    # 查询接口
    # ------------------------------------------------------------------

    def list_skills(self, active_only: bool = False) -> list[dict[str, Any]]:
        """列出所有技能的元数据（不含 body 全文）。"""
        skills = cx_skill_registry.list_skills(active_only=active_only)
        return [s.to_dict() for s in skills]

    def get_skill(self, skill_id: str) -> dict[str, Any] | None:
        """获取单个技能详情（含 body 全文）。"""
        skill = cx_skill_registry.get(skill_id)
        if skill is None:
            return None
        return skill.to_detail_dict()

    def get_stats(self) -> dict[str, Any]:
        """返回技能系统统计信息。"""
        return cx_skill_registry.stats()

    # ------------------------------------------------------------------
    # 启用/禁用（带持久化）
    # ------------------------------------------------------------------

    def enable_skill(self, skill_id: str) -> bool:
        """启用技能。返回是否操作成功（skill 是否存在）。"""
        ok = cx_skill_registry.enable(skill_id)
        if ok:
            self._persist_disabled()
        return ok

    def disable_skill(self, skill_id: str) -> bool:
        """禁用技能。返回是否操作成功（skill 是否存在）。"""
        ok = cx_skill_registry.disable(skill_id)
        if ok:
            self._persist_disabled()
        return ok

    def _persist_disabled(self) -> None:
        """将当前禁用列表持久化到 JsonStore。"""
        disabled_ids = cx_skill_registry.get_disabled_ids()
        _disabled_store.set("disabled_ids", disabled_ids)

    # ------------------------------------------------------------------
    # 重载
    # ------------------------------------------------------------------

    async def reload_skill(self, skill_id: str) -> bool:
        """重载单个技能（用于 SKILL.md 修改后热更新）。"""
        ok = await cx_skill_loader.reload_single(skill_id)
        if ok:
            logger.info(f"[CxSkillService] Reloaded skill: {skill_id}")
        return ok

    async def reload_all(self) -> int:
        """重载所有技能。"""
        count = await cx_skill_loader.reload_all()
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
        return cx_skill_registry.build_skills_index_prompt()

    def get_skills_prompt_for_injection(self, context: str = "", max_skills: int = 5) -> str:
        """获取技能注入 prompt（按上下文匹配，含 body）。

        供 ContextService 在用户消息匹配到技能时注入完整指令体。

        Args:
            context: 用户最近消息文本，用于匹配 trigger_keywords
            max_skills: 最多注入的技能数量

        Returns:
            <available_skills> 块字符串，无匹配时返回空字符串
        """
        return cx_skill_registry.build_skills_prompt(context=context, max_skills=max_skills)

    # ------------------------------------------------------------------
    # 卸载（用于热重载/卸载场景）
    # ------------------------------------------------------------------

    async def unload_skill(self, skill_id: str) -> bool:
        """卸载技能（不删除文件，仅从注册表移除）。"""
        return await cx_skill_loader.unload_single(skill_id)

    # ------------------------------------------------------------------
    # 写入与删除（供 skill-creator 元技能 / API 调用）
    # ------------------------------------------------------------------

    def validate_skill_id(self, skill_id: str) -> None:
        """校验 skill_id 合法性（委托给 loader，统一错误信息）。"""
        cx_skill_loader.validate_skill_id(skill_id)

    def validate_skill_md_content(self, content: str, expected_id: str) -> dict[str, Any]:
        """校验 SKILL.md 内容合法性，返回 frontmatter。"""
        return cx_skill_loader.validate_skill_md_content(content, expected_id)

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
        import os

        self.validate_skill_id(skill_id)
        self.validate_skill_md_content(content, skill_id)

        skill_dir = os.path.join(cx_skill_loader._skill_dir, skill_id)
        skill_md_path = os.path.join(skill_dir, "SKILL.md")
        created = not os.path.isfile(skill_md_path)

        if not created and not overwrite:
            raise ValueError(f"技能已存在: {skill_id}（overwrite=False）")

        loaded = await cx_skill_loader.write_and_load(skill_id, content)
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
        result = await cx_skill_loader.delete_and_unload(skill_id)
        logger.info(f"[CxSkillService] Deleted skill: {skill_id} (ok={result})")
        return {
            "skill_id": skill_id,
            "deleted": result,
        }

    async def get_skill_raw_content(self, skill_id: str) -> str | None:
        """获取 SKILL.md 原始文本内容（供编辑接口使用）。

        若 skill 不存在返回 None。
        """
        import os

        skill = cx_skill_registry.get(skill_id)
        if skill is None:
            return None
        if not skill.source_path or not os.path.isfile(skill.source_path):
            return None
        with open(skill.source_path, encoding="utf-8") as f:
            return f.read()


# 全局单例
cx_skill_service = CxSkillService()
