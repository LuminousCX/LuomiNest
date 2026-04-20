"""时间处理工具类。

提供统一的时间格式化、计算、解析功能。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

_BEIJING_TZ = timezone(timedelta(hours=8))

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M:%S"


def now_beijing() -> datetime:
    """获取当前北京时间。"""
    return datetime.now(_BEIJING_TZ)


def format_datetime(dt: Optional[datetime] = None, fmt: str = DATETIME_FORMAT) -> str:
    """格式化日期时间。

    Args:
        dt: 待格式化的 datetime，为 None 时使用当前时间。
        fmt: 格式化模板。

    Returns:
        格式化后的时间字符串。
    """
    if dt is None:
        dt = now_beijing()
    return dt.strftime(fmt)


def parse_datetime(time_str: str, fmt: str = DATETIME_FORMAT) -> datetime:
    """解析时间字符串为 datetime 对象。

    Args:
        time_str: 时间字符串。
        fmt: 解析格式。

    Returns:
        解析后的 datetime 对象。
    """
    return datetime.strptime(time_str, fmt).replace(tzinfo=_BEIJING_TZ)


def time_ago(dt: datetime) -> str:
    """计算距离当前时间的相对描述。

    Args:
        dt: 目标时间。

    Returns:
        如 "3分钟前"、"2小时前"、"1天前" 等描述。
    """
    delta = now_beijing() - dt
    total_seconds = int(delta.total_seconds())

    if total_seconds < 60:
        return "刚刚"
    if total_seconds < 3600:
        minutes = total_seconds // 60
        return f"{minutes}分钟前"
    if total_seconds < 86400:
        hours = total_seconds // 3600
        return f"{hours}小时前"
    if total_seconds < 2592000:
        days = total_seconds // 86400
        return f"{days}天前"
    if total_seconds < 31536000:
        months = total_seconds // 2592000
        return f"{months}个月前"
    years = total_seconds // 31536000
    return f"{years}年前"


def is_greeting_time() -> str:
    """根据当前时间返回问候时段。

    Returns:
        "早上" / "上午" / "中午" / "下午" / "晚上" / "深夜"
    """
    hour = now_beijing().hour
    if 5 <= hour < 8:
        return "早上"
    if 8 <= hour < 11:
        return "上午"
    if 11 <= hour < 13:
        return "中午"
    if 13 <= hour < 18:
        return "下午"
    if 18 <= hour < 22:
        return "晚上"
    return "深夜"
