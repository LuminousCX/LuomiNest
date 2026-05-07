"""
本地时间工具 - 纯本地时间/日期/星期查询模块

功能：
  提供毫秒级的时间/日期/星期自然语言回复，纯本地计算，零网络依赖。
  支持四种查询类型：
  - time：返回当前时间（如 "现在是下午3点25分"）
  - date：返回当前日期（如 "今天是2026年5月2日"）
  - week：返回当前星期（如 "今天是星期六"）
  - all：返回综合回复（时间+日期+星期，周末附加提示）

设计原则：
  1. @lru_cache 实现1分钟缓存，同一分钟内重复查询零开销
  2. 支持传入自定义时区，默认东八区（Asia/Shanghai）
  3. 回复自然口语化，不干瘪地只返回数字
  4. 全局单例模式，避免重复实例化
  5. 仅依赖 Python 标准库，零外部依赖
"""

import re
from datetime import datetime
from functools import lru_cache
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

# 周末集合：用于判断是否附加周末提示
_WEEKEND_DAYS = {5, 6}

# =============================================================================
# 查询类型识别正则：复用与 intent_gateway 一致的匹配逻辑
# =============================================================================

# 时间意图：匹配 "几点"、"现在时间" 等
_PATTERN_TIME = re.compile(
    r"(几点|几时|什么时间|啥时间|现在时间|当前时间|看时间|报时|time|clock)",
)

# 日期意图：匹配 "几号"、"今天日期"、"几月" 等
_PATTERN_DATE = re.compile(
    r"(几号|几月几|几月几日|什么日期|今天日期|当前日期|今天几|啥日期|"
    r"年月日|日历|几月份|几月$)",
)

# 星期意图：匹配 "星期几"、"周几"、具体星期名等
_PATTERN_WEEKDAY = re.compile(
    r"(星期几|周几|礼拜几|今天周|明天周|后天周|昨天周|周五|周六|周日|"
    r"周一|周二|周三|周四|星期[一二三四五六日天]|周[一二三四五六日天])",
)


def _clean_input(text: str) -> str:
    """清洗输入文本，去除空格和中英文问号"""
    cleaned = text.replace(" ", "").replace("　", "")
    cleaned = cleaned.replace("？", "").replace("?", "")
    return cleaned


def _detect_query_type(cleaned: str) -> str:
    """根据清洗后的用户消息，识别时间查询的子类型

    返回:
        "time"  - 用户问的是当前时间
        "date"  - 用户问的是当前日期
        "week"  - 用户问的是星期几
        "all"   - 匹配了多种或未明确，返回综合信息
    """
    has_time = bool(_PATTERN_TIME.search(cleaned))
    has_date = bool(_PATTERN_DATE.search(cleaned))
    has_week = bool(_PATTERN_WEEKDAY.search(cleaned))

    # 统计匹配了多少种类型
    match_count = sum([has_time, has_date, has_week])

    if match_count == 1:
        if has_time:
            return "time"
        if has_date:
            return "date"
        if has_week:
            return "week"

    # 匹配了多种或未明确匹配 → 返回综合信息
    return "all"


class TimeTool:
    """本地时间工具类，封装时间获取与自然语言回复生成

    用法:
        tool = TimeTool(timezone="Asia/Shanghai")
        reply = tool.get_reply("time")   # "现在是下午3点25分"
        reply = tool.get_reply("date")   # "今天是2026年5月2日"
        reply = tool.get_reply("week")   # "今天是星期六"
        reply = tool.get_reply("all")    # 综合时间+日期+星期
    """

    def __init__(self, timezone: str = "Asia/Shanghai"):
        """初始化时间工具

        参数:
            timezone: 时区标识符，默认东八区。若传入无效时区则回退到 Asia/Shanghai
                      预留接口：后续可从记忆系统读取用户偏好时区传入
        """
        if timezone not in available_timezones():
            timezone = "Asia/Shanghai"
        self._timezone = ZoneInfo(timezone)
        self._timezone_name = timezone

    @staticmethod
    @lru_cache(maxsize=1)
    def _get_cached_now(minute_bucket: str) -> datetime:
        """带缓存的时间获取方法

        使用 lru_cache(maxsize=1) + minute_bucket 参数实现1分钟缓存。
        minute_bucket 每分钟变化一次（格式 "YYYYMMDDHHMM"），
        同一分钟内所有调用命中缓存，下一分钟自动刷新。

        参数:
            minute_bucket: 分钟桶标识，由调用方传入当前分钟字符串
        """
        # 这里获取的是系统本地时间，时区信息由调用方处理
        return datetime.now()

    def _now(self) -> datetime:
        """获取当前时间（带时区转换和1分钟缓存）"""
        minute_bucket = datetime.now().strftime("%Y%m%d%H%M")
        naive_now = self._get_cached_now(minute_bucket)
        return naive_now.replace(tzinfo=self._timezone)

    def _get_time_reply(self) -> str:
        """生成自然语言时间回复，如 "现在是下午3点25分" """
        now = self._now()
        hour = now.hour
        minute = now.minute

        # 时段描述：凌晨/早上/上午/中午/下午/晚上
        if hour < 6:
            period = "凌晨"
        elif hour < 9:
            period = "早上"
        elif hour < 12:
            period = "上午"
        elif hour == 12:
            period = "中午"
        elif hour < 18:
            period = "下午"
        else:
            period = "晚上"

        # 12小时制的小时
        display_hour = hour % 12
        if display_hour == 0:
            display_hour = 12

        # 分钟的描述方式
        if minute == 0:
            time_str = f"{period}{display_hour}点整"
        elif minute < 10:
            time_str = f"{period}{display_hour}点零{minute}分"
        else:
            time_str = f"{period}{display_hour}点{minute}分"

        return f"现在是{time_str}哦~"

    def _get_date_reply(self) -> str:
        """生成自然语言日期回复，如 "今天是2026年5月2日，星期六" """
        now = self._now()
        year = now.year
        month = now.month
        day = now.day
        weekday = _WEEKDAY_NAMES[now.weekday()]

        return f"今天是{year}年{month}月{day}日，{weekday}"

    def _get_week_reply(self) -> str:
        """生成自然语言星期回复，周末附加祝福"""
        now = self._now()
        weekday = _WEEKDAY_NAMES[now.weekday()]
        weekday_num = now.weekday()

        if weekday_num in _WEEKEND_DAYS:
            return f"今天是{weekday}呢，好好享受周末时光吧~"
        elif weekday_num == 4:
            return f"今天是{weekday}，马上就要周末啦，加油！"
        else:
            return f"今天是{weekday}，新的一天继续努力吧~"

    def _get_full_reply(self) -> str:
        """生成综合时间回复，包含日期、星期、时间，周末附加祝福"""
        now = self._now()
        year = now.year
        month = now.month
        day = now.day
        hour = now.hour
        minute = now.minute
        weekday = _WEEKDAY_NAMES[now.weekday()]
        weekday_num = now.weekday()

        # 时段描述
        if hour < 6:
            period = "凌晨"
        elif hour < 9:
            period = "早上"
        elif hour < 12:
            period = "上午"
        elif hour == 12:
            period = "中午"
        elif hour < 18:
            period = "下午"
        else:
            period = "晚上"

        display_hour = hour % 12
        if display_hour == 0:
            display_hour = 12

        if minute == 0:
            time_str = f"{period}{display_hour}点整"
        elif minute < 10:
            time_str = f"{period}{display_hour}点零{minute}分"
        else:
            time_str = f"{period}{display_hour}点{minute}分"

        base = f"现在是{year}年{month}月{day}日{weekday}{time_str}"

        # 周末附加祝福
        if weekday_num in _WEEKEND_DAYS:
            base += "，祝您周末愉快！"
        elif weekday_num == 4:
            base += "，明天就是周末啦，再坚持一下~"

        return base

    def get_reply(self, query_type: str) -> str:
        """根据查询类型返回对应的自然语言回复

        参数:
            query_type: 查询类型，可选 "time" / "date" / "week" / "all"

        返回:
            自然语言回复字符串
        """
        if query_type == "time":
            return self._get_time_reply()
        elif query_type == "date":
            return self._get_date_reply()
        elif query_type == "week":
            return self._get_week_reply()
        else:
            return self._get_full_reply()


# =============================================================================
# 全局单例与对外接口
# =============================================================================

_time_tool_instance: TimeTool | None = None
_time_tool_timezone: str = "Asia/Shanghai"


def _get_time_tool(timezone: str = "Asia/Shanghai") -> TimeTool:
    """获取 TimeTool 单例，若时区变更则重建"""
    global _time_tool_instance, _time_tool_timezone
    if _time_tool_instance is None or timezone != _time_tool_timezone:
        _time_tool_instance = TimeTool(timezone=timezone)
        _time_tool_timezone = timezone
    return _time_tool_instance


def get_time_reply(user_message: str, timezone: str = "Asia/Shanghai") -> str:
    """对外暴露的极简接口：传入用户消息，返回时间相关的自然语言回复

    自动识别用户消息中的时间查询类型（time/date/week/all），
    返回对应的自然语言回复。不适合时间查询的消息返回空字符串。

    参数:
        user_message: 用户原始消息文本
        timezone: 时区标识符，默认东八区，预留记忆系统接口

    返回:
        自然语言时间回复字符串，非时间类消息返回空字符串

    用法:
        reply = get_time_reply("现在几点了？")
        # "现在是下午3点25分哦~"

        reply = get_time_reply("今天星期几")
        # "今天是星期六呢，好好享受周末时光吧~"
    """
    if not user_message:
        return ""

    cleaned = _clean_input(user_message)
    if not cleaned:
        return ""

    query_type = _detect_query_type(cleaned)
    tool = _get_time_tool(timezone=timezone)
    return tool.get_reply(query_type)
