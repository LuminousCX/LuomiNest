"""命令执行类工具的三档用户确认中间件（陪伴式安全）。

洋葱位置：LoopGuard 内、SSEEmit 外——permission_request 事件需在
tool_event "started" 之前到达前端，让用户在看到"开始执行"前先做决定。

作用范围：GATED_TOOLS（当前为 cli）。工作流 internal_tool_registry 的
console.execute 走工作流自身的计划确认体系，不经此中间件。

三档许可见 security/sandbox/permission.py 模块文档：
- 弹窗路径：ctx.sse_emitter 发 permission_request chunk → 前端弹窗 →
  POST /chat/tool-permission/{request_id} 回调 → asyncio.Event 恢复。
- 非流式路径无法推送确认事件：fail-closed 直接拒绝（桌面端始终流式，不影响主场景）。
- 子 Agent 不弹窗：有会话授权/完全访问则放行，否则拒绝并提示到主对话授权。
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

# 需要用户确认的命令执行类工具
GATED_TOOLS = frozenset({"cli"})

# 默认确认超时（秒）：超时按拒绝处理，防止 agent 永久挂起
DEFAULT_CONFIRM_TIMEOUT = 120.0


class PermissionGateMiddleware(AgentMiddleware):
    """工具执行前的三档用户确认闸门。"""

    async def wrap_tool_call(
        self,
        ctx: AgentContext,
        tool_call: dict[str, Any],
        next_fn: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        tool_name = tool_call.get("function", {}).get("name", "")
        if tool_name not in GATED_TOOLS:
            return await next_fn(tool_call)

        command = self._extract_command(tool_call)
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
                    "子 Agent 执行命令需要用户授权：请让用户在主对话中授权"
                    "（选择「允许该对话」或「完全访问」）后再委派。",
                )
            return await next_fn(tool_call)

        # 非流式路径无法把确认请求送达前端：fail-closed
        if not ctx.extra.get("is_stream", True) or not ctx.sse_emitter:
            return self._denied(
                tool_call,
                "当前模式无法发起命令执行确认（非流式），已拒绝执行。"
                "请在流式对话中重试，或在设置中开启完全访问。",
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
            return self._denied(tool_call, "确认请求发送失败，已拒绝执行本次命令。")

        decision = await agent_command_permissions.request_approval(
            conversation_id, tool_name, command,
            timeout=DEFAULT_CONFIRM_TIMEOUT,
            request_id=request_id,  # 与 SSE 载荷同 id：前端回调才能命中 _pending
        )
        logger.info(
            f"[PermissionGate] 命令确认完成: conv={conversation_id} decision={decision} "
            f"command={command[:80]}"
        )
        if decision == DECISION_DENY:
            return self._denied(tool_call, "用户拒绝了本次命令执行（或未在限时内响应）。")
        return await next_fn(tool_call)

    # ── 内部工具 ──────────────────────────────────────────────────────

    @staticmethod
    def _extract_command(tool_call: dict[str, Any]) -> str:
        raw = tool_call.get("function", {}).get("arguments", "{}")
        try:
            args = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except (json.JSONDecodeError, TypeError):
            args = {}
        command = args.get("command", "")
        return command if isinstance(command, str) else str(command)

    @staticmethod
    def _denied(tool_call: dict[str, Any], reason: str) -> dict[str, Any]:
        return {
            "role": "tool",
            "tool_call_id": tool_call.get("id", ""),
            "name": tool_call.get("function", {}).get("name", ""),
            "content": f"[命令执行已取消] {reason}",
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
