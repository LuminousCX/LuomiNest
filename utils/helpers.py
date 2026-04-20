"""
工具函数模块
Author: LumiNest Team
Date: 2026-04-14
"""
import re
from datetime import datetime
from typing import Optional, Set, List

GREETINGS: Set[str] = {"你好", "您好", "早上好", "下午好", "晚上好", "嗨", "哈喽", "嗨喽", "嗨嗨", "你好啊", "您好啊"}
FAREWELLS: Set[str] = {"再见", "拜拜", "晚安", "bye", "byebye", "再见啦", "拜拜啦", "晚安啦"}
QUESTION_WORDS: Set[str] = {"什么", "为什么", "怎么", "怎样", "如何", "哪里", "哪儿", "何时", "什么时候", "谁", "哪个", "哪些", "吗", "呢", "吧"}
TIME_WORDS: Set[str] = {"几点", "时间", "现在", "今天", "日期", "几号", "星期"}
WEATHER_WORDS: Set[str] = {"天气", "气温", "温度", "下雨", "晴天", "阴天", "雪", "风", "云"}

NAME_PATTERNS: List[str] = [
    r'我的名字叫(.*?)[，。！？]?',
    r'我叫(.*?)[，。！？]?',
    r'你可以叫我(.*?)[，。！？]?',
    r'我的名字是(.*?)[，。！？]?',
    r'我是(.*?)[，。！？]?',
    r'系统名字叫(.*?)[，。！？]?',
    r'你的名字叫(.*?)[，。！？]?',
    r'你改名叫(.*?)[，。！？]?',
    r'你现在改名叫(.*?)[，。！？]?',
    r'你的名字是(.*?)[，。！？]?'
]


def get_current_time() -> str:
    """获取当前时间字符串
    
    Returns:
        str: 格式化的当前时间字符串
    """
    return datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")


def get_current_date() -> str:
    """获取当前日期字符串
    
    Returns:
        str: 格式化的当前日期字符串
    """
    return datetime.now().strftime("%Y年%m月%d日")


def extract_name(text: str) -> Optional[str]:
    """从文本中提取名字
    
    Args:
        text: 输入文本
        
    Returns:
        Optional[str]: 提取到的名字，未找到则返回None
    """
    for pattern in NAME_PATTERNS:
        if match := re.search(pattern, text):
            name = re.sub(r'[，。！？]', '', match.group(1).strip())
            return name if name else None
    return None


def is_greeting(text: str) -> bool:
    """判断文本是否包含问候语
    
    Args:
        text: 输入文本
        
    Returns:
        bool: 是否包含问候语
    """
    return any(g in text for g in GREETINGS)


def is_farewell(text: str) -> bool:
    """判断文本是否包含告别语
    
    Args:
        text: 输入文本
        
    Returns:
        bool: 是否包含告别语
    """
    return any(f in text for f in FAREWELLS)


def is_question(text: str) -> bool:
    """判断文本是否为问题
    
    Args:
        text: 输入文本
        
    Returns:
        bool: 是否为问题
    """
    return any(w in text for w in QUESTION_WORDS) or "?" in text


def contains_time_query(text: str) -> bool:
    """判断文本是否包含时间查询
    
    Args:
        text: 输入文本
        
    Returns:
        bool: 是否包含时间查询
    """
    return any(w in text for w in TIME_WORDS)


def contains_weather_query(text: str) -> bool:
    """判断文本是否包含天气查询
    
    Args:
        text: 输入文本
        
    Returns:
        bool: 是否包含天气查询
    """
    return any(w in text for w in WEATHER_WORDS)
