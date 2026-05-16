"""
工具结果处理器 —— 在工具原始结果和大模型之间新增一层程序化过滤聚合

功能：
  对每个工具的原始返回结果进行过滤、聚合、精简，只保留核心有效信息，
  去除冗余 JSON 结构、无关字段、重复内容，降低 37% 以上的 token 消耗。

设计原则：
  1. 每个工具一个专属处理函数，针对性过滤无关字段
  2. 未定义专属处理器的工具走通用兜底，自动提取核心信息
  3. 绝对不丢失用户需要的核心内容，仅过滤冗余数据
  4. 处理异常时降级返回原始结果，不影响用户体验
  5. 纯函数设计，零副作用，极低延迟（毫秒级）
"""

import json
import re
from loguru import logger


# =============================================================================
# 核心接口：process_tool_result
# =============================================================================

def process_tool_result(tool_name: str, raw_result: str) -> str:
    """工具结果处理入口 —— 根据工具名分发到对应的处理函数

    流程：
      1. 在 TOOL_PROCESSORS 中查找该工具的专属处理器
      2. 找到 → 调用专属处理函数，返回精简后的结果
      3. 未找到 → 调用通用兜底处理器 _process_generic
      4. 异常 → 降级返回原始结果，确保对话不中断

    参数:
        tool_name: 工具名称，如 "get_weather"、"get_current_time"
        raw_result: 工具返回的原始结果文本（通常是 JSON 字符串或自然语言）

    返回:
        精简后的核心信息文本，供大模型生成最终回复

    用法:
        processed = process_tool_result("get_weather", '{"city":"北京",...}')
    """
    if not raw_result:
        return ""

    processor = TOOL_PROCESSORS.get(tool_name, _process_generic)
    try:
        processed = processor(raw_result)
        # 确保处理后的结果非空，空结果降级为原始结果
        if not processed or not processed.strip():
            logger.debug(f"[ResultProcessor] {tool_name} 处理结果为空，降级到原始结果")
            return raw_result
        return processed
    except Exception as e:
        logger.warning(f"[ResultProcessor] {tool_name} 处理异常，降级到原始结果: {e}")
        return raw_result


# =============================================================================
# 专属处理器
# =============================================================================

def _process_weather_result(raw: str) -> str:
    """天气结果处理器 —— 按日期类型智能精简

    原始结果包含（来自 weather_tool.py + Open-Meteo API）：
      实时天气：city, date, weather, temp_min/max, wind_scale/dir,
                humidity, precip_prob, formatted
      预报天气：city, date, weather, temp_min/max, wind_scale/dir,
                precip_prob, day_offset, formatted

    精简规则：
      实时天气：保留 formatted（含完整建议）或组装核心字段
      预报天气：保留 formatted（含日期 + 预报 + 建议）
      兜底话术：保留原样，确保不丢信息

    token 节省估算：原始 ~180 tokens → 处理后 ~45 tokens（节省 75%）
    """
    # 尝试解析 JSON
    data = _safe_parse_json(raw)
    if data is None:
        # 非 JSON 格式（如已经是自然语言或兜底话术），直接返回
        return _strip_json_wrapper(raw)

    # 优先取 formatted 字段（weather_tool 已生成口语化回复）
    formatted = data.get("formatted", "")
    if formatted:
        return formatted

    # 兜底：从原始字段组装精简结果
    city = data.get("city", "")
    fore_days = data.get("forecast_days", [])

    if fore_days:
        # 多日数据 → 只保留每天的核心字段
        parts = [f"{city}" if city else ""]
        for day in fore_days[:3]:  # 最多3天
            date = day.get("date", "")[-5:]  # MM-DD
            w = day.get("weather", "")
            t = f"{day.get('temp_min', '')}~{day.get('temp_max', '')}℃"
            parts.append(f"{date} {w} {t}")
        return "；".join(parts)
    else:
        # 单日数据
        weather = data.get("weather", "")
        temp_min = data.get("temp_min", "")
        temp_max = data.get("temp_max", "")
        temps = f"{temp_min}℃ ~ {temp_max}℃" if temp_min and temp_max else ""
        suggestion = data.get("suggestion", "")

        parts = []
        if city and weather:
            parts.append(f"{city}{weather}")
        if temps:
            parts.append(f"气温{temps}")
        if suggestion:
            parts.append(suggestion)

        return "，".join(parts) if parts else raw


def _process_time_result(raw: str) -> str:
    """时间结果处理器 —— 过滤多余时间戳和时区详情

    原始结果包含（来自 get_current_time）：
      datetime, date, time, weekday, year, month, day, hour, minute, second

    精简后只保留：
      日期、时间、星期

    处理逻辑：
      1. 解析 JSON 提取 date/time/weekday 三个核心字段
      2. 丢弃 year/month/day/hour/minute/second 等冗余子字段
      3. 组装成自然语言短句

    token 节省估算：原始 ~80 tokens → 处理后 ~25 tokens（节省 69%）
    """
    data = _safe_parse_json(raw)
    if data is None:
        return _strip_json_wrapper(raw)

    # 只提取用户需要的三个核心字段
    date = data.get("date", "")
    time_val = data.get("time", "")
    weekday = data.get("weekday", "")
    # 如果 date/time 为空，尝试从 datetime 或其它字段推断
    datetime_val = data.get("datetime", "")
    if not date and datetime_val:
        date = datetime_val[:10]
    if not time_val and datetime_val:
        time_val = datetime_val[11:19]

    # 组装自然语言
    parts = []
    if date:
        parts.append(f"日期：{date}")
    if weekday:
        parts.append(f"{weekday}")
    if time_val:
        parts.append(f"时间：{time_val}")

    return "，".join(parts) if parts else raw


def _process_search_result(raw: str) -> str:
    """搜索结果处理器 —— 截断过长结果，保留核心摘要

    原始结果可能包含大量检索文档内容，需要截断并提取核心信息。

    处理逻辑：
      1. 如果结果过长（>800 字符），截断并附加省略标记
      2. 去除 JSON 包装
      3. 保留前几条最相关的结果

    token 节省估算：原始 ~500 tokens → 处理后 ~200 tokens（节省 60%）
    """
    MAX_CHARS = 800
    text = _strip_json_wrapper(raw)

    if len(text) <= MAX_CHARS:
        return text

    # 截断到最大长度，在最近的句号或换行处断开
    truncated = text[:MAX_CHARS]
    # 尝试在最后一个完整句子处断开
    last_period = max(
        truncated.rfind("。"),
        truncated.rfind("\n"),
        truncated.rfind(". "),
    )
    if last_period > MAX_CHARS // 2:
        truncated = truncated[:last_period + 1]

    return f"{truncated}\n…（结果已截断，共 {len(text)} 字符）"


def _process_calculate_result(raw: str) -> str:
    """计算结果处理器 —— 只保留表达式和计算结果

    原始结果（JSON）：{"expression": "3+5", "result": 8}
    精简后：计算 3+5，结果 = 8

    处理逻辑：
      1. 解析 JSON 提取 expression 和 result
      2. 忽略所有元数据字段
      3. 组装成一行简洁结果

    token 节省估算：原始 ~40 tokens → 处理后 ~15 tokens（节省 63%）
    """
    data = _safe_parse_json(raw)
    if data is None:
        return _strip_json_wrapper(raw)

    expression = data.get("expression", "")
    result = data.get("result", "")
    if result is not None:
        return f"计算：{expression} = {result}"
    return raw


def _process_web_search_result(raw: str) -> str:
    """网页搜索结果处理器 —— 保留搜索查询和结果摘要

    处理逻辑：同 _process_search_result，针对网页搜索场景
    """
    return _process_search_result(raw)


def _process_transfer_result(raw: str) -> str:
    """Agent 转交结果处理器 —— 保留转交目标和任务描述

    处理逻辑：
      1. 解析 JSON 提取 transferred_to 和 task
      2. 过滤 agent_id 等内部元数据
    """
    data = _safe_parse_json(raw)
    if data is None:
        return _strip_json_wrapper(raw)

    agent = data.get("transferred_to", data.get("agent_name", ""))
    task = data.get("task", "")
    if agent and task:
        return f"已将任务「{task}」转交给 Agent「{agent}」"
    if agent:
        return f"已转交给 Agent「{agent}」"
    return _strip_json_wrapper(raw)


def _process_generic(raw: str) -> str:
    """通用兜底处理器 —— 针对未定义专属处理器的工具

    自动执行以下精简操作：
      1. 去除 JSON 外层包装结构
      2. 过滤 null/空字符串/空列表等空值字段
      3. 去除过度的缩进和格式化空白
      4. 保留核心文本内容

    处理逻辑：
      1. 尝试解析 JSON，提取所有非空字段的值
      2. 如果是纯文本，去除多余空白
      3. 过长文本截断处理
    """
    data = _safe_parse_json(raw)
    if data is None:
        # 非 JSON，做基本文本清理
        return _clean_text(raw)

    # 遍历 JSON 提取非空核心字段
    core_parts: list[str] = []
    for key, value in data.items():
        if value is None or value == "" or value == [] or value == {}:
            continue
        if isinstance(value, str):
            core_parts.append(value)
        elif isinstance(value, (int, float, bool)):
            core_parts.append(f"{key}: {value}")
        elif isinstance(value, list):
            # 列表只取前 3 项
            items = [str(v) for v in value[:3] if v is not None]
            if items:
                core_parts.append("，".join(items))
            if len(value) > 3:
                core_parts.append(f"（共 {len(value)} 项）")
        elif isinstance(value, dict):
            # 嵌套字典扁平化
            flat = _flatten_dict(value)
            if flat:
                core_parts.append(flat)

    result = "\n".join(core_parts) if core_parts else _strip_json_wrapper(raw)
    # 过长时截断
    if len(result) > 1000:
        return _process_search_result(result)
    return result


# =============================================================================
# 处理器注册表 —— 工具名 → 处理函数
# =============================================================================

TOOL_PROCESSORS: dict[str, callable] = {
    "get_weather": _process_weather_result,
    "get_current_time": _process_time_result,
    "search": _process_search_result,
    "calculate": _process_calculate_result,
    "web_search": _process_web_search_result,
    "transfer_to_agent": _process_transfer_result,
}


# =============================================================================
# 内部辅助函数
# =============================================================================

def _safe_parse_json(text: str) -> dict | None:
    """安全解析 JSON —— 失败返回 None，绝不抛异常"""
    if not text or not text.strip():
        return None
    text = text.strip()
    # 只处理以 { 或 [ 开头的内容
    if not (text.startswith("{") or text.startswith("[")):
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def _strip_json_wrapper(text: str) -> str:
    """去除 JSON 外层结构，提取纯文本内容

    如果 text 本身就是自然语言（不含 JSON 结构），原样返回。
    如果 text 是 JSON，尝试提取其中最有意义的字符串字段。
    """
    data = _safe_parse_json(text)
    if data is None:
        return text

    # 如果是字典，尝试取第一个有意义的值
    if isinstance(data, dict):
        for key in ["formatted", "content", "text", "summary", "result"]:
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val
        # 取第一个字符串值
        for val in data.values():
            if isinstance(val, str) and val.strip():
                return val
    elif isinstance(data, str):
        return data
    elif isinstance(data, (int, float, bool)):
        return str(data)
    elif isinstance(data, list):
        parts = [str(v) for v in data[:3] if v is not None]
        return "，".join(parts) if parts else text

    return text


def _flatten_dict(d: dict, max_depth: int = 2) -> str:
    """扁平化嵌套字典，提取非空值"""
    parts: list[str] = []
    for key, value in d.items():
        if value is None or value == "":
            continue
        if isinstance(value, dict) and max_depth > 0:
            inner = _flatten_dict(value, max_depth - 1)
            if inner:
                parts.append(f"{key}({inner})")
        elif isinstance(value, (str, int, float, bool)):
            parts.append(f"{key}: {value}")
    return "，".join(parts)


def _clean_text(text: str) -> str:
    """基本文本清理：去除多余空白和空行"""
    # 去除前导空白
    text = text.strip()
    # 压缩多个空行为单个空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 压缩多余空格（但不压缩中文之间的空格）
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text


# =============================================================================
# 对比验证 —— 展示原始 vs 精简效果（python -m app.utils.tool_result_processor）
# =============================================================================
if __name__ == "__main__":
    # 模拟工具原始返回结果
    mock_results = [
        # ----- 天气工具：模拟 Open-Meteo API 原始返回 -----
        (
            "get_weather",
            json.dumps({
                "city": "北京",
                "date": "2026-05-06",
                "forecast_days": [{
                    "date": "2026-05-06",
                    "weather": "晴",
                    "temp_min": 14.2,
                    "temp_max": 23.2,
                    "wind_scale": "大风",
                    "wind_direction": "北",
                    "humidity": "25%",
                    "precipitation_probability": 0,
                }],
            }, ensure_ascii=False),
        ),
        # ----- 天气工具（已格式化版本，weather_tool 口语化输出）-----
        (
            "get_weather",
            json.dumps({
                "formatted": "天气晴好正适合出门，「北京」现在是晴天，气温在14.2℃到23.2℃之间。当前北大风，体感温度会偏低一些。早晚有些凉，最好备一件外搭。气温舒适宜人，穿件衬衫或薄长袖就刚好。风力较大，外出注意防风，尽量远离广告牌。"
            }, ensure_ascii=False),
        ),
        # ----- 天气工具（预报格式）-----
        (
            "get_weather",
            json.dumps({
                "formatted": "「广州」明天天气预报来啦——预计小雨，气温23.1℃ ~ 28.8℃。东北清风，降水概率94%，建议安排室内活动。出门别忘了带把伞。"
            }, ensure_ascii=False),
        ),
        # ----- 时间工具：模拟 get_current_time 原始返回 -----
        (
            "get_current_time",
            json.dumps({
                "datetime": "2026-05-03 15:30:00",
                "date": "2026-05-03",
                "time": "15:30:00",
                "weekday": "星期一",
                "year": 2026,
                "month": 5,
                "day": 3,
                "hour": 15,
                "minute": 30,
                "second": 0,
            }, ensure_ascii=False),
        ),
        # ----- 计算工具 -----
        (
            "calculate",
            json.dumps({"expression": "165 * 38", "result": 6270}, ensure_ascii=False),
        ),
        # ----- 搜索工具（模拟长结果）-----
        (
            "search",
            "检索到以下内容：消防工程师考试2026年报名时间为6月1日至6月30日，考试科目包括消防安全技术实务、消防安全技术综合能力、消防安全案例分析三门。"
            + "报名条件要求大专以上学历，从事消防工作满6年。考试费用每科65元。"
            + "（此段为冗余扩展内容，用于测试搜索结果的截断处理效果，正常情况下大模型不需要看到这么长的原始结果文本，" * 3
            + "实际场景中原始搜索返回可能包含数千字符，通过处理器截断后仅保留核心信息）",
        ),
        # ----- Agent 转交 -----
        (
            "transfer_to_agent",
            json.dumps({
                "transferred_to": "消防专家Agent",
                "task": "解答关于消防通道设计的规范要求",
                "agent_id": "agent-001",
            }, ensure_ascii=False),
        ),
        # ----- 未注册工具（走通用兜底）-----
        (
            "unknown_tool",
            json.dumps({
                "status": "ok",
                "data": "操作成功",
                "error": None,
                "timestamp": "2026-05-03T15:30:00Z",
                "trace_id": "",
            }, ensure_ascii=False),
        ),
    ]

    print("=" * 80)
    print("  工具结果处理器 —— 原始 vs 精简 对比验证")
    print("=" * 80)

    total_raw_chars = 0
    total_processed_chars = 0

    for tool_name, raw_result in mock_results:
        processed = process_tool_result(tool_name, raw_result)
        total_raw_chars += len(raw_result)
        total_processed_chars += len(processed)

        raw_preview = raw_result[:120] + "…" if len(raw_result) > 120 else raw_result
        processed_preview = processed[:120] + "…" if len(processed) > 120 else processed

        print(f"\n  ┌─ 工具: {tool_name}")
        print(f"  ├─ 原始 ({len(raw_result)} 字符): {raw_preview}")
        print(f"  └─ 精简 ({len(processed)} 字符): {processed_preview}")

    # 汇总统计
    print()
    print("=" * 80)
    print("  Token 消耗对比汇总")
    print("=" * 80)
    # 中文约 1 token ≈ 1.5 字符
    raw_tokens_est = total_raw_chars // 2
    processed_tokens_est = total_processed_chars // 2
    savings = raw_tokens_est - processed_tokens_est
    savings_pct = (savings / raw_tokens_est * 100) if raw_tokens_est > 0 else 0

    print(f"  原始总字符数:   {total_raw_chars} 字符")
    print(f"  精简后字符数:   {total_processed_chars} 字符")
    print(f"  估算原始 tokens: ~{raw_tokens_est}")
    print(f"  估算精简 tokens: ~{processed_tokens_est}")
    print(f"  节省 tokens:     ~{savings}")
    print(f"  节省比例:        {savings_pct:.1f}%")
    print()
    print("  " + ("=" * 76))

    if savings_pct >= 37:
        print(f"  [PASS] Token 节省比例 {savings_pct:.1f}% >= 37%，目标达成")
    else:
        print(f"  [WARN] Token 节省比例 {savings_pct:.1f}% < 37%，可进一步优化")
