"""取消传播回归测试（链路审查 §4 主题二：结构化取消传播）。

背景（02-工作台对话链路.md P1-4）：subagent 执行器的 execute() 捕获
CancelledError 后返回提示文案字符串，吞掉取消，破坏上游结构化取消
（asyncio.wait_for 超时 / 父任务 cancel 的"已取消"判定失真）。

统一修法：CancelledError 必须 re-raise（py3.12 下 except Exception 本就
不捕 CancelledError，此处测试同时守护该语义不被改成 except BaseException）；
用户可感知语义保持——协作式取消（cancel_event）仍把取消文案作为工具结果
返回父 Agent，结构化取消（父任务 cancel）向上传播。

覆盖：
1. subagent 结构化取消：CancelledError 传出 + 清理代码（record.mark_cancelled）先行执行
2. subagent 协作式取消：返回取消文案字符串（原契约不回退）
3. subagent 双源取消：cancel_event 已置位但父任务 cancel 仍传播（cancelling() 判定）
4. workflow submit：runner 任务被 cancel 时 CancelledError 穿透 except Exception 兜底
5. workflow submit_stream：runner 收到 CancelledError 后 finally 清理（emitter 哨兵）
   先执行，SSE 消费端能正常收尾而非悬挂
"""

import asyncio

import pytest

from app.core.agents.lifecycle import LuomiNestTaskStatus, luominest_task_registry
from app.core.agents.subagent_executor import SubagentExecutor
from app.core.workflow.models import WorkflowPhase


async def _settle() -> None:
    """让出事件循环若干轮，确保被测任务完成注册/进入挂起。"""
    for _ in range(50):
        await asyncio.sleep(0)


# ── subagent 执行器 ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_subagent_structured_cancel_reraises_and_cleans_up():
    """父任务 cancel：CancelledError 必须传出，且 record 已被标记 CANCELLED。"""
    executor = SubagentExecutor()

    async def hang_loop(*args, **kwargs):
        await asyncio.sleep(3600)

    executor._run_subagent_loop = hang_loop

    task_id = "subagent_cancel_structured_test"
    task = asyncio.create_task(executor.execute("长任务", task_id=task_id))
    try:
        await _settle()
        record = await luominest_task_registry.get(task_id)
        assert record is not None, "execute 应先注册任务记录"

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert task.cancelled()

        # 清理代码已在 re-raise 前执行
        record = await luominest_task_registry.get(task_id)
        assert record.status == LuomiNestTaskStatus.CANCELLED
    finally:
        await luominest_task_registry.remove(task_id)


@pytest.mark.asyncio
async def test_subagent_cooperative_cancel_returns_tool_result():
    """协作式取消（cancel_event）：保持原契约，返回取消文案字符串。"""
    executor = SubagentExecutor()
    cancel_event = asyncio.Event()

    async def loop_until_cancelled(*args, **kwargs):
        await cancel_event.wait()
        raise asyncio.CancelledError()

    executor._run_subagent_loop = loop_until_cancelled

    task = asyncio.create_task(executor.execute("长任务", cancel_event=cancel_event))
    await _settle()
    cancel_event.set()
    result = await asyncio.wait_for(task, timeout=5)
    assert "已被取消" in result


@pytest.mark.asyncio
async def test_subagent_structured_cancel_wins_over_cooperative_flag():
    """cancel_event 已置位但父任务 cancel：结构化取消仍必须传播。"""
    executor = SubagentExecutor()
    cancel_event = asyncio.Event()
    loop_started = asyncio.Event()

    async def loop_after_flag(*args, **kwargs):
        loop_started.set()
        await asyncio.sleep(3600)

    executor._run_subagent_loop = loop_after_flag

    task = asyncio.create_task(
        executor.execute("长任务", cancel_event=cancel_event)
    )
    await loop_started.wait()
    cancel_event.set()  # 协作标志先置位
    task.cancel()       # 随后父任务硬取消
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.cancelled()


# ── workflow 引擎 ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_workflow_submit_cancellation_propagates(monkeypatch):
    """submit 的 runner 任务被 cancel：CancelledError 穿透 except Exception 兜底，
    会话不得被误标 FAILED（取消≠失败）。

    注意：monkeypatch 替换的是实例属性，函数不经历绑定，签名不带 self。
    """
    from app.core.workflow import WorkflowMode, workflow_engine

    async def hang_workflow(session, provider, model, event_callback):
        await asyncio.sleep(3600)

    monkeypatch.setattr(workflow_engine, "_run_workflow", hang_workflow)

    task = asyncio.create_task(
        workflow_engine.submit("长任务", mode=WorkflowMode.STANDARD)
    )
    try:
        await _settle()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert task.cancelled()

        # except Exception 兜底未把取消当成失败
        sessions = [
            s for s in workflow_engine._active_sessions.values()
            if s.user_message == "长任务"
        ]
        assert sessions, "会话应已注册"
        assert sessions[-1].phase != WorkflowPhase.FAILED
    finally:
        for s in list(workflow_engine._active_sessions.values()):
            if s.user_message == "长任务":
                await workflow_engine._unregister_session(s.session_id)


@pytest.mark.asyncio
async def test_workflow_stream_runner_cancel_propagates_with_cleanup(monkeypatch):
    """submit_stream 的 runner 收到 CancelledError：_run 的 except Exception
    不得吞掉；finally 清理（emitter 哨兵 + 移除注册）先执行，SSE 消费端
    以 CancelledError 收场而非悬挂。"""
    from app.core.workflow import WorkflowMode, workflow_engine

    async def cancelled_workflow(session, provider, model, event_callback):
        raise asyncio.CancelledError()

    monkeypatch.setattr(workflow_engine, "_run_workflow", cancelled_workflow)

    gen = workflow_engine.submit_stream("长任务", mode=WorkflowMode.STANDARD)
    first = await gen.__anext__()
    assert first["type"] == "session_start"
    session_id = first["data"]["session_id"]
    try:
        # 消费直到 runner 的 CancelledError 穿透：若 except 吞掉取消，这里会
        # 收到 type=error 事件而非 CancelledError；若清理缺失则会悬挂
        with pytest.raises(asyncio.CancelledError):
            async for _event in gen:
                pass
        # 留出轮次让 emitter 转发任务消费哨兵后自行退出
        await _settle()
    finally:
        await workflow_engine._unregister_session(session_id)
