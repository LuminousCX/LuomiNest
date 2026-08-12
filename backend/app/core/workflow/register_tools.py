"""内部模块接口注册

将 LuomiNest 各内部模块（浏览器、计划、记忆等）的操作注册到
internal_tool_registry，供工作流引擎调度。

每个模块的接口封装现有工具或服务，提供高层操作语义。
执行后通过 WorkflowEventEmitter 推送结构化事件到前端。
"""
import json
import functools
from typing import Any

from loguru import logger

from app.core.tools.builtin.browser_automation import BROWSER_ACTION_SPECS, _format_output
from app.core.workflow.event_emitter import WorkflowEventEmitter
from app.core.workflow.internal_registry import internal_tool_registry
from app.core.workflow.models import WorkflowTaskResult
from app.core.ports.browser_automation import execute_browser_action

# 当前活跃的事件推送器（由 WorkflowEngine 在执行前设置）
# key: session_id, value: WorkflowEventEmitter
_active_emitters: dict[str, WorkflowEventEmitter] = {}


def set_emitter(session_id: str, emitter: WorkflowEventEmitter) -> None:
    """设置当前工作流会话的事件推送器"""
    _active_emitters[session_id] = emitter


def remove_emitter(session_id: str) -> None:
    """移除事件推送器"""
    _active_emitters.pop(session_id, None)


def _get_emitter() -> WorkflowEventEmitter | None:
    """获取当前活跃的事件推送器（取最后一个）"""
    if not _active_emitters:
        return None
    # 返回最后注册的 emitter（当前正在执行的会话）
    return list(_active_emitters.values())[-1]


class _MemoryEngineNotReady(Exception):
    """记忆引擎未初始化"""
    pass


def _require_memory_engine():
    """获取记忆引擎实例，未初始化则抛出异常（由 @_wf_catch 统一捕获）。"""
    from app.engines.memory import get_memory_engine
    engine = get_memory_engine()
    if engine is None:
        raise _MemoryEngineNotReady("Memory engine not initialized")
    return engine


def _wf_catch(tool_name: str):
    """工作流工具 try/except 装饰器，统一错误日志和返回值。"""
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            try:
                return await fn(*args, **kwargs)
            except Exception as e:
                logger.error(f"[Workflow:{tool_name}] Failed: {{}}", str(e), exc_info=True)
                return WorkflowTaskResult(success=False, error=str(e))
        return wrapper
    return decorator


def _make_skill_tool_handler(tool_name: str):
    """构造技能工具的 internal handler（桥接 tool_registry 中的 ToolBase 工具）。

    洋葱架构 §11.3：皮套工坊/桌宠为 standard 模式，工具来自 internal_tool_registry，
    在此桥接 skills 工具使 standard/ultra 模式自动获得技能能力。
    """

    @_wf_catch(tool_name)
    async def handler(args: dict[str, Any]) -> WorkflowTaskResult:
        from app.core.tools.registry import tool_registry
        tool = tool_registry.get(tool_name)
        if tool is None:
            return WorkflowTaskResult(success=False, error=f"技能工具未注册: {tool_name}")
        result = await tool.execute(args or {})
        return WorkflowTaskResult(
            success=result.success,
            output=result.output,
            error=result.error,
            metadata=result.metadata,
        )

    return handler


def _make_browser_bridge_handler(tool_name: str, action: str, timeout: float):
    """创建浏览器自动化桥接 handler

    将工作流引擎的工具调用桥接到 execute_browser_action，
    通过 WebSocket 调用前端 Electron Main 的 LuomiAutomationExecutor 执行真实操作。

    Args:
        tool_name: 工具名（如 browser_navigate，用于日志和输出格式化）
        action: 前端动作名（如 navigate）
        timeout: 超时秒数
    """
    async def handler(args: dict[str, Any]) -> WorkflowTaskResult:
        try:
            data = await execute_browser_action(action, args, timeout=timeout)
            output = _format_output(tool_name, data)
            logger.info(f"[Workflow:{tool_name}] action={action} 执行成功")
            return WorkflowTaskResult(
                success=True,
                output=output,
                metadata=data,
            )
        except ConnectionError as e:
            logger.warning(f"[Workflow:{tool_name}] 浏览器未连接: {e}")
            return WorkflowTaskResult(success=False, error=str(e))
        except Exception as e:
            logger.error(f"[Workflow:{tool_name}] Failed: {e}", exc_info=True)
            return WorkflowTaskResult(success=False, error=str(e))
    return handler


async def _browser_search(args: dict[str, Any]) -> WorkflowTaskResult:
    """浏览器搜索：在浏览器中打开搜索结果页

    高层语义工具，构建搜索 URL 后调用 execute_browser_action("navigate") 导航。
    不属于 29 个细粒度浏览器自动化工具，STANDARD 模式下可用。
    """
    query = args.get("query", "")
    engine = args.get("engine", "google")
    if not query:
        return WorkflowTaskResult(success=False, error="Missing required parameter: query")

    engine_urls = {
        "google": "https://www.google.com/search?q=",
        "bing": "https://www.bing.com/search?q=",
        "baidu": "https://www.baidu.com/s?wd=",
    }
    base_url = engine_urls.get(engine, engine_urls["google"])
    url = f"{base_url}{query}"

    try:
        await execute_browser_action("navigate", {"url": url})
        logger.info(f"[Workflow:browser.search] query={query}, engine={engine}")
        return WorkflowTaskResult(
            success=True,
            output=f"已在浏览器中搜索「{query}」（{engine}）: {url}",
            metadata={"url": url, "engine": engine, "action": "navigate"},
        )
    except ConnectionError as e:
        logger.warning(f"[Workflow:browser.search] 浏览器未连接: {e}")
        return WorkflowTaskResult(success=False, error=str(e))
    except Exception as e:
        logger.error("[Workflow:browser.search] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def _schedule_create(args: dict[str, Any]) -> WorkflowTaskResult:
    """创建定时任务"""
    name = args.get("name", "")
    schedule = args.get("schedule", "")
    action = args.get("action", "")
    description = args.get("description", "")
    context = args.get("context", "")

    if not name or not schedule or not action:
        return WorkflowTaskResult(
            success=False,
            error="Missing required parameters: name, schedule, action",
        )

    try:
        from app.core.tools.builtin.scheduler_tool import CreateScheduledTaskTool

        tool = CreateScheduledTaskTool()
        result = await tool.execute(
            name=name,
            schedule=schedule,
            action=action,
            description=description,
            context=context,
        )

        if result.success:
            # 推送工作流事件
            emitter = _get_emitter()
            if emitter:
                task_id = result.metadata.get("task_id", "")
                await emitter.emit_schedule_created(
                    task_id=task_id,
                    name=name,
                    schedule=schedule,
                    action=action,
                )

            return WorkflowTaskResult(
                success=True,
                output=result.output,
                metadata=result.metadata,
            )
        return WorkflowTaskResult(success=False, error=result.error)
    except Exception as e:
        logger.error("[Workflow:schedule.create] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


@_wf_catch("memory.search")
async def _memory_search(args: dict[str, Any]) -> WorkflowTaskResult:
    """语义检索记忆中枢（基于向量检索）"""
    query = args.get("query", "")
    top_k = args.get("top_k", 5)

    if not query:
        return WorkflowTaskResult(success=False, error="Missing required parameter: query")

    engine = _require_memory_engine()

    results = await engine.vector_retrieve(query=query, k=top_k)
    results_count = len(results) if isinstance(results, list) else 0
    output = json.dumps(results, ensure_ascii=False, default=str) if results else "未找到相关记忆"

    # 推送工作流事件
    emitter = _get_emitter()
    if emitter:
        await emitter.emit_memory_recalled(
            query=query,
            results_count=results_count,
        )

    return WorkflowTaskResult(
        success=True,
        output=output,
        metadata={"count": results_count},
    )


@_wf_catch("memory.build_context")
async def _memory_build_context(args: dict[str, Any]) -> WorkflowTaskResult:
    """构建记忆上下文（按优先级注入档案/事实/知识/每日记录）"""
    query = args.get("query", "")
    conversation_id = args.get("conversation_id")
    max_chars = args.get("max_chars", 4000)

    engine = _require_memory_engine()

    context = engine.build_context(
        max_chars=max_chars,
        query=query,
        conversation_id=conversation_id,
    )

    return WorkflowTaskResult(
        success=True,
        output=context or "（无可用记忆上下文）",
        metadata={"query": query, "conversation_id": conversation_id},
    )


@_wf_catch("memory.update_knowledge")
async def _memory_update_knowledge(args: dict[str, Any]) -> WorkflowTaskResult:
    """更新知识库内容"""
    content = args.get("content", "")
    if not content:
        return WorkflowTaskResult(success=False, error="Missing required parameter: content")

    engine = _require_memory_engine()
    engine.save_knowledge(content)

    emitter = _get_emitter()
    if emitter:
        await emitter.emit_memory_stored(
            memory_id="knowledge",
            content=content[:200],
            category="knowledge",
        )

    logger.info(f"[Workflow:memory.update_knowledge] content_len={len(content)}")
    return WorkflowTaskResult(
        success=True,
        output=f"已更新知识库（{len(content)} 字符）",
    )


@_wf_catch("memory.update_profile")
async def _memory_update_profile(args: dict[str, Any]) -> WorkflowTaskResult:
    """更新用户画像（通过写入 memory.md 解析 name 和 static_facts）"""
    content = args.get("content", "")
    if not content:
        return WorkflowTaskResult(success=False, error="Missing required parameter: content")

    engine = _require_memory_engine()
    engine.save_memory(content)
    profile = engine.parse_profile()

    logger.info(f"[Workflow:memory.update_profile] name={profile.get('name', '')}")
    return WorkflowTaskResult(
        success=True,
        output=f"已更新用户画像（name={profile.get('name', '未知')}）",
        metadata={"profile": profile},
    )


@_wf_catch("memory.append_daily")
async def _memory_append_daily(args: dict[str, Any]) -> WorkflowTaskResult:
    """追加每日记录"""
    content = args.get("content", "")
    date = args.get("date")
    conversation_id = args.get("conversation_id")

    if not content:
        return WorkflowTaskResult(success=False, error="Missing required parameter: content")

    engine = _require_memory_engine()
    engine.append_daily(content, date, conversation_id=conversation_id)

    logger.info(f"[Workflow:memory.append_daily] date={date or 'today'}, len={len(content)}")
    return WorkflowTaskResult(
        success=True,
        output=f"已追加每日记录（{date or '今天'}）",
    )


@_wf_catch("memory.get_daily")
async def _memory_get_daily(args: dict[str, Any]) -> WorkflowTaskResult:
    """获取每日记录"""
    date = args.get("date")
    conversation_id = args.get("conversation_id")

    engine = _require_memory_engine()
    content = engine.load_daily(date, conversation_id)

    return WorkflowTaskResult(
        success=True,
        output=content or "（无每日记录）",
        metadata={"date": date or "today", "conversation_id": conversation_id},
    )


@_wf_catch("memory.list_dailies")
async def _memory_list_dailies(args: dict[str, Any]) -> WorkflowTaskResult:
    """列出有每日记录的日期"""
    conversation_id = args.get("conversation_id")

    engine = _require_memory_engine()
    dates = engine.list_dailies(conversation_id)

    return WorkflowTaskResult(
        success=True,
        output=json.dumps(dates, ensure_ascii=False),
        metadata={"count": len(dates), "conversation_id": conversation_id},
    )


@_wf_catch("memory.vector_rebuild")
async def _memory_vector_rebuild(args: dict[str, Any]) -> WorkflowTaskResult:
    """重建记忆向量索引"""
    conversation_id = args.get("conversation_id")

    engine = _require_memory_engine()
    count = await engine.vector_rebuild(conversation_id)

    logger.info(f"[Workflow:memory.vector_rebuild] indexed={count}")
    return WorkflowTaskResult(
        success=True,
        output=f"已重建向量索引（{count} 条）",
        metadata={"indexed_count": count},
    )


@_wf_catch("memory.promote_conversation_facts")
async def _memory_promote_conversation_facts(args: dict[str, Any]) -> WorkflowTaskResult:
    """将对话级事实提升为 Agent 级"""
    conversation_id = args.get("conversation_id", "")
    fact_ids = args.get("fact_ids")

    if not conversation_id:
        return WorkflowTaskResult(success=False, error="Missing required parameter: conversation_id")

    engine = _require_memory_engine()
    promoted_count = engine.promote_conversation_facts(conversation_id, fact_ids)

    logger.info(f"[Workflow:memory.promote_conversation_facts] promoted={promoted_count}")
    return WorkflowTaskResult(
        success=True,
        output=f"已提升 {promoted_count} 条对话级事实到 Agent 级",
        metadata={"promoted_count": promoted_count},
    )


@_wf_catch("memory.clear_facts")
async def _memory_clear_facts(args: dict[str, Any]) -> WorkflowTaskResult:
    """清空所有事实"""
    engine = _require_memory_engine()
    engine.clear_facts()

    logger.info("[Workflow:memory.clear_facts] all facts cleared")
    return WorkflowTaskResult(
        success=True,
        output="已清空所有事实",
    )


async def _console_execute(args: dict[str, Any]) -> WorkflowTaskResult:
    """执行控制台命令"""
    command = args.get("command", "")
    if not command:
        return WorkflowTaskResult(success=False, error="Missing required parameter: command")

    try:
        from app.api.v1.endpoints.console import (
            _execute_command_via_sandbox,
            _get_console_sandbox,
        )

        # 获取沙盒实例（内置白名单验证）
        sandbox = _get_console_sandbox()

        # 执行命令（沙盒环境：白名单 + 超时 + 输出截断）
        timeout = min(args.get("timeout", 30), 120)
        exit_code, stdout, stderr = await _execute_command_via_sandbox(
            sandbox, command, timeout
        )

        success = exit_code == 0
        output = stdout if success else stderr or stdout

        # 推送工作流事件
        emitter = _get_emitter()
        if emitter:
            await emitter.emit_console_output(
                command=command,
                output=output,
                success=success,
            )

        if success:
            return WorkflowTaskResult(
                success=True,
                output=output,
                metadata={"exit_code": exit_code},
            )
        return WorkflowTaskResult(
            success=False,
            error=stderr or f"命令执行失败 (exit_code={exit_code})",
        )
    except Exception as e:
        logger.error("[Workflow:console.execute] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def _schedule_list(args: dict[str, Any]) -> WorkflowTaskResult:
    """列出所有定时任务"""
    try:
        from app.core.scheduler import luomi_scheduler

        tasks = luomi_scheduler.list_tasks()
        task_list = [t.model_dump() for t in tasks]

        emitter = _get_emitter()
        if emitter:
            await emitter.emit_module_action(
                module="schedule",
                action="list",
                success=True,
                output=f"共 {len(task_list)} 个定时任务",
                metadata={"count": len(task_list)},
            )

        return WorkflowTaskResult(
            success=True,
            output=json.dumps(task_list, ensure_ascii=False),
            metadata={"count": len(task_list)},
        )
    except Exception as e:
        logger.error("[Workflow:schedule.list] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def _schedule_get(args: dict[str, Any]) -> WorkflowTaskResult:
    """获取单个定时任务详情"""
    task_id = args.get("task_id", "")
    if not task_id:
        return WorkflowTaskResult(success=False, error="Missing required parameter: task_id")

    try:
        from app.core.scheduler import luomi_scheduler

        task = luomi_scheduler.get_task(task_id)
        if not task:
            return WorkflowTaskResult(success=False, error=f"任务 {task_id} 不存在")

        return WorkflowTaskResult(
            success=True,
            output=json.dumps(task.model_dump(), ensure_ascii=False),
            metadata={"task_id": task_id},
        )
    except Exception as e:
        logger.error("[Workflow:schedule.get] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def _schedule_delete(args: dict[str, Any]) -> WorkflowTaskResult:
    """删除定时任务"""
    task_id = args.get("task_id", "")
    if not task_id:
        return WorkflowTaskResult(success=False, error="Missing required parameter: task_id")

    try:
        from app.core.scheduler import luomi_scheduler

        success = await luomi_scheduler.remove_task(task_id)
        if not success:
            return WorkflowTaskResult(success=False, error=f"任务 {task_id} 不存在")

        emitter = _get_emitter()
        if emitter:
            await emitter.emit_module_action(
                module="schedule",
                action="deleted",
                success=True,
                output=f"已删除任务 {task_id}",
                metadata={"task_id": task_id},
            )

        return WorkflowTaskResult(
            success=True,
            output=f"已删除定时任务: {task_id}",
            metadata={"task_id": task_id},
        )
    except Exception as e:
        logger.error("[Workflow:schedule.delete] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def _subagent_delegate(args: dict[str, Any]) -> WorkflowTaskResult:
    """委派任务给子 Agent"""
    task = args.get("task", "")
    context = args.get("context", "")

    if not task:
        return WorkflowTaskResult(success=False, error="Missing required parameter: task")

    try:
        from app.core.agents.subagent_executor import subagent_executor
        from app.core.tools.builtin.subagent_tool import get_subagent_event_callback

        # 读取当前异步上下文的事件回调，与 DelegateToSubagentTool 行为一致
        # 使 workflow 路径触发的子 Agent 委派也能推送 subagent_event 到 SSE 流
        event_callback = get_subagent_event_callback()

        result = await subagent_executor.execute(
            task=task,
            context=context,
            depth=0,
            event_callback=event_callback,
        )
        return WorkflowTaskResult(
            success=True,
            output=result,
            metadata={"task": task},
        )
    except Exception as e:
        logger.error("[Workflow:subagent.delegate] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def _smart_home_control(args: dict[str, Any]) -> WorkflowTaskResult:
    """控制智能家居设备

    通过平台实例（MQTT/HomeAssistant/小米IoT）向设备发送控制命令。
    """
    device_id = args.get("device_id", "")
    action = args.get("action", "")
    params = args.get("params", {})

    if not device_id or not action:
        return WorkflowTaskResult(
            success=False,
            error="Missing required parameters: device_id, action",
        )

    try:
        from app.runtime.platform.registry import list_instances
        from app.runtime.platform.base import PlatformResponse

        # 查找包含该设备 ID 的 IoT 平台实例
        instances = list_instances()
        iot_instances = [
            inst for inst in instances
            if inst.adapter_type in ("mqtt_terminal", "home_assistant", "xiaomi_iot")
        ]

        if not iot_instances:
            return WorkflowTaskResult(
                success=False,
                error="未找到已启动的 IoT 平台实例，请先在设置中配置并启动智能家居适配器",
            )

        # 向第一个活跃的 IoT 实例发送命令
        target = iot_instances[0]
        command_payload = {
            "device_id": device_id,
            "action": action,
            "params": params,
        }

        adapter = target.adapter
        if not adapter:
            return WorkflowTaskResult(
                success=False,
                error=f"实例 {target.instance_id} 没有可用的适配器",
            )

        response = PlatformResponse(
            content=json.dumps(command_payload, ensure_ascii=False),
            message_type="text",
        )
        success = await adapter.send_message(response, target=device_id)

        # 推送工作流事件
        emitter = _get_emitter()
        if emitter:
            await emitter.emit_module_action(
                module="smart_home",
                action=action,
                success=success,
                output=f"设备 {device_id} {action} 操作已发送" if success else "",
                error="" if success else "命令发送失败",
                metadata={"device_id": device_id, "action": action, "params": params},
            )

        if success:
            return WorkflowTaskResult(
                success=True,
                output=f"已向设备 {device_id} 发送 {action} 命令",
                metadata={"device_id": device_id, "action": action},
            )
        return WorkflowTaskResult(
            success=False,
            error=f"向设备 {device_id} 发送命令失败",
        )
    except Exception as e:
        logger.error("[Workflow:smart_home.control] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


@_wf_catch("memory.list_facts")
async def _memory_list_facts(args: dict[str, Any]) -> WorkflowTaskResult:
    """列出记忆中枢的事实（支持分类过滤）"""
    category = args.get("category")
    limit = min(args.get("limit", 100), 500)

    engine = _require_memory_engine()
    facts = engine.get_facts(category)
    fact_list = [f.model_dump() for f in facts[:limit]]

    return WorkflowTaskResult(
        success=True,
        output=json.dumps(fact_list, ensure_ascii=False),
        metadata={"count": len(fact_list), "category": category or "all"},
    )


@_wf_catch("memory.create_fact")
async def _memory_create_fact(args: dict[str, Any]) -> WorkflowTaskResult:
    """在记忆中枢创建事实"""
    content = args.get("content", "")
    category = args.get("category", "context")
    confidence = args.get("confidence", 0.8)

    if not content:
        return WorkflowTaskResult(success=False, error="Missing required parameter: content")

    from app.engines.memory.memory_engine import FactItem, FACT_CATEGORIES

    if category not in FACT_CATEGORIES:
        return WorkflowTaskResult(
            success=False,
            error=f"Invalid category. Must be one of: {FACT_CATEGORIES}",
        )

    engine = _require_memory_engine()
    fact = FactItem(
        content=content,
        category=category,
        confidence=confidence,
        source="workflow",
    )
    engine.add_fact(fact)

    emitter = _get_emitter()
    if emitter:
        await emitter.emit_module_action(
            module="memory",
            action="fact_created",
            success=True,
            output=f"已创建事实: {content[:100]}",
            metadata={"fact_id": fact.id, "category": category},
        )

    return WorkflowTaskResult(
        success=True,
        output=f"已创建事实: {content[:100]}",
        metadata={"fact_id": fact.id, "category": category},
    )


@_wf_catch("memory.update_fact")
async def _memory_update_fact(args: dict[str, Any]) -> WorkflowTaskResult:
    """更新记忆中枢的事实"""
    fact_id = args.get("fact_id", "")
    content = args.get("content")
    category = args.get("category")
    confidence = args.get("confidence")

    if not fact_id:
        return WorkflowTaskResult(success=False, error="Missing required parameter: fact_id")

    from app.engines.memory.memory_engine import FACT_CATEGORIES

    if category is not None and category not in FACT_CATEGORIES:
        return WorkflowTaskResult(
            success=False,
            error=f"Invalid category. Must be one of: {FACT_CATEGORIES}",
        )

    engine = _require_memory_engine()
    success = engine.update_fact(fact_id, content, category, confidence)
    if not success:
        return WorkflowTaskResult(success=False, error=f"事实 {fact_id} 不存在")

    emitter = _get_emitter()
    if emitter:
        await emitter.emit_module_action(
            module="memory",
            action="fact_updated",
            success=True,
            output=f"已更新事实: {fact_id}",
            metadata={"fact_id": fact_id},
        )

    return WorkflowTaskResult(
        success=True,
        output=f"已更新事实: {fact_id}",
        metadata={"fact_id": fact_id},
    )


@_wf_catch("memory.delete_fact")
async def _memory_delete_fact(args: dict[str, Any]) -> WorkflowTaskResult:
    """删除记忆中枢的事实"""
    fact_id = args.get("fact_id", "")
    if not fact_id:
        return WorkflowTaskResult(success=False, error="Missing required parameter: fact_id")

    engine = _require_memory_engine()
    success = engine.remove_fact(fact_id)
    if not success:
        return WorkflowTaskResult(success=False, error=f"事实 {fact_id} 不存在")

    emitter = _get_emitter()
    if emitter:
        await emitter.emit_module_action(
            module="memory",
            action="fact_deleted",
            success=True,
            output=f"已删除事实: {fact_id}",
            metadata={"fact_id": fact_id},
        )

    return WorkflowTaskResult(
        success=True,
        output=f"已删除事实: {fact_id}",
        metadata={"fact_id": fact_id},
    )


@_wf_catch("memory.get_summary")
async def _memory_get_summary(args: dict[str, Any]) -> WorkflowTaskResult:
    """获取记忆中枢的摘要"""
    engine = _require_memory_engine()
    content = engine.load_summary()

    return WorkflowTaskResult(
        success=True,
        output=content or "暂无摘要",
        metadata={"length": len(content)},
    )


@_wf_catch("memory.update_summary")
async def _memory_update_summary(args: dict[str, Any]) -> WorkflowTaskResult:
    """更新记忆中枢的摘要"""
    content = args.get("content", "")
    if not content:
        return WorkflowTaskResult(success=False, error="Missing required parameter: content")

    engine = _require_memory_engine()
    engine.save_summary(content)

    emitter = _get_emitter()
    if emitter:
        await emitter.emit_module_action(
            module="memory",
            action="summary_updated",
            success=True,
            output=f"已更新摘要（{len(content)} 字符）",
            metadata={"length": len(content)},
        )

    return WorkflowTaskResult(
        success=True,
        output=f"已更新记忆摘要",
        metadata={"length": len(content)},
    )


@_wf_catch("memory.get_knowledge")
async def _memory_get_knowledge(args: dict[str, Any]) -> WorkflowTaskResult:
    """获取记忆中枢的知识库"""
    engine = _require_memory_engine()
    content = engine.load_knowledge()

    return WorkflowTaskResult(
        success=True,
        output=content or "暂无知识库内容",
        metadata={"length": len(content)},
    )


@_wf_catch("memory.get_profile")
async def _memory_get_profile(args: dict[str, Any]) -> WorkflowTaskResult:
    """获取用户画像"""
    engine = _require_memory_engine()
    profile = engine.parse_profile()

    return WorkflowTaskResult(
        success=True,
        output=json.dumps(profile, ensure_ascii=False),
        metadata=profile,
    )


@_wf_catch("memory.distill")
async def _memory_distill(args: dict[str, Any]) -> WorkflowTaskResult:
    """蒸馏对话为记忆"""
    messages = args.get("messages", [])
    if not messages:
        return WorkflowTaskResult(success=False, error="Missing required parameter: messages")

    engine = _require_memory_engine()
    result = await engine.distill_conversation(messages)

    emitter = _get_emitter()
    if emitter:
        await emitter.emit_module_action(
            module="memory",
            action="distilled",
            success=True,
            output="对话已蒸馏为记忆" if result else "无需蒸馏",
            metadata={"has_change": bool(result)},
        )

    return WorkflowTaskResult(
        success=True,
        output=result or "对话无需蒸馏",
        metadata={"has_change": bool(result)},
    )


async def _market_install(args: dict[str, Any]) -> WorkflowTaskResult:
    """安装扩展市场内容"""
    item_id = args.get("item_id", "")
    item_type = args.get("item_type", "")
    item_name = args.get("item_name", "")
    download_url = args.get("download_url", "")
    version = args.get("version", "1.0.0")

    if not item_id or not item_type or not item_name:
        return WorkflowTaskResult(
            success=False,
            error="Missing required parameters: item_id, item_type, item_name",
        )

    try:
        from app.infrastructure.install.install_service import download_item, is_installed

        if is_installed(item_id):
            return WorkflowTaskResult(
                success=False,
                error=f"条目 {item_id} 已安装",
            )

        result = await download_item(
            item_id=item_id,
            download_url=download_url,
            item_type=item_type,
            item_name=item_name,
            version=version,
        )

        emitter = _get_emitter()
        if emitter:
            await emitter.emit_module_action(
                module="market",
                action="installed",
                success=result.get("status") == "installed",
                output=f"已安装: {item_name}",
                error=result.get("error", ""),
                metadata={"item_id": item_id, "item_type": item_type},
            )

        return WorkflowTaskResult(
            success=result.get("status") == "installed",
            output=f"已安装: {item_name}",
            metadata={"item_id": item_id, "item_type": item_type},
        )
    except Exception as e:
        logger.error("[Workflow:market.install] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def _market_uninstall(args: dict[str, Any]) -> WorkflowTaskResult:
    """卸载扩展市场内容"""
    item_id = args.get("item_id", "")
    if not item_id:
        return WorkflowTaskResult(success=False, error="Missing required parameter: item_id")

    try:
        from app.infrastructure.install.install_service import uninstall_item

        result = await uninstall_item(item_id)
        if not result.get("success"):
            return WorkflowTaskResult(
                success=False,
                error=result.get("error", "卸载失败"),
            )

        emitter = _get_emitter()
        if emitter:
            await emitter.emit_module_action(
                module="market",
                action="uninstalled",
                success=True,
                output=f"已卸载: {item_id}",
                metadata={"item_id": item_id},
            )

        return WorkflowTaskResult(
            success=True,
            output=f"已卸载: {item_id}",
            metadata={"item_id": item_id},
        )
    except Exception as e:
        logger.error("[Workflow:market.uninstall] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def _market_list_installed(args: dict[str, Any]) -> WorkflowTaskResult:
    """列出已安装的扩展市场内容"""
    item_type = args.get("item_type")

    try:
        from app.infrastructure.install.install_service import get_installed_items

        items = get_installed_items()
        if item_type and item_type in ("plugin", "skill", "agent"):
            items = [i for i in items if i.get("type") == item_type]

        return WorkflowTaskResult(
            success=True,
            output=json.dumps(items, ensure_ascii=False),
            metadata={"count": len(items)},
        )
    except Exception as e:
        logger.error("[Workflow:market.list_installed] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def _market_get_leaderboard(args: dict[str, Any]) -> WorkflowTaskResult:
    """获取扩展市场排行榜"""
    item_type = args.get("item_type")
    sort_by = args.get("sort_by", "composite")
    limit = min(args.get("limit", 20), 100)

    try:
        from app.infrastructure.database.json_store import marketplace_stats_store

        all_stats = await marketplace_stats_store.list_all_async()
        items = []
        for item_id, stats in all_stats.items():
            if item_id.startswith("__"):
                continue
            if item_type and stats.get("type") != item_type:
                continue
            dl = stats.get("downloadCount", 0)
            lk = stats.get("likeCount", 0)
            items.append({
                "itemId": item_id,
                "downloadCount": dl,
                "likeCount": lk,
                "type": stats.get("type", ""),
                "score": dl + lk * 3,
            })

        if sort_by == "downloads":
            items.sort(key=lambda x: x["downloadCount"], reverse=True)
        elif sort_by == "likes":
            items.sort(key=lambda x: x["likeCount"], reverse=True)
        else:
            items.sort(key=lambda x: x["score"], reverse=True)

        result = items[:limit]
        return WorkflowTaskResult(
            success=True,
            output=json.dumps(result, ensure_ascii=False),
            metadata={"count": len(result)},
        )
    except Exception as e:
        logger.error("[Workflow:market.get_leaderboard] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def _platform_list_instances(args: dict[str, Any]) -> WorkflowTaskResult:
    """列出所有平台实例"""
    try:
        from app.runtime.platform.registry import list_instances

        instances = list_instances()
        instance_list = []
        for inst in instances:
            instance_list.append({
                "id": inst.instance_id,
                "adapter_type": inst.adapter_type,
                "name": inst.name,
                "status": inst.status.value if hasattr(inst.status, 'value') else str(inst.status),
                "enable": inst.enable,
            })

        return WorkflowTaskResult(
            success=True,
            output=json.dumps(instance_list, ensure_ascii=False),
            metadata={"count": len(instance_list)},
        )
    except Exception as e:
        logger.error("[Workflow:platform.list_instances] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def _platform_start_instance(args: dict[str, Any]) -> WorkflowTaskResult:
    """启动平台实例"""
    instance_id = args.get("instance_id", "")
    if not instance_id:
        return WorkflowTaskResult(success=False, error="Missing required parameter: instance_id")

    try:
        from app.runtime.platform.registry import start_instance

        await start_instance(instance_id)

        emitter = _get_emitter()
        if emitter:
            await emitter.emit_module_action(
                module="platform",
                action="started",
                success=True,
                output=f"已启动平台实例: {instance_id}",
                metadata={"instance_id": instance_id},
            )

        return WorkflowTaskResult(
            success=True,
            output=f"已启动平台实例: {instance_id}",
            metadata={"instance_id": instance_id},
        )
    except Exception as e:
        logger.error("[Workflow:platform.start_instance] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def _platform_stop_instance(args: dict[str, Any]) -> WorkflowTaskResult:
    """停止平台实例"""
    instance_id = args.get("instance_id", "")
    if not instance_id:
        return WorkflowTaskResult(success=False, error="Missing required parameter: instance_id")

    try:
        from app.runtime.platform.registry import stop_instance

        await stop_instance(instance_id)

        emitter = _get_emitter()
        if emitter:
            await emitter.emit_module_action(
                module="platform",
                action="stopped",
                success=True,
                output=f"已停止平台实例: {instance_id}",
                metadata={"instance_id": instance_id},
            )

        return WorkflowTaskResult(
            success=True,
            output=f"已停止平台实例: {instance_id}",
            metadata={"instance_id": instance_id},
        )
    except Exception as e:
        logger.error("[Workflow:platform.stop_instance] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def _platform_send_message(args: dict[str, Any]) -> WorkflowTaskResult:
    """通过平台实例发送消息"""
    instance_id = args.get("instance_id", "")
    message = args.get("message", "")
    target = args.get("target", "")

    if not instance_id or not message:
        return WorkflowTaskResult(
            success=False,
            error="Missing required parameters: instance_id, message",
        )

    try:
        from app.runtime.platform.registry import get_instance

        instance = get_instance(instance_id)
        if not instance:
            return WorkflowTaskResult(success=False, error=f"平台实例 {instance_id} 不存在")

        payload = json.dumps({
            "type": "send_message",
            "message": message,
            "target": target,
        }, ensure_ascii=False)

        success = await instance.send_message(payload)

        emitter = _get_emitter()
        if emitter:
            await emitter.emit_module_action(
                module="platform",
                action="message_sent",
                success=success,
                output=f"已发送消息到 {instance_id}" if success else "发送失败",
                metadata={"instance_id": instance_id, "target": target},
            )

        if success:
            return WorkflowTaskResult(
                success=True,
                output=f"已通过平台实例 {instance_id} 发送消息",
                metadata={"instance_id": instance_id},
            )
        return WorkflowTaskResult(success=False, error="消息发送失败")
    except Exception as e:
        logger.error("[Workflow:platform.send_message] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def _smart_home_list_devices(args: dict[str, Any]) -> WorkflowTaskResult:
    """列出智能家居设备"""
    try:
        from app.runtime.platform.registry import list_instances

        instances = list_instances()
        iot_instances = [
            inst for inst in instances
            if inst.adapter_type in ("mqtt_terminal", "home_assistant", "xiaomi_iot")
        ]

        devices = []
        for inst in iot_instances:
            devices.append({
                "instance_id": inst.instance_id,
                "name": inst.name,
                "adapter_type": inst.adapter_type,
                "status": inst.status.value if hasattr(inst.status, 'value') else str(inst.status),
            })

        return WorkflowTaskResult(
            success=True,
            output=json.dumps(devices, ensure_ascii=False),
            metadata={"count": len(devices)},
        )
    except Exception as e:
        logger.error("[Workflow:smart_home.list_devices] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def _smart_home_list_scenes(args: dict[str, Any]) -> WorkflowTaskResult:
    """列出智能家居场景"""
    try:
        from app.api.v1.endpoints.smart_home import list_scenes

        result = await list_scenes()
        scenes = result if isinstance(result, list) else []

        return WorkflowTaskResult(
            success=True,
            output=json.dumps(scenes, ensure_ascii=False),
            metadata={"count": len(scenes)},
        )
    except Exception as e:
        logger.error("[Workflow:smart_home.list_scenes] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def register_internal_tools() -> None:
    """注册所有内部模块接口到 internal_tool_registry

    在应用启动时调用（app_factory.py lifespan）。
    """
    # ─── 浏览器自动化模块（29 个真实工具，桥接到 execute_browser_action）───
    # 通过 WebSocket 调用前端 Electron Main 的 LuomiAutomationExecutor 执行真实操作
    # 命名规范：browser.{action}（如 browser.navigate），与 BROWSER_AUTOMATION_TOOL_NAMES 一致
    for _tool_name, _spec in BROWSER_ACTION_SPECS.items():
        _action = _spec["action"]
        _internal_name = f"browser.{_action}"
        await internal_tool_registry.register(
            name=_internal_name,
            module="browser",
            description=_spec["description"],
            handler=_make_browser_bridge_handler(_tool_name, _action, _spec.get("timeout", 30.0)),
            parameters_schema=_spec["parameters"],
            is_concurrent_safe=True,
            timeout_seconds=int(_spec.get("timeout", 30.0)) + 5,
        )

    # ─── 浏览器语义工具（高层封装，STANDARD 模式可用）───
    await internal_tool_registry.register(
        name="browser.search",
        module="browser",
        description="在浏览器中执行搜索（构建搜索 URL 并导航）",
        handler=_browser_search,
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "engine": {
                    "type": "string",
                    "enum": ["google", "bing", "baidu"],
                    "description": "搜索引擎（默认 google）",
                },
            },
            "required": ["query"],
        },
        is_concurrent_safe=True,
    )

    # 计划任务模块
    await internal_tool_registry.register(
        name="schedule.create",
        module="schedule",
        description="创建定时任务（支持 cron 表达式、间隔、一次性）",
        handler=_schedule_create,
        parameters_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "任务名称"},
                "schedule": {
                    "type": "string",
                    "description": "调度表达式: cron '0 9 * * *', interval 'every 60s', 或 ISO datetime",
                },
                "action": {"type": "string", "description": "要执行的任务指令"},
                "description": {"type": "string", "description": "任务描述（可选）"},
                "context": {"type": "string", "description": "附加上下文（可选）"},
            },
            "required": ["name", "schedule", "action"],
        },
        is_concurrent_safe=False,
    )

    # 记忆中枢模块
    await internal_tool_registry.register(
        name="memory.search",
        module="memory",
        description="语义检索记忆中枢（基于向量检索召回相关事实）",
        handler=_memory_search,
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索查询"},
                "top_k": {"type": "integer", "description": "返回结果数量（默认 5）"},
            },
            "required": ["query"],
        },
        is_concurrent_safe=True,
    )

    await internal_tool_registry.register(
        name="memory.build_context",
        module="memory",
        description="构建记忆上下文（按优先级注入档案/事实/知识/每日记录，用于增强 LLM 提示）",
        handler=_memory_build_context,
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "查询字符串（用于召回相关事实）"},
                "conversation_id": {"type": "string", "description": "对话 ID（可选，用于读取对话级记忆）"},
                "max_chars": {"type": "integer", "description": "最大字符数（默认 4000）"},
            },
        },
        is_concurrent_safe=True,
    )

    # 控制台模块
    await internal_tool_registry.register(
        name="console.execute",
        module="console",
        description="在控制台沙盒中执行命令（白名单 + 超时保护）",
        handler=_console_execute,
        parameters_schema={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的命令（Windows: PowerShell, Linux: Bash）"},
                "working_dir": {"type": "string", "description": "工作目录（可选）"},
                "timeout": {"type": "integer", "description": "超时秒数（默认 30，最大 120）"},
            },
            "required": ["command"],
        },
        is_concurrent_safe=False,
        timeout_seconds=120,
    )

    # 子 Agent 委派模块
    await internal_tool_registry.register(
        name="subagent.delegate",
        module="subagent",
        description="将任务委派给子 Agent 独立执行",
        handler=_subagent_delegate,
        parameters_schema={
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "委派给子 Agent 的任务"},
                "context": {"type": "string", "description": "附加上下文（可选）"},
            },
            "required": ["task"],
        },
        is_concurrent_safe=False,
        timeout_seconds=300,
    )

    # 智能家居控制模块
    await internal_tool_registry.register(
        name="smart_home.control",
        module="smart_home",
        description="控制智能家居设备（开关、调节亮度/温度等）",
        handler=_smart_home_control,
        parameters_schema={
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "设备 ID"},
                "action": {
                    "type": "string",
                    "description": "操作: turn_on, turn_off, toggle, set_brightness, set_temperature, query_status",
                },
                "params": {"type": "object", "description": "操作参数（如亮度值、温度值等）"},
            },
            "required": ["device_id", "action"],
        },
        is_concurrent_safe=False,
        timeout_seconds=30,
    )

    # ─── 计划视图模块（补充 CRUD）───
    await internal_tool_registry.register(
        name="schedule.list",
        module="schedule",
        description="列出所有定时任务",
        handler=_schedule_list,
        parameters_schema={
            "type": "object",
            "properties": {},
        },
        is_concurrent_safe=True,
    )

    await internal_tool_registry.register(
        name="schedule.get",
        module="schedule",
        description="获取单个定时任务详情",
        handler=_schedule_get,
        parameters_schema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "任务 ID"},
            },
            "required": ["task_id"],
        },
        is_concurrent_safe=True,
    )

    await internal_tool_registry.register(
        name="schedule.delete",
        module="schedule",
        description="删除定时任务",
        handler=_schedule_delete,
        parameters_schema={
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "要删除的任务 ID"},
            },
            "required": ["task_id"],
        },
        is_concurrent_safe=False,
    )

    # ─── 记忆中枢模块（补充 facts CRUD + 摘要/知识/画像/蒸馏）───
    await internal_tool_registry.register(
        name="memory.list_facts",
        module="memory",
        description="列出记忆中枢的事实（支持按分类过滤）",
        handler=_memory_list_facts,
        parameters_schema={
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "事实分类（可选）: context, preference, event, relationship, fact, schedule",
                },
                "limit": {"type": "integer", "description": "返回数量上限（默认 100，最大 500）"},
            },
        },
        is_concurrent_safe=True,
    )

    await internal_tool_registry.register(
        name="memory.create_fact",
        module="memory",
        description="在记忆中枢创建新事实",
        handler=_memory_create_fact,
        parameters_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "事实内容"},
                "category": {
                    "type": "string",
                    "description": "分类: context, preference, event, relationship, fact, schedule",
                },
                "confidence": {"type": "number", "description": "置信度 0.0-1.0（默认 0.8）"},
            },
            "required": ["content"],
        },
        is_concurrent_safe=False,
    )

    await internal_tool_registry.register(
        name="memory.update_fact",
        module="memory",
        description="更新记忆中枢的指定事实",
        handler=_memory_update_fact,
        parameters_schema={
            "type": "object",
            "properties": {
                "fact_id": {"type": "string", "description": "事实 ID"},
                "content": {"type": "string", "description": "新内容（可选）"},
                "category": {"type": "string", "description": "新分类（可选）"},
                "confidence": {"type": "number", "description": "新置信度（可选）"},
            },
            "required": ["fact_id"],
        },
        is_concurrent_safe=False,
    )

    await internal_tool_registry.register(
        name="memory.delete_fact",
        module="memory",
        description="删除记忆中枢的指定事实",
        handler=_memory_delete_fact,
        parameters_schema={
            "type": "object",
            "properties": {
                "fact_id": {"type": "string", "description": "要删除的事实 ID"},
            },
            "required": ["fact_id"],
        },
        is_concurrent_safe=False,
    )

    await internal_tool_registry.register(
        name="memory.get_summary",
        module="memory",
        description="获取记忆中枢的 AI 摘要内容",
        handler=_memory_get_summary,
        parameters_schema={"type": "object", "properties": {}},
        is_concurrent_safe=True,
    )

    await internal_tool_registry.register(
        name="memory.update_summary",
        module="memory",
        description="更新记忆中枢的 AI 摘要内容",
        handler=_memory_update_summary,
        parameters_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "新的摘要内容"},
            },
            "required": ["content"],
        },
        is_concurrent_safe=False,
    )

    await internal_tool_registry.register(
        name="memory.get_knowledge",
        module="memory",
        description="获取记忆中枢的知识库内容",
        handler=_memory_get_knowledge,
        parameters_schema={"type": "object", "properties": {}},
        is_concurrent_safe=True,
    )

    await internal_tool_registry.register(
        name="memory.get_profile",
        module="memory",
        description="获取用户画像信息",
        handler=_memory_get_profile,
        parameters_schema={"type": "object", "properties": {}},
        is_concurrent_safe=True,
    )

    await internal_tool_registry.register(
        name="memory.distill",
        module="memory",
        description="将对话蒸馏为记忆（提取关键信息存储到记忆中枢）",
        handler=_memory_distill,
        parameters_schema={
            "type": "object",
            "properties": {
                "messages": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "要蒸馏的对话消息列表",
                },
            },
            "required": ["messages"],
        },
        is_concurrent_safe=False,
        timeout_seconds=120,
    )

    await internal_tool_registry.register(
        name="memory.update_knowledge",
        module="memory",
        description="更新记忆中枢的知识库内容（可复用的知识点）",
        handler=_memory_update_knowledge,
        parameters_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "新的知识库内容（Markdown 格式）"},
            },
            "required": ["content"],
        },
        is_concurrent_safe=False,
    )

    await internal_tool_registry.register(
        name="memory.update_profile",
        module="memory",
        description="更新用户画像（姓名、长期事实、近期上下文）",
        handler=_memory_update_profile,
        parameters_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "新的画像内容（Markdown 格式，首行格式: # 姓名）"},
            },
            "required": ["content"],
        },
        is_concurrent_safe=False,
    )

    await internal_tool_registry.register(
        name="memory.append_daily",
        module="memory",
        description="追加每日记录（记录当天发生的事件）",
        handler=_memory_append_daily,
        parameters_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "要追加的内容"},
                "date": {"type": "string", "description": "日期（YYYY-MM-DD，默认今天）"},
                "conversation_id": {"type": "string", "description": "对话 ID（可选，写入对话级记录）"},
            },
            "required": ["content"],
        },
        is_concurrent_safe=False,
    )

    await internal_tool_registry.register(
        name="memory.get_daily",
        module="memory",
        description="获取每日记录内容",
        handler=_memory_get_daily,
        parameters_schema={
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "日期（YYYY-MM-DD，默认今天）"},
                "conversation_id": {"type": "string", "description": "对话 ID（可选，读取对话级记录）"},
            },
        },
        is_concurrent_safe=True,
    )

    await internal_tool_registry.register(
        name="memory.list_dailies",
        module="memory",
        description="列出有每日记录的日期列表",
        handler=_memory_list_dailies,
        parameters_schema={
            "type": "object",
            "properties": {
                "conversation_id": {"type": "string", "description": "对话 ID（可选，列出对话级记录）"},
            },
        },
        is_concurrent_safe=True,
    )

    await internal_tool_registry.register(
        name="memory.vector_rebuild",
        module="memory",
        description="重建记忆向量索引（用于修复语义检索异常）",
        handler=_memory_vector_rebuild,
        parameters_schema={
            "type": "object",
            "properties": {
                "conversation_id": {"type": "string", "description": "对话 ID（可选，仅重建该对话的索引）"},
            },
        },
        is_concurrent_safe=False,
        timeout_seconds=120,
    )

    await internal_tool_registry.register(
        name="memory.promote_conversation_facts",
        module="memory",
        description="将对话级事实提升为 Agent 级（长期可见）",
        handler=_memory_promote_conversation_facts,
        parameters_schema={
            "type": "object",
            "properties": {
                "conversation_id": {"type": "string", "description": "源对话 ID"},
                "fact_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要提升的事实 ID 列表（可选，默认提升全部）",
                },
            },
            "required": ["conversation_id"],
        },
        is_concurrent_safe=False,
    )

    await internal_tool_registry.register(
        name="memory.clear_facts",
        module="memory",
        description="清空所有记忆事实（谨慎操作）",
        handler=_memory_clear_facts,
        parameters_schema={"type": "object", "properties": {}},
        is_concurrent_safe=False,
    )

    # ─── 扩展市场模块 ───
    await internal_tool_registry.register(
        name="market.install",
        module="market",
        description="安装扩展市场内容（插件/技能/Agent）",
        handler=_market_install,
        parameters_schema={
            "type": "object",
            "properties": {
                "item_id": {"type": "string", "description": "市场条目 ID"},
                "item_type": {"type": "string", "description": "类型: plugin, skill, agent"},
                "item_name": {"type": "string", "description": "条目名称"},
                "download_url": {"type": "string", "description": "下载 URL"},
                "version": {"type": "string", "description": "版本号（默认 1.0.0）"},
            },
            "required": ["item_id", "item_type", "item_name"],
        },
        is_concurrent_safe=False,
        timeout_seconds=300,
    )

    await internal_tool_registry.register(
        name="market.uninstall",
        module="market",
        description="卸载已安装的扩展市场内容",
        handler=_market_uninstall,
        parameters_schema={
            "type": "object",
            "properties": {
                "item_id": {"type": "string", "description": "要卸载的条目 ID"},
            },
            "required": ["item_id"],
        },
        is_concurrent_safe=False,
    )

    await internal_tool_registry.register(
        name="market.list_installed",
        module="market",
        description="列出所有已安装的扩展市场内容",
        handler=_market_list_installed,
        parameters_schema={
            "type": "object",
            "properties": {
                "item_type": {"type": "string", "description": "按类型过滤: plugin, skill, agent"},
            },
        },
        is_concurrent_safe=True,
    )

    await internal_tool_registry.register(
        name="market.get_leaderboard",
        module="market",
        description="获取扩展市场排行榜（按下载量/喜欢数/综合排序）",
        handler=_market_get_leaderboard,
        parameters_schema={
            "type": "object",
            "properties": {
                "item_type": {"type": "string", "description": "按类型过滤: plugin, skill, agent"},
                "sort_by": {
                    "type": "string",
                    "enum": ["composite", "downloads", "likes"],
                    "description": "排序方式（默认 composite）",
                },
                "limit": {"type": "integer", "description": "返回数量（默认 20，最大 100）"},
            },
        },
        is_concurrent_safe=True,
    )

    # ─── 平台接入/设备与群组模块 ───
    await internal_tool_registry.register(
        name="platform.list_instances",
        module="platform",
        description="列出所有已配置的平台实例（QQ/微信/Discord/Telegram 等）",
        handler=_platform_list_instances,
        parameters_schema={"type": "object", "properties": {}},
        is_concurrent_safe=True,
    )

    await internal_tool_registry.register(
        name="platform.start_instance",
        module="platform",
        description="启动指定的平台实例",
        handler=_platform_start_instance,
        parameters_schema={
            "type": "object",
            "properties": {
                "instance_id": {"type": "string", "description": "平台实例 ID"},
            },
            "required": ["instance_id"],
        },
        is_concurrent_safe=False,
        timeout_seconds=60,
    )

    await internal_tool_registry.register(
        name="platform.stop_instance",
        module="platform",
        description="停止指定的平台实例",
        handler=_platform_stop_instance,
        parameters_schema={
            "type": "object",
            "properties": {
                "instance_id": {"type": "string", "description": "平台实例 ID"},
            },
            "required": ["instance_id"],
        },
        is_concurrent_safe=False,
        timeout_seconds=30,
    )

    await internal_tool_registry.register(
        name="platform.send_message",
        module="platform",
        description="通过指定的平台实例发送消息",
        handler=_platform_send_message,
        parameters_schema={
            "type": "object",
            "properties": {
                "instance_id": {"type": "string", "description": "平台实例 ID"},
                "message": {"type": "string", "description": "要发送的消息内容"},
                "target": {"type": "string", "description": "目标会话/用户 ID（可选）"},
            },
            "required": ["instance_id", "message"],
        },
        is_concurrent_safe=False,
        timeout_seconds=30,
    )

    # ─── 智能家居模块（补充查询）───
    await internal_tool_registry.register(
        name="smart_home.list_devices",
        module="smart_home",
        description="列出所有已连接的智能家居设备",
        handler=_smart_home_list_devices,
        parameters_schema={"type": "object", "properties": {}},
        is_concurrent_safe=True,
    )

    await internal_tool_registry.register(
        name="smart_home.list_scenes",
        module="smart_home",
        description="列出所有智能家居场景",
        handler=_smart_home_list_scenes,
        parameters_schema={"type": "object", "properties": {}},
        is_concurrent_safe=True,
    )

    # ─── 技能模块（洋葱架构 §11.2/§11.3：各场景通用，standard/ultra 工具集自动包含）───
    from app.core.tools.builtin.skills_tools import get_luominest_skills_tools
    for _skill_tool in get_luominest_skills_tools():
        await internal_tool_registry.register(
            name=_skill_tool.name,
            module="skills",
            description=_skill_tool.description,
            handler=_make_skill_tool_handler(_skill_tool.name),
            parameters_schema=_skill_tool.parameters,
            is_concurrent_safe=True,
        )

    # ─── 文件搜索模块（search.everything，桥接 SearchEverythingTool 适配器）───
    await internal_tool_registry.register(
        name="search.everything",
        module="search",
        description="秒级搜索本地文件（按文件名，支持子串和 glob 模式）",
        handler=_make_skill_tool_handler("search_everything"),
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "文件名搜索关键词或 glob 模式"},
                "path": {"type": "string", "description": "搜索根路径（可选，默认全盘）"},
                "max_results": {"type": "integer", "description": "最大返回条数（默认 50）"},
            },
            "required": ["query"],
        },
        is_concurrent_safe=True,
    )

    logger.info(
        f"[Workflow] Registered {len(internal_tool_registry.list_names())} internal tools: "
        f"{', '.join(internal_tool_registry.list_names())}"
    )
