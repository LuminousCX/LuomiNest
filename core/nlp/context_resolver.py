"""
上下文解析器 - 处理对话上下文和代词消解
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
import re


@dataclass
class ConversationTurn:
    """对话轮次"""
    user_input: str
    system_response: str
    timestamp: float = 0.0
    entities: Dict[str, Any] = field(default_factory=dict)


class ContextResolver:
    """上下文解析器"""
    
    PRONOUNS = {
        "它": "thing",
        "他": "person",
        "她": "person",
        "这个": "thing",
        "那个": "thing",
        "这些": "things",
        "那些": "things",
    }
    
    FOLLOW_UP_PATTERNS = [
        r'怎么样',
        r'为什么呢',
        r'为什么呢？',
        r'为什么',
        r'怎么',
        r'如何',
        r'什么意思',
        r'是什么',
        r'能详细说说吗',
        r'能再解释一下吗',
        r'还有呢',
    ]
    
    def __init__(self, max_turns: int = 10):
        self.max_turns = max_turns
        self._turns: List[ConversationTurn] = []
    
    def add_turn(self, user_input: str, system_response: str) -> None:
        """添加对话轮次"""
        import time
        turn = ConversationTurn(
            user_input=user_input,
            system_response=system_response,
            timestamp=time.time()
        )
        self._turns.append(turn)
        
        if len(self._turns) > self.max_turns:
            self._turns.pop(0)
    
    def get_last_turn(self) -> Optional[ConversationTurn]:
        """获取最后一轮对话"""
        return self._turns[-1] if self._turns else None
    
    def get_context_summary(self, max_turns: int = 3) -> str:
        """获取上下文摘要"""
        if not self._turns:
            return ""
        
        recent = self._turns[-max_turns:]
        parts = []
        
        for turn in recent:
            parts.append(f"用户: {turn.user_input[:100]}")
            parts.append(f"系统: {turn.system_response[:100]}")
        
        return "\n".join(parts)
    
    def resolve_pronoun(self, text: str) -> Optional[str]:
        """解析代词，返回指代的内容"""
        for pronoun, _ in self.PRONOUNS.items():
            if pronoun in text:
                last_turn = self.get_last_turn()
                if last_turn:
                    return last_turn.user_input
        return None
    
    def is_follow_up_question(self, text: str) -> bool:
        """判断是否是追问"""
        for pattern in self.FOLLOW_UP_PATTERNS:
            if re.search(pattern, text):
                return True
        return False
    
    def get_relevant_context(self, query: str) -> str:
        """获取相关上下文"""
        if not self._turns:
            return ""
        
        context_parts = []
        
        for turn in reversed(self._turns[-3:]):
            if any(word in turn.user_input for word in query.split()):
                context_parts.append(f"之前讨论过: {turn.user_input[:50]}")
        
        return "\n".join(context_parts) if context_parts else ""
    
    def clear(self) -> None:
        """清空上下文"""
        self._turns = []


_context_resolver: Optional[ContextResolver] = None


def get_context_resolver() -> ContextResolver:
    """获取上下文解析器单例"""
    global _context_resolver
    if _context_resolver is None:
        _context_resolver = ContextResolver()
    return _context_resolver
