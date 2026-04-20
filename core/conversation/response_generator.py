"""
响应生成模块
Author: LumiNest Team
Date: 2026-04-14
"""
import random
from typing import Dict, List, Optional, Any

from utils.helpers import get_current_time


class ResponseGenerator:
    """响应生成器类
    
    根据意图和上下文生成合适的响应内容
    """
    
    GREETINGS: List[str] = [
        "{name}在这里，有什么可以帮助你的吗？",
        "嗨！{name}随时为你解答问题～",
        "你好呀！我是{name}，今天过得怎么样？",
        "你好！我是{name}，很高兴为你服务！",
    ]
    
    FAREWELLS: List[str] = [
        "再见！祝你有美好的一天！",
        "拜拜啦！期待下次见到你！",
        "晚安！做个好梦！",
        "再见，有需要随时找我哦！",
    ]
    
    GRATITUDE: List[str] = [
        "不客气，很高兴能帮到你！",
        "这是我应该做的，有需要随时找我！",
        "不用谢，能帮到你我也很开心！",
        "你的满意就是我最大的动力！",
        "随时为你服务！",
        "很高兴能帮到你，有问题随时问我！",
    ]
    
    WEATHER_RESPONSES: List[str] = [
        "抱歉，我暂时无法获取实时天气信息。你可以尝试使用其他天气服务或应用查询。",
        "对不起，我目前没有天气查询功能。建议你使用专业的天气应用获取最新天气信息。",
        "很抱歉，我无法提供天气查询服务。你可以通过手机天气应用或网站查看天气情况。",
    ]
    
    POSITIVE_FEEDBACK: List[str] = [
        "谢谢你的肯定！我会继续努力的！",
        "很高兴你满意！有其他问题随时问我～",
        "你的认可让我更有动力了！",
        "太好了！能帮到你真是太棒了！",
        "谢谢！我会继续保持的！",
    ]
    
    NEGATIVE_FEEDBACK: List[str] = [
        "抱歉让你不满意，能告诉我哪里需要改进吗？",
        "我会努力改进的，请告诉我具体的问题。",
        "谢谢你的反馈，我会认真对待的。",
        "很抱歉，我会努力做得更好！",
        "感谢你的坦诚，我会改进这个问题。",
    ]
    
    EMOTION_RESPONSES: Dict[str, List[str]] = {
        "sad": [
            "听到你这么说，我很心疼。能告诉我发生什么事了吗？",
            "我能感受到你的难过，你愿意和我分享一下吗？",
            "别难过，一切都会好起来的。我在这里陪着你。",
            "我理解你的感受，这种时候确实很难熬。",
            "你现在一定很痛苦，我能为你做些什么吗？",
        ],
        "happy": [
            "看到你这么开心，我也很高兴！",
            "太棒了！能分享一下是什么让你这么开心吗？",
            "你的快乐感染了我，真好！",
            "真为你感到高兴，继续保持这份好心情！",
        ],
        "angry": [
            "我能理解你的感受，遇到这样的事确实会让人很生气。",
            "别生气，深呼吸，一切都会过去的。",
            "生气对身体不好，我们一起想想怎么解决这个问题吧。",
            "我知道你现在很生气，想说什么就说出来吧，我在听。",
        ],
    }
    
    EMOTION_KEYWORDS: Dict[str, set] = {
        "sad": {"伤心", "难过", "悲伤", "痛苦", "哭", "不开心", "郁闷", "沮丧"},
        "happy": {"开心", "高兴", "快乐", "兴奋", "喜悦", "幸福"},
        "angry": {"生气", "愤怒", "恼火", "不爽", "讨厌"},
    }
    
    DEFAULT_RESPONSES: List[str] = [
        "我不太理解你的意思，能再说一遍吗？",
        "抱歉，我没有理解你的问题。",
        "可以换个方式表达吗？",
        "我正在努力理解，能提供更多信息吗？",
        "这个问题有点难，我需要再学习一下。",
    ]

    def __init__(self, system_name: str):
        """初始化响应生成器
        
        Args:
            system_name: 系统名称
        """
        self.system_name = system_name

    def generate_response(self, intent: str, user_input: str, context: Optional[Dict] = None) -> str:
        """根据意图生成响应
        
        Args:
            intent: 意图类型
            user_input: 用户输入
            context: 上下文信息
            
        Returns:
            str: 生成的响应内容
        """
        handlers = {
            "greeting": lambda: self._greeting(),
            "farewell": lambda: random.choice(self.FAREWELLS),
            "gratitude": lambda: random.choice(self.GRATITUDE),
            "ask_time": lambda: self._time_response(),
            "ask_weather": lambda: random.choice(self.WEATHER_RESPONSES),
            "ask_name": lambda: self._name_response(),
            "set_name": lambda: self._set_name_response(context),
            "set_system_name": lambda: self._set_system_name_response(context),
            "chat": lambda: self._chat_response(),
            "help": lambda: self._help_response(),
            "feedback_positive": lambda: random.choice(self.POSITIVE_FEEDBACK),
            "feedback_negative": lambda: random.choice(self.NEGATIVE_FEEDBACK),
        }
        
        if handler := handlers.get(intent):
            return handler()
        return self._default_response(user_input)

    def _greeting(self) -> str:
        """生成问候响应
        
        Returns:
            str: 问候响应内容
        """
        return random.choice(self.GREETINGS).format(name=self.system_name)

    def _time_response(self) -> str:
        """生成时间响应
        
        Returns:
            str: 时间响应内容
        """
        current_time = get_current_time()
        templates = [
            f"现在是{current_time}",
            f"当前时间：{current_time}",
            f"现在的时间是{current_time}",
        ]
        return random.choice(templates)

    def _name_response(self) -> str:
        """生成名称响应
        
        Returns:
            str: 名称响应内容
        """
        templates = [
            f"我是{self.system_name}，你的智能助手！",
            f"你好，我叫{self.system_name}，很高兴认识你！",
            f"我的名字是{self.system_name}，有什么可以帮助你的吗？",
        ]
        return random.choice(templates)

    def _set_name_response(self, context: Optional[Dict]) -> str:
        """生成设置用户名响应
        
        Args:
            context: 包含用户名的上下文
            
        Returns:
            str: 设置名称响应内容
        """
        if context and (user_name := context.get("user_name")):
            templates = [
                f"好的，我记住了，你叫{user_name}！",
                f"很高兴认识你，{user_name}！",
                f"{user_name}，这个名字真好听！",
            ]
            return random.choice(templates)
        return "好的，我记住了你的名字！"

    def _set_system_name_response(self, context: Optional[Dict]) -> str:
        """生成设置系统名响应
        
        Args:
            context: 包含新系统名的上下文
            
        Returns:
            str: 设置系统名响应内容
        """
        if context and (new_name := context.get("system_name")):
            templates = [
                f"好的，我现在改名叫{new_name}了！",
                f"从现在开始，我就是{new_name}了！",
                f"好的，以后请叫我{new_name}～",
            ]
            return random.choice(templates)
        return "好的，我会记住新名字的！"

    def _chat_response(self) -> str:
        """生成聊天响应
        
        Returns:
            str: 聊天响应内容
        """
        responses = [
            "你最近怎么样？",
            "有什么新鲜事可以分享吗？",
            "今天过得如何？",
            "我在听，你继续说...",
            "很有趣，能详细说说吗？",
        ]
        return random.choice(responses)

    def _help_response(self) -> str:
        """生成帮助响应
        
        Returns:
            str: 帮助响应内容
        """
        return f"""我是{self.system_name}，你的智能助手！我可以帮你：

1. 回答问题 - 问我任何你想知道的事情
2. 学习辅导 - 编程、语言、知识学习
3. 日常对话 - 聊天、分享心情
4. 记忆管理 - 记住你的重要信息
5. 网页解析 - 发送链接，我帮你分析内容

常用命令：
/clear - 清空记忆

有什么我可以帮你的吗？"""

    def _default_response(self, user_input: str) -> str:
        """生成默认响应
        
        Args:
            user_input: 用户输入
            
        Returns:
            str: 默认响应内容
        """
        for emotion, keywords in self.EMOTION_KEYWORDS.items():
            if any(kw in user_input for kw in keywords):
                return random.choice(self.EMOTION_RESPONSES[emotion])
        return random.choice(self.DEFAULT_RESPONSES)

    def update_system_name(self, new_name: str) -> None:
        """更新系统名称
        
        Args:
            new_name: 新的系统名称
        """
        self.system_name = new_name
