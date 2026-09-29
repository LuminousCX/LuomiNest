"""P0-5「非流式工具循环 + 小修集合」回归测试。

覆盖：
- registry.register 同名冲突默认拒绝、force=True 显式覆盖
- non_stream_generate 复用 _select_tools_for_turn + AgentRunner.run_non_stream：
  mock LLM 第一轮回 tool_call、第二轮回文本，断言工具被执行且最终文本正确
- LLMEmbeddingProvider 嵌入模型兜底解析（仅 openai 系默认 text-embedding-3-small、
  其余用 provider 已配置模型名、缺省 fail-fast、MEMORY_EMBED_MODEL 覆盖；
  embed() HTTP 请求 mock httpx）
- platform_bridge_tool tier 修正与 pyproject 死依赖守护
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.config import settings
from app.core.tools import tool_registry
from app.core.tools.registry import ToolBase, ToolRegistry, ToolResult
from app.engines.memory import vector_store as vector_store_module
from app.engines.memory.vector_store import LLMEmbeddingProvider
from app.runtime.provider.llm.types import LLMResponse
from app.services import chat_service as chat_service_module
from app.services.chat_service import ChatService


# ──────────────────────────────────────────────────────────────
# 工具替身
# ──────────────────────────────────────────────────────────────

def _make_tool(name: str) -> ToolBase:
    """构造最小可注册工具（tier=core 保证三级注入必进常驻层）。"""

    class _T(ToolBase):
        tier: str = "core"
        scope: str = "shared"

        @property
        def name(self) -> str:
            return name

        @property
        def description(self) -> str:
            return "P0-5 测试工具"

        @property
        def parameters(self) -> dict:
            return {"type": "object", "properties": {}}

        async def execute(self, arguments: dict) -> ToolResult:
            return ToolResult.ok("ok")

    return _T()


class _EchoTool(ToolBase):
    """回声工具：记录调用参数，供工具循环断言。"""

    tier: str = "core"
    scope: str = "shared"

    def __init__(self) -> None:
        self.calls: list[dict] = []

    @property
    def name(self) -> str:
        return "p05_echo_tool"

    @property
    def description(self) -> str:
        return "P0-5 测试回声工具：原样返回输入文本。当用户要求 echo 时使用。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "回声文本"}},
            "required": ["text"],
        }

    async def execute(self, arguments: dict) -> ToolResult:
        self.calls.append(dict(arguments))
        return ToolResult.ok(f"echo: {arguments.get('text', '')}")


# ──────────────────────────────────────────────────────────────
# ① registry.register 撞名防护
# ──────────────────────────────────────────────────────────────

def test_register_rejects_duplicate_by_default():
    reg = ToolRegistry()
    first = _make_tool("dup_tool")
    second = _make_tool("dup_tool")

    assert reg.register(first) is True
    # 默认拒绝覆盖同名工具
    assert reg.register(second) is False
    assert reg.get("dup_tool") is first
    # force=True 显式覆盖
    assert reg.register(second, force=True) is True
    assert reg.get("dup_tool") is second


def test_global_registry_register_new_tool_succeeds():
    tool = _make_tool("p05_registry_probe_tool")
    try:
        assert tool_registry.register(tool) is True
        assert tool_registry.get("p05_registry_probe_tool") is tool
    finally:
        tool_registry.unregister("p05_registry_probe_tool")


# ──────────────────────────────────────────────────────────────
# ② 非流式工具循环
# ──────────────────────────────────────────────────────────────

async def test_non_stream_generate_runs_tool_loop(monkeypatch):
    """mock LLM：第一轮回 tool_call、第二轮回文本；断言工具执行且最终文本正确。"""
    echo_tool = _EchoTool()
    assert tool_registry.register(echo_tool) is True
    try:
        # 钉住三级注入 auto 模式，隔离 .env / 环境变量差异
        monkeypatch.setattr(settings, "LLM_TOOL_INJECTION_MODE", "auto")
        context = MagicMock()
        context.get_user_query = MagicMock(return_value="请帮我 echo 一下")
        svc = ChatService(context=context, suggestions=MagicMock())

        llm_calls: list[dict] = []

        async def fake_chat(**kwargs):
            llm_calls.append({
                "tools": kwargs.get("tools"),
                "roles": [m.get("role") for m in kwargs.get("messages", [])],
            })
            if len(llm_calls) == 1:
                # 第一轮：必须携带工具 schema，并回 tool_call
                assert kwargs.get("tools"), "第一轮请求必须携带工具 schema"
                return LLMResponse(
                    content="",
                    tool_calls=[{
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "p05_echo_tool", "arguments": '{"text": "hi"}'},
                    }],
                    finish_reason="tool_calls",
                )
            # 第二轮：请求应携带上一轮的工具结果消息
            assert "tool" in llm_calls[-1]["roles"], "第二轮请求应携带工具结果消息"
            return LLMResponse(content="工具循环完成：echo hi", finish_reason="stop")
        monkeypatch.setattr(chat_service_module.llm_adapter, "chat", fake_chat)
        monkeypatch.setattr(
            chat_service_module.llm_adapter, "supports_tool_calls", lambda p, m: True,
        )

        # usage 记录由管线内 UsageTrackMiddleware 完成（单例，就地打桩防真实落库）
        from app.services import usage_tracker as usage_tracker_module

        record_usage = MagicMock()
        monkeypatch.setattr(usage_tracker_module.usage_tracker, "record_usage", record_usage)

        messages = [{"role": "user", "content": "请帮我 echo 一下"}]
        state = {"content": "", "reasoning": "", "aborted": False}
        await svc.non_stream_generate(
            state, messages, "openai", "gpt-test", conv_id="conv-p05",
        )

        # 工具确实被执行（一次，参数正确）
        assert echo_tool.calls == [{"text": "hi"}]
        # 两次 LLM 调用（工具循环回合并推进）
        assert len(llm_calls) == 2
        # 最终文本写入 state（照旧供落库）
        assert state["content"] == "工具循环完成：echo hi"
        assert state["aborted"] is False
        # 工具循环痕迹回填进消息列表：assistant(tool_calls) + tool 结果
        assert any(
            m.get("role") == "assistant" and m.get("tool_calls") for m in messages
        )
        assert any(
            m.get("role") == "tool" and "echo: hi" in (m.get("content") or "")
            for m in messages
        )
        # UsageTrackMiddleware（after_agent）记录一次 usage
        record_usage.assert_called_once()
    finally:
        tool_registry.unregister("p05_echo_tool")


# ──────────────────────────────────────────────────────────────
# ③ embed 兜底解析（LLMEmbeddingProvider）
# ──────────────────────────────────────────────────────────────

def test_embed_openai_provider_defaults_to_official_model():
    provider = SimpleNamespace(
        provider_name="openai", base_url="https://api.openai.com/v1",
        default_model="gpt-4o-mini", api_key="k",
    )
    ep = LLMEmbeddingProvider(provider)
    assert ep._model == "text-embedding-3-small"
    assert ep.dim == 1536


def test_embed_non_openai_uses_configured_model():
    """非 openai 系不再静默发 text-embedding-3-small，而用其已配置模型名。"""
    provider = SimpleNamespace(
        provider_name="ollama", base_url="http://127.0.0.1:11434/v1",
        default_model="qwen2.5:7b", api_key="",
    )
    ep = LLMEmbeddingProvider(provider)
    assert ep._model == "qwen2.5:7b"


def test_embed_embed_named_model_kept_for_any_vendor():
    provider = SimpleNamespace(
        provider_name="siliconflow", base_url="https://api.siliconflow.cn/v1",
        default_model="BAAI/bge-m3", api_key="",
    )
    ep = LLMEmbeddingProvider(provider)
    assert ep._model == "BAAI/bge-m3"
    # 未知模型维度兜底常量不变（换模型需重嵌入，见类 docstring）
    assert ep.dim == 1536


def test_embed_missing_model_fails_fast():
    provider = SimpleNamespace(
        provider_name="custom", base_url="http://localhost:9999",
        default_model="", api_key="",
    )
    with pytest.raises(ValueError):
        LLMEmbeddingProvider(provider)


def test_embed_env_override_and_explicit_param_priority(monkeypatch):
    monkeypatch.setattr(settings, "MEMORY_EMBED_MODEL", "env-embed-model")
    provider = SimpleNamespace(
        provider_name="custom", base_url="http://localhost:9999",
        default_model="", api_key="",
    )
    # env 覆盖缺省解析
    ep = LLMEmbeddingProvider(provider)
    assert ep._model == "env-embed-model"
    # 显式参数优先于 env
    ep2 = LLMEmbeddingProvider(provider, model="explicit-model")
    assert ep2._model == "explicit-model"


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]}


class _FakeAsyncClient:
    last_url: str = ""
    last_payload: dict = {}

    def __init__(self, **kwargs) -> None:
        pass

    async def post(self, url, headers=None, json=None):
        _FakeAsyncClient.last_url = url
        _FakeAsyncClient.last_payload = json or {}
        return _FakeResponse()


async def test_embed_posts_resolved_model(monkeypatch):
    """embed() HTTP 请求（mock httpx）：请求 URL 与模型名按解析结果发出。"""
    monkeypatch.setattr(vector_store_module.httpx, "AsyncClient", _FakeAsyncClient)
    provider = SimpleNamespace(
        provider_name="ollama", base_url="http://127.0.0.1:11434/v1",
        default_model="qwen2.5:7b", api_key="",
    )
    ep = LLMEmbeddingProvider(provider)

    vecs = await ep.embed(["a", "b"])
    assert vecs == [[0.1, 0.2], [0.3, 0.4]]
    assert _FakeAsyncClient.last_url == "http://127.0.0.1:11434/v1/embeddings"
    assert _FakeAsyncClient.last_payload["model"] == "qwen2.5:7b"
    assert _FakeAsyncClient.last_payload["input"] == ["a", "b"]


# ──────────────────────────────────────────────────────────────
# 附：tier 修正与 pyproject 死依赖守护
# ──────────────────────────────────────────────────────────────

def test_platform_bridge_tool_tier_is_domain():
    from app.core.tools.builtin.platform_bridge_tool import PlatformInvokeTool

    assert PlatformInvokeTool().tier == "domain"


def test_pyproject_has_no_openai_anthropic_dependency():
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    assert "openai>=" not in text
    assert "anthropic>=" not in text
