"""
增强版意图识别器
结合本地知识库、语义相似度、用户画像等多维度进行意图识别
"""

from typing import List, Dict, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import re
import time
from functools import lru_cache

from .semantic_similarity import (
    SemanticSimilarityCalculator,
    get_semantic_calculator,
    SynonymDictionary
)


class IntentCategory(Enum):
    QUERY = "query"
    COMMAND = "command"
    SOCIAL = "social"
    EMOTIONAL = "emotional"
    CONTINUATION = "continuation"
    CLARIFICATION = "clarification"
    FEEDBACK = "feedback"
    KNOWLEDGE = "knowledge"
    SYSTEM = "system"


class IntentPriority(Enum):
    CRITICAL = 10
    HIGH = 8
    MEDIUM = 5
    LOW = 3
    MINIMAL = 1


@dataclass
class IntentMatch:
    name: str
    category: IntentCategory
    confidence: float
    priority: int
    keywords: List[str] = field(default_factory=list)
    semantic_score: float = 0.0
    knowledge_score: float = 0.0
    context_score: float = 0.0
    combined_score: float = 0.0
    matched_patterns: List[str] = field(default_factory=list)
    entities: Dict[str, Any] = field(default_factory=dict)
    suggested_action: Optional[str] = None
    local_function: Optional[str] = None


@dataclass
class IntentAnalysisResult:
    primary_intent: IntentMatch
    secondary_intents: List[IntentMatch] = field(default_factory=list)
    all_candidates: List[IntentMatch] = field(default_factory=list)
    topic: Optional[str] = None
    sentiment: str = "neutral"
    entities: Dict[str, Any] = field(default_factory=dict)
    context_used: Dict[str, Any] = field(default_factory=dict)
    knowledge_matches: List[Dict] = field(default_factory=list)
    analysis_metadata: Dict[str, Any] = field(default_factory=dict)


class IntentPatternRegistry:
    """意图模式注册表"""
    
    INTENT_PATTERNS = {
        "greeting": {
            "patterns": [r'你好', r'您好', r'嗨', r'哈喽', r'hello', r'hi', r'早上好', r'下午好', r'晚上好'],
            "category": IntentCategory.SOCIAL,
            "priority": IntentPriority.HIGH.value,
            "semantic_group": "greeting",
            "local_function": "respond_greeting",
            "keywords": ["你好", "您好", "嗨", "哈喽", "hello", "hi"],
        },
        "farewell": {
            "patterns": [r'再见', r'拜拜', r'bye', r'晚安', r'下次见', r'告辞', r'先走了'],
            "category": IntentCategory.SOCIAL,
            "priority": IntentPriority.HIGH.value,
            "semantic_group": "farewell",
            "local_function": "respond_farewell",
            "keywords": ["再见", "拜拜", "bye", "晚安"],
        },
        "gratitude": {
            "patterns": [r'谢谢', r'感谢', r'多谢', r'thanks', r'thank', r'谢谢你'],
            "category": IntentCategory.SOCIAL,
            "priority": IntentPriority.HIGH.value,
            "semantic_group": "gratitude",
            "local_function": "respond_gratitude",
            "keywords": ["谢谢", "感谢", "多谢", "thanks"],
        },
        "ask_time": {
            "patterns": [r'几点', r'现在.*时间', r'今天.*几号', r'星期几', r'日期', r'现在几点'],
            "category": IntentCategory.QUERY,
            "priority": IntentPriority.MEDIUM.value,
            "semantic_group": "time",
            "local_function": "get_current_time",
            "keywords": ["几点", "时间", "日期", "星期"],
        },
        "ask_weather": {
            "patterns": [r'天气', r'气温', r'温度', r'下雨', r'晴天', r'阴天', r'雪', r'风'],
            "category": IntentCategory.QUERY,
            "priority": IntentPriority.MEDIUM.value,
            "semantic_group": "weather",
            "local_function": "get_weather",
            "keywords": ["天气", "气温", "温度", "下雨"],
        },
        "ask_name": {
            "patterns": [r'你.*名字', r'你叫什么', r'你是谁', r'自我介绍', r'你的名字'],
            "category": IntentCategory.QUERY,
            "priority": IntentPriority.MEDIUM.value,
            "semantic_group": "identity",
            "local_function": "introduce_self",
            "keywords": ["名字", "叫什么", "你是谁"],
        },
        "set_name": {
            "patterns": [r'我的名字叫', r'我叫', r'你可以叫我', r'我的名字是'],
            "category": IntentCategory.COMMAND,
            "priority": IntentPriority.HIGH.value,
            "semantic_group": "identity",
            "local_function": "set_user_name",
            "keywords": ["我叫", "我的名字"],
        },
        "set_system_name": {
            "patterns": [r'系统名字叫', r'你的名字叫', r'你改名叫', r'你现在改名叫'],
            "category": IntentCategory.COMMAND,
            "priority": IntentPriority.HIGH.value,
            "semantic_group": "identity",
            "local_function": "set_system_name",
            "keywords": ["你的名字叫", "你改名"],
        },
        "clear_memory": {
            "patterns": [r'/clear', r'清空记忆', r'清除记忆', r'忘记一切', r'重置记忆'],
            "category": IntentCategory.SYSTEM,
            "priority": IntentPriority.CRITICAL.value,
            "semantic_group": "system",
            "local_function": "clear_memory",
            "keywords": ["/clear", "清空记忆", "清除记忆"],
        },
        "admin_login": {
            "patterns": [r'/admin', r'管理员登录', r'登录管理员'],
            "category": IntentCategory.SYSTEM,
            "priority": IntentPriority.CRITICAL.value,
            "semantic_group": "system",
            "local_function": "admin_login",
            "keywords": ["/admin", "管理员登录"],
        },
        "help": {
            "patterns": [r'帮助', r'help', r'怎么用', r'使用方法', r'功能介绍', r'能做什么'],
            "category": IntentCategory.QUERY,
            "priority": IntentPriority.MEDIUM.value,
            "semantic_group": "help",
            "local_function": "show_help",
            "keywords": ["帮助", "help", "怎么用", "功能"],
        },
        "continuation": {
            "patterns": [r'再来一个', r'再来', r'新的', r'另一个', r'继续', r'还有呢', r'然后呢'],
            "category": IntentCategory.CONTINUATION,
            "priority": IntentPriority.HIGH.value,
            "semantic_group": "continuation",
            "local_function": "continue_previous",
            "keywords": ["再来", "继续", "还有呢"],
        },
        "clarification": {
            "patterns": [r'什么意思', r'是什么', r'能详细说说', r'能再解释', r'具体点', r'展开说说'],
            "category": IntentCategory.CLARIFICATION,
            "priority": IntentPriority.MEDIUM.value,
            "semantic_group": "clarification",
            "local_function": "clarify_response",
            "keywords": ["什么意思", "详细", "解释"],
        },
        "why_question": {
            "patterns": [r'为什么', r'为啥', r'怎么会', r'原因是'],
            "category": IntentCategory.QUERY,
            "priority": IntentPriority.MEDIUM.value,
            "semantic_group": "inquiry",
            "local_function": "explain_reason",
            "keywords": ["为什么", "为啥", "原因"],
        },
        "how_to": {
            "patterns": [r'怎么', r'如何', r'怎样', r'方法', r'步骤'],
            "category": IntentCategory.QUERY,
            "priority": IntentPriority.MEDIUM.value,
            "semantic_group": "instruction",
            "local_function": "provide_instructions",
            "keywords": ["怎么", "如何", "方法"],
        },
        "what_is": {
            "patterns": [r'是什么', r'什么是', r'介绍一下', r'解释一下'],
            "category": IntentCategory.QUERY,
            "priority": IntentPriority.MEDIUM.value,
            "semantic_group": "definition",
            "local_function": "explain_concept",
            "keywords": ["是什么", "什么是", "介绍"],
        },
        "opinion": {
            "patterns": [r'你觉得', r'你认为', r'怎么看', r'想法', r'观点'],
            "category": IntentCategory.QUERY,
            "priority": IntentPriority.MEDIUM.value,
            "semantic_group": "opinion",
            "local_function": "share_opinion",
            "keywords": ["你觉得", "你认为", "怎么看"],
        },
        "comparison": {
            "patterns": [r'区别', r'比较', r'哪个好', r'对比', r'差异', r'不同'],
            "category": IntentCategory.QUERY,
            "priority": IntentPriority.MEDIUM.value,
            "semantic_group": "comparison",
            "local_function": "compare_items",
            "keywords": ["区别", "比较", "对比"],
        },
        "recommendation": {
            "patterns": [r'推荐', r'建议', r'有什么好', r'安利'],
            "category": IntentCategory.QUERY,
            "priority": IntentPriority.MEDIUM.value,
            "semantic_group": "recommendation",
            "local_function": "provide_recommendation",
            "keywords": ["推荐", "建议"],
        },
        "emotional_sad": {
            "patterns": [r'伤心', r'难过', r'悲伤', r'痛苦', r'哭', r'不开心', r'郁闷', r'沮丧', r'失落'],
            "category": IntentCategory.EMOTIONAL,
            "priority": IntentPriority.HIGH.value,
            "semantic_group": "sadness",
            "local_function": "provide_emotional_support",
            "keywords": ["伤心", "难过", "悲伤", "痛苦"],
        },
        "emotional_happy": {
            "patterns": [r'开心', r'高兴', r'快乐', r'兴奋', r'喜悦', r'幸福', r'太棒了'],
            "category": IntentCategory.EMOTIONAL,
            "priority": IntentPriority.MEDIUM.value,
            "semantic_group": "happiness",
            "local_function": "share_happiness",
            "keywords": ["开心", "高兴", "快乐"],
        },
        "emotional_angry": {
            "patterns": [r'生气', r'愤怒', r'恼火', r'不爽', r'讨厌', r'烦'],
            "category": IntentCategory.EMOTIONAL,
            "priority": IntentPriority.HIGH.value,
            "semantic_group": "anger",
            "local_function": "handle_anger",
            "keywords": ["生气", "愤怒", "恼火"],
        },
        "emotional_anxious": {
            "patterns": [r'焦虑', r'担心', r'紧张', r'害怕', r'恐惧', r'不安'],
            "category": IntentCategory.EMOTIONAL,
            "priority": IntentPriority.HIGH.value,
            "semantic_group": "anxiety",
            "local_function": "calm_anxiety",
            "keywords": ["焦虑", "担心", "紧张", "害怕"],
        },
        "feedback_positive": {
            "patterns": [r'很好', r'不错', r'很棒', r'厉害', r'优秀', r'完美', r'赞'],
            "category": IntentCategory.FEEDBACK,
            "priority": IntentPriority.MEDIUM.value,
            "semantic_group": "positive_feedback",
            "local_function": "acknowledge_positive_feedback",
            "keywords": ["很好", "不错", "很棒", "厉害"],
        },
        "feedback_negative": {
            "patterns": [r'不好', r'不行', r'错误', r'不对', r'有问题', r'不满意', r'差评'],
            "category": IntentCategory.FEEDBACK,
            "priority": IntentPriority.HIGH.value,
            "semantic_group": "negative_feedback",
            "local_function": "handle_negative_feedback",
            "keywords": ["不好", "错误", "有问题"],
        },
        "knowledge_query": {
            "patterns": [r'查询', r'搜索', r'查找', r'寻找', r'有没有.*知识'],
            "category": IntentCategory.KNOWLEDGE,
            "priority": IntentPriority.MEDIUM.value,
            "semantic_group": "knowledge",
            "local_function": "search_knowledge_base",
            "keywords": ["查询", "搜索", "查找"],
        },
        "add_knowledge": {
            "patterns": [r'添加知识', r'记录知识', r'保存知识', r'记住.*知识'],
            "category": IntentCategory.KNOWLEDGE,
            "priority": IntentPriority.HIGH.value,
            "semantic_group": "knowledge",
            "local_function": "add_to_knowledge_base",
            "keywords": ["添加知识", "记录知识", "保存知识"],
        },
        "parse_url": {
            "patterns": [r'https?://', r'解析.*网页', r'分析.*网站'],
            "category": IntentCategory.QUERY,
            "priority": IntentPriority.MEDIUM.value,
            "semantic_group": "web_parsing",
            "local_function": "parse_web_content",
            "keywords": ["http", "网页", "网站"],
        },
        "chat": {
            "patterns": [r'聊天', r'聊聊', r'说说话', r'陪我聊'],
            "category": IntentCategory.SOCIAL,
            "priority": IntentPriority.LOW.value,
            "semantic_group": "chat",
            "local_function": "start_conversation",
            "keywords": ["聊天", "聊聊"],
        },
    }
    
    TOPIC_KEYWORDS = {
        "programming": ["编程", "代码", "程序", "开发", "python", "java", "javascript", "函数", "变量", "算法"],
        "learning": ["学习", "读书", "课程", "培训", "教育", "知识", "技能", "考试", "学校"],
        "work": ["工作", "职业", "上班", "职场", "事业", "项目", "公司", "工资", "加班"],
        "life": ["生活", "日常", "习惯", "健康", "运动", "饮食", "睡眠", "家庭"],
        "entertainment": ["电影", "音乐", "游戏", "小说", "综艺", "直播", "动漫", "体育"],
        "food": ["美食", "吃的", "餐厅", "菜", "食物", "烹饪", "食材", "口味"],
        "travel": ["旅游", "旅行", "景点", "度假", "出游", "酒店", "机票", "签证"],
        "finance": ["投资", "理财", "股票", "基金", "财务", "钱", "银行", "贷款"],
        "relationship": ["朋友", "家人", "恋爱", "感情", "关系", "婚姻", "亲情"],
        "technology": ["科技", "AI", "人工智能", "机器学习", "数据", "算法", "模型"],
        "health": ["健康", "运动", "健身", "医疗", "养生", "保健", "体检"],
    }
    
    @classmethod
    def get_intent_names(cls) -> List[str]:
        """获取所有意图名称"""
        return list(cls.INTENT_PATTERNS.keys())
    
    @classmethod
    def get_intent_config(cls, intent_name: str) -> Optional[Dict]:
        """获取意图配置"""
        return cls.INTENT_PATTERNS.get(intent_name)


class EnhancedIntentRecognizer:
    """增强版意图识别器"""
    
    def __init__(
        self,
        knowledge_manager=None,
        memory_manager=None
    ):
        self.semantic_calc = get_semantic_calculator()
        self.pattern_registry = IntentPatternRegistry()
        self.knowledge_manager = knowledge_manager
        self.memory_manager = memory_manager
        
        self._conversation_history: List[Dict] = []
        self._current_topic: Optional[str] = None
        self._topic_history: List[str] = []
        self._last_intent: Optional[IntentMatch] = None
        self._entity_cache: Dict[str, Any] = {}
    
    def set_knowledge_manager(self, manager):
        """设置知识管理器"""
        self.knowledge_manager = manager
    
    def set_memory_manager(self, manager):
        """设置记忆管理器"""
        self.memory_manager = manager
    
    def analyze(
        self,
        user_input: str,
        conversation_history: List[Dict] = None,
        context: Dict[str, Any] = None
    ) -> IntentAnalysisResult:
        """综合分析用户意图"""
        start_time = time.time()
        
        if conversation_history:
            self._conversation_history = conversation_history
        
        context = context or {}
        
        candidates = self._recognize_all_intents(user_input)
        
        knowledge_matches = []
        if self.knowledge_manager:
            knowledge_matches = self._search_knowledge(user_input)
            candidates = self._enhance_with_knowledge(candidates, knowledge_matches)
        
        candidates = self._calculate_semantic_scores(user_input, candidates)
        
        candidates = self._apply_context_boost(user_input, candidates, context)
        
        candidates.sort(key=lambda x: x.combined_score, reverse=True)
        
        primary_intent = candidates[0] if candidates else self._create_unknown_intent()
        secondary_intents = candidates[1:4] if len(candidates) > 1 else []
        
        topic = self._detect_topic(user_input)
        sentiment = self._analyze_sentiment(user_input)
        entities = self._extract_entities(user_input)
        
        context_used = self._build_context_summary(context, knowledge_matches)
        
        self._last_intent = primary_intent
        if topic:
            self._current_topic = topic
            self._topic_history.append(topic)
            if len(self._topic_history) > 10:
                self._topic_history.pop(0)
        
        analysis_time = (time.time() - start_time) * 1000
        
        return IntentAnalysisResult(
            primary_intent=primary_intent,
            secondary_intents=secondary_intents,
            all_candidates=candidates[:10],
            topic=topic,
            sentiment=sentiment,
            entities=entities,
            context_used=context_used,
            knowledge_matches=knowledge_matches[:3],
            analysis_metadata={
                "analysis_time_ms": round(analysis_time, 2),
                "candidate_count": len(candidates),
                "has_knowledge_match": len(knowledge_matches) > 0,
                "topic_continuation": topic == self._current_topic,
            }
        )
    
    def _recognize_all_intents(self, text: str) -> List[IntentMatch]:
        """识别所有可能的意图"""
        candidates = []
        text_lower = text.lower()
        
        for intent_name, config in self.pattern_registry.INTENT_PATTERNS.items():
            matched_patterns = []
            matched_keywords = []
            
            for pattern in config["patterns"]:
                if re.search(pattern, text_lower):
                    matched_patterns.append(pattern)
            
            if config.get("keywords"):
                for keyword in config["keywords"]:
                    if keyword in text_lower:
                        matched_keywords.append(keyword)
            
            if matched_patterns or matched_keywords:
                confidence = self._calculate_base_confidence(
                    text, matched_patterns, matched_keywords
                )
                
                intent = IntentMatch(
                    name=intent_name,
                    category=config["category"],
                    confidence=confidence,
                    priority=config["priority"],
                    keywords=list(set(matched_keywords)),
                    matched_patterns=matched_patterns,
                    local_function=config.get("local_function"),
                    suggested_action=config.get("local_function"),
                )
                candidates.append(intent)
        
        if not candidates:
            candidates.append(self._create_unknown_intent())
        
        return candidates
    
    def _calculate_base_confidence(
        self,
        text: str,
        matched_patterns: List[str],
        matched_keywords: List[str]
    ) -> float:
        """计算基础置信度"""
        if not text:
            return 0.0
        
        text_len = len(text)
        
        pattern_score = 0.0
        for pattern in matched_patterns:
            pattern_len = len(pattern.replace(r'.*', '').replace(r'.', ''))
            pattern_score += pattern_len / text_len
        
        keyword_score = sum(len(kw) for kw in matched_keywords) / text_len if matched_keywords else 0
        
        position_bonus = 0.0
        for kw in matched_keywords:
            pos = text.find(kw)
            if pos != -1:
                position_bonus += 0.1 * (1 - pos / text_len)
        
        count_bonus = min(len(matched_patterns) * 0.1 + len(matched_keywords) * 0.05, 0.3)
        
        confidence = min((pattern_score + keyword_score) / 2 + position_bonus + count_bonus, 1.0)
        return round(confidence, 3)
    
    def _search_knowledge(self, text: str) -> List[Dict]:
        """搜索知识库"""
        if not self.knowledge_manager:
            return []
        
        try:
            results = self.knowledge_manager.search_knowledge(text, threshold=0.3)
            return results
        except Exception:
            return []
    
    def _enhance_with_knowledge(
        self,
        candidates: List[IntentMatch],
        knowledge_matches: List[Dict]
    ) -> List[IntentMatch]:
        """使用知识库增强意图识别"""
        if not knowledge_matches:
            return candidates
        
        knowledge_intent = IntentMatch(
            name="knowledge_match",
            category=IntentCategory.KNOWLEDGE,
            confidence=0.8,
            priority=IntentPriority.MEDIUM.value,
            knowledge_score=0.8,
            local_function="use_knowledge_base",
            suggested_action="use_knowledge_base",
        )
        
        for item in knowledge_matches[:3]:
            if isinstance(item, dict) and 'question' in item:
                similarity = self.semantic_calc.calculate_similarity(
                    knowledge_intent.name,
                    item.get('question', '')
                )
                if similarity.score > 0.5:
                    knowledge_intent.confidence = max(
                        knowledge_intent.confidence,
                        similarity.score
                    )
        
        candidates.append(knowledge_intent)
        return candidates
    
    def _calculate_semantic_scores(
        self,
        text: str,
        candidates: List[IntentMatch]
    ) -> List[IntentMatch]:
        """计算语义分数"""
        for intent in candidates:
            score, matched = self.semantic_calc.calculate_intent_similarity(
                text, intent.name
            )
            intent.semantic_score = score
            
            if matched:
                intent.keywords = list(set(intent.keywords + matched))
        
        return candidates
    
    def _apply_context_boost(
        self,
        text: str,
        candidates: List[IntentMatch],
        context: Dict[str, Any]
    ) -> List[IntentMatch]:
        """应用上下文增强"""
        for intent in candidates:
            boost = 0.0
            
            if self._last_intent:
                if intent.name == self._last_intent.name:
                    boost += 0.1
                
                if intent.category == self._last_intent.category:
                    boost += 0.05
            
            if self._current_topic:
                topic_keywords = self.pattern_registry.TOPIC_KEYWORDS.get(self._current_topic, [])
                if any(kw in text for kw in topic_keywords):
                    boost += 0.1
            
            intent.context_score = boost
            
            intent.combined_score = self._calculate_combined_score(intent)
        
        return candidates
    
    def _calculate_combined_score(self, intent: IntentMatch) -> float:
        """计算综合分数"""
        weights = {
            "confidence": 0.35,
            "semantic": 0.25,
            "priority": 0.15,
            "context": 0.15,
            "knowledge": 0.10,
        }
        
        normalized_priority = intent.priority / 10.0
        
        score = (
            intent.confidence * weights["confidence"] +
            intent.semantic_score * weights["semantic"] +
            normalized_priority * weights["priority"] +
            intent.context_score * weights["context"] +
            intent.knowledge_score * weights["knowledge"]
        )
        
        return round(score, 3)
    
    def _detect_topic(self, text: str) -> Optional[str]:
        """检测话题"""
        detected_topic = None
        max_matches = 0
        
        for topic, keywords in self.pattern_registry.TOPIC_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in text.lower())
            if matches > max_matches:
                max_matches = matches
                detected_topic = topic
        
        return detected_topic
    
    def _analyze_sentiment(self, text: str) -> str:
        """分析情感"""
        positive_words = ["好", "棒", "喜欢", "爱", "开心", "高兴", "感谢", "谢谢", "优秀", "完美"]
        negative_words = ["不好", "讨厌", "烦", "难过", "伤心", "生气", "愤怒", "失望", "糟糕"]
        
        positive_count = sum(1 for w in positive_words if w in text)
        negative_count = sum(1 for w in negative_words if w in text)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
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
    
    def _build_context_summary(
        self,
        context: Dict[str, Any],
        knowledge_matches: List[Dict]
    ) -> Dict[str, Any]:
        """构建上下文摘要"""
        summary = {
            "has_knowledge": len(knowledge_matches) > 0,
            "knowledge_count": len(knowledge_matches),
            "current_topic": self._current_topic,
            "last_intent": self._last_intent.name if self._last_intent else None,
        }
        
        summary.update(context)
        return summary
    
    def _create_unknown_intent(self) -> IntentMatch:
        """创建未知意图"""
        return IntentMatch(
            name="unknown",
            category=IntentCategory.QUERY,
            confidence=0.0,
            priority=IntentPriority.MINIMAL.value,
            local_function="use_api_fallback",
            suggested_action="use_api_fallback",
        )
    
    def get_local_function(self, intent_name: str) -> Optional[str]:
        """获取意图对应的本地功能"""
        config = self.pattern_registry.get_intent_config(intent_name)
        if config:
            return config.get("local_function")
        return None
    
    def get_suggested_action(self, intent_name: str) -> Optional[str]:
        """获取建议的动作"""
        return self.get_local_function(intent_name)
    
    def expand_query_with_synonyms(self, query: str) -> List[str]:
        """使用同义词扩展查询"""
        return self.semantic_calc.expand_query(query)
    
    def get_current_topic(self) -> Optional[str]:
        """获取当前话题"""
        return self._current_topic
    
    def get_topic_history(self) -> List[str]:
        """获取话题历史"""
        return self._topic_history.copy()
    
    def clear_context(self):
        """清空上下文"""
        self._conversation_history = []
        self._current_topic = None
        self._topic_history = []
        self._last_intent = None
        self._entity_cache = {}


_intent_recognizer: Optional[EnhancedIntentRecognizer] = None


def get_intent_recognizer() -> EnhancedIntentRecognizer:
    """获取意图识别器单例"""
    global _intent_recognizer
    if _intent_recognizer is None:
        _intent_recognizer = EnhancedIntentRecognizer()
    return _intent_recognizer
