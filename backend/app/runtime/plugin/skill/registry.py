"""CxSkill 注册表 — 管理技能元数据与 Prompt 注入。

参照 CxPluginRegistry 的异步锁 + 全局单例模式，使用 Cx 品牌前缀。
提供技能的注册/注销/查询/禁用能力，以及 Prompt 注入时的技能筛选。
"""
from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from app.runtime.plugin.skill.models import SkillDefinition, SkillStatus


class SkillRegistry:
    """技能注册表 — 全局单例。

    存储已加载的技能定义，提供查询、禁用、Prompt 注入等能力。
    """

    def __init__(self) -> None:
        self._skills: dict[str, SkillDefinition] = {}
        self._disabled: set[str] = set()
        self._lock = asyncio.Lock()

    async def register(self, skill: SkillDefinition) -> None:
        """注册技能定义。"""
        async with self._lock:
            # 应用禁用状态
            if skill.id in self._disabled:
                skill.status = SkillStatus.DISABLED
            self._skills[skill.id] = skill
            logger.debug(f"[CxSkill] Registered skill: {skill.id}")

    async def unregister(self, skill_id: str) -> None:
        """注销技能。"""
        async with self._lock:
            self._skills.pop(skill_id, None)
            logger.debug(f"[CxSkill] Unregistered skill: {skill_id}")

    def get(self, skill_id: str) -> SkillDefinition | None:
        """获取单个技能定义。"""
        return self._skills.get(skill_id)

    def list_skills(self, active_only: bool = False) -> list[SkillDefinition]:
        """列出所有技能。"""
        if active_only:
            return [s for s in self._skills.values() if s.is_active]
        return list(self._skills.values())

    def enable(self, skill_id: str) -> bool:
        """启用技能。"""
        skill = self._skills.get(skill_id)
        if skill is None:
            return False
        self._disabled.discard(skill_id)
        skill.status = SkillStatus.LOADED
        logger.info(f"[CxSkill] Enabled: {skill_id}")
        return True

    def disable(self, skill_id: str) -> bool:
        """禁用技能（不卸载，仅标记为禁用状态，不参与 Prompt 注入）。"""
        skill = self._skills.get(skill_id)
        if skill is None:
            return False
        self._disabled.add(skill_id)
        skill.status = SkillStatus.DISABLED
        logger.info(f"[CxSkill] Disabled: {skill_id}")
        return True

    def is_enabled(self, skill_id: str) -> bool:
        """检查技能是否启用。"""
        return skill_id not in self._disabled

    def get_disabled_ids(self) -> list[str]:
        """获取已禁用的技能 ID 列表。"""
        return list(self._disabled)

    def set_disabled_ids(self, skill_ids: list[str]) -> None:
        """批量设置禁用列表（用于持久化恢复）。"""
        self._disabled = set(skill_ids)
        # 更新已加载技能的状态
        for skill_id, skill in self._skills.items():
            if skill_id in self._disabled:
                skill.status = SkillStatus.DISABLED
            elif skill.status == SkillStatus.DISABLED:
                skill.status = SkillStatus.LOADED

    def build_skills_prompt(self, context: str = "", max_skills: int = 5) -> str:
        """构建注入到 LLM system prompt 的 <available_skills> 块。

        策略：
        1. 若 context 非空，优先匹配 trigger_keywords / name
        2. 若无匹配，返回空字符串（避免无差别注入污染上下文）
        3. 最多注入 max_skills 个技能，避免 prompt 过长

        Args:
            context: 用户最近消息文本，用于技能匹配
            max_skills: 最多注入的技能数量

        Returns:
            格式化的 <available_skills>...</available_skills> 块，无匹配时返回空字符串
        """
        active_skills = [s for s in self._skills.values() if s.is_active and s.body]
        if not active_skills:
            return ""

        # 匹配阶段
        matched: list[SkillDefinition] = []
        if context:
            for skill in active_skills:
                if skill.matches_context(context):
                    matched.append(skill)
        # 无匹配时不注入（避免无差别污染）
        if not matched:
            return ""

        # 限制数量
        matched = matched[:max_skills]
        if not matched:
            return ""

        # 构建注入块
        blocks: list[str] = []
        for skill in matched:
            blocks.append(
                f'<skill id="{skill.id}" name="{skill.name}">\n'
                f"{skill.body}\n"
                f"</skill>"
            )

        return (
            "<available_skills>\n"
            "以下是当前可用的技能。当用户的请求与某个技能匹配时，"
            "请按照技能描述的指引完成用户需求。\n\n"
            + "\n\n".join(blocks)
            + "\n</available_skills>"
        )

    def build_selected_skills_prompt(self, skill_ids: list[str]) -> str:
        """构建用户显式选择技能的 prompt 块（与自动匹配注入共用同一 <available_skills> 格式）。

        仅注入存在且已启用的技能；未知 / 已禁用的 skill_id 静默忽略。
        用户选择优先于关键词匹配：命中列表中的技能一定注入完整 body。

        Args:
            skill_ids: 用户本次请求显式选择的技能 ID 列表

        Returns:
            <available_skills> 块文本；无有效技能时返回空字符串
        """
        blocks: list[str] = []
        for skill_id in skill_ids or []:
            skill = self._skills.get(skill_id)
            if skill is None or not skill.is_active or not skill.body:
                continue
            blocks.append(
                f'<skill id="{skill.id}" name="{skill.name}">\n'
                f"{skill.body}\n"
                f"</skill>"
            )
        if not blocks:
            return ""

        return (
            "<available_skills>\n"
            "以下是用户本次会话显式选择的技能，请严格按照技能描述的指引完成用户需求：\n\n"
            + "\n\n".join(blocks)
            + "\n</available_skills>"
        )

    def build_skills_index_prompt(self) -> str:
        """构建技能索引 prompt（仅列出技能 id/name/description，不含 body）。

        用于让 AI 知道有哪些技能可用，从而在用户询问"你能做什么"时列出能力。
        始终注入（不依赖 context 匹配），但体积小。
        """
        active_skills = [s for s in self._skills.values() if s.is_active]
        if not active_skills:
            return ""

        lines: list[str] = []
        for skill in active_skills:
            desc = skill.description or skill.name
            lines.append(f"- {skill.id}: {desc}")

        return (
            "<skill_index>\n"
            "你具备以下技能能力。当用户的请求与某技能相关时，可主动应用相应技能：\n"
            + "\n".join(lines)
            + "\n</skill_index>"
        )

    def clear(self) -> None:
        """清空所有注册数据（热重载时使用）。"""
        self._skills.clear()
        # 不清空 _disabled，保留用户的禁用偏好

    def count(self) -> int:
        """已加载技能数量。"""
        return len(self._skills)

    def stats(self) -> dict[str, Any]:
        """返回注册表统计信息。"""
        return {
            "total": len(self._skills),
            "active": sum(1 for s in self._skills.values() if s.is_active),
            "disabled": len(self._disabled),
        }


# 全局单例
cx_skill_registry = SkillRegistry()
