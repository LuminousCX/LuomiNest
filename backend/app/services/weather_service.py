"""天气查询服务（P0-4「天气多源缓存」）。

原 QuickWeatherTool 在工具内直连 wttr.in（单点依赖、无缓存）；本服务把查询
逻辑迁出为可复用服务，工具侧只做参数校验与结果包装（schema 不变）：

- 缓存：城市规范化（strip + casefold）为键的 LRU（默认 64 条），TTL 内命中
  不再打外网（同城市连查只打一次）；仅缓存成功结果，失败不污染缓存；
- provider 链：wttr.in（保留原有紧凑格式 + j1 JSON 双段解析）
  → Open-Meteo（免 key：geocoding 拿经纬度 → forecast 拿当前实况，
  WMO weather_code 映射中文天气描述）→ 兜底文案；
- 全程 httpx 异步 + 可配超时（默认 8 秒），单一 provider 失败仅告警并降级
  到下一级，绝不抛出。
"""
from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any
from urllib.parse import quote

import httpx
from loguru import logger

from app.core.config import settings

# wttr.in 沿用 curl UA（服务端按 UA 出文本格式，浏览器 UA 会拿回 HTML）
_WTTR_HEADERS = {"User-Agent": "curl/7.68.0"}

# LRU 最大条目数：常用城市量级，超限淘汰最久未命中的条目
_CACHE_MAX_ENTRIES = 64

# ── WMO weather code → 中文天气描述 ─────────────────────────────────────────
# Open-Meteo forecast 接口 current.weather_code 的标准映射（WMO 4677 表子集）

_WMO_WEATHER_CODE_ZH: dict[int, str] = {
    0: "晴",
    1: "基本晴",
    2: "局部多云",
    3: "阴",
    45: "雾",
    48: "雾凇",
    51: "轻毛毛雨",
    53: "中毛毛雨",
    55: "浓毛毛雨",
    56: "轻冻毛毛雨",
    57: "浓冻毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    66: "轻冻雨",
    67: "强冻雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    77: "雪粒",
    80: "小阵雨",
    81: "中阵雨",
    82: "强阵雨",
    85: "小阵雪",
    86: "大阵雪",
    95: "雷阵雨",
    96: "雷阵雨伴小冰雹",
    99: "雷阵雨伴大冰雹",
}


def wmo_code_to_desc(code: Any) -> str:
    """WMO weather code → 中文天气描述（未知/非法值返回「未知天气」）。"""
    try:
        return _WMO_WEATHER_CODE_ZH.get(int(code), "未知天气")
    except (TypeError, ValueError):
        return "未知天气"


class WeatherService:
    """天气查询服务（LRU 缓存 + wttr.in → Open-Meteo → 兜底 provider 链）。

    Usage:
        text = await weather_service.query_weather("北京")
    """

    def __init__(
        self,
        ttl: float | None = None,
        max_entries: int = _CACHE_MAX_ENTRIES,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._ttl = float(ttl) if ttl is not None else float(settings.WEATHER_CACHE_TTL)
        self._max_entries = int(max_entries)
        # transport 仅供测试注入 httpx.MockTransport（生产恒为 None 走真实网络）
        self._transport = transport
        # city_key -> (formatted_text, cached_at)
        self._cache: OrderedDict[str, tuple[str, float]] = OrderedDict()

    # ── 对外入口 ────────────────────────────────────────────────────────────

    async def query_weather(self, city: str) -> str:
        """查询城市实时天气，恒返回可读文本（全部 provider 失败时返回兜底文案）。"""
        city = (city or "").strip()
        if not city:
            return "缺少城市名称，请指定要查询天气的城市（如 '北京'、'Shanghai'）。"

        cache_key = self._normalize_city(city)
        cached = self._cache_get(cache_key)
        if cached is not None:
            logger.debug(f"[WeatherService] 缓存命中: {city}")
            return cached

        # provider 链：wttr.in → Open-Meteo（免 key）→ 兜底文案
        text = await self._fetch_wttr(city)
        if text is None:
            text = await self._fetch_open_meteo(city)
        if text is None:
            # 失败结果不入缓存：下一轮查询立即重试，不让短暂故障被 TTL 放大
            logger.warning(f"[WeatherService] 全部天气源查询失败: {city}")
            return f"暂未获取到城市「{city}」的实时气象数据，请稍后重试或检查城市名称。"

        self._cache_set(cache_key, text)
        return text

    def clear_cache(self) -> None:
        """清空缓存（测试 / 手动刷新用）。"""
        self._cache.clear()

    # ── provider 1：wttr.in（保留原有双段解析） ─────────────────────────────

    async def _fetch_wttr(self, city: str) -> str | None:
        """wttr.in 紧凑格式优先，失败再试 j1 JSON；任何异常返回 None 降级。"""
        try:
            # 优先使用 wttr.in 紧凑格式
            async with self._build_client() as client:
                resp = await client.get(
                    f"https://wttr.in/{city}?format=%l:+%c+%t,+湿度:+%h,+风力:+%w&lang=zh",
                    headers=_WTTR_HEADERS,
                )
                if resp.status_code == 200 and resp.text.strip():
                    text = resp.text.strip()
                    # 避免 404/未知页面的 HTML 返回
                    if "<html" not in text.lower():
                        return f"【{city} 天气】{text}"

            # 备用方案：wttr.in json
            async with self._build_client() as client:
                resp = await client.get(
                    f"https://wttr.in/{city}?format=j1&lang=zh",
                    headers=_WTTR_HEADERS,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    current = data.get("current_condition", [{}])[0]
                    temp_c = current.get("temp_C", "--")
                    desc = (
                        current.get("lang_zh", [{}])[0].get("value")
                        or current.get("weatherDesc", [{}])[0].get("value", "晴")
                    )
                    humidity = current.get("humidity", "--")
                    wind = current.get("windspeedKmph", "--")
                    return (
                        f"【{city} 实时天气】\n"
                        f"- 天气状况: {desc}\n"
                        f"- 当前气温: {temp_c}°C\n"
                        f"- 相对湿度: {humidity}%\n"
                        f"- 风速: {wind} km/h"
                    )
        except Exception as e:
            logger.warning(f"[WeatherService] wttr.in 查询失败（{city}），尝试下一数据源: {e}")
        return None

    # ── provider 2：Open-Meteo（免 key） ────────────────────────────────────

    async def _fetch_open_meteo(self, city: str) -> str | None:
        """Open-Meteo 免 key 链：geocoding 拿经纬度 → forecast 拿当前实况。"""
        try:
            geo = await self._geocode(city)
            if geo is None:
                return None
            lat, lon, name = geo

            url = (
                "https://api.open-meteo.com/v1/forecast"
                f"?latitude={lat}&longitude={lon}"
                "&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
                "&timezone=auto"
            )
            async with self._build_client() as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.warning(f"[WeatherService] Open-Meteo forecast HTTP {resp.status_code}（{city}）")
                    return None
                data = resp.json()

            current = data.get("current") or {}
            desc = wmo_code_to_desc(current.get("weather_code"))
            temp = current.get("temperature_2m", "--")
            humidity = current.get("relative_humidity_2m", "--")
            wind = current.get("wind_speed_10m", "--")
            return (
                f"【{name or city} 实时天气】（数据源: Open-Meteo）\n"
                f"- 天气状况: {desc}\n"
                f"- 当前气温: {temp}°C\n"
                f"- 相对湿度: {humidity}%\n"
                f"- 风速: {wind} km/h"
            )
        except Exception as e:
            logger.warning(f"[WeatherService] Open-Meteo 查询失败（{city}）: {e}")
            return None

    async def _geocode(self, city: str) -> tuple[float, float, str] | None:
        """Open-Meteo geocoding：城市名 → (纬度, 经度, 规范地名)。解析失败返回 None。"""
        url = (
            "https://geocoding-api.open-meteo.com/v1/search"
            f"?name={quote(city)}&count=1&language=zh&format=json"
        )
        async with self._build_client() as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                logger.warning(f"[WeatherService] Open-Meteo geocoding HTTP {resp.status_code}（{city}）")
                return None
            data = resp.json()
        results = data.get("results") or []
        if not results:
            logger.warning(f"[WeatherService] Open-Meteo geocoding 无结果（{city}）")
            return None
        first = results[0]
        return float(first["latitude"]), float(first["longitude"]), str(first.get("name") or city)

    # ── 缓存与 HTTP 工具 ────────────────────────────────────────────────────

    def _build_client(self) -> httpx.AsyncClient:
        """构造 httpx 客户端（transport 仅测试注入 MockTransport）。"""
        kwargs: dict[str, Any] = {
            "timeout": settings.WEATHER_HTTP_TIMEOUT,
            "follow_redirects": True,
        }
        if self._transport is not None:
            kwargs["transport"] = self._transport
        return httpx.AsyncClient(**kwargs)

    @staticmethod
    def _normalize_city(city: str) -> str:
        """缓存键：城市名规范化（去首尾空白 + casefold，拉丁名大小写归一）。"""
        return city.strip().casefold()

    def _cache_get(self, key: str) -> str | None:
        """LRU 命中读取：过期即淘汰，命中则移到队尾。"""
        entry = self._cache.get(key)
        if entry is None:
            return None
        text, cached_at = entry
        if time.time() - cached_at > self._ttl:
            self._cache.pop(key, None)
            return None
        self._cache.move_to_end(key)
        return text

    def _cache_set(self, key: str, text: str) -> None:
        """LRU 写入：超限淘汰最久未命中的条目。"""
        self._cache[key] = (text, time.time())
        self._cache.move_to_end(key)
        while len(self._cache) > self._max_entries:
            self._cache.popitem(last=False)


# 模块级单例（工具侧直接引用；测试可用 WeatherService(ttl=..., transport=...) 自建实例）
weather_service = WeatherService()
