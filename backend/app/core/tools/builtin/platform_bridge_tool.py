"""桌面端跨平台操作网桥工具 (Platform Bridge Tool).

当用户在桌面陪伴界面要求向 QQ群、微信、Discord、Telegram 发送消息或执行操作时，
该工具桥接桌面 Agent 与平台运行时实例，执行平台专用工具。
"""
from __future__ import annotations

import json
from typing import Any

from loguru import logger

from app.core.tools.registry import ToolBase, ToolResult


class PlatformInvokeTool(ToolBase):
    """跨平台操作网桥工具。"""

    def __init__(self) -> None:
        self._name = "platform_invoke"
        self._description = (
            "跨平台网桥工具：允许主 Agent 调用已连接的外部平台（QQ、微信、Discord、Telegram 等）"
            "执行发消息、查群信息、拍一拍、禁言、设置群公告等平台专用操作。"
        )
        self._parameters = {
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "enum": ["qq_onebot", "wechat_personal", "discord", "telegram"],
                    "description": "目标平台类型标识（如 qq_onebot, wechat_personal, discord, telegram）",
                },
                "action": {
                    "type": "string",
                    "description": "要执行的平台具体动作名称（如 qq.send_msg, qq.poke, qq.send_group_notice, wechat.send_text_message, discord.send_message, telegram.send_message 等）",
                },
                "arguments": {
                    "type": "object",
                    "description": "动作所需的参数字典",
                },
            },
            "required": ["platform", "action", "arguments"],
        }
        self.tier = "standard"
        self.category = "platform"

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict[str, Any]:
        return self._parameters

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        platform = str(arguments.get("platform", "")).strip().lower()
        action = str(arguments.get("action", "")).strip()
        action_args = arguments.get("arguments", {})
        if isinstance(action_args, str):
            try:
                action_args = json.loads(action_args)
            except Exception:
                action_args = {}

        from app.runtime.platform.registry import list_instances

        all_instances = list_instances()
        running_instances = [inst for inst in all_instances if getattr(inst.status, "value", str(inst.status)) == "running"]

        matched_instance = None
        for inst in running_instances:
            inst_type = (inst.adapter_type or "").lower()
            if platform in inst_type or inst_type in platform:
                matched_instance = inst
                break

        if not matched_instance:
            running_summary = ", ".join([f"{i.name}({i.adapter_type})" for i in running_instances]) or "无"
            msg = (
                f"未能执行平台操作：未检测到正在运行的 [{platform}] 平台连接（当前运行中的平台实例: {running_summary}）。\n"
                f"如果需要使用此功能，请先在 LuomiNest「平台设置」中启动该平台实例。"
            )
            logger.info(f"[PlatformInvokeTool] {msg}")
            return ToolResult.fail(msg)

        adapter = matched_instance.adapter
        if not adapter or not hasattr(adapter, "execute_platform_tool"):
            return ToolResult.fail(f"平台实例 {matched_instance.name} 未就绪或不支持工具调用。")

        try:
            logger.info(f"[PlatformInvokeTool] 正在通过实例 {matched_instance.name} 执行平台操作: {action}")
            result = await adapter.execute_platform_tool(action, action_args)
            success = bool(result.get("success", False))
            output = str(result.get("output", ""))
            error = str(result.get("error", ""))

            if success:
                return ToolResult.ok(output or f"平台动作 {action} 执行成功")
            else:
                return ToolResult.fail(error or output or f"平台动作 {action} 执行失败")
        except Exception as e:
            logger.error(f"[PlatformInvokeTool] 执行异常: {e}", exc_info=True)
            return ToolResult.fail(f"执行平台动作失败: {e}")
