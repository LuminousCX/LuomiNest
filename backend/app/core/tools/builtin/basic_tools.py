"""LuomiNest 基础日常工具（时间与天气查询）。

提供日常伴侣所需的即时时间与快速气象查询能力：
- get_current_time: 获取精确系统时间、星期与时区
- query_weather: 快速天气查询工具（调用轻量气象服务）
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.core.tools.registry import ToolBase, ToolResult


class GetCurrentTimeTool(ToolBase):
    """当前时间查询工具。"""

    tier: str = "core"
    scope: str = "shared"

    @property
    def name(self) -> str:
        return "get_current_time"

    @property
    def description(self) -> str:
        return "获取系统当前的精确日期、时间、星期几以及时区信息。当用户询问时间、今天几号或计算时间差时使用。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "目标时区（如 'Asia/Shanghai', 'UTC', 'America/New_York'），默认为 'Asia/Shanghai'",
                    "default": "Asia/Shanghai",
                },
            },
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        tz_name = (arguments.get("timezone") or "Asia/Shanghai").strip()
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo("Asia/Shanghai")
            tz_name = "Asia/Shanghai"

        now = datetime.now(tz)
        weekdays_zh = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        weekdays_en = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        output = (
            f"当前时间: {now.strftime('%Y年%m月%d日')} {weekdays_zh[now.weekday()]} "
            f"{now.strftime('%H:%M:%S')} ({tz_name})\n"
            f"ISO 8601: {now.isoformat()}\n"
            f"Timestamp: {int(time.time())}"
        )
        return ToolResult.ok(
            output,
            metadata={
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "weekday": weekdays_zh[now.weekday()],
                "timestamp": int(time.time()),
            },
        )


class QuickWeatherTool(ToolBase):
    """快速天气查询工具。"""

    tier: str = "core"
    scope: str = "shared"

    @property
    def name(self) -> str:
        return "query_weather"

    @property
    def description(self) -> str:
        return "快速查询指定城市或地区的实时天气状况（温度、天气现象、风力风向、湿度等）。支持中文城市名（如 '北京'、'广州'、'东京'）。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "要查询天气的城市名称（如 '北京'、'深圳'、'上海'、'Chengdu'）",
                },
            },
            "required": ["city"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        city = (arguments.get("city") or "").strip()
        if not city:
            return ToolResult.fail("缺少 city 参数")

        # P0-4：查询逻辑迁入 WeatherService（wttr.in → Open-Meteo → 兜底 + LRU 缓存）
        from app.services.weather_service import weather_service

        text = await weather_service.query_weather(city)
        return ToolResult.ok(text)
