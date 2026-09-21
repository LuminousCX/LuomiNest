"""LuomiNest 基础日常工具（时间与天气查询）。

提供日常伴侣所需的即时时间与快速气象查询能力：
- get_current_time: 获取精确系统时间、星期、农历/节气提示与时区
- query_weather: 快速天气查询工具（调用轻量气象服务）
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from loguru import logger

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

        import httpx

        # 优先使用 wttr.in 紧凑格式
        url = f"https://wttr.in/{city}?format=%l:+%c+%t,+湿度:+%h,+风力:+%w&lang=zh"
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                resp = await client.get(
                    url,
                    headers={"User-Agent": "curl/7.68.0"},
                )
                if resp.status_code == 200 and resp.text.strip():
                    text = resp.text.strip()
                    # 避免 404/未知页面的 HTML 返回
                    if "<html" not in text.lower():
                        return ToolResult.ok(f"【{city} 天气】{text}")

            # 备用方案：wttr.in json
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                resp = await client.get(
                    f"https://wttr.in/{city}?format=j1&lang=zh",
                    headers={"User-Agent": "curl/7.68.0"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    current = data.get("current_condition", [{}])[0]
                    temp_c = current.get("temp_C", "--")
                    desc = current.get("lang_zh", [{}])[0].get("value") or current.get("weatherDesc", [{}])[0].get("value", "晴")
                    humidity = current.get("humidity", "--")
                    wind = current.get("windspeedKmph", "--")
                    return ToolResult.ok(
                        f"【{city} 实时天气】\n"
                        f"- 天气状况: {desc}\n"
                        f"- 当前气温: {temp_c}°C\n"
                        f"- 相对湿度: {humidity}%\n"
                        f"- 风速: {wind} km/h"
                    )
        except Exception as e:
            logger.warning(f"[QuickWeatherTool] 天气服务连接超时或异常 ({city}): {e}")

        return ToolResult.ok(f"暂未获取到城市「{city}」的实时气象数据，请稍后重试或检查城市名称。")
