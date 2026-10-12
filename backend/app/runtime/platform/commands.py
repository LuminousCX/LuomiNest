"""平台命令体系（2026-10-12 拍板：命令制会话管理）。

设计要点（参照 AstrBot 的管道拦截思想，洁净室自研实现）：
- 命令是消息管道中 LLM 之前的短路层：文本以 "/" 起始且首 token 为合法命令名
  （ASCII 字母开头，仅字母/数字/下划线）时做命令解析，命中即由命令处理器
  直接回复，不再进入 LLM；未命中已知命令时回复引导文案（同样不进 LLM，
  防止模型幻觉执行不存在的命令）。
- 首 token 不符合命令名形态（如 "/usr/local"、"/帮助"）不视为命令，
  照常进 LLM，避免误伤普通消息与路径文本。
- 会话策略（拍板）：私聊每人一会、群聊一群一会；唯一的开新会话入口是 /new
  命令；平台页会话列表只是推送落地记录的展示，不是聊天入口。
- 权限：个人部署场景，内置命令对私聊与群聊成员平等开放，不做权限分层；
  群聊 /memory 只展示全局画像（scope=global），防私聊专属记忆泄露到群里。
"""
import re
from dataclasses import dataclass
from typing import Awaitable, Callable

from loguru import logger

from app.runtime.platform.base import PlatformMessage, PlatformResponse
from app.runtime.platform.platform_logger import platform_logger

# 命令名形态：/ + ASCII 字母开头的字母数字下划线串（"/usr/local"、"/帮助" 均不算命令）
_COMMAND_NAME_PATTERN = re.compile(r"^/[A-Za-z][A-Za-z0-9_]*$")

# /memory 展示上限（平台消息不宜长刷屏，置顶事实优先）
_MEMORY_MAX_FACTS = 10
_MEMORY_FACT_CONTENT_LIMIT = 60


@dataclass
class CommandContext:
    """命令处理上下文：路由器在消息管道中组装，命令处理器只读。"""

    message: PlatformMessage
    instance_id: str
    # 平台会话标识（message.session_id or message.user_id），/new 以此为键重建映射
    session_id: str
    agent_name: str


Handler = Callable[[CommandContext], Awaitable[PlatformResponse]]


def _reply(ctx: CommandContext, content: str) -> PlatformResponse:
    return PlatformResponse(
        content=f"[{ctx.agent_name}] {content}",
        message_type="text",
        reply_to=ctx.message.message_id,
    )


def parse_command(text: str) -> tuple[str, str] | None:
    """解析平台消息文本为命令。

    返回 (命令名小写, 参数串)；非命令文本返回 None。命令名统一小写
    （/New 与 /new 等价），参数为首个空白后的剩余文本（保留原样大小写）。
    """
    stripped = (text or "").strip()
    if not stripped.startswith("/"):
        return None
    parts = stripped.split(None, 1)
    if not _COMMAND_NAME_PATTERN.match(parts[0]):
        return None
    args = parts[1].strip() if len(parts) > 1 else ""
    return parts[0][1:].lower(), args


# ─── 内置命令 ───────────────────────────────────────────────


async def _cmd_help(ctx: CommandContext) -> PlatformResponse:
    lines = ["可用命令："]
    for cmd in iter_commands():
        lines.append(f"/{cmd['name']} - {cmd['description']}")
    return _reply(ctx, "\n".join(lines))


async def _cmd_new(ctx: CommandContext) -> PlatformResponse:
    from app.runtime.platform.session import create_new_conversation

    try:
        # 显式传入消息侧元数据：映射缺失时不再回退 "unknown"，标题保持可读
        await create_new_conversation(
            ctx.instance_id,
            ctx.session_id,
            platform_name=ctx.message.platform,
            sender_name=ctx.message.sender_name or ctx.message.user_id,
            is_group=ctx.message.is_group,
        )
    except Exception as e:
        # 服务端日志保留完整异常；对平台用户只返回固定提示，不暴露内部错误
        logger.error(f"[PlatformCommands] /new failed: {e}", exc_info=True)
        return _reply(ctx, "新建对话失败，请稍后重试")

    platform_logger.log(
        ctx.instance_id, "success", "new_conversation_created",
        f"已为会话 {ctx.session_id} 创建新对话（/{'new'} 命令）",
        details={
            "session": f"{ctx.instance_id}:{ctx.session_id}",
            "command": "new",
            "sender": ctx.message.sender_name or ctx.message.user_id,
        },
    )
    return _reply(ctx, "已为您开启新对话，之前的上下文已保留在历史记录中。")


async def _cmd_memory(ctx: CommandContext) -> PlatformResponse:
    from app.core.domain_policy import TRACK_USERS, platform_user_key
    from app.engines.memory import get_track_engine

    uid = (ctx.message.user_id or "").strip()
    if not uid:
        return _reply(ctx, "无法识别你的用户标识，暂时无法查询记忆")

    engine = get_track_engine(TRACK_USERS, platform_user_key(ctx.message.platform, uid))
    facts = engine.fact_manager.get_facts()

    is_group = ctx.message.is_group
    if is_group:
        # 群聊只展示全局画像：私聊专属秘密（scope=private）与单群记忆不进群
        facts = [f for f in facts if f.scope == "global"]

    if not facts:
        hint = "（群聊仅展示公开记忆）" if is_group else ""
        return _reply(ctx, f"我还没有记住关于你的信息，多聊聊我就会记住啦{hint}")

    # 置顶优先，其余按创建时间倒序，展示最近 N 条
    facts_sorted = sorted(facts, key=lambda f: (not f.pinned, f.created_at), reverse=True)
    shown = facts_sorted[:_MEMORY_MAX_FACTS]

    who = ctx.message.sender_name or uid
    scope_note = "（群聊仅展示公开记忆）" if is_group else ""
    lines = [f"关于 {who}，我记住了 {len(facts)} 条{scope_note}："]
    for i, f in enumerate(shown, 1):
        content = f.content if len(f.content) <= _MEMORY_FACT_CONTENT_LIMIT else f.content[:_MEMORY_FACT_CONTENT_LIMIT] + "…"
        pin_mark = "📌 " if f.pinned else ""
        lines.append(f"{i}. {pin_mark}[{f.category}] {content}")
    if len(facts_sorted) > len(shown):
        lines.append(f"…还有 {len(facts_sorted) - len(shown)} 条未展示")
    return _reply(ctx, "\n".join(lines))


@dataclass(frozen=True)
class PlatformCommand:
    name: str
    description: str
    handler: Handler


_COMMANDS: dict[str, PlatformCommand] = {
    cmd.name: cmd
    for cmd in (
        PlatformCommand("help", "查看可用命令", _cmd_help),
        PlatformCommand("new", "开启新对话（清空当前上下文重新开始）", _cmd_new),
        PlatformCommand("memory", "查看我记住了关于你的哪些信息", _cmd_memory),
    )
}


def iter_commands() -> list[dict]:
    """内置命令清单（/help 展示与测试用）。"""
    return [
        {"name": c.name, "description": c.description}
        for c in _COMMANDS.values()
    ]


def is_command_text(text: str) -> bool:
    """消息是否为命令形态（合法命令名，未知命令也算）。"""
    return parse_command(text) is not None


async def dispatch_platform_command(ctx: CommandContext) -> PlatformResponse | None:
    """命令分发入口：消息管道中 LLM 之前的短路层。

    返回 PlatformResponse 表示消息已被命令处理（调用方直接回包，不进 LLM）；
    返回 None 表示非命令文本，调用方继续正常路由。
    """
    parsed = parse_command(ctx.message.content)
    if parsed is None:
        return None
    name, _args = parsed
    command = _COMMANDS.get(name)
    if command is None:
        platform_logger.log(
            ctx.instance_id, "info", "command_unknown",
            f"未知命令 /{name}",
            details={
                "session": f"{ctx.instance_id}:{ctx.session_id}",
                "command": name,
                "sender": ctx.message.sender_name or ctx.message.user_id,
            },
        )
        return _reply(ctx, f"未知命令 /{name}，发送 /help 查看可用命令")

    platform_logger.log(
        ctx.instance_id, "info", "command_received",
        f"命令 /{name} 来自 {ctx.message.sender_name or ctx.message.user_id}",
        details={
            "session": f"{ctx.instance_id}:{ctx.session_id}",
            "command": name,
            "sender": ctx.message.sender_name or ctx.message.user_id,
        },
    )
    try:
        return await command.handler(ctx)
    except Exception as e:
        logger.error(f"[PlatformCommands] /{name} handler failed: {e}", exc_info=True)
        return _reply(ctx, "命令执行失败，请稍后重试")
