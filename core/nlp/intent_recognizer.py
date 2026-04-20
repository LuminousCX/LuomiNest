"""
意图识别模块
Author: LumiNest Team
Date: 2026-04-14
"""
from typing import Dict, List


class IntentRecognizer:
    """意图识别器类
    
    根据用户输入识别意图类型
    """
    
    INTENT_PATTERNS: Dict[str, List[str]] = {
        "greeting": ["你好", "您好", "早上好", "下午好", "晚上好", "嗨", "哈喽"],
        "farewell": ["再见", "拜拜", "晚安", "bye", "byebye"],
        "ask_time": ["几点", "时间", "现在", "今天", "日期", "几号", "星期"],
        "ask_weather": ["天气", "气温", "温度", "下雨", "晴天", "阴天", "雪", "风"],
        "ask_name": ["名字", "叫什么", "你是谁"],
        "set_name": ["我的名字叫", "我叫", "你可以叫我", "我的名字是", "我是"],
        "set_system_name": ["系统名字叫", "你的名字叫", "你改名叫", "你现在改名叫", "你的名字是"],
        "clear_memory": ["/clear", "清空记忆", "清除记忆"],
        "admin_login": ["/admin", "管理员登录", "登录管理员"],
        "admin_logout": ["/logout", "管理员登出", "登出管理员"],
        "chat": ["聊天", "聊聊", "说说话"],
    }

    def recognize_intent(self, text: str) -> str:
        """识别用户输入的意图
        
        Args:
            text: 用户输入文本
            
        Returns:
            str: 识别到的意图类型
        """
        for intent, patterns in self.INTENT_PATTERNS.items():
            if any(pattern in text for pattern in patterns):
                return intent
        return "unknown"

    def get_intent_confidence(self, text: str, intent: str) -> float:
        """获取意图识别的置信度
        
        Args:
            text: 用户输入文本
            intent: 意图类型
            
        Returns:
            float: 置信度（0.0-1.0）
        """
        if intent not in self.INTENT_PATTERNS:
            return 0.0
        
        patterns = self.INTENT_PATTERNS[intent]
        for pattern in patterns:
            if pattern in text:
                return min(len(pattern) / len(text) if text else 0.0, 1.0)
        return 0.0
