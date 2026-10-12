"""五类标签网关单测（辰汐生态打通 W2，分册 08 §15 / 分册 10 §18）。

覆盖：
- TagStreamParser 五类标签解析（含跨 token 边界切分的流式喂入、宽松变体、残片净化）
- TagTranslator 8→12 映射、12 语义 ID 透传、neutral 兜底与计数、JSON 覆盖表
- 词表外工具/动作静默丢弃 + 计数（皮套工具开关、motion 注册表）
- 非自闭合 legacy <exp:X> 兼容（现役行为不回退：闭合标签回归 neutral）
- 无标签纯文本直通（含 "<" 数学比较不误吞）
- StreamProcessor 接线：事件随 chunk.data 透传、dispatch(detected) 存 ctx 挂点不下发
- fast_brain 开关对系统提示词的影响 + 四段式注入冻结字段
- TTS 过滤器剥离全族标签
"""

import asyncio
import json

from app.core.agents.middleware.base import AgentContext, HookRegistry
from app.core.tags import TagStreamParser, TagTranslator, parse_tags
from app.core.tags.definitions import TASK_DISPATCH_DETECTED_KEY
from app.core.tags.translator import get_default_translator
from app.runtime.provider.llm.types import StreamEvent
from app.services.avatar_manager import EmotionStreamParser, strip_emotion_tags
from app.services.context_service import ContextService
from app.services.stream_processor import StreamProcessor
from app.utils.tts_text_filter import filter_tts_text

# ──────────────────────────────────────────────────────────────
# 工具
# ──────────────────────────────────────────────────────────────


def _feed_all(parser: TagStreamParser, chunks: list[str]):
    """按切片依次喂入，返回 (拼接 clean, 全部事件)。"""
    clean_parts, events = [], []
    for c in chunks:
        clean, evs = parser.feed(c)
        clean_parts.append(clean)
        events.extend(evs)
    parser.flush()
    return "".join(clean_parts), events


def _kinds(events, kind):
    return [e.value for e in events if e.kind == kind]


# ──────────────────────────────────────────────────────────────
# 1. 五类标签解析
# ──────────────────────────────────────────────────────────────


class TestTagParsing:
    def test_emotion_contract_self_closing(self):
        clean, events = parse_tags("你好呀<exp:smile/>今天真开心")
        assert clean == "你好呀今天真开心"
        assert _kinds(events, "emotion") == ["happy"]

    def test_all_five_tag_families(self):
        text = (
            "<exp:smile/>嗨！<act:nod/>"
            "<ui:navigate target=\"settings_page\"/>"
            "<tool:avatar_motion name=\"wave\"/>"
            "<dispatch task=\"查一下明天的天气并总结\"/>"
        )
        clean, events = parse_tags(text, motion_registry=["wave"], avatar_tools_enabled=True)
        assert clean == "嗨！"
        assert _kinds(events, "emotion") == ["happy"]
        assert _kinds(events, "action") == ["nod"]
        assert _kinds(events, "navigate") == ["settings_page"]
        assert _kinds(events, "avatar_tool") == [{"name": "wave", "args": {}}]
        dispatch = _kinds(events, "dispatch")
        assert dispatch == [{
            "task": "查一下明天的天气并总结",
            "phase": "detected",
            "task_id": None,
            "summary": None,
        }]

    def test_streaming_split_across_token_boundaries(self):
        """标签被 token 切在任意边界：半截标签绝不放行到下游。"""
        full = "好<exp:surprise/>你居然知道<tool:avatar_motion name=\"jump\"/><act:think/>嗯"
        for cut in range(1, len(full)):
            parser = TagStreamParser(motion_registry=["jump"])
            chunks = [full[i:i + cut] for i in range(0, len(full), cut)]
            clean, events = _feed_all(parser, chunks)
            assert clean == "好你居然知道嗯", f"cut={cut} clean={clean!r}"
            assert _kinds(events, "emotion") == ["surprise"], f"cut={cut}"
            assert _kinds(events, "avatar_tool") == [{"name": "jump", "args": {}}], f"cut={cut}"
            assert _kinds(events, "action") == ["think"], f"cut={cut}"

    def test_loose_variants(self):
        """宽松级：大写、漏斜杠、= 替身、内部空格。"""
        clean, events = parse_tags("a<exp:SMILE>b<EXP:shy />c<act:NOD>d<exp=tilt>e")
        assert clean == "abcde"
        assert _kinds(events, "emotion") == ["happy", "shy", "curious"]
        assert _kinds(events, "action") == ["nod"]

    def test_fullwidth_colon_normalized(self):
        """中文冒号幻觉：归一后命中，事件取值不被小写折叠污染。"""
        clean, events = parse_tags("<exp：smile/>在吗")
        assert clean == "在吗"
        assert _kinds(events, "emotion") == ["happy"]

    def test_residual_fragment_purged_on_flush(self):
        parser = TagStreamParser()
        clean, events = parser.feed("文本<exp:smi")
        assert clean == "文本"
        clean2, events2 = parser.flush()
        assert clean2 == "" and events2 == []
        assert parser.counters["residual_dropped"] == 1

    def test_plain_text_passthrough(self):
        """无标签纯文本（含 '<' 数学比较、HTML）逐字直通。"""
        text = "1 < 2 且 a<b，看 <b>加粗</b> 和 3<5 吗？"
        parser = TagStreamParser()
        clean, events = _feed_all(parser, [text])
        assert clean == text
        assert events == []

    def test_unknown_emotion_falls_back_neutral(self):
        clean, events = parse_tags("嗯<exp:wink/>好")
        assert clean == "嗯好"
        assert _kinds(events, "emotion") == ["neutral"]
        assert get_default_translator().counters["unknown_fallback"] >= 1

    def test_emotion_change_suppression(self):
        """情绪未变化不重复发射（与现役 EmotionStreamParser 行为一致）。"""
        _, events = parse_tags("<exp:smile/>a<exp:smile/>b<exp:happy/>c")
        # smile 发射；重复 smile 抑制；happy 与当前值相同也抑制
        assert _kinds(events, "emotion") == ["happy"]

    def test_unknown_act_dropped_with_counter(self):
        parser = TagStreamParser()
        clean, events = _feed_all(parser, ["好<act:dance/>的"])
        assert clean == "好的"
        assert _kinds(events, "action") == []
        assert parser.counters["unknown_act"] == 1

    def test_dispatch_tag_never_reaches_visible_text(self):
        clean, _ = parse_tags("让我查查<dispatch task=\"\"/>好的")
        assert clean == "让我查查好的"


# ──────────────────────────────────────────────────────────────
# 2. 皮套工具开关 / 注册表
# ──────────────────────────────────────────────────────────────


class TestAvatarTools:
    def test_motion_registry_violation_dropped(self):
        parser = TagStreamParser(motion_registry=["wave"], avatar_tools_enabled=True)
        clean, events = _feed_all(parser, ["<tool:avatar_motion name=\"backflip\"/>"])
        assert clean == ""
        assert events == []
        assert parser.counters["tool_dropped"] == 1

    def test_motion_registry_hit_emitted(self):
        parser = TagStreamParser(motion_registry=["wave", "jump"], avatar_tools_enabled=True)
        _, events = _feed_all(parser, ["<tool:avatar_motion name=\"jump\"/>"])
        assert _kinds(events, "avatar_tool") == [{"name": "jump", "args": {}}]

    def test_tools_disabled_dropped_with_counter(self):
        """皮套工具仅快脑可挂：开关关闭时剥离不发射（留痕计数）。"""
        parser = TagStreamParser(motion_registry=["wave"], avatar_tools_enabled=False)
        clean, events = _feed_all(parser, ["<tool:avatar_expression name=\"sparkle\"/>"])
        assert clean == ""
        assert events == []
        assert parser.counters["tool_dropped"] == 1

    def test_tool_name_too_long_dropped(self):
        parser = TagStreamParser(avatar_tools_enabled=True)
        _, events = _feed_all(parser, ["<tool:avatar_motion name=\"" + "a" * 33 + "\"/>"])
        assert events == []
        assert parser.counters["tool_dropped"] == 1

    def test_expression_tool_format_only(self):
        """expression 本期无注册表配置：仅格式校验（≤32 字符小写/数字/下划线）。"""
        parser = TagStreamParser(avatar_tools_enabled=True)
        _, events = _feed_all(parser, ["<tool:avatar_expression name=\"cat_ears\"/>"])
        assert _kinds(events, "avatar_tool") == [{"name": "cat_ears", "args": {}}]

    def test_tool_does_not_override_emotion_channel(self):
        """优先级条款 1：工具调用不影响情绪通道（情绪只归 <exp:>）。"""
        parser = TagStreamParser(motion_registry=["wave"], avatar_tools_enabled=True)
        _, events = _feed_all(parser, ["<exp:shy/><tool:avatar_expression name=\"x\"/>"])
        assert _kinds(events, "emotion") == ["shy"]
        assert _kinds(events, "avatar_tool") == [{"name": "x", "args": {}}]


# ──────────────────────────────────────────────────────────────
# 3. 翻译映射表
# ──────────────────────────────────────────────────────────────


class TestTranslator:
    def test_builtin_8_to_12_mapping(self):
        tr = TagTranslator()
        expect = {
            "smile": "happy", "angry": "angry", "shy": "shy", "surprise": "surprise",
            "tilt": "curious", "sigh": "awkward", "wronged": "sad", "cry": "sad",
        }
        for word, semantic in expect.items():
            assert tr.translate(word) == (semantic, True), word
        assert tr.counters["contract_translated"] == 8

    def test_semantic_passthrough(self):
        """在役 12 语义 ID 透传（现役非自闭合行为不回退）。"""
        tr = TagTranslator()
        assert tr.translate("love") == ("love", True)
        assert tr.translate("excited") == ("excited", True)
        assert tr.translate("confused") == ("confused", True)
        assert tr.counters["semantic_passthrough"] == 3

    def test_unknown_neutral_and_counter(self):
        tr = TagTranslator()
        assert tr.translate("wink") == ("neutral", False)
        assert tr.translate("") == ("neutral", False)
        assert tr.counters["unknown_fallback"] == 2
        # 新实例只经过本用例的两次兜底，未命中映射/透传
        assert tr.counters["contract_translated"] == 0
        assert tr.counters["semantic_passthrough"] == 0

    def test_override_json_file(self, tmp_path):
        override = tmp_path / "translation.json"
        override.write_text(
            json.dumps({"smile": "love", "bogus": "not-an-id", 3: "sad"}),
            encoding="utf-8",
        )
        tr = TagTranslator(override_path=str(override))
        assert tr.translate("smile") == ("love", True)   # 覆盖表优先
        assert tr.translate("tilt") == ("curious", True)  # 未覆盖走内置
        # 非法条目（值非语义 ID / 键非字符串）被跳过
        assert tr.translate("bogus") == ("neutral", False)

    def test_override_missing_file_uses_builtin(self, tmp_path):
        tr = TagTranslator(override_path=str(tmp_path / "nope.json"))
        assert tr.translate("smile") == ("happy", True)


# ──────────────────────────────────────────────────────────────
# 4. legacy <exp:X> 非自闭合兼容（现役行为不回退）
# ──────────────────────────────────────────────────────────────


class TestLegacyEmotionCompat:
    def test_legacy_open_tag_and_closing_tag(self):
        parser = EmotionStreamParser()
        clean, emo = parser.feed("今天<exp:happy>真开心！</exp:happy>")
        assert clean == "今天真开心！"
        assert emo == "neutral"  # 闭合标签回归 neutral（最后事件）

    def test_legacy_streaming_split(self):
        parser = EmotionStreamParser()
        clean1, emo1 = parser.feed("好<exp:")
        assert clean1 == "好" and emo1 is None
        clean2, emo2 = parser.feed("curious>接着说")
        assert clean1 + clean2 == "好接着说"
        assert emo2 == "curious"

    def test_legacy_stream_of_tokens_no_leak(self):
        full = "<exp:happy>太好了！<exp:shy>嘿嘿～"
        parser = EmotionStreamParser()
        chunks = [full[i:i + 3] for i in range(0, len(full), 3)]
        clean_parts, emotions = [], []
        for c in chunks:
            clean, emo = parser.feed(c)
            clean_parts.append(clean)
            if emo:
                emotions.append(emo)
        assert "".join(clean_parts) == "太好了！嘿嘿～"
        assert emotions == ["happy", "shy"]

    def test_strip_emotion_tags_covers_all_families(self):
        text = (
            "<exp:happy>你好<act:nod/><ui:navigate target=\"x\"/>"
            "<tool:avatar_motion name=\"w\"/><dispatch task=\"查天气\"/>完了"
        )
        assert strip_emotion_tags(text) == "你好完了"

    def test_legacy_loose_space_variant(self):
        parser = EmotionStreamParser()
        clean, emo = parser.feed("< exp:surprise >哇")
        assert clean == "哇"
        assert emo == "surprise"


# ──────────────────────────────────────────────────────────────
# 5. StreamProcessor 接线：事件透传与 ctx 挂点
# ──────────────────────────────────────────────────────────────


def _make_processor(monkeypatch, motion_registry=None, tools_enabled=True):
    from app.core.config import settings

    monkeypatch.setattr(settings, "AVATAR_MOTION_REGISTRY", motion_registry or [])
    monkeypatch.setattr(settings, "AVATAR_TOOLS_ENABLED", tools_enabled)
    return StreamProcessor(HookRegistry())


class TestStreamProcessorWiring:
    def test_events_flow_to_chunk_data_and_dispatch_to_ctx(self, monkeypatch):
        processor = _make_processor(monkeypatch, motion_registry=["wave"])

        async def source():
            for token in ["今天<exp:smile/", ">真开心<act:nod/><dispatch task=\"查天", "气并总结\"/>"]:
                yield StreamEvent("content", {"content": token})

        ctx = AgentContext(messages=[], state={"chat_id": "c1", "model": "m", "provider": "p"})
        collected = []

        async def run():
            async for chunk in processor.process_stream(source(), ctx):
                collected.append(chunk)

        asyncio.run(run())

        contents = "".join(c.data.get("content", "") for c in collected)
        assert contents == "今天真开心"
        # emotion/action 随 chunk.data 透传（→ runner → SSE chunk 契约字段）
        emotions = [c.data["emotion"] for c in collected if "emotion" in c.data]
        actions = [c.data["action"] for c in collected if "action" in c.data]
        assert emotions == ["happy"]
        assert actions == ["nod"]
        # dispatch(detected) 不进 chunk.data，存 ctx.state 挂点（派发中间件约定字段）
        assert all("dispatch" not in c.data and "task_dispatch" not in c.data for c in collected)
        pending = ctx.state.get(TASK_DISPATCH_DETECTED_KEY)
        assert pending == [{
            "task": "查天气并总结", "phase": "detected",
            "task_id": None, "summary": None,
        }]

    def test_avatar_tool_event_flows(self, monkeypatch):
        processor = _make_processor(monkeypatch, motion_registry=["wave"])

        async def source():
            yield StreamEvent("content", {"content": "<tool:avatar_motion name=\"wave\"/>"})

        ctx = AgentContext(messages=[], state={})
        collected = []

        async def run():
            async for chunk in processor.process_stream(source(), ctx):
                collected.append(chunk)

        asyncio.run(run())
        tools = [c.data["avatar_tool"] for c in collected if "avatar_tool" in c.data]
        assert tools == [{"name": "wave", "args": {}}]


# ──────────────────────────────────────────────────────────────
# 6. fast_brain 开关：提示词注入与四段式
# ──────────────────────────────────────────────────────────────


class TestFastBrainPrompt:
    def test_fast_brain_off_keeps_legacy_prompt(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "FAST_BRAIN", "")
        prompt = ContextService.build_system_prompt(None, provider="p", model="m")
        assert "<exp:EMOTION_ID>" in prompt        # 现役 12 语义 ID 块
        assert "<exp:WORD/>" not in prompt         # 合同风格块未注入
        assert "dispatch_discipline" not in prompt

    def test_fast_brain_match_switches_blocks(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "FAST_BRAIN", "p/m")
        monkeypatch.setattr(settings, "AVATAR_TOOLS_ENABLED", True)
        monkeypatch.setattr(settings, "AVATAR_MOTION_REGISTRY", ["wave", "jump"])

        prompt = ContextService.build_system_prompt(None, provider="p", model="m")
        assert "<exp:WORD/>" in prompt
        for word in ("smile", "tilt", "sigh", "wronged", "cry"):
            assert word in prompt
        assert "nod" in prompt and "hug" in prompt
        # 派发自律条款原文（分册 10 §18.3 逐字）
        assert ContextService._DISPATCH_DISCIPLINE_TEXT in prompt
        # 皮套工具说明（开关开 + 注册表非空）
        assert "<tool:avatar_motion name=\"ID\"/>" in prompt
        assert "wave" in prompt

    def test_fast_brain_mismatch_keeps_legacy(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "FAST_BRAIN", "p/m")
        prompt = ContextService.build_system_prompt(None, provider="p", model="other")
        assert "<exp:EMOTION_ID>" in prompt
        assert "dispatch_discipline" not in prompt

    def test_fast_brain_tools_block_requires_registry(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "FAST_BRAIN", "p/m")
        monkeypatch.setattr(settings, "AVATAR_TOOLS_ENABLED", True)
        monkeypatch.setattr(settings, "AVATAR_MOTION_REGISTRY", [])
        prompt = ContextService.build_system_prompt(None, provider="p", model="m")
        assert "avatar_tools" not in prompt  # 注册表空 → 不注入工具说明

    def test_is_fast_brain_model_matching(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "FAST_BRAIN", "deepseek/deepseek-chat")
        assert ContextService.is_fast_brain_model("deepseek", "deepseek-chat") is True
        assert ContextService.is_fast_brain_model("deepseek", "other") is False
        assert ContextService.is_fast_brain_model("openai", "deepseek-chat") is False
        # model_id 自身含 "/"：按首个 "/" 切分
        monkeypatch.setattr(settings, "FAST_BRAIN", "sf/deepseek-ai/V3")
        assert ContextService.is_fast_brain_model("sf", "deepseek-ai/V3") is True
        # 空 = 关闭
        monkeypatch.setattr(settings, "FAST_BRAIN", "")
        assert ContextService.is_fast_brain_model("sf", "x") is False


class TestFourPartInjection:
    def test_frozen_segments_and_fields(self, monkeypatch):
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "今天天气怎么样？"},
        ]
        out = ContextService.inject_fast_brain_protocol(
            messages, agent_id=None, session_mode="private_chat", is_owner=True,
        )
        content = out[-1]["content"]
        assert content.startswith("[当前说话人] ")
        assert "[时间节律] " in content
        assert "[平台状态] " in content
        assert content.endswith("今天天气怎么样？")
        # 冻结 JSON 字段名（分册 10 §18.1：name/is_owner/now/part_of_day/app/session_mode）
        assert "\"name\":" in content and "\"is_owner\": true" in content
        assert "\"now\":" in content and "\"part_of_day\":" in content
        assert "\"app\": \"luominest\"" in content
        assert "\"session_mode\": \"private_chat\"" in content
        # 前面的消息不受影响
        assert out[0]["content"] == "sys"

    def test_no_user_message_noop(self):
        messages = [{"role": "system", "content": "sys"}]
        out = ContextService.inject_fast_brain_protocol(messages, agent_id=None)
        assert out == messages

    def test_multimodal_content_untouched(self):
        content = [{"type": "text", "text": "看图"}, {"type": "image_url", "image_url": {"url": "x"}}]
        messages = [{"role": "user", "content": content}]
        out = ContextService.inject_fast_brain_protocol(messages, agent_id=None)
        assert out[-1]["content"] == content

    def test_speaker_name_fallback_and_override(self, monkeypatch):
        messages = [{"role": "user", "content": "hi"}]
        out = ContextService.inject_fast_brain_protocol(
            messages, agent_id=None, speaker_name="辰汐", is_owner=False,
        )
        assert "\"name\": \"辰汐\"" in out[-1]["content"]
        assert "\"is_owner\": false" in out[-1]["content"]

    def test_resolve_session_mode(self):
        assert ContextService.resolve_session_mode("", "workbench") == "private_chat"
        assert ContextService.resolve_session_mode("platform_group", "") == "group_chat"
        assert ContextService.resolve_session_mode("platform", "workbench") == "private_chat"


# ──────────────────────────────────────────────────────────────
# 7. TTS 过滤
# ──────────────────────────────────────────────────────────────


class TestTTSFilter:
    def test_all_tag_families_stripped(self):
        text = (
            "<exp:happy>你好呀<act:nod/>"
            "<ui:navigate target=\"main\"/>"
            "<tool:avatar_motion name=\"wave\"/>"
            "<tool:avatar_expression name=\"sparkle\"/>"
            "<dispatch task=\"查天气\"/>"
            "<exp:shy>今天也可以哦"
        )
        out = filter_tts_text(text)
        assert "exp:" not in out and "act:" not in out
        assert "navigate" not in out and "avatar_" not in out and "dispatch" not in out
        assert "你好呀" in out and "今天也可以哦" in out

    def test_plain_text_untouched(self):
        text = "普通句子，1 < 2，没有标签。"
        assert "普通句子" in filter_tts_text(text)
