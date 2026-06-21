"""子 Agent 执行器。

参考 hermes-agent 的 delegate_tool 和 claude-code-src 的 AgentTool 设计，
为主 Agent 提供子 Agent 委派能力。

核心原则：
1. 子 Agent 拥有独立上下文（不继承父对话历史）
2. 子 Agent 不读写记忆（避免污染主 Agent 记忆）
3. 深度限制（默认 max_depth=3，防止无限递归）
4. 仅返回最终摘要（不返回中间工具调用过程）
5. 支持事件回调，将执行过程通过 SSE 推送到前端
"""
import json
import uuid
from typing import Any, Awaitable, Callable

from loguru import logger

from app.core.tools.orchestrator import tool_orchestrator
from app.core.tools.registry import tool_registry
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
{depth_warning}"""

_DEPTH_WARNING_TEMPLATE = """
**深度限制警告**：你已接近最大委派深度，无法再创建子 Agent。请直接使用工具完成任务。"""


class SubagentExecutor:
    """子 Agent 执行器

    管理子 Agent 的创建、执行和结果返回。
    支持嵌套委派（子 Agent 可以再创建子 Agent），通过深度限制防止无限递归。
    支持事件回调，将执行过程推送到前端展示。
    """

    def __init__(
        self,
        max_depth: int = 3,
        max_iterations: int = 10,
        max_concurrent: int = 3,
    ):
        """
        Args:
            max_depth: 最大委派深度（1=仅主 Agent 可委派，2=子 Agent 也可委派，以此类推）
            max_iterations: 单个子 Agent 的最大工具调用循环次数
            max_concurrent: 最大并发子 Agent 数量
        """
        self.max_depth = max_depth
        self.max_iterations = max_iterations
        self.max_concurrent = max_concurrent
        self._active_count = 0

    def _build_system_prompt(self, depth: int) -> str:
        """构建子 Agent 系统提示"""
        depth_warning = ""
        if depth >= self.max_depth - 1:
            depth_warning = _DEPTH_WARNING_TEMPLATE

        return _SUBAGENT_SYSTEM_PROMPT.format(
            depth=depth,
            max_depth=self.max_depth,
            depth_warning=depth_warning,
        )

    def _get_tools_for_subagent(self, depth: int) -> list[dict[str, Any]]:
        """获取子 Agent 可用的工具列表

        在最大深度 - 1 时，移除 delegate_to_subagent 工具以防止进一步嵌套。
        """
        all_tools = tool_orchestrator.get_tools_for_llm()
        if depth >= self.max_depth - 1:
            # 接近最大深度，移除委派工具
            return [
                t for t in all_tools
                if t.get("function", {}).get("name") != "delegate_to_subagent"
            ]
        return all_tools

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
    ) -> str:
        """执行子 Agent 任务

        Args:
            task: 委派给子 Agent 的任务描述
            context: 额外上下文信息（可选）
            depth: 当前委派深度（0=主 Agent 直接委派的子 Agent）
            provider: LLM provider（默认继承主 Agent）
            model: LLM model（默认继承主 Agent）
            event_callback: 事件回调（可选），用于将执行过程推送到前端

        Returns:
            子 Agent 的最终响应文本
        """
        if depth >= self.max_depth:
            return (
                f"已达到最大子 Agent 委派深度 ({self.max_depth})，"
                f"无法继续创建子 Agent。请直接使用工具完成任务。"
            )

        if self._active_count >= self.max_concurrent:
            return (
                f"已达到最大并发子 Agent 数量 ({self.max_concurrent})，"
                f"请等待现有子 Agent 完成后再委派。"
            )

        self._active_count += 1
        subagent_id = f"subagent_d{depth}_{uuid.uuid4().hex[:8]}"
        logger.info(
            f"[SubagentExecutor] 启动子 Agent: id={subagent_id}, "
            f"depth={depth}/{self.max_depth}, task_len={len(task)}"
        )

        # 推送 started 事件
        await self._emit_event(event_callback, {
            "subagent_id": subagent_id,
            "status": "started",
            "task": task,
            "depth": depth,
            "iteration": 0,
        })

        try:
            result = await self._run_subagent_loop(
                task, context, depth, provider, model, subagent_id, event_callback,
            )
            logger.info(
                f"[SubagentExecutor] 子 Agent 完成: id={subagent_id}, "
                f"result_len={len(result)}"
            )
            # 推送 completed 事件
            await self._emit_event(event_callback, {
                "subagent_id": subagent_id,
                "status": "completed",
                "task": task,
                "depth": depth,
                "result": result,
            })
            return result
        except Exception as e:
            logger.error(
                f"[SubagentExecutor] 子 Agent 异常: id={subagent_id}, error={e}",
                exc_info=True,
            )
            # 推送 failed 事件
            await self._emit_event(event_callback, {
                "subagent_id": subagent_id,
                "status": "failed",
                "task": task,
                "depth": depth,
                "error": str(e),
            })
            return f"子 Agent 执行失败: {e}"
        finally:
            self._active_count -= 1

    async def _run_subagent_loop(
        self,
        task: str,
        context: str,
        depth: int,
        provider: str | None,
        model: str | None,
        subagent_id: str,
        event_callback: SubagentEventCallback | None,
    ) -> str:
        """运行子 Agent 的工具调用循环"""
        # 构建初始消息
        user_content = task
        if context:
            user_content += f"\n\n[附加上下文]\n{context}"

        messages: list[dict] = [
            {"role": "system", "content": self._build_system_prompt(depth)},
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

        for iteration in range(self.max_iterations):
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
    ) -> dict:
        """处理子 Agent 的嵌套委派调用"""
        try:
            args = json.loads(args_str) if isinstance(args_str, str) else args_str
        except json.JSONDecodeError:
            args = {}

        task = args.get("task", "")
        context = args.get("context", "")

        if not task:
            return {
                "role": "tool",
                "tool_call_id": "",
                "name": "delegate_to_subagent",
                "content": "错误：缺少 task 参数",
            }

        child_depth = parent_depth + 1
        logger.info(
            f"[SubagentExecutor] 嵌套委派: parent={parent_id}, "
            f"child_depth={child_depth}"
        )

        result = await self.execute(
            task=task,
            context=context,
            depth=child_depth,
            provider=provider,
            model=model,
            event_callback=event_callback,
        )

        return {
            "role": "tool",
            "tool_call_id": "",
            "name": "delegate_to_subagent",
            "content": result,
        }


# 全局单例
subagent_executor = SubagentExecutor()
