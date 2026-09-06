"""内部模块接口注册

将 LuomiNest 各内部模块（浏览器、计划、记忆等）的操作注册到
internal_tool_registry，供工作流引擎调度。

每个模块的接口封装现有工具或服务，提供高层操作语义。
执行后通过 WorkflowEventEmitter 推送结构化事件到前端。

大文件拆分说明：各工具处理函数按域拆至 tool_domains/ 子包
（memory_tools / schedule_tools / market_tools / platform_tools /
smart_home_tools / console_tools，共享设施在 tool_domains.common），
本文件保留为注册入口——工具桥接工厂与 register_internal_tools 的
注册顺序、工具名、schema 与拆分前完全一致；
set_emitter / remove_emitter 仍从本模块导入（re-export）。
"""
import json
from typing import Any

from loguru import logger

from app.core.ports.browser_automation import execute_browser_action
from app.core.tools.builtin.browser_automation import BROWSER_ACTION_SPECS, _format_output
from app.core.workflow.internal_registry import internal_tool_registry
from app.core.workflow.models import WorkflowTaskResult
from app.core.workflow.tool_domains.common import (
    _get_emitter,
    _wf_catch,
    remove_emitter,
    set_emitter,
)
from app.core.workflow.tool_domains.console_tools import (
    _console_execute,
    _context_compress,
    _subagent_delegate,
)
from app.core.workflow.tool_domains.market_tools import (
    _market_get_leaderboard,
    _market_install,
    _market_list_installed,
    _market_uninstall,
)
from app.core.workflow.tool_domains.memory_tools import (
    _memory_append_daily,
    _memory_build_context,
    _memory_clear_facts,
    _memory_create_fact,
    _memory_delete_fact,
    _memory_distill,
    _memory_get_daily,
    _memory_get_knowledge,
    _memory_get_profile,
    _memory_get_summary,
    _memory_list_dailies,
    _memory_list_facts,
    _memory_promote_conversation_facts,
    _memory_search,
    _memory_update_fact,
    _memory_update_knowledge,
    _memory_update_profile,
    _memory_update_summary,
    _memory_vector_rebuild,
)
from app.core.workflow.tool_domains.platform_tools import (
    _platform_list_instances,
    _platform_send_message,
    _platform_start_instance,
    _platform_stop_instance,
)
from app.core.workflow.tool_domains.schedule_tools import (
    _schedule_create,
    _schedule_delete,
    _schedule_get,
    _schedule_list,
)
from app.core.workflow.tool_domains.smart_home_tools import (
    _smart_home_control,
    _smart_home_list_devices,
    _smart_home_list_scenes,
)

__all__ = [
    "register_internal_tools",
    "remove_emitter",
    "set_emitter",
]


def _make_skill_tool_handler(tool_name: str):
    """构造技能工具的 internal handler（桥接 tool_registry 中的 ToolBase 工具）。

    洋葱架构 §11.3：皮套工坊/桌宠为 standard 模式，工具来自 internal_tool_registry，
    在此桥接 skills 工具使 standard 模式自动获得技能能力。
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


def _make_workflow_template_handler(action: str):
    """构造工作流模板工具的 internal handler（桥接 WorkflowTemplateService）。

    tool-opt §4.8.6：模板管理工具，tier=domain。
    action 取值: list / save / run，对应 template_service 的三个核心操作。
    """

    @_wf_catch(f"workflow.{action}_template" if action != "list" else "workflow.list_templates")
    async def handler(args: dict[str, Any]) -> WorkflowTaskResult:
        from app.core.workflow.template_service import WorkflowTemplateService

        service = WorkflowTemplateService()

        if action == "list":
            templates = await service.list_templates()
            return WorkflowTaskResult(
                success=True,
                output=json.dumps(templates, ensure_ascii=False),
                metadata={"count": len(templates) if isinstance(templates, list) else 0},
            )

        elif action == "save":
            name = args.get("name", "")
            plan_json = args.get("plan_json", "")
            if not name or not plan_json:
                return WorkflowTaskResult(
                    success=False,
                    error="Missing required parameters: name, plan_json",
                )
            template = await service.save_template(
                name=name,
                description=args.get("description", ""),
                plan_json=plan_json,
                parameters_schema=args.get("parameters_schema", "{}"),
                auto_approve=args.get("auto_approve", False),
                created_from=args.get("created_from", "ai"),
                source_session_id=args.get("source_session_id", ""),
            )
            emitter = _get_emitter()
            if emitter:
                await emitter.emit_module_action(
                    module="workflow",
                    action="template_saved",
                    success=True,
                    output=f"已保存模板: {name}",
                    metadata={"template": template},
                )
            return WorkflowTaskResult(
                success=True,
                output=f"已保存工作流模板: {name}",
                metadata=template if isinstance(template, dict) else {},
            )

        elif action == "run":
            template_id = args.get("template_id", "")
            if not template_id:
                return WorkflowTaskResult(
                    success=False,
                    error="Missing required parameter: template_id",
                )
            result = await service.run_template(
                template_id=template_id,
                params=args.get("params", {}),
                auto_approve=args.get("auto_approve"),
            )
            emitter = _get_emitter()
            if emitter:
                await emitter.emit_module_action(
                    module="workflow",
                    action="template_run",
                    success=True,
                    output=f"已执行模板: {template_id}",
                    metadata={"template_id": template_id, "result": result},
                )
            return WorkflowTaskResult(
                success=True,
                output=f"已实例化执行工作流模板: {template_id}",
                metadata=result if isinstance(result, dict) else {},
            )

        else:
            return WorkflowTaskResult(success=False, error=f"Unknown action: {action}")

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


async def register_internal_tools() -> None:
    """注册所有内部模块接口到 internal_tool_registry

    在应用启动时调用（app_factory.py lifespan）。
    """
    # ─── 工具元信息模块（S1b：长尾工具按需取完整参数定义）───
    async def _tool_read(args: dict[str, Any]) -> WorkflowTaskResult:
        name = args.get("name", "")
        entry = internal_tool_registry.get(name)
        if entry is None:
            return WorkflowTaskResult(
                success=False,
                error=f"Internal tool '{name}' not found. Available modules: {internal_tool_registry.list_modules()}",
            )
        return WorkflowTaskResult(
            success=True,
            output=json.dumps(
                {
                    "name": entry.name,
                    "module": entry.module,
                    "description": entry.description,
                    "parameters": entry.parameters_schema,
                },
                ensure_ascii=False,
            ),
        )

    await internal_tool_registry.register(
        name="tool.read",
        module="meta",
        description="读取某个内部工具的完整参数定义（规划使用 other_tools_name_only 中的工具前先调用）",
        handler=_tool_read,
        parameters_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "内部工具名（如 memory.search）"},
            },
            "required": ["name"],
        },
        is_concurrent_safe=True,
    )

    # ─── 浏览器观察模块（2 个工具，桥接到 execute_browser_action）───
    # 仅保留 screenshot/get_html 两个观察类工具（工具链瘦身）；
    # 交互类能力保留在前端 DevPanel，由用户直接使用
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

    # ─── 技能模块（洋葱架构 §11.2/§11.3：各场景通用，standard 工具集自动包含）───
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

    # ─── 上下文压缩模块（tool-opt §4.3 T4：复用 CompressContextTool）───
    await internal_tool_registry.register(
        name="context.compress",
        module="context",
        description="压缩对话上下文（释放 token 空间，保留关键摘要）",
        handler=_context_compress,
        parameters_schema={
            "type": "object",
            "properties": {
                "conversation_id": {"type": "string", "description": "要压缩的对话 ID"},
                "max_tokens": {"type": "integer", "description": "压缩后目标 token 上限（可选）"},
            },
            "required": ["conversation_id"],
        },
        is_concurrent_safe=False,
        timeout_seconds=120,
    )

    # ─── 应用启动模块（app.launch，桥接 LaunchApplicationTool）───
    await internal_tool_registry.register(
        name="app.launch",
        module="app",
        description="按名称搜索并启动已安装的应用程序",
        handler=_make_skill_tool_handler("launch_application"),
        parameters_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "应用名称或关键词"},
                "action": {"type": "string", "enum": ["search", "launch"], "description": "search=仅搜索，launch=搜索并启动"},
                "app_id": {"type": "string", "description": "直接启动指定 app_id"},
            },
            "required": ["name"],
        },
        is_concurrent_safe=False,
    )

    # ─── 工作流模板模块（tool-opt §4.8.6：模板管理工具，tier=domain）───
    await internal_tool_registry.register(
        name="workflow.list_templates",
        module="workflow",
        description="列出所有已保存的工作流模板",
        handler=_make_workflow_template_handler("list"),
        parameters_schema={
            "type": "object",
            "properties": {},
        },
        is_concurrent_safe=True,
    )

    await internal_tool_registry.register(
        name="workflow.save_template",
        module="workflow",
        description="将工作流计划保存为可复用模板",
        handler=_make_workflow_template_handler("save"),
        parameters_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "模板名称"},
                "description": {"type": "string", "description": "模板描述（可选）"},
                "plan_json": {"type": "string", "description": "工作流计划 JSON 字符串"},
                "parameters_schema": {"type": "string", "description": "参数 JSON Schema 字符串（默认 {}）"},
                "auto_approve": {"type": "boolean", "description": "是否自动审批（默认 false）"},
                "created_from": {"type": "string", "enum": ["user", "ai"], "description": "创建来源（默认 ai）"},
                "source_session_id": {"type": "string", "description": "来源会话 ID（可选）"},
            },
            "required": ["name", "plan_json"],
        },
        is_concurrent_safe=False,
    )

    await internal_tool_registry.register(
        name="workflow.run_template",
        module="workflow",
        description="实例化执行指定的工作流模板",
        handler=_make_workflow_template_handler("run"),
        parameters_schema={
            "type": "object",
            "properties": {
                "template_id": {"type": "string", "description": "模板 ID"},
                "params": {"type": "object", "description": "模板参数（可选）"},
                "auto_approve": {"type": "boolean", "description": "是否自动审批（可选，默认使用模板设置）"},
            },
            "required": ["template_id"],
        },
        is_concurrent_safe=False,
        timeout_seconds=300,
    )

    logger.info(
        f"[Workflow] Registered {len(internal_tool_registry.list_names())} internal tools: "
        f"{', '.join(internal_tool_registry.list_names())}"
    )
