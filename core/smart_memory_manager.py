"""
智能记忆管理器 - 增强版记忆管理
整合工作记忆、长期记忆、上下文管理
"""

from core.memory.memory_store import MemoryStore
from core.memory.fact_extractor import FactExtractor
from typing import List, Dict, Any, Optional
import time


class SmartMemoryManager:
    """智能记忆管理器 - 整合多种记忆功能"""
    
    def __init__(self, storage_path: str):
        """初始化智能记忆管理器"""
        self.memory_store = MemoryStore(storage_path)
        self.fact_extractor = FactExtractor()
        
        self.working_memory: List[str] = []
        self.max_working_memory: int = 100
        
        self._conversation_context: List[Dict[str, Any]] = []
        self._max_context_length: int = 50
    
    def add_to_working_memory(self, content: str) -> None:
        """添加到工作记忆"""
        self.working_memory.append(content)
        if len(self.working_memory) > self.max_working_memory:
            self.working_memory.pop(0)
    
    def get_working_memory(self) -> List[str]:
        """获取工作记忆"""
        return self.working_memory.copy()
    
    def clear_working_memory(self) -> None:
        """清空工作记忆"""
        self.working_memory = []
    
    def add_memory(self, user_input: str, system_response: str) -> None:
        """添加对话记忆"""
        self.memory_store.add_memory(f"用户: {user_input}", importance=1)
        self.memory_store.add_memory(f"系统: {system_response}", importance=1)
        
        self._conversation_context.append({
            "user_input": user_input,
            "system_response": system_response,
            "timestamp": time.time()
        })
        
        if len(self._conversation_context) > self._max_context_length:
            self._conversation_context.pop(0)
    
    def search_memory(self, query: str, limit: int = 5) -> List[str]:
        """搜索记忆"""
        working_results = [item for item in self.working_memory if query.lower() in item.lower()]
        
        remaining_limit = max(0, limit - len(working_results))
        long_term_results = self.memory_store.search_memories(query, remaining_limit)
        
        long_term_contents = [item.get('content', '') for item in long_term_results]
        results = working_results + long_term_contents
        return results[:limit]
    
    def extract_and_store_facts(self, text: str) -> Dict[str, str]:
        """提取并存储事实"""
        facts = self.fact_extractor.extract_facts(text)
        for fact_type, value in facts.items():
            fact_content = f"{fact_type}: {value}"
            self.memory_store.add_memory(fact_content, importance=2)
        return facts
    
    def get_all_memories(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取所有记忆"""
        return self.memory_store.get_memories(limit)
    
    def clear_all_memory(self) -> None:
        """清空所有记忆"""
        self.clear_working_memory()
        self.memory_store.clear_memories()
        self._conversation_context = []
    
    def get_memory_count(self) -> int:
        """获取记忆数量"""
        return self.memory_store.get_memory_count()
    
    def get_context_summary(self, max_items: int = 5) -> str:
        """获取上下文摘要"""
        if not self._conversation_context:
            return ""
        
        recent = self._conversation_context[-max_items:]
        summary_parts = []
        
        for ctx in recent:
            user_input = ctx.get("user_input", "")[:50]
            summary_parts.append(f"用户: {user_input}")
        
        return "\n".join(summary_parts)
    
    @property
    def conversation_context(self) -> List[Dict[str, Any]]:
        """获取对话上下文"""
        return self._conversation_context.copy()
