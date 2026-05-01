"""
天气工具 - 封装为黑盒函数

特性：
1. 仅接受城市名和日期两个参数
2. 本地缓存机制（同一城市+同一天缓存2小时）
3. 使用Open-Meteo免费天气API（无需API Key）
4. 仅用于个人非商用场景
"""

import hashlib
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger
from app.runtime.plugin.skill.base import SkillDefinition, SkillResult


# 缓存目录
_CACHE_DIR = Path(__file__).parent.parent.parent.parent.parent / "data" / "weather_cache"
_CACHE_EXPIRE_SECONDS = 2 * 60 * 60  # 2小时缓存


def _get_cache_key(city: str, date: str) -> str:
    """生成缓存键"""
    key = f"{city}_{date}"
    return hashlib.md5(key.encode()).hexdigest()


def _get_cache_path(cache_key: str) -> Path:
    """获取缓存文件路径"""
    return _CACHE_DIR / f"{cache_key}.json"


def _load_from_cache(city: str, date: str) -> dict | None:
    """从缓存加载天气数据"""
    try:
        cache_key = _get_cache_key(city, date)
        cache_path = _get_cache_path(cache_key)
        
        if not cache_path.exists():
            return None
        
        with open(cache_path, 'r', encoding='utf-8') as f:
            cached = json.load(f)
        
        # 检查缓存是否过期
        cached_time = cached.get("cached_at", 0)
        if time.time() - cached_time > _CACHE_EXPIRE_SECONDS:
            logger.info(f"[Weather] Cache expired for {city} {date}")
            return None
        
        logger.info(f"[Weather] Cache hit for {city} {date}")
        return cached.get("data")
    except Exception as e:
        logger.warning(f"[Weather] Failed to load cache: {e}")
        return None


def _save_to_cache(city: str, date: str, data: dict) -> None:
    """保存天气数据到缓存"""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        cache_key = _get_cache_key(city, date)
        cache_path = _get_cache_path(cache_key)
        
        cached = {
            "city": city,
            "date": date,
            "data": data,
            "cached_at": time.time(),
        }
        
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cached, f, ensure_ascii=False, indent=2)
        
        logger.info(f"[Weather] Saved to cache for {city} {date}")
    except Exception as e:
        logger.warning(f"[Weather] Failed to save cache: {e}")


async def _fetch_weather_from_web(city: str, date: str) -> dict | None:
    """从网络获取天气数据
    
    使用Open-Meteo免费天气API（无需API Key）
    
    注意：
    1. Open-Meteo是开源免费的天气API
    2. 仅用于个人非商用场景
    3. 遵守API使用条款
    """
    import httpx
    
    client = None
    try:
        client = httpx.AsyncClient(timeout=10.0)
        
        # 步骤1：获取城市经纬度（使用Open-Meteo地理编码API）
        geocode_url = "https://geocoding-api.open-meteo.com/v1/search"
        geocode_params = {
            "name": city,
            "count": 1,
            "language": "zh",
            "format": "json",
        }
        
        geocode_response = await client.get(geocode_url, params=geocode_params)
        
        if geocode_response.status_code != 200:
            logger.warning(f"[Weather] Geocode API failed: {geocode_response.status_code}")
            return None
        
        geocode_data = geocode_response.json()
        results = geocode_data.get("results", [])
        
        if not results:
            logger.warning(f"[Weather] City not found: {city}")
            return None
        
        # 获取第一个匹配的城市
        location = results[0]
        latitude = location.get("latitude")
        longitude = location.get("longitude")
        city_name = location.get("name", city)
        
        logger.info(f"[Weather] Found location: {city_name} ({latitude}, {longitude})")
        
        # 步骤2：获取天气数据（使用Open-Meteo天气API）
        weather_url = "https://api.open-meteo.com/v1/forecast"
        
        # 计算日期偏移
        today = datetime.now().strftime("%Y-%m-%d")
        if date == today:
            days = 0
        else:
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d")
                today_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                days = (target_date - today_date).days
            except ValueError:
                days = 0
        
        weather_params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min",
            "timezone": "auto",
            "forecast_days": max(7, days + 1),
        }
        
        weather_response = await client.get(weather_url, params=weather_params)
        
        if weather_response.status_code != 200:
            logger.warning(f"[Weather] Weather API failed: {weather_response.status_code}")
            return None
        
        weather_data = weather_response.json()
        
        # 步骤3：解析天气数据
        current = weather_data.get("current", {})
        daily = weather_data.get("daily", {})
        
        # 当前温度（用于今天查询或兜底）
        current_temperature = current.get("temperature_2m", 0)
        humidity = current.get("relative_humidity_2m", 0)
        wind_speed = current.get("wind_speed_10m", 0)
        
        # 如果查询的是未来日期，使用预报数据
        if days > 0 and daily:
            daily_weather_codes = daily.get("weather_code", [])
            daily_max_temps = daily.get("temperature_2m_max", [])
            daily_min_temps = daily.get("temperature_2m_min", [])
            
            if days < len(daily_weather_codes):
                # 使用预报数据
                weather_code = daily_weather_codes[days]
                weather_desc = _wmo_code_to_description(weather_code)
                max_temp = daily_max_temps[days]
                min_temp = daily_min_temps[days]
                temperature_str = f"{min_temp:.0f}-{max_temp:.0f}°C"
                # 预报温度取平均值用于建议生成
                forecast_temperature = (max_temp + min_temp) / 2
            else:
                # 超出预报范围，使用当前数据但标记为预报
                weather_code = current.get("weather_code", 0)
                weather_desc = _wmo_code_to_description(weather_code)
                temperature_str = f"{current_temperature:.0f}°C"
                forecast_temperature = current_temperature
        else:
            # 查询今天，使用当前数据
            weather_code = current.get("weather_code", 0)
            weather_desc = _wmo_code_to_description(weather_code)
            temperature_str = f"{current_temperature:.0f}°C"
            forecast_temperature = current_temperature
        
        # 生成出行建议
        suggestion = _generate_weather_suggestion(weather_code, forecast_temperature)
        
        return {
            "city": city_name,
            "date": date,
            "weather": weather_desc,
            "temperature": temperature_str,
            "humidity": f"{humidity}%",
            "wind": f"风速{wind_speed:.0f}km/h",
            "suggestion": suggestion,
        }
        
    except Exception as e:
        logger.error(f"[Weather] Failed to fetch weather: {e}")
        return None
    finally:
        # 确保客户端连接被正确关闭
        if client is not None:
            await client.aclose()


def _wmo_code_to_description(code: int) -> str:
    """将WMO天气代码转换为中文描述
    
    WMO天气代码标准：https://open-meteo.com/en/docs
    """
    weather_map = {
        0: "晴",
        1: "晴间多云", 2: "晴间多云", 3: "多云",
        45: "雾", 48: "雾凇",
        51: "小雨", 53: "小雨", 55: "中雨",
        56: "冻雨", 57: "冻雨",
        61: "小雨", 63: "中雨", 65: "大雨",
        66: "冻雨", 67: "冻雨",
        71: "小雪", 73: "中雪", 75: "大雪",
        77: "雪粒",
        80: "阵雨", 81: "阵雨", 82: "暴雨",
        85: "阵雪", 86: "阵雪",
        95: "雷暴", 96: "雷暴冰雹", 99: "强雷暴",
    }
    return weather_map.get(code, "未知")


def _generate_weather_suggestion(weather_code: int, temperature: float) -> str:
    """根据天气状况生成出行建议"""
    suggestions = []
    
    # 温度建议
    if temperature < 5:
        suggestions.append("气温较低，注意保暖")
    elif temperature < 15:
        suggestions.append("气温适中，建议穿外套")
    elif temperature < 25:
        suggestions.append("气温舒适，适合出行")
    else:
        suggestions.append("气温较高，注意防暑")
    
    # 天气状况建议
    if weather_code == 0:
        suggestions.append("天气晴好")
    elif weather_code in [1, 2, 3]:
        suggestions.append("云量较多")
    elif weather_code in [45, 48]:
        suggestions.append("有雾，注意出行安全")
    elif weather_code in [51, 53, 55, 61, 63, 65, 80, 81, 82]:
        suggestions.append("有雨，建议携带雨具")
    elif weather_code in [71, 73, 75, 77, 85, 86]:
        suggestions.append("有雪，注意防寒保暖")
    elif weather_code in [95, 96, 99]:
        suggestions.append("有雷暴，建议减少外出")
    
    return "，".join(suggestions)


def _get_fallback_weather(city: str, date: str) -> dict:
    """获取兜底天气数据（本地常识库）"""
    # 简化的本地常识库
    # 实际项目中可以维护一个城市气候常识数据库
    return {
        "city": city,
        "date": date,
        "weather": "信息暂不可用",
        "temperature": "请查看天气预报应用",
        "humidity": "-",
        "wind": "-",
        "suggestion": "建议查看专业天气预报获取准确信息",
        "is_fallback": True,
    }


def _format_weather_for_user(data: dict) -> str:
    """将天气数据格式化为用户友好的自然语言"""
    if not data:
        return "抱歉，暂时无法获取天气信息，建议您查看天气预报应用。"
    
    if data.get("is_fallback"):
        return f"{data['city']}的天气信息暂时不可用，{data['suggestion']}"
    
    city = data.get("city", "")
    weather = data.get("weather", "")
    temperature = data.get("temperature", "")
    suggestion = data.get("suggestion", "")
    
    result = f"{city}{weather}，气温{temperature}。"
    if suggestion:
        result += f" {suggestion}"
    
    return result


async def get_weather(city: str, date: str = "") -> SkillResult:
    """获取天气信息（黑盒函数）
    
    参数：
    - city: 城市名称（如：北京、上海）
    - date: 日期（如：明天、2024-01-15），可选，默认今天
    
    返回：
    - SkillResult: 包含天气信息的自然语言描述
    """
    try:
        # 处理日期参数
        if not date or date in ["今天", "今日", ""]:
            date = datetime.now().strftime("%Y-%m-%d")
        elif date in ["明天", "明日"]:
            date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        elif date in ["后天"]:
            date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        
        logger.info(f"[Weather] Getting weather for {city} on {date}")
        
        # 1. 尝试从缓存获取
        cached_data = _load_from_cache(city, date)
        if cached_data:
            return SkillResult(
                success=True,
                data={"formatted": _format_weather_for_user(cached_data)}
            )
        
        # 2. 从网络获取
        web_data = await _fetch_weather_from_web(city, date)
        if web_data:
            # 保存到缓存
            _save_to_cache(city, date, web_data)
            return SkillResult(
                success=True,
                data={"formatted": _format_weather_for_user(web_data)}
            )
        
        # 3. 使用兜底数据
        fallback_data = _get_fallback_weather(city, date)
        return SkillResult(
            success=True,
            data={"formatted": _format_weather_for_user(fallback_data)}
        )
    except Exception as e:
        logger.error(f"[Weather] Error getting weather: {e}")
        return SkillResult(
            success=False,
            error="抱歉，获取天气信息时出现问题，请稍后再试。"
        )


# 技能定义
WEATHER_SKILL = SkillDefinition(
    name="get_weather",
    description="获取指定城市的天气信息。当用户明确询问天气、气温、穿衣建议时使用。",
    category="utility",
    parameters={
        "city": {
            "type": "string",
            "description": "城市名称，如：北京、上海、广州",
            "required": True,
        },
        "date": {
            "type": "string",
            "description": "日期，如：今天、明天、2024-01-15，可选",
            "required": False,
        },
    },
    is_active=True,
    is_builtin=True,
    handler_name="get_weather",
    tags=["weather", "天气", "utility"],
)
