"""LuomiNest 子 Agent 执行器。

参考 hermes-agent 的 delegate_tool、claude-code-src 的 AgentTool、deer-flow 的 SubagentExecutor 设计，
为主 Agent 提供子 Agent 委派能力。

核心原则：
1. 子 Agent 拥有独立上下文（不继承父对话历史）
2. 子 Agent 不读写记忆（避免污染主 Agent 记忆）
3. 深度限制（默认 max_depth=3，防止无限递归）
4. 仅返回最终摘要（不返回中间工具调用过程）
5. 支持事件回调，将执行过程通过 SSE 推送到前端
6. 支持 consensus_content（共识规范）注入子 Agent 系统提示词
7. 支持协作式取消（cancel_event）和硬超时（timeout_seconds）
8. 支持显式任务生命周期跟踪（task_id + LuomiNestTaskRegistry）
9. 支持并发限制（asyncio.Semaphore）
"""
import asyncio
import json
import uuid
from typing import Any, Awaitable, Callable

from loguru import logger

from app.core.agents.lifecycle import (
    LuomiNestTaskRecord,
    LuomiNestTaskStatus,
    luominest_task_registry,
)
from app.core.tools.orchestrator import tool_orchestrator
from app.runtime.provider.llm.adapter import llm_adapter


# 子 Agent 事件回调类型：接收事件字典，异步返回 None
SubagentEventCallback = Callable[[dict[str, Any]], Awaitable[None]]


# 子 Agent 系统提示模板
_SUBAGENT_SYSTEM_PROMPT = """你是 LuomiNest 主 Agent 委派的子 Agent，负责独立完成特定任务。

当前委派深度：{depth}/{max_depth}

你的职责：
1. 专注完成委派给你的任务，不要偏离主题
2. 可以使用提供的工具来完成任务
3. 完成后给出清晰、简洁的最终结果摘要

注意事项：
- 你拥有独立上下文，不要假设有 prior 对话历史
- 你的执行过程不会写入长期记忆
- 如果任务无法完成，请明确说明原因并给出建议
{consensus_section}{depth_warning}"""

_DEPTH_WARNING_TEMPLATE = """
**深度限制警告**：你已接近最大委派深度，无法再创建子 Agent。请直接使用工具完成任务。"""

_CONSENSUS_TEMPLATE = """
【Luminous 共识规范】
请严格遵循以下共识规范执行任务：
{consensus_content}
"""


class SubagentExecutor:
    """子 Agent 执行器

    管理子 Agent 的创建、执行和结果返回。
    支持嵌套委派（子 Agent 可以再创建子 Agent），通过深度限制防止无限递归。
    支持事件回调，将执行过程推送到前端展示。
    支持共识规范注入、协作式取消、硬超时、并发限制。
    """

    def __init__(
        self,
        max_depth: int = 3,
        max_iterations: int = 10,
        max_concurrent: int = 3,
        default_timeout: int = 300,
    ):
        """
        Args:
            max_depth: 最大委派深度（1=仅主 Agent 可委派，2=子 Agent 也可委派，以此类推）
            max_iterations: 单个子 Agent 的最大工具调用循环次数
            max_concurrent: 最大并发子 Agent 数量
            default_timeout: 默认硬超时秒数（单个子 Agent 任务的最长执行时间）
        """
        self.max_depth = max_depth
        self.max_iterations = max_iterations
        self.max_concurrent = max_concurrent
        self.default_timeout = default_timeout
        # 显式信号量替代原 _active_count 计数，确保并发安全
        self._semaphore = asyncio.Semaphore(max_concurrent)

    def _build_system_prompt(
        self,
        depth: int,
        consensus_content: str | None = None,
    ) -> str:
        """构建子 Agent 系统提示

        Args:
            depth: 当前委派深度
            consensus_content: 共识规范内容（可选），注入到系统提示词
        """
        depth_warning = ""
        if depth >= self.max_depth - 1:
            depth_warning = _DEPTH_WARNING_TEMPLATE

        consensus_section = ""
        if consensus_content:
            consensus_section = _CONSENSUS_TEMPLATE.format(consensus_content=consensus_content)

        return _SUBAGENT_SYSTEM_PROMPT.format(
            depth=depth,
            max_depth=self.max_depth,
            consensus_section=consensus_section,
            depth_warning=depth_warning,
        )

    def _get_tools_for_subagent(self, depth: int) -> list[dict[str, Any]]:
        """获取子 Agent 可用的工具列表

        在最大深度 - 1 时，移除 delegate_to_subagent 工具以防止进一步嵌套。
        同时始终移除 start_collaboration（子 Agent 不应发起多 Agent 协作）。
        """
        all_tools = tool_orchestrator.get_tools_for_llm()
        # 始终禁用协作工具，避免子 Agent 嵌套发起协作
        forbidden_names = {"start_collaboration"}
        # 接近最大深度时，额外禁用委派工具
        if depth >= self.max_depth - 1:
            forbidden_names.add("delegate_to_subagent")
            forbidden_names.add("agent_tool_call")
        return [
            t
            for t in all_tools
            if t.get("function", {}).get("name") not in forbidden_names
        ]

    async def _emit_event(
        self,
        callback: SubagentEventCallback | None,
        event: dict[str, Any],
    ) -> None:
        """安全推送子 Agent 事件"""
        if callback is None:
            return
        try:
            await callback(event)
        except Exception as e:
            logger.warning(f"[SubagentExecutor] 事件回调失败: {e}")

    async def execute(
        self,
        task: str,
        context: str = "",
        depth: int = 0,
        provider: str | None = None,
        model: str | None = None,
        event_callback: SubagentEventCallback | None = None,
        consensus_content: str | None = None,
        timeout_seconds: int | None = None,
        cancel_event: asyncio.Event | None = None,
        task_id: str | None = None,
    ) -> str:
        """执行子 Agent 任务

        Args:
            task: 委派给子 Agent 的任务描述
            context: 额外上下文信息（可选）
            depth: 当前委派深度（0=主 Agent 直接委派的子 Agent）
            provider: LLM provider（默认继承主 Agent）
            model: LLM model（默认继承主 Agent）
            event_callback: 事件回调（可选），用于将执行过程推送到前端
            consensus_content: 共识规范（可选），注入子 Agent 系统提示词
            timeout_seconds: 硬超时秒数（None 使用 default_timeout）
            cancel_event: 协作式取消信号（可选），子 Agent 在迭代边界检查
            task_id: 显式任务 ID（可选），注册到 LuomiNestTaskRegistry 跟踪生命周期

        Returns:
            子 Agent 的最终响应文本
        """
        if depth >= self.max_depth:
            return (
                f"已达到最大子 Agent 委派深度 ({self.max_depth})，"
                f"无法继续创建子 Agent。请直接使用工具完成任务。"
            )

        # 应用硬超时
        effective_timeout = timeout_seconds if timeout_seconds is not None else self.default_timeout

        # 创建任务记录（如果提供了 task_id）
        record: LuomiNestTaskRecord | None = None
        if task_id:
            record = LuomiNestTaskRecord(task_id=task_id)
            await luominest_task_registry.register(task_id, record)
        else:
            # 未提供 task_id 时内部生成一个，用于日志追踪
            task_id = f"subagent_d{depth}_{uuid.uuid4().hex[:8]}"

        # 合并外部 cancel_event 与 record 的 cancel_event
        effective_cancel_event = cancel_event
        if record is not None:
            if effective_cancel_event is None:
                effective_cancel_event = record.cancel_event
            else:
                # 若外部传入了 cancel_event，将其与 record 的绑定（外部取消也设置 record）
                async def _bridge_cancel() -> None:
                    if cancel_event is not None:
                        await cancel_event.wait()
                        record.request_cancel()
                asyncio.create_task(_bridge_cancel())

        logger.info(
            f"[SubagentExecutor] 启动子 Agent: id={task_id}, "
            f"depth={depth}/{self.max_depth}, task_len={len(task)}, "
            f"timeout={effective_timeout}s, has_consensus={bool(consensus_content)}"
        )

        # 推送 started 事件
        await self._emit_event(event_callback, {
            "subagent_id": task_id,
            "status": "started",
            "task": task,
            "depth": depth,
            "iteration": 0,
        })

        # 标记为运行中
        if record is not None:
            record.mark_running()

        try:
            # 通过信号量限制并发，并应用硬超时
            async with self._semaphore:
                result = await asyncio.wait_for(
                    self._run_subagent_loop(
                        task=task,
                        context=context,
                        depth=depth,
                        provider=provider,
                        model=model,
                        subagent_id=task_id,
                        event_callback=event_callback,
                        consensus_content=consensus_content,
                        cancel_event=effective_cancel_event,
                    ),
                    timeout=effective_timeout,
                )

            logger.info(
                f"[SubagentExecutor] 子 Agent 完成: id={task_id}, "
                f"result_len={len(result)}"
            )
            if record is not None:
                record.mark_completed(result)
            # 推送 completed 事件
            await self._emit_event(event_callback, {
                "subagent_id": task_id,
                "status": "completed",
                "task": task,
                "depth": depth,
                "result": result,
            })
            return result

        except asyncio.TimeoutError:
            logger.warning(
                f"[SubagentExecutor] 子 Agent 超时: id={task_id}, "
                f"timeout={effective_timeout}s"
            )
            if record is not None:
                record.mark_timed_out()
            timeout_msg = (
                f"子 Agent 执行超时（{effective_timeout}秒），任务可能过于复杂。"
                f"建议：拆分任务、增加 timeout_seconds，或简化要求。"
            )
            await self._emit_event(event_callback, {
                "subagent_id": task_id,
                "status": "failed",
                "task": task,
                "depth": depth,
                "error": timeout_msg,
            })
            return timeout_msg

        except asyncio.CancelledError:
            logger.info(
                f"[SubagentExecutor] 子 Agent 被取消: id={task_id}"
            )
            if record is not None:
                record.mark_cancelled()
            cancel_msg = "子 Agent 任务已被取消"
            await self._emit_event(event_callback, {
                "subagent_id": task_id,
                "status": "failed",
                "task": task,
                "depth": depth,
                "error": cancel_msg,
            })
            return cancel_msg

        except Exception as e:
            logger.error(
                f"[SubagentExecutor] 子 Agent 异常: id={task_id}, error={e}",
                exc_info=True,
            )
            if record is not None:
                record.mark_failed(str(e))
            # 推送 failed 事件
            await self._emit_event(event_callback, {
                "subagent_id": task_id,
                "status": "failed",
                "task": task,
                "depth": depth,
                "error": str(e),
            })
            return f"子 Agent 执行失败: {e}"

    async def _run_subagent_loop(
        self,
        task: str,
        context: str,
        depth: int,
        provider: str | None,
        model: str | None,
        subagent_id: str,
        event_callback: SubagentEventCallback | None,
        consensus_content: str | None = None,
        cancel_event: asyncio.Event | None = None,
    ) -> str:
        """运行子 Agent 的工具调用循环"""
        # 构建初始消息
        user_content = task
        if context:
            user_content += f"\n\n[附加上下文]\n{context}"

        messages: list[dict] = [
            {"role": "system", "content": self._build_system_prompt(depth, consensus_content)},
            {"role": "user", "content": user_content},
        ]

        # 获取子 Agent 可用工具
        tools = self._get_tools_for_subagent(depth)

        # 解析 provider 和 model
        actual_provider = provider or llm_adapter.default_provider
        if model is None:
            model = llm_adapter.get_provider(actual_provider).default_model

        # 检查 provider 是否支持工具调用
        use_tools = bool(tools) and llm_adapter.supports_tool_calls(actual_provider, model)

        content = ""
        for iteration in range(self.max_iterations):
            # 协作式取消检查
            if cancel_event is not None and cancel_event.is_set():
                logger.info(
                    f"[SubagentExecutor] 子 Agent {subagent_id} 在迭代 {iteration + 1} 被取消"
                )
                raise asyncio.CancelledError()

            logger.info(
                f"[SubagentExecutor] 子 Agent {subagent_id} 第 {iteration + 1} 轮调用"
            )

            # 推送 running 事件（含当前迭代）
            await self._emit_event(event_callback, {
                "subagent_id": subagent_id,
                "status": "running",
                "task": task,
                "depth": depth,
                "iteration": iteration,
                "progress": f"第 {iteration + 1} 轮思考中",
            })

            # 调用 LLM（非流式，return_raw=True 以获取 tool_calls）
            try:
                result = await llm_adapter.chat(
                    messages=messages,
                    tools=tools if use_tools else None,
                    stream=False,
                    return_raw=True,
                    provider_name=actual_provider,
                    model=model,
                )
            except Exception as e:
                logger.error(
                    f"[SubagentExecutor] LLM 调用失败: id={subagent_id}, error={e}"
                )
                return f"子 Agent LLM 调用失败: {e}"

            # 解析响应
            if isinstance(result, dict):
                content = result.get("content", "")
                tool_calls = result.get("tool_calls", [])
            else:
                content = str(result)
                tool_calls = []

            # 无工具调用，返回最终结果
            if not tool_calls or not use_tools:
                logger.info(
                    f"[SubagentExecutor] 子 Agent {subagent_id} 完成，"
                    f"无更多工具调用，返回最终结果"
                )
                return content or "(子 Agent 未返回内容)"

            # 有工具调用，执行工具
            # 添加 assistant 消息（含 tool_calls）
            messages.append({
                "role": "assistant",
                "content": content or "",
                "tool_calls": tool_calls,
            })

            for tc in tool_calls:
                # 工具调用前再次检查取消
                if cancel_event is not None and cancel_event.is_set():
                    raise asyncio.CancelledError()

                tc_id = tc.get("id", "")
                tc_function = tc.get("function", {})
                tc_name = tc_function.get("name", "")
                tc_args = tc_function.get("arguments", "{}")

                logger.info(
                    f"[SubagentExecutor] 子 Agent {subagent_id} 调用工具: "
                    f"{tc_name} (iteration={iteration + 1})"
                )

                # 推送 tool_call 事件
                await self._emit_event(event_callback, {
                    "subagent_id": subagent_id,
                    "status": "running",
                    "task": task,
                    "depth": depth,
                    "iteration": iteration,
                    "tool_name": tc_name,
                    "tool_args": tc_args,
                    "progress": f"调用工具 {tc_name}",
                })

                # 如果是委派工具，传递 depth + 1
                if tc_name == "delegate_to_subagent":
                    tool_msg = await self._handle_nested_delegate(
                        tc_args, depth, actual_provider, model, subagent_id, event_callback,
                        consensus_content=consensus_content,
                        cancel_event=cancel_event,
                        tc_id=tc_id,
                    )
                else:
                    tool_msg = await tool_orchestrator.execute_tool_call(tc)

                tool_output = tool_msg.get("content", "") if isinstance(tool_msg, dict) else str(tool_msg)
                messages.append(tool_msg)

                # 推送 tool_result 事件
                await self._emit_event(event_callback, {
                    "subagent_id": subagent_id,
                    "status": "running",
                    "task": task,
                    "depth": depth,
                    "iteration": iteration,
                    "tool_name": tc_name,
                    "tool_output": tool_output[:500] if tool_output else "",
                    "progress": f"工具 {tc_name} 完成",
                })

                logger.info(
                    f"[SubagentExecutor] 子 Agent {subagent_id} 工具 {tc_name} 完成"
                )

        # 达到最大迭代次数
        logger.warning(
            f"[SubagentExecutor] 子 Agent {subagent_id} 达到最大迭代次数 "
            f"({self.max_iterations})"
        )
        return (
            f"子 Agent 达到最大工具调用迭代次数 ({self.max_iterations})，"
            f"最后内容: {content[:500] if content else '(空)'}"
        )

    async def _handle_nested_delegate(
        self,
        args_str: str,
        parent_depth: int,
        provider: str,
        model: str,
        parent_id: str,
        event_callback: SubagentEventCallback | None,
        consensus_content: str | None = None,
        cancel_event: asyncio.Event | None = None,
        tc_id: str = "",
    ) -> dict:
        """处理子 Agent 的嵌套委派调用"""
        try:
            args = json.loads(args_str) if isinstance(args_str, str) else args_str
        except json.JSONDecodeError:
            args = {}

        task = args.get("task", "")
        context = args.get("context", "")
        nested_consensus = args.get("consensus_content", consensus_content)

        if not task:
            return {
                "role": "tool",
                "tool_call_id": tc_id,
                "name": "delegate_to_subagent",
                "content": "错误：缺少 task 参数",
            }

        child_depth = parent_depth + 1
        child_task_id = f"subagent_d{child_depth}_{uuid.uuid4().hex[:8]}"
        logger.info(
            f"[SubagentExecutor] 嵌套委派: parent={parent_id}, "
            f"child={child_task_id}, child_depth={child_depth}"
        )

        result = await self.execute(
            task=task,
            context=context,
            depth=child_depth,
            provider=provider,
            model=model,
            event_callback=event_callback,
            consensus_content=nested_consensus,
            cancel_event=cancel_event,
            task_id=child_task_id,
        )

        return {
            "role": "tool",
            "tool_call_id": tc_id,
            "name": "delegate_to_subagent",
            "content": result,
        }

    async def cancel(self, task_id: str) -> bool:
        """取消指定任务（便捷方法，委托给 Registry）"""
        return await luominest_task_registry.cancel(task_id)


# 全局单例
subagent_executor = SubagentExecutor()
