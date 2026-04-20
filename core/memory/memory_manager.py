from .memory_store import MemoryStore
from .fact_extractor import FactExtractor

class MemoryManager:
    def __init__(self, storage_path):
        self.memory_store = MemoryStore(storage_path)
        self.fact_extractor = FactExtractor()
        self.working_memory = []  # 工作记忆
        self.max_working_memory = 100  # 工作记忆容量
    
    def add_to_working_memory(self, content):
        """添加到工作记忆"""
        self.working_memory.append(content)
        if len(self.working_memory) > self.max_working_memory:
            self.working_memory.pop(0)
    
    def get_working_memory(self):
        """获取工作记忆"""
        return self.working_memory
    
    def clear_working_memory(self):
        """清空工作记忆"""
        self.working_memory = []
    
    def add_to_long_term_memory(self, content, importance=1):
        """添加到长期记忆"""
        return self.memory_store.add_memory(content, importance)
    
    def search_memory(self, query, limit=5):
        """搜索记忆"""
        # 先搜索工作记忆
        working_results = [item for item in self.working_memory if query in item]
        
        # 再搜索长期记忆
        long_term_results = self.memory_store.search_memories(query, limit - len(working_results))
        
        # 合并结果
        results = working_results + [item.get('content', '') for item in long_term_results]
        return results[:limit]
    
    def extract_and_store_facts(self, text):
        """提取并存储事实"""
        facts = self.fact_extractor.extract_facts(text)
        for fact_type, value in facts.items():
            fact_content = f"{fact_type}: {value}"
            self.add_to_long_term_memory(fact_content, importance=2)
        return facts
    
    def get_all_memories(self, limit=20):
        """获取所有记忆"""
        return self.memory_store.get_memories(limit)
    
    def clear_all_memory(self):
        """清空所有记忆"""
        self.clear_working_memory()
        self.memory_store.clear_memories()
    
    def get_memory_count(self):
        """获取记忆数量"""
        return self.memory_store.get_memory_count()
