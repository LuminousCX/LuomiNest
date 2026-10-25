"""G0 升格关键缺口单测（赛博生命升格计划书 §6.1，2026-10-25 拍板⑧⑨⑩⑪⑫）。

覆盖：
- G0-A 平台非流式独立挂载组（build_default_pipeline scene="platform"）；
- G0-A DispatchMiddleware 平台场景扩展（scene 守卫 + 结果登记挂点 + dispatch_context 快照）；
- G0-B Ollama think 参数透传（chat_completions payload）；
- G0-C 群上下文扩容（group_config context_limit/分段参数 + 历史加载条数）；
- G0-D 分段发送服务（segmenter 切分/延迟/清理/发送计划）；
- G0-F avatar_drive model_id 修复（schema 路由键字段）。
"""
from __future__ import annotations

import pytest

from app.core.agents.middleware.base import AgentContext
from app.core.tags.definitions import (
    TASK_DISPATCH_DETECTED_KEY,
    TASK_DISPATCH_RESULTS_KEY,
)


# ──────────────────────────────────────────────────────────────
# G0-A 平台非流式独立挂载组
# ──────────────────────────────────────────────────────────────


class TestPlatformPipelineWiring:
    """scene="platform" 独立挂载组（拍板⑧：不动 chat 流式组）。"""

    def _types(self, extra: dict) -> list[type]:
        from app.core.tools.orchestrator import ToolOrchestrator

        return [type(m) for m in ToolOrchestrator().build_default_pipeline(extra).middlewares]

    def _required(self):
        from app.core.agents.middleware.builtin import (
            ContextTrimMiddleware,
            LoopGuardMiddleware,
            MemoryAccessMiddleware,
            ToolExecutionMiddleware,
            ToolFilterMiddleware,
            UsageTrackMiddleware,
        )
        from app.core.agents.middleware.dispatch import DispatchMiddleware
        from app.core.agents.middleware.permission import PermissionGateMiddleware

        return (
            MemoryAccessMiddleware,
            ToolFilterMiddleware,
            ContextTrimMiddleware,
            LoopGuardMiddleware,
            PermissionGateMiddleware,
            DispatchMiddleware,
            ToolExecutionMiddleware,
            UsageTrackMiddleware,
        )

    def _forbidden(self):
        from app.core.agents.middleware.builtin import (
            SpecialToolMiddleware,
            SSEEmitMiddleware,
            SubagentCancelMiddleware,
        )

        return (SpecialToolMiddleware, SSEEmitMiddleware, SubagentCancelMiddleware)

    def test_platform_non_stream_mount_group(self):
        types = self._types({"scene": "platform", "is_stream": False})
        for mw in self._required():
            assert mw in types, f"{mw.__name__} 应挂载于 platform 管道"
        for mw in self._forbidden():
            assert mw not in types, f"{mw.__name__} 不应挂载于 platform 管道（流式/子Agent 专用）"

    def test_platform_order_dispatch_before_tool_execution(self):
        from app.core.agents.middleware.builtin import ToolExecutionMiddleware
        from app.core.agents.middleware.dispatch import DispatchMiddleware

        types = self._types({"scene": "platform", "is_stream": False})
        # after_model 反序执行 → Dispatch 先于 ToolExecution 消费挂点
        assert types.index(DispatchMiddleware) < types.index(ToolExecutionMiddleware)

    def test_chat_stream_group_unchanged(self):
        """回归保护：chat 流式挂载组与 G0 前一致。"""
        types = self._types({"scene": "chat", "is_stream": True})
        for mw in self._forbidden():
            if mw.__name__ == "SubagentCancelMiddleware":
                assert mw not in types
            else:
                assert mw in types

    def test_chat_non_stream_still_no_dispatch(self):
        types = self._types({"scene": "chat", "is_stream": False})
        from app.core.agents.middleware.dispatch import DispatchMiddleware

        assert DispatchMiddleware not in types

    def test_subagent_group_unchanged(self):
        types = self._types({"scene": "subagent", "is_stream": True})
        from app.core.agents.middleware.builtin import SubagentCancelMiddleware
        from app.core.agents.middleware.dispatch import DispatchMiddleware

        assert SubagentCancelMiddleware in types
        assert DispatchMiddleware not in types


# ──────────────────────────────────────────────────────────────
# G0-A DispatchMiddleware 平台场景
# ──────────────────────────────────────────────────────────────


class TestDispatchPlatformScene:
    def _ctx(self, scene: str) -> AgentContext:
        return AgentContext(
            messages=[],
            tools=None,
            state={"provider": "p", "model": "m"},
            extra={"scene": scene, "is_stream": False},
        )

    @pytest.mark.asyncio
    async def test_platform_scene_processes_dispatch_and_registers_result(self, monkeypatch):
        from app.core.agents.middleware import dispatch as dispatch_mod

        async def _fake_slow_brain(ctx, task, slow):
            return "慢脑执行结果文本"

        monkeypatch.setattr(dispatch_mod, "resolve_slow_brain", lambda: {
            "provider": "p", "model": "m", "source": "slow_brain",
        })
        monkeypatch.setattr(dispatch_mod, "heuristic_filter", lambda task: None)
        monkeypatch.setattr(
            dispatch_mod.DispatchMiddleware, "_run_slow_brain",
            staticmethod(_fake_slow_brain),
        )

        ctx = self._ctx("platform")
        ctx.state[TASK_DISPATCH_DETECTED_KEY] = [{"task": "帮我把这件事查清楚"}]
        await dispatch_mod.DispatchMiddleware().after_model(ctx, {})

        results = ctx.state.get(TASK_DISPATCH_RESULTS_KEY) or []
        assert len(results) == 1
        assert results[0]["result"] == "慢脑执行结果文本"
        assert results[0]["task_id"].startswith("dispatch_")

    @pytest.mark.asyncio
    async def test_group_scene_still_skipped(self, monkeypatch):
        from app.core.agents.middleware import dispatch as dispatch_mod

        ctx = self._ctx("group")
        ctx.state[TASK_DISPATCH_DETECTED_KEY] = [{"task": "帮我把这件事查清楚"}]
        await dispatch_mod.DispatchMiddleware().after_model(ctx, {})
        assert not (ctx.state.get(TASK_DISPATCH_RESULTS_KEY) or [])

    @pytest.mark.asyncio
    async def test_error_phase_not_registered_as_result(self, monkeypatch):
        """无慢脑 → error 事件，不登记结果（platform_router 只投递 done 结果）。"""
        from app.core.agents.middleware import dispatch as dispatch_mod

        monkeypatch.setattr(dispatch_mod, "resolve_slow_brain", lambda: None)
        monkeypatch.setattr(dispatch_mod, "heuristic_filter", lambda task: None)

        ctx = self._ctx("platform")
        ctx.state[TASK_DISPATCH_DETECTED_KEY] = [{"task": "帮我把这件事查清楚"}]
        await dispatch_mod.DispatchMiddleware().after_model(ctx, {})
        assert not (ctx.state.get(TASK_DISPATCH_RESULTS_KEY) or [])

    def test_context_snapshot_prefers_dispatch_context(self):
        """G0-C：ctx.extra["dispatch_context"] 优先于最小快照（8000 字裁剪）。"""
        from app.core.agents.middleware.dispatch import DispatchMiddleware, _DISPATCH_CONTEXT_MAX

        ctx = self._ctx("platform")
        long_text = "事实" * (_DISPATCH_CONTEXT_MAX // 2 + 10)
        ctx.extra["dispatch_context"] = long_text
        ctx.messages = [{"role": "user", "content": "来源会话最近消息"}]
        snapshot = DispatchMiddleware._context_snapshot(ctx)
        assert snapshot.startswith("事实")
        assert len(snapshot) <= _DISPATCH_CONTEXT_MAX + 1  # 裁剪 + 省略号
        assert "来源会话最近消息" not in snapshot

    def test_context_snapshot_fallback_minimal(self):
        from app.core.agents.middleware.dispatch import DispatchMiddleware

        ctx = self._ctx("platform")
        ctx.messages = [{"role": "user", "content": "来源会话最近消息"}]
        assert "来源会话用户最近消息" in DispatchMiddleware._context_snapshot(ctx)


# ──────────────────────────────────────────────────────────────
# G0-B Ollama think 参数透传
# ──────────────────────────────────────────────────────────────


class TestOllamaThinkPayload:
    def _payload(self, extra: dict) -> dict:
        from app.runtime.provider.llm.adapters.chat_completions import OpenAICompatibleProvider
        from app.runtime.provider.llm.types import LLMRequest

        provider = OpenAICompatibleProvider({
            "id": "ollama", "name": "Ollama", "api_base": "http://127.0.0.1:11434/v1",
            "api_key": "ollama", "default_model": "qwen3:8b",
        })
        request = LLMRequest(
            messages=[{"role": "user", "content": "hi"}],
            model="qwen3:8b",
            extra=extra,
        )
        return provider._build_payload(request, stream=False)

    def test_think_false_lands_in_payload(self):
        assert self._payload({"think": False})["think"] is False

    def test_think_true_lands_in_payload(self):
        assert self._payload({"think": True})["think"] is True

    def test_no_think_key_when_absent(self):
        assert "think" not in self._payload({})


# ──────────────────────────────────────────────────────────────
# G0-C 群上下文扩容
# ──────────────────────────────────────────────────────────────


class TestGroupConfigG0:
    @pytest.mark.usefixtures("_init_test_db")
    def test_new_defaults_present(self):
        from app.runtime.platform.group_config import DEFAULT_GROUP_CONFIG, get_group_config

        cfg = get_group_config("inst_g0", "10001")
        assert cfg["context_limit"] == 100
        assert cfg["segment_enabled"] is True
        assert cfg["segment_max_chars"] == 150
        assert cfg["segment_delay_mode"] == "log"
        assert DEFAULT_GROUP_CONFIG["segment_delay_min"] == 1.5
        assert DEFAULT_GROUP_CONFIG["segment_delay_max"] == 3.5

    @pytest.mark.usefixtures("_init_test_db")
    def test_context_limit_clamped_and_int(self):
        from app.runtime.platform.group_config import get_group_config, set_group_config

        cfg = set_group_config("inst_g0", "10001", {"context_limit": 5})
        assert cfg["context_limit"] == 10  # 下边界夹取
        cfg = set_group_config("inst_g0", "10001", {"context_limit": 99999})
        assert cfg["context_limit"] == 500  # 上边界夹取
        cfg = set_group_config("inst_g0", "10001", {"context_limit": 80.7})
        assert cfg["context_limit"] == 80 and isinstance(cfg["context_limit"], int)

    @pytest.mark.usefixtures("_init_test_db")
    def test_segment_delay_mode_validated(self):
        from app.runtime.platform.group_config import set_group_config

        with pytest.raises(ValueError):
            set_group_config("inst_g0", "10001", {"segment_delay_mode": "instant"})
        cfg = set_group_config("inst_g0", "10001", {"segment_delay_mode": "random"})
        assert cfg["segment_delay_mode"] == "random"


class TestHistoryLimit:
    def test_load_history_limit(self):
        from app.services.platform_router import LuomiNestPlatformRouter

        conv = {"messages": [{"role": "user", "content": f"m{i}"} for i in range(150)]}
        history = LuomiNestPlatformRouter._load_history_messages(conv, limit=50)
        assert len(history) == 50
        assert history[-1]["content"] == "m149"

        history_default = LuomiNestPlatformRouter._load_history_messages(conv)
        assert len(history_default) == 100

        history_small = LuomiNestPlatformRouter._load_history_messages(
            {"messages": [{"role": "user", "content": "hi"}]}, limit=100,
        )
        assert len(history_small) == 1


# ──────────────────────────────────────────────────────────────
# G0-D 分段发送服务
# ──────────────────────────────────────────────────────────────


class TestSegmenter:
    def test_split_short_reply(self):
        from app.runtime.platform.segmenter import SegmentParams, split_reply

        params = SegmentParams(max_chars=150)
        segs = split_reply("今天天气不错。我们去散步吧！好吗？", params)
        assert segs == ["今天天气不错", "我们去散步吧", "好吗"]

    def test_long_reply_sent_whole(self):
        """总长超 max_chars 直接整发（防刷屏碎条保护，AstrBot 同款）。"""
        from app.runtime.platform.segmenter import SegmentParams, split_reply

        long_text = "这是一个很长的句子。" * 30
        assert split_reply(long_text, SegmentParams(max_chars=150)) == [long_text.strip()]

    def test_trailing_period_stripped_question_kept(self):
        from app.runtime.platform.segmenter import clean_segment

        assert clean_segment("好的。") == "好的"
        assert clean_segment("真的吗？") == "真的吗？"
        assert clean_segment("太棒了！") == "太棒了！"

    def test_empty_segments_dropped(self):
        from app.runtime.platform.segmenter import SegmentParams, split_reply

        assert split_reply("好的。。。", SegmentParams()) == ["好的"]

    def test_log_delay_grows_with_length(self):
        from app.runtime.platform.segmenter import SegmentParams, segment_delay

        params = SegmentParams(log_base=2.6, delay_mode="log")
        short = segment_delay("好", params)
        longer = segment_delay("这句话稍微长一些", params)
        assert 0.5 <= short <= longer
        assert longer <= 8.0

    def test_random_delay_in_range(self):
        from app.runtime.platform.segmenter import SegmentParams, segment_delay

        params = SegmentParams(delay_mode="random", delay_min=1.5, delay_max=3.5)
        for _ in range(20):
            assert 1.5 <= segment_delay("任意段", params) <= 3.5

    def test_think_delay_has_jitter(self):
        from app.runtime.platform.segmenter import SegmentParams, think_delay

        params = SegmentParams(think_base=1.2, think_jitter=2.0)
        values = {round(think_delay(params), 2) for _ in range(30)}
        assert all(1.2 <= v <= 3.2 for v in values)
        assert len(values) > 1  # 抖动生效

    def test_reply_plan_first_delay_is_think(self):
        from app.runtime.platform.segmenter import SegmentParams, segment_reply_plan

        params = SegmentParams(think_base=1.2, think_jitter=0.0)
        plan = segment_reply_plan("第一句。第二句！第三句？", params)
        assert [seg for seg, _ in plan] == ["第一句", "第二句", "第三句"]
        assert plan[0][1] == 1.2  # 思考延迟（jitter=0 时恰为 base）
        assert all(d > 0 for _, d in plan)

    def test_empty_text_no_plan(self):
        from app.runtime.platform.segmenter import segment_reply_plan

        assert segment_reply_plan("", None) == []


# ──────────────────────────────────────────────────────────────
# G0-F avatar_drive model_id 修复
# ──────────────────────────────────────────────────────────────


class TestAvatarDrivePacketModelId:
    def test_model_id_field_exists_and_defaults_empty(self):
        from app.schemas.avatar import AvatarDriveData, AvatarDrivePacket

        packet = AvatarDrivePacket(timestamp=1, data=AvatarDriveData(emotion="happy"))
        assert packet.model_id == ""

    def test_model_id_round_trips(self):
        """修复点：协议携带的 model_id 不再被丢弃（曾误用 emotion 值寻址）。"""
        from app.schemas.avatar import AvatarDriveData, AvatarDrivePacket

        packet = AvatarDrivePacket.model_validate({
            "type": "emotion_drive", "timestamp": 1,
            "model_id": "vrm_main", "data": {"emotion": "happy"},
        })
        assert packet.model_id == "vrm_main"
        assert packet.data.emotion == "happy"
