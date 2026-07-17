"""日志敏感信息脱敏。

对日志文本中的 Token、手机号、邮箱、API Key、密码等敏感信息
进行正则替换脱敏，防止敏感数据泄露到日志系统。
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass

from loguru import logger


@dataclass
class SanitizeRule:
    """单条脱敏规则。

    Attributes:
        name: 规则名称，用于日志标识。
        pattern: 正则表达式（编译后的 Pattern）。
        replacement: 替换文本，支持正则反向引用。
    """

    name: str
    pattern: re.Pattern[str]
    replacement: str = "***"


# 内置规则定义（name, regex, replacement）
_BUILTIN_RULES: list[tuple[str, str, str]] = [
    # Bot Token / 通用 Token（常见格式: 字母数字+点号+字母数字）
    (
        "bot_token",
        r"(?i)(?:bot[_\s-]?token|token)[\s:=]+['\"]?([A-Za-z0-9_\-]{20,})['\"]?",
        r"\g<0>[:=] ***",
    ),
    # 手机号（中国大陆 11 位）
    (
        "phone",
        r"(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)",
        r"\1****\2",
    ),
    # 邮箱地址
    (
        "email",
        r"(?<![A-Za-z0-9._%+-])([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})(?![A-Za-z0-9.-])",
        r"***@***",
    ),
    # API Key（常见格式: sk-xxx, key-xxx, 或长串字母数字）
    (
        "api_key",
        r"(?i)(?:api[_\s-]?key|apikey)[\s:=]+['\"]?([A-Za-z0-9_\-]{16,})['\"]?",
        r"\g<0>[:=] ***",
    ),
    # 密码字段（password=xxx, passwd=xxx 等）
    (
        "password",
        r"(?i)(?:password|passwd|pwd|secret)[\s:=]+['\"]?([^\s'\"]{3,})['\"]?",
        r"\g<0>[:=] ***",
    ),
    # Bearer Token
    (
        "bearer_token",
        r"(?i)Bearer\s+([A-Za-z0-9_\-\.]+)",
        "Bearer ***",
    ),
]


class LogSanitizer:
    """日志敏感信息脱敏器（单例）。

    全局共享一个实例，支持内置规则和自定义规则。
    线程安全。

    使用示例：

    .. code-block:: python

        sanitizer = LogSanitizer.get_instance()
        safe_text = sanitizer.sanitize("token=abc123def456...")
        logger.info(safe_text)
    """

    _instance: LogSanitizer | None = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        """初始化脱敏器，加载内置规则。"""
        self._rules: list[SanitizeRule] = []
        self._load_builtin_rules()

    @classmethod
    def get_instance(cls) -> LogSanitizer:
        """获取全局单例。

        Returns:
            LogSanitizer 全局实例。
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _load_builtin_rules(self) -> None:
        """加载内置脱敏规则。"""
        for name, regex, replacement in _BUILTIN_RULES:
            try:
                self._rules.append(
                    SanitizeRule(
                        name=name,
                        pattern=re.compile(regex),
                        replacement=replacement,
                    )
                )
            except re.error as e:
                logger.warning(f"[Sanitizer] 内置规则 '{name}' 编译失败: {e}")

    def add_rule(
        self,
        name: str,
        pattern: str,
        replacement: str = "***",
    ) -> None:
        """添加自定义脱敏规则。

        Args:
            name: 规则名称。
            pattern: 正则表达式字符串。
            replacement: 替换文本，支持正则反向引用。

        Raises:
            re.error: 正则表达式编译失败。
        """
        compiled = re.compile(pattern)
        self._rules.append(
            SanitizeRule(name=name, pattern=compiled, replacement=replacement)
        )
        logger.debug(f"[Sanitizer] 添加自定义规则: {name}")

    def remove_rule(self, name: str) -> bool:
        """移除指定名称的规则。

        Args:
            name: 规则名称。

        Returns:
            True 表示成功移除，False 表示未找到。
        """
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.name != name]
        removed = before - len(self._rules)
        if removed:
            logger.debug(f"[Sanitizer] 移除规则: {name}")
        return removed > 0

    def sanitize(self, text: str) -> str:
        """对文本执行所有脱敏规则。

        按规则添加顺序依次执行替换。

        Args:
            text: 原始文本。

        Returns:
            脱敏后的文本。
        """
        if not text:
            return text

        result = text
        for rule in self._rules:
            try:
                result = rule.pattern.sub(rule.replacement, result)
            except Exception as e:
                logger.warning(
                    f"[Sanitizer] 规则 '{rule.name}' 执行失败: {e}"
                )
        return result

    @property
    def rules(self) -> list[str]:
        """当前所有规则名称列表。"""
        return [r.name for r in self._rules]


# 模块级便捷函数
def sanitize(text: str) -> str:
    """对文本执行脱敏（使用全局单例）。

    Args:
        text: 原始文本。

    Returns:
        脱敏后的文本。
    """
    return LogSanitizer.get_instance().sanitize(text)
