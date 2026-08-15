"""CxSkill 系统 — LuomiNest 技能运行时核心。

公共 API 导出，供 app_factory 和 skill_service 使用。

模块组成：
- models：SkillDefinition（技能定义）+ SkillSourceFormat + SkillStatus
- loader：SkillLoader 扫描/解析 SKILL.md + manifest.json
- registry：SkillRegistry 全局注册表 + Prompt 注入

设计理念（参考 hermes-agent / Cyrene-Agent）：
- SKILL.md 为 AI 原生载体（YAML frontmatter + Markdown 指令体）
- 兼容现有 manifest.json（市场展示格式）
- AI 可直接理解技能内容并据此行动
- 用户可请求 AI 创建/修改技能，即时生效无需重启
"""

from app.runtime.plugin.skill.loader import SkillLoader, luominest_skill_loader
from app.runtime.plugin.skill.models import (
    SkillDefinition,
    SkillSourceFormat,
    SkillStatus,
)
from app.runtime.plugin.skill.registry import SkillRegistry, luominest_skill_registry

__all__ = [
    # 数据模型
    "SkillDefinition",
    "SkillSourceFormat",
    "SkillStatus",
    # 运行时组件
    "SkillLoader",
    "SkillRegistry",
    "luominest_skill_loader",
    "luominest_skill_registry",
]
