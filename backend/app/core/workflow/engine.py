"""工作流引擎核心

主 Agent 长任务工作流引擎，负责：
1. 接收工作台输入的长任务
2. 调用 LLM 分析任务并生成执行计划
3. 调度内部模块接口执行子任务
4. 管理任务状态机，流式推送进度

参考：
- hermes-agent: delegate_task 委派机制 + AIAgent 工具调用循环
- deer-flow: SubagentExecutor + 中间件链 + StreamBridge
- claude-code: QueryEngine 多轮循环 + 分区批处理工具编排
"""
import asyncio
import json
import re
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from loguru import logger

from app.core.utils import AsyncKeyLocks, parse_llm_json, utc_now
from app.runtime.provider.llm.types import RouteHint
from app.core.workflow.event_emitter import WorkflowEventEmitter
from app.core.workflow.internal_registry import internal_tool_registry
from app.core.workflow.context_manager import workflow_context_manager
from app.core.workflow.models import (
    MODE_CONFIGS,
    WorkflowMode,
    WorkflowPhase,
    WorkflowPriority,
    WorkflowSession,
    WorkflowStatus,
    WorkflowTask,
    WorkflowTaskResult,
    WorkflowTaskType,
)


# 事件回调类型：接收事件字典，异步返回 None
WorkflowEventCallback = Callable[[dict[str, Any]], Awaitable[None]]


# ── 模块级依赖注入（由组合根 app_factory 装配）──
# setter 未调用时保留函数内延迟导入兜底，行为向后兼容。
# 纪律：本模块顶层不得新增对 app.services / app.infrastructure 的导入。
_chat_service_cls: Any | None = None
_conversation_store: Any | None = None
_llm_adapter: Any | None = None


def configure_engine(
    chat_service_cls: Any | None = None,
    conversation_store: Any | None = None,
    llm_adapter: Any | None = None,
) -> None:
    """装配工作流引擎的外部依赖（由组合根在启动阶段调用一次）。

    Args:
        chat_service_cls: ChatService 类（引擎使用其静态持久化辅助方法）
        conversation_store: 对话存储门面实例（ConversationFacade）
        llm_adapter: LLM 适配器实例

    任一参数传 None 时该依赖保持原有延迟导入兜底。
    """
    global _chat_service_cls, _conversation_store, _llm_adapter
    if chat_service_cls is not None:
        _chat_service_cls = chat_service_cls
    if conversation_store is not None:
        _conversation_store = conversation_store
    if llm_adapter is not None:
        _llm_adapter = llm_adapter


def _get_chat_service_cls() -> Any:
    """获取 ChatService 类（优先注入实例，兜底延迟导入）。"""
    if _chat_service_cls is None:
        from app.services.chat_service import ChatService
        return ChatService
    return _chat_service_cls


def _get_conversation_store() -> Any:
    """获取对话存储门面（优先注入实例，兜底延迟导入）。"""
    if _conversation_store is None:
        from app.infrastructure.database.conversation_store import conversation_store
        return conversation_store
    return _conversation_store


def _get_llm_adapter() -> Any:
    """获取 LLM 适配器（优先注入实例，兜底延迟导入）。"""
    if _llm_adapter is None:
        from app.runtime.provider.llm.adapter import llm_adapter
        return llm_adapter
    return _llm_adapter


# 常驻核心内部工具（S1b：始终注入完整 schema；其余工具仅名称+一句话，按需 tool.read）
_CORE_INTERNAL_TOOLS: frozenset[str] = frozenset({
    "memory.search",
    "memory.build_context",
    "memory.get_profile",
    "schedule.create",
    "schedule.list",
    "schedule.get",
    "schedule.delete",
    "browser.screenshot",
    "browser.get_html",
    "console.execute",
    "subagent.delegate",
    "context.compress",
    "app.launch",
    "search.everything",
    "smart_home.control",
    "smart_home.list_devices",
    "market.list_installed",
    "platform.list_instances",
    "platform.send_message",
    "workflow.list_templates",
    "workflow.run_template",
    "tool.read",
})


# 工作流系统提示模板（英文）
_WORKFLOW_SYSTEM_PROMPT = """You are the LuomiNest main Agent workflow engine. Your role is to decompose complex user tasks into executable subtask plans.

Your responsibilities:
1. Analyze the user's task and determine which internal modules to invoke
2. Generate a structured execution plan (JSON format)
3. Each subtask must specify the internal tool to call and its arguments

Available internal module interfaces:
{available_tools}

OUTPUT FORMAT - STRICTLY FOLLOW:
You must output ONLY a JSON object. Do NOT output any other text, explanations, markdown, or code blocks.
The JSON object format is:
{{
  "analysis": "Brief task analysis",
  "plan": "Brief execution plan description",
  "tasks": [
    {{
      "title": "Subtask title",
      "description": "What this subtask does",
      "tool_name": "Internal tool name (e.g. browser.navigate, memory.search, schedule.create)",
      "arguments": {{}},
      "depends_on": [],
      "priority": "normal|high|urgent|low",
      "node_type": "input|agent|tool|condition|output"
    }}
  ]
}}

Rules:
- tasks array is ordered by dependency
- depends_on references previous tasks' titles
- If no tool call is needed (pure text reply, chat, simple Q&A), tasks MUST be an empty array []
- Prefer internal module interfaces over generic tools
- Do NOT wrap JSON in ```json``` code blocks; output pure JSON directly
- Even for chat or simple Q&A, you must return a valid JSON object
- node_type values: "input" for user request entry, "tool" for tool calls, "agent" for subagent delegation, "condition" for conditional branching, "output" for final result"""


def _extract_json_plan(text: str) -> dict[str, Any] | None:
    """从 LLM 响应中提取 JSON 执行计划

    候选提取（```json / ``` 围栏、{...} 片段、整段文本）与截断修复
    （finish_reason=length 时 JSON 不完整）已统一收口到
    core.utils.parse_llm_json；本处仅保留工作流计划的 "tasks" 键约束。
    """
    return parse_llm_json(text, require_keys=("tasks",))


_THINK_TAG_PATTERN = re.compile(r'<think>([\s\S]*?)</think>', re.IGNORECASE)
_THINK_OPEN_PATTERN = re.compile(r'<think\s*>', re.IGNORECASE)


def _extract_think_content(text: str) -> tuple[str, str]:
    """从文本中提取 <think></think> 标签内的思考过程

    部分模型（DeepSeek-R1、Qwen3、本地 Ollama 模型等）会将思考过程
    嵌入 content 字段的 <think>...</think> 标签中。此函数负责：
    1. 提取标签内的思考内容
    2. 从原文中移除标签，确保后续 JSON 解析不被干扰

    Returns:
        tuple: (cleaned_text, think_content)
            - cleaned_text: 移除 think 标签后的文本
            - think_content: 提取到的思考内容（可能为空字符串）
    """
    if not text:
        return text, ""

    think_parts: list[str] = []

    # 优先匹配完整的 <think>...</think> 闭合标签
    matches = _THINK_TAG_PATTERN.findall(text)
    if matches:
        think_parts.extend(matches)
        text = _THINK_TAG_PATTERN.sub("", text)

    # 兜底：处理未闭合的 <think> 标签（取 <think> 之后的所有内容）
    open_match = _THINK_OPEN_PATTERN.search(text)
    if open_match:
        think_parts.append(text[open_match.end():])
        text = text[:open_match.start()]

    think_content = "\n".join(part.strip() for part in think_parts if part.strip())
    return text.strip(), think_content


class WorkflowEngine:
    """工作流引擎

    管理长任务的完整生命周期：分析 → 规划 → 执行 → 综合 → 完成。

    核心流程：
    1. submit(): 接收用户任务，创建 WorkflowSession
    2. _analyze_and_plan(): 调用 LLM 分析任务，生成执行计划
    3. _execute_tasks(): 按依赖关系调度内部模块接口执行子任务
    4. _synthesize(): 综合所有子任务结果，生成最终回复
    5. 流式推送进度事件到前端（通过 event_callback）
    """

    def __init__(
        self,
        max_iterations: int = 20,
        max_concurrent: int = 3,
        planning_temperature: float = 0.3,
        synthesis_temperature: float = 0.4,
    ):
        self.max_iterations = max_iterations
        self.max_concurrent = max_concurrent
        self.planning_temperature = planning_temperature
        self.synthesis_temperature = synthesis_temperature
        self._active_sessions: dict[str, WorkflowSession] = {}
        self._session_locks: AsyncKeyLocks = AsyncKeyLocks()
        self._dict_lock = asyncio.Lock()

    async def _register_session(self, session: WorkflowSession) -> None:
        """注册会话到字典（加锁保护，防止并发 submit 竞态）"""
        async with self._dict_lock:
            self._active_sessions[session.session_id] = session
            await self._session_locks.get(session.session_id)

    async def _unregister_session(self, session_id: str) -> None:
        """从字典移除会话（加锁保护）"""
        async with self._dict_lock:
            self._active_sessions.pop(session_id, None)
            self._session_locks.discard(session_id)

    def _create_session(
        self,
        user_message: str,
        mode: WorkflowMode,
        conversation_id: str | None = None,
        skip_confirmation: bool | None = None,
    ) -> WorkflowSession:
        """根据执行模式创建工作流会话，注入 MODE_CONFIGS 中的参数

        P2 长任务执行模式：不同模式调整迭代次数、并发度、温度、max_tokens、
        是否跳过计划确认。配置在创建时固化到 session，运行时直接读取。

        Args:
            skip_confirmation: 覆盖模式默认的 skip_confirmation（None 表示使用模式默认值）
        """
        config = MODE_CONFIGS.get(mode, MODE_CONFIGS[WorkflowMode.STANDARD])
        return WorkflowSession(
            user_message=user_message,
            mode=mode,
            max_iterations=config["max_iterations"],
            max_concurrent=config["max_concurrent"],
            planning_temperature=config["planning_temperature"],
            synthesis_temperature=config["synthesis_temperature"],
            planning_max_tokens=config["planning_max_tokens"],
            skip_confirmation=skip_confirmation if skip_confirmation is not None else config["skip_confirmation"],
            conversation_id=conversation_id,
        )

    async def submit(
        self,
        user_message: str,
        provider: str | None = None,
        model: str | None = None,
        event_callback: WorkflowEventCallback | None = None,
        mode: WorkflowMode = WorkflowMode.STANDARD,
        conversation_id: str | None = None,
        skip_confirmation: bool | None = None,
    ) -> WorkflowSession:
        """提交长任务到工作流引擎（非流式）

        Args:
            user_message: 用户的长任务请求
            provider: LLM provider（默认使用系统配置）
            model: LLM model（默认使用系统配置）
            event_callback: 事件回调（可选），用于推送执行进度
            mode: 工作流执行模式（standard）
            conversation_id: 关联对话 ID（可选，用于持久化和前端跳转）
            skip_confirmation: 覆盖模式默认的 skip_confirmation（None 表示使用模式默认值）

        Returns:
            WorkflowSession: 包含完整执行过程的会话对象
        """
        session = self._create_session(user_message, mode, conversation_id, skip_confirmation=skip_confirmation)
        await self._register_session(session)

        try:
            await self._run_workflow(session, provider, model, event_callback)
        except Exception as e:
            logger.error(
                f"[WorkflowEngine] Session {session.session_id} failed: {e}",
                exc_info=True,
            )
            session.phase = WorkflowPhase.FAILED
            session.error = str(e)
            session.completed_at = utc_now()

        return session

    async def submit_stream(
        self,
        user_message: str,
        provider: str | None = None,
        model: str | None = None,
        mode: WorkflowMode = WorkflowMode.STANDARD,
        conversation_id: str | None = None,
        skip_confirmation: bool | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """提交长任务到工作流引擎（流式）

        逐步 yield 事件，包含 session_start、phase_change、task_started、
        task_completed、module_action、final_result 等事件类型。

        Args:
            user_message: 用户的长任务请求
            provider: LLM provider
            model: LLM model
            mode: 工作流执行模式（standard）
            conversation_id: 关联对话 ID（可选，用于持久化和前端跳转）
            skip_confirmation: 覆盖模式默认的 skip_confirmation（None 表示使用模式默认值）

        Yields:
            dict: 事件字典
        """
        from app.core.workflow.register_tools import set_emitter, remove_emitter

        session = self._create_session(user_message, mode, conversation_id, skip_confirmation=skip_confirmation)
        await self._register_session(session)

        logger.debug(f"[WorkflowEngine][DEBUG] submit_stream START: session_id={session.session_id}")
        logger.debug(f"[WorkflowEngine][DEBUG] submit_stream: provider={provider}, model={model}, mode={mode.value}")
        logger.debug(f"[WorkflowEngine][DEBUG] submit_stream: user_message (len={len(user_message)}): {user_message[:300]}")
        logger.debug(f"[WorkflowEngine][DEBUG] submit_stream: max_iterations={session.max_iterations}, max_concurrent={session.max_concurrent}, skip_confirmation={session.skip_confirmation}")

        # 创建事件推送器，将模块事件合并到 SSE 流
        emitter = WorkflowEventEmitter(session.session_id)
        set_emitter(session.session_id, emitter)
        logger.debug(f"[WorkflowEngine][DEBUG] submit_stream: emitter created and registered for session {session.session_id}")

        event_queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

        async def _callback(event: dict[str, Any]) -> None:
            event_type = event.get("type", "unknown")
            logger.debug(f"[WorkflowEngine][DEBUG] Session {session.session_id} _callback received event: type={event_type}")
            await event_queue.put(event)

        async def _run():
            forwarder = None
            try:
                # 保存用户消息到 conversation_store（工作流模式复用普通对话的持久化机制）
                if session.conversation_id:
                    try:
                        conv = await _get_conversation_store().get_async(session.conversation_id)
                        if conv:
                            _get_chat_service_cls().save_user_message(conv, session.user_message)
                            await _get_chat_service_cls().persist_conv(session.conversation_id, conv)
                            logger.debug(f"[WorkflowEngine][DEBUG] Session {session.session_id} user message saved to conversation {session.conversation_id}")
                    except Exception as save_err:
                        logger.warning(f"[WorkflowEngine] Save user message failed: {save_err}")

                # 启动 emitter 事件转发任务
                async def _forward_emitter_events():
                    async for event in emitter.stream():
                        logger.debug(f"[WorkflowEngine][DEBUG] Session {session.session_id} emitter forwarded event: type={event.get('type', 'unknown')}")
                        await event_queue.put(event)

                forwarder = asyncio.create_task(_forward_emitter_events())
                logger.debug(f"[WorkflowEngine][DEBUG] Session {session.session_id} emitter forwarder task started")

                logger.debug(f"[WorkflowEngine][DEBUG] Session {session.session_id} calling _run_workflow...")
                await self._run_workflow(session, provider, model, _callback)
                logger.debug(f"[WorkflowEngine][DEBUG] Session {session.session_id} _run_workflow completed")

                # 工作流完成后，保存 assistant 消息到 conversation_store
                if session.conversation_id and session.final_result:
                    try:
                        conv = await _get_conversation_store().get_async(session.conversation_id)
                        if conv:
                            _get_chat_service_cls().save_assistant_message(conv, {
                                "content": session.final_result,
                                "reasoning": "",
                                "aborted": session.phase == WorkflowPhase.FAILED,
                            })
                            await ChatService.persist_conv(session.conversation_id, conv)
                            logger.debug(f"[WorkflowEngine][DEBUG] Session {session.session_id} assistant message saved to conversation {session.conversation_id}")
                    except Exception as save_err:
                        logger.warning(f"[WorkflowEngine] Save assistant message failed: {save_err}")

                # 工作流完成后，结束 emitter
                await emitter.finish()
                if forwarder:
                    await forwarder
                logger.debug(f"[WorkflowEngine][DEBUG] Session {session.session_id} emitter finished and forwarder joined")
            except Exception as e:
                logger.error(
                    f"[WorkflowEngine] Stream session {session.session_id} failed: {e}",
                    exc_info=True,
                )
                logger.debug(f"[WorkflowEngine][DEBUG] Session {session.session_id} _run exception: {type(e).__name__}: {e}")
                session.phase = WorkflowPhase.FAILED
                session.error = str(e)
                session.completed_at = utc_now()
                # 异常时也保存 assistant 消息（记录错误信息），避免聊天记录丢失
                if session.conversation_id:
                    try:
                        conv = await _get_conversation_store().get_async(session.conversation_id)
                        if conv:
                            _get_chat_service_cls().save_assistant_message(conv, {
                                "content": f"工作流执行失败：{e}",
                                "reasoning": "",
                                "aborted": True,
                            })
                            await ChatService.persist_conv(session.conversation_id, conv)
                    except Exception as save_err:
                        logger.warning(f"[WorkflowEngine] Save error assistant message failed: {save_err}")
                await event_queue.put({
                    "type": "error",
                    "data": {"message": str(e)},
                })
            finally:
                await emitter.finish()
                remove_emitter(session.session_id)
                await event_queue.put(None)
                logger.debug(f"[WorkflowEngine][DEBUG] Session {session.session_id} _run finally: emitter removed, queue sentinel sent")

        runner = asyncio.create_task(_run())
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session.session_id} runner task created")

        logger.debug(f"[WorkflowEngine][DEBUG] Session {session.session_id} yielding session_start event")
        yield {
            "type": "session_start",
            "data": {
                "session_id": session.session_id,
                "phase": WorkflowPhase.ANALYZING.value,
            },
        }

        event_count = 0
        while True:
            event = await event_queue.get()
            if event is None:
                logger.debug(f"[WorkflowEngine][DEBUG] Session {session.session_id} received sentinel (None), breaking event loop. total_events={event_count}")
                break
            event_count += 1
            event_type = event.get("type", "unknown")
            logger.debug(f"[WorkflowEngine][DEBUG] Session {session.session_id} yielding event #{event_count}: type={event_type}")
            yield event

        logger.debug(f"[WorkflowEngine][DEBUG] Session {session.session_id} awaiting runner to complete")
        await runner
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session.session_id} submit_stream END")

    async def _run_workflow(
        self,
        session: WorkflowSession,
        provider: str | None,
        model: str | None,
        event_callback: WorkflowEventCallback | None,
    ) -> None:
        """执行工作流完整流程"""
        session_id = session.session_id
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} _run_workflow START")
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} _run_workflow: provider={provider}, model={model}")

        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} emitting phase_change: ANALYZING")
        await self._emit(event_callback, {
            "type": "phase_change",
            "data": {"phase": WorkflowPhase.ANALYZING.value},
        })

        # 阶段 1: 分析和规划
        session.phase = WorkflowPhase.PLANNING
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} emitting phase_change: PLANNING")
        await self._emit(event_callback, {
            "type": "phase_change",
            "data": {"phase": WorkflowPhase.PLANNING.value},
        })

        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} calling _analyze_and_plan...")
        plan = await self._analyze_and_plan(
            session, provider, model, event_callback,
        )
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} _analyze_and_plan returned: plan={type(plan).__name__}, has_tasks={bool(plan and plan.get('tasks'))}")

        if not plan or not plan.get("tasks"):
            # 无需工具调用，直接返回分析结果
            # 如果用户询问工具/能力，主动附加可用工具列表，避免只返回一句空泛分析
            logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} no tasks in plan, building direct response")
            analysis = plan.get("analysis", "无法处理该请求") if plan else "无法处理该请求"
            tools_text = self._format_available_tools_for_user()
            final_result = analysis
            if tools_text and ("工具" in session.user_message or "能" in session.user_message or "哪些" in session.user_message):
                final_result = f"{analysis}\n\n{tools_text}"
                logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} appended available tools to direct response")
            session.phase = WorkflowPhase.COMPLETED
            session.final_result = final_result
            session.completed_at = utc_now()
            logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} emitting final_result (direct): content_len={len(session.final_result)}")
            await self._emit(event_callback, {
                "type": "final_result",
                "data": {"content": session.final_result},
            })
            logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} _run_workflow END (no tasks)")
            return

        session.plan = plan.get("plan", "")
        tasks = self._create_tasks_from_plan(plan)
        session.tasks = tasks
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} created {len(tasks)} WorkflowTask objects from plan")
        for i, t in enumerate(tasks):
            logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} task[{i}]: id={t.task_id}, title={t.title}, tool={t.tool_name}, type={t.task_type.value}, priority={t.priority.value}, depends_on={t.depends_on}")

        # 持久化会话和节点到数据库
        try:
            import json as _json
            from app.services.workflow_persistence import save_workflow_session, save_workflow_nodes
            await save_workflow_session(
                session_id=session.session_id,
                user_message=session.user_message,
                mode=session.mode.value,
                phase=session.phase.value,
                analysis=plan.get("analysis"),
                plan_json=_json.dumps(plan, ensure_ascii=False),
                conversation_id=session.conversation_id,
            )
            await save_workflow_nodes(session.session_id, [t.to_dict() for t in tasks])
            logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} persisted to database")
        except Exception as persist_err:
            logger.warning(f"[WorkflowEngine] Persistence failed: {persist_err}")

        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} emitting plan_created: task_count={len(tasks)}")
        await self._emit(event_callback, {
            "type": "plan_created",
            "data": {
                "plan": session.plan,
                "task_count": len(tasks),
                "tasks": [t.to_dict() for t in tasks],
            },
        })

        # 计划确认机制（借鉴 deer-flow ClarificationMiddleware）
        # P2：闪电模式（skip_confirmation=True）跳过用户确认，直接执行
        if session.skip_confirmation:
            logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} skip_confirmation=True (mode={session.mode.value}), auto-confirming plan")
            await self._emit(event_callback, {
                "type": "plan_auto_confirmed",
                "data": {
                    "session_id": session_id,
                    "mode": session.mode.value,
                    "plan": session.plan,
                    "task_count": len(tasks),
                },
            })
        else:
            # 推送 plan_pending_confirmation 事件，暂停等待用户确认
            session.phase = WorkflowPhase.WAITING_CONFIRMATION
            logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} emitting phase_change: WAITING_CONFIRMATION")
            await self._emit(event_callback, {
                "type": "phase_change",
                "data": {"phase": WorkflowPhase.WAITING_CONFIRMATION.value},
            })
            logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} emitting plan_pending_confirmation")
            await self._emit(event_callback, {
                "type": "plan_pending_confirmation",
                "data": {
                    "session_id": session_id,
                    "plan": session.plan,
                    "task_count": len(tasks),
                    "tasks": [t.to_dict() for t in tasks],
                },
            })

            # 阻塞等待用户确认
            logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} waiting for user confirmation...")
            await session.confirmation_event.wait()
            logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} confirmation received: result={session.confirmation_result}, feedback={session.confirmation_feedback[:200] if session.confirmation_feedback else ''}")

            if not session.confirmation_result:
                # 用户拒绝执行
                session.phase = WorkflowPhase.COMPLETED
                session.completed_at = utc_now()
                reject_msg = f"用户拒绝了执行计划。{f' 反馈: {session.confirmation_feedback}' if session.confirmation_feedback else ''}"
                session.final_result = reject_msg
                logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} plan rejected, emitting final_result")
                await self._emit(event_callback, {
                    "type": "plan_rejected",
                    "data": {
                        "feedback": session.confirmation_feedback,
                    },
                })
                await self._emit(event_callback, {
                    "type": "final_result",
                    "data": {"content": reject_msg},
                })
                logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} _run_workflow END (plan rejected)")
                return

            # 用户确认执行，继续
            logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} plan confirmed, proceeding to execution")
            await self._emit(event_callback, {
                "type": "plan_confirmed",
                "data": {
                    "feedback": session.confirmation_feedback,
                },
            })

        # 阶段 2: 执行子任务
        session.phase = WorkflowPhase.EXECUTING
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} emitting phase_change: EXECUTING")
        await self._emit(event_callback, {
            "type": "phase_change",
            "data": {"phase": WorkflowPhase.EXECUTING.value},
        })

        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} calling _execute_tasks...")
        await self._execute_tasks(session, event_callback)
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} _execute_tasks completed")

        # 阶段 3: 直接汇总结果（不调用 LLM，避免上下文膨胀）
        # LLM 只负责输出计划，工具执行结果由前端拼接展示
        session.phase = WorkflowPhase.COMPLETED
        session.completed_at = utc_now()

        # P3 Layer 1：压缩超长工具结果，避免最终摘要上下文膨胀
        # 前端已通过 task_completed 事件收到完整结果，此处仅压缩存储版本
        workflow_context_manager.compact_task_results(session.tasks)

        # 生成结果摘要（从工具输出中提取，不调用 LLM）
        completed = [t for t in session.tasks if t.status == WorkflowStatus.COMPLETED]
        failed = [t for t in session.tasks if t.status == WorkflowStatus.FAILED]
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} task results: completed={len(completed)}, failed={len(failed)}, total={len(session.tasks)}")
        summary_lines = []
        if completed:
            summary_lines.append(f"已完成 {len(completed)} 个子任务：")
            for t in completed:
                summary_lines.append(f"  - {t.title}: {t.result[:200] if t.result else '成功'}")
        if failed:
            summary_lines.append(f"失败 {len(failed)} 个子任务：")
            for t in failed:
                summary_lines.append(f"  - {t.title}: {t.error or '未知错误'}")
        if not summary_lines:
            summary_lines.append("没有子任务需要执行")

        final_result = "\n".join(summary_lines)
        session.final_result = final_result
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} final_result (len={len(final_result)}): {final_result[:500]}")

        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} emitting final_result with stats")
        await self._emit(event_callback, {
            "type": "final_result",
            "data": {
                "content": final_result,
                "stats": {
                    "total": len(session.tasks),
                    "completed": session.completed_task_count,
                    "failed": session.failed_task_count,
                },
            },
        })
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} _run_workflow END (with tasks)")

    async def _analyze_and_plan(
        self,
        session: WorkflowSession,
        provider: str | None,
        model: str | None,
        event_callback: WorkflowEventCallback | None,
    ) -> dict[str, Any] | None:
        """调用 LLM 分析任务并生成执行计划

        使用 return_raw=True 获取完整响应（含 reasoning 思考过程），
        并提取 <think></think> 标签内的思考内容，推送到前端 SSE 流。
        """
        llm_adapter = _get_llm_adapter()

        session_id = session.session_id
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} _analyze_and_plan START")
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} provider={provider}, model={model}")
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} user_message (len={len(session.user_message)}): {session.user_message[:300]}")

        # 工具清单注入（S1b 瘦身）：常驻核心工具给完整 schema，其余仅名称+一句话；
        # 按用户消息召回 top-K 补全 schema；长尾工具用 tool.read 按需取完整定义
        recalled = internal_tool_registry.search(session.user_message, top_k=8)
        recalled_names = {t.name for t in recalled}
        core_schemas = internal_tool_registry.get_schemas_for(
            set(_CORE_INTERNAL_TOOLS) | recalled_names,
        )
        available_tools = {
            "core_tools": core_schemas,
            "other_tools_name_only": internal_tool_registry.get_module_summary(),
            "hint": (
                "core_tools 含完整参数 schema；other_tools_name_only 仅列出名称与用途，"
                "规划使用其中某个工具前，先调用 tool.read 获取其完整参数定义。"
            ),
        }
        tools_text = json.dumps(available_tools, ensure_ascii=False)
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} core_tools count={len(core_schemas)}")
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} tools_text (len={len(tools_text)}): {tools_text[:500]}")

        system_prompt = _WORKFLOW_SYSTEM_PROMPT.format(available_tools=tools_text)
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} system_prompt (len={len(system_prompt)}): {system_prompt[:500]}")

        # 注入记忆上下文到 system prompt（专业模式标准行为）
        system_prompt = workflow_context_manager.inject_memory_context(
            system_prompt=system_prompt,
            query=session.user_message,
            conversation_id=session.conversation_id if hasattr(session, 'conversation_id') else None,
        )
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} system_prompt after memory injection (len={len(system_prompt)})")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": session.user_message},
        ]
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} messages count={len(messages)}")

        actual_provider = provider or llm_adapter.default_provider
        if model is None:
            provider_obj = llm_adapter.get_provider(actual_provider)
            model = provider_obj.default_model if provider_obj else ""
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} resolved provider={actual_provider}, model={model}")
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} mode={session.mode.value}, planning_temperature={session.planning_temperature}, planning_max_tokens={session.planning_max_tokens}")

        await self._emit(event_callback, {
            "type": "planning",
            "data": {"message": "正在分析任务并生成执行计划..."},
        })

        # 流式调用 LLM，实时推送 reasoning 和 content_delta 事件
        # 改造原因：原非流式 llm_adapter.chat 导致分析阶段无流式输出，用户长时间等待无反馈
        content = ""
        reasoning = ""
        finish_reason = "stop"
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} calling llm_adapter.chat_stream...")
        async for chunk in llm_adapter.chat_stream(
            messages=messages,
            provider_name=actual_provider,
            model=model,
            temperature=session.planning_temperature,
            max_tokens=session.planning_max_tokens,
            route_hint=RouteHint.REASONER,
        ):
            if chunk.type == "content":
                delta = chunk.data.get("content", "")
                if delta:
                    content += delta
                    # 实时推送 content_delta 事件（前端用于流式显示直接回复）
                    await self._emit(event_callback, {
                        "type": "content_delta",
                        "data": {"content": delta},
                    })
            elif chunk.type == "reasoning":
                delta = chunk.data.get("reasoning", "")
                if delta:
                    reasoning += delta
                    # 实时推送 reasoning 事件（思考过程增量）
                    await self._emit(event_callback, {
                        "type": "reasoning",
                        "data": {
                            "content": delta,
                            "phase": "planning",
                        },
                    })
            elif chunk.type == "finish_reason":
                finish_reason = chunk.data.get("finish_reason", "stop")
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} chat_stream completed: content_len={len(content)}, reasoning_len={len(reasoning)}, finish_reason={finish_reason}")

        # 检测 LLM 输出截断
        if finish_reason == "length":
            logger.warning(
                "[WorkflowEngine] Session {} LLM output truncated (finish_reason=length, "
                "max_tokens={}). Attempting JSON repair...",
                session_id, session.planning_max_tokens,
            )

        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} raw content (first 800): {content[:800]}")

        # 检测并提取 <think></think> 标签中的思考过程
        # 部分模型（DeepSeek-R1、Qwen3）将思考过程嵌入 content 的 <think> 标签中
        has_think_tag = "<think>" in content.lower() or "</think>" in content.lower()
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} has_think_tag_in_content={has_think_tag}")

        think_content = ""
        if has_think_tag:
            content_before_len = len(content)
            content, think_content = _extract_think_content(content)
            logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} extracted think_content (len={len(think_content)}): {think_content[:500]}")
            logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} content after think removal (len={len(content)}, before={content_before_len}): {content[:500]}")

        # 如果有 think 标签内容，推送为 reasoning 事件（流式过程中未作为 reasoning 推送）
        if think_content:
            logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} emitting think_content as reasoning (len={len(think_content)})")
            await self._emit(event_callback, {
                "type": "reasoning",
                "data": {
                    "content": think_content,
                    "phase": "planning",
                },
            })

        combined_reasoning = reasoning + ("\n" + think_content if think_content else "")

        logger.info(
            "[WorkflowEngine] Session {} LLM response: content_len={}, reasoning_len={}, think_tag={}",
            session_id, len(content), len(combined_reasoning), has_think_tag,
        )
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} content for JSON extraction (first 800): {content[:800]}")

        plan = _extract_json_plan(content)
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} _extract_json_plan result: {type(plan).__name__}, keys={list(plan.keys()) if plan else 'None'}")

        if plan:
            task_count = len(plan.get("tasks", []))
            logger.info(
                f"[WorkflowEngine] Session {session_id} plan created with {task_count} tasks"
            )
            logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} plan details: analysis={plan.get('analysis', '')[:200]}, plan={plan.get('plan', '')[:200]}")
            if task_count > 0:
                for i, t in enumerate(plan.get("tasks", [])):
                    logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} task[{i}]: title={t.get('title')}, tool={t.get('tool_name')}, priority={t.get('priority')}")
        else:
            logger.info(
                f"[WorkflowEngine] Session {session_id} no structured plan, using direct response"
            )
            logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} falling back to direct response as analysis")
            # 如果 LLM 输出被截断且 JSON 修复失败，在 analysis 中附加提示
            if finish_reason == "length":
                return {
                    "analysis": content + "\n\n[注意：LLM 输出因 token 限制被截断，JSON 计划不完整。请考虑简化任务。]",
                    "plan": "",
                    "tasks": [],
                }
            return {"analysis": content, "plan": "", "tasks": []}

        return plan

    def _create_tasks_from_plan(self, plan: dict[str, Any]) -> list[WorkflowTask]:
        """从 LLM 规划结果创建 WorkflowTask 列表"""
        tasks_def = plan.get("tasks", [])
        title_to_id: dict[str, str] = {}
        workflow_tasks: list[WorkflowTask] = []

        for task_def in tasks_def:
            title = task_def.get("title", f"task_{len(workflow_tasks)}")
            task_id = f"wf_task_{uuid.uuid4().hex[:8]}"
            title_to_id[title] = task_id

        for task_def in tasks_def:
            title = task_def.get("title", "")
            tool_name = task_def.get("tool_name", "")
            task_type = self._infer_task_type(tool_name)
            priority_str = task_def.get("priority", "normal")
            try:
                priority = WorkflowPriority(priority_str)
            except ValueError:
                priority = WorkflowPriority.NORMAL

            depends_on_titles = task_def.get("depends_on", [])
            depends_on_ids = [
                title_to_id.get(dep, dep) for dep in depends_on_titles
            ]

            task = WorkflowTask(
                title=title,
                description=task_def.get("description", ""),
                task_type=task_type,
                tool_name=tool_name,
                arguments=task_def.get("arguments", {}),
                depends_on=depends_on_ids,
                priority=priority,
                node_type=task_def.get("node_type", "tool"),
            )
            workflow_tasks.append(task)

        return workflow_tasks

    def _infer_task_type(self, tool_name: str) -> WorkflowTaskType:
        """根据工具名推断任务类型"""
        if not tool_name:
            return WorkflowTaskType.CUSTOM
        prefix = tool_name.split(".")[0].lower()
        mapping = {
            "browser": WorkflowTaskType.BROWSER,
            "schedule": WorkflowTaskType.SCHEDULE,
            "memory": WorkflowTaskType.MEMORY,
            "console": WorkflowTaskType.CONSOLE,
            "market": WorkflowTaskType.MARKET,
            "smart_home": WorkflowTaskType.SMART_HOME,
            "smarthome": WorkflowTaskType.SMART_HOME,
            "device": WorkflowTaskType.DEVICE,
            "platform": WorkflowTaskType.PLATFORM,
            "subagent": WorkflowTaskType.SUBAGENT,
            "delegate": WorkflowTaskType.SUBAGENT,
        }
        return mapping.get(prefix, WorkflowTaskType.CUSTOM)

    def _format_available_tools_for_user(self) -> str:
        """将内部模块接口列表格式化为用户友好的文本

        当用户直接询问"有哪些工具/能做什么"时，在无需调用工具的分支中
        主动附加可用工具列表，避免只返回一句空泛分析。
        """
        try:
            modules = internal_tool_registry.get_module_summary()
            if not modules:
                return ""

            lines: list[str] = []
            lines.append("## 当前可用的内部工具")
            lines.append("")
            for module in sorted(modules, key=lambda m: m.get("module", "")):
                module_name = module.get("module", "其他")
                lines.append(f"**{module_name}**")
                tools = module.get("tools", [])
                if not tools:
                    lines.append("  - 暂无工具")
                    continue
                for tool in sorted(tools, key=lambda t: t.get("name", "")):
                    name = tool.get("name", "")
                    desc = tool.get("description", "")
                    lines.append(f"  - `{name}`: {desc}")
                lines.append("")
            return "\n".join(lines).strip()
        except Exception as e:
            logger.debug(f"[WorkflowEngine][DEBUG] _format_available_tools_for_user failed: {e}")
            return ""

    async def _execute_tasks(
        self,
        session: WorkflowSession,
        event_callback: WorkflowEventCallback | None,
    ) -> None:
        """按依赖关系执行子任务

        参考 claude-code 的分区批处理策略：
        - 依赖已满足的任务可以并行执行
        - 有依赖关系的任务串行执行
        """
        session_id = session.session_id
        completed_ids: set[str] = set()
        failed_ids: set[str] = set()
        max_rounds = len(session.tasks) + 1
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} _execute_tasks START: total_tasks={len(session.tasks)}, max_rounds={max_rounds}")

        for round_num in range(1, max_rounds + 1):
            logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} _execute_tasks round {round_num}/{max_rounds}: completed={len(completed_ids)}, failed={len(failed_ids)}")
            if session.abort_requested:
                logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} abort requested, cancelling pending tasks")
                for task in session.tasks:
                    if task.status == WorkflowStatus.PENDING:
                        task.mark_cancelled()
                break

            ready = self._get_ready_tasks(session, completed_ids, failed_ids)
            logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} round {round_num}: ready_tasks={len(ready)}")
            if not ready:
                stuck = [
                    t for t in session.tasks
                    if t.status == WorkflowStatus.PENDING
                ]
                logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} no ready tasks, stuck_tasks={len(stuck)}")
                for t in stuck:
                    t.mark_failed("Unresolvable dependency")
                    failed_ids.add(t.task_id)
                    await self._emit(event_callback, {
                        "type": "task_failed",
                        "data": {
                            "task_id": t.task_id,
                            "title": t.title,
                            "error": "Unresolvable dependency",
                        },
                    })
                break

            if len(ready) == 1:
                logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} round {round_num}: executing single task {ready[0].task_id} ({ready[0].title})")
                await self._execute_single_task(ready[0], session, event_callback)
            else:
                logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} round {round_num}: executing {len(ready)} tasks in parallel: {[t.task_id for t in ready]}")
                results = await asyncio.gather(*[
                    self._execute_single_task(t, session, event_callback)
                    for t in ready
                ], return_exceptions=True)
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(
                            f"[WorkflowEngine] Task {ready[i].task_id} "
                            f"gather error: {result}"
                        )
                        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} gather exception for task {ready[i].task_id}: {type(result).__name__}: {result}")

            for t in ready:
                if t.status == WorkflowStatus.COMPLETED:
                    completed_ids.add(t.task_id)
                elif t.status == WorkflowStatus.FAILED:
                    failed_ids.add(t.task_id)

            if len(completed_ids) + len(failed_ids) >= len(session.tasks):
                logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} all tasks resolved (completed={len(completed_ids)}, failed={len(failed_ids)}), breaking")
                break

        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} _execute_tasks END: completed={len(completed_ids)}, failed={len(failed_ids)}")

    def _get_ready_tasks(
        self,
        session: WorkflowSession,
        completed_ids: set[str],
        failed_ids: set[str],
    ) -> list[WorkflowTask]:
        """获取依赖已满足的待执行任务"""
        ready = []
        for task in session.tasks:
            if task.status != WorkflowStatus.PENDING:
                continue
            deps_ok = all(
                dep in completed_ids or dep in failed_ids
                for dep in task.depends_on
            )
            if deps_ok:
                ready.append(task)
        ready.sort(key=lambda t: {
            WorkflowPriority.URGENT: 0,
            WorkflowPriority.HIGH: 1,
            WorkflowPriority.NORMAL: 2,
            WorkflowPriority.LOW: 3,
        }[t.priority])
        return ready[:session.max_concurrent]

    async def _execute_single_task(
        self,
        task: WorkflowTask,
        session: WorkflowSession,
        event_callback: WorkflowEventCallback | None,
    ) -> None:
        """执行单个子任务"""
        session_id = session.session_id
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} _execute_single_task START: task_id={task.task_id}, title={task.title}, tool={task.tool_name}")
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} task arguments: {json.dumps(task.arguments, ensure_ascii=False)[:500]}")
        task.mark_running()
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} task {task.task_id} marked as RUNNING")

        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} emitting task_started: task_id={task.task_id}")
        await self._emit(event_callback, {
            "type": "task_started",
            "data": {
                "task_id": task.task_id,
                "title": task.title,
                "description": task.description,
                "tool_name": task.tool_name,
                "task_type": task.task_type.value,
            },
        })

        try:
            if not task.tool_name:
                logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} task {task.task_id} has no tool_name, marking as completed (skipped)")
                task.mark_completed("任务无需工具调用，已跳过")
                await self._emit(event_callback, {
                    "type": "task_completed",
                    "data": {
                        "task_id": task.task_id,
                        "title": task.title,
                        "result": task.result,
                    },
                })
                return

            logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} task {task.task_id} calling internal_tool_registry.execute: tool={task.tool_name}")
            result = await internal_tool_registry.execute(
                task.tool_name, task.arguments,
                session_id=session_id,
                conversation_id=getattr(session, "conversation_id", None),
            )
            logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} task {task.task_id} tool execution returned: success={result.success}, output_len={len(result.output) if result.output else 0}, error={result.error}")

            if result.success:
                task.mark_completed(result.output)
                task.metadata = result.metadata
                logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} task {task.task_id} marked as COMPLETED, result_len={len(result.output) if result.output else 0}")
                await self._emit(event_callback, {
                    "type": "task_completed",
                    "data": {
                        "task_id": task.task_id,
                        "title": task.title,
                        "result": result.output,
                        "metadata": result.metadata,
                    },
                })
            else:
                task.mark_failed(result.error)
                logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} task {task.task_id} marked as FAILED: error={result.error}")
                await self._emit(event_callback, {
                    "type": "task_failed",
                    "data": {
                        "task_id": task.task_id,
                        "title": task.title,
                        "error": result.error,
                    },
                })

        except Exception as e:
            logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} task {task.task_id} exception: {type(e).__name__}: {e}")
            task.mark_failed(str(e))
            await self._emit(event_callback, {
                "type": "task_failed",
                "data": {
                    "task_id": task.task_id,
                    "title": task.title,
                    "error": str(e),
                },
            })
        logger.debug(f"[WorkflowEngine][DEBUG] Session {session_id} _execute_single_task END: task_id={task.task_id}, final_status={task.status.value}")

    async def _synthesize_results(
        self,
        session: WorkflowSession,
        provider: str | None,
        model: str | None,
        event_callback: WorkflowEventCallback | None,
    ) -> str:
        """综合所有子任务结果，生成最终回复"""
        llm_adapter = _get_llm_adapter()

        completed = [t for t in session.tasks if t.status == WorkflowStatus.COMPLETED]
        failed = [t for t in session.tasks if t.status == WorkflowStatus.FAILED]

        if not completed and not failed:
            return "工作流未产生任何结果"

        results_text = ""
        for task in completed:
            results_text += f"\n### {task.title}\n{task.result or '(无结果)'}\n"

        if failed:
            results_text += "\n### 失败的任务\n"
            for task in failed:
                results_text += f"- {task.title}: {task.error}\n"

        synthesis_prompt = f"""你是 LuomiNest 主 Agent，请综合工作流执行结果，给出最终回复。

用户原始请求: {session.user_message}

执行计划: {session.plan or '无'}

各子任务执行结果:
{results_text}

要求：
1. 整合各子任务的关键结果
2. 去除重复内容
3. 保持逻辑清晰
4. 如有失败的任务，说明影响和替代方案
5. 使用中文回复"""

        messages = [
            {"role": "system", "content": synthesis_prompt},
            {"role": "user", "content": "请综合以上结果，给出最终回复。"},
        ]

        actual_provider = provider or llm_adapter.default_provider
        if model is None:
            provider_obj = llm_adapter.get_provider(actual_provider)
            model = provider_obj.default_model if provider_obj else ""

        result = await llm_adapter.chat(
            messages=messages,
            provider_name=actual_provider,
            model=model,
            temperature=session.synthesis_temperature,
            max_tokens=1500,
            route_hint=RouteHint.REASONER,
        )

        return str(result)

    async def _emit(
        self,
        callback: WorkflowEventCallback | None,
        event: dict[str, Any],
    ) -> None:
        """安全推送事件"""
        if callback is None:
            return
        try:
            await callback(event)
        except Exception as e:
            logger.warning("[WorkflowEngine] Event callback failed: {}", str(e))

    def get_session(self, session_id: str) -> WorkflowSession | None:
        """获取指定 ID 的工作流会话"""
        return self._active_sessions.get(session_id)

    def list_active_sessions(self) -> list[WorkflowSession]:
        """列出所有活跃的工作流会话"""
        return [
            s for s in self._active_sessions.values()
            if not s.is_terminal
        ]

    async def cancel_session(self, session_id: str) -> bool:
        """请求取消工作流会话

        采用协作式取消：设置 abort_requested 标志，
        正在执行的任务会完成后检查该标志。
        """
        session = self._active_sessions.get(session_id)
        if session is None:
            return False
        if session.is_terminal:
            return False
        session.abort_requested = True
        logger.info(f"[WorkflowEngine] Cancel requested for session {session_id}")
        return True

    def confirm_session(self, session_id: str, feedback: str = "") -> bool:
        """确认执行工作流计划

        用户在 plan_pending_confirmation 阶段确认后调用此方法，
        触发 confirmation_event，工作流继续执行。

        Args:
            session_id: 工作流会话 ID
            feedback: 用户反馈（可选）

        Returns:
            bool: 是否成功触发确认
        """
        session = self._active_sessions.get(session_id)
        if session is None:
            return False
        if session.phase != WorkflowPhase.WAITING_CONFIRMATION:
            return False
        session.confirmation_result = True
        session.confirmation_feedback = feedback
        session.confirmation_event.set()
        logger.info(f"[WorkflowEngine] Session {session_id} confirmed by user")
        return True

    def reject_session(self, session_id: str, feedback: str = "") -> bool:
        """拒绝执行工作流计划

        用户在 plan_pending_confirmation 阶段拒绝后调用此方法，
        触发 confirmation_event，工作流终止。

        Args:
            session_id: 工作流会话 ID
            feedback: 拒绝原因（可选）

        Returns:
            bool: 是否成功触发拒绝
        """
        session = self._active_sessions.get(session_id)
        if session is None:
            return False
        if session.phase != WorkflowPhase.WAITING_CONFIRMATION:
            return False
        session.confirmation_result = False
        session.confirmation_feedback = feedback
        session.confirmation_event.set()
        logger.info(f"[WorkflowEngine] Session {session_id} rejected by user")
        return True

    async def cleanup_session(self, session_id: str) -> None:
        """清理已完成的会话"""
        session = self._active_sessions.get(session_id)
        if session and session.is_terminal:
            await self._unregister_session(session_id)


# 全局单例
workflow_engine = WorkflowEngine()
