"""工作流模板渲染器 — {{param}} 占位符替换。

按 parameters_schema 声明的参数列表，替换 plan_json 中的 {{param}} 占位符。
支持嵌套替换（plan_json 中任意位置的 {{param}}）。
未匹配的参数保持原样（不报错），方便调试。
"""
import json
import re
from typing import Any

from loguru import logger


def render_plan(plan_json_str: str, params: dict[str, Any]) -> dict[str, Any]:
    """将 plan_json 字符串中的 {{param}} 占位符替换为实际值。

    Args:
        plan_json_str: JSON 序列化的计划字符串（含 {{param}} 占位符）
        params: 参数键值对

    Returns:
        替换后的计划字典

    Raises:
        ValueError: plan_json 解析失败
    """
    # 1. 替换占位符
    def _replace(match):
        param_name = match.group(1).strip()
        if param_name in params:
            value = params[param_name]
            # 如果值是字符串，直接替换；否则 JSON 序列化
            if isinstance(value, str):
                return value
            return json.dumps(value, ensure_ascii=False)
        # 未匹配的参数保持原样
        return match.group(0)

    rendered_str = re.sub(r"\{\{(\s*[\w.]+\s*)\}\}", _replace, plan_json_str)

    # 2. 解析 JSON
    try:
        plan = json.loads(rendered_str)
    except json.JSONDecodeError as e:
        logger.error(f"[TemplateRenderer] JSON 解析失败: {e}")
        raise ValueError(f"渲染后的 plan_json 不是有效 JSON: {e}")

    return plan
