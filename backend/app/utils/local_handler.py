"""
本地请求处理器 - 本地工具请求的统一分发入口

功能：
  将用户消息分流到对应的本地处理工具，当前已接入：
  - 时间工具（time_tool）：毫秒级时间/日期/星期查询
  - 天气工具（weather_tool）：毫秒级天气查询

职责：
  1. 调用 intent_gateway 进行请求分类
  2. 命中 LOCAL_TOOL 后，调用对应工具生成回复
  3. 命中天气请求时，提取城市后调用天气工具
  4. 未命中则返回 None，不影响调用方继续走原有的对话流程
  5. 全链路异常兜底，绝对不会中断主流程

设计原则：
  1. 纯分发逻辑，不包含任何业务计算
  2. 返回 None 表示"此请求不属于本地处理范围"，调用方可继续走大模型
  3. 返回有效字符串表示"已本地处理完毕"，调用方可直接使用回复
  4. 极端异常也返回兜底话术，确保对话不中断
"""

import re

from loguru import logger

from app.utils.intent_gateway import classify_request, RequestType, is_weather_query
from app.utils.time_tool import get_time_reply
from app.utils.weather_tool import _weather_tool


# =============================================================================
# 城市名提取 —— 从用户消息中提取城市名称
# =============================================================================

# 中国主要城市名正则（支持简写如"京"、"沪"）
_CITY_PATTERN = re.compile(
    r"(北京|上海|广州|深圳|杭州|成都|武汉|西安|南京|重庆|天津|"
    r"苏州|长沙|郑州|济南|青岛|大连|厦门|福州|昆明|贵阳|南宁|"
    r"海口|三亚|哈尔滨|长春|沈阳|乌鲁木齐|拉萨|兰州|银川|西宁|"
    r"呼和浩特|太原|石家庄|合肥|南昌|东莞|佛山|无锡|宁波|温州|"
    r"徐州|珠海|惠州|中山|烟台|威海|"
    r"京|沪|穗|深|蓉|渝)"
)

# 城市别名映射 —— "京"→"北京"
_CITY_ALIAS: dict[str, str] = {
    "京": "北京", "沪": "上海", "穗": "广州",
    "深": "深圳", "蓉": "成都", "渝": "重庆",
}


def _extract_city(user_message: str) -> str | None:
    """从用户消息中提取城市名称

    在消息中搜索匹配的城市名，返回第一个匹配的城市（完整名称）。
    支持城市别名自动映射（如"京"→"北京"）。

    参数:
        user_message: 用户输入的原始消息文本

    返回:
        城市完整名称，未找到返回 None
    """
    matched = _CITY_PATTERN.findall(user_message)
    if not matched:
        return None
    city = matched[0]
    return _CITY_ALIAS.get(city, city)


def _extract_date_from_message(user_message: str, city: str) -> str:
    """从用户消息中提取日期部分，传给天气工具的 parse_query_date 解析

    处理流程：
      1. 去掉消息中的城市名称
      2. 去掉常见的天气查询词（天气、气温、多少度等）
      3. 剩下的部分即为日期候选文本

    参数:
        user_message: 用户输入的原始消息文本
        city: 已提取的城市名

    返回:
        日期候选文本，如"明天"、"5.1号"、"下周一"，无日期时返回空字符串
    """
    clean = user_message
    # 去掉城市名
    clean = clean.replace(city, "")
    # 去掉常见查询后缀
    for phrase in [
        "天气怎么样", "天气如何", "天气怎样", "天气",
        "气温", "温度", "多少度", "几度", "冷不冷", "热不热",
        "怎么样", "如何", "怎样", "预报", "天气预报",
        "穿衣", "带伞", "防晒", "的", "吗", "吧", "呢", "啊", "哦",
    ]:
        clean = clean.replace(phrase, "")

    return clean.strip()


# =============================================================================
# 天气请求处理
# =============================================================================

async def handle_weather_request(user_message: str) -> str | None:
    """处理天气查询请求 —— 提取城市和日期，调用天气工具

    流程：
      1. 从消息中提取城市名称
      2. 从消息中提取日期（如"明天"、"5.1号"、"下周一"）
      3. 若提取城市失败 → 返回 None，让调用方继续走原有流程
      4. 直接 await 天气工具的异步接口获取回复

    参数:
        user_message: 用户输入的原始消息文本

    返回:
        - 有效字符串：天气回复
        - None：无法提取城市，应由调用方继续处理

    用法:
        reply = await handle_weather_request("北京明天天气怎么样")
        if reply:
            return reply  # 已本地处理
    """
    try:
        city = _extract_city(user_message)
        if city is None:
            # 无城市名 → 返回 None，让调用方走工具调用循环
            # （大模型可以从上下文推断城市）
            return None

        # 提取日期：去掉城市名称部分后传入 parse_query_date
        date_str = _extract_date_from_message(user_message, city)

        # 在异步上下文中直接 await，避免同步封装的事件循环冲突
        reply = await _weather_tool.get_reply(city, date_str)
        return reply

    except Exception as e:
        logger.warning(f"[LocalHandler] 处理天气请求异常: {e}")
        return None


# =============================================================================
# 统一分发入口
# =============================================================================


async def handle_local_tool_request(user_message: str) -> str | None:
    """处理本地工具请求的入口函数

    流程：
      1. 调用 classify_request 判断请求类型
      2. 若为 LOCAL_TOOL，调用时间工具生成回复
      3. 若为 TOOL_CALL（天气），尝试提取城市并调用天气工具
      4. 若为其他类型，返回 None 让调用方继续走大模型对话
      5. 若发生异常，返回友好的兜底话术

    参数:
        user_message: 用户输入的原始消息文本

    返回:
        - 有效字符串：本地已处理完成，可直接用作对话回复
        - None：此请求不属于本地工具范围，调用方应继续走大模型

    用法:
        reply = await handle_local_tool_request("现在几点？")
        if reply is not None:
            return reply
    """
    try:
        # 第一步：分类
        request_type = classify_request(user_message)

        # 第二步：时间查询（LOCAL_TOOL）
        if request_type == RequestType.LOCAL_TOOL:
            reply = get_time_reply(user_message)
            if reply:
                return reply
            return None

        # 第三步：天气查询（TOOL_CALL）
        if request_type == RequestType.TOOL_CALL:
            # 二次确认：is_weather_query 用专属规则树验证
            if is_weather_query(user_message):
                reply = await handle_weather_request(user_message)
                if reply:
                    return reply
            # 不是天气的 TOOL_CALL（搜索/旅游等）→ 返回 None 走工具调用循环
            return None

        # 第四步：其他类型 → 返回 None
        return None

    except Exception as e:
        # 全链路兜底：任何异常都不中断对话，返回友好话术
        logger.warning(f"[LocalHandler] 处理本地工具请求异常: {e}")
        return "抱歉，我暂时无法处理这个请求，您可以换种方式问我哦~"
