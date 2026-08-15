"""Phase 5 集成测试: subagent_executor + group_chat 与 AgentRunner 集成。

验证：
1. subagent_executor 基本执行（无工具）— content 返回 + running 事件
2. subagent_executor 工具调用 — tool_call/tool_result 事件 + 多轮循环
3. subagent_executor 取消 — CancelledError
4. subagent_executor 达到最大迭代 — 返回 max iterations 消息
5. group_chat 基本流式（无工具）— agent_message_delta + agent_message_end
6. group_chat emotion 清洗 — 标签剥离
7. group_chat 工具调用 — 多轮 + content
8. group_chat LLM 异常 — agent_error

运行方式：python tests/integration/test_phase5_remaining.py
"""
import os
import sys
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, r"d:\Projects\Project\LuomiNest\backend")
os.environ.setdefault("DATA_DIR", "/tmp/luominest_test_phase5_remaining")
os.environ.setdefault("SECRET_KEY", "test-key-not-for-production-use")

from app.runtime.provider.llm.types import RouteHint, StreamEvent, LLMResponse
from app.core.agents.subagent_executor import SubagentExecutor

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


# ════════════════════════════════════════════════════
# 1. subagent_executor 基本执行（无工具）
# ════════════════════════════════════════════════════
print("\n=== 1. subagent_executor 基本执行（无工具） ===")


async def test_subagent_basic():
    events: list[dict] = []

    async def event_cb(event):
        events.append(event)

    executor = SubagentExecutor(max_iterations=5)

    with patch("app.core.agents.subagent_executor.llm_adapter") as mock_adapter:
        mock_adapter.default_provider = "test-provider"
        mock_provider = MagicMock()
        mock_provider.default_model = "test-model"
        mock_adapter.get_provider.return_value = mock_provider
        mock_adapter.supports_tool_calls.return_value = False

        async def mock_chat(**kwargs):
            return {"content": "任务完成结果", "tool_calls": []}
        mock_adapter.chat = mock_chat

        result = await executor.execute(
            task="测试任务",
            event_callback=event_cb,
        )

    check("返回内容正确", result == "任务完成结果", f"got={result!r}")
    check("有 started 事件", any(e.get("status") == "started" for e in events))
    check("有 running 事件", any(e.get("status") == "running" for e in events))
    check("有 completed 事件", any(e.get("status") == "completed" for e in events))


asyncio.run(test_subagent_basic())


# ════════════════════════════════════════════════════
# 2. subagent_executor 工具调用（多轮循环）
# ════════════════════════════════════════════════════
print("\n=== 2. subagent_executor 工具调用 ===")

_call_count = 0


async def mock_chat_with_tools(**kwargs):
    global _call_count
    _call_count += 1
    if _call_count == 1:
        return {
            "content": "让我查看文件",
            "tool_calls": [{
                "id": "call_001",
                "type": "function",
                "function": {"name": "read_file", "arguments": '{"path":"test.txt"}'},
            }],
        }
    return {"content": "文件内容是测试数据", "tool_calls": []}


async def mock_execute_tool_call(tool_call):
    return {
        "role": "tool",
        "tool_call_id": tool_call.get("id", ""),
        "name": tool_call.get("function", {}).get("name", ""),
        "content": "test file content",
    }


async def test_subagent_tools():
    global _call_count
    _call_count = 0

    events: list[dict] = []

    async def event_cb(event):
        events.append(event)

    executor = SubagentExecutor(max_iterations=5)

    tools = [{"type": "function", "function": {"name": "read_file", "description": "read", "parameters": {}}}]

    with patch("app.core.agents.subagent_executor.llm_adapter") as mock_adapter:
        mock_adapter.default_provider = "test-provider"
        mock_provider = MagicMock()
        mock_provider.default_model = "test-model"
        mock_adapter.get_provider.return_value = mock_provider
        mock_adapter.supports_tool_calls.return_value = True
        mock_adapter.chat = mock_chat_with_tools

        with patch("app.core.agents.subagent_executor.tool_orchestrator") as mock_orch:
            from app.core.tools.orchestrator import tool_orchestrator as real_orch
            mock_orch.get_tools_for_llm.return_value = tools
            mock_orch.max_iterations = 10
            mock_orch.build_assistant_message_with_tool_calls = (
                real_orch.build_assistant_message_with_tool_calls
            )
            mock_orch.create_runner = real_orch.create_runner
            mock_orch.execute_tool_call = mock_execute_tool_call

            result = await executor.execute(
                task="读文件",
                event_callback=event_cb,
            )

    tool_call_events = [e for e in events if e.get("tool_name") == "read_file"]
    tool_result_events = [e for e in events if e.get("tool_output")]

    check("返回最终内容", result == "文件内容是测试数据", f"got={result!r}")
    check("LLM 被调用 2 次", _call_count == 2, f"call_count={_call_count}")
    check("有 tool_call 事件", len(tool_call_events) >= 1)
    check("有 tool_result 事件", len(tool_result_events) >= 1)
    check("tool_result 含内容", tool_result_events[0]["tool_output"] == "test file content")


asyncio.run(test_subagent_tools())


# ════════════════════════════════════════════════════
# 3. subagent_executor 取消
# ════════════════════════════════════════════════════
print("\n=== 3. subagent_executor 取消 ===")


async def test_subagent_cancel():
    cancel_event = asyncio.Event()
    cancel_event.set()  # 预先设置取消

    events: list[dict] = []

    async def event_cb(event):
        events.append(event)

    executor = SubagentExecutor(max_iterations=5)

    with patch("app.core.agents.subagent_executor.llm_adapter") as mock_adapter:
        mock_adapter.default_provider = "test-provider"
        mock_provider = MagicMock()
        mock_provider.default_model = "test-model"
        mock_adapter.get_provider.return_value = mock_provider
        mock_adapter.supports_tool_calls.return_value = False

        async def mock_chat(**kwargs):
            return {"content": "不应到达", "tool_calls": []}
        mock_adapter.chat = mock_chat

        result = await executor.execute(
            task="应被取消",
            event_callback=event_cb,
            cancel_event=cancel_event,
        )

    check("返回取消消息", "取消" in result, f"got={result!r}")


asyncio.run(test_subagent_cancel())


# ════════════════════════════════════════════════════
# 4. subagent_executor 达到最大迭代
# ════════════════════════════════════════════════════
print("\n=== 4. subagent_executor 达到最大迭代 ===")

_iter_call_count = 0


async def mock_chat_always_tools(**kwargs):
    global _iter_call_count
    _iter_call_count += 1
    return {
        "content": f"迭代{_iter_call_count}",
        "tool_calls": [{
            "id": f"call_{_iter_call_count}",
            "type": "function",
            "function": {"name": "read_file", "arguments": "{}"},
        }],
    }


async def test_subagent_max_iterations():
    global _iter_call_count
    _iter_call_count = 0

    events: list[dict] = []

    async def event_cb(event):
        events.append(event)

    executor = SubagentExecutor(max_iterations=2)

    tools = [{"type": "function", "function": {"name": "read_file", "description": "read", "parameters": {}}}]

    with patch("app.core.agents.subagent_executor.llm_adapter") as mock_adapter:
        mock_adapter.default_provider = "test-provider"
        mock_provider = MagicMock()
        mock_provider.default_model = "test-model"
        mock_adapter.get_provider.return_value = mock_provider
        mock_adapter.supports_tool_calls.return_value = True
        mock_adapter.chat = mock_chat_always_tools

        with patch("app.core.agents.subagent_executor.tool_orchestrator") as mock_orch:
            from app.core.tools.orchestrator import tool_orchestrator as real_orch
            mock_orch.get_tools_for_llm.return_value = tools
            mock_orch.max_iterations = 2
            mock_orch.build_assistant_message_with_tool_calls = (
                real_orch.build_assistant_message_with_tool_calls
            )
            mock_orch.create_runner = real_orch.create_runner
            mock_orch.execute_tool_call = mock_execute_tool_call

            result = await executor.execute(
                task="无限工具调用",
                event_callback=event_cb,
            )

    check("返回最大迭代消息", "最大" in result or "迭代" in result, f"got={result!r}")


asyncio.run(test_subagent_max_iterations())


# ════════════════════════════════════════════════════
# 5. group_chat 基本流式（无工具）
# ════════════════════════════════════════════════════
print("\n=== 5. group_chat 基本流式（无工具） ===")

from app.domains.social.group_chat import GroupChatManager


async def mock_chat_stream_basic(**kwargs):
    yield StreamEvent("content", {"content": "你好"})
    yield StreamEvent("content", {"content": "，世界"})
    yield StreamEvent("finish_reason", {"finish_reason": "stop"})


async def test_group_chat_basic():
    manager = GroupChatManager()
    agent = {"id": "agent-1", "name": "测试Agent", "is_active": True}
    member = {"agent_id": "agent-1", "name": "测试Agent", "role": "member"}
    group = {"id": "group-1", "name": "测试群"}

    # resolve_provider/resolve_model 使用 agent_orchestrator 模块自己的 llm_adapter
    # （懒加载、providers 为空），必须在 group_chat 命名空间直接 mock 才能命中
    with patch("app.domains.social.group_chat.resolve_provider", return_value="test-provider"), \
         patch("app.domains.social.group_chat.resolve_model", return_value="test-model"), \
         patch("app.domains.social.group_chat.llm_adapter") as mock_adapter:
        mock_adapter.chat_stream = mock_chat_stream_basic
        mock_adapter.supports_tool_calls.return_value = False
        mock_provider = MagicMock()
        mock_provider.default_model = "test-model"
        mock_adapter.providers = {"test-provider": mock_provider}
        mock_adapter.default_provider = "test-provider"
        with patch("app.domains.social.group_chat.tool_registry") as mock_registry:
            mock_registry.list_names.return_value = []
            with patch("app.domains.social.group_chat.agents_store") as mock_store:
                mock_store.get.return_value = agent

                events = []
                async for event in manager._respond_as_agent_stream(
                    group, member, "你好", "",
                ):
                    events.append(event)

    deltas = [e for e in events if e["type"] == "agent_message_delta"]
    ends = [e for e in events if e["type"] == "agent_message_end"]
    starts = [e for e in events if e["type"] == "agent_message_start"]

    check("有 agent_message_start", len(starts) == 1)
    check("有 2 个 agent_message_delta", len(deltas) == 2, f"got={len(deltas)}")
    check("第一个 delta content='你好'", deltas[0]["data"]["content"] == "你好")
    check("第二个 delta content='，世界'", deltas[1]["data"]["content"] == "，世界")
    check("有 agent_message_end", len(ends) == 1)
    check("end content 含完整内容", "你好" in ends[0]["data"]["content"] and "世界" in ends[0]["data"]["content"])


asyncio.run(test_group_chat_basic())


# ════════════════════════════════════════════════════
# 6. group_chat emotion 清洗
# ════════════════════════════════════════════════════
print("\n=== 6. group_chat emotion 清洗 ===")


async def mock_chat_stream_emotion(**kwargs):
    yield StreamEvent("content", {"content": "你好"})
    yield StreamEvent("content", {"content": "<exp:happy>"})
    yield StreamEvent("content", {"content": "今天不错"})
    yield StreamEvent("finish_reason", {"finish_reason": "stop"})


async def test_group_chat_emotion():
    manager = GroupChatManager()
    agent = {"id": "agent-1", "name": "测试Agent", "is_active": True}
    member = {"agent_id": "agent-1", "name": "测试Agent", "role": "member"}
    group = {"id": "group-1", "name": "测试群"}

    with patch("app.domains.social.group_chat.resolve_provider", return_value="test-provider"), \
         patch("app.domains.social.group_chat.resolve_model", return_value="test-model"), \
         patch("app.domains.social.group_chat.llm_adapter") as mock_adapter:
        mock_adapter.chat_stream = mock_chat_stream_emotion
        mock_adapter.supports_tool_calls.return_value = False
        mock_provider = MagicMock()
        mock_provider.default_model = "test-model"
        mock_adapter.providers = {"test-provider": mock_provider}
        mock_adapter.default_provider = "test-provider"
        with patch("app.domains.social.group_chat.tool_registry") as mock_registry:
            mock_registry.list_names.return_value = []
            with patch("app.domains.social.group_chat.agents_store") as mock_store:
                mock_store.get.return_value = agent

                events = []
                async for event in manager._respond_as_agent_stream(
                    group, member, "你好", "",
                ):
                    events.append(event)

    deltas = [e for e in events if e["type"] == "agent_message_delta"]
    all_content = "".join(d["data"]["content"] for d in deltas)

    check("content 无 <exp: 标签", "<exp:" not in all_content, f"content={all_content!r}")
    check("有 content delta", len(deltas) >= 2)


asyncio.run(test_group_chat_emotion())


# ════════════════════════════════════════════════════
# 7. group_chat 工具调用
# ════════════════════════════════════════════════════
print("\n=== 7. group_chat 工具调用 ===")

_gc_call_count = 0


async def mock_chat_stream_with_tools(**kwargs):
    global _gc_call_count
    _gc_call_count += 1
    if _gc_call_count == 1:
        yield StreamEvent("content", {"content": "让我搜索"})
        yield StreamEvent("tool_call_delta", {
            "index": 0,
            "tool_call_id": "call_gc_1",
            "function_name": "memory_search",
            "function_arguments": '{"query":"test"}',
        })
        yield StreamEvent("finish_reason", {"finish_reason": "tool_calls"})
    else:
        yield StreamEvent("content", {"content": "搜索完成，结果是..."})
        yield StreamEvent("finish_reason", {"finish_reason": "stop"})


async def mock_gc_execute_tool_call(tool_call):
    return {
        "role": "tool",
        "tool_call_id": tool_call.get("id", ""),
        "name": tool_call.get("function", {}).get("name", ""),
        "content": "找到 3 条记忆",
    }


async def test_group_chat_tools():
    global _gc_call_count
    _gc_call_count = 0

    manager = GroupChatManager()
    agent = {"id": "agent-1", "name": "测试Agent", "is_active": True}
    member = {"agent_id": "agent-1", "name": "测试Agent", "role": "member"}
    group = {"id": "group-1", "name": "测试群"}

    tools = [{"type": "function", "function": {"name": "memory_search", "description": "search", "parameters": {}}}]

    with patch("app.domains.social.group_chat.resolve_provider", return_value="test-provider"), \
         patch("app.domains.social.group_chat.resolve_model", return_value="test-model"), \
         patch("app.domains.social.group_chat.llm_adapter") as mock_adapter:
        mock_adapter.chat_stream = mock_chat_stream_with_tools
        mock_adapter.supports_tool_calls.return_value = True
        mock_provider = MagicMock()
        mock_provider.default_model = "test-model"
        mock_adapter.providers = {"test-provider": mock_provider}
        mock_adapter.default_provider = "test-provider"
        with patch("app.domains.social.group_chat.tool_registry") as mock_registry:
            mock_registry.list_names.return_value = ["memory_search"]
            with patch("app.domains.social.group_chat.agents_store") as mock_store:
                mock_store.get.return_value = agent
                with patch("app.domains.social.group_chat.tool_orchestrator") as mock_orch:
                    from app.core.tools.orchestrator import tool_orchestrator as real_orch
                    mock_orch.get_tools_for_llm.return_value = tools
                    mock_orch.max_iterations = 10
                    mock_orch.build_assistant_message_with_tool_calls = (
                        real_orch.build_assistant_message_with_tool_calls
                    )
                    mock_orch.create_runner = real_orch.create_runner
                    mock_orch.execute_tool_call = mock_gc_execute_tool_call

                    events = []
                    async for event in manager._respond_as_agent_stream(
                        group, member, "搜索记忆", "",
                    ):
                        events.append(event)

    deltas = [e for e in events if e["type"] == "agent_message_delta"]
    ends = [e for e in events if e["type"] == "agent_message_end"]

    all_content = "".join(d["data"]["content"] for d in deltas)
    check("有 content delta", len(deltas) >= 2, f"got={len(deltas)}")
    check("content 含两轮内容", "让我搜索" in all_content and "搜索完成" in all_content,
          f"content={all_content!r}")
    check("有 agent_message_end", len(ends) == 1)
    check("LLM 被调用 2 次", _gc_call_count == 2, f"call_count={_gc_call_count}")


asyncio.run(test_group_chat_tools())


# ════════════════════════════════════════════════════
# 8. group_chat LLM 异常
# ════════════════════════════════════════════════════
print("\n=== 8. group_chat LLM 异常 ===")


async def mock_chat_stream_error(**kwargs):
    yield StreamEvent("content", {"content": "部分内容"})
    raise RuntimeError("LLM 连接中断")


async def test_group_chat_error():
    manager = GroupChatManager()
    agent = {"id": "agent-1", "name": "测试Agent", "is_active": True}
    member = {"agent_id": "agent-1", "name": "测试Agent", "role": "member"}
    group = {"id": "group-1", "name": "测试群"}

    with patch("app.domains.social.group_chat.resolve_provider", return_value="test-provider"), \
         patch("app.domains.social.group_chat.resolve_model", return_value="test-model"), \
         patch("app.domains.social.group_chat.llm_adapter") as mock_adapter:
        mock_adapter.chat_stream = mock_chat_stream_error
        mock_adapter.supports_tool_calls.return_value = False
        mock_provider = MagicMock()
        mock_provider.default_model = "test-model"
        mock_adapter.providers = {"test-provider": mock_provider}
        mock_adapter.default_provider = "test-provider"
        with patch("app.domains.social.group_chat.tool_registry") as mock_registry:
            mock_registry.list_names.return_value = []
            with patch("app.domains.social.group_chat.agents_store") as mock_store:
                mock_store.get.return_value = agent

                events = []
                async for event in manager._respond_as_agent_stream(
                    group, member, "你好", "",
                ):
                    events.append(event)

    errors = [e for e in events if e["type"] == "agent_error"]
    deltas = [e for e in events if e["type"] == "agent_message_delta"]

    check("有 agent_error 事件", len(errors) == 1, f"got={len(errors)}")
    check("error content 含中断信息", "中断" in errors[0]["data"]["content"],
          f"content={errors[0]['data']['content']!r}")
    check("部分内容已推送", len(deltas) >= 1)


asyncio.run(test_group_chat_error())


# ════════════════════════════════════════════════════
# 结果汇总
# ════════════════════════════════════════════════════
print("\n" + "=" * 60)
print(f"test_phase5_remaining 结果: {passed} passed, {failed} failed")
print("=" * 60)
sys.exit(0 if failed == 0 else 1)
