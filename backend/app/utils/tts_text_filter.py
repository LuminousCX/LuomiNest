"""TTS 文本过滤器 - 在合成语音前清理文本中的 markdown/emoji/特殊符号.

前端已做完整过滤，此模块作为后端兜底，防止非前端调用或前端遗漏.
参考: super-agent-party 的 clean_markdown 实现.
"""

import re
from loguru import logger

# 表情标签 <exp:NAME> / <exp=NAME> 及各种变体（空格、自闭合等）→ 删除
# 与 avatar_manager.py 的 _EMOTION_TAG_LOOSE_RE 保持一致
_EMOTION_TAG_RE = re.compile(r"<\s*exp[:=]\s*[a-zA-Z]+\s*/?\s*>")

# 标题标记
_HEADING_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)

# 列表标记
_UNORDERED_LIST_RE = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)
_ORDERED_LIST_RE = re.compile(r"^\s*\d+\.\s+", re.MULTILINE)

# 引用
_BLOCKQUOTE_RE = re.compile(r"^\s*>\s*", re.MULTILINE)

# 水平分割线
_HR_RE = re.compile(r"^\s*([-*_])\1{2,}\s*$", re.MULTILINE)

# 表格
_TABLE_SEP_RE = re.compile(r"^\s*\|[\s:|-]*-{3,}[\s:|-]*\|?\s*$", re.MULTILINE)
_TABLE_PIPE_RE = re.compile(r"\|")

# 图片
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")

# 链接 → 保留文字
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")

# 行内代码 → 保留内容
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")

# 粗体 → 保留文字
_BOLD_ASTERISK_RE = re.compile(r"\*\*([^*]+)\*\*")
_BOLD_UNDERSCORE_RE = re.compile(r"__([^_]+)__")

# 斜体 → 保留文字
_ITALIC_ASTERISK_RE = re.compile(r"\*([^*]+)\*")
_ITALIC_UNDERSCORE_RE = re.compile(r"_([^_]+)_")

# 删除线 → 保留文字
_STRIKE_RE = re.compile(r"~~([^~]+)~~")

# emoji 及特殊符号（覆盖 Emoji 1.0-15.0 + 符号 + 箭头）
_EMOJI_RE = re.compile(
    r"[\U0001F000-\U0001FAFF\u2600-\u27BF\u2190-\u21FF\u2B00-\u2BFF"
    r"\uFE0F\u200D\u2300-\u23FF\u25A0-\u25FF]",
    flags=re.UNICODE,
)

# 多余空白
_MULTI_SPACE_RE = re.compile(r"[ \t]+")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


def filter_tts_text(text: str) -> str:
    """清理 TTS 文本，移除 markdown 语法、emoji 和特殊符号.

    Args:
        text: 原始文本（可能包含 markdown/emoji）

    Returns:
        清理后的纯文本，适合 TTS 朗读
    """
    if not text:
        return ""

    # 表情标签 <exp:xxx> → 删除（必须在最前面，防止标签被朗读）
    text = _EMOTION_TAG_RE.sub("", text)

    # 行内代码 → 保留内容
    text = _INLINE_CODE_RE.sub(r"\1", text)

    # 图片 → 删除
    text = _IMAGE_RE.sub("", text)

    # 链接 → 保留文字
    text = _LINK_RE.sub(r"\1", text)

    # 标题/列表/引用/分割线/表格
    text = _HEADING_RE.sub("", text)
    text = _UNORDERED_LIST_RE.sub("", text)
    text = _ORDERED_LIST_RE.sub("", text)
    text = _BLOCKQUOTE_RE.sub("", text)
    text = _HR_RE.sub("", text)
    text = _TABLE_SEP_RE.sub("", text)
    text = _TABLE_PIPE_RE.sub(" ", text)

    # 粗体/斜体/删除线 → 保留文字
    text = _BOLD_ASTERISK_RE.sub(r"\1", text)
    text = _BOLD_UNDERSCORE_RE.sub(r"\1", text)
    text = _ITALIC_ASTERISK_RE.sub(r"\1", text)
    text = _ITALIC_UNDERSCORE_RE.sub(r"\1", text)
    text = _STRIKE_RE.sub(r"\1", text)

    # emoji → 删除
    text = _EMOJI_RE.sub("", text)

    # 空白合并
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)

    return text.strip()
