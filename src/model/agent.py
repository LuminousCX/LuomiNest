"""Agent 人格数据模型。

定义 Agent 人格的 ORM 模型、Pydantic 实体和枚举类型。
采用 SQLAlchemy ORM 进行数据库持久化，Pydantic 用于 API 数据校验。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import JSON, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.model.base import DeclarativeBaseModel
from src.utils.datetime_utils import now_beijing


class AgentType(str, Enum):
    """Agent 人格类型。"""

    PRESET = "preset"
    CUSTOM = "custom"


class AgentStatus(str, Enum):
    """Agent 人格状态。"""

    ACTIVE = "active"
    INACTIVE = "inactive"


class AgentModel(DeclarativeBaseModel):
    """Agent 人格 SQLAlchemy ORM 模型。

    对应数据库表 agent，存储人格的结构化数据。
    """

    __tablename__ = "agent"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="人格名称")
    avatar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="头像URL")
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="", comment="一句话介绍")
    background: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="经历背景")
    personality: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="性格特点")
    speaking_style: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="说话风格")
    constraints: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="行为约束")
    prompt_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="自定义prompt模板")
    response_config: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, comment="响应配置"
    )
    agent_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="custom", comment="人格类型"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", comment="状态"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    def __repr__(self) -> str:
        return f"<AgentModel(id={self.id}, name='{self.name}', type='{self.agent_type}')>"


class ResponseConfig(BaseModel):
    """Agent 响应配置。"""

    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="模型温度")
    max_tokens: int = Field(default=1024, ge=1, le=8192, description="最大输出token数")
    response_length: str = Field(default="detailed", description="回复长度偏好")
    tone: str = Field(default="友好", description="语气风格")
    format_preference: str = Field(default="markdown", description="输出格式偏好")
    emoji_usage: bool = Field(default=False, description="是否使用emoji")


class AgentEntity(BaseModel):
    """Agent 人格实体（Pydantic 模型）。

    用于业务逻辑层和 API 层的数据传输。
    """

    id: Optional[int] = Field(default=None, description="主键ID")
    name: str = Field(..., min_length=1, max_length=50, description="人格名称")
    avatar: Optional[str] = Field(default=None, max_length=500, description="头像URL")
    title: str = Field(default="", max_length=200, description="一句话介绍")
    background: str = Field(default="", max_length=5000, description="经历背景")
    personality: str = Field(default="", max_length=2000, description="性格特点")
    speaking_style: str = Field(default="", max_length=2000, description="说话风格")
    constraints: str = Field(default="", max_length=3000, description="行为约束")
    prompt_template: Optional[str] = Field(default=None, max_length=10000, description="自定义prompt模板")
    response_config: ResponseConfig = Field(
        default_factory=ResponseConfig, description="响应配置"
    )
    agent_type: AgentType = Field(default=AgentType.CUSTOM, description="人格类型")
    status: AgentStatus = Field(default=AgentStatus.ACTIVE, description="状态")
    created_at: datetime = Field(default_factory=now_beijing, description="创建时间")
    updated_at: datetime = Field(default_factory=now_beijing, description="更新时间")

    def build_system_prompt(self, template_service=None, memories: list[str] | None = None) -> str:
        """构建系统 prompt。

        Args:
            template_service: Prompt 模板服务实例。
            memories: 召回的记忆内容列表。

        Returns:
            完整的系统 prompt 字符串。
        """
        if template_service is not None:
            return template_service.render_system_prompt(self, memories=memories)
        return self._build_prompt_fallback(memories)

    def _build_prompt_fallback(self, memories: list[str] | None = None) -> str:
        """后备方法：直接拼接 prompt。"""
        parts: list[str] = []

        if self.prompt_template:
            parts.append(self.prompt_template)

        if self.name:
            parts.append(f"你的名字是「{self.name}」。")

        if self.title:
            parts.append(f"你的简介：{self.title}")

        if self.background:
            parts.append(f"你的经历：{self.background}")

        if self.personality:
            parts.append(f"你的性格：{self.personality}")

        if self.speaking_style:
            parts.append(f"你的说话风格：{self.speaking_style}")

        if self.constraints:
            parts.append(f"你的行为约束：{self.constraints}")

        if memories:
            memory_text = "\n".join(f"- {m}" for m in memories)
            parts.append(f"以下是用户的历史记忆，请结合记忆回答问题：\n{memory_text}")

        config = self.response_config
        style_parts: list[str] = []
        if config.tone:
            style_parts.append(f"语气风格：{config.tone}")
        if config.format_preference:
            style_parts.append(f"输出格式偏好：{config.format_preference}")
        if config.response_length:
            style_parts.append(f"回复长度偏好：{config.response_length}")
        if not config.emoji_usage:
            style_parts.append("不要使用 emoji")

        if style_parts:
            parts.append("你的回答风格：" + "；".join(style_parts) + "。")

        return "\n".join(parts)

    def to_orm_model(self) -> AgentModel:
        """转换为 SQLAlchemy ORM 模型。"""
        return AgentModel(
            id=self.id,
            name=self.name,
            avatar=self.avatar,
            title=self.title,
            background=self.background,
            personality=self.personality,
            speaking_style=self.speaking_style,
            constraints=self.constraints,
            prompt_template=self.prompt_template,
            response_config=self.response_config.model_dump(),
            agent_type=self.agent_type.value,
            status=self.status.value,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_orm_model(cls, orm_model: AgentModel) -> AgentEntity:
        """从 SQLAlchemy ORM 模型创建实体。"""
        response_config_data = orm_model.response_config or {}
        constraints = getattr(orm_model, "constraints", "") or ""
        return cls(
            id=orm_model.id,
            name=orm_model.name,
            avatar=orm_model.avatar,
            title=orm_model.title or "",
            background=orm_model.background or "",
            personality=orm_model.personality or "",
            speaking_style=orm_model.speaking_style or "",
            constraints=constraints,
            prompt_template=orm_model.prompt_template,
            response_config=ResponseConfig(**response_config_data),
            agent_type=AgentType(orm_model.agent_type),
            status=AgentStatus(orm_model.status),
            created_at=orm_model.created_at,
            updated_at=orm_model.updated_at,
        )


class PresetAgentConfig:
    """预设 Agent 人格配置。"""

    PRESET_AGENTS: list[dict[str, Any]] = [
        {
            "name": "代可行",
            "agent_type": AgentType.PRESET,
            "title": "热爱手搓的程序员，什么都能行",
            "background": (
                "全栈工程师，10年开发经验，精通 Python、JavaScript、Rust。"
                "热爱开源，喜欢从零手搓各种工具和框架。"
                "信奉「Talk is cheap, show me the code」。"
                "擅长系统架构设计、性能优化、DevOps。"
            ),
            "personality": "热情、务实、直接、乐于分享",
            "speaking_style": "喜欢用代码说话，回答中会包含完整的代码示例，主动指出潜在问题",
            "constraints": "不编造不确定的技术信息，不推荐未经验证的方案",
            "prompt_template": (
                "你是一位热爱手搓的程序员，名叫「代可行」。"
                "你总是充满热情地帮助用户解决技术问题，"
                "喜欢用代码说话，回答中会包含完整的代码示例。"
                "你会主动指出代码中的潜在问题，并给出优化建议。"
                "遇到不确定的问题，你会坦诚说明，而不是编造答案。"
            ),
            "response_config": {
                "temperature": 0.5,
                "max_tokens": 2048,
                "response_length": "detailed",
                "tone": "热情务实",
                "format_preference": "markdown",
                "emoji_usage": False,
            },
        },
        {
            "name": "无言",
            "agent_type": AgentType.PRESET,
            "title": "寡言的自由撰稿人，字字珠玑",
            "background": (
                "自由撰稿人，15年文字工作经验。"
                "曾为多家知名媒体撰写深度报道和专栏。"
                "信奉「少即是多」，每一个字都经过反复推敲。"
                "擅长文案创作、品牌故事、深度分析。"
            ),
            "personality": "沉稳、内敛、深思熟虑、审美极高",
            "speaking_style": "惜字如金，每句话都经过深思熟虑，简洁有力，直击要害",
            "constraints": "不做无意义的寒暄，不使用多余修饰词",
            "prompt_template": (
                "你是一位寡言的自由撰稿人，名叫「无言」。"
                "你惜字如金，但每句话都经过深思熟虑。"
                "你的回答简洁有力，直击要害。"
                "你不使用多余的修饰词，不做无意义的寒暄。"
                "在文字创作方面，你有极高的审美标准。"
            ),
            "response_config": {
                "temperature": 0.3,
                "max_tokens": 512,
                "response_length": "concise",
                "tone": "沉稳内敛",
                "format_preference": "plain",
                "emoji_usage": False,
            },
        },
        {
            "name": "林且慢",
            "agent_type": AgentType.PRESET,
            "title": "少年系辅导员，温柔且耐心",
            "background": (
                "高校辅导员，8年学生工作经验。"
                "擅长倾听和共情，总是能从学生的角度理解问题。"
                "喜欢用温暖的方式引导，而非说教。"
                "对学业规划、职业发展、人际关系有丰富经验。"
            ),
            "personality": "温柔、耐心、善于倾听、富有同理心",
            "speaking_style": "总是先倾听再回应，善于用类比和故事解释复杂概念，给予情感支持",
            "constraints": "不说教，不评判，尊重每个人的节奏",
            "prompt_template": (
                "你是一位温柔耐心的辅导员，名叫「林且慢」。"
                "你总是先倾听，再回应，从不急于下结论。"
                "你善于用类比和故事来解释复杂的概念。"
                "你关心用户的感受，会在回答中给予情感支持。"
                "你相信每个人都有自己的节奏，不需要和别人比较。"
                "遇到困难时，你会鼓励用户一步一步来，不着急。"
            ),
            "response_config": {
                "temperature": 0.6,
                "max_tokens": 2048,
                "response_length": "detailed",
                "tone": "温柔耐心",
                "format_preference": "markdown",
                "emoji_usage": False,
            },
        },
    ]
