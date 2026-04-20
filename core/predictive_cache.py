"""
预测性缓存系统 - 加速常见查询的响应速度
"""

import time
from collections import defaultdict
from typing import Optional, Dict, List
import threading

class PredictiveCache:
    """预测性缓存系统"""
    
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        
        # 缓存存储
        self.cache = {}  # {query: response}
        self.access_count = defaultdict(int)  # 访问计数
        self.last_access = {}  # 最后访问时间
        
        # 热门查询缓存（预加载）
        self.hot_queries = {
            '你好': '你好！很高兴见到你。',
            '你是谁': '我是汐汐，一个智能助手。',
            '你叫什么': '我叫汐汐。',
            '你能做什么': '我可以回答问题、提供建议、陪你聊天。',
            '谢谢': '不客气！有什么其他问题吗？',
            '再见': '再见！期待下次和你聊天。',
        }
        
        # 线程锁
        self.lock = threading.Lock()
        
        # 统计信息
        self.stats = {
            'hits': 0,
            'misses': 0,
            'total_queries': 0
        }
    
    def get(self, query: str) -> Optional[str]:
        """获取缓存"""
        with self.lock:
            self.stats['total_queries'] += 1
            
            # 检查热门查询
            if query in self.hot_queries:
                self.stats['hits'] += 1
                return self.hot_queries[query]
            
            # 检查缓存
            if query in self.cache:
                self.stats['hits'] += 1
                self.access_count[query] += 1
                self.last_access[query] = time.time()
                return self.cache[query]
            
            self.stats['misses'] += 1
            return None
    
    def set(self, query: str, response: str):
        """设置缓存"""
        with self.lock:
            # 如果缓存已满，移除最少使用的
            if len(self.cache) >= self.max_size:
                self._evict_lru()
            
            self.cache[query] = response
            self.access_count[query] = 1
            self.last_access[query] = time.time()
    
    def _evict_lru(self):
        """移除最近最少使用的缓存"""
        if not self.cache:
            return
        
        # 找到访问次数最少且最久未访问的
        min_count = min(self.access_count.values())
        candidates = [q for q, c in self.access_count.items() if c == min_count]
        
        if candidates:
            # 在候选中选择最久未访问的
            oldest_query = min(candidates, key=lambda q: self.last_access.get(q, 0))
            
            # 移除
            del self.cache[oldest_query]
            del self.access_count[oldest_query]
            del self.last_access[oldest_query]
    
    def get_hit_rate(self) -> float:
        """获取缓存命中率"""
        if self.stats['total_queries'] == 0:
            return 0.0
        return self.stats['hits'] / self.stats['total_queries']
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self.stats,
            'cache_size': len(self.cache),
            'hot_queries': len(self.hot_queries),
            'hit_rate': f"{self.get_hit_rate():.2%}"
        }
    
    def clear(self):
        """清空缓存"""
        with self.lock:
            self.cache.clear()
            self.access_count.clear()
            self.last_access.clear()
    
    def preload_common_queries(self, queries: Dict[str, str]):
        """预加载常见查询"""
        with self.lock:
            self.hot_queries.update(queries)

# 全局缓存实例
predictive_cache = PredictiveCache()
