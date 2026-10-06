"""工作流最终回复落库回归测试（链路审查 2026-10-05 P0-1）。

修复前：engine.py 成功/失败两条路径的持久化调用直接引用未导入的
ChatService（`await ChatService.persist_conv(...)`），NameError 被外层
except 吞成 warning——assistant 消息从不写入 conversation，用户刷新后
工作流回答消失，只剩自己的用户消息。

覆盖：
- 成功路径（无任务直答）：final_result 作为 assistant 消息落库，无 interrupted 标记
- 失败路径（LLM 规划抛错）：错误文案作为 aborted（interrupted）assistant 消息落库

两条路径均消费完整 submit_stream 流，走临时 SQLite（_init_test_db）与真实
conversation_store 门面断言最终库态；LLM 适配器用替身注入（monkeypatch
engine 模块全局，测试后自动还原）。
"""

from types import SimpleNamespace

import pytest
from sqlalchemy import delete as sa_delete

from app.core.workflow import WorkflowMode, workflow_engine
from app.infrastructure.database.conversation_store import conversation_store
from app.infrastructure.database.models.conversation import Conversation
from app.infrastructure.database.models.conversation_message import ConversationMessage
from app.services.chat_service import ChatService

import app.core.workflow.engine as engine_mod


CONV_ID = "conv-wf-persist"


class _FakeLLMAdapter:
    """LLM 适配器替身：chat_stream 按脚本产出 chunk，可注入异常模拟规划失败。"""

    default_provider = "openai"

    def __init__(self, chunks=None, exc: Exception | None = None):
        self._chunks = chunks or []
        self._exc = exc

    def get_provider(self, _name):
        return SimpleNamespace(default_model="gpt-test")

    async def chat_stream(self, messages, **kwargs):
        if self._exc is not None:
            raise self._exc
        for chunk in self._chunks:
            yield chunk


def _content_chunks(text: str) -> list:
    return [
        SimpleNamespace(type="content", data={"content": text}),
        SimpleNamespace(type="finish_reason", data={"finish_reason": "stop"}),
    ]


@pytest.fixture
def engine_deps(monkeypatch):
    """装配引擎依赖：真实 ChatService 类 + 真实 conversation_store（临时 SQLite），
    LLM 适配器由用例注入。monkeypatch 保证测试后模块全局还原为 None（兜底延迟导入）。"""
    monkeypatch.setattr(engine_mod, "_chat_service_cls", ChatService)
    monkeypatch.setattr(engine_mod, "_conversation_store", conversation_store)

    def _install_adapter(adapter):
        monkeypatch.setattr(engine_mod, "_llm_adapter", adapter)

    return _install_adapter


@pytest.fixture(autouse=True)
def _clean_conversations(_init_test_db):
    """用例前后清空对话与消息行，保证与其它用例/两遍运行互不污染。"""
    yield
    from app.infrastructure.database.session import sync_session_factory

    with sync_session_factory() as session:
        session.execute(sa_delete(ConversationMessage))
        session.execute(sa_delete(Conversation))
        session.commit()


async def _seed_conversation(conv_id: str) -> None:
    await conversation_store.set_async(conv_id, {
        "id": conv_id,
        "title": "工作流落库",
        "messages": [],
    })


async def _drain_submit(user_message: str) -> list[dict]:
    events: list[dict] = []
    async for event in workflow_engine.submit_stream(
        user_message,
        conversation_id=CONV_ID,
        mode=WorkflowMode.STANDARD,
        skip_confirmation=True,
    ):
        events.append(event)
    return events


async def test_success_path_persists_final_reply(engine_deps):
    """无任务直答：final_result 必须作为 assistant 消息写入数据库。"""
    await _seed_conversation(CONV_ID)
    reply = "这是工作流的最终回复，刷新页面后不能消失。"
    engine_deps(_FakeLLMAdapter(chunks=_content_chunks(reply)))

    events = await _drain_submit("帮我测试工作流落库")

    # 工作流本身正常完成并推送了 final_result
    final_events = [e for e in events if e.get("type") == "final_result"]
    assert final_events, f"未收到 final_result 事件: {[e.get('type') for e in events]}"
    assert final_events[0]["data"]["content"] == reply

    # 核心断言：assistant 消息确实落库（修复前 NameError 被吞，库里只有 user 消息）
    conv = await conversation_store.get_async(CONV_ID)
    roles = [m["role"] for m in conv["messages"]]
    assert roles == ["user", "assistant"], f"落库消息序列异常: {roles}"
    assistant = conv["messages"][-1]
    assert assistant["content"] == reply
    assert assistant.get("id"), "assistant 消息缺少持久化 id"
    assert not assistant.get("interrupted"), "成功路径不应带 interrupted 标记"


async def test_failure_path_persists_error_reply(engine_deps):
    """规划阶段抛错：错误文案必须作为 interrupted assistant 消息写入数据库。"""
    await _seed_conversation(CONV_ID)
    engine_deps(_FakeLLMAdapter(exc=RuntimeError("LLM 规划爆炸")))

    events = await _drain_submit("帮我测试工作流失败落库")

    error_events = [e for e in events if e.get("type") == "error"]
    assert error_events, f"未收到 error 事件: {[e.get('type') for e in events]}"

    conv = await conversation_store.get_async(CONV_ID)
    roles = [m["role"] for m in conv["messages"]]
    assert roles == ["user", "assistant"], f"落库消息序列异常: {roles}"
    assistant = conv["messages"][-1]
    assert assistant["content"] == "工作流执行失败：LLM 规划爆炸"
    assert assistant.get("interrupted") is True
