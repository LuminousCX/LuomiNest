"""regenerate 链路 P1-8 三重缺陷修复回归测试（LLM/记忆/蒸馏全部 mock，不触碰真实库）。

覆盖：
- 尾消息重生成：弹掉末尾 assistant 消息后重建（旧行为兼容）
- 非尾重生成（message_id）：从目标消息起整段截断后原地重建，后续消息随旧回答移除
- 目标 id 未命中回退尾条语义（前端刚生成、本地占位 id 未刷新的场景）
- 目标为非 assistant 消息：400 拒绝，会话数据不被改动
- 并发流互斥：同会话已有流在跑时 regenerate 409 拒绝且不触发截断；令牌释放后恢复
- 流互斥令牌生命周期：旧流收尾不误释放替换它的新流标记
- versions 双风格归一：camelCase 旧条目读时归一为 snake_case，写入端统一落 snake_case
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.v1.endpoints.chat import (
    RegenerateRequest,
    UpdateMessageVersionRequest,
    regenerate_message,
    update_message_version,
)
from app.core.exceptions import BadRequestError, ConflictError
from app.services import chat_service as chat_service_module
from app.services import usage_tracker as usage_tracker_module
from app.services.chat_service import (
    ChatService,
    normalize_message_version,
    normalize_message_versions,
)


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
        self.get_async = AsyncMock(return_value=conv)
        self.append_message_async = AsyncMock(return_value=True)
        self.update_message_async = AsyncMock(return_value=True)
        self.update_meta_async = AsyncMock(return_value=None)
        self.set_async = AsyncMock(return_value=None)


@pytest.fixture
def conv_env(monkeypatch):
    """会话 + 假 store：persist_conv 为静态方法、直写模块级 conversation_store
    单例。pytest 下 chat_service 模块可能被重复导入（静态方法 __globals__ 指向
    另一份副本），故同时替换模块全局与 ChatService 类属性两条访问路径，
    保证测试不触碰真实库。"""
    conv = _make_conv()
    store = FakeConversationStore(conv)
    monkeypatch.setattr(chat_service_module, "conversation_store", store)

    async def fake_persist_conv(conv_id: str, c: dict) -> None:
        c["updated_at"] = "test-now"
        await store.set_async(conv_id, c)

    monkeypatch.setattr(ChatService, "persist_conv", staticmethod(fake_persist_conv))
    return conv, store


def _make_conv() -> dict:
    return {
        "id": "conv-1",
        "title": "New Conversation",
        "agent_id": "test-agent",
        "chat_mode": "normal",
        "messages": [
            {"role": "user", "content": "你好", "id": "u1"},
            {"role": "assistant", "content": "回答一", "id": "a1"},
            {"role": "user", "content": "继续", "id": "u2"},
            {"role": "assistant", "content": "回答二", "id": "a2"},
        ],
    }


def _make_request(stream: bool = False, versions: list | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        messages=[SimpleNamespace(role="user", content="继续")],
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
        versions=versions,
        chat_mode="normal",
    )


def _patch_generation(monkeypatch):
    """替换生成链路的外部依赖：LLM 返回固定回复，模型解析/压缩/蒸馏全部打桩。"""
    llm_mock = AsyncMock(return_value="重新生成的回答")
    monkeypatch.setattr(chat_service_module.llm_adapter, "chat", llm_mock)
    monkeypatch.setattr(usage_tracker_module.usage_tracker, "record_usage", MagicMock())
    monkeypatch.setattr(
        chat_service_module.distillation_service, "maybe_distill", AsyncMock(return_value=None)
    )
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


# ── 缺陷 1：非尾重生成损坏历史 ─────────────────────────────────


async def test_regenerate_tail_message_rebuilds(chat_svc, fake_adapter, monkeypatch, conv_env):
    """尾消息重生成（不带 message_id，旧行为兼容）：弹尾后新回答追加为唯一尾条。"""
    _patch_generation(monkeypatch)
    conv, store = conv_env

    result = await chat_svc.process_conversation_turn(
        "conv-1", _make_request(), fake_adapter, store, regenerate=True,
    )

    assert result["content"] == "重新生成的回答"
    msgs = conv["messages"]
    # 尾条语义：仅弹掉末尾 assistant 消息（a2），新回答追加为唯一尾条
    assert [m["id"] for m in msgs[:-1]] == ["u1", "a1", "u2"]
    assert msgs[-1]["role"] == "assistant"
    assert msgs[-1]["content"] == "重新生成的回答"
    assert msgs[-1]["id"] != "a2"
    # 截断先全量持久化，随后新回答增量追加
    assert store.set_async.await_count == 1
    assert store.append_message_async.await_count == 1
    assert store.append_message_async.await_args.args[1]["role"] == "assistant"


async def test_regenerate_non_tail_truncates_from_message_id(chat_svc, fake_adapter, monkeypatch, conv_env):
    """非尾重生成（message_id）：从目标消息起整段截断后原地重建，后续消息随旧回答移除。"""
    _patch_generation(monkeypatch)
    conv, store = conv_env

    await chat_svc.process_conversation_turn(
        "conv-1", _make_request(), fake_adapter, store,
        regenerate=True, regenerate_message_id="a1",
    )

    msgs = conv["messages"]
    # 目标 a1 与其后的 u2/a2 一并截断，新回答接在 u1 之后（原位置）
    assert [m["id"] for m in msgs[:-1]] == ["u1"]
    assert msgs[-1]["role"] == "assistant"
    assert msgs[-1]["content"] == "重新生成的回答"
    assert "a1" not in [m["id"] for m in msgs]
    assert "a2" not in [m["id"] for m in msgs]
    assert "u2" not in [m["id"] for m in msgs]
    # 截断先全量持久化，再增量追加新回答
    assert store.set_async.await_count == 1
    assert store.append_message_async.await_count == 1


async def test_regenerate_unknown_message_id_falls_back_to_tail(chat_svc, fake_adapter, monkeypatch, conv_env):
    """message_id 未命中（前端刚生成、本地占位 id 未刷新）：回退尾条语义，不报错。"""
    _patch_generation(monkeypatch)
    conv, store = conv_env

    await chat_svc.process_conversation_turn(
        "conv-1", _make_request(), fake_adapter, store,
        regenerate=True, regenerate_message_id="local-placeholder-id",
    )

    msgs = conv["messages"]
    assert [m["id"] for m in msgs[:-1]] == ["u1", "a1", "u2"]
    assert msgs[-1]["content"] == "重新生成的回答"


async def test_regenerate_user_message_id_rejected(chat_svc, fake_adapter, monkeypatch, conv_env):
    """目标为用户消息：400 拒绝且会话数据不被改动。"""
    _patch_generation(monkeypatch)
    conv, store = conv_env

    with pytest.raises(BadRequestError):
        await chat_svc.process_conversation_turn(
            "conv-1", _make_request(), fake_adapter, store,
            regenerate=True, regenerate_message_id="u1",
        )

    # 未发生任何截断/持久化
    assert [m["id"] for m in conv["messages"]] == ["u1", "a1", "u2", "a2"]
    assert store.set_async.await_count == 0


# ── 缺陷 2：无流互斥 ──────────────────────────────────────────


def test_stream_mutex_token_semantics(chat_svc):
    """令牌语义：占用期拒绝、替换登记、旧流收尾不误删新流标记、释放后可复用。"""
    t1 = chat_svc.begin_conv_stream("conv-1")
    with pytest.raises(ConflictError):
        chat_svc.begin_conv_stream("conv-1")

    # 发送新消息路径（cancel-and-replace）：强制登记新令牌
    t2 = chat_svc.begin_conv_stream("conv-1", replace=True)
    assert t1 != t2

    # 被顶掉的旧流收尾：不误释放新流标记
    chat_svc.end_conv_stream("conv-1", t1)
    assert chat_svc._active_streams.get("conv-1") == t2

    chat_svc.end_conv_stream("conv-1", t2)
    assert "conv-1" not in chat_svc._active_streams

    t3 = chat_svc.begin_conv_stream("conv-1")
    chat_svc.end_conv_stream("conv-1", t3)
    assert "conv-1" not in chat_svc._active_streams


async def test_regenerate_conflict_while_stream_active(chat_svc, fake_adapter, monkeypatch, conv_env):
    """同会话已有流在跑：regenerate（流式/非流式）409 拒绝，且不触发截断。"""
    _patch_generation(monkeypatch)
    conv, store = conv_env

    token = chat_svc.begin_conv_stream("conv-1")
    try:
        # 非流式 regenerate：服务内补查标记拒绝
        with pytest.raises(ConflictError):
            await chat_svc.process_conversation_turn(
                "conv-1", _make_request(), fake_adapter, store,
                regenerate=True, regenerate_message_id="a2",
            )
        # 流式 regenerate：服务层入口同样拒绝（路由层 begin_conv_stream 抛 409）
        with pytest.raises(ConflictError):
            chat_svc.begin_conv_stream("conv-1")

        # 拒绝路径未改动会话数据
        assert [m["id"] for m in conv["messages"]] == ["u1", "a1", "u2", "a2"]
        assert store.set_async.await_count == 0
    finally:
        chat_svc.end_conv_stream("conv-1", token)

    # 释放后恢复正常
    await chat_svc.process_conversation_turn(
        "conv-1", _make_request(), fake_adapter, store,
        regenerate=True, regenerate_message_id="a2",
    )
    assert [m["id"] for m in conv["messages"][:-1]] == ["u1", "a1", "u2"]


async def test_stream_regenerate_endpoint_claims_and_releases_token(
    chat_svc, fake_adapter, monkeypatch, conv_env,
):
    """端到端接线：regenerate 路由先占位、令牌随流参数下传、按令牌释放。"""
    conv, store = conv_env

    captured: dict = {}

    async def fake_stream_response(
        conv_id, conv, request, all_messages, provider, model, agent_id,
        state, start_time, versions=None, notice="", stream_token=None,
    ):
        captured["stream_token"] = stream_token
        captured["versions"] = versions
        return "sse-response"

    monkeypatch.setattr(chat_svc, "stream_response", fake_stream_response)

    request = RegenerateRequest(stream=True, message_id="a2", versions=[{"content": "旧回答"}])
    resp = await regenerate_message(
        "conv-1", request,
        adapter=fake_adapter, chat_service=chat_svc, conversation_store=store,
    )
    assert resp == "sse-response"
    token = captured["stream_token"]
    assert token and chat_svc._active_streams.get("conv-1") == token
    assert captured["versions"] == [{"content": "旧回答"}]
    # 业务流程完成后标记仍被流持有（由生成器 finally 释放）
    # 截断自 a2：a1 在目标之前保留，a2 已移除
    assert [m["id"] for m in conv["messages"]] == ["u1", "a1", "u2"]

    # 模拟流生成器 finally：按令牌释放后标记清空，下一条流可登记
    chat_svc.end_conv_stream("conv-1", token)
    assert "conv-1" not in chat_svc._active_streams


async def test_add_message_stream_replaces_marker(chat_svc, fake_adapter, monkeypatch, conv_env):
    """发送新消息路径（replace=True）：顶掉旧流标记，旧流收尾不误删新标记。"""
    conv, store = conv_env

    captured: dict = {}

    async def fake_stream_response(
        conv_id, conv, request, all_messages, provider, model, agent_id,
        state, start_time, versions=None, notice="", stream_token=None,
    ):
        captured["stream_token"] = stream_token
        return "sse-response"

    monkeypatch.setattr(chat_svc, "stream_response", fake_stream_response)

    old_token = chat_svc.begin_conv_stream("conv-1")
    new_token = chat_svc.begin_conv_stream("conv-1", replace=True)
    assert new_token != old_token

    from app.api.v1.endpoints.chat import ChatRequest  # 局部导入：仅流式路由用

    body = ChatRequest(messages=[{"role": "user", "content": "你好"}], stream=True)
    await chat_svc.process_conversation_turn(
        "conv-1", body, fake_adapter, store, stream_token=new_token,
    )
    assert captured["stream_token"] == new_token
    assert chat_svc._active_streams.get("conv-1") == new_token

    # 旧流（被顶掉的流）收尾：不影响新流标记
    chat_svc.end_conv_stream("conv-1", old_token)
    assert chat_svc._active_streams.get("conv-1") == new_token
    chat_svc.end_conv_stream("conv-1", new_token)
    assert "conv-1" not in chat_svc._active_streams


# ── 缺陷 3：versions 双风格混存 ───────────────────────────────


def test_normalize_message_version_migrates_camel_case():
    """camelCase 别名键迁移为 snake_case 规范键，其余字段原样保留。"""
    v = normalize_message_version({
        "content": "旧回答",
        "reasoningContent": "旧推理",
        "suggestedQuestions": ["问题1"],
        "model": "m1",
        "provider": "p1",
        "id": "vid",
    })
    assert v["reasoning_content"] == "旧推理"
    assert v["suggested_questions"] == ["问题1"]
    assert "reasoningContent" not in v
    assert "suggestedQuestions" not in v
    assert v["model"] == "m1"
    assert v["provider"] == "p1"
    assert v["id"] == "vid"


def test_normalize_message_versions_drops_non_dict_entries():
    versions = normalize_message_versions([
        {"content": "v1", "reasoningContent": "r1"},
        "garbage",
        {"content": "v2", "suggested_questions": ["q"]},
    ])
    assert [v["content"] for v in versions] == ["v1", "v2"]
    assert versions[0]["reasoning_content"] == "r1"
    assert normalize_message_versions(None) == []


def test_save_assistant_message_normalizes_versions_on_write():
    """写入端归一：请求携带的 camelCase 历史版本落库前统一为 snake_case。"""
    conv: dict = {"messages": []}
    state = {
        "content": "新回答", "reasoning": "新推理", "aborted": False,
        "model": "m", "provider": "p", "suggested_questions": ["新问题"],
    }
    ChatService.save_assistant_message(conv, state, versions=[
        {"content": "旧回答", "reasoningContent": "旧推理", "suggestedQuestions": ["q1"]},
        {"content": "旧回答2", "reasoning_content": "旧推理2", "suggested_questions": ["q2"]},
    ])
    entry = conv["messages"][-1]
    assert len(entry["versions"]) == 3
    for v in entry["versions"]:
        assert "reasoningContent" not in v
        assert "suggestedQuestions" not in v
    assert entry["versions"][0]["reasoning_content"] == "旧推理"
    assert entry["versions"][0]["suggested_questions"] == ["q1"]
    assert entry["versions"][-1]["content"] == "新回答"
    assert entry["versions"][-1]["suggested_questions"] == ["新问题"]
    assert entry["current_version"] == 2


async def test_update_message_version_reads_legacy_camel_case(chat_svc, conv_env):
    """版本切换读取端兼容旧格式：camelCase 条目读时归一并写回（渐进迁移）。"""
    conv, store = conv_env
    conv["messages"][1]["versions"] = [
        {"content": "v1内容", "reasoningContent": "v1推理", "suggestedQuestions": ["s1"]},
        {"content": "v2内容", "reasoning_content": "v2推理", "suggested_questions": ["s2"]},
    ]

    resp = await update_message_version(
        "conv-1",
        UpdateMessageVersionRequest(message_id="a1", current_version=0),
        chat_service=chat_svc,
        conversation_store=store,
    )
    assert resp["code"] == 0

    msg = conv["messages"][1]
    assert msg["content"] == "v1内容"
    assert msg["reasoning_content"] == "v1推理"
    assert msg["suggested_questions"] == ["s1"]
    assert msg["current_version"] == 0
    # 写回即归一：整个版本数组不再含 camelCase 键
    for v in msg["versions"]:
        assert "reasoningContent" not in v
        assert "suggestedQuestions" not in v
    assert store.set_async.await_count == 1
