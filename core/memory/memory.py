"""
记忆管理模块
"""

from .memory_store import MemoryStore
from .fact_extractor import FactExtractor
from config import DEFAULT_USER_ID

class Memory:
    """模仿 mem0 的主 Memory 类"""

    def __init__(self, file_path):
        self.store = MemoryStore(file_path)
        self.extractor = FactExtractor()

    def add(self, text, user_id=DEFAULT_USER_ID):
        facts = self.extractor.extract_from_user_input(text)
        existing_facts = set()
        # 安全获取已存在的事实
        for m in self.store.get_by_user(user_id):
            fact = m.get("fact", "")
            if fact:
                existing_facts.add(fact)

        for f in facts:
            if f and f not in existing_facts:
                self.store.add(f, user_id)

    def search(self, query, user_id=DEFAULT_USER_ID, limit=6):
        return self.store.search(query, user_id, limit)

    def get_all_facts(self, user_id=DEFAULT_USER_ID):
        return [m.get("fact", "") for m in self.store.get_by_user(user_id) if m.get("fact")]

    def get_working_memory(self, user_id=DEFAULT_USER_ID):
        """获取工作记忆（最近的记忆）"""
        all_facts = self.get_all_facts(user_id)
        # 返回最近的10条记忆作为工作记忆
        return all_facts[-10:]

    def clear_working_memory(self, user_id=DEFAULT_USER_ID):
        """清空工作记忆"""
        # 获取所有记忆
        user_memories = self.store.get_by_user(user_id)
        if user_memories:
            # 只保留前N条记忆，删除最近的记忆
            # 这里我们保留前80%的记忆，删除最近的20%
            keep_count = int(len(user_memories) * 0.8)
            if keep_count < len(user_memories):
                # 保留前keep_count条记忆
                self.store.memories = [m for m in self.store.memories if not (isinstance(m, dict) and m.get("user_id") == user_id)]
                # 添加回要保留的记忆
                for m in user_memories[:keep_count]:
                    self.store.memories.append(m)
                # 保存并重建索引
                self.store._save()

    def clear_all_memory(self, user_id=DEFAULT_USER_ID):
        """清空所有记忆"""
        # 移除指定用户的所有记忆
        self.store.memories = [m for m in self.store.memories if not (isinstance(m, dict) and m.get("user_id") == user_id)]
        # 保存并重建索引
        self.store._save()
