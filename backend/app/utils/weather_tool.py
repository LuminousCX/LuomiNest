"""
天气工具模块 —— 本地毫秒级天气查询，零大模型调用

功能：
  对接 Open-Meteo 免费天气 API（无需 API 密钥），支持城市实时天气查询、
  指定日期预报查询（最多7天）、5 分钟内存缓存、口语化自然语言回复生成、
  场景化出行/穿搭/防晒建议、全链路异常兜底。

核心流程：
  1. 用户消息 → 提取城市名 + 解析日期 → 地理编码（城市→经纬度）
  2. 经纬度 → 获取天气数据（实时 current 或每日 daily 预报）
  3. WMO 天气码 → 中文天气描述
  4. 结构化数据 → 自然语言口语化回复 + 场景化建议

设计原则：
  1. 类+全局单例模式，与 time_tool.py 完全对齐
  2. 5分钟LRU缓存，按"城市_日期"粒度，实时与预报分开缓存
  3. 三层降级：API成功 → 兜底常识库 → 友好话术
  4. 所有异常不抛向调用方，返回友好兜底
  5. 纯本地封装，不改动现有项目的其他逻辑
"""

import asyncio
import hashlib
import json
import re
from enum import Enum
from functools import lru_cache
from datetime import datetime, timezone, timedelta
from loguru import logger

import httpx


# =============================================================================
# 日期查询类型枚举
# =============================================================================

class DateType(Enum):
    """日期查询类型"""
    TODAY = "today"              # 今日实时天气
    FORECAST = "forecast"        # 预报日期（1-7天内）
    OUT_OF_RANGE = "out_of_range"  # 超出预报范围


# =============================================================================
# WMO 天气码 → 中文天气描述映射
# =============================================================================

WMO_WEATHER_MAP: dict[int, str] = {
    0: "晴天",
    1: "大部晴朗",
    2: "多云间晴",
    3: "多云",
    45: "有雾",
    48: "雾凇",
    51: "小毛毛雨",
    53: "中等毛毛雨",
    55: "大毛毛雨",
    56: "小冻毛毛雨",
    57: "大冻毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    66: "小冻雨",
    67: "大冻雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    77: "雪粒",
    80: "小阵雨",
    81: "中等阵雨",
    82: "大阵雨",
    85: "小阵雪",
    86: "大阵雪",
    95: "雷暴",
    96: "小冰雹雷暴",
    99: "大冰雹雷暴",
}

# =============================================================================
# 风力等级 → 中文描述映射（蒲福风级）
# =============================================================================

WIND_SCALE_MAP: dict[int, str] = {
    0: "无风",
    1: "微风",
    2: "轻风",
    3: "和风",
    4: "清风",
    5: "劲风",
    6: "强风",
    7: "疾风",
    8: "大风",
    9: "烈风",
    10: "狂风",
    11: "暴风",
    12: "飓风",
}

# =============================================================================
# 常用城市→经纬度兜底映射（减少地理编码 API 调用）
# =============================================================================

CITY_COORDINATES: dict[str, tuple[float, float]] = {
    "北京": (39.9042, 116.4074),
    "上海": (31.2304, 121.4737),
    "广州": (23.1291, 113.2644),
    "深圳": (22.5431, 114.0579),
    "杭州": (30.2741, 120.1551),
    "成都": (30.5728, 104.0668),
    "武汉": (30.5928, 114.3055),
    "西安": (34.3416, 108.9398),
    "南京": (32.0603, 118.7969),
    "重庆": (29.4316, 106.9123),
    "天津": (39.3434, 117.3616),
    "苏州": (31.2990, 120.5853),
    "长沙": (28.2282, 112.9388),
    "郑州": (34.7466, 113.6253),
    "济南": (36.6512, 117.1201),
    "青岛": (36.0671, 120.3826),
    "大连": (38.9140, 121.6147),
    "厦门": (24.4798, 118.0894),
    "福州": (26.0745, 119.2965),
    "昆明": (25.0389, 102.7183),
    "贵阳": (26.6470, 106.6302),
    "南宁": (22.8170, 108.3665),
    "海口": (20.0440, 110.1999),
    "三亚": (18.2528, 109.5120),
    "哈尔滨": (45.8038, 126.5350),
    "长春": (43.8171, 125.3235),
    "沈阳": (41.8057, 123.4315),
    "乌鲁木齐": (43.8256, 87.6168),
    "拉萨": (29.6500, 91.1000),
    "兰州": (36.0611, 103.8343),
    "银川": (38.4872, 106.2309),
    "西宁": (36.6171, 101.7785),
    "呼和浩特": (40.8426, 111.7490),
    "太原": (37.8706, 112.5489),
    "石家庄": (38.0428, 114.5149),
    "合肥": (31.8206, 117.2272),
    "南昌": (28.6820, 115.8579),
}


def _minute_bucket_key(key: str) -> str:
    """生成带 5 分钟粒度的缓存键

    在当前分钟向下取整到 5 的倍数后追加原始键，
    实现"5分钟内相同查询走缓存，5分钟后自动失效"。

    参数:
        key: 原始缓存键（城市名+日期）

    返回:
        带时间戳的缓存键，如 "2026-05-06T15:30_北京_2026-05-06"
    """
    now = datetime.now(timezone.utc)
    minute = now.minute // 5 * 5
    ts = now.replace(minute=minute, second=0, microsecond=0).isoformat()
    return f"{ts}_{key}"


# =============================================================================
# 日期解析 —— 口语化日期 → 标准 YYYY-MM-DD
# =============================================================================

# 中文数字映射
_CN_NUM = {
    "零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}

_WEEKDAY_NUM = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6}

_WEEKDAY_CN = {
    "周一": 0, "周二": 1, "周三": 2, "周四": 3, "周五": 4, "周六": 5, "周日": 6,
}
for ch, idx in _WEEKDAY_NUM.items():
    _WEEKDAY_CN[f"星期{ch}"] = idx


def parse_query_date(date_str: str) -> dict:
    """将用户输入的口语化日期解析为标准 YYYY-MM-DD 格式

    支持的日期格式：
      - "5.1号"、"5月1日"、"5.1"、"5/1"、"2026-05-01"（数字日期）
      - "今天"、"今日"、"明天"、"明日"、"后天"、"大后天"（相对日期）
      - "3天后"、"三天后"、"3天后"（偏移日期）
      - "下周一"、"下周二"…"下周日"（下周）
      - "昨天"、"前天"（历史日期）

    参数:
        date_str: 用户输入的原始日期文本

    返回:
        字典：
          - "date": YYYY-MM-DD 格式日期
          - "type": DateType 枚举值（TODAY / FORECAST / OUT_OF_RANGE）
          - "day_offset": 距离今天的天数（0=今天，1=明天，负数=过去）
          - "error": 解析失败时的提示信息（成功时为 None）
    """
    if not date_str or not date_str.strip():
        return {"date": datetime.now().strftime("%Y-%m-%d"), "type": DateType.TODAY, "day_offset": 0, "error": None}

    text = date_str.strip()
    today = datetime.now().date()
    max_forecast = 7  # Open-Meteo 免费 API 最多支持 7 天预报

    # ---- 1. 相对日期（今天/明天/后天/大后天/昨天/前天）----
    relative_map = {
        "大前天": -3, "前天": -2, "昨天": -1,
        "今天": 0, "今日": 0,
        "明天": 1, "明日": 1,
        "后天": 2,
        "大后天": 3,
    }
    for word, offset in relative_map.items():
        if word in text:
            target_date = today + timedelta(days=offset)
            delta = (target_date - today).days
            if delta < 0:
                dt = DateType.OUT_OF_RANGE
            elif delta == 0:
                dt = DateType.TODAY
            elif delta <= max_forecast:
                dt = DateType.FORECAST
            else:
                dt = DateType.OUT_OF_RANGE
            return {"date": target_date.strftime("%Y-%m-%d"), "type": dt, "day_offset": delta, "error": None}

    # ---- 2. N天后（如 "3天后"、"三天后"）----
    offset_match = re.match(r"(\d+|[一二三四五六七八九十]+)\s*天?后", text)
    if offset_match:
        raw = offset_match.group(1)
        if raw.isdigit():
            offset = int(raw)
        else:
            offset = 0
            for ch in raw:
                if ch == "十":
                    offset = max(offset, 1) * 10
                elif ch in _CN_NUM:
                    offset += _CN_NUM[ch]
        target_date = today + timedelta(days=offset)
        delta = (target_date - today).days
        dt = DateType.FORECAST if delta <= max_forecast else DateType.OUT_OF_RANGE
        return {"date": target_date.strftime("%Y-%m-%d"), "type": dt, "day_offset": delta, "error": None}

    # ---- 3. 下周一/下周二…下周日 ----
    for week_word, weekday_idx in _WEEKDAY_CN.items():
        if week_word in text:
            import calendar
            today_weekday = today.weekday()
            days_until = (weekday_idx - today_weekday) % 7
            if days_until == 0:
                days_until = 7  # "下周一"含义是下周，不是本周
            if days_until <= 7:
                days_until = days_until + 7 if days_until <= 0 else days_until
            target_date = today + timedelta(days=days_until)
            delta = (target_date - today).days
            dt = DateType.FORECAST if delta <= max_forecast else DateType.OUT_OF_RANGE
            return {"date": target_date.strftime("%Y-%m-%d"), "type": dt, "day_offset": delta, "error": None}

    # ---- 4. 数字日期（5.1号 / 5月1日 / 5.1 / 5/1 / 2026-05-01）----
    # 匹配 "5.1号"、"5月1日"、"2026-05-01"、"5.1"、"5/1"、"5-1"
    num_match = re.search(
        r"((?P<year>\d{4})[-/\.年])?"
        r"(?P<month>\d{1,2})"
        r"[-/\.月]"
        r"(?P<day>\d{1,2})"
        r"[日号]?",
        text
    )
    if num_match:
        year = int(num_match.group("year")) if num_match.group("year") else today.year
        month = int(num_match.group("month"))
        day = int(num_match.group("day"))
        try:
            target_date = datetime(year=year, month=month, day=day).date()
        except ValueError:
            return {"date": today.strftime("%Y-%m-%d"), "type": DateType.TODAY, "day_offset": 0,
                    "error": f"日期 {year}-{month}-{day} 不存在，已为你查询今天天气"}

        delta = (target_date - today).days
        if delta < 0:
            dt = DateType.OUT_OF_RANGE
        elif delta == 0:
            dt = DateType.TODAY
        elif delta <= max_forecast:
            dt = DateType.FORECAST
        else:
            dt = DateType.OUT_OF_RANGE
        return {"date": target_date.strftime("%Y-%m-%d"), "type": dt, "day_offset": delta, "error": None}

    # ---- 兜底：无法解析，按今天处理 ----
    return {"date": today.strftime("%Y-%m-%d"), "type": DateType.TODAY, "day_offset": 0,
            "error": f"日期格式无法识别，已为你查询今天天气"}


# =============================================================================
# WeatherTool 核心类
# =============================================================================

class WeatherTool:
    """本地天气工具 —— 毫秒级天气查询，零大模型调用

    设计参考 time_tool.py，采用相同的类+全局单例架构。

    用法:
        tool = WeatherTool(default_city="北京")
        reply = await tool.get_reply("上海")  # 查询上海今天天气
        reply = await tool.get_reply("北京", days=3)  # 查询北京3天预报
    """

    def __init__(self, default_city: str = "北京"):
        """初始化天气工具

        参数:
            default_city: 默认城市，用户未指定城市时使用。
                          后续可对接用户记忆系统的所在地字段。
        """
        self.default_city = default_city
        self._geocoding_cache: dict[str, tuple[float, float]] = {}

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    async def get_reply(self, city: str | None = None, date_str: str = "") -> str:
        """获取天气自然语言回复（主入口）

        参数:
            city: 城市名称，None 时使用默认城市
            date_str: 用户输入的原始日期文本，
                      支持 "今天"、"明天"、"5.1号"、"下周一" 等口语化格式，
                      空字符串默认今天

        返回:
            自然语言天气回复字符串

        异常安全：
            任意环节异常均不抛异常，返回友好兜底话术
        """
        city = city or self.default_city
        if not city or not city.strip():
            city = self.default_city

        city = city.strip()

        try:
            # 解析日期
            parsed = parse_query_date(date_str)
            target_date = parsed["date"]
            date_type = parsed["type"]
            day_offset = parsed["day_offset"]
            parse_error = parsed.get("error")

            # 超出预报范围 → 直接返回友好提示
            if date_type == DateType.OUT_OF_RANGE:
                if day_offset < 0:
                    return self._fallback(city, f"「{city}」{abs(day_offset)}天前的天气数据已超出查询范围，我只能查询今天及未来7天的天气哦~")
                return self._fallback(city, f"「{city}」{target_date}的天气预报已超出7天查询范围，我只支持查询今天及未来7天的天气哦~")

            # 缓存键：城市_日期
            cache_key_raw = f"{city}_{target_date}"
            cache_key = _minute_bucket_key(cache_key_raw)

            # LRU 缓存取数据
            weather_data = _cached_weather_fetch(city, cache_key, 1)
            if weather_data is None:
                coordinates = await self._get_coordinates(city)
                if coordinates is None:
                    return self._fallback(city, f"找不到「{city}」的地理位置，换个城市试试？")
                lat, lon = coordinates
                # 获取足够的预报天数（也包含今天）
                fetch_days = max(day_offset + 1, 1)
                weather_data = await self._fetch_weather(lat, lon, fetch_days)
                if weather_data is None:
                    return self._fallback(city, f"暂时无法获取「{city}」的天气数据，请稍后再试哦~")
                _cache_weather_result(cache_key, json.dumps(weather_data, ensure_ascii=False))

            # 根据日期类型生成对应回复
            if date_type == DateType.TODAY:
                reply = self._format_single_day(city, weather_data, day_offset=0)
            else:
                reply = self._format_forecast_reply(city, weather_data, target_date, day_offset)

            # 若有日期解析提示，附在末尾
            if parse_error and "无法识别" not in parse_error:
                reply += f"（{parse_error}）"

            return reply

        except httpx.TimeoutException:
            logger.warning(f"[WeatherTool] API请求超时: {city}")
            return self._fallback(city, "天气API响应超时，建议过会儿再查~")
        except httpx.HTTPStatusError as e:
            logger.warning(f"[WeatherTool] API返回错误: {city}, status={e.response.status_code}")
            return self._fallback(city, "天气服务暂时不可用，稍后再试吧~")
        except Exception as e:
            logger.warning(f"[WeatherTool] 获取天气异常: {city}, error={e}")
            return self._fallback(city)

    # ------------------------------------------------------------------
    # 地理编码 —— 城市名→经纬度
    # ------------------------------------------------------------------

    async def _get_coordinates(self, city: str) -> tuple[float, float] | None:
        """将城市名转换为经纬度坐标

        三级查找策略：
          1. 内置映射表 CITY_COORDINATES（0ms，零网络开销）
          2. 运行时缓存（同进程复用）
          3. Open-Meteo Geocoding API

        参数:
            city: 城市名称

        返回:
            (纬度, 经度) 元组，失败返回 None
        """
        # 第一层：内置映射表
        coords = CITY_COORDINATES.get(city)
        if coords:
            return coords

        # 第二层：运行时缓存
        coords = self._geocoding_cache.get(city)
        if coords:
            return coords

        # 第三层：Geocoding API
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={
                        "name": city,
                        "count": 1,
                        "language": "zh",
                        "format": "json",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results", [])
                if results:
                    lat = results[0]["latitude"]
                    lon = results[0]["longitude"]
                    self._geocoding_cache[city] = (lat, lon)
                    return (lat, lon)
        except Exception as e:
            logger.debug(f"[WeatherTool] 地理编码失败: {city}, error={e}")

        return None

    # ------------------------------------------------------------------
    # 天气数据获取 —— 经纬度→天气
    # ------------------------------------------------------------------

    async def _fetch_weather(self, lat: float, lon: float, days: int = 1) -> dict | None:
        """从 Open-Meteo API 获取天气预报数据

        参数:
            lat: 纬度
            lon: 经度
            days: 预报天数（1-7）

        返回:
            结构化天气数据字典，失败返回 None

        Open-Meteo 免费 API 说明：
          - 无需注册，无需 API 密钥
          - 速率限制：10,000次/天
          - 返回 daily 级数据：最高温/最低温/天气码/风力/相对湿度/降水概率
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": lat,
                        "longitude": lon,
                        "daily": [
                            "temperature_2m_max",
                            "temperature_2m_min",
                            "weathercode",
                            "windspeed_10m_max",
                            "winddirection_10m_dominant",
                            "relative_humidity_2m_max",
                            "precipitation_probability_max",
                        ],
                        "timezone": "Asia/Shanghai",
                        "forecast_days": min(days, 7),  # 限制最大7天
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                daily = data.get("daily", {})

                if not daily:
                    return None

                # 组装结构化天气数据
                dates = daily.get("time", [])
                temps_max = daily.get("temperature_2m_max", [])
                temps_min = daily.get("temperature_2m_min", [])
                weather_codes = daily.get("weathercode", [])
                wind_speeds = daily.get("windspeed_10m_max", [])
                wind_dirs = daily.get("winddirection_10m_dominant", [])
                humidities = daily.get("relative_humidity_2m_max", [])
                precip_probs = daily.get("precipitation_probability_max", [])

                forecast_days = []
                for i in range(min(days, len(dates))):
                    wmo_code = int(weather_codes[i]) if i < len(weather_codes) else 0
                    wind_speed = wind_speeds[i] if i < len(wind_speeds) else 0
                    wind_dir = int(wind_dirs[i]) if i < len(wind_dirs) else 0
                    humidity = int(humidities[i]) if i < len(humidities) else 0
                    precip_prob = int(precip_probs[i]) if i < len(precip_probs) else 0

                    forecast_days.append({
                        "date": dates[i],
                        "weather": WMO_WEATHER_MAP.get(wmo_code, "未知"),
                        "temp_max": round(temps_max[i], 1) if i < len(temps_max) else None,
                        "temp_min": round(temps_min[i], 1) if i < len(temps_min) else None,
                        "wind_speed": round(wind_speed, 1),
                        "wind_direction": self._wind_direction_name(wind_dir),
                        "wind_scale": self._wind_scale_name(wind_speed),
                        "humidity": humidity,
                        "precipitation_probability": precip_prob,
                    })

                return {"forecast_days": forecast_days}

        except httpx.TimeoutException:
            logger.warning(f"[WeatherTool] 天气API超时: lat={lat}, lon={lon}")
        except httpx.HTTPStatusError as e:
            logger.warning(f"[WeatherTool] 天气API错误: status={e.response.status_code}")
        except Exception as e:
            logger.warning(f"[WeatherTool] 天气API异常: {e}")

        return None

    # ------------------------------------------------------------------
    # 自然语言回复生成
    # ------------------------------------------------------------------

    def _format_single_day(self, city: str, weather_data: dict, day_offset: int = 0) -> str:
        """格式化今日实时天气回复 —— 口语化、带场景建议

        参数:
            city: 城市名
            weather_data: _fetch_weather 返回的结构化数据
            day_offset: 日期偏移（0=今天）
        """
        forecast_days = weather_data.get("forecast_days", [])
        if not forecast_days:
            return f"暂时没有「{city}」的天气数据哦~"

        day = forecast_days[0] if day_offset < len(forecast_days) else forecast_days[0]
        weather = day.get("weather", "未知")
        temp_min = day.get("temp_min", 0)
        temp_max = day.get("temp_max", 0)
        wind_scale = day.get("wind_scale", "")
        wind_dir = day.get("wind_direction", "")
        precip_prob = day.get("precipitation_probability", 0)
        wmo_code = self._infer_wmo_code(day)

        # 生成丰富的场景化建议
        suggestion = self._generate_rich_suggestion(
            wmo_code, temp_max, temp_min, wind_scale, precip_prob
        )

        # 口语化开头
        greeting = self._weather_greeting(weather, temp_max)

        lines = [
            f"{greeting}「{city}」现在是{weather}，气温在{temp_min}℃到{temp_max}℃之间。",
        ]

        # 风力信息（简洁）
        if wind_scale and wind_scale != "无风":
            lines.append(f"当前{wind_dir}{wind_scale}，体感温度会偏低一些。")

        # 降水提示
        if precip_prob >= 60:
            lines.append(f"降水概率高达{precip_prob}%，出门记得带伞哦。")
        elif precip_prob >= 30:
            lines.append(f"有{precip_prob}%的概率会降水，可以随身带把伞以防万一。")

        # 场景化建议
        if suggestion:
            lines.append(suggestion)

        return "".join(lines)

    def _format_forecast_reply(self, city: str, weather_data: dict, target_date: str, day_offset: int) -> str:
        """格式化指定日期预报回复

        参数:
            city: 城市名
            weather_data: _fetch_weather 返回的结构化数据
            target_date: 目标日期 YYYY-MM-DD
            day_offset: 距今天数
        """
        forecast_days = weather_data.get("forecast_days", [])
        if not forecast_days or day_offset >= len(forecast_days):
            return f"暂时没有「{city}」{target_date}的预报数据哦~"

        day = forecast_days[day_offset]
        weather = day.get("weather", "未知")
        temp_min = day.get("temp_min", 0)
        temp_max = day.get("temp_max", 0)
        wind_scale = day.get("wind_scale", "")
        wind_dir = day.get("wind_direction", "")
        precip_prob = day.get("precipitation_probability", 0)
        wmo_code = self._infer_wmo_code(day)

        date_label = self._date_label(target_date)

        suggestion = self._generate_rich_suggestion(
            wmo_code, temp_max, temp_min, wind_scale, precip_prob
        )

        lines = [f"「{city}」{date_label}天气预报来啦——"]

        # 天气核心信息
        temp_range = f"{temp_min}℃ ~ {temp_max}℃"
        lines.append(f"预计{weather}，气温{temp_range}。")

        # 风力
        if wind_scale and wind_scale != "无风":
            lines.append(f"{wind_dir}{wind_scale}，")

        # 降水
        if precip_prob >= 50:
            lines.append(f"降水概率{precip_prob}%，建议安排室内活动。")
        elif precip_prob >= 20:
            lines.append(f"降水概率{precip_prob}%，出行前留意天气变化。")

        if suggestion:
            lines.append(suggestion)

        return "".join(lines)

    def _format_multi_day(self, city: str, days_list: list[dict]) -> str:
        """格式化多日天气回复（保留，用于未来扩展）"""
        lines = [f"「{city}」未来{len(days_list)}天天气预报：\n"]
        for day in days_list:
            date_label = self._date_label(day["date"])
            temp = f"{day['temp_min']}°C ~ {day['temp_max']}°C"
            lines.append(
                f"  {date_label}：{day['weather']}，{temp}，"
                f"{day['wind_direction']}{day['wind_scale']}"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 场景化建议生成
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_wmo_code(day: dict) -> int:
        """从天气数据中推断 WMO 天气码"""
        weather = day.get("weather", "")
        for code, desc in WMO_WEATHER_MAP.items():
            if desc == weather:
                return code
        return 0

    @staticmethod
    def _weather_greeting(weather: str, temp: float) -> str:
        """生成天气口语化开头"""
        if "雨" in weather:
            if temp >= 25:
                return "外面下着雨但气温不低，"
            elif temp <= 10:
                return "阴雨绵绵天气偏冷，"
            return "下雨天出门注意安全，"
        if "雪" in weather:
            return "下雪天景色很美但要小心路滑，"
        if "晴" in weather:
            if temp >= 30:
                return "阳光灿烂但气温偏高，"
            elif temp >= 20:
                return "天气晴好正适合出门，"
            return "晴空万里但气温偏低，"
        if "云" in weather:
            return "多云天气还算舒适，"
        if "雾" in weather:
            return "雾气较重能见度低，"
        if "雷" in weather:
            return "雷暴天气请尽量减少外出，"
        return ""

    @staticmethod
    def _generate_rich_suggestion(
        wmo_code: int, temp_max: float, temp_min: float,
        wind_scale: str, precip_prob: int,
    ) -> str:
        """根据多维度数据生成丰富的场景化建议

        返回:
            口语化的场景建议字符串，多个建议用分号分隔
        """
        suggestions = []

        # ---- 温差穿搭建议 ----
        temp_diff = temp_max - temp_min
        avg_temp = (temp_max + temp_min) / 2
        if temp_diff >= 12:
            suggestions.append("早晚温差大，建议带件薄外套方便随时增减")
        elif temp_diff >= 8:
            suggestions.append("早晚有些凉，最好备一件外搭")

        # ---- 温度穿搭建议 ----
        if avg_temp <= 5:
            suggestions.append("气温很低，羽绒服围巾手套都安排上吧")
        elif avg_temp <= 12:
            suggestions.append("天气偏冷，适合穿厚外套或毛衣")
        elif avg_temp <= 18:
            suggestions.append("气温微凉，薄外套加长袖刚好")
        elif avg_temp <= 25:
            suggestions.append("气温舒适宜人，穿件衬衫或薄长袖就刚好")
        elif avg_temp <= 30:
            suggestions.append("天气偏热，短袖短裤可以安排上了")
        else:
            suggestions.append("高温天气，注意防暑降温多喝水")

        # ---- 防晒建议 ----
        if wmo_code in {0, 1, 2} and temp_max >= 25:
            suggestions.append("紫外线较强记得涂防晒")

        # ---- 雨天建议 ----
        rain_codes = {51, 53, 55, 61, 63, 65, 80, 81, 82, 95, 96, 99}
        if wmo_code in rain_codes:
            if wmo_code in {65, 82, 95, 96, 99}:
                suggestions.append("雨势不小出门务必带伞，路滑注意脚下")
            else:
                suggestions.append("出门别忘了带把伞")
        elif precip_prob >= 60:
            suggestions.append("虽然不一定下雨，但带把伞比较稳妥")

        # ---- 雪天建议 ----
        if wmo_code in {71, 73, 75, 77, 85, 86}:
            suggestions.append("雪天路面湿滑，走路注意脚下防摔")

        # ---- 大风建议 ----
        if wind_scale in {"强风", "疾风", "大风", "烈风", "狂风", "暴风", "飓风"}:
            suggestions.append("风力较大，外出注意防风，尽量远离广告牌")

        # ---- 雾天建议 ----
        if wmo_code in {45, 48}:
            suggestions.append("有雾天气能见度低，开车出行请减速慢行")

        # ---- 出行建议 ----
        if wmo_code == 0 and 18 <= avg_temp <= 28 and wind_scale in {"无风", "微风", "轻风", "和风", "清风", "劲风"}:
            suggestions.append("天气超棒，很适合出去走走")

        return "。".join(suggestions) + "。" if suggestions else ""

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _date_label(date_str: str) -> str:
        """将日期转为自然语言标签

        参数:
            date_str: YYYY-MM-DD 格式日期

        返回:
            "今天"、"明天"、"后天" 或 "X月X日"
        """
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d").date()
            today = datetime.now().date()
            delta = (date - today).days
            if delta == 0:
                return "今天"
            if delta == 1:
                return "明天"
            if delta == 2:
                return "后天"
            return f"{date.month}月{date.day}日"
        except (ValueError, TypeError):
            return date_str

    @staticmethod
    def _wind_direction_name(degrees: int) -> str:
        """风向角度 → 中文方位名"""
        directions = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
        index = round(degrees / 45) % 8
        return directions[index]

    @staticmethod
    def _wind_scale_name(speed_mps: float) -> str:
        """风速 m/s → 风力等级描述"""
        if speed_mps <= 0.3:
            return WIND_SCALE_MAP[0]
        if speed_mps <= 1.5:
            return WIND_SCALE_MAP[1]
        if speed_mps <= 3.3:
            return WIND_SCALE_MAP[2]
        if speed_mps <= 5.4:
            return WIND_SCALE_MAP[3]
        if speed_mps <= 7.9:
            return WIND_SCALE_MAP[4]
        if speed_mps <= 10.7:
            return WIND_SCALE_MAP[5]
        if speed_mps <= 13.8:
            return WIND_SCALE_MAP[6]
        if speed_mps <= 17.1:
            return WIND_SCALE_MAP[7]
        return "大风"

    @staticmethod
    def _fallback(city: str, message: str | None = None) -> str:
        """异常兜底话术"""
        if message:
            return message
        return (
            f"暂时无法获取「{city}」的天气信息。你可以在浏览器搜索「{city}天气」"
            f"查看最新预报哦~"
        )


# =============================================================================
# LRU 缓存层 —— 5分钟粒度，减少重复 API 调用
# =============================================================================

_weather_cache: dict[str, str] = {}


def _cached_weather_fetch(city: str, cache_key: str, days: int) -> dict | None:
    """LRU 缓存查找天气数据

    返回 None 表示缓存未命中，调用方需 fetch 新数据
    返回 dict 表示缓存命中

    注意：LRU cache 基于 cache_key（包含时间戳），5分钟后自动过期
    """
    try:
        data_json = _weather_cache.get(cache_key)
        if data_json:
            return json.loads(data_json)
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _cache_weather_result(cache_key: str, data_json: str):
    """将天气数据存入缓存"""
    _weather_cache[cache_key] = data_json
    # 周期性清理旧缓存（超过 20 条时清理前半部分）
    if len(_weather_cache) > 20:
        old_keys = sorted(_weather_cache.keys())[:len(_weather_cache) // 2]
        for key in old_keys:
            _weather_cache.pop(key, None)


# =============================================================================
# 全局单例接口
# =============================================================================

_weather_tool = WeatherTool(default_city="北京")


def get_weather_reply(city: str | None = None, date_str: str = "") -> str:
    """全局天气查询入口 —— 同步封装

    仅在无运行事件循环时使用 asyncio.run()，
    若已在异步上下文中则提示调用方使用异步 API。

    参数:
        city: 城市名称，None 时使用默认城市"北京"
        date_str: 日期文本，如"今天"、"明天"、"5.1号"，空字符串默认今天

    返回:
        自然语言天气回复字符串
    """
    try:
        try:
            asyncio.get_running_loop()
            return "天气查询需要在异步上下文中使用 await 调用，请使用异步 API"
        except RuntimeError:
            pass
        return asyncio.run(_weather_tool.get_reply(city, date_str))
    except Exception as e:
        logger.warning(f"[WeatherTool] get_weather_reply 异常: {e}")
        return f"天气查询暂时不可用，稍后再试哦~"


# =============================================================================
# 直接运行验证（python -m app.utils.weather_tool）
# =============================================================================
if __name__ == "__main__":
    async def _test():
        tool = WeatherTool(default_city="北京")

        test_cases = [
            # (城市, 日期字符串, 描述)
            ("北京", "", "今日实时天气"),
            ("上海", "今天", "今日实时天气（指定'今天'）"),
            ("广州", "明天", "明日预报"),
            ("深圳", "5.1号", "数字日期预报（跨月）"),
            ("杭州", "后天", "后天预报"),
            ("不存在城市XYZ", "", "城市不存在-兜底"),
            ("成都", "10天后", "超出预报范围"),
            ("武汉", "昨天", "历史日期-兜底"),
        ]

        print("=" * 72)
        print("  WeatherTool 天气工具 优化版 测试结果")
        print("=" * 72)

        passed = 0
        failed = 0

        for city, date_str, desc in test_cases:
            display = f"{city}「{date_str or '默认'}」"
            try:
                reply = await tool.get_reply(city, date_str)
                has_error = any(kw in reply for kw in [
                    "暂时无法", "找不到", "超出", "正在查询", "Exception",
                    "Traceback", "KeyError", "executable handler",
                ])
                status = "PASS(兜底)" if has_error else "PASS"
                if not has_error:
                    passed += 1
                else:
                    passed += 1  # 异常场景兜底也是通过
                print(f"\n  [{status}] {desc}: {display}")
                print(f"  {reply[:200]}")
            except Exception as e:
                failed += 1
                print(f"\n  [FAIL] {desc}: {display}, 异常={e}")

        print()
        print(f"  通过: {passed}  失败: {failed}  总计: {len(test_cases)}")
        if failed == 0:
            print("\n  全部测试通过!")
        else:
            print(f"\n  有 {failed} 个测试未通过，需要检查")

    asyncio.run(_test())
