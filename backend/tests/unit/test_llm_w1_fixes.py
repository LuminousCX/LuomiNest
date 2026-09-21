"""W1 大模型对接修复的单元测试（2026-09-21 修改书 W1）。

覆盖：
1. reasoning_effort 打通：OpenAI 风格 effort / Qwen3 enable_thinking / 未知厂商不下发
2. Anthropic extended thinking：effort → budget 映射、约束（temperature=1、去 top_p、
   max_tokens > budget）、工具历史时安全跳过
3. 流式 fallback：首块前失败降级、已产出内容后失败原样抛出
4. 视觉门控与截图去重（runner）
"""
import pytest

from app.runtime.provider.llm.adapters.chat_completions import OpenAICompatibleProvider
from app.runtime.provider.llm.adapters.anthropic_messages import AnthropicMessagesProvider
from app.runtime.provider.llm.types import LLMRequest


def _req(extra=None, messages=None):
    return LLMRequest(
        messages=messages or [{"role": "user", "content": "你好"}],
        extra=extra or {},
    )


# ── 1. reasoning_effort（OpenAI 兼容协议）────────────────────────────────────

class TestChatCompletionsEffort:
    def test_openai_style_effort(self):
        p = OpenAICompatibleProvider(
            api_key="k", base_url="https://api.openai.com/v1",
            default_model="gpt-5", provider_name="openai",
        )
        payload = p._build_payload(_req({"reasoning_effort": "high"}))
        assert payload["reasoning_effort"] == "high"

    def test_dashscope_style_effort(self):
        p = OpenAICompatibleProvider(
            api_key="k", base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            default_model="qwen3-max", provider_name="dashscope",
        )
        payload = p._build_payload(_req({"reasoning_effort": "high"}))
        assert payload["enable_thinking"] is True
        assert payload["thinking_budget"] == 20480
        assert "reasoning_effort" not in payload

    def test_unknown_vendor_skips_effort(self):
        # moonshot 未声明 supports_thinking：不下发任何思考参数，避免 400
        p = OpenAICompatibleProvider(
            api_key="k", base_url="https://api.moonshot.cn/v1",
            default_model="kimi-k2", provider_name="moonshot",
        )
        payload = p._build_payload(_req({"reasoning_effort": "high"}))
        assert "reasoning_effort" not in payload
        assert "enable_thinking" not in payload

    def test_no_effort_no_thinking_params(self):
        p = OpenAICompatibleProvider(
            api_key="k", base_url="https://api.openai.com/v1",
            default_model="gpt-4o-mini", provider_name="openai",
        )
        payload = p._build_payload(_req())
        assert "reasoning_effort" not in payload


# ── 2. Anthropic extended thinking ──────────────────────────────────────────

class TestAnthropicThinking:
    def _provider(self) -> AnthropicMessagesProvider:
        return AnthropicMessagesProvider(
            api_key="k", base_url="https://api.anthropic.com/v1",
            default_model="claude-sonnet-4-20250514", provider_name="anthropic",
        )

    def test_effort_maps_to_thinking(self):
        p = self._provider()
        payload = p._build_payload(_req({"reasoning_effort": "high"}), stream=False)
        assert payload["thinking"] == {"type": "enabled", "budget_tokens": 16384}
        assert payload["temperature"] == 1.0
        assert "top_p" not in payload
        # max_tokens 必须大于 budget_tokens
        assert payload["max_tokens"] > 16384

    def test_numeric_effort_passthrough(self):
        p = self._provider()
        payload = p._build_payload(_req({"reasoning_effort": "2048"}), stream=False)
        assert payload["thinking"]["budget_tokens"] == 2048

    def test_tool_history_skips_thinking(self):
        # 工具循环要求回传 thinking 块，当前管道不保留 → 有工具历史时安全跳过
        p = self._provider()
        messages = [
            {"role": "user", "content": "查天气"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "t1", "type": "function",
                 "function": {"name": "query_weather", "arguments": "{}"}}
            ]},
            {"role": "tool", "tool_call_id": "t1", "name": "query_weather", "content": "晴"},
        ]
        payload = p._build_payload(_req({"reasoning_effort": "high"}, messages), stream=False)
        assert "thinking" not in payload

    def test_no_effort_no_thinking(self):
        p = self._provider()
        payload = p._build_payload(_req(), stream=False)
        assert "thinking" not in payload

    def test_disable_reasoning_flag_respected(self):
        p = self._provider()
        payload = p._build_payload(
            _req({"reasoning_effort": "high", "enable_reasoning": False}), stream=False,
        )
        assert "thinking" not in payload


# ── 3. 流式 fallback ────────────────────────────────────────────────────────

class _FakeStreamProvider:
    """最小 provider 桩：chat_stream 可配置为立即失败/产出后失败/正常。"""

    def __init__(self, name: str, chunks=None, fail_immediately=False, fail_after_first=False):
        self.provider_name = name
        self.default_model = "fake-model"
        self._chunks = chunks or []
        self._fail_immediately = fail_immediately
        self._fail_after_first = fail_after_first

    async def chat_stream(self, request):
        if self._fail_immediately:
            raise RuntimeError(f"{self.provider_name} boom")
        first = True
        for chunk in self._chunks:
            if self._fail_after_first and not first:
                raise RuntimeError(f"{self.provider_name} mid-stream boom")
            first = False
            yield chunk
        if self._fail_after_first:
            raise RuntimeError(f"{self.provider_name} mid-stream boom")


@pytest.mark.asyncio
async def test_stream_fallback_on_first_chunk_failure():
    from app.runtime.provider.llm.adapter import LLMAdapter

    adapter = LLMAdapter()
    adapter._loaded = True
    ok = _FakeStreamProvider("backup", chunks=[{"type": "content"}, {"type": "done"}])
    bad = _FakeStreamProvider("primary", fail_immediately=True)
    adapter.providers = {"primary": bad, "backup": ok}
    adapter.default_provider = "primary"

    chunks = []
    async for chunk in adapter.chat_stream(messages=[{"role": "user", "content": "hi"}], model="fake-model"):
        chunks.append(chunk)
    assert len(chunks) == 2
    assert chunks[0] == {"type": "content"}


@pytest.mark.asyncio
async def test_stream_midstream_failure_raises():
    from app.runtime.provider.llm.adapter import LLMAdapter

    adapter = LLMAdapter()
    adapter._loaded = True
    flaky = _FakeStreamProvider("primary", chunks=[{"type": "content"}], fail_after_first=True)
    adapter.providers = {"primary": flaky}
    adapter.default_provider = "primary"

    received = []
    with pytest.raises(RuntimeError):
        async for chunk in adapter.chat_stream(messages=[{"role": "user", "content": "hi"}], model="fake-model"):
            received.append(chunk)
    assert len(received) == 1  # 已产出的内容正常到达调用方，随后抛错


@pytest.mark.asyncio
async def test_stream_fallback_all_fail_raises_provider_error():
    from app.runtime.provider.llm.adapter import LLMAdapter
    from app.core.exceptions import ProviderError

    adapter = LLMAdapter()
    adapter._loaded = True
    adapter.providers = {"primary": _FakeStreamProvider("primary", fail_immediately=True)}
    adapter.default_provider = "primary"

    with pytest.raises(ProviderError):
        async for _ in adapter.chat_stream(messages=[{"role": "user", "content": "hi"}], model="fake-model"):
            pass


# ── 4. 视觉门控与截图去重 ────────────────────────────────────────────────────

class TestVisionFeedback:
    def _ctx(self, extra=None, state=None):
        from app.core.agents.middleware.base import AgentContext
        return AgentContext(messages=[], extra=extra or {}, state=state or {})

    def test_supports_vision_unknown_defaults_false(self, monkeypatch):
        # 真正的"未知"路径是能力查询异常（默认 provider 解析失败等）→ 必须 False，
        # 向纯文本模型注入 image_url 会被上游 400 拒绝
        from app.core.agents.middleware.runner import AgentRunner
        from app.runtime.provider.llm.adapter import llm_adapter

        def _boom(*args, **kwargs):
            raise RuntimeError("caps unavailable")

        monkeypatch.setattr(llm_adapter, "get_capabilities", _boom)
        runner = AgentRunner.__new__(AgentRunner)
        ctx = self._ctx(state={})
        assert runner._supports_vision(ctx) is False

    def test_supports_vision_falls_back_to_default_provider_caps(self):
        # state 缺 provider/model 时回退默认 provider 能力声明（openai 默认支持视觉）
        from app.core.agents.middleware.runner import AgentRunner
        runner = AgentRunner.__new__(AgentRunner)
        ctx = self._ctx(state={})
        assert runner._supports_vision(ctx) is True

    def test_supports_vision_explicit_override(self):
        from app.core.agents.middleware.runner import AgentRunner
        runner = AgentRunner.__new__(AgentRunner)
        ctx = self._ctx(extra={"supports_vision": True})
        assert runner._supports_vision(ctx) is True

    def test_vision_feedback_dedup(self):
        from app.core.agents.middleware.runner import AgentRunner

        messages = [{"role": "user", "content": "你好"}]
        AgentRunner._append_vision_feedback(messages, "data:image/png;base64,AAA")
        assert len(messages) == 2
        # 第二张截图应替换而非追加
        AgentRunner._append_vision_feedback(messages, "data:image/png;base64,BBB")
        assert len(messages) == 2
        content = messages[-1]["content"]
        assert content[1]["image_url"]["url"] == "data:image/png;base64,BBB"
