"""chat_service 非流式路径回归测试（LLM/记忆/蒸馏全部 mock，不触碰真实库）。

覆盖：
- 非流式回合：响应返回时后台记忆管线已 spawn 但未阻塞（schedule_memory_update 尚未执行）
- 管线补跑：先记忆写入后蒸馏按序执行，任务完成后从 _background_tasks 清理（防 GC 引用管理）
- _spawn_background_task：任务完成后 done_callback 移除引用
- non_stream_generate：正常写入 content；LLM 异常时 aborted + 兜底文案不外抛
- suggestions 后台任务持久化（链路审查 P1-1）：按消息 id 单行增量回写，
  与主写入路径（append_message_async）交错时互不丢数据，且不再全量 set_async 回写
"""

import asyncio
import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import chat_service as chat_service_module
from app.services import usage_tracker as usage_tracker_module
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


class RowStore:
    """行语义假 store：模拟 conversation_messages 表（每消息一行，按 mid 定位）。

    与 FakeConversationStore 的区别：append/update 是真实的行操作，
    可断言「并发追加的消息在全量回写下会丢失、在单行更新下保留」。
    """

    def __init__(self, messages: list[dict]):
        self.rows: list[dict] = [dict(m) for m in messages]
        self.update_calls: list[tuple[str, str]] = []
        self.set_async = AsyncMock(return_value=None)
        self.update_meta_async = AsyncMock(return_value=None)

    async def append_message_async(self, conversation_id: str, message: dict) -> bool:
        self.rows.append(dict(message))
        return True

    async def update_message_async(self, conversation_id: str, mid: str, message: dict) -> bool:
        self.update_calls.append((conversation_id, mid))
        for i in range(len(self.rows) - 1, -1, -1):
            if str(self.rows[i].get("id", "") or "") == mid:
                self.rows[i] = dict(message)
                return True
        return False


def _make_request(stream: bool = False, client_message_id: str | None = None) -> SimpleNamespace:
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
        client_message_id=client_message_id,
    )


def _patch_generation(monkeypatch):
    """替换生成链路的外部依赖：LLM 返回带 emotion 标签的固定回复。"""
    llm_mock = AsyncMock(return_value="<exp:happy>你好呀！")
    monkeypatch.setattr(chat_service_module.llm_adapter, "chat", llm_mock)
    # P0-5 后 usage 记录在 AgentRunner 管线内（UsageTrackMiddleware），
    # 直接对 usage_tracker 单例打桩（chat_service 模块不再导入该符号）
    monkeypatch.setattr(usage_tracker_module.usage_tracker, "record_usage", MagicMock())
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
    # P0-5 后 usage 记录在 UsageTrackMiddleware：对 usage_tracker 单例打桩
    monkeypatch.setattr(usage_tracker_module.usage_tracker, "record_usage", record_usage)

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


# ── suggestions 后台任务持久化（链路审查 P1-1）─────────────────────────


def _gate_suggestions(chat_svc, monkeypatch, questions: list[str]) -> asyncio.Event:
    """把 suggestions 生成替换为事件门控的慢 LLM：控制竞态窗口的开关。"""
    release = asyncio.Event()

    async def slow_generate(**kwargs):
        await release.wait()  # 模拟 LLM 往返（秒级竞态窗口）
        return list(questions)

    monkeypatch.setattr(chat_svc._suggestions, "generate_suggestions_for_conv", slow_generate)
    return release


async def test_suggestions_writeback_preserves_concurrent_append(chat_svc, monkeypatch):
    """核心竞态回归：suggestions 生成期间主写入路径 append 的新消息不丢。

    修复前：后台任务持回合开始时的 conv 快照全量 set_async 回写，竞态窗口内
    append_message_async 追加的新消息被陈旧快照覆盖（从 DB 消失）。
    修复后：按消息 id 单行 update_message_async，只覆盖本条 assistant 消息行。
    """
    user_msg = {"role": "user", "content": "上一问"}
    assistant_msg = {
        "role": "assistant", "content": "上一答", "id": "assistant-1",
        "versions": [{"content": "上一答", "id": "v1"}], "current_version": 0,
    }
    store = RowStore([user_msg, assistant_msg])
    monkeypatch.setattr(chat_service_module, "conversation_store", store)
    release = _gate_suggestions(chat_svc, monkeypatch, ["问题一", "问题二", "问题三"])

    task = chat_svc._spawn_background_task(chat_svc._generate_suggestions_after_done(
        conv_id="conv-1",
        assistant_message_id="assistant-1",
        assistant_message=assistant_msg,
        messages=[user_msg],
        agent_id=None,
        provider="openai",
        model="gpt-test",
    ))

    await asyncio.sleep(0)  # 任务推进到 LLM 等待点（进入竞态窗口）
    # 竞态窗口内：另一端新回合主写入路径直接 INSERT 新 user 消息
    await store.append_message_async("conv-1", {"role": "user", "content": "竞态新消息", "id": "user-new"})

    release.set()
    await task

    # 不再全量回写（修复点：set_async 零调用）
    store.set_async.assert_not_awaited()
    # 按消息 id 单行更新，suggested_questions 写进当前 version
    assert store.update_calls == [("conv-1", "assistant-1")]
    updated = next(r for r in store.rows if r.get("id") == "assistant-1")
    assert updated["versions"][0]["suggested_questions"] == ["问题一", "问题二", "问题三"]
    # 关键断言：竞态窗口内追加的新消息仍在 DB，未被陈旧快照覆盖丢失
    assert [r.get("id") for r in store.rows] == [None, "assistant-1", "user-new"]
    assert store.rows[-1]["content"] == "竞态新消息"


async def test_suggestions_writeback_without_versions_targets_top_level(chat_svc, monkeypatch):
    """无 versions 形状（普通发送）：suggested_questions 写在消息顶层。"""
    assistant_msg = {"role": "assistant", "content": "回答", "id": "assistant-2"}
    store = RowStore([assistant_msg])
    monkeypatch.setattr(chat_service_module, "conversation_store", store)
    monkeypatch.setattr(
        chat_svc._suggestions, "generate_suggestions_for_conv",
        AsyncMock(return_value=["问题一"]),
    )

    await chat_svc._generate_suggestions_after_done(
        conv_id="conv-1",
        assistant_message_id="assistant-2",
        assistant_message=assistant_msg,
        messages=[{"role": "user", "content": "问"}],
        agent_id=None,
        provider="openai",
        model="gpt-test",
    )

    store.set_async.assert_not_awaited()
    assert store.update_calls == [("conv-1", "assistant-2")]
    assert store.rows[0]["suggested_questions"] == ["问题一"]


async def test_suggestions_writeback_drops_when_row_missing(chat_svc, monkeypatch):
    """消息行不存在（会话已被删除/重建）：丢弃 suggestions，不回退全量回写。"""
    store = RowStore([])  # 空行：update_message_async 必然 False
    monkeypatch.setattr(chat_service_module, "conversation_store", store)
    monkeypatch.setattr(
        chat_svc._suggestions, "generate_suggestions_for_conv",
        AsyncMock(return_value=["问题一"]),
    )

    await chat_svc._generate_suggestions_after_done(
        conv_id="conv-1",
        assistant_message_id="gone",
        assistant_message={"role": "assistant", "content": "回答", "id": "gone"},
        messages=[{"role": "user", "content": "问"}],
        agent_id=None,
        provider="openai",
        model="gpt-test",
    )

    store.set_async.assert_not_awaited()  # 绝不回退全量回写（那会重新引入 P1-1）


async def test_stream_turn_spawns_suggestions_after_persist(chat_svc, monkeypatch):
    """stream_response 接线：suggestions 任务在 assistant 消息落库后 spawn，
    携带其 uuid id；与竞态窗口内的新消息写入交错后互不丢数据。"""
    conv = {"id": "conv-1", "messages": [{"role": "user", "content": "你好"}], "title": "New Conversation"}
    store = RowStore(list(conv["messages"]))
    monkeypatch.setattr(chat_service_module, "conversation_store", store)
    monkeypatch.setattr(chat_service_module, "_select_tools_for_turn", lambda *a, **k: (None, None))
    monkeypatch.setattr(
        chat_service_module.distillation_service, "maybe_distill", AsyncMock(return_value=None)
    )
    fake_ctx_mgr = MagicMock()
    fake_ctx_mgr.token_counter.count_tokens = MagicMock(return_value=42)
    fake_ctx_mgr.max_context_tokens = 8192
    monkeypatch.setattr(chat_service_module, "get_context_manager", MagicMock(return_value=fake_ctx_mgr))

    # 假 runner：直接写 ctx.state（与真实管线一致）并产出一个 content chunk
    async def fake_run_stream(ctx, llm_call_fn):
        ctx.state["content"] = "回答内容"
        yield chat_service_module.sse_data(chat_service_module.ChatStreamChunk(
            id=ctx.state.get("chat_id", "x"), content="回答内容",
            model="gpt-test", provider="openai",
        ))

    fake_runner = MagicMock()
    fake_runner.run_stream = fake_run_stream
    monkeypatch.setattr(
        chat_service_module.tool_orchestrator, "create_runner", MagicMock(return_value=fake_runner)
    )

    release = _gate_suggestions(chat_svc, monkeypatch, ["接下来问什么？"])

    resp = await chat_svc.stream_response(
        conv_id="conv-1",
        conv=conv,
        request=_make_request(stream=True),
        all_messages=[{"role": "user", "content": "你好"}],
        provider="openai",
        model="gpt-test",
        agent_id=None,
        state={"content": "", "reasoning": "", "aborted": False, "started": True},
        start_time=0.0,
        versions=None,
    )
    async for _ in resp.body_iterator:
        pass  # 流结束 → finally 已持久化 assistant 消息并 spawn suggestions 任务

    # 竞态窗口：另一端新回合 append 新 user 消息（本回合的 in-memory conv 看不到它）
    await store.append_message_async("conv-1", {"role": "user", "content": "竞态新消息", "id": "user-new"})

    release.set()
    pending = [t for t in chat_svc._background_tasks if not t.done()]
    if pending:
        await asyncio.gather(*pending)

    # assistant 消息以 uuid id 增量落库；suggestions 按同一 id 单行回写
    assert [r.get("role") for r in store.rows] == ["user", "assistant", "user"]
    assistant_row = store.rows[1]
    assert assistant_row["content"] == "回答内容"
    assert assistant_row.get("id")
    assert store.update_calls == [("conv-1", assistant_row["id"])]
    assert assistant_row["suggested_questions"] == ["接下来问什么？"]
    # 全程零全量回写；竞态窗口内的新消息未丢
    store.set_async.assert_not_awaited()
    assert store.rows[2]["content"] == "竞态新消息"


# ── 用户消息持久 id 与幂等去重（链路审查 P1-6）─────────────────────────


def test_save_user_message_generates_stable_uuid_id():
    """user 消息落库即带持久 uuid id（与 assistant 消息同构）；连续 user 消息
    合并进同一行时 id 保持稳定，新消息生成新 uuid。"""
    conv = {"messages": []}
    ChatService.save_user_message(conv, "你好")
    first = conv["messages"][0]
    assert first["role"] == "user" and first["id"]
    uuid.UUID(first["id"])

    # 连续 user 消息合并（补充文件内容语义）：不新增行，id 不变
    ChatService.save_user_message(conv, "你好")
    assert len(conv["messages"]) == 1
    assert conv["messages"][0]["id"] == first["id"]

    # assistant 回复后的新 user 消息：新持久 uuid
    conv["messages"].append({"role": "assistant", "content": "你好呀", "id": str(uuid.uuid4())})
    ChatService.save_user_message(conv, "再来一条")
    second = conv["messages"][2]
    assert second["role"] == "user"
    assert second["id"] != first["id"]
    uuid.UUID(second["id"])


async def test_user_message_persists_with_id_and_turn_returns_ids(chat_svc, fake_adapter, monkeypatch):
    """非流式回合：user/assistant 消息均以持久 id 落库，响应随体返回两个 id。"""
    _patch_generation(monkeypatch)
    conv = {"id": "conv-1", "messages": [], "title": "New Conversation", "agent_id": "test-agent"}
    store = FakeConversationStore(conv)

    result = await chat_svc.process_conversation_turn("conv-1", _make_request(), fake_adapter, store)

    user_msg = store.append_message_async.await_args_list[0][0][1]
    assistant_msg = store.append_message_async.await_args_list[1][0][1]
    assert user_msg["role"] == "user"
    assert user_msg["id"]
    assert assistant_msg["id"]
    assert result["user_message_id"] == user_msg["id"]
    assert result["message_id"] == assistant_msg["id"]


async def test_duplicate_client_message_id_skips_reappend(chat_svc, fake_adapter, monkeypatch):
    """幂等去重：同一（会话 + client_message_id）重复提交时跳过 user 消息重复落库，
    生成照常执行；两次响应返回同一 user 消息 id。"""
    _patch_generation(monkeypatch)
    conv = {"id": "conv-1", "messages": [], "title": "New Conversation", "agent_id": "test-agent"}
    store = FakeConversationStore(conv)

    first = await chat_svc.process_conversation_turn(
        "conv-1", _make_request(client_message_id="cm-1"), fake_adapter, store
    )
    # get_async 返回同一 conv dict：内存态已含 cm-1，模拟重试命中同一会话
    second = await chat_svc.process_conversation_turn(
        "conv-1", _make_request(client_message_id="cm-1"), fake_adapter, store
    )

    user_appends = [
        c for c in store.append_message_async.await_args_list if c.args[1]["role"] == "user"
    ]
    assert len(user_appends) == 1
    assert first["user_message_id"] == second["user_message_id"]
    # 去重路径零全量回写（未动 conv 持久状态）
    store.set_async.assert_not_awaited()


async def test_stream_done_chunk_carries_persistent_ids(chat_svc, monkeypatch):
    """流式回合：done chunk 携带本回合 user/assistant 消息的落库 uuid，
    与 append_message_async 落库行的 id 一致（前端据其替换本地占位 id）。"""
    conv = {
        "id": "conv-1",
        "messages": [{"role": "user", "content": "你好", "id": str(uuid.uuid4())}],
        "title": "New Conversation",
    }
    store = RowStore(list(conv["messages"]))
    monkeypatch.setattr(chat_service_module, "conversation_store", store)
    monkeypatch.setattr(chat_service_module, "_select_tools_for_turn", lambda *a, **k: (None, None))
    monkeypatch.setattr(
        chat_service_module.distillation_service, "maybe_distill", AsyncMock(return_value=None)
    )
    fake_ctx_mgr = MagicMock()
    fake_ctx_mgr.token_counter.count_tokens = MagicMock(return_value=42)
    fake_ctx_mgr.max_context_tokens = 8192
    monkeypatch.setattr(chat_service_module, "get_context_manager", MagicMock(return_value=fake_ctx_mgr))

    async def fake_run_stream(ctx, llm_call_fn):
        ctx.state["content"] = "回答内容"
        yield chat_service_module.sse_data(chat_service_module.ChatStreamChunk(
            id=ctx.state.get("chat_id", "x"), content="回答内容",
            model="gpt-test", provider="openai",
        ))

    fake_runner = MagicMock()
    fake_runner.run_stream = fake_run_stream
    monkeypatch.setattr(
        chat_service_module.tool_orchestrator, "create_runner", MagicMock(return_value=fake_runner)
    )
    monkeypatch.setattr(
        chat_svc._suggestions, "generate_suggestions_for_conv", AsyncMock(return_value=[])
    )

    resp = await chat_svc.stream_response(
        conv_id="conv-1",
        conv=conv,
        request=_make_request(stream=True),
        all_messages=[{"role": "user", "content": "你好"}],
        provider="openai",
        model="gpt-test",
        agent_id=None,
        state={"content": "", "reasoning": "", "aborted": False, "started": True},
        start_time=0.0,
        versions=None,
    )
    chunks = []
    async for raw in resp.body_iterator:
        for line in raw.split("\n"):
            if line.startswith("data: "):
                chunks.append(json.loads(line[len("data: "):]))

    done_chunk = next(c for c in chunks if c.get("done"))
    user_row, assistant_row = store.rows[0], store.rows[1]
    assert assistant_row["role"] == "assistant" and assistant_row.get("id")
    assert done_chunk["message_id"] == assistant_row["id"]
    assert done_chunk["user_message_id"] == user_row["id"]
