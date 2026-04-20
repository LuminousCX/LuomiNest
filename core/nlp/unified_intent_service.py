"""
统一意图分析服务
整合语义相似度、意图识别、功能映射、用户画像、记忆系统等所有组件
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import time

from .semantic_similarity import (
    SemanticSimilarityCalculator,
    get_semantic_calculator,
    SimilarityResult
)
from .intent_recognizer_enhanced import (
    EnhancedIntentRecognizer,
    IntentAnalysisResult,
    IntentMatch,
    get_intent_recognizer
)
from .intent_function_mapper import (
    IntentFunctionMapper,
    FunctionResult,
    get_intent_function_mapper
)


@dataclass
class UnifiedAnalysisResult:
    user_input: str
    primary_intent: IntentMatch
    secondary_intents: List[IntentMatch] = field(default_factory=list)
    topic: Optional[str] = None
    sentiment: str = "neutral"
    entities: Dict[str, Any] = field(default_factory=dict)
    
    function_result: Optional[FunctionResult] = None
    should_use_api: bool = True
    api_context: str = ""
    
    memory_context: str = ""
    knowledge_context: str = ""
    
    semantic_similarity: float = 0.0
    confidence: float = 0.0
    
    analysis_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class UnifiedIntentService:
    """统一意图分析服务"""
    
    def __init__(self):
        self.semantic_calc = get_semantic_calculator()
        self.intent_recognizer = get_intent_recognizer()
        self.function_mapper = get_intent_function_mapper()
        
        self._knowledge_manager = None
        self._memory_manager = None
        self._ai_personality_manager = None
        
        self._conversation_history: List[Dict] = []
        self._last_result: Optional[UnifiedAnalysisResult] = None
    
    def set_knowledge_manager(self, manager):
        """设置知识管理器"""
        self._knowledge_manager = manager
        self.intent_recognizer.set_knowledge_manager(manager)
        self.function_mapper.set_knowledge_manager(manager)
    
    def set_memory_manager(self, manager):
        """设置记忆管理器"""
        self._memory_manager = manager
        self.intent_recognizer.set_memory_manager(manager)
        self.function_mapper.set_memory_manager(manager)
    
    def set_ai_personality_manager(self, manager):
        """设置AI人格管理器"""
        self._ai_personality_manager = manager
        self.function_mapper.set_ai_personality_manager(manager)
    
    def analyze(
        self,
        user_input: str,
        conversation_history: List[Dict] = None,
        additional_context: Dict[str, Any] = None
    ) -> UnifiedAnalysisResult:
        """
        综合分析用户输入
        
        Args:
            user_input: 用户输入文本
            conversation_history: 对话历史
            additional_context: 额外的上下文信息
        
        Returns:
            UnifiedAnalysisResult: 统一分析结果
        """
        start_time = time.time()
        
        if conversation_history:
            self._conversation_history = conversation_history
        
        additional_context = additional_context or {}
        
        intent_result = self.intent_recognizer.analyze(
            user_input,
            conversation_history,
            additional_context
        )
        
        memory_context = self._get_memory_context(user_input)
        knowledge_context = self._get_knowledge_context(user_input)
        
        function_result = self.function_mapper.execute_intent(
            intent_result.primary_intent,
            user_input,
            {
                "memory": memory_context,
                "knowledge": knowledge_context,
                **additional_context
            }
        )
        
        api_context = self._build_api_context(
            user_input,
            intent_result,
            function_result,
            memory_context,
            knowledge_context
        )
        
        semantic_similarity = self._calculate_overall_similarity(user_input, intent_result)
        
        analysis_time = (time.time() - start_time) * 1000
        
        result = UnifiedAnalysisResult(
            user_input=user_input,
            primary_intent=intent_result.primary_intent,
            secondary_intents=intent_result.secondary_intents,
            topic=intent_result.topic,
            sentiment=intent_result.sentiment,
            entities=intent_result.entities,
            function_result=function_result,
            should_use_api=function_result.should_use_api if function_result else True,
            api_context=api_context,
            memory_context=memory_context,
            knowledge_context=knowledge_context,
            semantic_similarity=semantic_similarity,
            confidence=intent_result.primary_intent.confidence,
            analysis_time_ms=round(analysis_time, 2),
            metadata={
                "intent_metadata": intent_result.analysis_metadata,
                "has_function_result": function_result is not None,
                "context_sources": {
                    "has_memory": bool(memory_context),
                    "has_knowledge": bool(knowledge_context),
                }
            }
        )
        
        self._last_result = result
        
        return result
    
    def _get_memory_context(self, query: str) -> str:
        """获取记忆上下文"""
        if not self._memory_manager:
            return ""
        
        try:
            memories = self._memory_manager.search_memory(query, limit=3)
            if memories:
                return "【相关记忆】\n" + "\n".join(memories)
        except Exception:
            pass
        
        return ""
    
    def _get_knowledge_context(self, query: str) -> str:
        """获取知识库上下文"""
        if not self._knowledge_manager:
            return ""
        
        try:
            expanded_queries = self.semantic_calc.expand_query(query)
            all_results = []
            
            for q in expanded_queries[:2]:
                results = self._knowledge_manager.search_knowledge(q, threshold=0.3)
                all_results.extend(results)
            
            unique_results = []
            seen = set()
            for r in all_results:
                key = r.get('question', '') if isinstance(r, dict) else str(r)
                if key and key not in seen:
                    seen.add(key)
                    unique_results.append(r)
            
            if unique_results:
                context = "【知识库匹配】\n"
                for r in unique_results[:3]:
                    if isinstance(r, dict):
                        context += f"- {r.get('question', '')}: {r.get('answer', '')[:100]}\n"
                    else:
                        context += f"- {r}\n"
                return context
        except Exception:
            pass
        
        return ""
    
    def _build_api_context(
        self,
        user_input: str,
        intent_result: IntentAnalysisResult,
        function_result: Optional[FunctionResult],
        memory_context: str,
        knowledge_context: str
    ) -> str:
        """构建API上下文"""
        parts = []
        
        if function_result and function_result.api_context:
            parts.append(function_result.api_context)
        
        if memory_context:
            parts.append(memory_context)
        
        if knowledge_context:
            parts.append(knowledge_context)
        
        if intent_result.topic:
            topic_context = f"【当前话题】{intent_result.topic}"
            parts.append(topic_context)
        
        if self._conversation_history:
            recent_history = self._conversation_history[-3:]
            history_context = "【最近对话】\n"
            for turn in recent_history:
                user_msg = turn.get('user_input', '')
                if user_msg:
                    history_context += f"用户: {user_msg[:50]}\n"
            parts.append(history_context)
        
        return "\n\n".join(parts)
    
    def _calculate_overall_similarity(
        self,
        user_input: str,
        intent_result: IntentAnalysisResult
    ) -> float:
        """计算整体语义相似度"""
        if not intent_result.primary_intent or intent_result.primary_intent.name == "unknown":
            return 0.0
        
        return intent_result.primary_intent.semantic_score
    
    def get_similar_intents(
        self,
        text: str,
        threshold: float = 0.3
    ) -> List[Tuple[str, float]]:
        """获取相似的意图列表"""
        from .intent_recognizer_enhanced import IntentPatternRegistry
        
        intent_names = IntentPatternRegistry.get_intent_names()
        similar_intents = []
        
        for intent_name in intent_names:
            score, _ = self.semantic_calc.calculate_intent_similarity(text, intent_name)
            if score >= threshold:
                similar_intents.append((intent_name, score))
        
        similar_intents.sort(key=lambda x: x[1], reverse=True)
        return similar_intents[:5]
    
    def expand_query(self, query: str) -> List[str]:
        """扩展查询（使用同义词和相关词）"""
        return self.semantic_calc.expand_query(query)
    
    def calculate_text_similarity(
        self,
        text1: str,
        text2: str
    ) -> SimilarityResult:
        """计算两段文本的相似度"""
        return self.semantic_calc.calculate_similarity(text1, text2)
    
    def get_local_function_for_intent(self, intent_name: str) -> Optional[str]:
        """获取意图对应的本地功能"""
        return self.function_mapper.get_function_description(intent_name)
    
    def get_current_topic(self) -> Optional[str]:
        """获取当前话题"""
        return self.intent_recognizer.get_current_topic()
    
    def get_topic_history(self) -> List[str]:
        """获取话题历史"""
        return self.intent_recognizer.get_topic_history()
    
    def clear_context(self):
        """清空上下文"""
        self._conversation_history = []
        self._last_result = None
        self.intent_recognizer.clear_context()
    
    def get_last_result(self) -> Optional[UnifiedAnalysisResult]:
        """获取最后一次分析结果"""
        return self._last_result


_unified_service: Optional[UnifiedIntentService] = None


def get_unified_intent_service() -> UnifiedIntentService:
    """获取统一意图分析服务单例"""
    global _unified_service
    if _unified_service is None:
        _unified_service = UnifiedIntentService()
    return _unified_service
