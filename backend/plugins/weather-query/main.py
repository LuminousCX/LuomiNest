"""weather-query 插件 — LuomiNest CxPlugin 示例。

演示 CxPlugin 系统的完整能力：
1. 通过 register_tool 注册自定义工具到全局 ToolRegistry（需 TOOL_REGISTER 权限）
2. 通过 @cx_handler 监听 ON_CHAT_MESSAGE 事件（默认 EVENT_LISTEN 权限）
3. 通过 get_http_client 调用外部 API（需 NETWORK 权限）
4. 通过 get_kv_store 持久化插件数据
5. 通过 get_logger 输出结构化日志

设计原则：
- 工具注册与事件监听解耦：工具供 LLM 主动调用，事件监听用于记录日志
- 不在事件处理器中阻塞主流程，仅记录与异步派发
- HTTP 客户端由 context 管理，插件不直接创建
"""
from __future__ import annotations

from typing import Any

from app.models.plugin import CxEventType
from app.runtime.plugin.cxplugin import CxPluginBase, cx_handler
from app.core.tools import ToolBase, ToolResult


# 触发天气查询的关键词（用于 ON_CHAT_MESSAGE 监听记录日志）
_WEATHER_KEYWORDS = ("天气", "weather", "气温", "温度", "下雨", "下雪", "temperatur")


class WeatherQueryTool(ToolBase):
    """天气查询工具 — 调用 wttr.in 服务查询指定城市的天气。

    工具名 `weather_query`，供 LLM function calling 调用。
    """

    @property
    def name(self) -> str:
        return "weather_query"

    @property
    def description(self) -> str:
        return "查询指定城市的当前天气情况，包括温度、湿度、风速、天气状况。支持中文城市名。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "要查询天气的城市名称，支持中英文（如 '北京'、'Shanghai'）",
                },
                "format": {
                    "type": "string",
                    "description": "返回格式（j1=JSON, j2=简略JSON），默认 j1",
                    "default": "j1",
                },
            },
            "required": ["city"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        city = str(arguments.get("city", "")).strip()
        if not city:
            return ToolResult.fail("城市名不能为空")

        fmt = str(arguments.get("format", "j1"))
        # 借用插件实例的 HTTP 客户端（由 CxPluginContext 管理生命周期）
        client = self._plugin.context.get_http_client()

        try:
            # wttr.in API: https://wttr.in/{city}?format=j1
            url = f"https://wttr.in/{city}"
            params = {"format": fmt}
            # wttr.in 根据 UA 返回不同格式，强制 JSON
            headers = {"Accept": "application/json"}
            resp = await client.get(url, params=params, headers=headers, timeout=15.0)
            if resp.status_code != 200:
                return ToolResult.fail(
                    f"天气服务返回错误：HTTP {resp.status_code}"
                )

            data = resp.json()
            # 解析 wttr.in j1 格式的核心字段
            current = data.get("current_condition", [{}])[0]
            area = data.get("nearest_area", [{}])[0]

            result_text = (
                f"📍 {area.get('areaName', [{}])[0].get('value', city)} "
                f"({area.get('country', [{}])[0].get('value', '')})\n"
                f"🌡️ 温度：{current.get('temp_C', '?')}°C（体感 {current.get('FeelsLikeC', '?')}°C）\n"
                f"☁️ 天气：{current.get('lang_zh', [{}])[0].get('value', current.get('weatherDesc', [{}])[0].get('value', '未知'))}\n"
                f"💧 湿度：{current.get('humidity', '?')}%\n"
                f"🌬️ 风速：{current.get('windspeedKmph', '?')} km/h（{current.get('winddir16Point', '?')}）\n"
                f"👁️ 能见度：{current.get('visibility', '?')} km\n"
                f"🌅 UV 指数：{current.get('uvIndex', '?')}"
            )

            # 记录调用次数到 KV 存储
            kv = self._plugin.context.get_kv_store()
            count = kv.get("query_count", 0) + 1
            kv.set("query_count", count)
            kv.set("last_query_city", city)

            self._plugin.logger.info(f"[WeatherQuery] 查询成功: {city} (第 {count} 次)")

            return ToolResult.ok(
                result_text,
                metadata={
                    "city": city,
                    "temp_c": current.get("temp_C"),
                    "query_count": count,
                },
            )
        except Exception as e:
            self._plugin.logger.error(f"[WeatherQuery] 查询失败: {city}, error={e}")
            return ToolResult.fail(f"天气查询失败：{e}")

    def bind_plugin(self, plugin: "WeatherQueryPlugin") -> "WeatherQueryTool":
        """绑定插件实例（用于访问 context.get_http_client）。"""
        self._plugin = plugin
        return self


class WeatherQueryPlugin(CxPluginBase):
    """weather-query 插件主类。

    在 initialize 阶段注册天气查询工具，并自动通过 @cx_handler 装饰器
    注册 ON_CHAT_MESSAGE 事件处理器（用于检测天气相关关键词并记录日志）。
    """

    plugin_name = "天气查询"
    plugin_version = "1.0.0"
    plugin_description = "注册天气查询工具，监听聊天消息中的天气相关关键词"

    async def initialize(self) -> None:
        # 注册天气查询工具（需 TOOL_REGISTER 权限，manifest 已声明）
        tool = WeatherQueryTool().bind_plugin(self)
        self.context.register_tool(tool)
        self.logger.info(
            f"[WeatherQuery] Plugin initialized: tool={tool.name}, "
            f"endpoint={self.context.get_config('api_endpoint')}"
        )

    @cx_handler(CxEventType.ON_CHAT_MESSAGE)
    async def on_chat_message(self, event: dict[str, Any]) -> None:
        """监听聊天消息，检测天气相关关键词并记录日志。

        此处理器仅用于日志记录与统计，不修改消息内容；
        实际天气数据由 LLM 通过 weather_query 工具主动获取。
        """
        try:
            user_text = str(event.get("user_text", "") or event.get("content", ""))
            if not user_text:
                return

            text_lower = user_text.casefold()
            matched = [kw for kw in _WEATHER_KEYWORDS if kw in text_lower]
            if not matched:
                return

            # 命中天气关键词，记录到 KV 存储用于统计分析
            kv = self.context.get_kv_store()
            hit_count = kv.get("keyword_hit_count", 0) + 1
            kv.set("keyword_hit_count", hit_count)

            self.logger.info(
                f"[WeatherQuery] 检测到天气关键词: {matched}, "
                f"消息片段: '{user_text[:50]}...' (累计命中 {hit_count} 次)"
            )
        except Exception as e:
            self.logger.warning(f"[WeatherQuery] on_chat_message 处理异常: {e}")

    async def terminate(self) -> None:
        self.logger.info("[WeatherQuery] Plugin terminated")
