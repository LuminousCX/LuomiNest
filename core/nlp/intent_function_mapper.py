"""
意图-功能映射系统
根据识别到的用户意图，调用相应的本地功能
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime
import re

from .intent_recognizer_enhanced import (
    IntentMatch,
    IntentAnalysisResult,
    IntentCategory,
    get_intent_recognizer
)
from .semantic_similarity import get_semantic_calculator


@dataclass
class FunctionResult:
    success: bool
    result: Any
    message: str
    should_use_api: bool = False
    api_context: str = ""


class LocalFunctionRegistry:
    """本地功能注册表"""
    
    FUNCTIONS = {
        "respond_greeting": {
            "description": "回应问候",
            "category": "social",
            "requires_context": False,
        },
        "respond_farewell": {
            "description": "回应告别",
            "category": "social",
            "requires_context": False,
        },
        "respond_gratitude": {
            "description": "回应感谢",
            "category": "social",
            "requires_context": False,
        },
        "get_current_time": {
            "description": "获取当前时间",
            "category": "query",
            "requires_context": False,
        },
        "get_weather": {
            "description": "获取天气信息",
            "category": "query",
            "requires_context": False,
            "requires_api": True,
        },
        "introduce_self": {
            "description": "自我介绍",
            "category": "query",
            "requires_context": False,
        },
        "set_user_name": {
            "description": "设置用户名字",
            "category": "command",
            "requires_context": False,
        },
        "set_system_name": {
            "description": "设置系统名字",
            "category": "command",
            "requires_context": False,
        },
        "clear_memory": {
            "description": "清空记忆",
            "category": "system",
            "requires_context": False,
        },

        "show_help": {
            "description": "显示帮助信息",
            "category": "query",
            "requires_context": False,
        },
        "continue_previous": {
            "description": "继续上一个话题",
            "category": "continuation",
            "requires_context": True,
        },
        "clarify_response": {
            "description": "澄清回答",
            "category": "clarification",
            "requires_context": True,
        },
        "explain_reason": {
            "description": "解释原因",
            "category": "query",
            "requires_context": True,
        },
        "provide_instructions": {
            "description": "提供指导",
            "category": "query",
            "requires_context": True,
        },
        "explain_concept": {
            "description": "解释概念",
            "category": "query",
            "requires_context": True,
        },
        "share_opinion": {
            "description": "分享观点",
            "category": "query",
            "requires_context": True,
        },
        "compare_items": {
            "description": "比较项目",
            "category": "query",
            "requires_context": True,
        },
        "provide_recommendation": {
            "description": "提供推荐",
            "category": "query",
            "requires_context": True,
        },
        "provide_emotional_support": {
            "description": "提供情感支持",
            "category": "emotional",
            "requires_context": False,
        },
        "share_happiness": {
            "description": "分享快乐",
            "category": "emotional",
            "requires_context": False,
        },
        "handle_anger": {
            "description": "处理愤怒情绪",
            "category": "emotional",
            "requires_context": False,
        },
        "calm_anxiety": {
            "description": "安抚焦虑",
            "category": "emotional",
            "requires_context": False,
        },
        "acknowledge_positive_feedback": {
            "description": "确认正面反馈",
            "category": "feedback",
            "requires_context": False,
        },
        "handle_negative_feedback": {
            "description": "处理负面反馈",
            "category": "feedback",
            "requires_context": False,
        },
        "search_knowledge_base": {
            "description": "搜索知识库",
            "category": "knowledge",
            "requires_context": False,
        },
        "add_to_knowledge_base": {
            "description": "添加到知识库",
            "category": "knowledge",
            "requires_context": False,
        },
        "parse_web_content": {
            "description": "解析网页内容",
            "category": "query",
            "requires_context": False,
        },
        "start_conversation": {
            "description": "开始对话",
            "category": "social",
            "requires_context": False,
        },
        "use_knowledge_base": {
            "description": "使用知识库回答",
            "category": "knowledge",
            "requires_context": False,
        },
        "use_api_fallback": {
            "description": "使用API回退",
            "category": "fallback",
            "requires_context": False,
        },
    }
    
    @classmethod
    def get_function(cls, name: str) -> Optional[Dict]:
        """获取功能配置"""
        return cls.FUNCTIONS.get(name)
    
    @classmethod
    def get_all_functions(cls) -> Dict[str, Dict]:
        """获取所有功能"""
        return cls.FUNCTIONS.copy()


class IntentFunctionMapper:
    """意图-功能映射器"""
    
    def __init__(
        self,
        knowledge_manager=None,
        memory_manager=None,
        ai_personality_manager=None
    ):
        self.knowledge_manager = knowledge_manager
        self.memory_manager = memory_manager
        self.ai_personality_manager = ai_personality_manager
        self.semantic_calc = get_semantic_calculator()
        self.intent_recognizer = get_intent_recognizer()
        
        self._function_handlers: Dict[str, Callable] = {}
        self._register_handlers()
    
    def _register_handlers(self):
        """注册功能处理器"""
        self._function_handlers = {
            "get_current_time": self._handle_get_time,
            "introduce_self": self._handle_introduce_self,
            "set_user_name": self._handle_set_user_name,
            "set_system_name": self._handle_set_system_name,
            "clear_memory": self._handle_clear_memory,
            "show_help": self._handle_show_help,
            "search_knowledge_base": self._handle_search_knowledge,
            "parse_web_content": self._handle_parse_url,
            "respond_greeting": self._handle_greeting,
            "respond_farewell": self._handle_farewell,
            "respond_gratitude": self._handle_gratitude,
            "provide_emotional_support": self._handle_emotional_support,
            "share_happiness": self._handle_happiness,
            "handle_anger": self._handle_anger,
            "calm_anxiety": self._handle_anxiety,
            "acknowledge_positive_feedback": self._handle_positive_feedback,
            "handle_negative_feedback": self._handle_negative_feedback,
        }
    
    def set_knowledge_manager(self, manager):
        """设置知识管理器"""
        self.knowledge_manager = manager
    
    def set_memory_manager(self, manager):
        """设置记忆管理器"""
        self.memory_manager = manager
    
    def set_ai_personality_manager(self, manager):
        """设置AI人格管理器"""
        self.ai_personality_manager = manager
    
    def execute_intent(
        self,
        intent: IntentMatch,
        user_input: str,
        context: Dict[str, Any] = None
    ) -> FunctionResult:
        """执行意图对应的本地功能"""
        context = context or {}
        
        function_name = intent.local_function
        if not function_name:
            return self._fallback_to_api(intent, user_input, context)
        
        handler = self._function_handlers.get(function_name)
        if handler:
            try:
                return handler(intent, user_input, context)
            except Exception as e:
                return FunctionResult(
                    success=False,
                    result=None,
                    message=f"执行功能时出错: {str(e)}",
                    should_use_api=True
                )
        
        return self._fallback_to_api(intent, user_input, context)
    
    def _handle_get_time(
        self,
        intent: IntentMatch,
        user_input: str,
        context: Dict[str, Any]
    ) -> FunctionResult:
        """处理获取时间请求"""
        now = datetime.now()
        weekdays = ['一', '二', '三', '四', '五', '六', '日']
        
        time_info = f"""现在是 {now.year}年{now.month}月{now.day}日
星期{weekdays[now.weekday()]}
时间 {now.hour}时{now.minute}分"""
        
        if "几号" in user_input or "日期" in user_input:
            time_info = f"今天是 {now.year}年{now.month}月{now.day}日，星期{weekdays[now.weekday()]}"
        elif "星期" in user_input:
            time_info = f"今天是星期{weekdays[now.weekday()]}"
        elif "几点" in user_input or "时间" in user_input:
            time_info = f"现在是 {now.hour}时{now.minute}分"
        
        return FunctionResult(
            success=True,
            result=time_info,
            message=time_info,
            should_use_api=False
        )
    
    def _handle_introduce_self(
        self,
        intent: IntentMatch,
        user_input: str,
        context: Dict[str, Any]
    ) -> FunctionResult:
        """处理自我介绍"""
        system_name = "辰汐"
        if self.ai_personality_manager:
            personality = self.ai_personality_manager.get_current_personality()
            if personality:
                system_name = personality.get("name", system_name)
        
        intro = f"""你好！我是{system_name}，一个智能助手。

我可以帮你：
- 回答问题和提供建议
- 搜索知识库中的信息
- 解析网页内容
- 进行日常对话
- 记住你的重要信息

有什么我可以帮助你的吗？"""
        
        return FunctionResult(
            success=True,
            result=intro,
            message=intro,
            should_use_api=False
        )
    
    def _handle_set_user_name(
        self,
        intent: IntentMatch,
        user_input: str,
        context: Dict[str, Any]
    ) -> FunctionResult:
        """处理设置用户名字"""
        name_patterns = [
            r'我叫([^\s，。！？]+)',
            r'我的名字[叫是]([^\s，。！？]+)',
            r'你可以叫我([^\s，。！？]+)',
        ]
        
        name = None
        for pattern in name_patterns:
            match = re.search(pattern, user_input)
            if match:
                name = match.group(1)
                break
        
        if name:
            return FunctionResult(
                success=True,
                result={"name": name},
                message=f"好的，我会记住你的名字是{name}！很高兴认识你！",
                should_use_api=False
            )
        
        return FunctionResult(
            success=False,
            result=None,
            message="请告诉我你的名字，比如'我叫小明'",
            should_use_api=True
        )
    
    def _handle_set_system_name(
        self,
        intent: IntentMatch,
        user_input: str,
        context: Dict[str, Any]
    ) -> FunctionResult:
        """处理设置系统名字"""
        name_patterns = [
            r'(?:系统|你)(?:的名字)?叫([^\s，。！？]+)',
            r'你改名叫([^\s，。！？]+)',
        ]
        
        name = None
        for pattern in name_patterns:
            match = re.search(pattern, user_input)
            if match:
                name = match.group(1)
                break
        
        if name and self.ai_personality_manager:
            self.ai_personality_manager.set_name(name)
            return FunctionResult(
                success=True,
                result={"name": name},
                message=f"好的，从现在开始我的名字是{name}！",
                should_use_api=False
            )
        
        return FunctionResult(
            success=False,
            result=None,
            message="请告诉我你想叫我什么名字",
            should_use_api=True
        )
    
    def _handle_clear_memory(
        self,
        intent: IntentMatch,
        user_input: str,
        context: Dict[str, Any]
    ) -> FunctionResult:
        """处理清空记忆"""
        if self.memory_manager:
            self.memory_manager.clear_memory()
        
        return FunctionResult(
            success=True,
            result=None,
            message="好的，我已经清空了所有记忆。让我们重新开始吧！",
            should_use_api=False
        )
    
    def _handle_show_help(
        self,
        intent: IntentMatch,
        user_input: str,
        context: Dict[str, Any]
    ) -> FunctionResult:
        """处理显示帮助"""
        help_text = """【功能帮助】

基础功能：
- 问候/告别：你好、再见、晚安
- 时间查询：几点了、今天几号、星期几
- 名字设置：我叫XX、你可以叫我XX
- 帮助：帮助、怎么用、能做什么

知识库功能：
- 查询知识：搜索XX、查找XX
- 添加知识：记录XX、记住XX

网页解析：
- 发送包含URL的消息，我会自动解析网页内容

系统命令：
- /clear - 清空记忆

其他问题可以直接问我，我会尽力帮助你！"""
        
        return FunctionResult(
            success=True,
            result=help_text,
            message=help_text,
            should_use_api=False
        )
    
    def _handle_search_knowledge(
        self,
        intent: IntentMatch,
        user_input: str,
        context: Dict[str, Any]
    ) -> FunctionResult:
        """处理搜索知识库"""
        if not self.knowledge_manager:
            return FunctionResult(
                success=False,
                result=None,
                message="知识库未初始化",
                should_use_api=True
            )
        
        query = re.sub(r'查询|搜索|查找|寻找', '', user_input).strip()
        if not query:
            query = user_input
        
        expanded_queries = self.semantic_calc.expand_query(query)
        all_results = []
        
        for q in expanded_queries[:3]:
            results = self.knowledge_manager.search_knowledge(q, threshold=0.3)
            all_results.extend(results)
        
        unique_results = []
        seen = set()
        for r in all_results:
            key = r.get('question', '') if isinstance(r, dict) else str(r)
            if key not in seen:
                seen.add(key)
                unique_results.append(r)
        
        if unique_results:
            result_text = "【知识库匹配结果】\n\n"
            for i, r in enumerate(unique_results[:3], 1):
                if isinstance(r, dict):
                    result_text += f"{i}. {r.get('question', '')}\n"
                    result_text += f"   {r.get('answer', '')}\n\n"
                else:
                    result_text += f"{i}. {r}\n\n"
            
            return FunctionResult(
                success=True,
                result=unique_results,
                message=result_text,
                should_use_api=False,
                api_context=result_text
            )
        
        return FunctionResult(
            success=False,
            result=None,
            message="知识库中未找到相关信息",
            should_use_api=True
        )
    
    def _handle_parse_url(
        self,
        intent: IntentMatch,
        user_input: str,
        context: Dict[str, Any]
    ) -> FunctionResult:
        """处理解析URL"""
        if not self.knowledge_manager:
            return FunctionResult(
                success=False,
                result=None,
                message="知识管理器未初始化",
                should_use_api=True
            )
        
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, user_input)
        
        if not urls:
            return FunctionResult(
                success=False,
                result=None,
                message="未检测到URL",
                should_use_api=True
            )
        
        results = self.knowledge_manager.parse_urls(urls[:3])
        
        if results and 'error' not in results[0]:
            context_text = "【网页解析结果】\n\n"
            for r in results:
                if 'error' in r:
                    context_text += f"URL: {r.get('url', '')}\n解析失败: {r['error']}\n\n"
                else:
                    context_text += f"标题: {r.get('title', '无标题')}\n"
                    context_text += f"URL: {r.get('url', '')}\n"
                    context_text += f"内容摘要:\n{r.get('content', '')[:500]}...\n\n"
            
            return FunctionResult(
                success=True,
                result=results,
                message="网页解析完成",
                should_use_api=True,
                api_context=context_text
            )
        
        return FunctionResult(
            success=False,
            result=None,
            message="网页解析失败",
            should_use_api=True
        )
    
    def _handle_greeting(
        self,
        intent: IntentMatch,
        user_input: str,
        context: Dict[str, Any]
    ) -> FunctionResult:
        """处理问候"""
        now = datetime.now()
        if 5 <= now.hour < 12:
            greeting = "早上好"
        elif 12 <= now.hour < 18:
            greeting = "下午好"
        else:
            greeting = "晚上好"
        
        message = f"{greeting}！有什么我可以帮助你的吗？"
        
        return FunctionResult(
            success=True,
            result=message,
            message=message,
            should_use_api=False
        )
    
    def _handle_farewell(
        self,
        intent: IntentMatch,
        user_input: str,
        context: Dict[str, Any]
    ) -> FunctionResult:
        message = "再见！期待下次和你聊天！"
        
        return FunctionResult(
            success=True,
            result=message,
            message=message,
            should_use_api=False
        )
    
    def _handle_gratitude(
        self,
        intent: IntentMatch,
        user_input: str,
        context: Dict[str, Any]
    ) -> FunctionResult:
        """处理感谢"""
        responses = [
            "不客气！能帮到你我很开心！",
            "不用谢！有需要随时找我！",
            "很高兴能帮到你！",
            "这是我应该做的！",
        ]
        
        import random
        message = random.choice(responses)
        
        return FunctionResult(
            success=True,
            result=message,
            message=message,
            should_use_api=False
        )
    
    def _handle_emotional_support(
        self,
        intent: IntentMatch,
        user_input: str,
        context: Dict[str, Any]
    ) -> FunctionResult:
        """处理情感支持"""
        return FunctionResult(
            success=True,
            result=None,
            message="",
            should_use_api=True,
            api_context="用户情绪低落，需要提供情感支持和安慰。"
        )
    
    def _handle_happiness(
        self,
        intent: IntentMatch,
        user_input: str,
        context: Dict[str, Any]
    ) -> FunctionResult:
        """处理快乐情绪"""
        return FunctionResult(
            success=True,
            result=None,
            message="",
            should_use_api=True,
            api_context="用户情绪开心，分享快乐并积极回应。"
        )
    
    def _handle_anger(
        self,
        intent: IntentMatch,
        user_input: str,
        context: Dict[str, Any]
    ) -> FunctionResult:
        """处理愤怒情绪"""
        return FunctionResult(
            success=True,
            result=None,
            message="",
            should_use_api=True,
            api_context="用户情绪愤怒，需要理解和安抚。"
        )
    
    def _handle_anxiety(
        self,
        intent: IntentMatch,
        user_input: str,
        context: Dict[str, Any]
    ) -> FunctionResult:
        """处理焦虑情绪"""
        return FunctionResult(
            success=True,
            result=None,
            message="",
            should_use_api=True,
            api_context="用户情绪焦虑，需要提供安慰和建议。"
        )
    
    def _handle_positive_feedback(
        self,
        intent: IntentMatch,
        user_input: str,
        context: Dict[str, Any]
    ) -> FunctionResult:
        """处理正面反馈"""
        responses = [
            "谢谢你的肯定！我会继续努力的！",
            "很高兴你满意！有其他需要帮助的吗？",
            "谢谢！能帮到你是我最大的动力！",
        ]
        
        import random
        message = random.choice(responses)
        
        return FunctionResult(
            success=True,
            result=message,
            message=message,
            should_use_api=False
        )
    
    def _handle_negative_feedback(
        self,
        intent: IntentMatch,
        user_input: str,
        context: Dict[str, Any]
    ) -> FunctionResult:
        """处理负面反馈"""
        return FunctionResult(
            success=True,
            result=None,
            message="",
            should_use_api=True,
            api_context="用户表达了不满意，需要道歉并改进。"
        )
    
    def _fallback_to_api(
        self,
        intent: IntentMatch,
        user_input: str,
        context: Dict[str, Any]
    ) -> FunctionResult:
        """回退到API"""
        api_context = ""
        
        if self.knowledge_manager:
            knowledge_results = self.knowledge_manager.search_knowledge(user_input, threshold=0.3)
            if knowledge_results:
                api_context += "【相关知识】\n"
                for r in knowledge_results[:2]:
                    if isinstance(r, dict):
                        api_context += f"- {r.get('question', '')}: {r.get('answer', '')[:100]}\n"
        
        return FunctionResult(
            success=True,
            result=None,
            message="",
            should_use_api=True,
            api_context=api_context
        )
    
    def get_function_description(self, function_name: str) -> Optional[str]:
        """获取功能描述"""
        func = LocalFunctionRegistry.get_function(function_name)
        if func:
            return func.get("description")
        return None


_intent_function_mapper: Optional[IntentFunctionMapper] = None


def get_intent_function_mapper() -> IntentFunctionMapper:
    """获取意图-功能映射器单例"""
    global _intent_function_mapper
    if _intent_function_mapper is None:
        _intent_function_mapper = IntentFunctionMapper()
    return _intent_function_mapper
