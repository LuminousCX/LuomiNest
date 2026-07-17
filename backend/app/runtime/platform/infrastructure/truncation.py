"""消息长度安全截断。

提供 UTF-16 感知的安全截断能力，适配 Telegram 等
按 UTF-16 编码计算消息长度的平台。
"""

from __future__ import annotations

from enum import Enum, auto


class TruncateMode(Enum):
    """截断模式枚举。"""

    CHARS = auto()   # 按字符数截断
    BYTES = auto()   # 按字节数截断
    UTF16 = auto()   # 按 UTF-16 编码单元数截断（Telegram 等平台使用）


class MessageTruncator:
    """消息长度安全截断器。

    支持按字符数、字节数、UTF-16 编码单元数三种模式截断，
    确保不会在 surrogate pair 中间截断导致乱码。

    使用示例：

    .. code-block:: python

        truncator = MessageTruncator()

        # 按 UTF-16 截断（Telegram 限制 4096）
        safe_text = truncator.truncate(long_text, max_length=4096, mode=TruncateMode.UTF16)

        # 按字符数截断
        short_text = truncator.truncate(text, max_length=200, mode=TruncateMode.CHARS)
    """

    def __init__(self, default_suffix: str = "...") -> None:
        """初始化截断器。

        Args:
            default_suffix: 截断后追加的后缀，默认为 "..."。
        """
        self.default_suffix = default_suffix

    def truncate(
        self,
        text: str,
        max_length: int,
        encoding: str = "utf-16",
        suffix: str | None = None,
        mode: TruncateMode | None = None,
    ) -> str:
        """安全截断文本到指定长度。

        Args:
            text: 原始文本。
            max_length: 最大长度限制。
            encoding: 编码名称，用于 BYTES 模式，默认 'utf-16'。
            suffix: 截断后缀，为 None 时使用默认后缀。
            mode: 截断模式，为 None 时根据 encoding 自动推断。

        Returns:
            截断后的文本（如果未超限则原样返回）。
        """
        if not text or max_length <= 0:
            return text

        # 推断截断模式
        if mode is None:
            if encoding.lower().replace("-", "") == "utf16":
                mode = TruncateMode.UTF16
            else:
                mode = TruncateMode.BYTES

        suffix = suffix if suffix is not None else self.default_suffix
        suffix_len = self._measure(suffix, encoding, mode)

        # 检查是否超限
        text_len = self._measure(text, encoding, mode)
        if text_len <= max_length:
            return text

        # 需要截断
        effective_max = max_length - suffix_len
        if effective_max <= 0:
            # 连后缀都放不下，直接截断到 max_length
            return self._safe_cut(text, max_length, encoding, mode)

        truncated = self._safe_cut(text, effective_max, encoding, mode)
        return truncated + suffix

    def _measure(self, text: str, encoding: str, mode: TruncateMode) -> int:
        """测量文本在指定模式下的长度。"""
        match mode:
            case TruncateMode.CHARS:
                return len(text)
            case TruncateMode.BYTES:
                return len(text.encode(encoding, errors="surrogatepass"))
            case TruncateMode.UTF16:
                return self._utf16_length(text)
        return len(text)

    def _utf16_length(self, text: str) -> int:
        """计算文本的 UTF-16 编码单元数。

        Python 内部使用 UTF-16 或 UTF-32 存储字符串，
        这里手动计算以确保与平台（如 Telegram）一致。
        """
        length = 0
        for char in text:
            code_point = ord(char)
            if code_point > 0xFFFF:
                # 需要 surrogate pair，占 2 个 UTF-16 单元
                length += 2
            else:
                length += 1
        return length

    def _safe_cut(
        self,
        text: str,
        max_length: int,
        encoding: str,
        mode: TruncateMode,
    ) -> str:
        """安全截断文本，避免在 surrogate pair 中间截断。"""
        match mode:
            case TruncateMode.CHARS:
                return text[:max_length]
            case TruncateMode.BYTES:
                return self._cut_by_bytes(text, max_length, encoding)
            case TruncateMode.UTF16:
                return self._cut_by_utf16(text, max_length)
        return text[:max_length]

    def _cut_by_bytes(self, text: str, max_bytes: int, encoding: str) -> str:
        """按字节数安全截断。"""
        encoded = text.encode(encoding, errors="surrogatepass")
        if len(encoded) <= max_bytes:
            return text

        # 二分查找合适的截断位置
        cut = encoded[:max_bytes]
        try:
            return cut.decode(encoding, errors="ignore")
        except (UnicodeDecodeError, LookupError):
            # 回退到逐字符截断
            return self._cut_by_chars_fallback(text, max_bytes, encoding)

    def _cut_by_chars_fallback(
        self, text: str, max_bytes: int, encoding: str
    ) -> str:
        """逐字符截断的兜底方案。"""
        result = ""
        for char in text:
            test = result + char
            if len(test.encode(encoding, errors="surrogatepass")) > max_bytes:
                break
            result = test
        return result

    def _cut_by_utf16(self, text: str, max_units: int) -> str:
        """按 UTF-16 编码单元数安全截断。"""
        result = []
        units = 0
        for char in text:
            code_point = ord(char)
            char_units = 2 if code_point > 0xFFFF else 1
            if units + char_units > max_units:
                break
            result.append(char)
            units += char_units
        return "".join(result)


# 模块级便捷函数
def truncate(
    text: str,
    max_length: int,
    encoding: str = "utf-16",
    suffix: str = "...",
) -> str:
    """便捷截断函数（使用默认配置）。

    Args:
        text: 原始文本。
        max_length: 最大长度限制（UTF-16 编码单元数）。
        encoding: 编码名称，默认 'utf-16'。
        suffix: 截断后缀，默认 "..."。

    Returns:
        截断后的文本。
    """
    truncator = MessageTruncator(default_suffix=suffix)
    return truncator.truncate(text, max_length, encoding=encoding)
