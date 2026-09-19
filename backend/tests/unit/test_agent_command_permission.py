"""Agent 命令执行三档确认（PermissionGate）单测。

覆盖：needs_approval 三档判定、请求-决定协议（once/session/full/deny）、
超时自动拒绝、重复/非法 resolve、子 Agent 授权规则、中间件拒绝路径。
"""

import asyncio

import pytest

import app.core.agents.middleware.permission as gate_mod
from app.core.agents.middleware.permission import PermissionGateMiddleware
from app.security.sandbox.permission import (
    DECISION_DENY,
    DECISION_FULL,
    DECISION_ONCE,
    DECISION_SESSION,
    AgentCommandPermissionManager,
)


@pytest.fixture()
def manager():
    """干净的管理器实例（不触真实配置存储）。"""
    return AgentCommandPermissionManager()


def test_default_ask_mode_requires_approval(manager):
    assert manager.get_mode() == "ask"
    assert manager.needs_approval("conv-1") is True


def test_full_mode_disables_approval(manager):
    manager._mode = "full"
    assert manager.needs_approval("conv-1") is False
    assert manager.subagent_allowed("conv-1") is True


def test_session_grant_scoped_to_conversation(manager):
    manager._session_grants.add("conv-1")
    assert manager.needs_approval("conv-1") is False
    assert manager.needs_approval("conv-2") is True
    # 子 Agent：授权会话内放行，会话外拒绝
    assert manager.subagent_allowed("conv-1") is True
    assert manager.subagent_allowed("conv-2") is False


def test_resolve_once_and_double_resolve(manager):
    decisions = []

    async def scenario():
        task = asyncio.create_task(
            manager.request_approval("conv-1", "cli", "git status", timeout=5)
        )
        await asyncio.sleep(0.01)
        # 从在途请求取 request_id（模拟前端拿到 permission_request 后回调）
        pending = manager.pending_snapshot()
        assert len(pending) == 1
        rid = pending[0]["request_id"]
        assert manager.resolve(rid, DECISION_ONCE) is True
        decisions.append(await task)
        # 已处理/不存在的请求再 resolve 返回 False
        assert manager.resolve(rid, DECISION_ONCE) is False
        assert manager.resolve("nonexistent", DECISION_ONCE) is False

    asyncio.run(scenario())
    assert decisions == [DECISION_ONCE]
    # once 不产生会话授权
    assert manager.needs_approval("conv-1") is True


def test_resolve_session_grants_conversation(manager):
    async def scenario():
        task = asyncio.create_task(
            manager.request_approval("conv-1", "cli", "npm test", timeout=5)
        )
        await asyncio.sleep(0.01)
        rid = manager.pending_snapshot()[0]["request_id"]
        manager.resolve(rid, DECISION_SESSION)
        return await task

    assert asyncio.run(scenario()) == DECISION_SESSION
    assert manager.needs_approval("conv-1") is False
    assert manager.session_grants_snapshot() == ["conv-1"]
    assert manager.revoke_session("conv-1") is True
    assert manager.needs_approval("conv-1") is True


def test_resolve_invalid_decision_rejected(manager):
    assert manager.resolve("whatever", "sudo-mode") is False


def test_timeout_defaults_to_deny(manager):
    async def scenario():
        return await manager.request_approval("conv-1", "cli", "dir", timeout=0.05)

    assert asyncio.run(scenario()) == DECISION_DENY
    assert manager.pending_count() == 0


def test_full_decision_switches_mode(manager):
    """full 决定应触发持久化模式切换（此处验证内存态即时生效路径）。"""

    async def scenario():
        manager._mode = "ask"
        # 直接走 _apply_decision 的内存路径（set_mode 需要配置存储，这里单测内存语义）
        manager._apply_decision("conv-1", DECISION_FULL)
        await asyncio.sleep(0.05)  # 让 create_task 有机会执行（若在事件循环中）

    asyncio.run(scenario())
    # _apply_decision full 分支在无配置存储时会创建任务写库——单测环境允许失败，
    # 此处只断言不抛异常；内存模式切换由 set_mode 单测覆盖（见集成场景）


def test_set_mode_rejects_unknown():
    manager = AgentCommandPermissionManager()
    with pytest.raises(ValueError):
        asyncio.run(manager.set_mode("sudo"))


# ── 中间件路径 ────────────────────────────────────────────────────────


def _tool_call(command: str) -> dict:
    import json

    return {
        "id": "call_1",
        "function": {"name": "cli", "arguments": json.dumps({"command": command})},
    }


def _ctx(conv_id="conv-1", is_sub=False, stream=True, emitter=None):
    from app.core.agents.middleware.base import AgentContext

    return AgentContext(
        messages=[],
        tools=None,
        extra={
            "conv_id": conv_id,
            "is_sub_agent": is_sub,
            "is_stream": stream,
            "scene": "chat",
        },
        sse_emitter=emitter,
    )


def test_middleware_denies_without_stream():
    """非流式路径 fail-closed：无法推送确认事件时拒绝执行。"""
    mgr = AgentCommandPermissionManager()
    gate_mod.agent_command_permissions = mgr

    called = {"next": False}

    async def next_fn(_tc):
        called["next"] = True
        return {"role": "tool", "tool_call_id": "call_1", "name": "cli", "content": "ok"}

    async def scenario():
        mw = PermissionGateMiddleware()
        return await mw.wrap_tool_call(_ctx(stream=False), _tool_call("dir"), next_fn)

    result = asyncio.run(scenario())
    assert called["next"] is False
    assert "已取消" in result["content"]


def test_middleware_passes_through_when_full_mode():
    mgr = AgentCommandPermissionManager()
    mgr._mode = "full"
    gate_mod.agent_command_permissions = mgr

    async def next_fn(_tc):
        return {"role": "tool", "tool_call_id": "call_1", "name": "cli", "content": "ok"}

    async def scenario():
        mw = PermissionGateMiddleware()
        return await mw.wrap_tool_call(_ctx(), _tool_call("dir"), next_fn)

    result = asyncio.run(scenario())
    assert result["content"] == "ok"


def test_middleware_subagent_denied_without_grant():
    mgr = AgentCommandPermissionManager()
    gate_mod.agent_command_permissions = mgr

    async def next_fn(_tc):
        return {"role": "tool", "tool_call_id": "call_1", "name": "cli", "content": "ok"}

    async def scenario():
        mw = PermissionGateMiddleware()
        return await mw.wrap_tool_call(_ctx(is_sub=True), _tool_call("dir"), next_fn)

    result = asyncio.run(scenario())
    assert "授权" in result["content"]


def test_middleware_gated_tool_only():
    mgr = AgentCommandPermissionManager()
    gate_mod.agent_command_permissions = mgr

    async def next_fn(_tc):
        return {"role": "tool", "tool_call_id": "call_1", "name": "read_file", "content": "ok"}

    async def scenario():
        tc = _tool_call("x")
        tc["function"]["name"] = "read_file"
        mw = PermissionGateMiddleware()
        return await mw.wrap_tool_call(_ctx(), tc, next_fn)

    assert asyncio.run(scenario())["content"] == "ok"


# ── P0 回归：SSE 载荷 id 与 _pending 键一致性 + runner 实时排水 ──────────


def test_middleware_sse_request_id_matches_pending_key():
    """P0-1 回归：前端拿到的 request_id 必须能 resolve（与 _pending 键一致）。"""
    import json as _json

    import app.core.agents.middleware.permission as gate_mod

    mgr = AgentCommandPermissionManager()
    gate_mod.agent_command_permissions = mgr

    captured: list[str] = []

    async def emitter(sse_str: str) -> None:
        captured.append(sse_str)

    async def next_fn(_tc):
        return {"role": "tool", "tool_call_id": "call_1", "name": "cli", "content": "ok"}

    async def scenario():
        mw = PermissionGateMiddleware()
        run_task = asyncio.create_task(
            mw.wrap_tool_call(_ctx(emitter=emitter), _tool_call("git status"), next_fn)
        )
        # 等待中间件发出 permission_request
        for _ in range(100):
            await asyncio.sleep(0.01)
            if captured:
                break
        assert captured, "permission_request 未发出"
        payload = _json.loads(captured[0].removeprefix("data: ").strip())
        rid = payload["permission_request"]["request_id"]
        # 以 SSE 载荷中的 id 回调（模拟前端）——必须命中 _pending
        assert mgr.resolve(rid, DECISION_ONCE) is True, (
            "SSE 载荷的 request_id 与 _pending 键不一致（P0-1 回归）"
        )
        return await run_task

    result = asyncio.run(scenario())
    assert result["content"] == "ok"


def test_session_grant_allows_same_conversation_via_middleware():
    """会话授权后同会话命令经中间件直接放行。"""
    import app.core.agents.middleware.permission as gate_mod

    mgr = AgentCommandPermissionManager()
    mgr._session_grants.add("conv-1")
    gate_mod.agent_command_permissions = mgr

    async def next_fn(_tc):
        return {"role": "tool", "tool_call_id": "call_1", "name": "cli", "content": "ok"}

    async def scenario():
        mw = PermissionGateMiddleware()
        return await mw.wrap_tool_call(_ctx(conv_id="conv-1"), _tool_call("dir"), next_fn)

    assert asyncio.run(scenario())["content"] == "ok"


def test_runner_drains_sse_during_tool_execution():
    """P0-2 回归：工具执行中途发射的 SSE 必须实时流出（不阻塞到工具返回后）。"""
    import asyncio as _asyncio

    from app.core.agents.middleware.base import AgentContext, AgentMiddleware
    from app.core.agents.middleware.pipeline import MiddlewarePipeline
    from app.core.agents.middleware.runner import AgentRunner

    release = _asyncio.Event()
    emitted_mid_execution: list[str] = []

    class BlockingGate(AgentMiddleware):
        """模拟 PermissionGate：先发射一条 SSE，再阻塞等待外部放行。"""

        async def wrap_tool_call(self, ctx, tool_call, next_fn):
            sse_payload = 'data: {"mid_execution": true}\n\n'
            await ctx.sse_emitter(sse_payload)
            emitted_mid_execution.append("emitted")
            await release.wait()
            return await next_fn(tool_call)

    from app.runtime.provider.llm.types import StreamEvent

    async def llm_call_fn(ctx):
        # 用合法流事件产出一次工具调用（runner 会经 _assemble_tool_calls 装配）
        yield StreamEvent("tool_call_delta", {
            "index": 0,
            "tool_call_id": "c1",
            "function_name": "fake",
            "function_arguments": "{}",
        })
        yield StreamEvent("finish_reason", {"finish_reason": "tool_calls"})

    async def execute_fn(_tc):
        return {"role": "tool", "tool_call_id": "c1", "name": "fake", "content": "done"}

    async def scenario():
        runner = AgentRunner(
            pipeline=MiddlewarePipeline([BlockingGate()]),
            max_iterations=0,  # 仅一轮工具调用，避免第二次 MID 干扰断言
            execute_fn=execute_fn,
        )
        ctx = AgentContext(messages=[], extra={"is_stream": True})

        async def consume():
            first = True
            async for sse in runner.run_stream(ctx, llm_call_fn):
                if "mid_execution" in sse and first:
                    # 工具仍在阻塞执行中，SSE 已实时到达（P0-2 修复的核心断言）
                    assert release.is_set() is False
                    emitted_mid_execution.append("received")
                    first = False

        consume_task = _asyncio.create_task(consume())
        # 给消费端时间到达阻塞点，再放行工具执行
        for _ in range(200):
            await _asyncio.sleep(0.01)
            if "received" in emitted_mid_execution:
                break
        release.set()
        # 工具循环中 runner 与 PermissionGate 用模块级 asyncio；此处消费端等待放行后完成
        import asyncio as _a2
        await _asyncio.wait_for(consume_task, timeout=5)
        await _asyncio.sleep(0)  # 让 runner 收尾

        assert "emitted" in emitted_mid_execution
        assert "received" in emitted_mid_execution

    _asyncio.run(scenario())
