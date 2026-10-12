"""TagStreamParser — 五类合同标签的流式安全统一网关（分册 08 §15.3）。

feed(chunk) -> (clean_text, [TagEvent, ...])：
- 缓冲匹配：标签可能被 token 切在边界（`<exp:` + `smile/>`、`<tool:avatar_` +
  `motion name="wave"/>`），疑似标签前缀挂起等待续包，闭合即解析；
  断流 flush() 时残片净化，绝不把半截标签放行到下游。
- 严格 + 宽松双正则：严格级 = 合同形态（自闭合、半角、小写）；宽松级 = 大小写
  归一、中文冒号 `：`→`:`、漏 `/`、`=` 冒号替身、标签内空格变体；两级都不过
  且已闭合才按普通文本放行。
- 优先级硬规则：情绪归属 <exp:> 通道（皮套工具不影响情绪通道）；词表外
  工具/动作静默丢弃 + 计数；任何情况下不抛错、不中断流。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from loguru import logger

from app.core.tags.definitions import (
    ACT_NAMES,
    ACT_TAG_RE,
    DEFAULT_EMOTION_ID,
    DISPATCH_TAG_RE,
    EMOTION_TAG_RE,
    NAVIGATE_TAG_RE,
    TOOL_AVATAR_MOTION,
    TOOL_NAME_MAX_LEN,
    TOOL_TAG_RE,
    maybe_tag_prefix,
)
from app.core.tags.translator import TagTranslator, get_default_translator


@dataclass
class TagEvent:
    """结构化标签事件。

    kind: "emotion" | "action" | "navigate" | "avatar_tool" | "dispatch"
    value: emotion=语义 ID；action=动作名；navigate=目标；
           avatar_tool={"name": str, "args": dict}；
           dispatch={"task": str, "phase": "detected", "task_id": None, "summary": None}
    """
    kind: str
    value: Any = None


@dataclass
class _MatchResult:
    kind: str
    end: int
    groups: tuple


class TagStreamParser:
    """有状态流式解析器。线程不安全：每条生成流各建一个实例（与 EmotionStreamParser 同约定）。"""

    def __init__(
        self,
        translator: TagTranslator | None = None,
        motion_registry: list[str] | None = None,
        avatar_tools_enabled: bool = True,
    ):
        """
        Args:
            translator: 情绪词翻译器；缺省取全局默认（含 JSON 覆盖表）。
            motion_registry: motion 注册表（model_config.avatar_motion_registry）。
                非空时注册表外的 <tool:avatar_motion> 取值静默丢弃 + 计数；
                为空时所有 motion 调用均视为注册表外（注册表即存在性声明）。
                <tool:avatar_expression> 本期无注册表配置，仅做格式校验（≤32 字符）。
            avatar_tools_enabled: 皮套工具总开关（model_config.avatar_tools_enabled）。
                关闭时 <tool:avatar_*> 一律剥离不发射（留痕日志 + 计数）——
                分册 08 §15.2 优先级条款 3：皮套工具仅快脑可挂。
        """
        self.translator = translator or get_default_translator()
        self.motion_registry = {
            m.strip().lower() for m in (motion_registry or [])
            if isinstance(m, str) and m.strip()
        }
        self.avatar_tools_enabled = bool(avatar_tools_enabled)
        self._pending: str = ""
        self._current_emotion: str | None = None
        # 解析器侧计数留痕（词级计数在 translator.counters）
        self.counters: dict[str, int] = {
            "unknown_act": 0,        # act 词表外
            "tool_dropped": 0,       # 工具标签丢弃（开关关闭/词表外/超长）
            "dispatch_detected": 0,  # 派发标签捕获数
            "residual_dropped": 0,   # 断流残片净化数
        }

    # ── 流式入口 ──────────────────────────────────────────────

    def feed(self, chunk: str) -> tuple[str, list[TagEvent]]:
        """喂入一个流式 token，返回 (干净文本, 结构化事件列表)。"""
        events: list[TagEvent] = []
        if not chunk:
            return ("", events)

        buf = self._pending + chunk
        self._pending = ""
        clean_parts: list[str] = []
        i = 0
        n = len(buf)

        while i < n:
            lt = buf.find("<", i)
            if lt == -1:
                clean_parts.append(buf[i:])
                break
            if lt > i:
                clean_parts.append(buf[i:lt])

            matched = self._match_strict(buf, lt)
            if matched is None:
                matched = self._match_normalized(buf, lt)

            if matched is not None:
                clean_parts.append(self._emit(matched, events))
                i = matched.end
                continue

            gt = buf.find(">", lt)
            if gt == -1 and maybe_tag_prefix(buf[lt:]):
                # 疑似标签前缀且尚未闭合：挂起等待续包（绝不放行半截标签）
                logger.debug(f"[TagParser] 挂起疑似标签残片: {buf[lt:]!r}")
                self._pending = buf[lt:]
                break
            # 不是本网关的标签（<b>、<3、已闭合但不匹配等）→ '<' 按普通文本放行
            clean_parts.append("<")
            i = lt + 1

        return ("".join(clean_parts), events)

    def flush(self) -> tuple[str, list[TagEvent]]:
        """断流 flush：挂起的疑似标签残片净化（丢弃 + 计数），绝不放行半截标签。"""
        events: list[TagEvent] = []
        if self._pending:
            self.counters["residual_dropped"] += 1
            logger.debug(f"[TagParser] 断流净化未闭合残片: {self._pending!r}")
            self._pending = ""
        return ("", events)

    def reset(self) -> None:
        self._pending = ""
        self._current_emotion = None

    @property
    def current_emotion(self) -> str | None:
        return self._current_emotion

    # ── 匹配通道 ──────────────────────────────────────────────

    @staticmethod
    def _match_strict(buf: str, lt: int) -> _MatchResult | None:
        """严格级：宽松正则族（含大小写/空格/漏斜杠容错，半角标点）直接匹配。"""
        for kind, regex in (
            ("emotion", EMOTION_TAG_RE),
            ("act", ACT_TAG_RE),
            ("navigate", NAVIGATE_TAG_RE),
            ("tool", TOOL_TAG_RE),
            ("dispatch", DISPATCH_TAG_RE),
        ):
            m = regex.match(buf, lt)
            if m:
                return _MatchResult(kind=kind, end=m.end(), groups=m.groups())
        return None

    @staticmethod
    def _match_normalized(buf: str, lt: int) -> _MatchResult | None:
        """宽松级补充：全角幻觉归一重试（中文冒号 `：`→`:`；正则本身已忽略大小写）。

        只对候选子串归一，原文不受影响，且事件取值从归一后的原文提取（不做
        小写折叠，避免篡改 dispatch task 等自由文本值）。已有 `>` 才尝试
        （未闭合的残片走挂起通道）。
        """
        gt = buf.find(">", lt)
        if gt == -1:
            return None
        candidate = buf[lt:gt + 1].replace("：", ":")
        for kind, regex in (
            ("emotion", EMOTION_TAG_RE),
            ("act", ACT_TAG_RE),
            ("navigate", NAVIGATE_TAG_RE),
            ("tool", TOOL_TAG_RE),
            ("dispatch", DISPATCH_TAG_RE),
        ):
            m = regex.match(candidate)
            if m:
                return _MatchResult(kind=kind, end=gt + 1, groups=m.groups())
        return None

    # ── 事件发射（永不抛错） ──────────────────────────────────

    def _emit(self, matched: _MatchResult, events: list[TagEvent]) -> str:
        """按标签族发射结构化事件，返回空串（标签从可见文本剥离）。"""
        try:
            handler = getattr(self, f"_on_{matched.kind}")
            handler(matched.groups, events)
        except Exception as e:  # 兜底防线：解析器任何异常都不中断流
            logger.warning(f"[TagParser] 事件发射异常已忽略: kind={matched.kind}, error={e}")
        return ""

    def _on_emotion(self, groups: tuple, events: list[TagEvent]) -> None:
        prefix, word = groups[0], groups[1]
        if prefix == "</":
            # 闭合标签 </exp:X>：回归 neutral（与在役 EmotionStreamParser 行为一致）
            if self._current_emotion is not None and self._current_emotion != DEFAULT_EMOTION_ID:
                self._current_emotion = DEFAULT_EMOTION_ID
                events.append(TagEvent("emotion", DEFAULT_EMOTION_ID))
            return
        semantic, _known = self.translator.translate(word)
        if semantic != self._current_emotion:
            self._current_emotion = semantic
            events.append(TagEvent("emotion", semantic))

    def _on_act(self, groups: tuple, events: list[TagEvent]) -> None:
        prefix, name = groups[0], groups[1]
        if prefix == "</":
            return  # 闭合形态非合同用法，静默剥离
        name = name.lower()
        if name in ACT_NAMES:
            events.append(TagEvent("action", name))
        else:
            # act 词表外：静默丢弃 + 计数
            self.counters["unknown_act"] += 1
            logger.debug(f"[TagParser] act 词表外已丢弃: {name!r}")

    def _on_navigate(self, groups: tuple, events: list[TagEvent]) -> None:
        events.append(TagEvent("navigate", groups[0]))

    def _on_tool(self, groups: tuple, events: list[TagEvent]) -> None:
        tool_name = groups[0].lower()
        name = (groups[1] or "").strip().lower()

        # 皮套工具仅快脑可挂（分册 08 §15.2 优先级条款 3）：开关关闭一律剥离 + 留痕
        if not self.avatar_tools_enabled:
            self.counters["tool_dropped"] += 1
            logger.debug(f"[TagParser] 皮套工具未启用已丢弃: <tool:{tool_name} name={name!r}>")
            return
        # 参数值 >32 字符判非法（分册 08 §15.2），静默丢弃 + 计数
        if not name or len(name) > TOOL_NAME_MAX_LEN:
            self.counters["tool_dropped"] += 1
            logger.debug(f"[TagParser] 皮套工具参数非法已丢弃: <tool:{tool_name} name={name!r}>")
            return
        # motion 注册表外取值 → 静默丢弃 + 计数（注册表为空 = 全部注册表外）
        if tool_name == TOOL_AVATAR_MOTION and self.motion_registry and name not in self.motion_registry:
            self.counters["tool_dropped"] += 1
            logger.debug(f"[TagParser] motion 注册表外已丢弃: {name!r}")
            return
        # 注册表为空时不做 motion 白名单（注册表未声明，仅格式校验）；
        # expression 本期无注册表配置，同仅格式校验。
        events.append(TagEvent("avatar_tool", {"name": name, "args": {}}))

    def _on_dispatch(self, groups: tuple, events: list[TagEvent]) -> None:
        task = next((g for g in groups if g is not None), "")
        self.counters["dispatch_detected"] += 1
        # W2 只产生 phase="detected"（解析层捕获）；start/done/error 由派发中间件产生。
        # 事件不直接下发前端：由 StreamProcessor 写入 ctx.state 挂点（见 definitions）。
        events.append(TagEvent("dispatch", {
            "task": task or "",
            "phase": "detected",
            "task_id": None,
            "summary": None,
        }))


# ── 非流式便捷函数（复用同一解析器，供非流式兜底 / 单测使用） ──────────

def parse_tags(
    text: str,
    translator: TagTranslator | None = None,
    motion_registry: list[str] | None = None,
    avatar_tools_enabled: bool = True,
) -> tuple[str, list[TagEvent]]:
    """整段文本一次性解析：返回 (剥离标签后的干净文本, 全部结构化事件)。"""
    parser = TagStreamParser(
        translator=translator,
        motion_registry=motion_registry,
        avatar_tools_enabled=avatar_tools_enabled,
    )
    clean, events = parser.feed(text)
    parser.flush()
    return clean, events


def strip_all_tags(
    text: str,
    translator: TagTranslator | None = None,
    motion_registry: list[str] | None = None,
    avatar_tools_enabled: bool = True,
) -> str:
    """剥离五族标签（含自闭合与非自闭合形态），返回干净文本。绝不抛错。"""
    try:
        return parse_tags(
            text, translator=translator, motion_registry=motion_registry,
            avatar_tools_enabled=avatar_tools_enabled,
        )[0]
    except Exception as e:  # 双重兜底：任何异常都回退原文清洗（只丢标签不丢流）
        logger.warning(f"[TagParser] strip_all_tags 异常已兜底: {e}")
        return text or ""
