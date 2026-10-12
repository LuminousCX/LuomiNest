"""LuomiNest avatar-voice binding configuration and emotion stream parser.

Mirrors frontend config to keep backend and frontend in sync.
Bindings map model_id -> voice / expression mapping / language.
The EmotionStreamParser strips <exp:emotion> tags from LLM output
and emits emotion changes for avatar driving.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.constants.voice import DEFAULT_EDGE_VOICE
from app.core.tags.definitions import LUOMINEST_EMOTION_IDS
from app.core.tags.parser import TagStreamParser

# Semantic emotion IDs supported across all avatars.
# The LLM is instructed to emit only these IDs inside <exp:...> tags.
# 辰汐生态打通 W2：单一定义源收敛到 app/core/tags/definitions.py
# （LUOMINEST_EMOTION_IDS），此处保持别名导出以维持既有引用不变。
SUPPORTED_EMOTION_IDS: tuple[str, ...] = LUOMINEST_EMOTION_IDS

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
        voice=DEFAULT_EDGE_VOICE,
        voice_lang="zh",
        expression_map=_LLNy_EXPRESSION_MAP,
        default_expression="- -",
    ),
    "hiyori": AvatarBinding(
        model_id="hiyori",
        voice=DEFAULT_EDGE_VOICE,
        voice_lang="zh",
        expression_map=dict(_DEFAULT_EXPRESSION_MAP),
        default_expression="neutral",
    ),
    "shizuku": AvatarBinding(
        model_id="shizuku",
        voice=DEFAULT_EDGE_VOICE,
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
    """Remove all LLM output tags from a complete text (non-streaming use).

    辰汐生态打通 W2（分册 08 §15.3）：剥离范围从 exp 单族扩展到五族标签
    （exp/act/ui/tool/dispatch，含自闭合与非自闭合形态），委托统一标签网关
    app/core/tags 实现；对既有调用方（chat_service / group_chat）而言
    「剥净标签返回干净文本」的对外行为不变，只是剥得更净。
    """
    from app.core.tags import strip_all_tags

    return strip_all_tags(text or "")


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
class EmotionStreamParser(TagStreamParser):
    """Stateful streaming parser for <exp:emotion> tags.

    辰汐生态打通 W2（分册 08 §15.3）：exp 解析逻辑并入统一标签网关
    app/core/tags.TagStreamParser，本类改为委托（继承），对外行为不变——
    feed() 仍返回 (clean_content, emotion_or_none)，emotion 仅在变化时发射，
    闭合标签回归 neutral。清洗范围随网关扩展到五族标签（平台/群聊文字渠道
    收益：act/ui/tool/dispatch 幻觉标签同样被剥净，皮套工具事件在非快脑链路
    一律不发射，仅计数留痕）。

    支持的标签格式（严格 + 宽松双正则，见 app/core/tags/definitions.py）：
    - <exp:NAME> / <exp=NAME> / <exp:NAME/>   标准与自闭合
    - < exp:NAME > / <exp: NAME />            含空格变体
    - <exp:smile/>                            合同 8 词自闭合（经翻译映射）
    """

    def __init__(self) -> None:
        # 平台/群聊文字渠道：皮套工具不启用（分册 08 §15.2 优先级条款 3，
        # 皮套工具仅快脑可挂），工具标签只剥离 + 计数
        super().__init__(avatar_tools_enabled=False)

    def feed(self, chunk: str) -> tuple[str, str | None]:
        clean_content, events = super().feed(chunk)
        # 与原实现语义一致：单变量覆盖，同 chunk 多次情绪切换时取最后一次
        emotion = None
        for event in events:
            if event.kind == "emotion":
                emotion = event.value
        return (clean_content, emotion)
