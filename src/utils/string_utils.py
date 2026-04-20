"""字符串处理工具类。

提供文本清洗、截断、模板渲染等通用字符串操作。
"""

from __future__ import annotations

import re
import uuid
from typing import Optional


def generate_id() -> str:
    """生成唯一 ID（基于 UUID4，去除连字符）。"""
    return uuid.uuid4().hex


def truncate(text: str, max_length: int = 200, suffix: str = "...") -> str:
    """截断文本到指定长度。

    Args:
        text: 原始文本。
        max_length: 最大长度。
        suffix: 截断后缀。

    Returns:
        截断后的文本。
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def strip_extra_whitespace(text: str) -> str:
    """去除多余空白字符（多个空格/换行合并为单个空格）。"""
    return re.sub(r"\s+", " ", text).strip()


def extract_chinese(text: str) -> str:
    """提取文本中的中文字符。"""
    return "".join(re.findall(r"[\u4e00-\u9fff]", text))


def is_chinese(text: str) -> bool:
    """判断文本是否主要为中文。"""
    chinese_chars = extract_chinese(text)
    return len(chinese_chars) > len(text) * 0.3 if text else False


def mask_sensitive(text: str, visible_prefix: int = 4, visible_suffix: int = 4) -> str:
    """遮蔽敏感信息（如 API Key）。

    Args:
        text: 原始文本。
        visible_prefix: 前部可见字符数。
        visible_suffix: 后部可见字符数。

    Returns:
        遮蔽后的文本，如 "a3d1****54fa"。
    """
    if len(text) <= visible_prefix + visible_suffix:
        return "****"
    return f"{text[:visible_prefix]}****{text[-visible_suffix:]}"


def render_template(template: str, **kwargs: str) -> str:
    """简单的字符串模板渲染，使用 {key} 占位符。

    Args:
        template: 模板字符串，如 "你好，{name}！我是{agent_name}。"
        **kwargs: 占位符对应的值。

    Returns:
        渲染后的字符串。
    """
    return template.format_map(kwargs)


def count_words(text: str) -> int:
    """估算文本词数（中文按字符计，英文按空格分词计）。"""
    chinese_chars = extract_chinese(text)
    chinese_count = len(chinese_chars)
    remaining = re.sub(r"[\u4e00-\u9fff]", " ", text)
    english_words = [w for w in remaining.split() if w.strip()]
    return chinese_count + len(english_words)


def safe_slice(text: str, start: int = 0, end: Optional[int] = None) -> str:
    """安全的字符串切片，不会在多字节字符中间截断。"""
    if end is None:
        return text[start:]
    return text[start:end]
