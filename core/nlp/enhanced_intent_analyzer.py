"""
高级意图分析器 - 增强版联合上下文分析
添加语义相似度、意图组合、时间衰减、动态权重、情感强度等高级功能
"""

from typing import List, Dict, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import re
import time
import math
from collections import defaultdict
from functools import lru_cache


class SentimentIntensity(Enum):
    VERY_WEAK = 1
    WEAK = 2
    MODERATE = 3
    STRONG = 4
    VERY_STRONG = 5


class TopicRelation(Enum):
    SAME = "same"
    RELATED = "related"
    DIFFERENT = "different"


@dataclass
class EnhancedIntent:
    name: str
    category: str
    confidence: float
    keywords: List[str] = field(default_factory=list)
    entities: Dict[str, Any] = field(default_factory=dict)
    context_relevance: float = 0.0
    priority: int = 0
    semantic_score: float = 0.0
    time_decay: float = 1.0
    combined_score: float = 0.0


@dataclass
class EnhancedAnalysisResult:
    primary_intent: EnhancedIntent
    secondary_intents: List[EnhancedIntent] = field(default_factory=list)
    intent_combinations: List[Tuple[str, float]] = field(default_factory=list)
    topic: Optional[str] = None
    topic_continuation: bool = False
    topic_relation: TopicRelation = TopicRelation.DIFFERENT
    sentiment: str = "neutral"
    sentiment_intensity: SentimentIntensity = SentimentIntensity.MODERATE
    entities: Dict[str, Any] = field(default_factory=dict)
    suggested_actions: List[str] = field(default_factory=list)
    context_quality: float = 0.0
    analysis_metadata: Dict[str, Any] = field(default_factory=dict)


class SemanticCalculator:
    """语义相似度计算器"""
    
    WORD_VECTORS = {
        "学习": {"学习": 1.0, "读书": 0.8, "课程": 0.7, "培训": 0.7, "教育": 0.6, "知识": 0.6},
        "工作": {"工作": 1.0, "职业": 0.8, "上班": 0.7, "职场": 0.7, "事业": 0.6, "项目": 0.5},
        "编程": {"编程": 1.0, "代码": 0.9, "程序": 0.8, "开发": 0.8, "python": 0.7, "java": 0.7},
        "开心": {"开心": 1.0, "高兴": 0.9, "快乐": 0.9, "兴奋": 0.7, "喜悦": 0.8, "幸福": 0.7},
        "难过": {"难过": 1.0, "伤心": 0.9, "悲伤": 0.9, "痛苦": 0.8, "郁闷": 0.7, "沮丧": 0.7},
        "生气": {"生气": 1.0, "愤怒": 0.9, "恼火": 0.8, "不爽": 0.7, "讨厌": 0.6, "烦": 0.6},
    }
    
    @classmethod
    def calculate_similarity(cls, word1: str, word2: str) -> float:
        """计算两个词的语义相似度"""
        if word1 == word2:
            return 1.0
        
        if word1 in cls.WORD_VECTORS:
            return cls.WORD_VECTORS[word1].get(word2, 0.0)
        
        if word2 in cls.WORD_VECTORS:
            return cls.WORD_VECTORS[word2].get(word1, 0.0)
        
        common_chars = set(word1) & set(word2)
        if not common_chars:
            return 0.0
        
        return len(common_chars) / max(len(set(word1) | set(word2)), 1)
    
    @classmethod
    def text_similarity(cls, text1: str, text2: str) -> float:
        """计算两段文本的相似度"""
        words1 = set(text1.lower())
        words2 = set(text2.lower())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union) if union else 0.0


class TimeDecayCalculator:
    """时间衰减计算器"""
    
    HALF_LIFE_SECONDS = 300
    
    @classmethod
    def calculate_decay(cls, timestamp: float, current_time: float = None) -> float:
        """计算时间衰减因子"""
        if current_time is None:
            current_time = time.time()
        
        elapsed = current_time - timestamp
        
        if elapsed <= 0:
            return 1.0
        
        decay = math.exp(-0.693 * elapsed / cls.HALF_LIFE_SECONDS)
        return max(decay, 0.1)
    
    @classmethod
    def calculate_weighted_relevance(
        cls,
        relevance: float,
        timestamp: float,
        current_time: float = None
    ) -> float:
        """计算加权相关性"""
        decay = cls.calculate_decay(timestamp, current_time)
        return relevance * decay


class SentimentAnalyzer:
    """增强版情感分析器"""
    
    INTENSITY_KEYWORDS = {
        SentimentIntensity.VERY_STRONG: [
            "非常", "极其", "特别", "超级", "无比", "极其", "太...了", "死...了"
        ],
        SentimentIntensity.STRONG: [
            "很", "好", "真", "实在", "确实", "真的", "相当"
        ],
        SentimentIntensity.MODERATE: [
            "比较", "还算", "挺", "蛮", "有些", "有点"
        ],
        SentimentIntensity.WEAK: [
            "稍微", "略微", "一点", "些许"
        ],
        SentimentIntensity.VERY_WEAK: [
            "可能", "也许", "大概", "似乎"
        ],
    }
    
    SENTIMENT_SCORES = {
        "positive": {
            "好": 1, "棒": 2, "喜欢": 1, "爱": 2, "开心": 2, "高兴": 2,
            "感谢": 1, "谢谢": 1, "优秀": 2, "完美": 3, "厉害": 2,
            "太棒了": 3, "超级": 2, "非常": 1,
        },
        "negative": {
            "不好": -1, "讨厌": -2, "烦": -1, "难过": -2, "伤心": -2,
            "生气": -2, "愤怒": -3, "失望": -2, "糟糕": -2, "差": -1,
            "很糟": -2, "太差": -3,
        },
    }
    
    @classmethod
    def analyze_with_intensity(cls, text: str) -> Tuple[str, SentimentIntensity, float]:
        """分析情感及其强度"""
        positive_score = 0
        negative_score = 0
        
        for word, score in cls.SENTIMENT_SCORES["positive"].items():
            if word in text:
                positive_score += score
        
        for word, score in cls.SENTIMENT_SCORES["negative"].items():
            if word in text:
                negative_score += score
        
        intensity = cls._detect_intensity(text)
        
        total_score = positive_score + negative_score
        
        if positive_score > abs(negative_score):
            sentiment = "positive"
            adjusted_score = positive_score * cls._intensity_multiplier(intensity)
        elif negative_score < 0:
            sentiment = "negative"
            adjusted_score = abs(negative_score) * cls._intensity_multiplier(intensity)
        else:
            sentiment = "neutral"
            adjusted_score = 0
        
        return sentiment, intensity, adjusted_score
    
    @classmethod
    def _detect_intensity(cls, text: str) -> SentimentIntensity:
        """检测情感强度"""
        for intensity, keywords in cls.INTENSITY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    return intensity
        return SentimentIntensity.MODERATE
    
    @classmethod
    def _intensity_multiplier(cls, intensity: SentimentIntensity) -> float:
        """获取强度乘数"""
        multipliers = {
            SentimentIntensity.VERY_WEAK: 0.5,
            SentimentIntensity.WEAK: 0.75,
            SentimentIntensity.MODERATE: 1.0,
            SentimentIntensity.STRONG: 1.5,
            SentimentIntensity.VERY_STRONG: 2.0,
        }
        return multipliers.get(intensity, 1.0)


class TopicAnalyzer:
    """话题分析器"""
    
    TOPIC_RELATIONS = {
        ("programming", "technology"): 0.8,
        ("programming", "learning"): 0.7,
        ("learning", "work"): 0.6,
        ("work", "life"): 0.5,
        ("entertainment", "life"): 0.6,
        ("food", "life"): 0.7,
        ("travel", "life"): 0.7,
        ("finance", "work"): 0.6,
        ("relationship", "life"): 0.7,
    }
    
    @classmethod
    def get_relation(cls, topic1: str, topic2: str) -> Tuple[TopicRelation, float]:
        """获取两个话题的关系"""
        if topic1 == topic2:
            return TopicRelation.SAME, 1.0
        
        if (topic1, topic2) in cls.TOPIC_RELATIONS:
            similarity = cls.TOPIC_RELATIONS[(topic1, topic2)]
        elif (topic2, topic1) in cls.TOPIC_RELATIONS:
            similarity = cls.TOPIC_RELATIONS[(topic2, topic1)]
        else:
            similarity = 0.0
        
        if similarity >= 0.7:
            return TopicRelation.RELATED, similarity
        else:
            return TopicRelation.DIFFERENT, similarity
    
    @classmethod
    def predict_next_topic(cls, topic_history: List[str]) -> Optional[str]:
        """预测下一个话题"""
        if not topic_history:
            return None
        
        last_topic = topic_history[-1]
        related_topics = []
        
        for (t1, t2), similarity in cls.TOPIC_RELATIONS.items():
            if t1 == last_topic and similarity >= 0.6:
                related_topics.append((t2, similarity))
            elif t2 == last_topic and similarity >= 0.6:
                related_topics.append((t1, similarity))
        
        if related_topics:
            related_topics.sort(key=lambda x: x[1], reverse=True)
            return related_topics[0][0]
        
        return None


class IntentCombiner:
    """意图组合器"""
    
    COMBINATION_RULES = {
        ("greeting", "ask_name"): ("greeting_with_intro", 0.9),
        ("emotional_sad", "why_question"): ("emotional_inquiry", 0.85),
        ("how_to", "topic_specific"): ("how_to_guide", 0.8),
        ("recommendation", "comparison"): ("recommend_with_compare", 0.85),
        ("feedback_positive", "gratitude"): ("satisfied_thanks", 0.9),
        ("feedback_negative", "clarification"): ("complaint_detail", 0.85),
    }
    
    @classmethod
    def combine_intents(
        cls,
        intents: List[EnhancedIntent]
    ) -> List[Tuple[str, float]]:
        """组合多个意图"""
        combinations = []
        
        if len(intents) < 2:
            return combinations
        
        intent_names = [i.name for i in intents[:3]]
        
        for (i1, i2), (combined_name, score) in cls.COMBINATION_RULES.items():
            if i1 in intent_names and i2 in intent_names:
                avg_confidence = (
                    intents[intent_names.index(i1)].confidence +
                    intents[intent_names.index(i2)].confidence
                ) / 2
                combinations.append((combined_name, avg_confidence * score))
        
        return combinations


class EnhancedIntentAnalyzer:
    """增强版意图分析器"""
    
    INTENT_PATTERNS = {
        "greeting": {
            "patterns": [r'你好', r'您好', r'早上好', r'下午好', r'晚上好', r'嗨', r'哈喽'],
            "category": "social",
            "priority": 10,
            "semantic_group": "greeting",
        },
        "farewell": {
            "patterns": [r'再见', r'拜拜', r'晚安', r'bye', r'下次见'],
            "category": "social",
            "priority": 10,
            "semantic_group": "farewell",
        },
        "gratitude": {
            "patterns": [r'谢谢', r'感谢', r'多谢', r'thanks'],
            "category": "social",
            "priority": 8,
            "semantic_group": "gratitude",
        },
        "ask_time": {
            "patterns": [r'几点', r'时间', r'现在.*时间', r'今天.*几号', r'星期几'],
            "category": "query",
            "priority": 7,
            "semantic_group": "time",
        },
        "ask_weather": {
            "patterns": [r'天气', r'气温', r'温度', r'下雨', r'晴天'],
            "category": "query",
            "priority": 7,
            "semantic_group": "weather",
        },
        "continuation": {
            "patterns": [r'再来一个', r'再来', r'新的', r'另一个', r'继续', r'还有呢'],
            "category": "continuation",
            "priority": 8,
            "semantic_group": "continuation",
        },
        "clarification": {
            "patterns": [r'什么意思', r'是什么', r'能详细说说', r'能再解释', r'具体点'],
            "category": "clarification",
            "priority": 7,
            "semantic_group": "clarification",
        },
        "why_question": {
            "patterns": [r'为什么', r'怎么会', r'原因是'],
            "category": "query",
            "priority": 6,
            "semantic_group": "inquiry",
        },
        "how_to": {
            "patterns": [r'怎么', r'如何', r'怎样', r'方法'],
            "category": "query",
            "priority": 5,
            "semantic_group": "instruction",
        },
        "what_is": {
            "patterns": [r'是什么', r'什么是', r'介绍一下'],
            "category": "query",
            "priority": 5,
            "semantic_group": "definition",
        },
        "opinion": {
            "patterns": [r'你觉得', r'你认为', r'怎么看', r'想法'],
            "category": "query",
            "priority": 5,
            "semantic_group": "opinion",
        },
        "comparison": {
            "patterns": [r'区别', r'比较', r'哪个好', r'对比', r'差异'],
            "category": "query",
            "priority": 5,
            "semantic_group": "comparison",
        },
        "recommendation": {
            "patterns": [r'推荐', r'建议', r'有什么好'],
            "category": "query",
            "priority": 5,
            "semantic_group": "recommendation",
        },
        "emotional_sad": {
            "patterns": [r'伤心', r'难过', r'悲伤', r'痛苦', r'哭', r'不开心'],
            "category": "emotional",
            "priority": 9,
            "semantic_group": "sadness",
        },
        "emotional_happy": {
            "patterns": [r'开心', r'高兴', r'快乐', r'兴奋', r'喜悦', r'幸福'],
            "category": "emotional",
            "priority": 8,
            "semantic_group": "happiness",
        },
        "emotional_angry": {
            "patterns": [r'生气', r'愤怒', r'恼火', r'不爽', r'讨厌'],
            "category": "emotional",
            "priority": 9,
            "semantic_group": "anger",
        },
        "emotional_anxious": {
            "patterns": [r'焦虑', r'担心', r'紧张', r'害怕', r'恐惧'],
            "category": "emotional",
            "priority": 9,
            "semantic_group": "anxiety",
        },
        "feedback_positive": {
            "patterns": [r'很好', r'不错', r'很棒', r'厉害', r'优秀', r'完美'],
            "category": "feedback",
            "priority": 7,
            "semantic_group": "positive_feedback",
        },
        "feedback_negative": {
            "patterns": [r'不好', r'不行', r'错误', r'不对', r'有问题'],
            "category": "feedback",
            "priority": 7,
            "semantic_group": "negative_feedback",
        },
        "set_name": {
            "patterns": [r'我的名字叫', r'我叫', r'你可以叫我'],
            "category": "command",
            "priority": 9,
            "semantic_group": "identity",
        },
        "help": {
            "patterns": [r'帮助', r'help', r'怎么用', r'使用方法'],
            "category": "query",
            "priority": 6,
            "semantic_group": "help",
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
    
    def __init__(self):
        self._conversation_history: List[Dict[str, Any]] = []
        self._current_topic: Optional[str] = None
        self._topic_history: List[str] = []
        self._entity_cache: Dict[str, Any] = {}
        self._last_intent: Optional[EnhancedIntent] = None
        self._max_history: int = 20
        self._analysis_cache: Dict[str, EnhancedAnalysisResult] = {}
        self._cache_max_size: int = 100
    
    def analyze(
        self,
        user_input: str,
        conversation_history: List[Dict[str, str]] = None,
        memory_results: List[str] = None,
        knowledge_results: List[str] = None,
    ) -> EnhancedAnalysisResult:
        """增强版综合分析"""
        start_time = time.time()
        
        cache_key = self._generate_cache_key(user_input, conversation_history)
        if cache_key in self._analysis_cache:
            return self._analysis_cache[cache_key]
        
        if conversation_history:
            self._conversation_history = conversation_history
        
        intents = self._recognize_intents_enhanced(user_input)
        
        context_intents = self._analyze_with_context_enhanced(user_input, intents)
        intents = self._merge_intents_enhanced(intents, context_intents)
        
        for intent in intents:
            intent.semantic_score = self._calculate_semantic_score(user_input, intent)
            intent.time_decay = self._calculate_time_decay()
            intent.combined_score = self._calculate_combined_score(intent)
        
        topic, topic_continuation = self._analyze_topic_enhanced(user_input)
        topic_relation = self._get_topic_relation(topic)
        
        sentiment, sentiment_intensity, sentiment_score = SentimentAnalyzer.analyze_with_intensity(user_input)
        
        entities = self._extract_entities_enhanced(user_input)
        
        intent_combinations = IntentCombiner.combine_intents(intents)
        
        intents.sort(key=lambda x: x.combined_score, reverse=True)
        
        primary_intent = intents[0] if intents else EnhancedIntent(
            name="unknown",
            category="query",
            confidence=0.0
        )
        secondary_intents = intents[1:4] if len(intents) > 1 else []
        
        context_quality = self._calculate_context_quality(
            conversation_history, memory_results
        )
        
        suggested_actions = self._suggest_actions_enhanced(
            primary_intent, topic, sentiment, sentiment_intensity, context_quality
        )
        
        self._last_intent = primary_intent
        if topic:
            self._current_topic = topic
            self._topic_history.append(topic)
            if len(self._topic_history) > 10:
                self._topic_history.pop(0)
        
        result = EnhancedAnalysisResult(
            primary_intent=primary_intent,
            secondary_intents=secondary_intents,
            intent_combinations=intent_combinations,
            topic=topic,
            topic_continuation=topic_continuation,
            topic_relation=topic_relation,
            sentiment=sentiment,
            sentiment_intensity=sentiment_intensity,
            entities=entities,
            suggested_actions=suggested_actions,
            context_quality=context_quality,
            analysis_metadata={
                "analysis_time_ms": (time.time() - start_time) * 1000,
                "intent_count": len(intents),
                "has_combinations": len(intent_combinations) > 0,
            }
        )
        
        self._update_cache(cache_key, result)
        
        return result
    
    def _recognize_intents_enhanced(self, text: str) -> List[EnhancedIntent]:
        """增强版意图识别"""
        intents = []
        text_lower = text.lower()
        
        for intent_name, intent_config in self.INTENT_PATTERNS.items():
            matched_keywords = []
            for pattern in intent_config["patterns"]:
                if re.search(pattern, text_lower):
                    matched_keywords.append(pattern)
            
            if matched_keywords:
                confidence = self._calculate_confidence_enhanced(text, matched_keywords)
                intent = EnhancedIntent(
                    name=intent_name,
                    category=intent_config["category"],
                    confidence=confidence,
                    keywords=matched_keywords,
                    priority=intent_config["priority"]
                )
                intents.append(intent)
        
        if not intents:
            intents.append(EnhancedIntent(
                name="general_query",
                category="query",
                confidence=0.5,
                priority=1
            ))
        
        return intents
    
    def _calculate_confidence_enhanced(self, text: str, matched_keywords: List[str]) -> float:
        """增强版置信度计算"""
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
        
        length_penalty = 0.0
        if text_len < 5:
            length_penalty = 0.1
        
        confidence = min(base_confidence + position_bonus + count_bonus - length_penalty, 1.0)
        return max(round(confidence, 3), 0.0)
    
    def _calculate_semantic_score(self, text: str, intent: EnhancedIntent) -> float:
        """计算语义分数"""
        semantic_group = self.INTENT_PATTERNS.get(intent.name, {}).get("semantic_group", "")
        
        if not semantic_group:
            return 0.0
        
        max_similarity = 0.0
        for keyword in intent.keywords:
            similarity = SemanticCalculator.calculate_similarity(keyword, semantic_group)
            max_similarity = max(max_similarity, similarity)
        
        return max_similarity
    
    def _calculate_time_decay(self) -> float:
        """计算时间衰减"""
        if not self._conversation_history:
            return 1.0
        
        last_turn = self._conversation_history[-1]
        timestamp = last_turn.get("timestamp", time.time())
        
        return TimeDecayCalculator.calculate_decay(timestamp)
    
    def _calculate_combined_score(self, intent: EnhancedIntent) -> float:
        """计算综合分数"""
        weights = {
            "confidence": 0.4,
            "semantic": 0.2,
            "priority": 0.2,
            "context": 0.1,
            "time_decay": 0.1,
        }
        
        normalized_priority = intent.priority / 10.0
        
        score = (
            intent.confidence * weights["confidence"] +
            intent.semantic_score * weights["semantic"] +
            normalized_priority * weights["priority"] +
            intent.context_relevance * weights["context"] +
            intent.time_decay * weights["time_decay"]
        )
        
        return round(score, 3)
    
    def _analyze_with_context_enhanced(
        self,
        text: str,
        current_intents: List[EnhancedIntent]
    ) -> List[EnhancedIntent]:
        """增强版上下文分析"""
        context_intents = []
        
        if not self._conversation_history:
            return context_intents
        
        last_turn = self._conversation_history[-1]
        last_user_input = last_turn.get("user_input", "")
        
        text_similarity = SemanticCalculator.text_similarity(text, last_user_input)
        
        if text_similarity > 0.5:
            context_intents.append(EnhancedIntent(
                name="high_similarity_continuation",
                category="continuation",
                confidence=text_similarity,
                context_relevance=text_similarity,
                priority=7
            ))
        
        if len(text) < 10 and self._last_intent:
            context_intents.append(EnhancedIntent(
                name="short_follow_up",
                category="continuation",
                confidence=0.7,
                context_relevance=0.8,
                priority=6
            ))
        
        return context_intents
    
    def _merge_intents_enhanced(
        self,
        intents1: List[EnhancedIntent],
        intents2: List[EnhancedIntent]
    ) -> List[EnhancedIntent]:
        """增强版意图合并"""
        merged = list(intents1)
        for intent in intents2:
            existing = next((i for i in merged if i.name == intent.name), None)
            if existing:
                existing.confidence = max(existing.confidence, intent.confidence)
                existing.context_relevance = max(existing.context_relevance, intent.context_relevance)
            else:
                merged.append(intent)
        return merged
    
    def _analyze_topic_enhanced(self, text: str) -> Tuple[Optional[str], bool]:
        """增强版话题分析"""
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
    
    def _get_topic_relation(self, topic: Optional[str]) -> TopicRelation:
        """获取话题关系"""
        if not topic or not self._current_topic:
            return TopicRelation.DIFFERENT
        
        relation, _ = TopicAnalyzer.get_relation(topic, self._current_topic)
        return relation
    
    def _extract_entities_enhanced(self, text: str) -> Dict[str, Any]:
        """增强版实体提取"""
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
    
    def _calculate_context_quality(
        self,
        conversation_history: List[Dict[str, str]],
        memory_results: List[str]
    ) -> float:
        """计算上下文质量"""
        quality = 0.0
        
        if conversation_history:
            history_score = min(len(conversation_history) / 5.0, 1.0)
            quality += history_score * 0.5
        
        if memory_results:
            memory_score = min(len(memory_results) / 3.0, 1.0)
            quality += memory_score * 0.5
        
        return round(quality, 2)
    
    def _suggest_actions_enhanced(
        self,
        primary_intent: EnhancedIntent,
        topic: Optional[str],
        sentiment: str,
        sentiment_intensity: SentimentIntensity,
        context_quality: float
    ) -> List[str]:
        """增强版动作建议"""
        actions = []
        
        if primary_intent.category == "emotional":
            actions.append("provide_emotional_support")
            if sentiment_intensity in [SentimentIntensity.STRONG, SentimentIntensity.VERY_STRONG]:
                actions.append("priority_response")
            if sentiment == "negative":
                actions.append("ask_clarifying_question")
        
        if primary_intent.category == "continuation":
            actions.append("use_previous_context")
            actions.append("generate_related_content")
        
        if primary_intent.category == "clarification":
            actions.append("provide_detailed_explanation")
            actions.append("use_examples")
        
        if topic:
            actions.append(f"focus_on_{topic}_topic")
        
        if context_quality < 0.3:
            actions.append("request_more_context")
        
        if primary_intent.name == "general_query" and primary_intent.confidence < 0.5:
            actions.append("search_knowledge_base")
            actions.append("use_api_fallback")
        
        return actions
    
    def _generate_cache_key(
        self,
        user_input: str,
        conversation_history: List[Dict[str, str]]
    ) -> str:
        """生成缓存键"""
        history_hash = ""
        if conversation_history:
            last_input = conversation_history[-1].get("user_input", "") if conversation_history else ""
            history_hash = str(hash(last_input))
        
        return f"{hash(user_input)}_{history_hash}"
    
    def _update_cache(self, key: str, result: EnhancedAnalysisResult) -> None:
        """更新缓存"""
        if len(self._analysis_cache) >= self._cache_max_size:
            oldest_key = next(iter(self._analysis_cache))
            del self._analysis_cache[oldest_key]
        
        self._analysis_cache[key] = result
    
    def clear_cache(self) -> None:
        """清空缓存"""
        self._analysis_cache.clear()
    
    def get_predicted_topic(self) -> Optional[str]:
        """获取预测的下一个话题"""
        return TopicAnalyzer.predict_next_topic(self._topic_history)


_enhanced_analyzer: Optional[EnhancedIntentAnalyzer] = None


def get_enhanced_intent_analyzer() -> EnhancedIntentAnalyzer:
    """获取增强版意图分析器单例"""
    global _enhanced_analyzer
    if _enhanced_analyzer is None:
        _enhanced_analyzer = EnhancedIntentAnalyzer()
    return _enhanced_analyzer
