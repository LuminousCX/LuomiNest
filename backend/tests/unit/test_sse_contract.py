"""SSE 事件契约回归测试（链路审查 P1-2 / P2-1 / P1-5 修复伴随测试）。

覆盖：
- ChatStreamChunk wire format：单一 "data: " 行（无 event:/id: 字段），
  notice / usage / context_tokens 字段按契约出现在对应 chunk 上
- AgentRunner usage 累加：多轮 LLM 调用的 usage 按次累加而非覆盖（P2-1）
- ChatService.stream_response done chunk：回填 ctx.state 的 usage（前端
  lastUsage/token 统计的数据源）与 context_tokens 估算双口径
- notice 头部事件：模型降级通知以首个空 content chunk 带出（P1-2）
"""

import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.agents.middleware.base import AgentContext
from app.core.agents.middleware.runner import AgentRunner
from app.core.utils import sse_data
from app.runtime.provider.llm.types import LLMResponse, StreamEvent
from app.schemas.chat import ChatStreamChunk
from app.services import chat_service as chat_service_module
from app.services.chat_service import ChatService


# ──────────────────────────────────────────────────────────────
# 工具：SSE wire format 解析
# ──────────────────────────────────────────────────────────────


def _parse_sse(sse_str: str) -> dict:
    """断言单条 SSE 数据行的 wire format 并解析 payload。

    契约（链路审查 §1.1-h）：仅 "data: " 单字段，无 event:/id: 行。
    """
    assert sse_str.startswith("data: "), f"expect data: prefix, got: {sse_str!r}"
    assert sse_str.endswith("\n\n"), f"expect blank-line terminated, got: {sse_str!r}"
    assert "event:" not in sse_str, "SSE 契约为单一 data 行，不得引入 event: 字段"
    return json.loads(sse_str[len("data: "):])


# ──────────────────────────────────────────────────────────────
# 1. ChatStreamChunk schema 序列化契约
# ──────────────────────────────────────────────────────────────


def test_notice_chunk_wire_format():
    """notice 事件：头部空 content chunk 携带 notice 字段（P1-2 前端映射的数据源）。"""
    line = sse_data(ChatStreamChunk(
        id="chat-1", content="", model="m", provider="p",
        notice="推理模型不可用，已退化为主模型",
    ))
    payload = _parse_sse(line)
    assert payload["notice"] == "推理模型不可用，已退化为主模型"
    assert payload["content"] == ""
    assert payload["done"] is False


def test_done_chunk_usage_and_context_tokens_wire_format():
    """done 事件：usage（真实用量，snake_case）与 context_tokens（估算）双口径分名。"""
    line = sse_data(ChatStreamChunk(
        id="chat-1", content="", model="m", provider="p",
        done=True,
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        context_tokens=123,
        context_max_tokens=1000,
    ))
    payload = _parse_sse(line)
    assert payload["done"] is True
    assert payload["usage"] == {
        "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15,
    }
    assert payload["context_tokens"] == 123
    assert payload["context_max_tokens"] == 1000


def test_done_chunk_without_usage_serializes_null():
    """provider 未上报 usage 时字段序列化为 null（前端按缺失处理，不报错）。"""
    line = sse_data(ChatStreamChunk(id="chat-1", model="m", provider="p", done=True))
    payload = _parse_sse(line)
    assert payload["usage"] is None


# ──────────────────────────────────────────────────────────────
# 2. AgentRunner usage 累加（P2-1：覆盖 → 累加）
# ──────────────────────────────────────────────────────────────


def _make_runner() -> AgentRunner:
    return AgentRunner(pipeline=MagicMock(), execute_fn=MagicMock())


def test_runner_stream_usage_accumulates_across_llm_calls():
    """多轮工具调用每轮各上报一次 usage，累加而非覆盖。"""
    runner = _make_runner()
    ctx = AgentContext(messages=[], state={})

    assert runner._process_stream_event(ctx, StreamEvent("usage", {
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    })) is None
    assert runner._process_stream_event(ctx, StreamEvent("usage", {
        "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
    })) is None

    assert ctx.state["usage"] == {
        "prompt_tokens": 17, "completion_tokens": 8, "total_tokens": 25,
    }


def test_runner_stream_usage_missing_keys_treated_as_zero():
    """单次调用缺某键时按 0 处理，不丢已有累计值。"""
    runner = _make_runner()
    ctx = AgentContext(messages=[], state={})
    runner._process_stream_event(ctx, StreamEvent("usage", {
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }))
    runner._process_stream_event(ctx, StreamEvent("usage", {
        "usage": {"completion_tokens": 4},
    }))
    assert ctx.state["usage"] == {
        "prompt_tokens": 10, "completion_tokens": 9, "total_tokens": 15,
    }


def test_runner_stream_usage_empty_event_is_noop():
    runner = _make_runner()
    ctx = AgentContext(messages=[], state={})
    runner._process_stream_event(ctx, StreamEvent("usage", {"usage": None}))
    runner._process_stream_event(ctx, StreamEvent("usage", {}))
    assert "usage" not in ctx.state


def test_runner_non_stream_usage_accumulates():
    """非流式路径同样累加（run_non_stream 每轮 LLMResponse.usage）。"""
    runner = _make_runner()
    ctx = AgentContext(messages=[], state={})
    runner._process_response(ctx, LLMResponse(
        content="a", usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    ))
    runner._process_response(ctx, LLMResponse(
        content="b", usage={"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
    ))
    assert ctx.state["usage"] == {
        "prompt_tokens": 17, "completion_tokens": 8, "total_tokens": 25,
    }


# ──────────────────────────────────────────────────────────────
# 3. ChatService.stream_response 事件序列契约
# ──────────────────────────────────────────────────────────────


class _FakeConversationStore:
    """进程内假 store：接口对齐 chat_service 用到的 conversation_store 子集。"""

    def __init__(self):
        self.appended: list[dict] = []
        self.set_calls: list[tuple[str, dict]] = []

    async def append_message_async(self, conv_id: str, message: dict) -> bool:
        self.appended.append(message)
        return True

    async def update_meta_async(self, conv_id: str, meta: dict) -> bool:
        return True

    async def set_async(self, conv_id: str, conv: dict) -> bool:
        self.set_calls.append((conv_id, conv))
        return True


class _FakeRunner:
    """AgentRunner 替身：按预置脚本回填 ctx.state 并 yield 预置 SSE。"""

    def __init__(self, script: list[tuple[dict, str | None]]):
        self._script = script

    async def run_stream(self, ctx: AgentContext, llm_call_fn) -> None:
        for state_patch, sse in self._script:
            ctx.state.update(state_patch)
            if sse:
                yield sse


@pytest.fixture
def chat_svc():
    context = MagicMock()
    return ChatService(context=context, suggestions=MagicMock())


def _stream_response_chunks(
    monkeypatch, chat_svc: ChatService, notice: str = "",
    final_state: dict | None = None,
) -> list[dict]:
    """跑通 stream_response 生成器并返回解析后的 chunk 列表。"""
    final_state = final_state if final_state is not None else {
        "content": "你好呀",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }

    monkeypatch.setattr(chat_service_module, "sse_response", lambda gen, **kw: gen)
    monkeypatch.setattr(chat_service_module, "_select_tools_for_turn", lambda *a, **k: (None, None))

    ctx_mgr = MagicMock()
    ctx_mgr.token_counter.count_tokens.return_value = 123
    ctx_mgr.max_context_tokens = 1000
    monkeypatch.setattr(chat_service_module, "get_context_manager", lambda *a, **k: ctx_mgr)

    store = _FakeConversationStore()
    monkeypatch.setattr(chat_service_module, "conversation_store", store)

    monkeypatch.setattr(
        chat_service_module.tool_orchestrator, "create_runner",
        lambda cfg: _FakeRunner([(final_state, None)]),
    )

    # 后台任务（推荐问题/记忆蒸馏）不在本测试范围，直接关闭协程防告警
    def _noop_spawn(coro):
        coro.close()
        return MagicMock()

    monkeypatch.setattr(chat_svc, "_spawn_background_task", _noop_spawn)

    conv = {"id": "conv-1", "title": "T", "messages": [{"role": "user", "content": "你好"}]}
    request = SimpleNamespace(chat_mode="normal", temperature=None, max_tokens=None, top_p=None)

    async def _collect():
        gen = await chat_svc.stream_response(
            conv_id="conv-1", conv=conv, request=request,
            all_messages=list(conv["messages"]),
            provider="openai", model="gpt-test", agent_id=None,
            state={}, start_time=time.time(), versions=None, notice=notice,
        )
        return [_parse_sse(sse_str) async for sse_str in gen]

    return asyncio.run(_collect())


def test_stream_response_notice_first_then_done_with_usage(monkeypatch, chat_svc):
    """事件序列契约：[notice?] → ... → done chunk（context_tokens + usage）。"""
    chunks = _stream_response_chunks(
        monkeypatch, chat_svc,
        notice="推理模型不可用，已退化为主模型",
    )

    # notice 为首个事件（P1-2：前端 apiStream 依赖此映射展示降级 toast）
    assert chunks[0]["notice"] == "推理模型不可用，已退化为主模型"
    assert chunks[0]["content"] == ""
    assert chunks[0]["done"] is False

    # done 为最后一个事件，携带双口径 token 统计
    done = chunks[-1]
    assert done["done"] is True
    assert done["usage"] == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    assert done["context_tokens"] == 123
    assert done["context_max_tokens"] == 1000

    # 中间事件序列：runner 内容原样透传，done 只出现一次且在末尾
    assert [c["done"] for c in chunks] == [False, True]
    # assistant 消息照常落库（usage 同步进 state 不影响持久化主流程）
    assert len(chat_service_module.conversation_store.appended) == 1
    assert chat_service_module.conversation_store.appended[0]["role"] == "assistant"


def test_stream_response_done_chunk_usage_null_without_state_usage(monkeypatch, chat_svc):
    """runner 未上报 usage（如 provider 不返回）时 done chunk 的 usage 为 null。"""
    chunks = _stream_response_chunks(monkeypatch, chat_svc, final_state={"content": "hi"})
    done = chunks[-1]
    assert done["done"] is True
    assert done["usage"] is None


def test_stream_response_no_notice_chunk_when_notice_empty(monkeypatch, chat_svc):
    """无降级通知时不发 notice 头部事件（后端按 notice 真值门控）。"""
    chunks = _stream_response_chunks(monkeypatch, chat_svc, notice="")
    assert all(c.get("notice") is None for c in chunks)
    assert chunks[-1]["done"] is True
