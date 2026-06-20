"""LuomiNest avatar-voice binding configuration and emotion stream parser.

Mirrors frontend config to keep backend and frontend in sync.
Bindings map model_id -> voice / expression mapping / language.
The EmotionStreamParser strips <exp:emotion> tags from LLM output
and emits emotion changes for avatar driving.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# Semantic emotion IDs supported across all avatars.
# The LLM is instructed to emit only these IDs inside <exp:...> tags.
SUPPORTED_EMOTION_IDS: tuple[str, ...] = (
    "happy", "sad", "neutral", "love", "surprise",
    "angry", "think", "awkward", "curious", "shy", "excited", "confused",
)

# Matches a complete <exp:emotion> tag. Used for final cleanup of
# non-streamed content and for sanity checks.
_EMOTION_TAG_RE = re.compile(r"<exp:([a-zA-Z]+)>")

# Loose pattern for defensive cleanup: matches <exp:NAME>, < exp:NAME >,
# <exp: NAME />, and other whitespace/self-closing variants that LLMs
# sometimes emit despite the prompt. Used as a safety net in _sse().
_EMOTION_TAG_LOOSE_RE = re.compile(r"<\s*exp:\s*[a-zA-Z]+\s*/?\s*>")


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
        voice="ja-JP-NanamiNeural",
        voice_lang="ja",
        expression_map=_LLNy_EXPRESSION_MAP,
        default_expression="- -",
    ),
    "hiyori": AvatarBinding(
        model_id="hiyori",
        voice="ja-JP-NanamiNeural",
        voice_lang="ja",
        expression_map=dict(_DEFAULT_EXPRESSION_MAP),
        default_expression="neutral",
    ),
    "shizuku": AvatarBinding(
        model_id="shizuku",
        voice="ja-JP-NanamiNeural",
        voice_lang="ja",
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


@dataclass
class EmotionStreamParser:
    """Stateful streaming parser for <exp:emotion> tags.

    Feed each LLM chunk via feed(). Returns (clean_content, emotion_or_none).
    emotion is emitted only when it changes from the previous value.
    Handles partial tags split across chunk boundaries.
    """

    _current_emotion: str | None = field(default=None, init=False)
    _pending: str = field(default="", init=False)

    def feed(self, chunk: str) -> tuple[str, str | None]:
        if not chunk:
            return ("", None)

        # Prepend any pending partial-tag text from the previous chunk.
        buf = self._pending + chunk
        self._pending = ""

        clean_parts: list[str] = []
        emitted_emotion: str | None = None
        i = 0
        n = len(buf)

        while i < n:
            lt = buf.find("<exp:", i)
            if lt == -1:
                # No more tag openings; flush the rest as clean content.
                clean_parts.append(buf[i:])
                break

            # Flush clean text before the tag opening.
            if lt > i:
                clean_parts.append(buf[i:lt])

            gt = buf.find(">", lt)
            if gt == -1:
                # Tag opening without a closing '>' in this chunk.
                # Hold the partial tag for the next chunk.
                self._pending = buf[lt:]
                break

            # Complete tag found: <exp:NAME>
            tag_body = buf[lt + 5:gt]  # skip '<exp:' and stop before '>'
            i = gt + 1

            if tag_body and is_supported_emotion(tag_body):
                if tag_body != self._current_emotion:
                    self._current_emotion = tag_body
                    emitted_emotion = tag_body
            # Unsupported emotion IDs are silently stripped (no emission).

        clean_content = "".join(clean_parts)
        return (clean_content, emitted_emotion)

    @property
    def current_emotion(self) -> str | None:
        return self._current_emotion

    def reset(self) -> None:
        self._current_emotion = None
        self._pending = ""
