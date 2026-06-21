"""LuomiNest avatar-voice binding configuration and emotion stream parser.

Mirrors frontend config to keep backend and frontend in sync.
Bindings map model_id -> voice / expression mapping / language.
The EmotionStreamParser strips <exp:emotion> tags from LLM output
and emits emotion changes for avatar driving.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from loguru import logger


# Semantic emotion IDs supported across all avatars.
# The LLM is instructed to emit only these IDs inside <exp:...> tags.
SUPPORTED_EMOTION_IDS: tuple[str, ...] = (
    "happy", "sad", "neutral", "love", "surprise",
    "angry", "think", "awkward", "curious", "shy", "excited", "confused",
)

# Matches a complete <exp:emotion> or <exp=emotion> tag. Used for final cleanup of
# non-streamed content and for sanity checks. Supports both ':' and '=' separators
# because LLMs sometimes emit <exp=NAME> instead of <exp:NAME>.
_EMOTION_TAG_RE = re.compile(r"<exp[:=]([a-zA-Z]+)>")

# Loose pattern for defensive cleanup: matches <exp:NAME>, <exp=NAME>, < exp:NAME >,
# <exp: NAME />, and other whitespace/self-closing variants that LLMs
# sometimes emit despite the prompt. Used as a safety net in _sse().
_EMOTION_TAG_LOOSE_RE = re.compile(r"<\s*exp[:=]\s*[a-zA-Z]+\s*/?\s*>")


@dataclass
class AvatarBinding:
    model_id: str
    voice: str
    voice_lang: str  # 'zh' | 'ja' | 'en'
    expression_map: dict[str, str] = field(default_factory=dict)
    default_expression: str = "neutral"


# Llny uses Chinese expression names defined in its model3.json.
_LLNy_EXPRESSION_MAP: dict[str, str] = {
    "happy": "星星",
    "sad": "哭",
    "neutral": "- -",
    "love": "脸红",
    "surprise": "阿尼亚",
    "angry": "生气",
    "think": "眼镜",
    "awkward": "脸黑",
    "curious": "吐舌",
    "shy": "脸红",
    "excited": "比心",
    "confused": "荷包蛋",
}

_DEFAULT_EXPRESSION_MAP: dict[str, str] = {
    emo: emo for emo in SUPPORTED_EMOTION_IDS
}


LUOMINEST_AVATAR_BINDINGS: dict[str, AvatarBinding] = {
    "llny": AvatarBinding(
        model_id="llny",
        voice="zh-CN-XiaoxiaoNeural",
        voice_lang="zh",
        expression_map=_LLNy_EXPRESSION_MAP,
        default_expression="- -",
    ),
    "hiyori": AvatarBinding(
        model_id="hiyori",
        voice="zh-CN-XiaoxiaoNeural",
        voice_lang="zh",
        expression_map=dict(_DEFAULT_EXPRESSION_MAP),
        default_expression="neutral",
    ),
    "shizuku": AvatarBinding(
        model_id="shizuku",
        voice="zh-CN-XiaoxiaoNeural",
        voice_lang="zh",
        expression_map=dict(_DEFAULT_EXPRESSION_MAP),
        default_expression="neutral",
    ),
}


def get_avatar_binding(model_id: str | None) -> AvatarBinding | None:
    if not model_id:
        return None
    return LUOMINEST_AVATAR_BINDINGS.get(model_id)


def resolve_expression(model_id: str | None, emotion_id: str) -> str:
    binding = get_avatar_binding(model_id)
    if not binding:
        return emotion_id
    return binding.expression_map.get(emotion_id, binding.default_expression)


def is_supported_emotion(emotion_id: str) -> bool:
    return emotion_id in SUPPORTED_EMOTION_IDS


def strip_emotion_tags(text: str) -> str:
    """Remove all <exp:...> tags from a complete text (non-streaming use)."""
    return _EMOTION_TAG_LOOSE_RE.sub("", _EMOTION_TAG_RE.sub("", text))


# 完整标签的宽松正则：同时匹配开始标签 <exp:NAME> 和闭合标签 </exp:NAME>
# 支持：前导空格 < exp:NAME>、内部空格 <exp: NAME />、自闭合 <exp:NAME/> <exp:NAME />
# group(1): '<' 或 '</'（用于区分开始/闭合标签）
# group(2): emotion ID
# 与前端 emotionTagInterceptor.ts 的 EMOTION_TAG_LOOSE_RE 保持一致
_EMOTION_TAG_FULL_RE = re.compile(r"(</?)\s*exp[:=]\s*([a-zA-Z]+)\s*/?\s*>")

# 部分标签前缀正则：用于判断 '<' 后续是否可能是 emotion 标签（开始或闭合）的开头
# 关键：必须匹配单个 '<' 和 '</'，因为 LLM 流式输出可能把标签拆成单字符 chunk
# 匹配：<、</、<e、</e、<ex、</ex、<exp、</exp、<exp:、</exp:、<exp:happy、</exp:happy 等
# 不匹配：<a、<1、<空格+a（避免误判 HTML 标签和数学公式）
_EMOTION_TAG_PARTIAL_RE = re.compile(r"</?(?:\s*e(?:x(?:p(?:(?::|=)(?:\s*[a-zA-Z]*)?)?)?)?)?$")


@dataclass
class EmotionStreamParser:
    """Stateful streaming parser for <exp:emotion> tags.

    Feed each LLM chunk via feed(). Returns (clean_content, emotion_or_none).
    emotion is emitted only when it changes from the previous value.
    Handles partial tags split across chunk boundaries.

    支持的标签格式（与 _EMOTION_TAG_LOOSE_RE 一致）：
    - <exp:NAME> / <exp=NAME>          标准格式
    - < exp:NAME > / <exp: NAME />     含空格变体
    - <exp:NAME/> / <exp:NAME />       自闭合变体
    """

    _current_emotion: str | None = field(default=None, init=False)
    _pending: str = field(default="", init=False)

    def feed(self, chunk: str) -> tuple[str, str | None]:
        if not chunk:
            return ("", None)

        # 合并上一个 chunk 保留的部分标签
        buf = self._pending + chunk
        self._pending = ""

        clean_parts: list[str] = []
        emitted_emotion: str | None = None
        i = 0

        while i < len(buf):
            lt = buf.find("<", i)
            if lt == -1:
                # 没有更多 '<'，刷新剩余内容为干净文本
                clean_parts.append(buf[i:])
                break

            # 刷新 '<' 之前的干净文本
            if lt > i:
                clean_parts.append(buf[i:lt])

            # 尝试从 lt 开始匹配完整的 emotion 标签
            match = _EMOTION_TAG_FULL_RE.match(buf, lt)
            if match:
                tag_prefix = match.group(1)  # '<' 或 '</'
                emotion_id = match.group(2)
                is_closing = tag_prefix == "</"
                if is_closing:
                    # 闭合标签 </exp:NAME>：发射 neutral 回归正常状态
                    # 这样前端可以在播放完标签内的语句后，通过 TTS 段同步切换回 neutral
                    if self._current_emotion is not None and self._current_emotion != "neutral":
                        self._current_emotion = "neutral"
                        emitted_emotion = "neutral"
                        logger.debug(f"[EmotionParser] 闭合标签回归 neutral: {match.group(0)!r}")
                    else:
                        logger.debug(f"[EmotionParser] 闭合标签剥离(无需回归): {match.group(0)!r}")
                elif is_supported_emotion(emotion_id):
                    if emotion_id != self._current_emotion:
                        self._current_emotion = emotion_id
                        emitted_emotion = emotion_id
                        logger.debug(f"[EmotionParser] 表情切换: {emotion_id} (原始标签: {match.group(0)!r})")
                    else:
                        logger.debug(f"[EmotionParser] 表情未变化(仍为 {emotion_id})，不发射")
                else:
                    logger.warning(f"[EmotionParser] 不支持的 emotion ID: {emotion_id!r} (原始标签: {match.group(0)!r})")
                # 不支持的 emotion ID 静默剥离（不发射）
                i = match.end()
            else:
                # 检查是否是部分标签（可能跨 chunk 完成）
                partial = buf[lt:]
                if _EMOTION_TAG_PARTIAL_RE.match(partial):
                    # 保留部分标签到下一个 chunk
                    logger.debug(f"[EmotionParser] 保留部分标签到下一 chunk: {partial!r}")
                    self._pending = partial
                    break
                else:
                    # 不是 emotion 标签，把 '<' 当作普通字符输出
                    clean_parts.append("<")
                    i = lt + 1

        clean_content = "".join(clean_parts)
        logger.debug(
            f"[EmotionParser] feed(chunk={chunk!r}) => "
            f"clean={clean_content!r}, emotion={emitted_emotion!r}, "
            f"current_emotion={self._current_emotion!r}, pending={self._pending!r}"
        )
        return (clean_content, emitted_emotion)

    @property
    def current_emotion(self) -> str | None:
        return self._current_emotion

    def reset(self) -> None:
        self._current_emotion = None
        self._pending = ""
