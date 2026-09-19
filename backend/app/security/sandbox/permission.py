"""Agent 命令执行的三档用户确认管理器（陪伴式安全）。

三档许可由用户在确认弹窗中选择（SSE permission_request → REST 回调）：
- once    允许单次：仅放行当前这一条命令
- session 允许该对话：本会话内后续 agent 命令免确认（内存态，应用重启失效）
- full    完全访问：持久化放行后续所有命令（config_items 持久化）
- deny    拒绝：返回拒绝 tool message，agent 会向用户说明

安全边界：
- 本管理器只负责"要不要问用户"；CommandValidator 的黑名单/危险模式/路径
  硬防线在任何档位下都照常生效（完全访问 ≠ 越过安全底线）。
- 子 Agent（后台执行）不弹窗：有会话授权或完全访问则放行，否则拒绝并
  提示到主对话授权，避免后台任务挂起等用户。
- 确认请求超时未响应按 deny 处理，防止 agent 永久挂起。
"""
import asyncio
import time
from dataclasses import dataclass, field
from uuid import uuid4

from loguru import logger

# 用户决定类别
DECISION_ONCE = "once"
DECISION_SESSION = "session"
DECISION_FULL = "full"
DECISION_DENY = "deny"
_VALID_DECISIONS = {DECISION_ONCE, DECISION_SESSION, DECISION_FULL, DECISION_DENY}

# 持久化模式（config_items 键）：ask=每条询问（默认）/ full=完全访问
MODE_KEY = "sandbox.agent_command_mode"
MODE_ASK = "ask"
MODE_FULL = "full"


@dataclass
class _PendingRequest:
    """一次待确认的命令执行请求。"""

    request_id: str
    conversation_id: str
    tool_name: str
    command: str
    event: asyncio.Event = field(default_factory=asyncio.Event)
    decision: str | None = None
    created_at: float = field(default_factory=time.monotonic)


class AgentCommandPermissionManager:
    """管理 agent 命令执行的用户确认请求、会话授权与持久化模式。"""

    def __init__(self) -> None:
        self._pending: dict[str, _PendingRequest] = {}
        self._session_grants: set[str] = set()
        self._mode: str = MODE_ASK
        self._persist_task: asyncio.Task | None = None

    # ── 持久化模式 ────────────────────────────────────────────────

    async def load_persisted_state(self) -> None:
        """启动时从 config_items 恢复持久化模式（应用 lifespan 调用一次）。"""
        try:
            from app.infrastructure.database.config_store import luominest_config_store

            mode = await luominest_config_store.get_async(MODE_KEY, MODE_ASK)
            self._mode = mode if mode in (MODE_ASK, MODE_FULL) else MODE_ASK
        except Exception as e:
            logger.warning(f"[AgentPermission] 恢复持久化模式失败，按 ask 处理: {e}")
            self._mode = MODE_ASK

    def get_mode(self) -> str:
        return self._mode

    async def set_mode(self, mode: str) -> None:
        """设置持久化模式（"full" 完全访问 / "ask" 恢复每条询问）。"""
        if mode not in (MODE_ASK, MODE_FULL):
            raise ValueError(f"未知模式: {mode}")
        from app.infrastructure.database.config_store import luominest_config_store

        await luominest_config_store.set_async(MODE_KEY, mode)
        self._mode = mode
        logger.info(f"[AgentPermission] agent 命令模式已切换: {mode}")

    # ── 授权判定 ──────────────────────────────────────────────────

    def needs_approval(self, conversation_id: str) -> bool:
        """当前命令是否需要弹窗询问用户。"""
        if self._mode == MODE_FULL:
            return False
        return conversation_id not in self._session_grants

    def subagent_allowed(self, conversation_id: str) -> bool:
        """子 Agent（不弹窗）是否可以免确认执行。"""
        return self._mode == MODE_FULL or conversation_id in self._session_grants

    # ── 请求-决定 协议 ────────────────────────────────────────────

    async def request_approval(
        self, conversation_id: str, tool_name: str, command: str, timeout: float = 120.0,
        request_id: str | None = None,
    ) -> str:
        """发出确认请求并等待用户决定，返回决策类别；超时未响应按 deny。

        request_id：由调用方（PermissionGate 中间件）生成并随 SSE 载荷下发，
        保证前端回调携带的 id 与 _pending 键一致（P0 修复：原两处各自生成）。"""
        request_id = request_id or uuid4().hex
        request = _PendingRequest(
            request_id=request_id,
            conversation_id=conversation_id,
            tool_name=tool_name,
            command=command,
        )
        self._pending[request_id] = request
        try:
            try:
                await asyncio.wait_for(request.event.wait(), timeout=timeout)
                decision = request.decision or DECISION_DENY
            except asyncio.TimeoutError:
                logger.info(
                    f"[AgentPermission] 确认请求超时未响应，按拒绝处理: {request_id}"
                )
                decision = DECISION_DENY
        finally:
            self._pending.pop(request_id, None)

        self._apply_decision(conversation_id, decision)
        return decision

    def resolve(self, request_id: str, decision: str) -> bool:
        """前端回调：处理一次用户决定。请求不存在/已处理/决定非法返回 False。"""
        if decision not in _VALID_DECISIONS:
            return False
        request = self._pending.get(request_id)
        if request is None or request.decision is not None:
            return False
        request.decision = decision
        request.event.set()
        return True

    def pending_count(self) -> int:
        return len(self._pending)

    def pending_snapshot(self) -> list[dict]:
        """在途确认请求快照（诊断/恢复用）。"""
        return [
            {
                "request_id": r.request_id,
                "conversation_id": r.conversation_id,
                "tool_name": r.tool_name,
                "command": r.command,
                "age_seconds": round(time.monotonic() - r.created_at, 1),
            }
            for r in self._pending.values()
        ]

    # ── 会话授权 ──────────────────────────────────────────────────

    def _apply_decision(self, conversation_id: str, decision: str) -> None:
        if decision == DECISION_SESSION and conversation_id:
            self._session_grants.add(conversation_id)
            logger.info(f"[AgentPermission] 会话授权: conv={conversation_id}")
        elif decision == DECISION_FULL:
            # 内存态先行生效（消除窗口期），持久化异步跟进（保存引用防 GC，失败告警）
            self._mode = MODE_FULL
            import asyncio as _asyncio

            try:
                running = _asyncio.get_running_loop()

                async def _persist_full_mode():
                    try:
                        await self.set_mode(MODE_FULL)
                    except Exception as e:
                        logger.error(f"[AgentPermission] 完全访问持久化失败（内存态已生效）: {e}")

                self._persist_task = running.create_task(_persist_full_mode())
            except RuntimeError:
                pass  # 无事件循环（单测同步调用）：内存态已生效

    def session_grants_snapshot(self) -> list[str]:
        return sorted(self._session_grants)

    def revoke_session(self, conversation_id: str) -> bool:
        """撤销会话授权（设置页/诊断用）。"""
        if conversation_id in self._session_grants:
            self._session_grants.discard(conversation_id)
            return True
        return False


agent_command_permissions = AgentCommandPermissionManager()
