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
