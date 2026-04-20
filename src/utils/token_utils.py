"""Token 用量计算与管理工具。

提供 token 估算、用量统计、剩余比例计算等功能。
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Optional

from src.utils.logger import get_logger

logger = get_logger()

CHINESE_CHARS_PER_TOKEN = 1.5
ENGLISH_CHARS_PER_TOKEN = 4.0

DEFAULT_TOKEN_BUDGET = 1_000_000


@dataclass
class TokenUsage:
    """Token 用量记录。

    Attributes:
        prompt_tokens: 输入 token 数。
        completion_tokens: 输出 token 数。
        total_tokens: 总 token 数。
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class TokenBudget:
    """Token 预算管理。

    Attributes:
        total_budget: 总预算 token 数。
        used_tokens: 已使用 token 数。
    """

    total_budget: int = DEFAULT_TOKEN_BUDGET
    used_tokens: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    @property
    def remaining_tokens(self) -> int:
        """剩余 token 数。"""
        return max(0, self.total_budget - self.used_tokens)

    @property
    def usage_ratio(self) -> float:
        """已用比例（0.0 ~ 1.0）。"""
        if self.total_budget <= 0:
            return 0.0
        return min(1.0, self.used_tokens / self.total_budget)

    @property
    def remaining_ratio(self) -> float:
        """剩余比例（0.0 ~ 1.0）。"""
        return 1.0 - self.usage_ratio

    def consume(self, token_count: int) -> None:
        """记录 token 消耗。"""
        with self._lock:
            self.used_tokens += token_count
        logger.debug(f"Token 消耗: +{token_count}, 总计: {self.used_tokens}/{self.total_budget}")

    def is_exceeded(self) -> bool:
        """是否超出预算。"""
        return self.used_tokens >= self.total_budget

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "total_budget": self.total_budget,
            "used_tokens": self.used_tokens,
            "remaining_tokens": self.remaining_tokens,
            "usage_ratio": round(self.usage_ratio, 4),
            "remaining_ratio": round(self.remaining_ratio, 4),
        }


def estimate_tokens(text: str) -> int:
    """估算文本的 token 数量。

    简易估算规则：
    - 中文字符约 1.5 字符/token
    - 英文字符约 4 字符/token

    Args:
        text: 待估算的文本。

    Returns:
        估算的 token 数量。
    """
    if not text:
        return 0

    chinese_chars = 0
    non_chinese_chars = 0
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            chinese_chars += 1
        elif ch.isascii() and not ch.isspace():
            non_chinese_chars += 1

    estimated = int(chinese_chars / CHINESE_CHARS_PER_TOKEN + non_chinese_chars / ENGLISH_CHARS_PER_TOKEN)
    return max(1, estimated)


def calculate_conversation_tokens(messages: list[dict[str, str]]) -> int:
    """计算对话消息列表的总 token 估算值。

    Args:
        messages: OpenAI 格式的消息列表，每项包含 role 和 content。

    Returns:
        估算的总 token 数。
    """
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        total += estimate_tokens(content)
        total += 4
    total += 2
    return total


_token_budget: Optional[TokenBudget] = None
_token_budget_lock = threading.Lock()


def get_token_budget() -> TokenBudget:
    """获取全局 Token 预算管理器。"""
    global _token_budget
    if _token_budget is None:
        with _token_budget_lock:
            if _token_budget is None:
                _token_budget = TokenBudget()
    return _token_budget


def reset_token_budget(total_budget: int = DEFAULT_TOKEN_BUDGET) -> TokenBudget:
    """重置 Token 预算管理器。"""
    global _token_budget
    with _token_budget_lock:
        _token_budget = TokenBudget(total_budget=total_budget)
    return _token_budget
