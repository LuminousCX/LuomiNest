"""Agent 工具执行的三档用户确认中间件（辰汐生态打通 W3：权限三级 T0/T1/T2）。

洋葱位置：LoopGuard 内、SSEEmit 外——permission_request 事件需在
tool_event "started" 之前到达前端，让用户在看到"开始执行"前先做决定。

三级判级（T0 自动档 / T1 确认档 / T2 信任档）：
- T0 自动档：只读/陪伴类工具免确认直接执行（read_file、get_current_time、
  memory_search、tool_explore 等一切未命中 T1 清单的内置工具）；
- T1 确认档：写文件、命令行、删除类、定时任务增删、IoT 命令、应用启动、
  平台外呼等高危工具（T1_BUILTIN_TOOLS 显式清单 + 插件 manifest 归级），
  保留既有弹窗确认交互（SSE permission_request → POST /chat/tool-permission/
  {request_id} 回调 → asyncio.Event 恢复）；
- T2 信任档：config_items['permission.trusted_mode']（运行时镜像
  settings.PERMISSION_TRUSTED_MODE）开启后所有工具免确认（总开关，默认关）。

插件（CxPlugin）工具纳管（G18 补课）：按注册插件的 manifest.permissions 归级——
含写/网络/执行类权限（T1_PLUGIN_PERMISSIONS）→ T1；纯只读（basic/event_listen/
file_read/tool_register）→ T0。

工作流 internal_tool_registry 的 console.execute 走工作流自身的计划确认体系，
不经此中间件。命令黑名单硬防线在 CommandValidator，任何档位（含 T2）都照常生效。
"""
import json
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from loguru import logger

from app.core.agents.middleware.base import AgentContext, AgentMiddleware
from app.core.utils import sse_data
from app.security.sandbox.permission import (
    DECISION_DENY,
    agent_command_permissions,
)

# ── 权限三级常量 ──────────────────────────────────────────────────
PERMISSION_TIER_T0 = "t0"  # 自动档：免确认直接执行
PERMISSION_TIER_T1 = "t1"  # 确认档：弹窗确认后执行
# T2 信任档不是工具属性而是全局开关（trusted_mode），见 is_trusted_mode()

# T1 内置高危工具显式清单（判级口径见仓库交付报告；只读/陪伴类一律 T0）
T1_BUILTIN_TOOLS = frozenset({
    "cli",                    # 命令行执行（原 GATED_TOOLS，保留弹窗）
    "write_file",             # 写文件
    "create_scheduled_task",  # 定时任务增
    "delete_scheduled_task",  # 定时任务删（删除类）
    "iot_send_command",       # IoT 命令
    "launch_application",     # 应用启动
    "platform_invoke",        # 跨平台外呼（发消息/禁言/群公告等平台操作）
    "memory_forget",          # 删除用户记忆（删除类）
})

# T1 归级所需的插件 manifest 权限（写/网络/执行/库/管理类，CxPermission 值）
T1_PLUGIN_PERMISSIONS = frozenset({
    "network",         # 网络访问（外呼）
    "file_write",      # 文件写入
    "file_system",     # 完整文件系统访问
    "system_command",  # 执行系统命令
    "database",        # 数据库访问（含写）
    "admin_api",       # 管理级 API
})

# 兼容别名：历史语义 = 需要确认的工具集合，现为 T1 内置清单
GATED_TOOLS = T1_BUILTIN_TOOLS

# 默认确认超时（秒）：超时按拒绝处理，防止 agent 永久挂起
DEFAULT_CONFIRM_TIMEOUT = 120.0

# trusted_mode 持久化键（config_items，跟随 sandbox.agent_command_mode 惯例）
TRUSTED_MODE_CONFIG_KEY = "permission.trusted_mode"


# ── T2 信任档：config_items 持久化 + settings 运行时镜像 ─────────────


def is_trusted_mode() -> bool:
    """T2 信任档是否开启（settings 运行时镜像，读失败按关闭处理）。"""
    try:
        from app.core.config import settings

        return bool(getattr(settings, "PERMISSION_TRUSTED_MODE", False))
    except Exception:
        return False


async def load_trusted_mode_from_db() -> None:
    """启动时从 config_items 恢复 trusted_mode 到 settings 运行时镜像（lifespan 调用）。"""
    from app.core.config import settings

    try:
        from app.infrastructure.database.config_store import luominest_config_store

        val = await luominest_config_store.get_async(TRUSTED_MODE_CONFIG_KEY, False)
        settings.PERMISSION_TRUSTED_MODE = bool(val)
    except Exception as e:
        logger.warning(f"[PermissionGate] 恢复 trusted_mode 失败，按关闭处理: {e}")
        settings.PERMISSION_TRUSTED_MODE = False


async def set_trusted_mode(enabled: bool) -> None:
    """设置 trusted_mode（内存镜像先行生效，持久化异步跟进）。"""
    from app.core.config import settings

    settings.PERMISSION_TRUSTED_MODE = bool(enabled)
    try:
        from app.infrastructure.database.config_store import luominest_config_store

        await luominest_config_store.set_async(TRUSTED_MODE_CONFIG_KEY, bool(enabled))
        logger.info(f"[PermissionGate] trusted_mode 已切换并持久化: {bool(enabled)}")
    except Exception as e:
        # 持久化失败不回滚内存态（重启后回落默认 false，fail-safe）
        logger.warning(f"[PermissionGate] trusted_mode 持久化失败（内存态已生效）: {e}")


# ── 判级：内置显式清单 + 插件 manifest 归级 ──────────────────────────


def resolve_tool_permission_tier(tool_name: str) -> str:
    """返回工具的权限档位（PERMISSION_TIER_T0 / PERMISSION_TIER_T1）。

    - T1 内置显式清单命中 → T1；
    - 插件注册工具按其 manifest.permissions 归级（含写/网络/执行类 → T1）；
    - 其余（含 MCP 网关工具、未知工具）→ T0（维持既有免确认行为）。
    """
    if tool_name in T1_BUILTIN_TOOLS:
        return PERMISSION_TIER_T1
    if _plugin_tool_is_t1(tool_name):
        return PERMISSION_TIER_T1
    return PERMISSION_TIER_T0


def _plugin_tool_is_t1(tool_name: str) -> bool:
    """查注册该工具的活跃插件并按 manifest.permissions 归级；查不到按 T0。"""
    try:
        from app.runtime.plugin.cxplugin.registry import luominest_plugin_registry

        for meta in luominest_plugin_registry.list_plugins(active_only=True):
            instance = luominest_plugin_registry.get_instance(meta.plugin_id)
            registered = []
            if instance is not None:
                registered = list(getattr(instance, "get_registered_tool_names", lambda: [])())
            if tool_name not in registered:
                continue
            perms = meta.manifest.get_permissions()
            hit = sorted(p.value for p in perms if p.value in T1_PLUGIN_PERMISSIONS)
            if hit:
                logger.debug(
                    f"[PermissionGate] 插件工具 {tool_name} 归级 T1（manifest: {hit}）"
                )
                return True
            return False  # 找到属主且无高危权限 → 纯只读 T0
    except Exception as e:
        logger.debug(f"[PermissionGate] 插件工具归级查询失败（按 T0 处理）: {e}")
    return False


class PermissionGateMiddleware(AgentMiddleware):
    """工具执行前的三档用户确认闸门（T0 放行 / T1 弹窗 / T2 总开关旁路）。"""

    async def wrap_tool_call(
        self,
        ctx: AgentContext,
        tool_call: dict[str, Any],
        next_fn: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        tool_name = tool_call.get("function", {}).get("name", "")

        # T2 信任档总开关：所有工具免确认（黑名单硬防线仍在 CommandValidator）
        if is_trusted_mode():
            return await next_fn(tool_call)

        # T0 自动档：免确认直接执行
        if resolve_tool_permission_tier(tool_name) != PERMISSION_TIER_T1:
            return await next_fn(tool_call)

        command = self._extract_display_args(tool_call)
        conversation_id = ctx.extra.get("conv_id") or ""
        is_sub_agent = bool(ctx.extra.get("is_sub_agent", False))

        # 完全访问 / 本会话已授权 → 直接放行（黑名单硬防线仍在 CommandValidator）
        if not agent_command_permissions.needs_approval(conversation_id):
            return await next_fn(tool_call)

        # 子 Agent 不弹窗：无授权则拒绝并指引到主对话
        if is_sub_agent:
            if not agent_command_permissions.subagent_allowed(conversation_id):
                return self._denied(
                    tool_call,
                    "子 Agent 执行高危工具需要用户授权：请让用户在主对话中授权"
                    "（选择「允许该对话」或「完全访问」）后再委派。",
                )
            return await next_fn(tool_call)

        # 非流式路径无法把确认请求送达前端：fail-closed
        if not ctx.extra.get("is_stream", True) or not ctx.sse_emitter:
            return self._denied(
                tool_call,
                "当前模式无法发起工具执行确认（非流式），已拒绝执行。"
                "请在流式对话中重试，或在设置中开启完全访问/信任模式。",
            )

        request_id = uuid4().hex
        try:
            await ctx.sse_emitter(
                self.format_permission_request_sse(
                    ctx, request_id, tool_name, command, DEFAULT_CONFIRM_TIMEOUT,
                )
            )
        except Exception as emit_err:
            logger.warning(f"[PermissionGate] permission_request 发射失败: {emit_err}")
            return self._denied(tool_call, "确认请求发送失败，已拒绝执行本次操作。")

        decision = await agent_command_permissions.request_approval(
            conversation_id, tool_name, command,
            timeout=DEFAULT_CONFIRM_TIMEOUT,
            request_id=request_id,  # 与 SSE 载荷同 id：前端回调才能命中 _pending
        )
        logger.info(
            f"[PermissionGate] 高危工具确认完成: conv={conversation_id} tool={tool_name} "
            f"decision={decision} args={command[:80]}"
        )
        if decision == DECISION_DENY:
            return self._denied(tool_call, "用户拒绝了本次执行（或未在限时内响应）。")
        return await next_fn(tool_call)

    # ── 内部工具 ──────────────────────────────────────────────────────

    @staticmethod
    def _extract_display_args(tool_call: dict[str, Any]) -> str:
        """提取确认弹窗展示文本：cli 取 command 原文；其余工具取参数摘要。"""
        raw = tool_call.get("function", {}).get("arguments", "{}")
        try:
            args = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except (json.JSONDecodeError, TypeError):
            args = {}
        if isinstance(args, dict):
            command = args.get("command", "")
            if isinstance(command, str) and command:
                return command
            try:
                text = json.dumps(args, ensure_ascii=False)
            except (TypeError, ValueError):
                text = str(args)
        else:
            text = str(args)
        return text[:200]

    @staticmethod
    def _denied(tool_call: dict[str, Any], reason: str) -> dict[str, Any]:
        return {
            "role": "tool",
            "tool_call_id": tool_call.get("id", ""),
            "name": tool_call.get("function", {}).get("name", ""),
            "content": f"[工具执行已取消] {reason}",
        }

    @staticmethod
    def format_permission_request_sse(
        ctx: AgentContext,
        request_id: str,
        tool_name: str,
        command: str,
        timeout: float,
    ) -> str:
        """格式化 permission_request SSE 字符串（前端据此弹确认窗）。"""
        chunk = _permission_request_chunk(
            ctx.state.get("chat_id", ""),
            ctx.state.get("model", ""),
            ctx.state.get("provider", ""),
            {
                "request_id": request_id,
                "tool": tool_name,
                "command": command,
                "timeout": timeout,
            },
            ctx.iteration,
        )
        return sse_data(chunk)


def _permission_request_chunk(
    chat_id: str, model: str, provider: str, request: dict, iteration: int = 0
):
    """构造带 permission_request 字段的流 chunk（延迟导入避免循环依赖）。"""
    from app.schemas.chat import ChatStreamChunk

    return ChatStreamChunk(
        id=chat_id,
        model=model,
        provider=provider,
        permission_request=request,
        iteration=iteration,
    )
