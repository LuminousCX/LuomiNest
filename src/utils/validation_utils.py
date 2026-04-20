"""数据校验工具类。

提供通用的参数校验、类型检查、范围检查等功能。
"""

from __future__ import annotations

import re
from typing import Any, Optional, Sequence

from src.exceptions import ParamError


def validate_not_empty(value: Any, field_name: str = "参数") -> None:
    """校验值非空。

    Args:
        value: 待校验的值。
        field_name: 字段名称，用于错误提示。

    Raises:
        ParamError: 值为空时抛出。
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ParamError(message=f"{field_name}不能为空")


def validate_length(
    value: str,
    min_length: int = 0,
    max_length: int = 5000,
    field_name: str = "参数",
) -> None:
    """校验字符串长度范围。

    Args:
        value: 待校验的字符串。
        min_length: 最小长度。
        max_length: 最大长度。
        field_name: 字段名称。

    Raises:
        ParamError: 长度不在范围内时抛出。
    """
    length = len(value)
    if length < min_length or length > max_length:
        raise ParamError(
            message=f"{field_name}长度必须在 {min_length}~{max_length} 之间，当前: {length}",
        )


def validate_in_options(
    value: Any,
    options: Sequence[Any],
    field_name: str = "参数",
) -> None:
    """校验值在可选范围内。

    Args:
        value: 待校验的值。
        options: 可选值列表。
        field_name: 字段名称。

    Raises:
        ParamError: 值不在可选范围内时抛出。
    """
    if value not in options:
        raise ParamError(
            message=f"{field_name}的值必须在 {list(options)} 中，当前: {value}",
        )


def validate_positive_int(value: Any, field_name: str = "参数") -> None:
    """校验值为正整数。

    Args:
        value: 待校验的值。
        field_name: 字段名称。

    Raises:
        ParamError: 值不是正整数时抛出。
    """
    if not isinstance(value, int) or value <= 0:
        raise ParamError(message=f"{field_name}必须为正整数，当前: {value}")


def validate_agent_id(agent_id: Any) -> None:
    """校验 Agent ID 格式。"""
    validate_not_empty(agent_id, "Agent ID")
    if not isinstance(agent_id, int):
        raise ParamError(message="Agent ID 必须为整数类型")


def validate_agent_name(name: Any) -> None:
    """校验 Agent 名称。"""
    validate_not_empty(name, "Agent 名称")
    if not isinstance(name, str):
        raise ParamError(message="Agent 名称必须为字符串类型")
    validate_length(name, min_length=1, max_length=50, field_name="Agent 名称")


def validate_prompt_template(template: Any) -> None:
    """校验 prompt 模板。"""
    validate_not_empty(template, "Prompt 模板")
    if not isinstance(template, str):
        raise ParamError(message="Prompt 模板必须为字符串类型")
    validate_length(template, min_length=1, max_length=10000, field_name="Prompt 模板")


def is_valid_uuid(value: str) -> bool:
    """判断字符串是否为有效的 UUID 格式。"""
    pattern = r"^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$"
    return bool(re.match(pattern, value, re.IGNORECASE))
