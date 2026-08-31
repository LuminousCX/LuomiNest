"""Phase 5 集成测试: stream_chat / stream_response 与 AgentRunner 集成。

验证：
1. stream_chat 基本流式输出（content + done）
2. stream_chat emotion 标签清洗（EmotionStreamParser 集成）
3. stream_chat 工具调用（tool_calls + tool_event SSE）
4. stream_response 基本流式输出（content + done + suggested_questions）
5. stream_response state 同步（content/model/provider/aborted）
6. stream_response 持久化调用（save_assistant_message + persist_conv）

运行方式：python tests/integration/test_chat_service_phase5.py
"""
import os
import sys
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, r"d:\Projects\Project\LuomiNest\backend")
os.environ.setdefault("DATA_DIR", "/tmp/luominest_test_chat_phase5")
os.environ.setdefault("SECRET_KEY", "test-key-not-for-production-use")

from app.runtime.provider.llm.types import RouteHint, StreamEvent
from app.schemas.chat import ChatStreamChunk
from app.services.chat_service import ChatService
from app.services.context_service import ContextService
from app.services.suggestion_service import SuggestionService

passed = 0
failed = 0


def check(name: str, cond: bool, detail: str = ""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name}" + (f" ({detail})" if detail else ""))


def parse_sse(sse_str: str) -> dict:
    """解析 SSE 字符串为 dict。"""
    assert sse_str.startswith("data: "), f"非 SSE 格式: {sse_str[:30]}"
    assert sse_str.endswith("\n\n"), f"SSE 缺少终止符: {sse_str[-4:]}"
    return json.loads(sse_str[len("data: "):-2])


class MockRequest:
    """模拟 ChatRequest。"""
    def __init__(self, temperature=0.7, max_tokens=4096, top_p=0.9,
                 is_sub_agent=False, disable_tools=None, agent_depth=0):
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.is_sub_agent = is_sub_agent
        self.disable_tools = disable_tools
        self.agent_depth = agent_depth


def make_chat_service():
    """创建 ChatService 实例（mock 依赖）。"""
    context = MagicMock(spec=ContextService)
    context.schedule_memory_update = AsyncMock()
    suggestions = MagicMock(spec=SuggestionService)
    suggestions.generate_suggestions_for_conv = AsyncMock(return_value=["q1", "q2"])
    return ChatService(context, suggestions)


# ════════════════════════════════════════════════════
# 1. stream_chat 基本流式输出（无工具）
# ════════════════════════════════════════════════════
print("\n=== 1. stream_chat 基本流式输出（无工具） ===")


async def mock_chat_stream_basic(**kwargs):
    yield StreamEvent("content", {"content": "Hello"})
    yield StreamEvent("content", {"content": " world"})
    yield StreamEvent("finish_reason", {"finish_reason": "stop"})


async def test_stream_chat_basic():
    service = make_chat_service()
    messages = [{"role": "user", "content": "hi"}]
    request = MockRequest()

    with patch("app.services.chat_service.llm_adapter") as mock_adapter:
        mock_adapter.chat_stream = mock_chat_stream_basic
        mock_adapter.supports_tool_calls.return_value = False
        with patch("app.services.chat_service.tool_registry") as mock_registry:
            mock_registry.list_names.return_value = []

            results = []
            async for sse in service.stream_chat(messages, request, "test-provider", "test-model", "agent-1"):
                results.append(sse)

    chunks = [parse_sse(s) for s in results]
    content_chunks = [c for c in chunks if c.get("content")]
    done_chunks = [c for c in chunks if c.get("done")]

    check("产出 2 个 content SSE", len(content_chunks) == 2, f"got {len(content_chunks)}")
    check("第一个 content 是 'Hello'", content_chunks[0]["content"] == "Hello", f"got {content_chunks[0]['content']!r}")
    check("第二个 content 是 ' world'", content_chunks[1]["content"] == " world", f"got {content_chunks[1]['content']!r}")
    check("有 done 事件", len(done_chunks) == 1)
    check("SSE 含 provider", chunks[0].get("provider") == "test-provider")
    check("SSE 含 model", chunks[0].get("model") == "test-model")


asyncio.run(test_stream_chat_basic())


# ════════════════════════════════════════════════════
# 2. stream_chat emotion 标签清洗
# ════════════════════════════════════════════════════
print("\n=== 2. stream_chat emotion 标签清洗 ===")


async def mock_chat_stream_emotion(**kwargs):
    yield StreamEvent("content", {"content": "你好"})
    yield StreamEvent("content", {"content": "<exp:happy>"})
    yield StreamEvent("content", {"content": "今天天气不错"})
    yield StreamEvent("finish_reason", {"finish_reason": "stop"})


async def test_stream_chat_emotion():
    service = make_chat_service()
    messages = [{"role": "user", "content": "你好"}]
    request = MockRequest()

    with patch("app.services.chat_service.llm_adapter") as mock_adapter:
        mock_adapter.chat_stream = mock_chat_stream_emotion
        mock_adapter.supports_tool_calls.return_value = False
        with patch("app.services.chat_service.tool_registry") as mock_registry:
            mock_registry.list_names.return_value = []

            results = []
            async for sse in service.stream_chat(messages, request, "p", "m"):
                results.append(sse)

    chunks = [parse_sse(s) for s in results]
    all_content = "".join(c.get("content", "") for c in chunks)
    emotions = [c.get("emotion") for c in chunks if c.get("emotion")]

    check("清洗后 content 无 <exp: 标签", "<exp:" not in all_content, f"content={all_content!r}")
    check("emotion 字段出现", len(emotions) > 0, "无 emotion")
    check("emotion 值是 happy", "happy" in emotions, f"emotions={emotions}")


asyncio.run(test_stream_chat_emotion())


# ════════════════════════════════════════════════════
# 3. stream_chat 工具调用（tool_calls + tool_event SSE）
# ════════════════════════════════════════════════════
print("\n=== 3. stream_chat 工具调用 ===")

_stream_call_count = 0


async def mock_chat_stream_with_tools(**kwargs):
    global _stream_call_count
    _stream_call_count += 1
    if _stream_call_count == 1:
        yield StreamEvent("content", {"content": "让我查看文件"})
        yield StreamEvent("tool_call_delta", {
            "index": 0,
            "tool_call_id": "call_001",
            "function_name": "read_file",
            "function_arguments": '{"path":"test.txt"}',
        })
        yield StreamEvent("finish_reason", {"finish_reason": "tool_calls"})
    else:
        yield StreamEvent("content", {"content": "文件内容是测试数据"})
        yield StreamEvent("finish_reason", {"finish_reason": "stop"})


async def mock_execute_tool_call(tool_call):
    return {
        "role": "tool",
        "tool_call_id": tool_call.get("id", ""),
        "name": tool_call.get("function", {}).get("name", ""),
        "content": "test file content",
    }


async def test_stream_chat_tools():
    global _stream_call_count
    _stream_call_count = 0
    service = make_chat_service()
    messages = [{"role": "user", "content": "读文件"}]
    request = MockRequest()
    tools = [{"type": "function", "function": {"name": "read_file", "description": "read", "parameters": {}}}]

    with patch("app.services.chat_service.llm_adapter") as mock_adapter:
        mock_adapter.chat_stream = mock_chat_stream_with_tools
        mock_adapter.supports_tool_calls.return_value = True
        with patch("app.services.chat_service.tool_registry") as mock_registry:
            mock_registry.list_names.return_value = ["read_file"]
            with patch("app.services.chat_service.tool_orchestrator") as mock_orch:
                from app.core.tools.orchestrator import tool_orchestrator as real_orch
                mock_orch.get_tools_for_llm.return_value = tools
                mock_orch.max_iterations = 10
                mock_orch.build_assistant_message_with_tool_calls = (
                    real_orch.build_assistant_message_with_tool_calls
                )
                mock_orch.create_runner = real_orch.create_runner
                mock_orch.execute_tool_call = mock_execute_tool_call

                results = []
                async for sse in service.stream_chat(messages, request, "p", "m"):
                    results.append(sse)

    chunks = [parse_sse(s) for s in results]
    content_chunks = [c for c in chunks if c.get("content")]
    tool_calls_chunks = [c for c in chunks if c.get("tool_calls")]
    tool_event_chunks = [c for c in chunks if c.get("tool_event")]
    done_chunks = [c for c in chunks if c.get("done")]

    check("有 content SSE", len(content_chunks) >= 2, f"got {len(content_chunks)}")
    check("有 tool_calls 公告 SSE", len(tool_calls_chunks) == 1, f"got {len(tool_calls_chunks)}")
    check("有 tool_event started/completed", len(tool_event_chunks) >= 2, f"got {len(tool_event_chunks)}")
    check("tool_event 含 started", any(c["tool_event"]["status"] == "started" for c in tool_event_chunks))
    check("tool_event 含 completed", any(c["tool_event"]["status"] == "completed" for c in tool_event_chunks))
    check("有 done 事件", len(done_chunks) == 1)


asyncio.run(test_stream_chat_tools())


# ════════════════════════════════════════════════════
# 4. stream_response 基本流式输出 + state 同步
# ════════════════════════════════════════════════════
print("\n=== 4. stream_response 基本流式输出 + state 同步 ===")


async def mock_chat_stream_response(**kwargs):
    yield StreamEvent("content", {"content": "这是回复"})
    yield StreamEvent("finish_reason", {"finish_reason": "stop"})


async def test_stream_response_basic():
    service = make_chat_service()
    messages = [{"role": "user", "content": "你好"}]
    conv = {"messages": list(messages), "title": "新对话"}
    request = MockRequest()
    state = {"content": "", "reasoning": "", "aborted": False, "started": True}

    with patch("app.services.chat_service.llm_adapter") as mock_adapter:
        mock_adapter.chat_stream = mock_chat_stream_response
        mock_adapter.supports_tool_calls.return_value = False
        with patch("app.services.chat_service.tool_registry") as mock_registry:
            mock_registry.list_names.return_value = []
            with patch("app.services.chat_service.conversation_store") as mock_store:
                # 热路径增量持久化（messages 拆独立表后：append_message + update_meta）
                mock_store.set_async = AsyncMock()
                mock_store.append_message_async = AsyncMock(return_value=True)
                mock_store.update_meta_async = AsyncMock()
                with patch("app.services.chat_service.distillation_service") as mock_distill:
                    mock_distill.maybe_distill = AsyncMock()

                    response = await service.stream_response(
                        "conv-1", conv, request, messages,
                        "test-provider", "test-model", "main-agent",
                        state, 0.0,
                    )
                    results = []
                    async for chunk in response.body_iterator:
                        results.append(chunk)

    chunks = [parse_sse(s) for s in results]
    content_chunks = [c for c in chunks if c.get("content")]
    done_chunks = [c for c in chunks if c.get("done")]

    check("有 content SSE", len(content_chunks) == 1, f"got {len(content_chunks)}")
    check("content 是 '这是回复'", content_chunks[0]["content"] == "这是回复")
    check("有 done 事件", len(done_chunks) == 1)
    check("done 含 suggested_questions", done_chunks[0].get("suggested_questions") == ["q1", "q2"])

    # state 同步
    check("state['content'] 已同步", state["content"] == "这是回复", f"got {state['content']!r}")
    check("state['model'] 已同步", state["model"] == "test-model")
    check("state['provider'] 已同步", state["provider"] == "test-provider")
    check("state['aborted'] 为 False", state["aborted"] is False)

    # 持久化调用（增量追加路径，替代旧的全量 set_async）
    check("append_message_async 被调用", mock_store.append_message_async.called)
    check("update_meta_async 被调用", mock_store.update_meta_async.called)
    check("未走全量 set_async", not mock_store.set_async.called)
    check("schedule_memory_update 被调用", service._context.schedule_memory_update.called)
    check("maybe_distill 被调用", mock_distill.maybe_distill.called)
    check("generate_suggestions 被调用", service._suggestions.generate_suggestions_for_conv.called)


asyncio.run(test_stream_response_basic())


# ════════════════════════════════════════════════════
# 5. stream_response LLM 异常时 state 同步
# ════════════════════════════════════════════════════
print("\n=== 5. stream_response LLM 异常时 state 同步 ===")


async def mock_chat_stream_error(**kwargs):
    yield StreamEvent("content", {"content": "部分内容"})
    raise RuntimeError("LLM 连接中断")


async def test_stream_response_error():
    service = make_chat_service()
    messages = [{"role": "user", "content": "你好"}]
    conv = {"messages": list(messages), "title": "新对话"}
    request = MockRequest()
    state = {"content": "", "reasoning": "", "aborted": False, "started": True}

    with patch("app.services.chat_service.llm_adapter") as mock_adapter:
        mock_adapter.chat_stream = mock_chat_stream_error
        mock_adapter.supports_tool_calls.return_value = False
        with patch("app.services.chat_service.tool_registry") as mock_registry:
            mock_registry.list_names.return_value = []
            with patch("app.services.chat_service.conversation_store") as mock_store:
                mock_store.set_async = AsyncMock()
                mock_store.append_message_async = AsyncMock(return_value=True)
                mock_store.update_meta_async = AsyncMock()
                with patch("app.services.chat_service.distillation_service") as mock_distill:
                    mock_distill.maybe_distill = AsyncMock()

                    response = await service.stream_response(
                        "conv-2", conv, request, messages,
                        "p", "m", "main-agent",
                        state, 0.0,
                    )
                    results = []
                    async for chunk in response.body_iterator:
                        results.append(chunk)

    chunks = [parse_sse(s) for s in results]
    error_chunks = [c for c in chunks if "[Error]" in c.get("content", "")]
    done_chunks = [c for c in chunks if c.get("done")]

    check("有 Error content SSE", len(error_chunks) == 1, f"got {len(error_chunks)}")
    check("有 done 事件", len(done_chunks) == 1)
    check("state['aborted'] 为 True", state["aborted"] is True)
    check("state['content'] 有部分内容", state["content"] == "部分内容", f"got {state['content']!r}")


asyncio.run(test_stream_response_error())


# ════════════════════════════════════════════════════
# 6. stream_chat 子 Agent 模式（depth_token + 跳过记忆）
# ════════════════════════════════════════════════════
print("\n=== 6. stream_chat 子 Agent 模式 ===")


async def test_stream_chat_subagent():
    service = make_chat_service()
    messages = [{"role": "user", "content": "子任务"}]
    request = MockRequest(is_sub_agent=True, agent_depth=1)

    with patch("app.services.chat_service.llm_adapter") as mock_adapter:
        mock_adapter.chat_stream = mock_chat_stream_basic
        mock_adapter.supports_tool_calls.return_value = False
        with patch("app.services.chat_service.tool_registry") as mock_registry:
            mock_registry.list_names.return_value = []

            results = []
            async for sse in service.stream_chat(messages, request, "p", "m"):
                results.append(sse)

    check("子 Agent 模式正常完成", len(results) > 0)
    check("子 Agent 跳过记忆更新", not service._context.schedule_memory_update.called,
          "schedule_memory_update 不应被调用")


asyncio.run(test_stream_chat_subagent())


# ════════════════════════════════════════════════════
# 结果汇总
# ════════════════════════════════════════════════════
print("\n" + "=" * 60)
print(f"test_chat_service_phase5 结果: {passed} passed, {failed} failed")
print("=" * 60)
sys.exit(0 if failed == 0 else 1)
