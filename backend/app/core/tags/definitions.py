"""标签网关词表 / 白名单 / 正则 / 约定常量（分册 08 §1.1 / §15，分册 10 §18）。

合同纪律：词表冻结（扩词表 = V5 提案，先改分册再动代码）；命名小写、下划线、
自闭合、半角 ASCII；解析侧对幻觉形态做宽松归一，绝不报错、绝不中断流。
"""
from __future__ import annotations

import re

# 合同 8 冻结词（分册 08 §1.1，唯一训练词表；消费端只译词、不改词）
CONTRACT_EXP_WORDS: tuple[str, ...] = (
    "smile", "angry", "shy", "surprise", "tilt", "sigh", "wronged", "cry",
)

# 内置翻译映射表（分册 08 §15.1 定稿）：合同 8 词 → LuomiNest 语义 12 ID。
# love / excited / think / confused 无合同来源，属消费端自有词位，不做反向映射；
# 在役模型直接输出的 12 语义 ID 走透传（现役非自闭合 <exp:X> 行为不回退）。
BUILTIN_EXP_TRANSLATION: dict[str, str] = {
    "smile": "happy",
    "angry": "angry",
    "shy": "shy",
    "surprise": "surprise",
    "tilt": "curious",
    "sigh": "awkward",
    "wronged": "sad",
    "cry": "sad",
}

# LuomiNest 语义 12 ID（与 avatar_manager.SUPPORTED_EMOTION_IDS 保持一致；
# core 不反向依赖 services，此处独立声明，改动需两侧同步）
LUOMINEST_EMOTION_IDS: tuple[str, ...] = (
    "happy", "sad", "neutral", "love", "surprise",
    "angry", "think", "awkward", "curious", "shy", "excited", "confused",
)

# 映射不到 / 词表外（含幻觉词）一律落 neutral（分册 08 §15.1 兜底硬条款）
DEFAULT_EMOTION_ID: str = "neutral"

# act 词表（分册 08 §15.1：4 动作语义档位；现行合同 = nod/shake/think/hug）
ACT_NAMES: tuple[str, ...] = ("nod", "shake", "think", "hug")

# 皮套工具子词表（分册 08 §15.2：本次启用 2 词）
TOOL_AVATAR_MOTION = "avatar_motion"
TOOL_AVATAR_EXPRESSION = "avatar_expression"

# 工具参数值合法格式：小写字母/数字/下划线，≤32 字符（>32 判非法，静默丢弃）
TOOL_NAME_MAX_LEN = 32

# 派发事件在执行上下文（AgentContext.state）上的挂点字段名。
# W2 解析层捕获 <dispatch task="X"/> 后把 phase="detected" 事件写入
# ctx.state[TASK_DISPATCH_DETECTED_KEY]（list[dict]），**不直接下发前端**；
# W3 派发中间件（middleware/dispatch.py）从该挂点读取并发起 start/done/error 事件。
TASK_DISPATCH_DETECTED_KEY = "task_dispatch_detected"

# ── W3 派发网关辅助状态键（消费端内部约定，非冻结词表）──────────────
# 派发计数留痕（第二关/第三关丢弃与执行计数）：{"detected", "executed",
# "dropped_short", "dropped_no_intent", "dropped_dup", "dropped_limit", "errors"}
TASK_DISPATCH_STATS_KEY = "task_dispatch_stats"
# 已消费的 detected 列表游标（after_model 每轮只处理新增检测，防重复消费）
TASK_DISPATCH_CONSUMED_KEY = "task_dispatch_consumed"
# 本轮已执行的派发数（防环第三关：单轮深度上限计数）
TASK_DISPATCH_DEPTH_KEY = "task_dispatch_depth"
# 本轮任务指纹集合（防环第三关：task 文本判重）
TASK_DISPATCH_FINGERPRINTS_KEY = "task_dispatch_fingerprints"
# 防环兜底硬上限：单次会话轮派发执行深度 ≤10（分册 10 §18.3 第三关）
TASK_DISPATCH_MAX_DEPTH = 10

# 已知标签名（前缀挂起判定用）：exp / act / ui / tool / dispatch 五族
TAG_FAMILY_NAMES: tuple[str, ...] = ("exp", "act", "ui", "tool", "dispatch")

# 标签名之后允许的分隔字符（属性区/自闭合起始）；含中文冒号全角幻觉
_TAG_NAME_SEPARATORS = ":= \t/'\"："

# ── 标签正则（宽松级：大小写归一、: / = 替身、内部空格、自闭合与非自闭合）──
# 说明：合同严格形态（自闭合小写半角）是以下模式的子集；中文冒号等全角幻觉
# 由 parser 的「归一重试」通道处理（只归一候选子串，不动原文）。

# 情绪：<exp:WORD> / <exp=WORD> / 自闭合 / 前导空格变体；group(1) 区分闭合标签
EMOTION_TAG_RE = re.compile(r"(</?)\s*exp\s*[:=]\s*([a-zA-Z]+)\s*/?\s*>", re.IGNORECASE)

# 动作：<act:NAME/>；group(1) 区分闭合标签（闭合静默丢弃）
ACT_TAG_RE = re.compile(r"(</?)\s*act\s*[:=]\s*([a-zA-Z]+)\s*/?\s*>", re.IGNORECASE)

# 导航：<ui:navigate target="X"/>（= 可作冒号替身，引号可省）
NAVIGATE_TAG_RE = re.compile(
    r"<\s*ui\s*:\s*navigate\s+target\s*[:=]\s*\"?([^\s\"'>]+)\"?\s*/?\s*>",
    re.IGNORECASE,
)

# 皮套工具：<tool:avatar_motion|avatar_expression name="X"/>
# name 宽松匹配到 64 字符以便区分「过长非法」与「非本网关标签」；合法值再按 ≤32 校验
TOOL_TAG_RE = re.compile(
    r"<\s*tool\s*:\s*(avatar_motion|avatar_expression)\s+name\s*[:=]\s*\"?([A-Za-z0-9_]{1,64})\"?\s*/?\s*>",
    re.IGNORECASE,
)

# 派发：<dispatch task="X"/>（task 为一句话，引号内可含任意字符；引号可省）
DISPATCH_TAG_RE = re.compile(
    r"<\s*dispatch\s+task\s*[:=]\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s/>]+))\s*/?\s*>",
    re.IGNORECASE,
)

# 五族标签全量宽松匹配（整段文本一次性剥离用，如非流式兜底 / TTS 净化）
ALL_GATEWAY_TAGS_RE = re.compile(
    r"<\s*/?\s*(?:"
    r"exp\s*[:=]\s*[a-zA-Z]+"                             # <exp:X/> / <exp:X> / <exp=X>
    r"|act\s*[:=]\s*[a-zA-Z]+"                            # <act:X/>
    r"|ui\s*:\s*navigate\b[^>]*"                          # <ui:navigate target="X"/>
    r"|tool\s*:\s*avatar_(?:motion|expression)\b[^>]*"    # <tool:avatar_* name="X"/>
    r"|dispatch\b[^>]*"                                   # <dispatch task="X"/>
    r")\s*/?\s*>",
    re.IGNORECASE,
)


def maybe_tag_prefix(fragment: str) -> bool:
    """判断「<」起始的残片是否可能是五族标签的前缀（跨 chunk 边界挂起判定）。

    仿 avatar_manager.EmotionStreamParser 的部分标签正则思路，泛化到五族：
    - 残片仍在标签名前缀内（如 `<e` / `<dis`）→ 挂起等待续包；
    - 标签名完整且其后是分隔字符/属性区（如 `<exp:smi` / `<dispatch task="查`）→ 挂起；
    - 其余（`<3`、`<b>`、`<expo` 等）→ 立即按普通文本放行，不误吞。
    """
    body = fragment[1:] if fragment.startswith("<") else fragment
    if body.startswith("/"):
        body = body[1:]
    body = body.lstrip()
    if not body:
        return True  # 裸 '<' 悬置，等续包判定（断流时由 flush 净化）
    low = body.lower()
    for name in TAG_FAMILY_NAMES:
        if name.startswith(low):
            return True  # 尚在标签名前缀内
        if low.startswith(name):
            rest = low[len(name):]
            if rest[0] in _TAG_NAME_SEPARATORS:
                return True  # 标签名完整，进入属性区（值可含任意字符，均挂起）
    return False
