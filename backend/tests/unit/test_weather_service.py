"""WeatherService（P0-4 天气多源 + 缓存）单元测试。

全部经 httpx.MockTransport 模拟上游，不打真实外网：
1. provider 链降级：wttr.in 失败 → Open-Meteo（geocoding + forecast）成功；
   两者都失败 → 兜底文案；
2. wttr.in 原有双段解析保留（紧凑格式成功 / 紧凑格式返回 HTML → j1 JSON）；
3. WMO weather_code → 中文描述映射；
4. LRU 缓存：TTL 内同城市连查只打一次外网、过期后重新拉取、LRU 容量淘汰。
"""
from __future__ import annotations

import time

import httpx
import pytest

from app.services.weather_service import WeatherService, wmo_code_to_desc

# ── MockTransport 构造 ──────────────────────────────────────────────────────

_WTTR_COMPACT = "Beijing: ☀️ +26.0°C, 湿度: 40%, 风力: 8 km/h"
_GEO_OK = {"results": [{"name": "北京", "latitude": 39.9042, "longitude": 116.4074}]}
_FORECAST_OK = {
    "current": {
        "temperature_2m": 25.3,
        "relative_humidity_2m": 60,
        "weather_code": 61,
        "wind_speed_10m": 12.3,
    }
}


def _make_transport(calls: list[str], spec: dict[str, object]) -> httpx.MockTransport:
    """按 host 路由的 MockTransport。

    spec 键：wttr_compact / wttr_json / geo / forecast，值为 httpx.Response 或 None
    （None 表示返回 500 模拟上游故障）。
    """

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        calls.append(url)
        host = request.url.host or ""
        if host == "wttr.in":
            key = "wttr_json" if "format=j1" in url else "wttr_compact"
            resp = spec.get(key)
            return resp if isinstance(resp, httpx.Response) else httpx.Response(500)
        if host == "geocoding-api.open-meteo.com":
            resp = spec.get("geo")
            return resp if isinstance(resp, httpx.Response) else httpx.Response(500)
        if host == "api.open-meteo.com":
            resp = spec.get("forecast")
            return resp if isinstance(resp, httpx.Response) else httpx.Response(500)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def _service(calls: list[str], **spec: object) -> WeatherService:
    return WeatherService(transport=_make_transport(calls, spec))


# ── provider 链 ─────────────────────────────────────────────────────────────

async def test_wttr_compact_success():
    """wttr.in 紧凑格式成功：保留原有输出形态，且不再请求其他源。"""
    calls: list[str] = []
    service = _service(calls, wttr_compact=httpx.Response(200, text=_WTTR_COMPACT))
    text = await service.query_weather("北京")
    assert text == "【北京 天气】" + _WTTR_COMPACT
    assert len(calls) == 1


async def test_wttr_compact_html_guard_falls_to_j1():
    """紧凑格式返回 HTML（404 页）→ 视为失败，降级到 wttr j1 JSON 解析。"""
    calls: list[str] = []
    service = _service(
        calls,
        wttr_compact=httpx.Response(200, text="<html><body>Not Found</body></html>"),
        wttr_json=httpx.Response(200, json={
            "current_condition": [{
                "temp_C": "26",
                "lang_zh": [{"value": "晴"}],
                "humidity": "40",
                "windspeedKmph": "8",
            }],
        }),
    )
    text = await service.query_weather("北京")
    assert "实时天气" in text and "晴" in text and "26°C" in text
    assert len(calls) == 2  # 紧凑 + j1，未走 Open-Meteo


async def test_wttr_fail_open_meteo_success():
    """wttr.in 全挂 → Open-Meteo 免 key 链成功（geocoding → forecast → 中文描述）。"""
    calls: list[str] = []
    service = _service(calls, geo=httpx.Response(200, json=_GEO_OK), forecast=httpx.Response(200, json=_FORECAST_OK))
    text = await service.query_weather("北京")

    assert "数据源: Open-Meteo" in text
    assert "小雨" in text                     # weather_code=61 的中文映射
    assert "25.3°C" in text
    assert "60%" in text
    assert "12.3" in text
    # 全部 4 次请求：wttr 紧凑 + wttr j1 + geocoding + forecast
    assert len(calls) == 4
    assert any("geocoding-api.open-meteo.com" in u for u in calls)
    assert any("api.open-meteo.com/v1/forecast" in u for u in calls)


async def test_both_fail_fallback_text():
    """wttr 与 Open-Meteo 都失败 → 兜底文案，且失败结果不写入缓存。"""
    calls: list[str] = []
    service = _service(calls)  # 全部 500
    text = await service.query_weather("北京")

    assert "暂未获取到城市「北京」的实时气象数据" in text
    assert service._cache == {}  # 失败不入缓存


async def test_geocode_no_results_fallback():
    """geocoding 解析不到城市（无 results）→ 兜底文案。"""
    calls: list[str] = []
    service = _service(calls, geo=httpx.Response(200, json={"results": []}))
    text = await service.query_weather("不存在城市xyz")
    assert "暂未获取到城市「不存在城市xyz」" in text


async def test_empty_city_prompt():
    """空城市名直接提示，不打外网。"""
    calls: list[str] = []
    service = _service(calls, wttr_compact=httpx.Response(200, text=_WTTR_COMPACT))
    text = await service.query_weather("  ")
    assert "缺少城市名称" in text
    assert calls == []


# ── WMO code 映射 ───────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (0, "晴"),
        (1, "基本晴"),
        (2, "局部多云"),
        (3, "阴"),
        (45, "雾"),
        (51, "轻毛毛雨"),
        (61, "小雨"),
        (65, "大雨"),
        (71, "小雪"),
        (75, "大雪"),
        (80, "小阵雨"),
        (86, "大阵雪"),
        (95, "雷阵雨"),
        (96, "雷阵雨伴小冰雹"),
        (99, "雷阵雨伴大冰雹"),
    ],
)
def test_wmo_code_mapping(code: int, expected: str):
    assert wmo_code_to_desc(code) == expected


def test_wmo_code_unknown_and_invalid():
    """未知编码与非法输入统一返回「未知天气」。"""
    assert wmo_code_to_desc(42) == "未知天气"
    assert wmo_code_to_desc(None) == "未知天气"
    assert wmo_code_to_desc("abc") == "未知天气"


# ── 缓存 ────────────────────────────────────────────────────────────────────

async def test_cache_hit_within_ttl_only_one_upstream_round():
    """TTL 内同城市连查只打一次外网（城市名大小写/首尾空白归一为同一缓存键）。"""
    calls: list[str] = []
    service = _service(calls, geo=httpx.Response(200, json=_GEO_OK), forecast=httpx.Response(200, json=_FORECAST_OK))

    text1 = await service.query_weather("Beijing")
    text2 = await service.query_weather("beijing")
    text3 = await service.query_weather("  BEIJING  ")  # strip + casefold 后同一缓存键

    assert text1 == text2 == text3
    assert len(calls) == 4  # 仅第一次查询产生的 4 次上游请求


async def test_cache_expiry_refetches():
    """超过 TTL 后重新拉取上游。"""
    calls: list[str] = []
    service = _service(calls, geo=httpx.Response(200, json=_GEO_OK), forecast=httpx.Response(200, json=_FORECAST_OK))

    await service.query_weather("北京")
    assert len(calls) == 4

    # 人为把缓存时间戳拨回 TTL 之前（确定性，不依赖 sleep 精度）
    key = service._normalize_city("北京")
    text, _ = service._cache[key]
    service._cache[key] = (text, time.time() - 1801)

    await service.query_weather("北京")
    assert len(calls) == 8  # 第二次查询重新打满上游


async def test_lru_eviction():
    """超过 LRU 容量淘汰最久未使用的条目。"""
    calls: list[str] = []
    service = WeatherService(max_entries=1, transport=_make_transport(
        calls,
        {"wttr_compact": httpx.Response(200, text=_WTTR_COMPACT)},
    ))

    await service.query_weather("北京")
    await service.query_weather("上海")
    assert set(service._cache) == {"上海"}


# ── 降级链补强（wttr.in 各失败形态） ────────────────────────────────────────

async def test_wttr_compact_http_500_falls_to_j1():
    """紧凑格式非 200 → 降级 j1 JSON（状态码分支，区别于 HTML 守卫）。"""
    calls: list[str] = []
    service = _service(
        calls,
        wttr_compact=httpx.Response(500),
        wttr_json=httpx.Response(200, json={
            "current_condition": [{
                "temp_C": "26",
                "lang_zh": [{"value": "晴"}],
                "humidity": "40",
                "windspeedKmph": "8",
            }],
        }),
    )
    text = await service.query_weather("北京")
    assert "实时天气" in text and "26°C" in text
    assert len(calls) == 2  # 紧凑 + j1，未走 Open-Meteo


async def test_wttr_compact_200_empty_body_falls_to_j1():
    """紧凑格式 200 但 body 去空白后为空 → 视为失败降级 j1（weatherDesc 英文回退）。"""
    calls: list[str] = []
    service = _service(
        calls,
        wttr_compact=httpx.Response(200, text="   \n"),
        wttr_json=httpx.Response(200, json={
            "current_condition": [{
                "temp_C": "18",
                "weatherDesc": [{"value": "Cloudy"}],
                "humidity": "70",
                "windspeedKmph": "5",
            }],
        }),
    )
    text = await service.query_weather("北京")
    assert "Cloudy" in text and "18°C" in text and "70%" in text and "5 km/h" in text
    assert len(calls) == 2


async def test_wttr_j1_defaults_when_fields_missing():
    """j1 响应缺 lang_zh/weatherDesc/temp 等字段时走默认值（晴 / --）。"""
    calls: list[str] = []
    service = _service(calls, wttr_json=httpx.Response(200, json={}))
    text = await service.query_weather("北京")
    assert "实时天气" in text
    assert "晴" in text       # weatherDesc 缺省 → "晴"
    assert "--°C" in text     # temp_C 缺省 → "--"
    assert len(calls) == 2    # j1 解析成功，未走 Open-Meteo


async def test_wttr_j1_malformed_json_falls_through_to_open_meteo():
    """j1 返回 200 但 body 非 JSON → 解析异常被吞，继续降级 Open-Meteo。"""
    calls: list[str] = []
    service = _service(
        calls,
        wttr_json=httpx.Response(200, text="<b>oops</b>"),
        geo=httpx.Response(200, json=_GEO_OK),
        forecast=httpx.Response(200, json=_FORECAST_OK),
    )
    text = await service.query_weather("北京")
    assert "数据源: Open-Meteo" in text
    assert len(calls) == 4  # wttr 紧凑 + wttr j1 + geocoding + forecast


async def test_wttr_j1_empty_current_condition_falls_through():
    """j1 current_condition 为空数组 → 取 [0] 越界异常被吞，降级 Open-Meteo。"""
    calls: list[str] = []
    service = _service(
        calls,
        wttr_json=httpx.Response(200, json={"current_condition": []}),
        geo=httpx.Response(200, json=_GEO_OK),
        forecast=httpx.Response(200, json=_FORECAST_OK),
    )
    text = await service.query_weather("北京")
    assert "数据源: Open-Meteo" in text
    assert len(calls) == 4


# ── 降级链补强（Open-Meteo 各形态） ─────────────────────────────────────────

async def test_open_meteo_forecast_http_error_fallback_not_cached():
    """geocoding 成功但 forecast 非 200 → 兜底文案，且失败不入缓存。"""
    calls: list[str] = []
    service = _service(calls, geo=httpx.Response(200, json=_GEO_OK), forecast=httpx.Response(503))
    text = await service.query_weather("北京")
    assert "暂未获取到城市「北京」的实时气象数据" in text
    assert service._cache == {}
    assert len(calls) == 4  # wttr×2 + geo + forecast（forecast 请求确实发出且 503）


async def test_open_meteo_missing_current_uses_placeholders_and_cached():
    """forecast 200 但无 current 字段 → 「未知天气」+ 占位符，仍作为成功结果入缓存。"""
    calls: list[str] = []
    service = _service(calls, geo=httpx.Response(200, json=_GEO_OK), forecast=httpx.Response(200, json={}))
    text = await service.query_weather("北京")
    assert "未知天气" in text
    assert "--" in text

    await service.query_weather("北京")
    assert len(calls) == 4  # 第二次命中缓存，不再打外网


async def test_open_meteo_prefers_geocoded_name_in_header():
    """输出头部使用 geocoding 返回的规范地名而非原始查询词。"""
    calls: list[str] = []
    geo = {"results": [{"name": "Beijing", "latitude": 39.9042, "longitude": 116.4074}]}
    service = _service(calls, geo=httpx.Response(200, json=geo), forecast=httpx.Response(200, json=_FORECAST_OK))
    text = await service.query_weather("bj")
    assert text.startswith("【Beijing 实时天气】（数据源: Open-Meteo）")


# ── WMO code 映射补强 ────────────────────────────────────────────────────────

def test_wmo_code_accepts_numeric_string_and_float():
    """数字字符串与浮点码可正常映射；空串等非法输入返回未知。"""
    assert wmo_code_to_desc("61") == "小雨"
    assert wmo_code_to_desc(61.0) == "小雨"
    assert wmo_code_to_desc("") == "未知天气"
    assert wmo_code_to_desc("6 1") == "未知天气"


# ── 缓存补强（命中刷新顺位 / 清空） ─────────────────────────────────────────

async def test_lru_hit_refreshes_recency():
    """命中刷新 LRU 顺位：热条目在容量超限时存活，冷条目先被淘汰。"""
    calls: list[str] = []
    service = WeatherService(
        max_entries=2,
        transport=_make_transport(calls, {"wttr_compact": httpx.Response(200, text=_WTTR_COMPACT)}),
    )

    await service.query_weather("北京")   # 写入 北京
    await service.query_weather("上海")   # 写入 上海
    await service.query_weather("北京")   # 缓存命中 → 北京移到队尾（最近使用）
    await service.query_weather("广州")   # 超限 → 淘汰最久未用的 上海

    assert set(service._cache) == {"北京", "广州"}


async def test_clear_cache_forces_refetch():
    """clear_cache 清空后同城市重新拉取上游。"""
    calls: list[str] = []
    service = _service(calls, wttr_compact=httpx.Response(200, text=_WTTR_COMPACT))

    await service.query_weather("北京")
    assert len(calls) == 1

    service.clear_cache()
    assert service._cache == {}

    await service.query_weather("北京")
    assert len(calls) == 2  # 清缓存后重新打上游
