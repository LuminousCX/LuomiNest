"""Prompt 模板工具类。

负责加载 Jinja2 模板并渲染 System Prompt。
解决原有逻辑问题：
- 不在代码中写死三引号 prompt
- 不由前端传递完整文案
- 后端根据 agent_id 或 agent_name 自动渲染
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, Template, TemplateNotFound, select_autoescape

from src.utils.logger import get_logger

logger = get_logger()

_TEMPLATE_BASE_DIR = Path(__file__).resolve().parent.parent / "templates" / "prompts"
_DEFAULT_TEMPLATE_NAME = "default.j2"


class PromptUtil:
    """Prompt 模板工具类。

    提供模板加载、缓存和渲染功能。
    模板查找顺序：
    1. agent_{id}.j2（按 Agent ID）
    2. agent_{name}.j2（按 Agent 名称）
    3. default.j2（默认模板）

    Attributes:
        env: Jinja2 环境实例。
        template_dir: 模板目录。
        _template_cache: 模板缓存。
    """

    def __init__(self, template_dir: Optional[Path] = None) -> None:
        """初始化 Prompt 工具类。

        Args:
            template_dir: 模板目录路径，默认为 templates/prompts/。
        """
        self.template_dir = template_dir or _TEMPLATE_BASE_DIR
        self.template_dir.mkdir(parents=True, exist_ok=True)

        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(default=False),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )
        self._template_cache: dict[str, Template] = {}

        logger.info(f"PromptUtil 初始化完成，模板目录: {self.template_dir}")

    def render(
        self,
        template_name: str,
        context: dict[str, Any],
    ) -> str:
        """渲染指定模板。

        Args:
            template_name: 模板文件名（不含路径）。
            context: 模板上下文变量。

        Returns:
            渲染后的字符串。
        """
        template = self._get_template(template_name)
        rendered = template.render(**context)
        return rendered.strip()

    def render_agent_prompt(
        self,
        agent_id: Optional[int] = None,
        agent_name: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> str:
        """渲染 Agent 专属模板。

        查找顺序：
        1. agent_{id}.j2
        2. agent_{name}.j2
        3. default.j2

        Args:
            agent_id: Agent ID。
            agent_name: Agent 名称。
            context: 模板上下文变量。

        Returns:
            渲染后的 System Prompt。
        """
        context = context or {}

        template_candidates = []
        if agent_id is not None:
            template_candidates.append(f"agent_{agent_id}.j2")
        if agent_name:
            template_candidates.append(f"agent_{agent_name}.j2")

        for template_name in template_candidates:
            try:
                return self.render(template_name, context)
            except TemplateNotFound:
                logger.debug(f"模板 {template_name} 不存在，尝试下一个")
                continue

        logger.debug("使用默认模板 default.j2")
        return self.render(_DEFAULT_TEMPLATE_NAME, context)

    def render_with_fallback(
        self,
        template_name: str,
        context: dict[str, Any],
        fallback_template: str = _DEFAULT_TEMPLATE_NAME,
    ) -> str:
        """渲染模板，失败时使用后备模板。

        Args:
            template_name: 主模板文件名。
            context: 模板上下文变量。
            fallback_template: 后备模板文件名。

        Returns:
            渲染后的字符串。
        """
        try:
            return self.render(template_name, context)
        except TemplateNotFound:
            logger.warning(f"模板 {template_name} 不存在，使用后备模板 {fallback_template}")
            return self.render(fallback_template, context)

    def _get_template(self, template_name: str) -> Template:
        """获取模板实例（带缓存）。

        Args:
            template_name: 模板文件名。

        Returns:
            Jinja2 Template 实例。

        Raises:
            TemplateNotFound: 模板文件不存在时抛出。
        """
        if template_name not in self._template_cache:
            self._template_cache[template_name] = self.env.get_template(template_name)
        return self._template_cache[template_name]

    def template_exists(self, template_name: str) -> bool:
        """检查模板文件是否存在。

        Args:
            template_name: 模板文件名。

        Returns:
            是否存在。
        """
        template_path = self.template_dir / template_name
        return template_path.exists()

    def create_template(self, template_name: str, content: str) -> Path:
        """创建新的模板文件。

        Args:
            template_name: 模板文件名。
            content: 模板内容。

        Returns:
            模板文件路径。
        """
        template_path = self.template_dir / template_name
        template_path.write_text(content, encoding="utf-8")

        if template_name in self._template_cache:
            del self._template_cache[template_name]

        logger.info(f"创建模板文件: {template_path}")
        return template_path

    def list_templates(self) -> list[str]:
        """列出所有模板文件。

        Returns:
            模板文件名列表。
        """
        templates = list(self.env.list_templates())
        return [t for t in templates if t.endswith(".j2")]


_prompt_util: Optional[PromptUtil] = None


def get_prompt_util() -> PromptUtil:
    """获取全局 PromptUtil 实例。"""
    global _prompt_util
    if _prompt_util is None:
        _prompt_util = PromptUtil()
    return _prompt_util


def render_system_prompt(
    agent_id: Optional[int] = None,
    agent_name: Optional[str] = None,
    name: str = "",
    title: str = "",
    background: str = "",
    personality: str = "",
    speaking_style: str = "",
    extra_context: Optional[dict[str, Any]] = None,
) -> str:
    """渲染 Agent 的 System Prompt。

    便捷函数，封装常用渲染逻辑。

    Args:
        agent_id: Agent ID。
        agent_name: Agent 名称。
        name: 人格名称。
        title: 一句话介绍。
        background: 经历背景。
        personality: 性格特点。
        speaking_style: 说话风格。
        extra_context: 额外的模板上下文。

    Returns:
        渲染后的 System Prompt。
    """
    context = {
        "name": name,
        "title": title,
        "background": background,
        "personality": personality,
        "speaking_style": speaking_style,
    }

    if extra_context:
        context.update(extra_context)

    return get_prompt_util().render_agent_prompt(
        agent_id=agent_id,
        agent_name=agent_name,
        context=context,
    )
