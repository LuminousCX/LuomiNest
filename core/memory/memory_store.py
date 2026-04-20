"""
记忆存储模块
Author: LumiNest Team
Date: 2026-04-14
"""
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional


class MemoryStore:
    """记忆存储类
    
    提供记忆的持久化存储和检索功能
    """
    
    def __init__(self, storage_path: str):
        """初始化记忆存储
        
        Args:
            storage_path: 存储文件路径
        """
        self.storage_path = storage_path
        self.memories: List[Dict[str, Any]] = self._load_memories()

    def _load_memories(self) -> List[Dict[str, Any]]:
        """从文件加载记忆数据
        
        Returns:
            List[Dict[str, Any]]: 记忆列表
        """
        if not os.path.exists(self.storage_path):
            return []
        
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

    def _save_memories(self) -> None:
        """保存记忆数据到文件"""
        with open(self.storage_path, 'w', encoding='utf-8') as f:
            json.dump(self.memories, f, ensure_ascii=False, indent=2)

    def add_memory(self, content: str, importance: int = 1) -> Dict[str, Any]:
        """添加新记忆
        
        Args:
            content: 记忆内容
            importance: 重要性级别，默认为1
            
        Returns:
            Dict[str, Any]: 新创建的记忆对象
        """
        memory = {
            "id": len(self.memories) + 1,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "importance": importance
        }
        self.memories.append(memory)
        self._save_memories()
        return memory

    def get_memories(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取记忆列表
        
        Args:
            limit: 返回数量限制，默认为10
            
        Returns:
            List[Dict[str, Any]]: 按重要性和时间排序的记忆列表
        """
        sorted_memories = sorted(
            self.memories,
            key=lambda x: (x.get('importance', 1), x.get('timestamp', '')),
            reverse=True
        )
        return sorted_memories[:limit]

    def search_memories(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """搜索记忆
        
        Args:
            query: 搜索关键词
            limit: 返回数量限制，默认为5
            
        Returns:
            List[Dict[str, Any]]: 匹配的记忆列表
        """
        results = [
            m for m in self.memories
            if query in m.get('content', '')
        ]
        results.sort(
            key=lambda x: (x.get('importance', 1), x.get('timestamp', '')),
            reverse=True
        )
        return results[:limit]

    def clear_memories(self) -> None:
        """清空所有记忆"""
        self.memories = []
        self._save_memories()

    def get_memory_count(self) -> int:
        """获取记忆总数
        
        Returns:
            int: 记忆数量
        """
        return len(self.memories)
