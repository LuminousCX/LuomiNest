"""
本地时间工具 - 纯本地时间/日期/星期查询模块

功能：
  提供毫秒级的时间/日期/星期自然语言回复，纯本地计算，零网络依赖。
  支持多种查询类型：time / date / week / date_offset / week_offset /
  lunar / holiday / timezone / all

核心能力：
  - 口语化时间格式化：零X分、整点简化、12小时制+六段划分
  - 多轮对话追踪：1分钟/5分钟重复查询适配不同话术
  - 六段场景适配：凌晨/早上/上午/中午/下午/晚上/深夜
  - 工作日/周末/节假日自动识别+个性化问候
  - 情绪急迫语境识别：安抚+精准报时话术
  - 记忆系统联动：时区/所在地/职业/日程/生日/作息/偏好
  - 跨工具联动：天气数据/行程计划/时差提示
  - 多Agent风格：通用/闲聊/办公/旅游/创作 五种风格
  - 三级兜底：个性化→通用友好→极简报时→硬编码安全兜底

设计原则：
  1. @lru_cache 实现1分钟缓存，同一分钟内重复查询零开销
  2. 所有规则/模板/时段/风格外提为可配置常量，修改无需动核心代码
  3. 回复自然口语化，逐场景精细打磨，彻底去除 AI 感
  4. 全局单例模式，避免重复实例化
  5. 仅依赖 Python 标准库，零外部依赖
"""

import re
import time as _time_module
from datetime import datetime, timedelta, date
from functools import lru_cache
from typing import Optional
from zoneinfo import ZoneInfo, available_timezones


# =============================================================================
# 星期映射表：将 Python 星期数字转为中文
# =============================================================================
_WEEKDAY_NAMES = {
    0: "星期一",
    1: "星期二",
    2: "星期三",
    3: "星期四",
    4: "星期五",
    5: "星期六",
    6: "星期日",
}

_WEEKDAY_NAMES_SHORT = {
    0: "周一",
    1: "周二",
    2: "周三",
    3: "周四",
    4: "周五",
    5: "周六",
    6: "周日",
}

# 周末集合：用于判断是否附加周末提示
_WEEKEND_DAYS = {5, 6}

# 中文数字映射
_CN_NUM = {
    "零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}

# 星期偏移中文映射
_WEEKDAY_OFFSET_CN = {
    "周一": 0, "周二": 1, "周三": 2, "周四": 3,
    "周五": 4, "周六": 5, "周日": 6,
}

# =============================================================================
# 农历数据（2025-2030）
# 格式: (公历(年,月,日), 农历(年,月,日,闰月标识))
# 数据来源：标准农历推算
# =============================================================================

_LUNAR_YEAR_NAMES = {
    2025: "乙巳", 2026: "丙午", 2027: "丁未",
    2028: "戊申", 2029: "己酉", 2030: "庚戌",
}

_LUNAR_MONTH_NAMES = [
    "", "正月", "二月", "三月", "四月", "五月", "六月",
    "七月", "八月", "九月", "十月", "冬月", "腊月",
]

_LUNAR_DAY_NAMES = [
    "", "初一", "初二", "初三", "初四", "初五", "初六", "初七", "初八", "初九", "初十",
    "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十",
    "廿一", "廿二", "廿三", "廿四", "廿五", "廿六", "廿七", "廿八", "廿九", "三十",
]

# 农历每月初一对应的公历日期（2025-2028）
# 格式: (公历年, 公历月, 公历日, 农历年, 农历月, 是否闰月)
_LUNAR_MONTH_STARTS = [
    # 2025 乙巳年
    (2025, 1, 29, 2025, 1, False),
    (2025, 2, 28, 2025, 2, False),
    (2025, 3, 29, 2025, 3, False),
    (2025, 4, 28, 2025, 4, False),
    (2025, 5, 27, 2025, 5, False),
    (2025, 6, 26, 2025, 6, False),
    (2025, 7, 25, 2025, 6, True),   # 闰六月
    (2025, 8, 23, 2025, 7, False),
    (2025, 9, 22, 2025, 8, False),
    (2025, 10, 21, 2025, 9, False),
    (2025, 11, 20, 2025, 10, False),
    (2025, 12, 19, 2025, 11, False),
    # 2026 丙午年 — 2026年春节是2月17日
    (2026, 1, 18, 2025, 12, False),  # 农历2025腊月初一
    (2026, 2, 17, 2026, 1, False),   # 正月初一（春节）
    (2026, 3, 19, 2026, 2, False),
    (2026, 4, 17, 2026, 3, False),
    (2026, 5, 16, 2026, 4, False),
    (2026, 6, 15, 2026, 5, False),
    (2026, 7, 14, 2026, 6, False),
    (2026, 8, 13, 2026, 7, False),
    (2026, 9, 11, 2026, 8, False),
    (2026, 10, 11, 2026, 9, False),
    (2026, 11, 9, 2026, 10, False),
    (2026, 12, 8, 2026, 11, False),
    # 2027 丁未年 — 2027年春节是2月6日
    (2027, 1, 6, 2026, 12, False),   # 农历2026腊月初一
    (2027, 2, 6, 2027, 1, False),    # 正月初一（春节）
    (2027, 3, 7, 2027, 2, False),
    (2027, 4, 5, 2027, 3, False),
    (2027, 5, 5, 2027, 4, False),
    (2027, 6, 4, 2027, 5, False),
    (2027, 7, 3, 2027, 5, True),     # 闰五月
    (2027, 8, 2, 2027, 6, False),
    (2027, 8, 31, 2027, 7, False),
    (2027, 9, 30, 2027, 8, False),
    (2027, 10, 29, 2027, 9, False),
    (2027, 11, 28, 2027, 10, False),
    (2027, 12, 27, 2027, 11, False),
    # 2028 戊申年 — 2028年春节是1月26日
    (2028, 1, 26, 2028, 1, False),   # 正月初一（春节）
    (2028, 2, 24, 2028, 2, False),
    (2028, 3, 25, 2028, 3, False),
    (2028, 4, 24, 2028, 4, False),
    (2028, 5, 23, 2028, 5, False),
    (2028, 6, 22, 2028, 6, False),
    (2028, 7, 21, 2028, 7, False),
    (2028, 8, 20, 2028, 8, False),
    (2028, 9, 18, 2028, 9, False),
    (2028, 10, 17, 2028, 10, False),
    (2028, 11, 16, 2028, 11, False),
    (2028, 12, 15, 2028, 12, False),
]

# 法定节假日（公历固定日期 + 农历浮动日期）
# 格式: (月, 日, 名称, 是否公历)
_FIXED_HOLIDAYS = [
    (1, 1, "元旦", True),
    (2, 14, "情人节", True),
    (3, 8, "妇女节", True),
    (3, 12, "植树节", True),
    (4, 1, "愚人节", True),
    (5, 1, "劳动节", True),
    (5, 4, "青年节", True),
    (6, 1, "儿童节", True),
    (7, 1, "建党节", True),
    (8, 1, "建军节", True),
    (9, 10, "教师节", True),
    (10, 1, "国庆节", True),
    (10, 31, "万圣节", True),
    (12, 25, "圣诞节", True),
]

# =============================================================================
# 查询类型识别正则（全部保留，不变）
# =============================================================================

_PATTERN_TIME = re.compile(
    r"(几点|几时|什么时间|啥时间|现在时间|当前时间|看时间|报时|time|clock)",
)

_PATTERN_DATE = re.compile(
    r"(几号|几月几|几月几日|什么日期|今天日期|当前日期|今天几|啥日期|"
    r"年月日|日历|几月份|几月$)",
)

_PATTERN_WEEKDAY = re.compile(
    r"(星期几|周几|礼拜几|今天周|明天周|后天周|昨天周|周五|周六|周日|"
    r"周一|周二|周三|周四|星期[一二三四五六日天]|周[一二三四五六日天])",
)

_PATTERN_DATE_OFFSET = re.compile(
    r"(明天|今日|今日|后天|大后天|昨天|前天|大前天|"
    r"\d+天后|\d+天前|[一二三四五六七八九十]+天后|[一二三四五六七八九十]+天前|"
    r"下周[一二三四五六日天]|下下周|上周[一二三四五六日天])",
)

_PATTERN_LUNAR = re.compile(
    r"(农历|阴历|初一|十五|元宵|端午|中秋|重阳|除夕|腊月|大年)",
)

_PATTERN_HOLIDAY = re.compile(
    r"(什么日子|什么节日|什么节|法定节假日|节假日|有没有假|放不放假|"
    r"过节|节日|庆祝|纪念日)",
)

_PATTERN_TIMEZONE = re.compile(
    r"[的地]时间"
    r"|"
    r"时间(?!点|分|钟|段|候|长|差)"
    r"|"
    r"时区|UTC|GMT|时差",
)

# 急迫语境关键词：用于安抚+精准报时
_PATTERN_URGENT = re.compile(
    r"(来不及|快迟到|赶时间|赶车|赶飞机|赶高铁|赶火车|"
    r"要出发|马上|快点|赶紧|加速|匆忙|急着)"
)

# 时间偏移关键词：X小时后、X分钟前、X天后等
_PATTERN_TIME_OFFSET = re.compile(
    r"(?P<num>\d+|[一二三四五六七八九十]+)"
    r"(?P<unit>个?(?:小时|分钟|天|钟头))"
    r"(?P<dir>[后前]|之后|之前|了)"
)


# =============================================================================
# 时间偏移解析 —— 支持口语化时间偏移查询
# =============================================================================

def parse_time_offset(user_message: str) -> dict:
    """解析用户输入的口语化时间偏移指令

    支持格式：
      - X小时后、X个小时后、X分钟后、X天后
      - X小时前、X分钟前、X天前
      - X小时之后、X分钟之前
      - 中文数字：一小时后、三十分钟后

    参数:
        user_message: 用户原始消息

    返回:
        字典：
          - "value": 偏移数值（int）
          - "unit": 单位（"小时"/"分钟"/"天"）
          - "direction": 方向（"后"/"前"）
          - "valid": 是否解析成功
          - "error": 解析失败时的提示信息
    """
    if not user_message:
        return {"valid": False, "error": "消息为空"}

    cleaned = _clean_input(user_message)

    # 匹配偏移模式
    match = _PATTERN_TIME_OFFSET.search(cleaned)
    if not match:
        return {"valid": False, "error": "未识别到时间偏移指令"}

    num_raw = match.group("num")
    unit_raw = match.group("unit")
    dir_raw = match.group("dir")

    # 解析数值
    if num_raw.isdigit():
        value = int(num_raw)
    else:
        value = 0
        for ch in num_raw:
            if ch in _CN_NUM:
                value += _CN_NUM[ch]

    if value <= 0:
        return {"valid": False, "error": "偏移数值必须大于0"}

    # 解析单位
    unit = "小时"
    if "分钟" in unit_raw or "分" in unit_raw:
        unit = "分钟"
    elif "天" in unit_raw or "日" in unit_raw:
        unit = "天"
    elif "小时" in unit_raw or "钟头" in unit_raw or "时" in unit_raw:
        unit = "小时"

    # 解析方向
    direction = "后"
    if "前" in dir_raw:
        direction = "前"

    return {
        "valid": True,
        "value": value,
        "unit": unit,
        "direction": direction,
        "error": None,
    }


def calc_offset_time(offset_info: dict, timezone: str = "Asia/Shanghai") -> str:
    """根据偏移参数计算目标时间，返回自然语言结果

    参数:
        offset_info: parse_time_offset 返回的字典
        timezone:    时区标识符

    返回:
        自然语言时间回复，如"1小时后是上午11点35分哦"

    异常安全：
        偏移信息无效时，自动降级为当前时间查询
    """
    if not offset_info.get("valid"):
        # 降级为当前时间
        now = datetime.now(ZoneInfo(timezone))
        _, _, time_str = TimeTool._format_time_oral(now.hour, now.minute)
        return f"现在是{time_str}"

    value = offset_info["value"]
    unit = offset_info["unit"]
    direction = offset_info["direction"]

    # 计算目标时间
    now = datetime.now(ZoneInfo(timezone))
    if direction == "后":
        if unit == "小时":
            target = now + timedelta(hours=value)
        elif unit == "分钟":
            target = now + timedelta(minutes=value)
        else:  # 天
            target = now + timedelta(days=value)
    else:  # 前
        if unit == "小时":
            target = now - timedelta(hours=value)
        elif unit == "分钟":
            target = now - timedelta(minutes=value)
        else:  # 天
            target = now - timedelta(days=value)

    # 格式化目标时间
    _, _, time_str = TimeTool._format_time_oral(target.hour, target.minute)

    # 判断日期是否变化
    date_changed = target.date() != now.date()
    day_offset = (target.date() - now.date()).days

    if date_changed:
        if day_offset == 1:
            return f"{value}{unit}{direction}是明天{time_str}"
        elif day_offset == -1:
            return f"{value}{unit}{direction}是昨天{time_str}"
        elif day_offset > 0:
            return f"{value}{unit}{direction}是{day_offset}天后{time_str}"
        else:
            return f"{value}{unit}{direction}是{abs(day_offset)}天前{time_str}"

    return f"{value}{unit}{direction}是{time_str}"


def _is_time_offset_query(cleaned: str) -> bool:
    """判断用户消息是否为时间偏移查询"""
    return bool(_PATTERN_TIME_OFFSET.search(cleaned))


def _clean_input(text: str) -> str:
    """清洗输入文本，去除空格和中英文问号"""
    cleaned = text.replace(" ", "").replace("　", "")
    cleaned = cleaned.replace("？", "").replace("?", "")
    return cleaned


def _detect_query_type(cleaned: str) -> str:
    """根据清洗后的用户消息，识别时间查询的子类型

    返回:
        "time"          - 当前时间
        "date"          - 当前日期
        "week"          - 星期几
        "date_offset"   - 偏移日期（明天几号）
        "week_offset"   - 偏移星期（后天周几）
        "lunar"         - 农历日期
        "holiday"       - 节假日
        "timezone"      - 指定时区时间
        "all"           - 综合信息
    """
    has_time = bool(_PATTERN_TIME.search(cleaned))
    has_date = bool(_PATTERN_DATE.search(cleaned))
    has_week = bool(_PATTERN_WEEKDAY.search(cleaned))
    has_offset = bool(_PATTERN_DATE_OFFSET.search(cleaned))
    has_lunar = bool(_PATTERN_LUNAR.search(cleaned))
    has_holiday = bool(_PATTERN_HOLIDAY.search(cleaned))
    has_timezone = bool(_PATTERN_TIMEZONE.search(cleaned))

    if has_lunar:
        return "lunar"
    if has_holiday:
        return "holiday"
    if has_timezone and has_time:
        return "timezone"
    if has_offset and (has_date or has_week):
        if has_date:
            return "date_offset"
        return "week_offset"
    if has_offset:
        return "date_offset"

    match_count = sum([has_time, has_date, has_week])
    if match_count == 1:
        if has_time:
            return "time"
        if has_date:
            return "date"
        if has_week:
            return "week"

    return "all"


def _extract_day_offset(cleaned: str, now: datetime | None = None) -> int:
    """从用户消息中提取日期偏移量

    支持格式：
      "明天"=1, "后天"=2, "大后天"=3,
      "昨天"=-1, "前天"=-2,
      "下周一"=next_monday, "3天后"=3

    参数:
        cleaned: 清洗后的用户消息
        now: 当前时间（时区感知），None 时使用 datetime.now()

    返回:
        距离今天的偏移天数，无法提取时返回 0
    """
    if "昨天" in cleaned:
        return -1
    if "前天" in cleaned:
        return -2
    if "大前天" in cleaned:
        return -3
    if "明天" in cleaned or "明日" in cleaned:
        return 1
    if "后天" in cleaned:
        return 2
    if "大后天" in cleaned:
        return 3

    offset_match = re.search(r"(\d+|[一二三四五六七八九十]+)\s*天?(后|前)", cleaned)
    if offset_match:
        raw = offset_match.group(1)
        direction = offset_match.group(2)
        if raw.isdigit():
            num = int(raw)
        else:
            num = 0
            for ch in raw:
                if ch in _CN_NUM:
                    num += _CN_NUM[ch]
        if direction == "前":
            return -num
        return num

    for week_word, weekday_idx in _WEEKDAY_OFFSET_CN.items():
        if week_word in cleaned:
            today_weekday = (now or datetime.now()).weekday()
            days_until = (weekday_idx - today_weekday) % 7
            is_next = "下" in cleaned or "下周" in cleaned or "下礼拜" in cleaned
            if is_next and days_until == 0:
                days_until = 7
            return days_until

    return 0


def _solar_to_lunar(solar: date) -> dict:
    """公历转农历"""
    solar_tuple = (solar.year, solar.month, solar.day)
    prev_start = None
    for start in _LUNAR_MONTH_STARTS:
        start_solar = (start[0], start[1], start[2])
        if start_solar <= solar_tuple:
            prev_start = start
        else:
            break
    if prev_start is None:
        return {"found": False}

    prev_date = date(prev_start[0], prev_start[1], prev_start[2])
    delta_days = (solar - prev_date).days
    lunar_year = prev_start[3]
    lunar_month = prev_start[4]
    is_leap = prev_start[5] if len(prev_start) > 5 else False
    lunar_day = delta_days + 1

    year_name = _LUNAR_YEAR_NAMES.get(lunar_year, "")
    month_name = (_LUNAR_MONTH_NAMES[lunar_month]
                  if 1 <= lunar_month <= 12 else f"{lunar_month}月")
    if is_leap:
        month_name = "闰" + month_name
    day_name = (_LUNAR_DAY_NAMES[lunar_day]
                if 1 <= lunar_day < len(_LUNAR_DAY_NAMES) else f"{lunar_day}日")
    spring_date = _get_spring_festival_date(lunar_year)

    return {
        "found": True,
        "lunar_year": lunar_year,
        "lunar_month": lunar_month,
        "lunar_day": lunar_day,
        "is_leap": is_leap,
        "year_name": year_name,
        "month_name": month_name,
        "day_name": day_name,
        "spring_date": spring_date,
    }


def _get_spring_festival_date(lunar_year: int) -> date | None:
    """获取指定农历年春节（正月初一）的公历日期"""
    for start in _LUNAR_MONTH_STARTS:
        if start[3] == lunar_year and start[4] == 1 and (
                len(start) <= 5 or not start[5]):
            return date(start[0], start[1], start[2])
    return None


def _get_holiday_info(solar: date, lunar_info: dict) -> str:
    """获取法定节假日信息，无节假日返回空字符串"""
    holidays = []
    month, day = solar.month, solar.day
    for (m, d, name, _) in _FIXED_HOLIDAYS:
        if m == month and d == day:
            holidays.append(name)

    if lunar_info.get("found"):
        lm = lunar_info["lunar_month"]
        ld = lunar_info["lunar_day"]
        if lm == 1 and ld == 1:
            holidays.append("春节")
        if lm == 1 and ld == 15:
            holidays.append("元宵节")
        if month == 4 and day in (4, 5):
            holidays.append("清明节")
        if lm == 5 and ld == 5:
            holidays.append("端午节")
        if lm == 7 and ld == 7:
            holidays.append("七夕节")
        if lm == 8 and ld == 15:
            holidays.append("中秋节")
        if lm == 9 and ld == 9:
            holidays.append("重阳节")
        if lm == 12 and ld == 30:
            holidays.append("除夕")
        elif lm == 12 and ld == 29:
            for start in _LUNAR_MONTH_STARTS:
                if start[3] == lunar_info["lunar_year"] and start[4] == 12:
                    next_idx = _LUNAR_MONTH_STARTS.index(start) + 1
                    if next_idx < len(_LUNAR_MONTH_STARTS):
                        nxt = _LUNAR_MONTH_STARTS[next_idx]
                        cur = date(start[0], start[1], start[2])
                        nxt_d = date(nxt[0], nxt[1], nxt[2])
                        if (nxt_d - cur).days == 29:
                            holidays.append("除夕")
    return "、".join(holidays)


def _get_holiday_message(holiday_name: str) -> str:
    """根据节假日名称生成祝福语"""
    holiday_messages = {
        "元旦": "祝你元旦快乐，新年新气象！",
        "春节": "祝你春节快乐，阖家幸福，万事如意！",
        "元宵节": "元宵节快乐，记得吃汤圆哦~",
        "情人节": "情人节快乐！",
        "妇女节": "祝你节日快乐！",
        "植树节": "植树节，一起爱护地球吧~",
        "清明节": "清明时节雨纷纷，注意出行安全。",
        "劳动节": "劳动节快乐，辛苦了！",
        "青年节": "青年节快乐，保持年轻心态！",
        "端午节": "端午节快乐，记得吃粽子~",
        "儿童节": "儿童节快乐，保持童心！",
        "七夕节": "七夕节快乐！",
        "中秋节": "中秋节快乐，花好月圆人团圆！",
        "国庆节": "国庆节快乐！",
        "重阳节": "重阳节快乐，登高望远心情好~",
        "万圣节": "万圣节快乐~",
        "圣诞节": "圣诞节快乐！",
        "除夕": "除夕快乐，辞旧迎新！",
    }
    return holiday_messages.get(holiday_name, f"{holiday_name}快乐！")


# =============================================================================
# 时区名称映射 —— 常见城市到时区
# =============================================================================

_CITY_TIMEZONE_MAP = {
    "北京": "Asia/Shanghai", "上海": "Asia/Shanghai", "广州": "Asia/Shanghai",
    "深圳": "Asia/Shanghai", "杭州": "Asia/Shanghai", "成都": "Asia/Shanghai",
    "西安": "Asia/Shanghai", "重庆": "Asia/Shanghai", "武汉": "Asia/Shanghai",
    "南京": "Asia/Shanghai", "苏州": "Asia/Shanghai", "天津": "Asia/Shanghai",
    "香港": "Asia/Hong_Kong", "澳门": "Asia/Macau", "台北": "Asia/Taipei",
    "东京": "Asia/Tokyo", "大阪": "Asia/Tokyo", "北海道": "Asia/Tokyo",
    "首尔": "Asia/Seoul", "釜山": "Asia/Seoul",
    "新加坡": "Asia/Singapore", "曼谷": "Asia/Bangkok",
    "吉隆坡": "Asia/Kuala_Lumpur",
    "雅加达": "Asia/Jakarta", "马尼拉": "Asia/Manila",
    "河内": "Asia/Ho_Chi_Minh",
    "新德里": "Asia/Kolkata", "孟买": "Asia/Kolkata",
    "科伦坡": "Asia/Colombo",
    "迪拜": "Asia/Dubai", "利雅得": "Asia/Riyadh",
    "德黑兰": "Asia/Tehran",
    "伦敦": "Europe/London", "巴黎": "Europe/Paris",
    "柏林": "Europe/Berlin",
    "罗马": "Europe/Rome", "马德里": "Europe/Madrid",
    "莫斯科": "Europe/Moscow",
    "阿姆斯特丹": "Europe/Amsterdam",
    "斯德哥尔摩": "Europe/Stockholm",
    "纽约": "America/New_York", "洛杉矶": "America/Los_Angeles",
    "芝加哥": "America/Chicago", "多伦多": "America/Toronto",
    "温哥华": "America/Vancouver", "旧金山": "America/Los_Angeles",
    "悉尼": "Australia/Sydney", "墨尔本": "Australia/Melbourne",
    "奥克兰": "Pacific/Auckland",
}

_TIMEZONE_KEYWORDS = {
    "东八区": "Asia/Shanghai", "北京时间": "Asia/Shanghai",
    "东京时间": "Asia/Tokyo", "日本时间": "Asia/Tokyo",
    "首尔时间": "Asia/Seoul", "韩国时间": "Asia/Seoul",
    "新加坡时间": "Asia/Singapore", "曼谷时间": "Asia/Bangkok",
    "伦敦时间": "Europe/London", "英国时间": "Europe/London",
    "巴黎时间": "Europe/Paris", "法国时间": "Europe/Paris",
    "纽约时间": "America/New_York", "美国东部时间": "America/New_York",
    "洛杉矶时间": "America/Los_Angeles", "美国西部时间": "America/Los_Angeles",
    "悉尼时间": "Australia/Sydney", "澳洲时间": "Australia/Sydney",
}


def _detect_timezone_from_message(cleaned: str) -> str | None:
    """从用户消息中提取时区信息"""
    for keyword, tz in _TIMEZONE_KEYWORDS.items():
        if keyword in cleaned:
            return tz
    for city, tz in _CITY_TIMEZONE_MAP.items():
        if city in cleaned:
            return tz
    return None


# =============================================================================
# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  可配置常量 — 时段划分 / 问候语 / Agent风格 / 多轮对话阈值              ║
# ║  修改这些常量即可调整回复风格，无需改核心代码                           ║
# ╚══════════════════════════════════════════════════════════════════════════╝
# =============================================================================

# ---- 时段划分（24小时制，左闭右开）----
# 通过 (开始小时, 结束小时, 时段名, 12小时制偏移, 问候前缀, 后缀提醒) 描述
_PERIODS = [
    # (start, end, name, display_offset, greetings_tuple, reminder)
    (0,  6,  "凌晨", 0,  ("夜深了，", "凌晨好，"),   "早点休息哦"),
    (6,  9,  "早上", 0,  ("早上好，", "早安，新的一天开始啦，"), ""),
    (9,  12, "上午", 0,  ("上午好，", ""),           ""),
    (12, 14, "中午", 12, ("中午好，", ""),           "别忘了按时吃饭~"),
    (14, 18, "下午", 12, ("下午好，", ""),           ""),
    (18, 22, "晚上", 12, ("晚上好，", "傍晚好，"),   ""),
    (22, 24, "深夜", 12, ("夜深了，", ""),           "早点休息哦"),
]

# ---- 多轮对话阈值（秒）----
_REPEAT_SAME_MINUTE = 60       # 1分钟内重复查询 → "还是XX时间哦"
_REPEAT_NEAR_MINUTE = 120      # 2分钟内重复查询 → "距离上次才过了X分钟"
_REPEAT_MAX_WINDOW = 180       # 超过3分钟视为正常查询（大于 NEAR 阈值）

# ---- 工作日/周末场景化后缀 ----
_WORKDAY_MOTIVATIONS = [
    "加油干，今天也是元气满满的一天！",
    "搬砖时间到，一起加油吧~",
    "新的一天，新的开始！",
    "认真工作的你最帅/最美！",
]

_WEEKEND_RELAXATIONS = [
    "周末愉快，好好享受休息时光~",
    "周末啦，今天有什么计划吗？",
    "周末是充电的好时机，放松一下吧~",
]

_FRIDAY_CELEBRATION = "明天就是周末啦，再坚持一下~"

# ---- 时段默认后缀池（每个时段都有，不再依赖reminder字段）----
# 格式: {时段名: [后缀1, 后缀2, ...]}
_PERIOD_DEFAULT_SUFFIXES = {
    "凌晨": [
        "早点休息，身体最重要",
        "熬夜伤身，快去睡吧",
        "这个点还没睡，是在加班吗？",
    ],
    "早上": [
        "新的一天开始了，精神点！",
        "早餐吃了吗？",
        "今天也要加油哦~",
    ],
    "上午": [
        "上午效率最高，抓紧干活！",
        "工作/学习顺利吗？",
        "记得适当休息，别一直盯着屏幕~",
    ],
    "中午": [
        "午饭吃了吗？",
        "午休一下，下午更有精神",
        "别吃太饱，容易犯困哈哈",
    ],
    "下午": [
        "下午容易犯困，来杯咖啡提提神？",
        "再坚持一下，很快就下班了",
        "工作/学习还顺利吗？",
    ],
    "晚上": [
        "晚饭吃了吗？",
        "晚上是属于自己的时间，好好放松",
        "今天过得怎么样？",
    ],
    "深夜": [
        "还不睡？明天还要早起呢",
        "熬夜对皮肤不好哦",
        "快去休息吧，晚安~",
    ],
}


def _get_period_default_suffix(hour: int, scene_ctx: dict) -> str:
    """根据当前时段返回默认场景化后缀

    参数:
        hour: 当前小时（0-23）
        scene_ctx: 场景上下文

    返回:
        随机选择的时段后缀，或空字符串
    """
    import random
    # 匹配当前时段
    period_name = "深夜"
    for (start, end, p_name, _, _, _) in _PERIODS:
        if start <= hour < end:
            period_name = p_name
            break

    # 根据用户作息偏好调整
    wake_time = scene_ctx.get("user_wake_time", "")
    sleep_time = scene_ctx.get("user_sleep_time", "")

    # 如果用户设置了起床时间，且当前接近起床时间，添加特殊提示
    if wake_time and period_name == "早上":
        try:
            wake_hour = int(wake_time.split(":")[0])
            if abs(hour - wake_hour) <= 1:
                return "该起床啦，别赖床哦~"
        except (ValueError, IndexError):
            pass

    # 如果用户设置了睡觉时间，且当前接近睡觉时间，添加特殊提示
    if sleep_time and period_name in ("晚上", "深夜"):
        try:
            sleep_hour = int(sleep_time.split(":")[0])
            if hour >= sleep_hour:
                return "该准备睡觉啦，晚安~"
        except (ValueError, IndexError):
            pass

    suffixes = _PERIOD_DEFAULT_SUFFIXES.get(period_name, [])
    if suffixes:
        return random.choice(suffixes)
    return ""


# ---- Agent 类型回复风格配置 ----
# 格式: {类型: {prefix: 前缀模板, suffix: 后缀模板, max_length: 最大字数, tone: 风格名}}
# 模板中 {time_str} 会被替换为实际时间
# 模板中 {greeting} 会被替换为时段问候
_AGENT_STYLES = {
    "通用": {   # general — 默认友好分时段
        "prefix": "{greeting}现在是{time_str}哦~",
        "suffix": "",
        "max_length": 60,
        "tone": "友好自然",
    },
    "闲聊": {   # casual — 轻松生活化+互动感
        "prefix": "{greeting}现在已经是{time_str}啦~",
        "suffix": "你在干嘛呢？",
        "max_length": 50,
        "tone": "轻松生活",
    },
    "办公": {   # office — 极简精准，无多余话术
        "prefix": "{time_str}",
        "suffix": "",
        "max_length": 20,
        "tone": "极简精准",
    },
    "旅游": {   # travel — 结合天气/行程/目的地
        "prefix": "{greeting}现在是{time_str}~",
        "suffix": "旅途愉快！",
        "max_length": 80,
        "tone": "旅行友好",
    },
    "创作": {   # creative — 文艺感表达
        "prefix": "{greeting}时光流转，已是{time_str}。",
        "suffix": "灵感来了吗？",
        "max_length": 60,
        "tone": "文艺清新",
    },
}

_DEFAULT_AGENT = "通用"


# =============================================================================
# TimeTool 类
# =============================================================================

class TimeTool:
    """本地时间工具类，封装时间获取与自然语言回复生成

    核心方法：
      - get_reply_with_context() — 完整个性化回复入口（推荐）
      - get_reply()               — 基础回复入口（向后兼容）
      - load_user_memory()        — 从记忆系统加载配置

    用法:
        tool = TimeTool(timezone="Asia/Shanghai")
        reply = tool.get_reply_with_context("time", user_context={...})
    """

    # ---- 类级别多轮对话状态 ----
    _last_query_time: float = 0.0
    _last_query_message: str = ""

    def __init__(self, timezone: str = "Asia/Shanghai",
                 agent_id: str | None = None):
        """初始化时间工具

        参数:
            timezone: 时区标识符，默认东八区，无效时回退 Asia/Shanghai
            agent_id:  用户标识，用于从记忆系统读取个性化配置
        """
        if timezone not in available_timezones():
            timezone = "Asia/Shanghai"
        self._timezone = ZoneInfo(timezone)
        self._timezone_name = timezone
        self._agent_id = agent_id
        self._user_location = ""
        self._user_profile: dict = {}    # 来自记忆系统的完整用户画像
        self._user_schedule: list = []   # 用户日程
        self._user_preferences: dict = {}  # 用户偏好
        # 实例级多轮状态（每个tool实例独立追踪）
        self._instance_last_query_time: float = 0.0

    # ------------------------------------------------------------------
    # 记忆系统对接（保留）
    # ------------------------------------------------------------------

    def load_user_memory(self, agent_id: str | None = None):
        """从用户记忆系统加载个性化配置

        读取用户的时区、所在地、职业、日程、作息、偏好等信息，
        存入内部状态供回复生成使用。
        记忆读取失败时保持默认配置，不影响基础功能。

        参数:
            agent_id: 用户标识
        """
        if agent_id:
            self._agent_id = agent_id
        if not self._agent_id:
            return
        try:
            from app.engines.memory.core import get_memory_storage
            storage = get_memory_storage()
            memory = storage.load(self._agent_id)
            profile = memory.profile
            if profile.timezone and profile.timezone in available_timezones():
                if profile.timezone != self._timezone_name:
                    self._timezone = ZoneInfo(profile.timezone)
                    self._timezone_name = profile.timezone
            if profile.location:
                self._user_location = profile.location
            self._user_profile = {
                "name": getattr(profile, "name", ""),
                "location": getattr(profile, "location", ""),
                "timezone": getattr(profile, "timezone", ""),
                "occupation": getattr(profile, "occupation", ""),
                "birthday": getattr(profile, "birthday", ""),
            }
            self._user_schedule = getattr(memory, "schedule", []) or []
            self._user_preferences = {
                "reply_style": getattr(profile, "reply_style", "友好"),
                "wake_time": getattr(profile, "wake_time", ""),
                "sleep_time": getattr(profile, "sleep_time", ""),
            }
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 时间获取（保留，核心链路不动）
    # ------------------------------------------------------------------

    @staticmethod
    @lru_cache(maxsize=64)
    def _get_cached_now(minute_bucket: str, tz_name: str) -> datetime:
        """带缓存的时间获取方法（按时区隔离缓存）"""
        from datetime import timezone as _tz
        tz = ZoneInfo(tz_name)
        return datetime.now(tz)

    def _now(self) -> datetime:
        """获取当前时间（带时区转换和1分钟缓存）"""
        minute_bucket = datetime.now(self._timezone).strftime("%Y%m%d%H%M")
        return self._get_cached_now(minute_bucket, self._timezone_name)

    # ==================================================================
    #  回复生成全链路（本次全面重写）
    # ==================================================================

    # ------------------------------------------------------------------
    # 口语化时间格式化 —— 核心格式化器
    # ------------------------------------------------------------------

    @staticmethod
    def _format_time_oral(hour: int, minute: int) -> tuple[str, str, str]:
        """将24小时制时间转为口语化中文表达

        返回: (时段名, 12小时制小时数, 口语化分秒字符串)
        示例:
          9:05  → ("上午", 9, "9点零5分")
          12:00 → ("中午", 12, "12点整")
          20:30 → ("晚上", 8, "8点30分")
          0:10  → ("凌晨", 12, "12点零10分")

        参数:
            hour:   24小时制小时（0-23）
            minute: 分钟（0-59）

        返回:
            (period_name, display_hour, time_str)
        """
        # 匹配时段配置
        period_name = "深夜"
        display_offset = 12
        for (start, end, p_name, offset, _, _rem) in _PERIODS:
            if start <= hour < end or (start == 0 and hour == 0):
                period_name = p_name
                display_offset = offset
                break

        # 12小时制转换
        if hour == 0:
            display_hour = 12
        elif hour <= 12:
            display_hour = hour if hour != 12 else 12
        else:
            display_hour = hour - 12
        if display_offset != 0:
            display_hour = hour - display_offset
            if display_hour <= 0:
                display_hour += 12

        # 分钟口语化
        if minute == 0:
            time_str = f"{period_name}{display_hour}点整"
        elif minute < 10:
            time_str = f"{period_name}{display_hour}点零{minute}分"
        else:
            time_str = f"{period_name}{display_hour}点{minute}分"

        return period_name, display_hour, time_str

    # ------------------------------------------------------------------
    # 多轮对话检测
    # ------------------------------------------------------------------

    def _check_repeat_query(self, now_ts: float) -> str | None:
        """检测是否重复查询时间，返回多轮对话提示

        返回值:
            None       — 非重复查询，正常生成回复
            非空字符串  — 重复查询，直接返回此提示

        规则:
          同一分钟内 → "还是XX时间哦，才过了不到一分钟~"
          5分钟以内   → "现在是XX时间，距离上次问才过了X分钟"
        """
        if self._instance_last_query_time == 0:
            return None

        elapsed = now_ts - self._instance_last_query_time

        if elapsed <= _REPEAT_SAME_MINUTE:
            now = self._now()
            _, _, time_str = self._format_time_oral(now.hour, now.minute)
            return f"还是{time_str}哦，才过了不到一分钟~"

        if elapsed <= _REPEAT_NEAR_MINUTE:
            now = self._now()
            _, _, time_str = self._format_time_oral(now.hour, now.minute)
            mins = int(elapsed // 60)
            mins_text = "1分钟" if mins <= 1 else f"{mins}分钟"
            return f"现在是{time_str}，距离你上次问才过了{mins_text}~"

        return None

    # ------------------------------------------------------------------
    # 场景化上下文构建
    # ------------------------------------------------------------------

    def _build_scene_context(self, now: datetime, user_message: str = "",
                             user_context: dict | None = None) -> dict:
        """构建场景化上下文，整合所有维度信息

        返回字典包含：
          is_weekend, is_friday, holiday_name, is_urgent,
          weather_data, travel_info, timezone_diff

        参数:
            now: 当前时间
            user_message: 用户消息（用于急迫语境检测）
            user_context: 外部传入的用户上下文（memory/weather/travel数据）
        """
        ctx: dict = {
            "is_weekend": now.weekday() in _WEEKEND_DAYS,
            "is_friday": now.weekday() == 4,
            "holiday_name": "",
            "is_urgent": False,
            "weather_data": None,
            "travel_info": None,
            "timezone_diff": 0,
            "user_location": self._user_location,
            "user_occupation": self._user_profile.get("occupation", ""),
        }

        # 节假日
        lunar_info = _solar_to_lunar(now.date())
        holiday = _get_holiday_info(now.date(), lunar_info)
        if holiday:
            ctx["holiday_name"] = holiday.split("、")[0]

        # 急迫语境检测
        if user_message and _PATTERN_URGENT.search(_clean_input(user_message)):
            ctx["is_urgent"] = True

        # 外部上下文（天气/行程/时区差）
        if user_context:
            ctx["weather_data"] = user_context.get("weather")
            ctx["travel_info"] = user_context.get("travel")
            if user_context.get("remote_timezone"):
                try:
                    remote_tz = ZoneInfo(user_context["remote_timezone"])
                    remote_now = datetime.now(remote_tz)
                    local_now = datetime.now(self._timezone)
                    diff_hours = (remote_now.utcoffset().total_seconds() -
                                  local_now.utcoffset().total_seconds()) / 3600
                    ctx["timezone_diff"] = int(diff_hours)
                except Exception:
                    pass

        return ctx

    # ------------------------------------------------------------------
    # 时段问候 + 场景后缀
    # ------------------------------------------------------------------

    @staticmethod
    def _get_greeting(hour: int, scene_ctx: dict, agent_type: str) -> str:
        """根据时段和场景生成问候前缀

        优先级：急迫安抚 > 办公极简 > 分时段问候
        节假日问候不再覆盖时段问候，而是叠加到后缀中
        """
        # 办公型无问候
        if agent_type == "办公":
            return ""

        # 急迫语境 → 安抚话术（前缀即完整开头）
        if scene_ctx.get("is_urgent"):
            now_ts = datetime.now()
            _, _, time_str = TimeTool._format_time_oral(now_ts.hour, now_ts.minute)
            return f"别慌别慌，现在是{time_str}"

        # 分时段问候（节假日不在这里处理，放到后缀中叠加）
        for (start, end, _, _, greetings, _reminder) in _PERIODS:
            if start <= hour < end:
                return greetings[0]
        return ""

    @staticmethod
    def _get_scene_suffix(hour: int, scene_ctx: dict, agent_type: str) -> str:
        """生成场景化后缀 —— 互斥选择，单次回复仅1个最适配短句

        按优先级从高到低遍历场景，命中第一个即返回，禁止叠加：
          1. 急迫安抚
          2. 行程提醒
          3. 节假日问候
          4. 周末/周五
          5. 天气联动
          6. 时段默认后缀
          7. 工作日激励（兜底）

        参数:
            hour:       当前小时
            scene_ctx:  场景上下文
            agent_type: Agent类型

        返回:
            单个场景短句，或空字符串
        """
        import random

        # ---- 1. 急迫安抚（最高优先级）----
        if scene_ctx.get("is_urgent"):
            return "深呼吸，别着急，来得及的"

        # ---- 2. 行程提醒 ----
        travel = scene_ctx.get("travel_info")
        if travel:
            t_time = travel.get("time", "")
            t_type = travel.get("type", "")
            if t_time:
                try:
                    t_dt = datetime.fromisoformat(t_time)
                    t_str = t_dt.strftime("%H:%M")
                    remaining = t_dt - datetime.now()
                    if 0 < remaining.total_seconds() < 7200:
                        hours_left = int(remaining.total_seconds() // 3600)
                        mins_left = int((remaining.total_seconds() % 3600) // 60)
                        parts = []
                        if hours_left > 0:
                            parts.append(f"{hours_left}小时")
                        if mins_left > 0:
                            parts.append(f"{mins_left}分钟")
                        if t_type:
                            return (f"距离你{t_str}的{t_type}还有"
                                    f"{''.join(parts)}，记得提前出发")
                except Exception:
                    pass

        # ---- 3. 节假日问候 ----
        holiday = scene_ctx.get("holiday_name", "")
        if holiday:
            return _get_holiday_message(holiday)

        # ---- 4. 周末/周五 ----
        if scene_ctx.get("is_weekend"):
            return random.choice(_WEEKEND_RELAXATIONS)
        if scene_ctx.get("is_friday"):
            return _FRIDAY_CELEBRATION

        # ---- 5. 天气联动 ----
        weather = scene_ctx.get("weather_data")
        if weather and agent_type not in ("办公",):
            w_desc = weather.get("desc", "")
            temp = weather.get("temp", "")
            if w_desc and "雨" in w_desc:
                return "今天有雨，出门记得带伞"
            if temp:
                try:
                    t = float(temp) if isinstance(temp, (int, float)) else 20
                    if isinstance(temp, str):
                        t = float(temp.replace("°C", "").replace("℃", ""))
                    if t <= 8:
                        return "外面挺冷的，多穿点"
                except (ValueError, TypeError):
                    pass

        # ---- 6. 时段默认后缀 ----
        period_suffix = _get_period_default_suffix(hour, scene_ctx)
        if period_suffix:
            return period_suffix

        # ---- 7. 工作日激励（兜底）----
        if (not scene_ctx.get("is_weekend")
                and not scene_ctx.get("is_friday")
                and not holiday
                and agent_type not in ("办公",)):
            return random.choice(_WORKDAY_MOTIVATIONS)

        return ""

    # ------------------------------------------------------------------
    # Agent 风格适配
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_agent_style(time_str: str, greeting: str, suffix: str,
                           agent_type: str) -> str:
        """根据 Agent 类型组装最终回复"""
        style = _AGENT_STYLES.get(agent_type, _AGENT_STYLES[_DEFAULT_AGENT])
        prefix_tpl = style["prefix"]
        suffix_tpl = style["suffix"]

        # 渲染前缀
        prefix = prefix_tpl.format(greeting=greeting, time_str=time_str)

        # 拼接
        parts = [prefix]
        if suffix:
            parts.append(suffix)
        if suffix_tpl and agent_type != "通用":
            parts.append(suffix_tpl)

        return "".join(parts)

    # ------------------------------------------------------------------
    # 三级兜底机制
    # ------------------------------------------------------------------

    def _generate_with_fallback(self, now: datetime, user_message: str,
                                user_context: dict | None,
                                agent_type: str) -> str:
        """三级兜底回复生成

        判断顺序（关键修复：特殊查询优先于重复提问）：
          1. 时间偏移查询（1小时后几点）→ 直接计算偏移时间
          2. 日期/时区/农历等特殊查询 → 走对应专用逻辑
          3. 重复提问检测（2分钟窗口）→ 短话术回复
          4. 正常场景化回复 → 互斥选择1个场景短句

        一级：完整个性化场景化回复（含记忆/天气/行程联动）
        二级：通用友好分时段回复（降级，不需要额外数据）
        三级：极简精准报时（最终安全兜底，只报时间不报日期）
        """
        try:
            # ---- 步骤1：时间偏移查询优先判断 ----
            cleaned = _clean_input(user_message) if user_message else ""
            if cleaned and _is_time_offset_query(cleaned):
                offset_info = parse_time_offset(user_message)
                if offset_info.get("valid"):
                    return calc_offset_time(
                        offset_info, timezone=self._timezone_name)
                # 偏移解析失败 → 降级为当前时间
                _, _, time_str = self._format_time_oral(now.hour, now.minute)
                return f"现在是{time_str}"

            # ---- 步骤2：日期/时区/农历等特殊查询 ----
            query_type = _detect_query_type(cleaned)
            if query_type in ("date", "date_offset", "week", "week_offset",
                               "lunar", "holiday", "timezone"):
                return self.get_reply(query_type, user_message=user_message)

            # ---- 步骤3：多轮对话检测（2分钟窗口）----
            now_ts = _time_module.time()
            repeat_msg = self._check_repeat_query(now_ts)
            if repeat_msg:
                self._instance_last_query_time = now_ts
                return repeat_msg

            # 更新时间记录
            self._instance_last_query_time = now_ts

            # ---- 步骤4：正常场景化回复 ----
            scene_ctx = self._build_scene_context(
                now, user_message, user_context)

            # 口语化格式化
            _, _, time_str = self._format_time_oral(now.hour, now.minute)

            # 问候
            greeting = self._get_greeting(now.hour, scene_ctx, agent_type)

            # 急迫语境：问候已包含时间，跳过 agent 前缀
            if scene_ctx.get("is_urgent"):
                base = greeting
            else:
                base = self._apply_agent_style(
                    time_str, greeting, "", agent_type)

            # 办公型极简返回
            if agent_type == "办公" and not scene_ctx.get("is_urgent"):
                return time_str

            # 互斥选择1个场景短句
            suffix = self._get_scene_suffix(now.hour, scene_ctx, agent_type)

            result = f"{base}"
            if suffix:
                sep = "。" if scene_ctx.get("is_urgent") else "，"
                result += sep + suffix
            return result

        except Exception:
            # ---- 二级：通用友好降级 ----
            try:
                _, _, time_str = self._format_time_oral(now.hour, now.minute)
                hour = now.hour
                for (start, end, _, _, greetings, _) in _PERIODS:
                    if start <= hour < end:
                        return f"{greetings[0]}现在是{time_str}哦~"
                return f"现在是{time_str}哦~"
            except Exception:
                # ---- 三级：极简硬编码兜底 ----
                h = now.hour
                m = now.minute
                display = h % 12 or 12
                m_str = "点整" if m == 0 else f"零{m}分" if m < 10 else f"{m}分"
                return f"现在是{display}点{m_str}"

    # ==================================================================
    #  公开接口
    # ==================================================================

    def get_reply_with_context(self, query_type: str = "all",
                               user_message: str = "",
                               user_context: dict | None = None,
                               agent_type: str = "通用") -> str:
        """完整个性化回复入口（推荐使用）

        自动整合所有维度信息生成回复：
          1. 口语化时间格式
          2. 多轮对话检测
          3. 六段场景问候
          4. 工作日/周末/节假日
          5. 急迫语境安抚
          6. 记忆联动（时区/所在地/职业/偏好）
          7. 跨工具联动（天气/行程）
          8. Agent 风格适配
          9. 三级兜底保护

        参数:
            query_type:    查询类型（time/date/week/all/date_offset/等）
            user_message:  用户原始消息（急迫检测 + 偏移计算用）
            user_context:  用户上下文（可选），格式:
                           {"weather": {"desc":"晴","temp":"22"},
                            "travel": {"type":"航班","time":"2026-05-07T10:00"},
                            "remote_timezone": "Asia/Tokyo"}
            agent_type:    Agent类型，"通用"|"闲聊"|"办公"|"旅游"|"创作"

        返回:
            经过所有规则处理的最终自然语言回复

        用法:
            reply = tool.get_reply_with_context(
                "time", "快迟到了现在几点",
                user_context={"travel": {"type": "会议", "time": "..."}},
                agent_type="办公"
            )
        """
        # 兜底值
        if agent_type not in _AGENT_STYLES:
            agent_type = _DEFAULT_AGENT

        # 日期类查询保持原有逻辑不变
        if query_type in ("date", "date_offset", "week", "week_offset",
                         "lunar", "holiday", "timezone"):
            return self.get_reply(query_type, user_message=user_message)

        # 时间和综合查询走新逻辑
        now = self._now()
        if query_type in ("time", "all"):
            return self._generate_with_fallback(
                now, user_message, user_context, agent_type)

        # 其他类型 fallback 到旧方法
        return self.get_reply(query_type, user_message=user_message)

    def get_reply(self, query_type: str, user_message: str = "") -> str:
        """统一回复入口

        参数:
            query_type: 查询类型（time/date/date_offset/week/week_offset/lunar/holiday/timezone）
            user_message: 用户原始消息

        返回:
            自然语言回复字符串
        """
        now = self._now()

        if query_type == "time":
            _, _, time_str = self._format_time_oral(now.hour, now.minute)
            greeting = self._contextual_greeting(now.hour)
            return f"{greeting}现在是{time_str}哦~"

        if query_type in ("date", "date_offset"):
            offset = _extract_day_offset(user_message, now) if (query_type == "date_offset" and user_message) else 0
            target_date = now.date() + timedelta(days=offset)
            target_dt = datetime.combine(target_date, now.time()).replace(tzinfo=self._timezone)
            year, month, day = target_dt.year, target_dt.month, target_dt.day
            weekday = _WEEKDAY_NAMES[target_dt.weekday()]

            prefix_map = {-1: "昨天是", -2: "前天是", 1: "明天是", 2: "后天是"}
            prefix = prefix_map.get(offset, "")
            if not prefix:
                if offset > 0:
                    prefix = f"{offset}天后是"
                elif offset < 0:
                    prefix = f"{abs(offset)}天前是"
                else:
                    prefix = "今天是"

            lunar_info = _solar_to_lunar(target_date)
            holiday = _get_holiday_info(target_date, lunar_info)
            holiday_text = ""
            if holiday:
                first = holiday.split("、")[0]
                holiday_text = f"，{_get_holiday_message(first)}"

            reply = f"{prefix}{year}年{month}月{day}日，{weekday}{holiday_text}"
            if lunar_info.get("found"):
                m_name = lunar_info["month_name"]
                d_name = lunar_info["day_name"]
                y_name = lunar_info["year_name"]
                if m_name not in ("正月", "腊月") or d_name != "初一":
                    reply += f"（农历{y_name}年{m_name}{d_name}）"
            return reply

        if query_type in ("week", "week_offset"):
            offset = _extract_day_offset(user_message, now) if (query_type == "week_offset" and user_message) else 0
            target_date = now.date() + timedelta(days=offset)
            target_dt = datetime.combine(target_date, now.time()).replace(tzinfo=self._timezone)
            weekday = _WEEKDAY_NAMES[target_dt.weekday()]
            weekday_num = target_dt.weekday()

            prefix_map = {1: "明天是", 2: "后天是", -1: "昨天是"}
            prefix = prefix_map.get(offset, "")
            if not prefix:
                if offset > 0:
                    prefix = f"{offset}天后是"
                elif offset < 0:
                    prefix = f"{abs(offset)}天前是"
                else:
                    prefix = "今天是"

            if weekday_num in _WEEKEND_DAYS:
                return f"{prefix}{weekday}呢，好好享受周末时光吧~"
            elif weekday_num == 4:
                return f"{prefix}{weekday}，马上就要周末啦，加油！"
            return f"{prefix}{weekday}~"

        if query_type == "lunar":
            lunar_info = _solar_to_lunar(now.date())
            if not lunar_info.get("found"):
                return f"今天是{now.strftime('%Y-%m-%d')}，" \
                       "很抱歉暂时没有该日期的农历数据哦~"
            year_name = lunar_info["year_name"]
            month_name = lunar_info["month_name"]
            day_name = lunar_info["day_name"]
            holiday_name = _get_holiday_info(now.date(), lunar_info)
            holiday_text = ""
            if holiday_name:
                holiday_names = holiday_name.split("、")
                holiday_text = "，" + _get_holiday_message(holiday_names[0])
            reply = f"今天是农历{year_name}年{month_name}{day_name}{holiday_text}"
            if lunar_info.get("spring_date"):
                spring = lunar_info["spring_date"]
                reply += f"（今年春节是{spring.year}年{spring.month}月{spring.day}日）"
            return reply

        if query_type == "holiday":
            lunar_info = _solar_to_lunar(now.date())
            holiday_name = _get_holiday_info(now.date(), lunar_info)
            year, month, day = now.year, now.month, now.day
            weekday = _WEEKDAY_NAMES[now.weekday()]
            if holiday_name:
                holiday_names = holiday_name.split("、")
                first = holiday_names[0]
                msg = _get_holiday_message(first)
                reply = f"今天是{year}年{month}月{day}日{weekday}，{msg}"
                if len(holiday_names) > 1:
                    reply += f"同时还是{holiday_name}，今天可是个好日子！"
                return reply
            return f"今天是{year}年{month}月{day}日{weekday}，今天不是法定节假日哦~"

        if query_type == "timezone":
            cleaned = _clean_input(user_message) if user_message else ""
            tz_name = self._detect_tz_city_name(cleaned)
            if tz_name:
                tz_id = (_CITY_TIMEZONE_MAP.get(tz_name) or
                         _TIMEZONE_KEYWORDS.get(tz_name + "时间"))
                if tz_id and tz_id in available_timezones():
                    tz_tool = TimeTool(timezone=tz_id)
                    tz_now = tz_tool._now()
                    _, _, tz_time_str = tz_tool._format_time_oral(tz_now.hour, tz_now.minute)
                    return f"{tz_name}现在是{tz_time_str}哦~"
                return f"抱歉，暂时不支持查询「{tz_name}」的时区信息哦~"

        # 综合回复
        year, month, day = now.year, now.month, now.day
        hour, minute = now.hour, now.minute
        weekday = _WEEKDAY_NAMES[now.weekday()]
        weekday_num = now.weekday()

        _, _, time_str = self._format_time_oral(hour, minute)
        greeting = self._contextual_greeting(hour)
        base = f"{greeting}现在是{year}年{month}月{day}日{weekday}{time_str}"

        lunar_info = _solar_to_lunar(now.date())
        holiday_name = _get_holiday_info(now.date(), lunar_info)
        if holiday_name:
            holiday_names = holiday_name.split("、")
            base += f"，今天是{holiday_name}"
            base += "，" + _get_holiday_message(holiday_names[0])

        if weekday_num in _WEEKEND_DAYS and not holiday_name:
            base += "，祝您周末愉快！"
        elif weekday_num == 4:
            base += "，明天就是周末啦，再坚持一下~"
        return base

    def _contextual_greeting(self, hour: int) -> str:
        """时段问候"""
        for (start, end, _, _, greetings, _) in _PERIODS:
            if start <= hour < end:
                return greetings[0]
        return ""

    @staticmethod
    def _detect_tz_city_name(cleaned: str) -> str | None:
        """时区城市名检测"""
        for city in _CITY_TIMEZONE_MAP:
            if city in cleaned:
                return city
        for keyword in _TIMEZONE_KEYWORDS:
            if keyword in cleaned:
                return keyword.replace("时间", "").replace("时区", "")
        return None


# =============================================================================
# 全局单例与对外接口
# =============================================================================

_time_tool_instance: Optional[TimeTool] = None
_time_tool_timezone: str = "Asia/Shanghai"
_time_tool_agent_id: Optional[str] = None


def _get_time_tool(timezone: str = "Asia/Shanghai",
                   agent_id: str | None = None) -> TimeTool:
    """获取 TimeTool 单例，时区/用户变更时重建"""
    global _time_tool_instance, _time_tool_timezone, _time_tool_agent_id
    if (_time_tool_instance is None
            or timezone != _time_tool_timezone
            or agent_id != _time_tool_agent_id):
        _time_tool_instance = TimeTool(timezone=timezone, agent_id=agent_id)
        _time_tool_timezone = timezone
        _time_tool_agent_id = agent_id
    return _time_tool_instance


def get_time_reply_enhanced(user_message: str,
                            timezone: str = "Asia/Shanghai",
                            agent_id: str | None = None,
                            user_context: dict | None = None,
                            agent_type: str = "通用") -> str:
    """增强对外接口 —— 支持个性化上下文 + 多Agent风格

    参数:
        user_message:  用户原始消息
        timezone:      时区（默认东八区）
        agent_id:      用户标识（记忆系统读取用）
        user_context:  用户上下文 {"weather":..., "travel":..., "remote_timezone":...}
        agent_type:    Agent类型，"通用"|"闲聊"|"办公"|"旅游"|"创作"

    用法:
        reply = get_time_reply_enhanced(
            "现在几点", agent_type="办公",
            user_context={"weather": {"desc": "雨", "temp": "12"}}
        )
    """
    if not user_message:
        return ""
    cleaned = _clean_input(user_message)
    if not cleaned:
        return ""
    query_type = _detect_query_type(cleaned)
    tool = _get_time_tool(timezone=timezone, agent_id=agent_id)

    if query_type != "timezone":
        detected_tz = _detect_timezone_from_message(cleaned)
        if detected_tz and detected_tz != timezone:
            tool = _get_time_tool(timezone=detected_tz, agent_id=agent_id)

    return tool.get_reply_with_context(
        query_type, user_message=user_message,
        user_context=user_context, agent_type=agent_type
    )


# =============================================================================
# 直接运行验证（python -m app.utils.time_tool）
# =============================================================================
if __name__ == "__main__":
    import random

    print("=" * 74)
    print("  TimeTool 回复优化版 全场景测试")
    print("=" * 74)

    successful = 0
    total = 0

    def test_one(label: str, fn, *args, **kw) -> str:
        global successful, total
        total += 1
        try:
            result = fn(*args, **kw)
            if result:
                print(f"\n  [{label}]")
                print(f"  {result}")
                successful += 1
            else:
                print(f"\n  [FAIL] {label} -> 空回复")
        except Exception as e:
            print(f"\n  [FAIL] {label} -> 异常: {e}")
        return ""

    # ---- 基础时间查询 ----
    test_one("基础-现在几点了", get_time_reply_enhanced, "现在几点了")
    test_one("基础-今天几号", get_time_reply_enhanced, "今天几号")
    test_one("基础-今天周几", get_time_reply_enhanced, "今天星期几")

    # ---- 日期偏移 ----
    test_one("偏移-明天几号", get_time_reply_enhanced, "明天几号")
    test_one("偏移-后天周几", get_time_reply_enhanced, "后天是星期几")
    test_one("偏移-下周一", get_time_reply_enhanced, "下周一")

    # ---- 农历/节假日 ----
    test_one("农历-今天", get_time_reply_enhanced, "农历今天")
    test_one("节假日-今天什么日子", get_time_reply_enhanced, "今天是什么日子")

    # ---- 时区 ----
    test_one("时区-东京时间", get_time_reply_enhanced, "现在东京时间几点")

    # ---- 多Agent风格对比（各自独立实例，避免多轮干扰）----
    print("\n" + "=" * 74)
    print("  Agent 风格对比 (同一消息: '现在几点了')")
    print("=" * 74)
    for agent in ["通用", "闲聊", "办公", "旅游", "创作"]:
        # 每个Agent用独立实例，展示各自风格
        t = TimeTool(timezone="Asia/Shanghai")
        r = t.get_reply_with_context("time", "现在几点了", agent_type=agent)
        total += 1
        if r:
            print(f"\n  [Agent-{agent}]")
            print(f"  {r}")
            successful += 1
        else:
            print(f"\n  [FAIL] Agent-{agent} -> 空回复")

    # ---- 场景化上下文联动（每个场景独立实例）----
    def test_one_direct(label: str, result: str):
        global successful, total
        total += 1
        if result:
            print(f"\n  [{label}]")
            print(f"  {result}")
            successful += 1
        else:
            print(f"\n  [FAIL] {label} -> 空回复")

    print("\n" + "=" * 74)
    print("  场景化联动测试")
    print("=" * 74)

    t = TimeTool(timezone="Asia/Shanghai")
    r = t.get_reply_with_context(
        "time", "现在几点", agent_type="通用",
        user_context={"weather": {"desc": "中雨", "temp": "12"}})
    test_one_direct("联动-下雨天", r)

    t2 = TimeTool(timezone="Asia/Shanghai")
    r2 = t2.get_reply_with_context(
        "time", "现在几点了", agent_type="通用",
        user_context={"travel": {
            "type": "航班",
            "time": (datetime.now() + timedelta(hours=1, minutes=30)
                     ).isoformat()
        }})
    test_one_direct("联动-有行程", r2)

    t3 = TimeTool(timezone="Asia/Shanghai")
    r3 = t3.get_reply_with_context("time", "来不及了现在几点", agent_type="通用")
    test_one_direct("联动-急迫语境", r3)

    # ---- 多轮对话模拟（共享同一实例）----
    print("\n" + "=" * 74)
    print("  多轮对话测试（同一实例连续3次查询）")
    print("=" * 74)
    multi_tool = TimeTool(timezone="Asia/Shanghai")
    for i in range(3):
        r = multi_tool.get_reply_with_context(
            "time", "现在几点了", agent_type="通用")
        test_one_direct(f"多轮-第{i+1}次", r)
        if i < 2:
            _time_module.sleep(0.05)

    # ---- 综合结果 ----
    print("\n" + "=" * 74)
    print(f"  总计: {successful}/{total} 通过")
    if successful == total:
        print("  全部测试通过!")
    else:
        print(f"  有 {total - successful} 个测试未通过")
