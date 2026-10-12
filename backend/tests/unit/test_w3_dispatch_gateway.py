"""dispatch 派发网关 + 权限三级单测（辰汐生态打通 W3，分册 10 §18.3）。

覆盖：
- 第二关启发式：短 task / 无工具动词无检索意图 → 丢弃；正常 task 放行；
  阈值/动词表为消费端配置项（settings 可调）
- 第三关防环：task 指纹判重（同轮重复丢弃）+ 单轮派发深度上限（≤10 可配）
- start/done/error 事件序列：mock 慢脑（detected 永不下发；游标防重复消费；
  无慢脑 → error 不抛异常；异常 → error）
- 慢脑解析顺序：model_config.slow_brain → reasoner 槽 → 云端默认 → None
- 快脑零原生工具（D3）：ToolFilter 注入面整体清空 + <tool_index> 剥除
- 权限三级：内置 T1 清单判级、只读 T0、插件 manifest 归级、trusted_mode 总开关
- 派发中间件挂载组合：仅 chat+流式挂载，位置在 SSEEmit 之前
"""

import asyncio
import json
from typing import Any

import pytest

from app.core.agents.middleware.base import AgentContext
from app.core.tags.definitions import (
    TASK_DISPATCH_CONSUMED_KEY,
    TASK_DISPATCH_DEPTH_KEY,
    TASK_DISPATCH_DETECTED_KEY,
    TASK_DISPATCH_FINGERPRINTS_KEY,
    TASK_DISPATCH_MAX_DEPTH,
    TASK_DISPATCH_STATS_KEY,
)

# ──────────────────────────────────────────────────────────────
# 工具
# ──────────────────────────────────────────────────────────────


class _SseCollector:
    """收集 ctx.sse_emitter 发出的 SSE 字符串并解析为 dict。"""

    def __init__(self) -> None:
        self.raw: list[str] = []

    async def __call__(self, sse_str: str) -> None:
        self.raw.append(sse_str)

    @property
    def chunks(self) -> list[dict[str, Any]]:
        return [json.loads(s.removeprefix("data: ").strip()) for s in self.raw]

    @property
    def dispatches(self) -> list[dict[str, Any]]:
        return [c["task_dispatch"] for c in self.chunks if c.get("task_dispatch")]


def _make_ctx(**extra) -> AgentContext:
    return AgentContext(
        messages=[{"role": "user", "content": "帮个忙"}],
        state={"chat_id": "c1", "provider": "prov", "model": "model"},
        extra={"scene": "chat", "is_stream": True, **extra},
    )


def _ctx_with(collector: _SseCollector, **extra) -> AgentContext:
    """带 SSE 收集器的执行上下文（模拟 runner 的 buffer emitter）。"""
    ctx = _make_ctx(**extra)
    ctx.sse_emitter = collector
    return ctx


def _detected(task: str) -> list[dict[str, Any]]:
    return [{"task": task, "phase": "detected", "task_id": None, "summary": None}]


@pytest.fixture()
def collector():
    return _SseCollector()


# ──────────────────────────────────────────────────────────────
# 1. 第二关：网关轻量检测
# ──────────────────────────────────────────────────────────────


class TestHeuristicFilter:
    def test_short_task_dropped(self):
        from app.core.agents.middleware.dispatch import heuristic_filter

        assert heuristic_filter("查天气") == "short"  # 去空白 3 字符 < 6
        assert heuristic_filter("   ") == "short"
        assert heuristic_filter("") == "short"

    def test_no_intent_task_dropped(self):
        from app.core.agents.middleware.dispatch import heuristic_filter

        # 长度足够但既无工具动词也无检索意图特征（闲聊/创作类）
        assert heuristic_filter("给我讲个笑话吧好不好呀") == "intent"
        assert heuristic_filter("陪我聊聊天说说话") == "intent"

    def test_verb_task_passes(self):
        from app.core.agents.middleware.dispatch import heuristic_filter

        assert heuristic_filter("帮我查一下北京明天的天气并总结") is None
        assert heuristic_filter("搜索一下最新的新闻") is None
        assert heuristic_filter("重启一下路由器") is None

    def test_intent_marker_passes_without_verb(self):
        from app.core.agents.middleware.dispatch import heuristic_filter

        assert heuristic_filter("明天会下雨吗出门要带伞吗") is None  # "明天" 特征

    def test_threshold_is_configurable(self, monkeypatch):
        from app.core.agents.middleware.dispatch import heuristic_filter
        from app.core.config import settings

        monkeypatch.setattr(settings, "DISPATCH_TASK_MIN_CHARS", 10)
        assert heuristic_filter("查一下天气情况") == "short"  # 6 字符 < 10
        monkeypatch.setattr(settings, "DISPATCH_TASK_MIN_CHARS", 6)
        assert heuristic_filter("查一下天气情况") is None

    def test_verb_table_is_configurable(self, monkeypatch):
        from app.core.agents.middleware.dispatch import heuristic_filter
        from app.core.config import settings

        monkeypatch.setattr(settings, "DISPATCH_TOOL_VERBS", "飞行")
        assert heuristic_filter("让无人机飞行一圈再回来") is None
        assert heuristic_filter("陪我聊聊天说说话") == "intent"  # 无自定义动词、无意图特征

    def test_short_and_intent_dropped_no_events(self, collector):
        """第二关丢弃：不发事件、计数留痕。"""
        from app.core.agents.middleware.dispatch import DispatchMiddleware

        mw = DispatchMiddleware()
        ctx = _make_ctx()
        ctx.state[TASK_DISPATCH_DETECTED_KEY] = _detected("查天气") + _detected("陪我聊聊天说说话")
        asyncio.run(mw.after_model(ctx, None))

        assert collector.dispatches == []
        assert ctx.state[TASK_DISPATCH_STATS_KEY]["detected"] == 2
        assert ctx.state[TASK_DISPATCH_STATS_KEY]["dropped_short"] == 1
        assert ctx.state[TASK_DISPATCH_STATS_KEY]["dropped_intent"] == 1
        assert ctx.state[TASK_DISPATCH_CONSUMED_KEY] == 2


# ──────────────────────────────────────────────────────────────
# 2. 第三关：防环兜底
# ──────────────────────────────────────────────────────────────


def _mock_slow_brain(monkeypatch, provider="prov", model="slow-m"):
    """把慢脑解析固定为可用（隔离真实 adapter/云端状态）。"""
    from app.core.agents.middleware import dispatch as dispatch_mod

    monkeypatch.setattr(
        dispatch_mod, "resolve_slow_brain",
        lambda: {"provider": provider, "model": model, "source": "slow_brain"},
    )


def _mock_execute(monkeypatch, result="任务完成：结果如下", capture=None):
    from app.core.agents.subagent_executor import subagent_executor

    async def fake_execute(**kwargs):
        if capture is not None:
            capture.append(kwargs)
        return result

    monkeypatch.setattr(subagent_executor, "execute", fake_execute)


class TestLoopGuard:
    def test_duplicate_fingerprint_dropped(self, monkeypatch, collector):
        from app.core.agents.middleware.dispatch import DispatchMiddleware

        _mock_slow_brain(monkeypatch)
        _mock_execute(monkeypatch)
        mw = DispatchMiddleware()
        ctx = _ctx_with(collector)
        task = "帮我查一下北京明天的天气并总结"
        ctx.state[TASK_DISPATCH_DETECTED_KEY] = _detected(task) + _detected(task)
        asyncio.run(mw.after_model(ctx, None))

        assert len(collector.dispatches) == 2  # start + done 各一次
        assert ctx.state[TASK_DISPATCH_STATS_KEY]["dropped_dup"] == 1
        assert ctx.state[TASK_DISPATCH_STATS_KEY]["executed"] == 1
        # 指纹集合中只留一条（第三关判重依据）
        assert len(ctx.state[TASK_DISPATCH_FINGERPRINTS_KEY]) == 1

    def test_depth_limit(self, monkeypatch, collector):
        from app.core.agents.middleware.dispatch import DispatchMiddleware

        _mock_slow_brain(monkeypatch)
        _mock_execute(monkeypatch)
        mw = DispatchMiddleware(max_depth=3)
        ctx = _ctx_with(collector)
        tasks = [f"帮我查一下第{i}号城市的天气预报情况" for i in range(5)]
        ctx.state[TASK_DISPATCH_DETECTED_KEY] = sum((_detected(t) for t in tasks), [])
        asyncio.run(mw.after_model(ctx, None))

        assert ctx.state[TASK_DISPATCH_DEPTH_KEY] == 3
        assert ctx.state[TASK_DISPATCH_STATS_KEY]["executed"] == 3
        assert ctx.state[TASK_DISPATCH_STATS_KEY]["dropped_limit"] == 2

    def test_default_max_depth_is_ten(self):
        from app.core.agents.middleware.dispatch import DispatchMiddleware

        assert DispatchMiddleware()._max_depth == TASK_DISPATCH_MAX_DEPTH == 10

    def test_fingerprint_normalized(self):
        from app.core.agents.middleware.dispatch import task_fingerprint

        assert task_fingerprint("查 一下 天气") == task_fingerprint("查一下天气")
        assert task_fingerprint("查天气A") != task_fingerprint("查天气B")


# ──────────────────────────────────────────────────────────────
# 3. start/done/error 事件序列（mock 慢脑）
# ──────────────────────────────────────────────────────────────


class TestEventSequence:
    def test_start_then_done(self, monkeypatch, collector):
        from app.core.agents.middleware.dispatch import DispatchMiddleware

        captured: list[dict] = []
        _mock_slow_brain(monkeypatch, provider="sp", model="sm")
        _mock_execute(monkeypatch, result="北京明天晴，气温 12 到 24 度。", capture=captured)
        mw = DispatchMiddleware()
        ctx = _ctx_with(collector)
        ctx.state[TASK_DISPATCH_DETECTED_KEY] = _detected("帮我查一下北京明天的天气并总结")
        asyncio.run(mw.after_model(ctx, None))

        evs = collector.dispatches
        assert [e["phase"] for e in evs] == ["start", "done"]
        assert evs[0]["task_id"] == evs[1]["task_id"]
        assert evs[0]["task_id"]  # 非 None/空
        assert evs[0]["task"] == evs[1]["task"] == "帮我查一下北京明天的天气并总结"
        assert "晴" in evs[1]["summary"]
        # detected 永不下发
        assert all(e["phase"] != "detected" for e in evs)
        # 慢脑 provider/model 透传给子 Agent 执行器（槽位不绑定模型）
        assert captured[0]["provider"] == "sp"
        assert captured[0]["model"] == "sm"

    def test_cursor_prevents_double_processing(self, monkeypatch, collector):
        from app.core.agents.middleware.dispatch import DispatchMiddleware

        _mock_slow_brain(monkeypatch)
        _mock_execute(monkeypatch)
        mw = DispatchMiddleware()
        ctx = _ctx_with(collector)
        ctx.state[TASK_DISPATCH_DETECTED_KEY] = _detected("帮我查一下北京明天的天气并总结")
        asyncio.run(mw.after_model(ctx, None))
        asyncio.run(mw.after_model(ctx, None))  # 第二轮无新增检测
        assert len(collector.dispatches) == 2  # 仍是 start + done
        # 追加新检测后仅处理新增
        ctx.state[TASK_DISPATCH_DETECTED_KEY].append(
            {"task": "帮我搜索一下最新的科技新闻", "phase": "detected", "task_id": None, "summary": None}
        )
        asyncio.run(mw.after_model(ctx, None))
        assert len(collector.dispatches) == 4

    def test_no_slow_brain_emits_error_not_raise(self, monkeypatch, collector):
        from app.core.agents.middleware import dispatch as dispatch_mod
        from app.core.agents.middleware.dispatch import DispatchMiddleware

        monkeypatch.setattr(dispatch_mod, "resolve_slow_brain", lambda: None)
        mw = DispatchMiddleware()
        ctx = _ctx_with(collector)
        ctx.state[TASK_DISPATCH_DETECTED_KEY] = _detected("帮我查一下北京明天的天气并总结")
        asyncio.run(mw.after_model(ctx, None))  # 不抛异常

        evs = collector.dispatches
        assert [e["phase"] for e in evs] == ["error"]
        assert "慢脑" in evs[0]["summary"]
        assert ctx.state[TASK_DISPATCH_STATS_KEY]["errors"] == 1

    def test_execution_failure_emits_error(self, monkeypatch, collector):
        from app.core.agents.middleware.dispatch import DispatchMiddleware

        _mock_slow_brain(monkeypatch)
        _mock_execute(monkeypatch, result=None)  # 慢脑无返回
        mw = DispatchMiddleware()
        ctx = _ctx_with(collector)
        ctx.state[TASK_DISPATCH_DETECTED_KEY] = _detected("帮我查一下北京明天的天气并总结")
        asyncio.run(mw.after_model(ctx, None))

        evs = collector.dispatches
        assert [e["phase"] for e in evs] == ["start", "error"]

    def test_non_chat_scene_skipped(self, monkeypatch, collector):
        from app.core.agents.middleware.dispatch import DispatchMiddleware

        _mock_slow_brain(monkeypatch)
        _mock_execute(monkeypatch)
        mw = DispatchMiddleware()
        ctx = _make_ctx(scene="subagent")
        ctx.state[TASK_DISPATCH_DETECTED_KEY] = _detected("帮我查一下北京明天的天气并总结")
        asyncio.run(mw.after_model(ctx, None))
        assert collector.dispatches == []

    def test_result_backfilled_to_conversation(self, monkeypatch, collector):
        """完整结果按 TaskResultDispatcher 惯例回填来源会话（assistant 消息）。"""
        from app.core.agents.middleware.dispatch import DispatchMiddleware

        _mock_slow_brain(monkeypatch)
        _mock_execute(monkeypatch, result="完整执行结果正文")

        appended: list[tuple[str, dict]] = []

        class _FakeStore:
            async def append_message_async(self, conv_id, message):
                appended.append((conv_id, message))
                return True

        import app.infrastructure.database.conversation_store as store_mod

        original = store_mod.conversation_store
        store_mod.conversation_store = _FakeStore()
        try:
            mw = DispatchMiddleware()
            ctx = _make_ctx(conv_id="conv-42")
            ctx.state[TASK_DISPATCH_DETECTED_KEY] = _detected("帮我查一下北京明天的天气并总结")
            asyncio.run(mw.after_model(ctx, None))
        finally:
            store_mod.conversation_store = original

        assert len(appended) == 1
        conv_id, message = appended[0]
        assert conv_id == "conv-42"
        assert message["role"] == "assistant"
        assert message["content"].startswith("[派发任务]《")
        assert "完整执行结果正文" in message["content"]
        assert message["task_dispatch"]["phase"] == "done"

    def test_backfill_skipped_without_conv_id(self, monkeypatch, collector):
        from app.core.agents.middleware.dispatch import DispatchMiddleware

        _mock_slow_brain(monkeypatch)
        _mock_execute(monkeypatch)
        mw = DispatchMiddleware()
        ctx = _ctx_with(collector, conv_id="")  # /chat/completions 等无会话来源
        ctx.state[TASK_DISPATCH_DETECTED_KEY] = _detected("帮我查一下北京明天的天气并总结")
        asyncio.run(mw.after_model(ctx, None))
        assert [e["phase"] for e in collector.dispatches] == ["start", "done"]  # 仅跳过回填


# ──────────────────────────────────────────────────────────────
# 4. 慢脑解析顺序（槽位不绑定模型）
# ──────────────────────────────────────────────────────────────


class _FakeProvider:
    def __init__(self, default_model="fallback-m") -> None:
        self.default_model = default_model


class TestResolveSlowBrain:
    def test_slow_brain_config_first(self, monkeypatch):
        from app.core.agents.middleware.dispatch import resolve_slow_brain
        from app.core.config import settings
        from app.runtime.provider.llm.adapter import llm_adapter

        monkeypatch.setattr(settings, "SLOW_BRAIN", "provX/modelY/subpath")
        monkeypatch.setattr(llm_adapter, "get_provider", lambda name=None: _FakeProvider())
        got = resolve_slow_brain()
        assert got == {"provider": "provX", "model": "modelY/subpath", "source": "slow_brain"}

    def test_slow_brain_without_slash_uses_default_provider(self, monkeypatch):
        from app.core.agents.middleware.dispatch import resolve_slow_brain
        from app.core.config import settings
        from app.runtime.provider.llm.adapter import llm_adapter

        monkeypatch.setattr(settings, "SLOW_BRAIN", "modelOnly")
        monkeypatch.setattr(llm_adapter, "get_provider", lambda name=None: _FakeProvider("dm"))
        monkeypatch.setattr(llm_adapter, "default_provider", "defaultProv", raising=False)
        got = resolve_slow_brain()
        assert got == {"provider": "defaultProv", "model": "modelOnly", "source": "slow_brain"}

    def test_falls_back_to_reasoner_slot(self, monkeypatch):
        from app.core.agents.middleware.dispatch import resolve_slow_brain
        from app.core.config import settings
        from app.runtime.provider.llm.adapter import llm_adapter

        monkeypatch.setattr(settings, "SLOW_BRAIN", "ghostProv/modelZ")

        def _get_provider(name=None):
            if name == "ghostProv":
                raise RuntimeError("not found")
            return _FakeProvider()

        monkeypatch.setattr(llm_adapter, "get_provider", _get_provider)
        monkeypatch.setattr(
            llm_adapter, "get_reasoner_provider",
            lambda: ("provR", "modelR", None, None, ""),
        )
        got = resolve_slow_brain()
        assert got == {"provider": "provR", "model": "modelR", "source": "reasoner"}

    def test_cloud_branch_via_real_resolver(self, monkeypatch):
        """SLOW_BRAIN 空 + reasoner 空 + 云路由激活 → source=cloud（provider/model 交给云路由）。"""
        from app.core.agents.middleware.dispatch import resolve_slow_brain
        from app.core.config import settings
        from app.runtime.provider.llm.adapter import llm_adapter
        from app.runtime.provider.llm.cloud_store import cloud_token_store

        monkeypatch.setattr(settings, "SLOW_BRAIN", "")
        monkeypatch.setattr(llm_adapter, "get_reasoner_provider", lambda: None)
        monkeypatch.setattr(
            cloud_token_store, "get",
            lambda: {"accessToken": "t", "cloudBaseUrl": "https://x", "routingMode": "all", "models": []},
        )
        monkeypatch.setattr(
            type(cloud_token_store), "configured",
            property(lambda self: True),
        )
        got = resolve_slow_brain()
        assert got == {"provider": None, "model": None, "source": "cloud"}

    def test_none_when_nothing_configured(self, monkeypatch):
        from app.core.agents.middleware.dispatch import resolve_slow_brain
        from app.core.config import settings
        from app.runtime.provider.llm.adapter import llm_adapter
        from app.runtime.provider.llm.cloud_store import cloud_token_store

        monkeypatch.setattr(settings, "SLOW_BRAIN", "")
        monkeypatch.setattr(llm_adapter, "get_reasoner_provider", lambda: None)
        monkeypatch.setattr(
            cloud_token_store, "get",
            lambda: {"accessToken": "", "cloudBaseUrl": "", "routingMode": "off", "models": []},
        )
        assert resolve_slow_brain() is None


# ──────────────────────────────────────────────────────────────
# 5. 快脑零原生工具（D3 口径）
# ──────────────────────────────────────────────────────────────


def _schema(name: str) -> dict[str, Any]:
    return {"type": "function", "function": {"name": name, "description": name, "parameters": {}}}


class TestFastBrainZeroTools:
    def test_before_agent_clears_tools_and_tool_index(self, monkeypatch):
        from app.core.agents.middleware.builtin import ToolFilterMiddleware
        from app.core.config import settings

        monkeypatch.setattr(settings, "FAST_BRAIN", "prov/fast-m")
        ctx = AgentContext(
            messages=[
                {"role": "system", "content": "人设<tool_index>\n- cli: 执行命令\n</tool_index>结尾"},
                {"role": "user", "content": "你好"},
            ],
            tools=[_schema("memory_search"), _schema("cli")],
            state={"provider": "prov", "model": "fast-m"},
        )
        ctx.state["dynamic_tool_schemas"] = [_schema("cli")]
        asyncio.run(ToolFilterMiddleware().before_agent(ctx))

        assert ctx.tools is None  # LLM 请求不带任何原生工具
        assert "dynamic_tool_schemas" not in ctx.state
        assert "<tool_index>" not in ctx.messages[0]["content"]
        assert "人设" in ctx.messages[0]["content"] and "结尾" in ctx.messages[0]["content"]

    def test_before_model_reclears_dynamic_additions(self, monkeypatch):
        from app.core.agents.middleware.builtin import ToolFilterMiddleware
        from app.core.config import settings

        monkeypatch.setattr(settings, "FAST_BRAIN", "prov/fast-m")
        ctx = AgentContext(
            messages=[], tools=None, state={"provider": "prov", "model": "fast-m"},
        )
        ctx.state["dynamic_tool_schemas"] = [_schema("tool_explore")]
        asyncio.run(ToolFilterMiddleware().before_model(ctx))
        assert ctx.tools is None

    def test_non_fast_brain_keeps_tools(self, monkeypatch):
        from app.core.agents.middleware.builtin import ToolFilterMiddleware
        from app.core.config import settings

        monkeypatch.setattr(settings, "FAST_BRAIN", "prov/fast-m")
        ctx = AgentContext(
            messages=[], tools=[_schema("memory_search")],
            state={"provider": "prov", "model": "other-m"},
        )
        asyncio.run(ToolFilterMiddleware().before_agent(ctx))
        assert ctx.tools == [_schema("memory_search")]

    def test_fast_brain_off_keeps_tools(self, monkeypatch):
        from app.core.agents.middleware.builtin import ToolFilterMiddleware
        from app.core.config import settings

        monkeypatch.setattr(settings, "FAST_BRAIN", "")
        ctx = AgentContext(
            messages=[], tools=[_schema("memory_search")],
            state={"provider": "prov", "model": "fast-m"},
        )
        asyncio.run(ToolFilterMiddleware().before_agent(ctx))
        assert ctx.tools == [_schema("memory_search")]


# ──────────────────────────────────────────────────────────────
# 6. 权限三级 T0/T1/T2
# ──────────────────────────────────────────────────────────────

# app_factory.py 注册的全部内置工具（33 个，含动态 a2a 前缀族）逐个归类
_T1_BUILTIN_EXPECTED = {
    "cli", "write_file", "create_scheduled_task", "delete_scheduled_task",
    "iot_send_command", "launch_application", "platform_invoke", "memory_forget",
}
_T0_BUILTIN_EXPECTED = {
    # 文件只读/列举/检索
    "read_file", "list_files", "search_files",
    # MCP
    "mcp_call", "list_mcp_servers",
    # 委派/集群/协作（子调用各自受闸门约束）
    "delegate_to_subagent", "agent_tool_call", "start_collaboration",
    # 定时任务只读
    "list_scheduled_tasks", "get_scheduled_task",
    # 浏览器只读
    "browser_visit", "browser_screenshot",
    # 记忆（读 + 非删除写）
    "memory_search", "memory_add", "memory_update", "memory_get_daily", "memory_pin",
    # 陪伴基础
    "get_current_time", "query_weather",
    # 探索发现
    "tool_explore", "skill_explore",
    # 文件名搜索 / 上下文压缩 / 传感只读
    "search_everything", "compress_context", "iot_get_sensor_data",
}


class TestPermissionTiers:
    def test_t1_builtin_list(self):
        from app.core.agents.middleware.permission import (
            GATED_TOOLS,
            T1_BUILTIN_TOOLS,
            resolve_tool_permission_tier,
        )

        assert T1_BUILTIN_TOOLS == _T1_BUILTIN_EXPECTED
        assert GATED_TOOLS is T1_BUILTIN_TOOLS  # 兼容别名
        for name in _T1_BUILTIN_EXPECTED:
            assert resolve_tool_permission_tier(name) == "t1", name

    def test_t0_builtin_classification(self):
        from app.core.agents.middleware.permission import resolve_tool_permission_tier

        assert len(_T0_BUILTIN_EXPECTED) + len(_T1_BUILTIN_EXPECTED) == 32
        for name in _T0_BUILTIN_EXPECTED:
            assert resolve_tool_permission_tier(name) == "t0", name
        # 动态注册的 A2A 工具（前缀族）按 T0（目标服务器由配置白名单约束）
        assert resolve_tool_permission_tier("a2a_tool_call_weather") == "t0"

    def _fake_plugin_registry(self, monkeypatch, permissions: list[str], tools: list[str]):
        from app.models.plugin import CxPluginManifest, CxPluginMetadata
        from app.runtime.plugin.cxplugin import registry as reg_mod

        class _Instance:
            def get_registered_tool_names(self):
                return tools

        meta = CxPluginMetadata(
            manifest=CxPluginManifest.from_dict({"id": "p1", "permissions": permissions}),
            module_path="m", plugin_dir="d",
        )

        class _FakeRegistry:
            def list_plugins(self, active_only=True):
                return [meta]

            def get_instance(self, plugin_id):
                return _Instance()

        monkeypatch.setattr(reg_mod, "luominest_plugin_registry", _FakeRegistry())
        return meta

    def test_plugin_tool_t1_by_manifest(self, monkeypatch):
        from app.core.agents.middleware.permission import resolve_tool_permission_tier

        self._fake_plugin_registry(monkeypatch, ["basic", "network"], ["plugin_fetch"])
        assert resolve_tool_permission_tier("plugin_fetch") == "t1"

        self._fake_plugin_registry(monkeypatch, ["system_command"], ["plugin_run"])
        assert resolve_tool_permission_tier("plugin_run") == "t1"

        self._fake_plugin_registry(monkeypatch, ["file_write"], ["plugin_save"])
        assert resolve_tool_permission_tier("plugin_save") == "t1"

    def test_plugin_tool_t0_when_readonly(self, monkeypatch):
        from app.core.agents.middleware.permission import resolve_tool_permission_tier

        self._fake_plugin_registry(
            monkeypatch, ["basic", "event_listen", "file_read", "tool_register"],
            ["plugin_lookup"],
        )
        assert resolve_tool_permission_tier("plugin_lookup") == "t0"

    def test_plugin_t1_permission_table(self):
        """判级映射表：写/网络/执行/库/管理 → T1；基础/监听/读/注册 → 不影响归级。"""
        from app.core.agents.middleware.permission import T1_PLUGIN_PERMISSIONS

        assert {
            "network", "file_write", "file_system", "system_command", "database", "admin_api",
        } == T1_PLUGIN_PERMISSIONS

    def test_unknown_tool_defaults_t0(self):
        from app.core.agents.middleware.permission import resolve_tool_permission_tier

        assert resolve_tool_permission_tier("mcp_call") == "t0"
        assert resolve_tool_permission_tier("totally_unknown") == "t0"


class TestTrustedMode:
    @staticmethod
    def _fresh_manager(monkeypatch):
        """干净确认管理器（替换模块全局，测试后自动恢复）。"""
        import app.core.agents.middleware.permission as gate_mod
        from app.security.sandbox.permission import AgentCommandPermissionManager

        mgr = AgentCommandPermissionManager()  # 默认 ask 模式
        monkeypatch.setattr(gate_mod, "agent_command_permissions", mgr)
        return mgr

    def test_trusted_mode_bypasses_t1_gate(self, monkeypatch):
        """T2 信任档：T1 高危工具免弹窗直接执行。"""
        from app.core.agents.middleware.permission import PermissionGateMiddleware
        from app.core.config import settings

        monkeypatch.setattr(settings, "PERMISSION_TRUSTED_MODE", True)
        assert self._fresh_manager(monkeypatch).needs_approval("conv-x") is True

        called = {"next": False}

        async def next_fn(_tc):
            called["next"] = True
            return {"role": "tool", "tool_call_id": "t1", "name": "cli", "content": "ok"}

        ctx = _make_ctx()
        emitted: list[str] = []

        async def emitter(sse):
            emitted.append(sse)

        ctx.sse_emitter = emitter
        tc = {"id": "t1", "type": "function", "function": {"name": "cli", "arguments": "{}"}}
        result = asyncio.run(PermissionGateMiddleware().wrap_tool_call(ctx, tc, next_fn))

        assert called["next"] is True
        assert result["content"] == "ok"
        assert emitted == []  # 未弹窗

    def test_t1_gate_without_trusted_mode_denies_non_stream(self, monkeypatch):
        """T1 确认档：非流式无法弹窗 → fail-closed 拒绝（既有交互不变）。"""
        from app.core.agents.middleware.permission import PermissionGateMiddleware
        from app.core.config import settings

        monkeypatch.setattr(settings, "PERMISSION_TRUSTED_MODE", False)
        assert self._fresh_manager(monkeypatch).needs_approval("conv-x") is True

        called = {"next": False}

        async def next_fn(_tc):
            called["next"] = True
            return {"role": "tool", "tool_call_id": "t1", "name": "cli", "content": "ok"}

        ctx = _make_ctx(is_stream=False)  # 无 sse_emitter
        tc = {"id": "t1", "type": "function", "function": {"name": "cli", "arguments": "{}"}}
        result = asyncio.run(PermissionGateMiddleware().wrap_tool_call(ctx, tc, next_fn))

        assert called["next"] is False
        assert "已取消" in result["content"]

    def test_t0_tool_passes_without_popup(self, monkeypatch):
        """T0 自动档：只读工具免确认直接执行（不受弹窗流程影响）。"""
        from app.core.agents.middleware.permission import PermissionGateMiddleware
        from app.core.config import settings

        monkeypatch.setattr(settings, "PERMISSION_TRUSTED_MODE", False)
        assert self._fresh_manager(monkeypatch).needs_approval("conv-x") is True

        called = {"next": False}

        async def next_fn(_tc):
            called["next"] = True
            return {"role": "tool", "tool_call_id": "t0", "name": "read_file", "content": "ok"}

        ctx = _make_ctx(is_stream=False)
        tc = {"id": "t0", "type": "function", "function": {"name": "read_file", "arguments": "{}"}}
        asyncio.run(PermissionGateMiddleware().wrap_tool_call(ctx, tc, next_fn))
        assert called["next"] is True

    def test_set_and_load_trusted_mode(self, monkeypatch):
        """trusted_mode 持久化往返（config_items 键 permission.trusted_mode）。"""
        import app.core.agents.middleware.permission as gate_mod
        from app.core.config import settings

        stored: dict[str, Any] = {}

        class _FakeConfigStore:
            async def get_async(self, key, default=None):
                return stored.get(key, default)

            async def set_async(self, key, value):
                stored[key] = value

        import app.infrastructure.database.config_store as store_mod

        monkeypatch.setattr(store_mod, "luominest_config_store", _FakeConfigStore())
        monkeypatch.setattr(settings, "PERMISSION_TRUSTED_MODE", False)

        asyncio.run(gate_mod.set_trusted_mode(True))
        assert settings.PERMISSION_TRUSTED_MODE is True
        assert stored[gate_mod.TRUSTED_MODE_CONFIG_KEY] is True

        settings.PERMISSION_TRUSTED_MODE = False
        asyncio.run(gate_mod.load_trusted_mode_from_db())
        assert settings.PERMISSION_TRUSTED_MODE is True  # 从持久化键恢复

    def test_trusted_mode_keeps_command_validator_blacklist(self, monkeypatch, tmp_path):
        """T2 信任档只旁路 PermissionGate 弹窗；CommandValidator 黑名单硬防线照常生效。

        信任档免确认放行的 cli 工具调用到达沙盒执行层时，命令本体（如 pkill）
        仍必须被黑名单拒绝——两道防线独立，信任档不触碰校验层。
        """
        from app.core.agents.middleware.permission import PermissionGateMiddleware
        from app.core.config import settings
        from app.security.sandbox.command_validator import CommandValidator
        from app.security.sandbox.exceptions import SandboxPermissionError

        monkeypatch.setattr(settings, "PERMISSION_TRUSTED_MODE", True)

        called = {"next": False}

        async def next_fn(_tc):
            called["next"] = True
            return {"role": "tool", "tool_call_id": "t1", "name": "cli", "content": "ok"}

        ctx = _make_ctx()
        tc = {
            "id": "t1",
            "type": "function",
            "function": {"name": "cli", "arguments": json.dumps({"command": "pkill notepad"})},
        }
        result = asyncio.run(PermissionGateMiddleware().wrap_tool_call(ctx, tc, next_fn))
        assert called["next"] is True  # 信任档：高危工具免弹窗直接放行到执行层
        assert result["content"] == "ok"

        # 同一条命令在沙盒校验层仍被黑名单拦截（信任档不影响 CommandValidator）。
        # 注意选 pkill：只命中 _DEFAULT_BLACKLIST_CMDS，不撞前置的危险命令正则
        validator = CommandValidator(workspace=tmp_path)
        with pytest.raises(SandboxPermissionError) as exc_info:
            validator.validate_command("pkill notepad")
        assert exc_info.value.operation == "command_blacklist"


class TestTrustedModeApi:
    """T2 信任档读写端点（W6 补 UI 入口：GET/PATCH /api/v1/chat/permission/trusted-mode）。"""

    @staticmethod
    def _fake_store(monkeypatch) -> dict[str, Any]:
        """dict 假持久化（替换单例，隔离会话级临时 DB，测试后自动恢复）。"""
        stored: dict[str, Any] = {}

        class _FakeConfigStore:
            async def get_async(self, key, default=None):
                return stored.get(key, default)

            async def set_async(self, key, value):
                stored[key] = value

        import app.infrastructure.database.config_store as store_mod

        monkeypatch.setattr(store_mod, "luominest_config_store", _FakeConfigStore())
        return stored

    def test_get_patch_roundtrip(self, monkeypatch):
        """默认 false → PATCH true（内存镜像 + persisted 实况）→ GET 回读 true。"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.v1.endpoints.chat import router as chat_router
        from app.core.config import settings

        self._fake_store(monkeypatch)
        monkeypatch.setattr(settings, "PERMISSION_TRUSTED_MODE", False)

        app = FastAPI()
        app.include_router(chat_router, prefix="/api/v1")
        client = TestClient(app)

        # 1) 默认关闭
        res = client.get("/api/v1/chat/permission/trusted-mode")
        assert res.status_code == 200
        assert res.json()["data"] == {"enabled": False}

        # 2) 开启：内存镜像先行生效，persisted 回读持久化实况
        res = client.patch("/api/v1/chat/permission/trusted-mode", json={"enabled": True})
        assert res.status_code == 200
        assert res.json()["data"] == {"enabled": True, "persisted": True}
        assert settings.PERMISSION_TRUSTED_MODE is True

        # 3) GET 回读开启态
        res = client.get("/api/v1/chat/permission/trusted-mode")
        assert res.json()["data"] == {"enabled": True}

        # 4) 关闭（恢复现场，避免泄漏到同会话其他测试）
        res = client.patch("/api/v1/chat/permission/trusted-mode", json={"enabled": False})
        assert res.status_code == 200
        assert settings.PERMISSION_TRUSTED_MODE is False


# ──────────────────────────────────────────────────────────────
# 7. 派发中间件挂载组合
# ──────────────────────────────────────────────────────────────


class TestPipelineWiring:
    def test_mounted_for_chat_stream(self):
        from app.core.agents.middleware.builtin import SSEEmitMiddleware
        from app.core.agents.middleware.dispatch import DispatchMiddleware
        from app.core.agents.middleware.permission import PermissionGateMiddleware
        from app.core.tools.orchestrator import ToolOrchestrator

        pipeline = ToolOrchestrator().build_default_pipeline({"scene": "chat", "is_stream": True})
        types = [type(m) for m in pipeline.middlewares]
        assert DispatchMiddleware in types
        # 位于 PermissionGate 之后（after_model 反序 → SSEEmit 的公告先于派发事件落 buffer）
        assert types.index(PermissionGateMiddleware) < types.index(DispatchMiddleware)
        assert types.index(DispatchMiddleware) < types.index(SSEEmitMiddleware)

    def test_not_mounted_for_non_stream(self):
        from app.core.agents.middleware.dispatch import DispatchMiddleware
        from app.core.tools.orchestrator import ToolOrchestrator

        pipeline = ToolOrchestrator().build_default_pipeline({"scene": "chat", "is_stream": False})
        assert DispatchMiddleware not in [type(m) for m in pipeline.middlewares]

    def test_not_mounted_for_subagent(self):
        from app.core.agents.middleware.dispatch import DispatchMiddleware
        from app.core.tools.orchestrator import ToolOrchestrator

        pipeline = ToolOrchestrator().build_default_pipeline({"scene": "subagent", "is_stream": True})
        assert DispatchMiddleware not in [type(m) for m in pipeline.middlewares]
