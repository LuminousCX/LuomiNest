"""CxSkill 数据模型 — LuomiNest 技能元数据与状态定义。

Skill（技能）是参考 hermes-agent 和 Cyrene-Agent 设计的轻量级能力单元：
- 本质是结构化的 Prompt + 配置 + 资源文件
- 以 SKILL.md（YAML frontmatter + Markdown 指令体）为主要载体
- 兼容现有 manifest.json 格式（用于市场展示）
- AI 大模型可直接理解 Skill 内容并据此行动
- 用户可请求 AI 修改或创建新 Skill，无需重启即时生效

数据契约：
- SkillSourceFormat：技能来源格式（SKILL.md / manifest.json / 双轨）
- SkillDefinition：技能定义数据类（含 prompt 注入体）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.core.utils import utc_now


class SkillSourceFormat(str, Enum):
    """技能来源格式 — 区分 SKILL.md 与 manifest.json 两种载体。"""

    SKILL_MD = "skill_md"          # 仅 SKILL.md（YAML frontmatter + Markdown body）
    MANIFEST_JSON = "manifest_json"  # 仅 manifest.json（市场展示格式）
    BOTH = "both"                   # 双轨：SKILL.md + manifest.json 共存


class SkillStatus(str, Enum):
    """技能运行时状态。"""

    LOADED = "loaded"
    DISABLED = "disabled"
    ERROR = "error"


@dataclass
class SkillDefinition:
    """技能定义 — 解析后的技能数据模型。

    SKILL.md 与 manifest.json 双轨格式的统一表示。
    body 字段为注入到 LLM Prompt 的指令体（Markdown）。
    """

    id: str
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    author: str = ""
    license: str = ""

    # Prompt 注入体（Markdown 指令）— SKILL.md 的 body，或从 manifest.json 构造
    body: str = ""

    # 分类与标签（用于市场展示与过滤）
    tags: list[str] = field(default_factory=list)
    category: str = ""
    icon: str = ""

    # 来源信息
    source_path: str = ""                                  # SKILL.md 或 manifest.json 路径
    source_format: SkillSourceFormat = SkillSourceFormat.SKILL_MD
    skill_dir: str = ""                                    # 技能目录路径

    # 额外元数据（frontmatter 中除标准字段外的内容）
    metadata: dict[str, Any] = field(default_factory=dict)

    # 触发关键词（用于 Prompt 注入时的简单匹配；后续可升级为语义搜索）
    trigger_keywords: list[str] = field(default_factory=list)

    # 运行时状态
    status: SkillStatus = SkillStatus.LOADED
    loaded_at: str = field(default_factory=utc_now)
    error_message: str = ""

    @property
    def is_active(self) -> bool:
        """技能是否处于可用状态。"""
        return self.status == SkillStatus.LOADED

    def to_dict(self) -> dict[str, Any]:
        """转为 API 响应字典（不含 body 全文，避免列表接口过大）。"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "license": self.license,
            "tags": self.tags,
            "category": self.category,
            "icon": self.icon,
            "source_format": self.source_format.value,
            "skill_dir": self.skill_dir,
            "trigger_keywords": self.trigger_keywords,
            "status": self.status.value,
            "loaded_at": self.loaded_at,
            "error_message": self.error_message,
            "body_length": len(self.body),
            "has_body": bool(self.body),
        }

    def to_detail_dict(self) -> dict[str, Any]:
        """转为详情字典（包含 body 全文，供详情接口使用）。"""
        result = self.to_dict()
        result["body"] = self.body
        result["metadata"] = self.metadata
        return result

    def matches_context(self, context: str) -> bool:
        """判断当前上下文是否应触发该技能。

        匹配策略（任一命中即触发）：
        1. trigger_keywords 中任一关键词出现在 context 中（大小写不敏感）
        2. name 中的词出现在 context 中
        3. 无 trigger_keywords 时始终返回 False（避免无差别注入）

        后续可升级为基于 embedding 的语义匹配。
        """
        if not self.is_active:
            return False
        if not context:
            return False
        context_lower = context.casefold()

        # 1. trigger_keywords 匹配
        for kw in self.trigger_keywords:
            if kw and kw.casefold() in context_lower:
                return True

        # 2. name 中的词匹配（按空格/中文字符切分）
        if self.name:
            # 简单切分：中文按字符，英文按空格
            name_words = [w for w in self.name.split() if len(w) >= 2]
            for word in name_words:
                if word.casefold() in context_lower:
                    return True

        return False
