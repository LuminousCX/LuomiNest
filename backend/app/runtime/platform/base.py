from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Awaitable, Callable


class AdapterStatus(StrEnum):
    PENDING = "pending"
    STARTING = "starting"
    RUNNING = "running"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    STOPPING = "stopping"
    STOPPED = "stopped"


MessageHandler = Callable[["PlatformMessage", str], Awaitable["PlatformResponse | None"]]


@dataclass
class PlatformMessage:
    """统一的平台入站消息模型。

    platform: 平台类型名（如 qq_onebot / wechat_work / minecraft）
    user_id: 发送者标识（QQ 号 / 微信 openid / MC 玩家名）
    content: 文本内容
    session_id: 会话标识，用于路由到主 Agent 的独立对话（如 group_id 或 user_id）
    message_id: 平台消息 ID
    group_id: 群组 ID（私聊为空）
    sender_name: 发送者昵称
    is_group: 是否群聊
    image_urls: 图片 URL 列表（用于多模态识别）
    raw: 原始消息对象
    """

    platform: str
    user_id: str
    content: str
    session_id: str = ""
    message_id: str = ""
    group_id: str = ""
    sender_name: str = ""
    is_group: bool = False
    image_urls: list[str] = field(default_factory=list)
    raw: Any = None


@dataclass
class PlatformResponse:
    """统一的平台出站响应模型。

    content: 文本内容
    message_type: 消息类型（text / image / mixed）
    reply_to: 回复的目标消息 ID
    image_urls: 图片 URL 列表
    extra: 平台特有字段
    """

    content: str
    message_type: str = "text"
    reply_to: str = ""
    image_urls: list[str] = field(default_factory=list)
    extra: dict[str, Any] | None = None


class BasePlatformAdapter(ABC):
    """平台适配器抽象基类。

    子类需实现：
    - initialize: 解析配置并初始化资源
    - send_message: 向平台发送响应
    - start: 启动平台监听
    - stop: 停止平台监听

    收到消息时调用 _emit_message 触发路由器回调。
    子类可通过 _log 方法将事件写入平台日志（同时流入控制台日志）。
    """

    platform_name: str = "base"

    def __init__(self) -> None:
        self._config: dict[str, Any] = {}
        self._instance_id: str = ""
        self._message_handler: MessageHandler | None = None
        self._status: AdapterStatus = AdapterStatus.PENDING
        self._started_at: float | None = None
        self._last_error: str | None = None
        self._error_count: int = 0
        self._message_count: int = 0

    def set_instance_id(self, instance_id: str) -> None:
        self._instance_id = instance_id

    def set_message_handler(self, handler: MessageHandler) -> None:
        self._message_handler = handler

    def initialize(self, config: dict[str, Any]) -> None:
        self._config = config

    def _log(
        self,
        level: str,
        event: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """将适配器事件写入平台日志（同时经 loguru 流入控制台日志）。

        level: info / success / warning / error
        event: 事件标识（如 connection_established / message_received / message_sent）
        message: 可读性强的中文描述
        details: 附加结构化详情
        """
        if not self._instance_id:
            return
        from app.runtime.platform.platform_logger import platform_logger
        platform_logger.log(
            instance_id=self._instance_id,
            level=level,
            event=event,
            message=message,
            adapter_type=self.platform_name,
            details=details,
        )

    @abstractmethod
    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        pass

    async def start(self) -> None:
        self._status = AdapterStatus.STARTING

    async def stop(self) -> None:
        self._status = AdapterStatus.STOPPING
        self._status = AdapterStatus.STOPPED

    async def _emit_message(self, message: PlatformMessage) -> PlatformResponse | None:
        """触发消息回调，将消息路由到主 Agent。"""
        if not self._message_handler:
            return None
        try:
            result = await self._message_handler(message, self._instance_id)
            self._message_count += 1
            return result
        except Exception as e:
            from loguru import logger
            logger.error(f"[{self.platform_name}] Message handler failed: {e}")
            self.record_error(str(e))
            return None

    async def health_check(self) -> dict:
        """健康检查，返回适配器状态信息。子类可重写。"""
        import time
        uptime = (time.time() - self._started_at) if self._started_at else 0.0
        return {
            "healthy": self._status == AdapterStatus.RUNNING,
            "status": self._status.value,
            "last_error": self._last_error,
            "uptime": uptime,
            "message_count": self._message_count,
            "error_count": self._error_count,
        }

    def get_status(self) -> dict:
        """获取适配器当前状态快照。"""
        import time
        return {
            "status": self._status.value,
            "uptime": (time.time() - self._started_at) if self._started_at else 0.0,
            "message_count": self._message_count,
            "error_count": self._error_count,
            "last_error": self._last_error,
        }

    def record_error(self, error: str) -> None:
        """记录错误信息。"""
        self._last_error = error
        self._error_count += 1
        self._status = AdapterStatus.ERROR

    def update_status(self, status: AdapterStatus) -> None:
        """更新适配器状态。"""
        self._status = status
        if status == AdapterStatus.RUNNING:
            import time
            self._started_at = time.time()

    # ─── 平台工具能力声明（tool-opt §4.7 T9 / M11）───

    @property
    def available_tools(self) -> list[dict[str, Any]]:
        """本适配器可用的平台专用工具清单（OpenAI function schema 格式）。

        子类覆盖此方法，声明自己支持的平台内操作（如 QQ 的撤回/拍一拍/群管理）。
        默认返回空列表（无平台专用工具）。

        返回的每个工具字典格式:
        {
            "type": "function",
            "function": {
                "name": "qq.poke",          # {platform}.{action} 格式
                "description": "拍一拍群成员",
                "parameters": { ... }       # JSON Schema
            }
        }
        """
        return []

    @property
    def platform_scope(self) -> str:
        """平台域 scope 标识，用于工具过滤。

        格式: "platform:{instance_id}"
        """
        return f"platform:{self._instance_id}" if self._instance_id else "platform"

    async def execute_platform_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """执行平台专用工具调用。

        Args:
            tool_name: 工具名（如 "qq.poke"）
            arguments: 工具参数

        Returns:
            {"success": bool, "output": str, "error": str}

        子类覆盖此方法，实现具体的平台工具执行逻辑。
        默认返回"工具不支持"错误。
        """
        return {
            "success": False,
            "output": "",
            "error": f"平台工具 {tool_name} 不支持（{self.platform_name} 适配器未实现）",
        }


# ─── 高风险平台工具风险闸门（修改书 W3-3，决策已定：默认关闭）───
# 按平台分组：每个平台的风险面不同（辰辰 2026-09-21 反馈）——QQ/微信是群管理
# 与撤回，Minecraft 是游戏内破坏与管理命令，互不混用，防 AI 上下文紊乱。

PLATFORM_HIGH_RISK_TOOLS: dict[str, frozenset[str]] = {
    "qq_onebot": frozenset({
        "qq.delete_msg",             # 撤回消息（不可逆）
        "qq.kick_group_member",      # 踢出群成员
        "qq.set_group_ban",          # 单人禁言
        "qq.set_group_whole_ban",    # 全员禁言
        "qq.set_group_card",         # 修改群名片（影响他人身份展示）
        "qq.set_group_special_title",  # 设置专属头衔
        "qq.set_essence_msg",        # 设为精华消息
        "qq.delete_essence_msg",     # 移除精华消息
    }),
    "wechat_personal": frozenset({
        "wechat.revoke_msg",         # 撤回消息（微信风控最高，从严）
    }),
    "telegram": frozenset({
        "telegram.delete_message",   # 删除消息（不可逆，且仅 48h 内可删）
    }),
    "discord": frozenset({
        "discord.delete_message",    # 删除消息
        "discord.timeout_member",    # 禁言成员 / timeout
    }),
    "minecraft": frozenset({
        "mc.execute_command",        # 任意服务器命令（kick/ban/op/stop 全部可达）——最高危
        "mc.attack",                 # 攻击实体（可骚扰其他玩家）
        "mc.mine_block",             # 破坏方块（改动世界/他人建筑）
    }),
    # mqtt_terminal / websocket / rest_api / game_websocket / home_assistant /
    # xiaomi_iot / qq_official / wechat_mp / wechat_work：暂无高风险平台工具
    # （IoT 设备命令为可逆的日常控制，默认开放）
}

# 未来若暴露 qq.set_group_leave（退群/解散群聊），必须归入最高档——
# 默认永不注入，即便实例开启了 platform_tools_risk_enabled 也不得自动注入，
# 仅允许在设置页手动显式开启后使用（防 AI 误操作导致失联/群损）。

# 全平台合并清单（执行面兜底判定用；工具名自带平台前缀全局唯一，合并判定等价。
# 注入面请用 get_high_risk_tools_for_platform 取对应平台子集）
HIGH_RISK_PLATFORM_TOOLS: frozenset[str] = frozenset().union(*PLATFORM_HIGH_RISK_TOOLS.values())


def get_high_risk_tools_for_platform(platform_name: str | None) -> frozenset[str]:
    """取指定平台的高风险工具清单（未知平台返回空集）。"""
    if not platform_name:
        return frozenset()
    return PLATFORM_HIGH_RISK_TOOLS.get(platform_name, frozenset())

# 高风险工具开关的实例配置键（inst.config["platform_tools_risk_enabled"]，默认 False）
PLATFORM_TOOLS_RISK_ENABLED_KEY = "platform_tools_risk_enabled"

# 执行侧拦截时的统一提示文案（注入面与执行面共用同一拒绝语）
HIGH_RISK_TOOL_BLOCKED_MESSAGE = "该操作为高风险操作，请在设置页开启后再试"


def filter_tools_by_risk(
    tools: list[dict[str, Any]],
    risk_enabled: bool,
) -> list[dict[str, Any]]:
    """按实例风险开关过滤工具清单中的高风险平台工具（W3-3 注入面闸门）。

    Args:
        tools: 适配器 available_tools 返回的 OpenAI function schema 列表，
            每项形如 {"type": "function", "function": {"name": ..., ...}}。
        risk_enabled: 实例配置 platform_tools_risk_enabled。
            False（默认）→ 剔除高风险工具（合并清单判定；适配器工具自带
            平台前缀，效果等价于按该平台子集过滤）；
            True → 原样返回（不过滤）。

    Returns:
        过滤后的工具 schema 列表（保持原有顺序）。
    """
    if risk_enabled:
        return tools
    filtered: list[dict[str, Any]] = []
    for tool in tools:
        name = ""
        if isinstance(tool, dict):
            fn = tool.get("function")
            if isinstance(fn, dict):
                name = str(fn.get("name") or "")
        if name in HIGH_RISK_PLATFORM_TOOLS:
            continue
        filtered.append(tool)
    return filtered


def get_standard_tools_for_platform(provider_name: str | None = None, model: str | None = None) -> list[dict[str, Any]]:
    """获取平台域对话的标准工具子集（双层注入第一层）。

    平台域不使用 normal 全量工具集（上下文长度原因），
    只注入 standard 层级的工具子集：
    - console.execute（命令行）
    - memory.search（记忆查询）
    - memory.build_context（记忆上下文构建）
    - schedule.list / schedule.get（定时任务查询）
    - search.everything（文件搜索）

    这些工具通过 tool_orchestrator.get_tools_for_llm() 获取，
    scope=None（只注入 shared 工具，排除 platform 专用工具）。
    然后通过白名单过滤，只保留标准子集中的工具。
    """
    from app.core.tools.orchestrator import tool_orchestrator

    # 标准子集白名单（高层语义工具，排除细粒度浏览器工具和高风险工具）
    STANDARD_WHITELIST = {
        "console.execute",
        "memory.search",
        "memory.build_context",
        "schedule.list",
        "schedule.get",
        "search.everything",
    }

    all_tools = tool_orchestrator.get_tools_for_llm(
        provider_name=provider_name,
        model=model,
        scope=None,  # 只获取 shared 工具
    )

    # 白名单过滤
    return [t for t in all_tools if t.get("function", {}).get("name") in STANDARD_WHITELIST]
