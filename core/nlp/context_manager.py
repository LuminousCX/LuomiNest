"""
上下文管理器 - 整合多源上下文信息
管理对话历史、记忆系统、知识库等上下文
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import time


@dataclass
class ContextSnapshot:
    """上下文快照"""
    timestamp: float
    user_input: str
    system_response: str
    intent: Optional[str] = None
    topic: Optional[str] = None
    entities: Dict[str, Any] = field(default_factory=dict)
    sentiment: str = "neutral"


class ContextManager:
    """上下文管理器 - 整合多源上下文"""
    
    def __init__(self, max_history: int = 20):
        self.max_history = max_history
        
        self._conversation_history: List[ContextSnapshot] = []
        self._current_topic: Optional[str] = None
        self._topic_stack: List[str] = []
        self._entity_context: Dict[str, Any] = {}
        self._intent_history: List[str] = []
        self._sentiment_history: List[str] = []
        
        self._memory_context: List[str] = []
        self._knowledge_context: List[str] = []
        
        self._context_weights = {
            "recent_conversation": 0.5,
            "memory": 0.3,
            "knowledge": 0.2,
        }
    
    def add_conversation_turn(
        self,
        user_input: str,
        system_response: str,
        intent: Optional[str] = None,
        topic: Optional[str] = None,
        entities: Optional[Dict[str, Any]] = None,
        sentiment: str = "neutral"
    ) -> None:
        """添加对话轮次"""
        snapshot = ContextSnapshot(
            timestamp=time.time(),
            user_input=user_input,
            system_response=system_response,
            intent=intent,
            topic=topic,
            entities=entities or {},
            sentiment=sentiment
        )
        
        self._conversation_history.append(snapshot)
        
        if len(self._conversation_history) > self.max_history:
            self._conversation_history.pop(0)
        
        if intent:
            self._intent_history.append(intent)
            if len(self._intent_history) > self.max_history:
                self._intent_history.pop(0)
        
        if topic:
            if topic != self._current_topic:
                self._topic_stack.append(topic)
                if len(self._topic_stack) > 5:
                    self._topic_stack.pop(0)
            self._current_topic = topic
        
        if entities:
            self._entity_context.update(entities)
        
        self._sentiment_history.append(sentiment)
        if len(self._sentiment_history) > self.max_history:
            self._sentiment_history.pop(0)
    
    def set_memory_context(self, memories: List[str]) -> None:
        """设置记忆上下文"""
        self._memory_context = memories[:5]
    
    def set_knowledge_context(self, knowledge: List[str]) -> None:
        """设置知识库上下文"""
        self._knowledge_context = knowledge[:5]
    
    def get_conversation_history(self, limit: int = 5) -> List[Dict[str, str]]:
        """获取对话历史"""
        if not self._conversation_history:
            return []
        
        recent = self._conversation_history[-limit:]
        return [
            {
                "user_input": snap.user_input,
                "system_response": snap.system_response,
                "intent": snap.intent,
                "topic": snap.topic,
                "timestamp": snap.timestamp
            }
            for snap in recent
        ]
    
    def get_last_turn(self) -> Optional[ContextSnapshot]:
        """获取最后一轮对话"""
        return self._conversation_history[-1] if self._conversation_history else None
    
    def get_recent_context(self, max_tokens: int = 500) -> str:
        """获取最近上下文（用于API提示）"""
        parts = []
        current_tokens = 0
        
        for snapshot in reversed(self._conversation_history[-5:]):
            turn_text = f"用户: {snapshot.user_input[:100]}\n系统: {snapshot.system_response[:100]}"
            turn_tokens = len(turn_text)
            
            if current_tokens + turn_tokens > max_tokens:
                break
            
            parts.insert(0, turn_text)
            current_tokens += turn_tokens
        
        return "\n\n".join(parts) if parts else ""
    
    def get_full_context(self) -> Dict[str, Any]:
        """获取完整上下文"""
        return {
            "conversation_history": self.get_conversation_history(),
            "current_topic": self._current_topic,
            "topic_stack": self._topic_stack,
            "entity_context": self._entity_context,
            "intent_history": self._intent_history[-5:],
            "sentiment_trend": self._analyze_sentiment_trend(),
            "memory_context": self._memory_context,
            "knowledge_context": self._knowledge_context,
        }
    
    def get_context_for_intent_analysis(self) -> Dict[str, Any]:
        """获取用于意图分析的上下文"""
        return {
            "conversation_history": self.get_conversation_history(3),
            "memory_results": self._memory_context,
            "knowledge_results": self._knowledge_context,
            "current_topic": self._current_topic,
            "last_intent": self._intent_history[-1] if self._intent_history else None,
            "entity_context": self._entity_context,
        }
    
    def get_context_summary(self) -> str:
        """获取上下文摘要"""
        parts = []
        
        if self._current_topic:
            parts.append(f"当前话题: {self._current_topic}")
        
        if self._intent_history:
            recent_intents = self._intent_history[-3:]
            parts.append(f"最近意图: {', '.join(recent_intents)}")
        
        if self._entity_context:
            entity_str = ", ".join(f"{k}: {v}" for k, v in list(self._entity_context.items())[:3])
            parts.append(f"实体信息: {entity_str}")
        
        sentiment = self._analyze_sentiment_trend()
        if sentiment != "neutral":
            parts.append(f"情感趋势: {sentiment}")
        
        return "\n".join(parts) if parts else ""
    
    def _analyze_sentiment_trend(self) -> str:
        """分析情感趋势"""
        if not self._sentiment_history:
            return "neutral"
        
        recent = self._sentiment_history[-5:]
        positive = recent.count("positive")
        negative = recent.count("negative")
        
        if positive > negative + 1:
            return "positive"
        elif negative > positive + 1:
            return "negative"
        else:
            return "neutral"
    
    def is_follow_up_question(self, text: str) -> bool:
        """判断是否是追问"""
        follow_up_indicators = [
            "怎么样", "为什么", "怎么", "如何", "什么意思",
            "能详细", "能再", "还有呢", "然后呢", "继续"
        ]
        
        if len(text) < 15:
            for indicator in follow_up_indicators:
                if indicator in text:
                    return True
        
        return False
    
    def get_referenced_content(self, text: str) -> Optional[str]:
        """获取引用内容（代词消解）"""
        pronouns = ["它", "他", "她", "这个", "那个", "刚才", "之前"]
        
        for pronoun in pronouns:
            if pronoun in text:
                last_turn = self.get_last_turn()
                if last_turn:
                    return last_turn.user_input
        
        return None
    
    def detect_topic_change(self, new_topic: Optional[str]) -> bool:
        """检测话题是否改变"""
        if not new_topic:
            return False
        return new_topic != self._current_topic
    
    def get_relevant_memories(self, query: str) -> List[str]:
        """获取相关记忆"""
        relevant = []
        query_lower = query.lower()
        
        for memory in self._memory_context:
            if query_lower in memory.lower():
                relevant.append(memory)
        
        return relevant[:3]
    
    def build_api_context(self, query: str) -> str:
        """构建API上下文提示"""
        context_parts = []
        
        conversation_context = self.get_recent_context(max_tokens=300)
        if conversation_context:
            context_parts.append(f"【对话历史】\n{conversation_context}")
        
        if self._current_topic:
            context_parts.append(f"【当前话题】{self._current_topic}")
        
        if self._memory_context:
            memory_str = "; ".join(self._memory_context[:2])
            context_parts.append(f"【相关记忆】{memory_str}")
        
        context_parts.append(f"【当前问题】{query}")
        
        return "\n\n".join(context_parts)
    
    def clear(self) -> None:
        """清空上下文"""
        self._conversation_history = []
        self._current_topic = None
        self._topic_stack = []
        self._entity_context = {}
        self._intent_history = []
        self._sentiment_history = []
        self._memory_context = []
        self._knowledge_context = []
    
    def export_context(self) -> Dict[str, Any]:
        """导出上下文（用于持久化）"""
        return {
            "conversation_history": [
                {
                    "timestamp": snap.timestamp,
                    "user_input": snap.user_input,
                    "system_response": snap.system_response,
                    "intent": snap.intent,
                    "topic": snap.topic,
                    "entities": snap.entities,
                    "sentiment": snap.sentiment
                }
                for snap in self._conversation_history
            ],
            "current_topic": self._current_topic,
            "topic_stack": self._topic_stack,
            "entity_context": self._entity_context,
            "intent_history": self._intent_history,
            "sentiment_history": self._sentiment_history,
        }
    
    def import_context(self, data: Dict[str, Any]) -> None:
        """导入上下文（用于恢复）"""
        self.clear()
        
        for item in data.get("conversation_history", []):
            snapshot = ContextSnapshot(
                timestamp=item.get("timestamp", time.time()),
                user_input=item.get("user_input", ""),
                system_response=item.get("system_response", ""),
                intent=item.get("intent"),
                topic=item.get("topic"),
                entities=item.get("entities", {}),
                sentiment=item.get("sentiment", "neutral")
            )
            self._conversation_history.append(snapshot)
        
        self._current_topic = data.get("current_topic")
        self._topic_stack = data.get("topic_stack", [])
        self._entity_context = data.get("entity_context", {})
        self._intent_history = data.get("intent_history", [])
        self._sentiment_history = data.get("sentiment_history", [])


_context_manager: Optional[ContextManager] = None


def get_context_manager() -> ContextManager:
    """获取上下文管理器单例"""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager
