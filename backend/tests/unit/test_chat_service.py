"""chat_service 非流式路径回归测试（LLM/记忆/蒸馏全部 mock，不触碰真实库）。

覆盖：
- 非流式回合：响应返回时后台记忆管线已 spawn 但未阻塞（schedule_memory_update 尚未执行）
- 管线补跑：先记忆写入后蒸馏按序执行，任务完成后从 _background_tasks 清理（防 GC 引用管理）
- _spawn_background_task：任务完成后 done_callback 移除引用
- non_stream_generate：正常写入 content；LLM 异常时 aborted + 兜底文案不外抛
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import chat_service as chat_service_module
from app.services.chat_service import ChatService


@pytest.fixture
def chat_svc():
    """组装 ChatService：context / suggestions 用 mock 替身。"""
    context = MagicMock()
    context.get_user_query = MagicMock(return_value="你好")
    context.build_system_prompt = MagicMock(return_value="sys-prompt")
    context.build_user_selected_skills_prompt = MagicMock(return_value="")
    context.inject_timestamp_prompt = MagicMock(side_effect=lambda m: m)
    context.inject_memory = AsyncMock(side_effect=lambda m, *a, **k: m)
    context.schedule_memory_update = AsyncMock(return_value=None)
    return ChatService(context=context, suggestions=MagicMock())


@pytest.fixture
def fake_adapter():
    """LLM 适配器替身：normal 模式不触发 reasoner 路由，仅需默认 provider/model。"""
    adapter = MagicMock()
    adapter.default_provider = "openai"
    adapter.get_provider.return_value.default_model = "gpt-test"
    adapter.get_provider.return_value.supports_multimodal.return_value = False
    return adapter


class FakeConversationStore:
    """进程内假 store：接口对齐 ConversationFacade，捕获写入调用。"""

    def __init__(self, conv: dict):
        self._conv = conv
        self.appended: list[dict] = []
        self.meta_updates: list[dict] = []
        self.get_async = AsyncMock(return_value=conv)
        self.append_message_async = AsyncMock(return_value=True)
        self.update_meta_async = AsyncMock(return_value=None)
        self.set_async = AsyncMock(return_value=None)


def _make_request(stream: bool = False) -> SimpleNamespace:
    """构造 process_conversation_turn 的请求体（Pydantic 模型仅流式路由校验用）。"""
    return SimpleNamespace(
        messages=[SimpleNamespace(role="user", content="你好")],
        stream=stream,
        provider=None,
        model=None,
        temperature=None,
        max_tokens=None,
        top_p=None,
        agent_id=None,
        file_content=None,
        file_name=None,
        file_type=None,
        search_results=None,
        skill_ids=[],
        versions=None,
        chat_mode="normal",
    )


def _patch_generation(monkeypatch):
    """替换生成链路的外部依赖：LLM 返回带 emotion 标签的固定回复。"""
    llm_mock = AsyncMock(return_value="<exp:happy>你好呀！")
    monkeypatch.setattr(chat_service_module.llm_adapter, "chat", llm_mock)
    monkeypatch.setattr(chat_service_module.usage_tracker, "record_usage", MagicMock())
    monkeypatch.setattr(
        chat_service_module.distillation_service, "maybe_distill", AsyncMock(return_value=None)
    )
    # 全局模型统一后模型解析委托门面：固定返回测试模型，隔离真实 DB / 全局单例
    monkeypatch.setattr(
        chat_service_module,
        "resolve_global_provider_model",
        lambda: ("openai", "gpt-test"),
    )
    fake_ctx_mgr = MagicMock()
    fake_ctx_mgr.process = AsyncMock(side_effect=lambda msgs, **kw: {"messages": msgs})
    monkeypatch.setattr(
        chat_service_module, "get_context_manager", MagicMock(return_value=fake_ctx_mgr)
    )
    return llm_mock


async def test_non_stream_turn_spawns_background_memory_pipeline(chat_svc, fake_adapter, monkeypatch):
    _patch_generation(monkeypatch)
    conv = {
        "id": "conv-1",
        "messages": [],
        "title": "New Conversation",
        "agent_id": "test-agent",
        "chat_mode": "normal",
    }
    store = FakeConversationStore(conv)

    result = await chat_svc.process_conversation_turn("conv-1", _make_request(), fake_adapter, store)

    # 生成结果写回响应，emotion 标签被清洗
    assert result["content"] == "你好呀！"
    assert result["model"] == "gpt-test"
    assert result["notice"] is None
    # 落库两次：先 user 消息（生成前），后 assistant 消息（生成后）
    assert store.append_message_async.await_count == 2
    user_msg = store.append_message_async.await_args_list[0][0][1]
    assert user_msg["role"] == "user"
    assert user_msg["content"] == "你好"
    appended = store.append_message_async.await_args_list[1][0][1]
    assert appended["role"] == "assistant"
    assert appended["content"] == "你好呀！"

    # 响应返回时：后台记忆管线已 spawn，但尚未执行（不阻塞响应）
    assert len(chat_svc._background_tasks) == 1
    assert chat_svc._context.schedule_memory_update.await_count == 0

    # 补跑管线：先记忆写入（带 conv/agent/adapter 上下文）后蒸馏
    task = next(iter(chat_svc._background_tasks))
    await task
    for _ in range(3):
        await asyncio.sleep(0)  # 让 done_callback 调度执行

    assert chat_svc._context.schedule_memory_update.await_count == 1
    mem_args = chat_svc._context.schedule_memory_update.await_args
    assert mem_args.args[1] == "conv-1"
    assert mem_args.args[2] == "test-agent"
    assert mem_args.kwargs["llm_adapter"] is fake_adapter
    chat_service_module.distillation_service.maybe_distill.assert_awaited_once()
    # 任务完成后引用从集合清理
    assert chat_svc._background_tasks == set()


async def test_spawn_background_task_discards_after_completion(chat_svc):
    done = asyncio.Event()

    async def quick():
        done.set()

    task = chat_svc._spawn_background_task(quick())
    assert task in chat_svc._background_tasks  # 持引用防 GC

    await task
    for _ in range(3):
        await asyncio.sleep(0)

    assert done.is_set()
    assert task not in chat_svc._background_tasks
    assert chat_svc._background_tasks == set()


async def test_non_stream_generate_writes_content(chat_svc, monkeypatch):
    llm_mock = AsyncMock(return_value="plain answer")
    monkeypatch.setattr(chat_service_module.llm_adapter, "chat", llm_mock)
    record_usage = MagicMock()
    monkeypatch.setattr(chat_service_module.usage_tracker, "record_usage", record_usage)

    state = {"content": "", "reasoning": "", "aborted": False, "started": True}
    await chat_svc.non_stream_generate(state, [{"role": "user", "content": "hi"}], "openai", "gpt-test")

    assert state["content"] == "plain answer"
    assert state["aborted"] is False
    llm_mock.assert_awaited_once()
    record_usage.assert_called_once()


async def test_non_stream_generate_swallows_llm_error(chat_svc, monkeypatch):
    monkeypatch.setattr(
        chat_service_module.llm_adapter, "chat", AsyncMock(side_effect=RuntimeError("boom"))
    )

    state = {"content": "", "reasoning": "", "aborted": False, "started": True}
    await chat_svc.non_stream_generate(state, [{"role": "user", "content": "hi"}], "openai", "gpt-test")

    # LLM 异常不外抛，标记中断并返回兜底文案
    assert state["aborted"] is True
    assert state["content"] == "[Error] An internal error occurred"
