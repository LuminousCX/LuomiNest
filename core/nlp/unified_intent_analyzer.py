"""
联合意图分析器 - 多维度上下文综合分析用户意图
整合对话历史、用户画像、记忆系统、知识库等多源信息
"""

from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import re
from datetime import datetime


class IntentCategory(Enum):
    QUERY = "query"
    COMMAND = "command"
    SOCIAL = "social"
    EMOTIONAL = "emotional"
    CONTINUATION = "continuation"
    CLARIFICATION = "clarification"
    FEEDBACK = "feedback"


@dataclass
class Intent:
    name: str
    category: IntentCategory
    confidence: float
    keywords: List[str] = field(default_factory=list)
    entities: Dict[str, Any] = field(default_factory=dict)
    context_relevance: float = 0.0
    priority: int = 0


@dataclass
class ContextInfo:
    source: str
    content: str
    relevance: float
    timestamp: float = 0.0


@dataclass
class AnalysisResult:
    primary_intent: Intent
    secondary_intents: List[Intent] = field(default_factory=list)
    context_used: List[ContextInfo] = field(default_factory=list)
    topic: Optional[str] = None
    topic_continuation: bool = False
    sentiment: str = "neutral"
    entities: Dict[str, Any] = field(default_factory=dict)
    suggested_actions: List[str] = field(default_factory=list)


class UnifiedIntentAnalyzer:
    """联合意图分析器 - 多维度上下文综合分析"""
    
    INTENT_PATTERNS = {
        "greeting": {
            "patterns": [r'你好', r'您好', r'早上好', r'下午好', r'晚上好', r'嗨', r'哈喽', r'hello', r'hi'],
            "category": IntentCategory.SOCIAL,
            "priority": 10
        },
        "farewell": {
            "patterns": [r'再见', r'拜拜', r'晚安', r'bye', r'byebye', r'下次见'],
            "category": IntentCategory.SOCIAL,
            "priority": 10
        },
        "gratitude": {
            "patterns": [r'谢谢', r'感谢', r'多谢', r'thanks', r'thank you'],
            "category": IntentCategory.SOCIAL,
            "priority": 8
        },
        "ask_time": {
            "patterns": [r'几点', r'时间', r'现在.*时间', r'今天.*几号', r'星期几', r'日期'],
            "category": IntentCategory.QUERY,
            "priority": 7
        },
        "ask_weather": {
            "patterns": [r'天气', r'气温', r'温度', r'下雨', r'晴天', r'阴天', r'雪', r'风'],
            "category": IntentCategory.QUERY,
            "priority": 7
        },
        "ask_name": {
            "patterns": [r'你.*名字', r'你叫什么', r'你是谁', r'自我介绍'],
            "category": IntentCategory.QUERY,
            "priority": 6
        },
        "set_name": {
            "patterns": [r'我的名字叫', r'我叫', r'你可以叫我', r'我的名字是'],
            "category": IntentCategory.COMMAND,
            "priority": 9
        },
        "set_system_name": {
            "patterns": [r'系统名字叫', r'你的名字叫', r'你改名叫', r'你现在改名叫'],
            "category": IntentCategory.COMMAND,
            "priority": 9
        },
        "clear_memory": {
            "patterns": [r'/clear', r'清空记忆', r'清除记忆', r'忘记一切'],
            "category": IntentCategory.COMMAND,
            "priority": 10
        },
        "admin_login": {
            "patterns": [r'/admin', r'管理员登录', r'登录管理员'],
            "category": IntentCategory.COMMAND,
            "priority": 10
        },
        "help": {
            "patterns": [r'帮助', r'help', r'怎么用', r'使用方法', r'功能'],
            "category": IntentCategory.QUERY,
            "priority": 6
        },
        "continuation": {
            "patterns": [r'再来一个', r'再来', r'新的', r'另一个', r'还有一个', r'再给我', r'继续', r'还有呢'],
            "category": IntentCategory.CONTINUATION,
            "priority": 8
        },
        "clarification": {
            "patterns": [r'什么意思', r'是什么', r'能详细说说', r'能再解释', r'具体点', r'展开说说'],
            "category": IntentCategory.CLARIFICATION,
            "priority": 7
        },
        "why_question": {
            "patterns": [r'为什么', r'怎么会', r'原因是'],
            "category": IntentCategory.QUERY,
            "priority": 6
        },
        "how_to": {
            "patterns": [r'怎么', r'如何', r'怎样', r'方法'],
            "category": IntentCategory.QUERY,
            "priority": 5
        },
        "what_is": {
            "patterns": [r'是什么', r'什么是', r'介绍一下'],
            "category": IntentCategory.QUERY,
            "priority": 5
        },
        "opinion": {
            "patterns": [r'你觉得', r'你认为', r'怎么看', r'想法'],
            "category": IntentCategory.QUERY,
            "priority": 5
        },
        "comparison": {
            "patterns": [r'区别', r'比较', r'哪个好', r'对比', r'差异'],
            "category": IntentCategory.QUERY,
            "priority": 5
        },
        "recommendation": {
            "patterns": [r'推荐', r'建议', r'有什么好'],
            "category": IntentCategory.QUERY,
            "priority": 5
        },
        "emotional_sad": {
            "patterns": [r'伤心', r'难过', r'悲伤', r'痛苦', r'哭', r'不开心', r'郁闷', r'沮丧', r'失落'],
            "category": IntentCategory.EMOTIONAL,
            "priority": 9
        },
        "emotional_happy": {
            "patterns": [r'开心', r'高兴', r'快乐', r'兴奋', r'喜悦', r'幸福', r'太棒了'],
            "category": IntentCategory.EMOTIONAL,
            "priority": 8
        },
        "emotional_angry": {
            "patterns": [r'生气', r'愤怒', r'恼火', r'不爽', r'讨厌', r'烦'],
            "category": IntentCategory.EMOTIONAL,
            "priority": 9
        },
        "emotional_anxious": {
            "patterns": [r'焦虑', r'担心', r'紧张', r'害怕', r'恐惧', r'不安'],
            "category": IntentCategory.EMOTIONAL,
            "priority": 9
        },
        "feedback_positive": {
            "patterns": [r'很好', r'不错', r'很棒', r'厉害', r'优秀', r'完美'],
            "category": IntentCategory.FEEDBACK,
            "priority": 7
        },
        "feedback_negative": {
            "patterns": [r'不好', r'不行', r'错误', r'不对', r'有问题', r'不满意'],
            "category": IntentCategory.FEEDBACK,
            "priority": 7
        },
    }
    
    TOPIC_KEYWORDS = {
        "programming": ["编程", "代码", "程序", "开发", "python", "java", "javascript", "函数", "变量"],
        "learning": ["学习", "读书", "课程", "培训", "教育", "知识", "技能"],
        "work": ["工作", "职业", "上班", "职场", "事业", "项目"],
        "life": ["生活", "日常", "习惯", "健康", "运动"],
        "entertainment": ["电影", "音乐", "游戏", "剧", "娱乐", "小说"],
        "food": ["美食", "吃的", "餐厅", "菜", "食物", "烹饪"],
        "travel": ["旅游", "旅行", "景点", "度假", "出游"],
        "finance": ["投资", "理财", "股票", "基金", "财务", "钱"],
        "relationship": ["朋友", "家人", "恋爱", "感情", "关系"],
        "technology": ["科技", "AI", "人工智能", "机器学习", "数据"],
    }
    
    PRONOUNS = {
        "它": {"type": "thing", "gender": "neutral"},
        "他": {"type": "person", "gender": "male"},
        "她": {"type": "person", "gender": "female"},
        "这个": {"type": "thing", "gender": "neutral"},
        "那个": {"type": "thing", "gender": "neutral"},
        "这些": {"type": "things", "gender": "neutral"},
        "那些": {"type": "things", "gender": "neutral"},
        "刚才": {"type": "time", "gender": "neutral"},
        "之前": {"type": "time", "gender": "neutral"},
    }
    
    SENTIMENT_KEYWORDS = {
        "positive": ["好", "棒", "喜欢", "爱", "开心", "高兴", "感谢", "谢谢", "优秀", "完美", "厉害"],
        "negative": ["不好", "讨厌", "烦", "难过", "伤心", "生气", "愤怒", "失望", "糟糕", "差"],
        "neutral": ["是", "有", "在", "能", "会", "可以", "需要", "想"],
    }
    
    def __init__(self):
        self._conversation_history: List[Dict[str, Any]] = []
        self._current_topic: Optional[str] = None
        self._topic_history: List[str] = []
        self._entity_cache: Dict[str, Any] = {}
        self._last_intent: Optional[Intent] = None
        self._max_history: int = 20
    
    def analyze(
        self,
        user_input: str,
        conversation_history: List[Dict[str, str]] = None,
        memory_results: List[str] = None,
        knowledge_results: List[str] = None,
    ) -> AnalysisResult:
        """
        综合分析用户意图
        
        Args:
            user_input: 用户输入
            conversation_history: 对话历史
            memory_results: 记忆搜索结果
            knowledge_results: 知识库搜索结果
        
        Returns:
            AnalysisResult: 分析结果
        """
        context_used: List[ContextInfo] = []
        
        if conversation_history:
            self._conversation_history = conversation_history
        
        intents = self._recognize_intents(user_input)
        
        context_intents = self._analyze_with_context(user_input, intents)
        intents = self._merge_intents(intents, context_intents)
        
        topic, topic_continuation = self._analyze_topic(user_input)
        
        sentiment = self._analyze_sentiment(user_input)
        
        entities = self._extract_entities(user_input)
        entities = self._resolve_entities(entities, user_input)
        
        if memory_results:
            memory_context = self._get_memory_context(memory_results)
            if memory_context:
                context_used.append(ContextInfo(
                    source="memory",
                    content=memory_context,
                    relevance=0.7
                ))
        
        if knowledge_results:
            knowledge_context = self._get_knowledge_context(knowledge_results)
            if knowledge_context:
                context_used.append(ContextInfo(
                    source="knowledge",
                    content=knowledge_context,
                    relevance=0.6
                ))
        
        intents = self._adjust_confidence_with_context(intents, context_used, sentiment)
        
        intents.sort(key=lambda x: (x.priority, x.confidence), reverse=True)
        
        primary_intent = intents[0] if intents else Intent(
            name="unknown",
            category=IntentCategory.QUERY,
            confidence=0.0
        )
        secondary_intents = intents[1:4] if len(intents) > 1 else []
        
        suggested_actions = self._suggest_actions(primary_intent, topic, sentiment)
        
        self._last_intent = primary_intent
        if topic:
            self._current_topic = topic
            self._topic_history.append(topic)
            if len(self._topic_history) > 10:
                self._topic_history.pop(0)
        
        return AnalysisResult(
            primary_intent=primary_intent,
            secondary_intents=secondary_intents,
            context_used=context_used,
            topic=topic,
            topic_continuation=topic_continuation,
            sentiment=sentiment,
            entities=entities,
            suggested_actions=suggested_actions
        )
    
    def _recognize_intents(self, text: str) -> List[Intent]:
        """识别用户意图"""
        intents = []
        text_lower = text.lower()
        
        for intent_name, intent_config in self.INTENT_PATTERNS.items():
            matched_keywords = []
            for pattern in intent_config["patterns"]:
                if re.search(pattern, text_lower):
                    matched_keywords.append(pattern)
            
            if matched_keywords:
                confidence = self._calculate_confidence(text, matched_keywords)
                intent = Intent(
                    name=intent_name,
                    category=intent_config["category"],
                    confidence=confidence,
                    keywords=matched_keywords,
                    priority=intent_config["priority"]
                )
                intents.append(intent)
        
        if not intents:
            intents.append(Intent(
                name="general_query",
                category=IntentCategory.QUERY,
                confidence=0.5,
                priority=1
            ))
        
        return intents
    
    def _calculate_confidence(self, text: str, matched_keywords: List[str]) -> float:
        """计算意图置信度"""
        if not text:
            return 0.0
        
        text_len = len(text)
        matched_len = sum(len(kw) for kw in matched_keywords)
        
        base_confidence = min(matched_len / text_len, 1.0)
        
        position_bonus = 0.0
        for kw in matched_keywords:
            pos = text.find(kw)
            if pos != -1:
                position_bonus += 0.1 * (1 - pos / text_len)
        
        count_bonus = min(len(matched_keywords) * 0.1, 0.3)
        
        confidence = min(base_confidence + position_bonus + count_bonus, 1.0)
        return round(confidence, 3)
    
    def _analyze_with_context(self, text: str, current_intents: List[Intent]) -> List[Intent]:
        """基于上下文分析意图"""
        context_intents = []
        
        if not self._conversation_history:
            return context_intents
        
        last_turn = self._conversation_history[-1] if self._conversation_history else None
        if not last_turn:
            return context_intents
        
        last_user_input = last_turn.get("user_input", "")
        last_system_response = last_turn.get("system_response", "")
        
        for pronoun, info in self.PRONOUNS.items():
            if pronoun in text:
                context_intents.append(Intent(
                    name="reference_resolution",
                    category=IntentCategory.CLARIFICATION,
                    confidence=0.8,
                    keywords=[pronoun],
                    entities={"pronoun": pronoun, "pronoun_info": info},
                    context_relevance=0.9,
                    priority=8
                ))
                break
        
        follow_up_patterns = [
            (r'怎么样', "follow_up_status"),
            (r'为什么呢', "follow_up_reason"),
            (r'为什么', "follow_up_reason"),
            (r'怎么', "follow_up_method"),
            (r'如何', "follow_up_method"),
            (r'还有呢', "follow_up_more"),
            (r'然后呢', "follow_up_continue"),
        ]
        
        for pattern, follow_up_type in follow_up_patterns:
            if re.search(pattern, text) and len(text) < 10:
                context_intents.append(Intent(
                    name=follow_up_type,
                    category=IntentCategory.CONTINUATION,
                    confidence=0.85,
                    keywords=[pattern],
                    context_relevance=0.95,
                    priority=8
                ))
                break
        
        if self._last_intent:
            if self._last_intent.name in ["emotional_sad", "emotional_happy", "emotional_angry", "emotional_anxious"]:
                if len(text) < 20 and not any(i.category == IntentCategory.EMOTIONAL for i in current_intents):
                    context_intents.append(Intent(
                        name="emotional_continuation",
                        category=IntentCategory.EMOTIONAL,
                        confidence=0.7,
                        context_relevance=0.8,
                        priority=7
                    ))
        
        return context_intents
    
    def _merge_intents(self, intents1: List[Intent], intents2: List[Intent]) -> List[Intent]:
        """合并意图列表"""
        merged = list(intents1)
        for intent in intents2:
            existing = next((i for i in merged if i.name == intent.name), None)
            if existing:
                existing.confidence = max(existing.confidence, intent.confidence)
                existing.context_relevance = max(existing.context_relevance, intent.context_relevance)
            else:
                merged.append(intent)
        return merged
    
    def _analyze_topic(self, text: str) -> Tuple[Optional[str], bool]:
        """分析话题"""
        detected_topic = None
        max_matches = 0
        
        for topic, keywords in self.TOPIC_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in text.lower())
            if matches > max_matches:
                max_matches = matches
                detected_topic = topic
        
        is_continuation = False
        if self._current_topic and detected_topic:
            is_continuation = (detected_topic == self._current_topic)
        elif self._current_topic and not detected_topic:
            if len(text) < 15:
                detected_topic = self._current_topic
                is_continuation = True
        
        return detected_topic, is_continuation
    
    def _analyze_sentiment(self, text: str) -> str:
        """分析情感"""
        positive_count = sum(1 for kw in self.SENTIMENT_KEYWORDS["positive"] if kw in text)
        negative_count = sum(1 for kw in self.SENTIMENT_KEYWORDS["negative"] if kw in text)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"
    
    def _extract_entities(self, text: str) -> Dict[str, Any]:
        """提取实体"""
        entities = {}
        
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, text)
        if urls:
            entities["urls"] = urls
        
        number_pattern = r'\d+(?:\.\d+)?'
        numbers = re.findall(number_pattern, text)
        if numbers:
            entities["numbers"] = numbers
        
        time_patterns = [
            (r'(\d{1,2})[点时](\d{1,2})分?', "time"),
            (r'(\d{4})年(\d{1,2})月(\d{1,2})日?', "date"),
            (r'今天|明天|后天|昨天|前天', "relative_date"),
        ]
        
        for pattern, entity_type in time_patterns:
            matches = re.findall(pattern, text)
            if matches:
                entities[entity_type] = matches
        
        name_patterns = [
            r'我叫([^\s，。！？]+)',
            r'我的名字是([^\s，。！？]+)',
        ]
        for pattern in name_patterns:
            match = re.search(pattern, text)
            if match:
                entities["user_name"] = match.group(1)
                break
        
        return entities
    
    def _resolve_entities(self, entities: Dict[str, Any], text: str) -> Dict[str, Any]:
        """消解实体（处理代词等）"""
        resolved = dict(entities)
        
        for pronoun, info in self.PRONOUNS.items():
            if pronoun in text:
                if self._entity_cache:
                    cache_key = info["type"]
                    if cache_key in self._entity_cache:
                        resolved[f"resolved_{pronoun}"] = self._entity_cache[cache_key]
        
        return resolved
    
    def _get_profile_context(self, profile: Dict[str, Any]) -> str:
        """获取用户画像上下文"""
        parts = []
        
        basic = profile.get("basic_info", {})
        if basic.get("name"):
            parts.append(f"用户名: {basic['name']}")
        if basic.get("occupation"):
            parts.append(f"职业: {basic['occupation']}")
        
        prefs = profile.get("preferences", {})
        if prefs.get("interests"):
            parts.append(f"兴趣: {', '.join(prefs['interests'][:3])}")
        
        return "; ".join(parts) if parts else ""
    
    def _get_memory_context(self, memories: List[str]) -> str:
        """获取记忆上下文"""
        if not memories:
            return ""
        return "; ".join(memories[:3])
    
    def _get_knowledge_context(self, knowledge: List[str]) -> str:
        """获取知识库上下文"""
        if not knowledge:
            return ""
        return "; ".join(knowledge[:3])
    
    def _adjust_confidence_with_context(
        self,
        intents: List[Intent],
        context_used: List[ContextInfo],
        sentiment: str
    ) -> List[Intent]:
        """根据上下文调整置信度"""
        for intent in intents:
            if intent.context_relevance > 0:
                intent.confidence = min(intent.confidence * (1 + intent.context_relevance * 0.3), 1.0)
            
            if intent.category == IntentCategory.EMOTIONAL:
                if sentiment == "negative" and "sad" in intent.name:
                    intent.confidence *= 1.2
                elif sentiment == "positive" and "happy" in intent.name:
                    intent.confidence *= 1.2
        
        return intents
    
    def _suggest_actions(
        self,
        primary_intent: Intent,
        topic: Optional[str],
        sentiment: str
    ) -> List[str]:
        """建议后续动作"""
        actions = []
        
        if primary_intent.category == IntentCategory.EMOTIONAL:
            actions.append("provide_emotional_support")
            if sentiment == "negative":
                actions.append("ask_clarifying_question")
        
        if primary_intent.category == IntentCategory.CONTINUATION:
            actions.append("use_previous_context")
            actions.append("generate_related_content")
        
        if primary_intent.category == IntentCategory.CLARIFICATION:
            actions.append("provide_detailed_explanation")
            actions.append("use_examples")
        
        if topic:
            actions.append(f"focus_on_{topic}_topic")
        
        if primary_intent.name == "general_query" and primary_intent.confidence < 0.5:
            actions.append("search_knowledge_base")
            actions.append("use_api_fallback")
        
        return actions
    
    def update_entity_cache(self, entities: Dict[str, Any]) -> None:
        """更新实体缓存"""
        for key, value in entities.items():
            if key in ["user_name", "urls"]:
                self._entity_cache[key] = value
    
    def get_current_topic(self) -> Optional[str]:
        """获取当前话题"""
        return self._current_topic
    
    def get_topic_history(self) -> List[str]:
        """获取话题历史"""
        return self._topic_history.copy()
    
    def clear_context(self) -> None:
        """清空上下文"""
        self._conversation_history = []
        self._current_topic = None
        self._topic_history = []
        self._entity_cache = {}
        self._last_intent = None


_unified_analyzer: Optional[UnifiedIntentAnalyzer] = None


def get_unified_intent_analyzer() -> UnifiedIntentAnalyzer:
    """获取联合意图分析器单例"""
    global _unified_analyzer
    if _unified_analyzer is None:
        _unified_analyzer = UnifiedIntentAnalyzer()
    return _unified_analyzer
