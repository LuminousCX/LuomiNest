"""Phase 4 集成测试: AgentRunner（统一工具调用循环）。

验证：
1. run_stream 流式循环（mock llm_call_fn 产出 StreamEvent）
2. run_non_stream 非流式循环
3. 工具调用后继续循环
4. max_iterations 边界终止
5. 无 tool_calls 时终止
6. SSE 事件格式正确（ChatStreamChunk 字段）

运行方式：python tests/integration/test_agent_runner.py
"""
import os
import sys
import asyncio
import json

sys.path.insert(0, r"d:\Projects\Project\LuomiNest\backend")
os.environ.setdefault("DATA_DIR", "/tmp/luominest_test_runner")
os.environ.setdefault("SECRET_KEY", "test-key-not-for-production-use")

from app.core.agents.middleware.base import AgentContext
from app.core.agents.middleware.builtin import SSEEmitMiddleware, ToolExecutionMiddleware
from app.core.agents.middleware.pipeline import MiddlewarePipeline
from app.core.agents.middleware.runner import AgentRunner
from app.runtime.provider.llm.types import LLMResponse, RouteHint, StreamEvent
from app.schemas.chat import ChatStreamChunk


def make_sse_pipeline() -> MiddlewarePipeline:
    """创建含 SSE 发射中间件的管道（用于验证 tool_calls/tool_event SSE 格式）。"""
    return MiddlewarePipeline([SSEEmitMiddleware(), ToolExecutionMiddleware()])

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


def make_ctx(tools=None) -> AgentContext:
    """创建测试用 AgentContext。"""
    ctx = AgentContext(
        messages=[{"role": "user", "content": "hello"}],
        tools=tools,
        route_hint=RouteHint.CHAT,
        state={
            "chat_id": "test-chat-id",
            "model": "test-model",
            "provider": "test-provider",
            "content": "",
            "reasoning": "",
        },
        extra={"scene": "chat", "is_stream": True},
    )
    return ctx


def make_mock_execute_fn(results: dict[str, str] | None = None):
    """创建 mock 工具执行函数。

    Args:
        results: {tool_name: output} 映射，默认返回 "tool_result"
    """
    results = results or {}

    async def execute_fn(tool_call):
        name = tool_call.get("function", {}).get("name", "unknown")
        output = results.get(name, f"result_of_{name}")
        return {
            "role": "tool",
            "tool_call_id": tool_call.get("id", ""),
            "name": name,
            "content": output,
        }

    return execute_fn


def parse_sse(sse_str: str) -> dict:
    """解析 SSE 字符串为 ChatStreamChunk dict。"""
    # 格式: "data: {json}\n\n"
    assert sse_str.startswith("data: "), f"非 SSE 格式: {sse_str[:30]}"
    assert sse_str.endswith("\n\n"), f"SSE 缺少终止符: {sse_str[-4:]}"
    json_str = sse_str[len("data: "):-2]
    return json.loads(json_str)


# ════════════════════════════════════════════════════
# 1. run_stream 流式循环（无工具调用，单轮终止）
# ════════════════════════════════════════════════════
print("\n=== 1. run_stream 流式循环（无工具调用） ===")

async def test_run_stream_basic():
    ctx = make_ctx()
    pipeline = MiddlewarePipeline([])
    runner = AgentRunner(pipeline, max_iterations=5, execute_fn=make_mock_execute_fn())

    async def llm_call_fn(ctx):
        yield StreamEvent("content", {"content": "Hello"})
        yield StreamEvent("content", {"content": " world"})
        yield StreamEvent("finish_reason", {"finish_reason": "stop"})

    sse_events = []
    async for sse in runner.run_stream(ctx, llm_call_fn):
        sse_events.append(sse)

    check("产出 SSE 事件", len(sse_events) >= 2)
    check("iteration 仍为 0（无工具调用）", ctx.iteration == 0)
    check("state.content 累积", ctx.state.get("content") == "Hello world",
          f"got={ctx.state.get('content')!r}")
    check("state.aborted 为 False", not ctx.state.get("aborted"))

    # 验证 SSE 格式
    chunk0 = parse_sse(sse_events[0])
    check("SSE id 正确", chunk0["id"] == "test-chat-id")
    check("SSE model 正确", chunk0["model"] == "test-model")
    check("SSE provider 正确", chunk0["provider"] == "test-provider")
    check("SSE content 第一个 chunk", chunk0["content"] == "Hello")

    chunk1 = parse_sse(sse_events[1])
    check("SSE content 第二个 chunk", chunk1["content"] == " world")

asyncio.run(test_run_stream_basic())


# ════════════════════════════════════════════════════
# 2. run_stream reasoning 事件
# ════════════════════════════════════════════════════
print("\n=== 2. run_stream reasoning 事件 ===")

async def test_run_stream_reasoning():
    ctx = make_ctx()
    pipeline = MiddlewarePipeline([])
    runner = AgentRunner(pipeline, max_iterations=5, execute_fn=make_mock_execute_fn())

    async def llm_call_fn(ctx):
        yield StreamEvent("reasoning", {"reasoning": "thinking..."})
        yield StreamEvent("content", {"content": "answer"})
        yield StreamEvent("finish_reason", {"finish_reason": "stop"})

    sse_events = []
    async for sse in runner.run_stream(ctx, llm_call_fn):
        sse_events.append(sse)

    check("产出 2 个 SSE 事件", len(sse_events) == 2)
    chunk0 = parse_sse(sse_events[0])
    check("reasoning SSE content 为空", chunk0["content"] == "")
    check("reasoning SSE reasoning_content 正确", chunk0["reasoning_content"] == "thinking...")
    check("state.reasoning 累积", ctx.state.get("reasoning") == "thinking...")

asyncio.run(test_run_stream_reasoning())


# ════════════════════════════════════════════════════
# 3. run_stream 工具调用后继续循环
# ════════════════════════════════════════════════════
print("\n=== 3. run_stream 工具调用后继续循环 ===")

async def test_run_stream_tool_continuation():
    ctx = make_ctx()
    pipeline = make_sse_pipeline()
    runner = AgentRunner(pipeline, max_iterations=5, execute_fn=make_mock_execute_fn())

    call_count = [0]

    async def llm_call_fn(ctx):
        if call_count[0] == 0:
            call_count[0] += 1
            yield StreamEvent("content", {"content": "Let me check."})
            yield StreamEvent("tool_call_delta", {
                "index": 0,
                "tool_call_id": "call_1",
                "function_name": "memory_search",
                "function_arguments": '{"query": "test"}',
            })
            yield StreamEvent("finish_reason", {"finish_reason": "tool_calls"})
        else:
            yield StreamEvent("content", {"content": "Done."})
            yield StreamEvent("finish_reason", {"finish_reason": "stop"})

    sse_events = []
    async for sse in runner.run_stream(ctx, llm_call_fn):
        sse_events.append(sse)

    check("LLM 被调用 2 次", call_count[0] == 1, f"call_count={call_count[0]}")
    check("iteration 推进到 1", ctx.iteration == 1)
    check("state.content 包含两轮内容",
          "Let me check." in ctx.state.get("content", "") and
          "Done." in ctx.state.get("content", ""),
          f"got={ctx.state.get('content')!r}")

    # 验证 messages 包含 assistant + tool 消息
    roles = [m.get("role") for m in ctx.messages]
    check("messages 含 assistant 消息（带 tool_calls）", "assistant" in roles)
    check("messages 含 tool 消息", "tool" in roles)
    check("messages 总数 = user + assistant + tool = 3", len(ctx.messages) == 3,
          f"got={len(ctx.messages)}")

    # 验证 SSE 中包含 tool_calls 公告
    has_tool_calls_sse = False
    has_tool_event_sse = False
    for sse in sse_events:
        chunk = parse_sse(sse)
        if chunk.get("tool_calls"):
            has_tool_calls_sse = True
        if chunk.get("tool_event"):
            has_tool_event_sse = True
    check("SSE 包含 tool_calls 公告", has_tool_calls_sse)
    check("SSE 包含 tool_event 事件", has_tool_event_sse)

asyncio.run(test_run_stream_tool_continuation())


# ════════════════════════════════════════════════════
# 4. run_stream max_iterations 边界终止
# ════════════════════════════════════════════════════
print("\n=== 4. run_stream max_iterations 边界终止 ===")

async def test_run_stream_max_iterations():
    ctx = make_ctx()
    pipeline = MiddlewarePipeline([])
    # max_iterations=2，LLM 每次都返回工具调用，应被 LoopGuard 终止
    # 但这里管道为空（无 LoopGuard），靠 runner 的 while 条件终止
    runner = AgentRunner(pipeline, max_iterations=2, execute_fn=make_mock_execute_fn())

    call_count = [0]

    async def llm_call_fn(ctx):
        call_count[0] += 1
        yield StreamEvent("content", {"content": f"iter{ctx.iteration}"})
        yield StreamEvent("tool_call_delta", {
            "index": 0,
            "tool_call_id": f"call_{ctx.iteration}",
            "function_name": "memory_search",
            "function_arguments": "{}",
        })
        yield StreamEvent("finish_reason", {"finish_reason": "tool_calls"})

    sse_events = []
    async for sse in runner.run_stream(ctx, llm_call_fn):
        sse_events.append(sse)

    # while ctx.iteration <= max_iterations: 迭代 0,1,2 共 3 次
    # iteration 0: stream → tools → iteration=1
    # iteration 1: stream → tools → iteration=2
    # iteration 2: while 2<=2 True → stream → tools → iteration=3
    # iteration 3: while 3<=2 False → exit
    # 但实际 iteration 2 执行后 iteration 变为 3，while 条件 3<=2 False 退出
    # 所以 LLM 被调用 3 次（iteration 0,1,2）
    check("LLM 被调用 3 次（iteration 0,1,2）", call_count[0] == 3,
          f"call_count={call_count[0]}")
    check("最终 iteration=3", ctx.iteration == 3, f"got={ctx.iteration}")

asyncio.run(test_run_stream_max_iterations())


# ════════════════════════════════════════════════════
# 5. run_stream 无 tool_calls 时终止
# ════════════════════════════════════════════════════
print("\n=== 5. run_stream 无 tool_calls 时终止 ===")

async def test_run_stream_no_tool_calls():
    ctx = make_ctx(tools=[{"type": "function", "function": {"name": "noop"}}])
    pipeline = MiddlewarePipeline([])
    runner = AgentRunner(pipeline, max_iterations=5, execute_fn=make_mock_execute_fn())

    async def llm_call_fn(ctx):
        yield StreamEvent("content", {"content": "just text"})
        yield StreamEvent("finish_reason", {"finish_reason": "stop"})

    sse_events = []
    async for sse in runner.run_stream(ctx, llm_call_fn):
        sse_events.append(sse)

    check("仅 1 个 content SSE", len(sse_events) == 1)
    check("iteration 仍为 0", ctx.iteration == 0)
    check("state.content = 'just text'", ctx.state.get("content") == "just text")
    check("messages 仅含原始 user 消息", len(ctx.messages) == 1)

asyncio.run(test_run_stream_no_tool_calls())


# ════════════════════════════════════════════════════
# 6. run_non_stream 非流式循环（无工具调用）
# ════════════════════════════════════════════════════
print("\n=== 6. run_non_stream 非流式循环（无工具调用） ===")

async def test_run_non_stream_basic():
    ctx = make_ctx()
    pipeline = MiddlewarePipeline([])
    runner = AgentRunner(pipeline, max_iterations=5, execute_fn=make_mock_execute_fn())

    async def llm_call_fn(ctx):
        return LLMResponse(content="Final answer", finish_reason="stop")

    state = await runner.run_non_stream(ctx, llm_call_fn)

    check("state.content = 'Final answer'", state.get("content") == "Final answer")
    check("state.tool_calls 为空", state.get("tool_calls") == [])
    check("iteration 仍为 0", ctx.iteration == 0)
    check("state.aborted 为 False", not state.get("aborted"))

asyncio.run(test_run_non_stream_basic())


# ════════════════════════════════════════════════════
# 7. run_non_stream 工具调用后继续循环
# ════════════════════════════════════════════════════
print("\n=== 7. run_non_stream 工具调用后继续循环 ===")

async def test_run_non_stream_tool_continuation():
    ctx = make_ctx()
    pipeline = MiddlewarePipeline([])
    runner = AgentRunner(pipeline, max_iterations=5, execute_fn=make_mock_execute_fn())

    call_count = [0]

    async def llm_call_fn(ctx):
        if call_count[0] == 0:
            call_count[0] += 1
            return LLMResponse(
                content="Checking",
                tool_calls=[{
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "memory_search", "arguments": "{}"},
                }],
                finish_reason="tool_calls",
            )
        return LLMResponse(content="Done", finish_reason="stop")

    state = await runner.run_non_stream(ctx, llm_call_fn)

    check("LLM 被调用 2 次", call_count[0] == 1)
    check("iteration 推进到 1", ctx.iteration == 1)
    check("state.content = 'Done'（最后一轮覆盖）", state.get("content") == "Done")
    check("messages 总数 = user + assistant + tool + assistant = 4",
          len(ctx.messages) == 4, f"got={len(ctx.messages)}")

    # 验证 messages 结构
    roles = [m.get("role") for m in ctx.messages]
    check("messages 角色序列正确",
          roles == ["user", "assistant", "tool", "assistant"],
          f"got={roles}")
    # 第一个 assistant 含 tool_calls
    check("第一个 assistant 含 tool_calls",
          bool(ctx.messages[1].get("tool_calls")))
    # tool 消息 content
    check("tool 消息 content 正确",
          ctx.messages[2].get("content") == "result_of_memory_search")

asyncio.run(test_run_non_stream_tool_continuation())


# ════════════════════════════════════════════════════
# 8. run_non_stream max_iterations 边界终止
# ════════════════════════════════════════════════════
print("\n=== 8. run_non_stream max_iterations 边界终止 ===")

async def test_run_non_stream_max_iterations():
    ctx = make_ctx()
    pipeline = MiddlewarePipeline([])
    runner = AgentRunner(pipeline, max_iterations=2, execute_fn=make_mock_execute_fn())

    call_count = [0]

    async def llm_call_fn(ctx):
        call_count[0] += 1
        return LLMResponse(
            content=f"iter{ctx.iteration}",
            tool_calls=[{
                "id": f"call_{ctx.iteration}",
                "type": "function",
                "function": {"name": "memory_search", "arguments": "{}"},
            }],
            finish_reason="tool_calls",
        )

    state = await runner.run_non_stream(ctx, llm_call_fn)

    # while ctx.iteration <= 2: 迭代 0,1,2 共 3 次
    check("LLM 被调用 3 次（iteration 0,1,2）", call_count[0] == 3,
          f"call_count={call_count[0]}")
    check("最终 iteration=3", ctx.iteration == 3, f"got={ctx.iteration}")

asyncio.run(test_run_non_stream_max_iterations())


# ════════════════════════════════════════════════════
# 9. run_non_stream 兼容 dict 响应（return_raw=True 格式）
# ════════════════════════════════════════════════════
print("\n=== 9. run_non_stream 兼容 dict 响应 ===")

async def test_run_non_stream_dict_response():
    ctx = make_ctx()
    pipeline = MiddlewarePipeline([])
    runner = AgentRunner(pipeline, max_iterations=5, execute_fn=make_mock_execute_fn())

    async def llm_call_fn(ctx):
        return {
            "content": "dict response",
            "tool_calls": [],
            "role": "assistant",
        }

    state = await runner.run_non_stream(ctx, llm_call_fn)

    check("dict 响应 content 正确", state.get("content") == "dict response")
    check("dict 响应 tool_calls 为空", state.get("tool_calls") == [])

asyncio.run(test_run_non_stream_dict_response())


# ════════════════════════════════════════════════════
# 10. SSE 事件格式正确（ChatStreamChunk 字段完整）
# ════════════════════════════════════════════════════
print("\n=== 10. SSE 事件格式正确（ChatStreamChunk 字段） ===")

async def test_sse_format():
    ctx = make_ctx()
    pipeline = make_sse_pipeline()
    runner = AgentRunner(pipeline, max_iterations=5, execute_fn=make_mock_execute_fn())

    async def llm_call_fn(ctx):
        yield StreamEvent("content", {"content": "text"})
        yield StreamEvent("tool_call_delta", {
            "index": 0,
            "tool_call_id": "call_x",
            "function_name": "memory_search",
            "function_arguments": "{}",
        })
        yield StreamEvent("finish_reason", {"finish_reason": "tool_calls"})

    sse_events = []
    async for sse in runner.run_stream(ctx, llm_call_fn):
        sse_events.append(sse)

    # 第一个 SSE：content
    content_chunk = parse_sse(sse_events[0])
    check("content SSE 含 id 字段", "id" in content_chunk)
    check("content SSE 含 content 字段", "content" in content_chunk)
    check("content SSE 含 reasoning_content 字段", "reasoning_content" in content_chunk)
    check("content SSE 含 model 字段", "model" in content_chunk)
    check("content SSE 含 provider 字段", "provider" in content_chunk)
    check("content SSE 含 done 字段", "done" in content_chunk)
    check("content SSE done=False", content_chunk["done"] is False)
    check("content SSE content='text'", content_chunk["content"] == "text")
    check("content SSE reasoning_content=''", content_chunk["reasoning_content"] == "")

    # 后续 SSE 应包含 tool_calls 和 tool_event
    found_tool_calls = False
    found_tool_event_started = False
    found_tool_event_completed = False
    for sse in sse_events[1:]:
        chunk = parse_sse(sse)
        if chunk.get("tool_calls"):
            found_tool_calls = True
            check("tool_calls SSE 含 iteration", "iteration" in chunk)
            check("tool_calls SSE 含 tool_calls 列表", isinstance(chunk["tool_calls"], list))
            check("tool_calls SSE 第一个 tool_call 含 id",
                  chunk["tool_calls"][0].get("id") == "call_x")
        if chunk.get("tool_event"):
            te = chunk["tool_event"]
            if te.get("status") == "started":
                found_tool_event_started = True
            if te.get("status") == "completed":
                found_tool_event_completed = True
                check("tool_event completed 含 output", "output" in te)

    check("SSE 包含 tool_calls 公告", found_tool_calls)
    check("SSE 包含 tool_event started", found_tool_event_started)
    check("SSE 包含 tool_event completed", found_tool_event_completed)

    # 验证所有 SSE 都能被 ChatStreamChunk 解析（向前端兼容）
    for sse in sse_events:
        json_str = sse[len("data: "):-2]
        chunk = ChatStreamChunk.model_validate_json(json_str)
        check(f"ChatStreamChunk 解析成功 (content={chunk.content!r})", True)

asyncio.run(test_sse_format())


# ════════════════════════════════════════════════════
# 11. tool_orchestrator.create_runner 集成验证
# ════════════════════════════════════════════════════
print("\n=== 11. tool_orchestrator.create_runner 集成验证 ===")

async def test_create_runner():
    from app.core.tools.orchestrator import tool_orchestrator

    # chat 场景
    runner_chat = tool_orchestrator.create_runner({
        "scene": "chat",
        "is_stream": True,
        "max_iterations": 3,
        "execute_fn": make_mock_execute_fn(),
    })
    check("chat 场景 runner 创建成功", runner_chat is not None)
    check("chat 场景 max_iterations=3", runner_chat._max_iterations == 3)
    check("chat 场景管道含中间件", len(runner_chat._pipeline.middlewares) > 0)

    # subagent 场景
    runner_sub = tool_orchestrator.create_runner({
        "scene": "subagent",
        "is_stream": False,
        "max_iterations": 5,
        "execute_fn": make_mock_execute_fn(),
    })
    check("subagent 场景 runner 创建成功", runner_sub is not None)

    # group 场景
    runner_group = tool_orchestrator.create_runner({
        "scene": "group",
        "is_stream": True,
        "execute_fn": make_mock_execute_fn(),
    })
    check("group 场景 runner 创建成功", runner_group is not None)

    # 验证 chat 场景管道中间件数量（MemoryAccess + ToolFilter + LoopGuard + SSEEmit + ToolExec + SpecialTool + UsageTrack = 7）
    chat_mw_count = len(runner_chat._pipeline.middlewares)
    check("chat 场景含 7 个中间件", chat_mw_count == 7, f"got={chat_mw_count}")

    # subagent 场景（无 SSEEmit + 无 SpecialTool + 有 SubagentCancel = 6）
    sub_mw_count = len(runner_sub._pipeline.middlewares)
    check("subagent 场景含 6 个中间件", sub_mw_count == 6, f"got={sub_mw_count}")

    # group 场景（无 SubagentCancel + 无 SpecialTool = 6）
    group_mw_count = len(runner_group._pipeline.middlewares)
    check("group 场景含 6 个中间件", group_mw_count == 6, f"got={group_mw_count}")

asyncio.run(test_create_runner())


# ════════════════════════════════════════════════════
# 12. ToolFilterMiddleware 工具过滤
# ════════════════════════════════════════════════════
print("\n=== 12. ToolFilterMiddleware 工具过滤 ===")

async def test_tool_filter():
    from app.core.agents.middleware.builtin import ToolFilterMiddleware

    ctx = AgentContext(
        messages=[],
        tools=[
            {"type": "function", "function": {"name": "memory_search"}},
            {"type": "function", "function": {"name": "read_file"}},
            {"type": "function", "function": {"name": "delegate_to_subagent"}},
        ],
        state={},
        extra={"disable_tools": ["delegate_to_subagent"]},
    )
    pipeline = MiddlewarePipeline([ToolFilterMiddleware()])
    await pipeline.run_before_agent(ctx)

    tool_names = [t["function"]["name"] for t in ctx.tools]
    check("disable_tools 过滤掉 delegate_to_subagent",
          "delegate_to_subagent" not in tool_names)
    check("保留 memory_search", "memory_search" in tool_names)
    check("保留 read_file", "read_file" in tool_names)

    # 白名单过滤
    ctx2 = AgentContext(
        messages=[],
        tools=[
            {"type": "function", "function": {"name": "memory_search"}},
            {"type": "function", "function": {"name": "read_file"}},
        ],
        state={},
        extra={"tool_whitelist": {"memory_search"}},
    )
    pipeline2 = MiddlewarePipeline([ToolFilterMiddleware()])
    await pipeline2.run_before_agent(ctx2)
    tool_names2 = [t["function"]["name"] for t in ctx2.tools]
    check("白名单仅保留 memory_search",
          tool_names2 == ["memory_search"], f"got={tool_names2}")

    # 过滤后为空 → None
    ctx3 = AgentContext(
        messages=[],
        tools=[
            {"type": "function", "function": {"name": "memory_search"}},
        ],
        state={},
        extra={"disable_tools": ["memory_search"]},
    )
    pipeline3 = MiddlewarePipeline([ToolFilterMiddleware()])
    await pipeline3.run_before_agent(ctx3)
    check("过滤后为空设为 None", ctx3.tools is None)

asyncio.run(test_tool_filter())


# ════════════════════════════════════════════════════
# 13. LoopGuardMiddleware 边界检测
# ════════════════════════════════════════════════════
print("\n=== 13. LoopGuardMiddleware 边界检测 ===")

async def test_loop_guard():
    from app.core.agents.middleware.builtin import LoopGuardMiddleware

    ctx = AgentContext(messages=[], state={"iteration_content": "ok", "tool_calls": []})

    # iteration < max → 不中止
    mw = LoopGuardMiddleware(max_iterations=5)
    ctx.iteration = 3
    await mw.after_model(ctx, None)
    check("iteration=3 < max=5 不中止", not ctx.state.get("aborted"))

    # iteration >= max → 中止
    ctx.iteration = 5
    await mw.after_model(ctx, None)
    check("iteration=5 >= max=5 中止", ctx.state.get("aborted") is True)
    ctx.state.pop("aborted", None)

    # 无进展（空内容 + 无工具调用）→ 中止
    ctx.iteration = 1
    ctx.state["iteration_content"] = ""
    ctx.state["tool_calls"] = []
    await mw.after_model(ctx, None)
    check("无进展（空内容+无工具调用）中止", ctx.state.get("aborted") is True)

asyncio.run(test_loop_guard())


# ════════════════════════════════════════════════════
# 14. SubagentCancelMiddleware 取消检测
# ════════════════════════════════════════════════════
print("\n=== 14. SubagentCancelMiddleware 取消检测 ===")

async def test_subagent_cancel():
    import asyncio as _asyncio
    from app.core.agents.middleware.builtin import SubagentCancelMiddleware

    ctx = AgentContext(messages=[], state={})
    mw = SubagentCancelMiddleware()

    # 未设置 cancel_event → 不中止
    await mw.before_model(ctx)
    check("无 cancel_event 不中止", not ctx.state.get("aborted"))

    # cancel_event 未触发 → 不中止
    event = _asyncio.Event()
    ctx.extra["cancel_event"] = event
    await mw.before_model(ctx)
    check("cancel_event 未触发不中止", not ctx.state.get("aborted"))

    # cancel_event 触发 → 中止
    event.set()
    await mw.before_model(ctx)
    check("cancel_event 触发后中止", ctx.state.get("aborted") is True)

asyncio.run(test_subagent_cancel())


# ════════════════════════════════════════════════════
# 15. MemoryAccessMiddleware contextvar 设置/重置
# ════════════════════════════════════════════════════
print("\n=== 15. MemoryAccessMiddleware contextvar 设置/重置 ===")

async def test_memory_access():
    from app.core.agents.middleware.builtin import MemoryAccessMiddleware
    from app.core.agents.memory_access import (
        get_luominest_memory_access,
        MEMORY_ACCESS_READ_WRITE,
        MEMORY_ACCESS_NONE,
    )

    # 初始默认值
    initial = get_luominest_memory_access()
    check("初始 memory_access 为 NONE", initial == MEMORY_ACCESS_NONE)

    ctx = AgentContext(
        messages=[], state={},
        extra={"memory_access": MEMORY_ACCESS_READ_WRITE},
    )
    pipeline = MiddlewarePipeline([MemoryAccessMiddleware()])

    # before_agent 设置 contextvar
    await pipeline.run_before_agent(ctx)
    check("before_agent 设置 memory_access=READ_WRITE",
          get_luominest_memory_access() == MEMORY_ACCESS_READ_WRITE)

    # after_agent 重置 contextvar
    await pipeline.run_after_agent(ctx)
    check("after_agent 重置 memory_access=NONE",
          get_luominest_memory_access() == MEMORY_ACCESS_NONE)

asyncio.run(test_memory_access())


# ════════════════════════════════════════════════════
# 结果汇总
# ════════════════════════════════════════════════════
print(f"\n{'=' * 60}")
print(f"test_agent_runner 结果: {passed} passed, {failed} failed")
print(f"{'=' * 60}")
sys.exit(0 if failed == 0 else 1)
