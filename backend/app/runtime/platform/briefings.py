"""平台 briefing 提示词（2026-09-21 辰辰需求：平台上下文按平台隔离）。

核心原则（对齐市面主流 Agent 的提示词工程实践）：
- system 提示词里只注入**当前平台**的能力边界、不具备的能力（反幻觉）、
  风险约束与防封要点——绝不把其他平台的工具/能力混进当前会话，
  防止 AI 在微信里幻想拍一拍、在 Minecraft 里幻想撤回消息这类上下文紊乱。
- 主 Agent 人设（identity）全局统一一份；平台差异全部收在本模块。
- briefing 静态写能力与风险边界，工具名清单动态拼自适配器声明
  （工具增减时提示词自动跟随，不漂移）。
"""
from __future__ import annotations

from app.runtime.platform.base import get_high_risk_tools_for_platform

# 每个平台一节：<platform_briefing> 块正文。占位符：
#   {tool_names}  当前实例实际注入的工具名清单（动态拼接，逗号分隔）
#   {risk_status} 高风险操作开关状态行（动态生成）
PLATFORM_BRIEFINGS: dict[str, str] = {
    "qq_onebot": """当前平台：QQ（经 NapCat/OneBot 协议接入）。
- 交互习惯：口语化短句；群聊中仅在被 @ 时响应，回复保持简洁。
- 你在本平台的操作能力（仅限以下工具）：{tool_names}
- 典型用法：拍一拍/点赞/签到是日常互动；发群公告、改群名片、设头衔、加精华、禁言、踢人、撤回属于群管理操作。
- {risk_status}
- 防封约束：不刷屏、不群发外链和营销内容；发送节奏由系统拟人延迟控制，不要向用户承诺或解释发送机制。""",
    "wechat_personal": """当前平台：个人微信（GeweChat 协议接入，风控全平台最高）。
- 你在本平台的操作能力（仅限以下工具，能力很少是正常现象）：{tool_names}
- 微信没有：拍一拍、群管理（禁言/踢人/公告/名片/头衔）、表情回应——用户要求这些时，如实说明微信平台不支持，不要尝试调用不存在的工具。
- 撤回仅支持自己发出的、两分钟内的消息（属高风险操作，默认锁定）。
- {risk_status}
- 防封约束（务必遵守）：不营销群发、不批量操作、不发送外链；回复自然简短，像真人。""",
    "telegram": """当前平台：Telegram（Bot API 接入）。
- 你在本平台的操作能力（仅限以下工具）：{tool_names}
- Telegram 没有拍一拍/点赞；踢人、禁言、频道管理等管理能力未接入，用户要求时如实说明。
- 删除消息仅支持 48 小时内的消息，属高风险操作（默认锁定）；置顶（pin）可逆、默认可用。
- {risk_status}
- Bot 操作受其管理员权限约束，操作失败时如实向用户转述原因，不要重试刷屏。""",
    "discord": """当前平台：Discord（Bot Gateway + REST 接入）。
- 你在本平台的操作能力（仅限以下工具）：{tool_names}
- 典型用法：表情回应（add_reaction）是日常互动；删除消息、timeout 属管理操作。
- 踢出/封禁/频道管理/Embed 消息未接入，用户要求时如实说明，不要幻觉调用。
- {risk_status}
- 遵守 Discord 速率限制（系统已处理 429），不要连续快速发送。""",
    "minecraft": """当前平台：Minecraft 游戏服务器（以主 Agent 的游戏角色身份在服内活动）。
- 你在本平台的操作能力（仅限以下工具）：{tool_names}
- 其中 mc.execute_command 可执行任意服务器命令（含 kick/ban/op/stop），是全平台最高危操作；mc.attack（攻击实体）与 mc.mine_block（破坏方块）可能影响其他玩家的体验与建筑。
- {risk_status}
- 行为准则：对其他玩家保持友好，仅在主人要求或服务器规则允许时做破坏性/管理性操作；建造与移动属于正常游戏行为，可自然进行。""",
    "mqtt_terminal": """当前平台：IoT 硬件终端（ESP32 等 MQTT 设备）。
- 你在本平台的能力：读取设备遥测（温度/湿度/电量等）、向设备下发控制命令。
- 无社交消息能力（不存在发消息/撤回/群管理概念），用户闲聊时自然回应即可。
- 设备控制是可逆的日常操作，默认可用；传感器数据可能延迟，报告数值时注明是最近一次上报。""",
}

# 未知平台的通用兜底模板（新适配器未写 briefing 时降级使用）
_GENERIC_BRIEFING = """当前平台：{platform_name}。
- 你在本平台的操作能力（仅限以下工具）：{tool_names}
- 只调用上方清单中真实存在的工具；清单里没有的能力，如实告知用户本平台不支持。
- {risk_status}"""


def _risk_status_line(platform_name: str, risk_enabled: bool) -> str:
    if risk_enabled:
        return (
            "高风险管理操作已由主人在设置页开启（踢人/禁言/撤回等会出现在你的工具里），"
            "执行这类操作前确认目标明确，拿不准时先向主人复述待执行的操作。"
        )
    high_risk = get_high_risk_tools_for_platform(platform_name)
    if not high_risk:
        return "本平台没有高风险管理操作。"
    sample = "、".join(sorted(high_risk)[:3])
    return (
        f"高风险管理操作（如 {sample} 等）当前已被主人关闭，你的工具清单里不会出现它们；"
        "用户要求这类操作时，告知需要主人在平台设置页开启「高风险操作」开关。"
    )


def get_platform_briefing(
    platform_name: str | None,
    risk_enabled: bool = False,
    tool_names: list[str] | None = None,
) -> str:
    """构建当前平台的 briefing 块（仅含本平台能力与风险，供 system 注入）。

    Args:
        platform_name: 适配器 platform_name（如 qq_onebot / minecraft）。
        risk_enabled: 实例的高风险操作开关状态（动态生成状态行）。
        tool_names: 当前实例实际注入的平台工具名（动态拼接，防漂移）。
    """
    if not platform_name:
        return ""
    names = ", ".join(tool_names or []) or "（无平台专属工具）"
    risk_line = _risk_status_line(platform_name, risk_enabled)
    template = PLATFORM_BRIEFINGS.get(platform_name, _GENERIC_BRIEFING)
    body = template.format(
        platform_name=platform_name,
        tool_names=names,
        risk_status=risk_line,
    )
    return f"<platform_briefing>\n{body}\n</platform_briefing>"
