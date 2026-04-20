"""Prompt 模板渲染服务。

基于 Jinja2 实现 Agent 人格的 System Prompt 动态渲染。
前端只需传递 agent_id，后端根据 Agent 人设自动生成完整 prompt。
支持记忆上下文注入，将召回的记忆融入 Prompt。

优化特性：
- 记忆 Token 预算管理
- 记忆摘要压缩
- Jinja2 沙箱化防 SSTI
"""

from __future__ import annotations

import threading
from typing import Any, Optional

from jinja2 import SandboxedEnvironment, Template

from src.model.agent import AgentEntity
from src.utils.logger import get_logger
from src.utils.prompt_util import get_prompt_util

logger = get_logger()


class PromptTemplateService:
    """Prompt 模板渲染服务。

    封装 PromptUtil，提供 Agent 专用的渲染方法。
    支持记忆上下文注入。
    """

    def __init__(self) -> None:
        self._sandbox_env = SandboxedEnvironment()

    def render_system_prompt(
        self,
        agent: AgentEntity,
        extra_context: Optional[dict[str, Any]] = None,
        memories: Optional[list[dict]] = None,
        max_tokens: int = 2048,
        memory_token_budget: float = 0.3,
    ) -> str:
        """渲染 Agent 的 System Prompt（带 Token 预算管理）。

        Args:
            agent: Agent 实体，包含人设信息。
            extra_context: 额外的模板上下文变量。
            memories: 召回的记忆内容列表（结构化结果）。
            max_tokens: LLM 上下文窗口最大 Token 数。
            memory_token_budget: 记忆占总 Token 的比例（0~1）。

        Returns:
            渲染后的完整 System Prompt 字符串。
        """
        context = self._build_context(agent)
        if extra_context:
            context.update(extra_context)

        memory_max_tokens = int(max_tokens * memory_token_budget)
        context["memories"] = self._budget_memory_tokens(
            memories or [], memory_max_tokens
        )
        context["has_memories"] = len(context["memories"]) > 0

        prompt_util = get_prompt_util()
        rendered = prompt_util.render_agent_prompt(
            agent_id=agent.id,
            agent_name=agent.name,
            context=context,
        )

        logger.debug(
            f"System Prompt 渲染完成，Agent: {agent.name}, "
            f"记忆数: {len(context['memories'])}"
        )
        return rendered

    def render_custom_prompt(
        self,
        template_content: str,
        agent: AgentEntity,
        extra_context: Optional[dict[str, Any]] = None,
        memories: Optional[list[dict]] = None,
        max_tokens: int = 2048,
        memory_token_budget: float = 0.3,
    ) -> str:
        """使用自定义模板内容渲染 Prompt（带 Token 预算管理）。"""
        context = self._build_context(agent)
        if extra_context:
            context.update(extra_context)

        memory_max_tokens = int(max_tokens * memory_token_budget)
        context["memories"] = self._budget_memory_tokens(
            memories or [], memory_max_tokens
        )
        context["has_memories"] = len(context["memories"]) > 0

        template = self._sandbox_env.from_string(template_content)
        return template.render(**context).strip()

    def _build_context(
        self,
        agent: AgentEntity,
    ) -> dict[str, Any]:
        """构建模板渲染上下文。"""
        config = agent.response_config
        context = {
            "name": agent.name,
            "title": agent.title,
            "background": agent.background,
            "personality": agent.personality,
            "speaking_style": agent.speaking_style,
            "constraints": agent.constraints,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "response_length": config.response_length,
            "tone": config.tone,
            "format_preference": config.format_preference,
            "emoji_usage": config.emoji_usage,
            "memories": [],
            "has_memories": False,
        }

        return context

    def _budget_memory_tokens(
        self,
        memories: list[dict],
        max_tokens: int,
    ) -> list[str]:
        """根据 Token 预算过滤和压缩记忆。

        策略：
        1. 按 score 降序排序
        2. 累加估算 Token 数，超过预算时停止
        3. 对超长记忆进行截断

        Args:
            memories: 记忆列表。
            max_tokens: 记忆预算最大 Token 数。

        Returns:
            预算内的记忆内容列表。
        """
        if not memories:
            return []

        # 按 score 降序排序
        sorted_memories = sorted(
            memories, key=lambda x: x.get("score", 0.0), reverse=True
        )

        selected: list[str] = []
        current_tokens = 0
        token_per_char = 0.7  # 经验值：1 字符 ≈ 0.7 Token

        for mem in sorted_memories:
            content = mem.get("content", "")
            estimated_tokens = len(content) * token_per_char

            if current_tokens + estimated_tokens > max_tokens:
                # 截断超长记忆
                remaining = max_tokens - current_tokens
                max_chars = int(remaining / token_per_char)
                if max_chars > 20:
                    truncated = content[:max_chars] + "..."
                    selected.append(truncated)
                break

            selected.append(content)
            current_tokens += estimated_tokens

        return selected

    def summarize_memories(
        self,
        memories: list[dict],
        max_summary_tokens: int = 500,
    ) -> str:
        """生成记忆摘要（可选：使用 LLM 总结）。

        Args:
            memories: 记忆列表。
            max_summary_tokens: 摘要最大 Token 数。

        Returns:
            记忆摘要字符串。
        """
        if not memories:
            return ""

        # 简单摘要：按 score 取前 N 条
        top_memories = sorted(
            memories, key=lambda x: x.get("score", 0.0), reverse=True
        )[:5]

        summary_lines = []
        for mem in top_memories:
            content = mem.get("content", "")
            if content:
                summary_lines.append(f"- {content}")

        return "\n".join(summary_lines)


_prompt_template_service: Optional[PromptTemplateService] = None
_prompt_template_service_lock = threading.Lock()


def get_prompt_template_service() -> PromptTemplateService:
    """获取全局 Prompt 模板服务实例。"""
    global _prompt_template_service
    if _prompt_template_service is None:
        with _prompt_template_service_lock:
            if _prompt_template_service is None:
                _prompt_template_service = PromptTemplateService()
    return _prompt_template_service
