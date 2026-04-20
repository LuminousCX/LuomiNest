import json
import os
import math
from functools import lru_cache

class VectorRAG:
    def __init__(self, vector_store_path):
        self.vector_store_path = vector_store_path
        self.vector_store = self.load_vector_store()
        self._build_vector_cache()  # 构建向量缓存
    
    def _build_vector_cache(self):
        """构建向量缓存，避免重复计算"""
        self.vectors_cache = []
        self.texts_cache = []
        for item in self.vector_store:
            vector = item.get('vector', [])
            if vector:
                self.vectors_cache.append(vector)
                self.texts_cache.append(item.get('text', ''))
    
    def load_vector_store(self):
        """加载向量存储"""
        if os.path.exists(self.vector_store_path):
            try:
                with open(self.vector_store_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return []
        return []
    
    def save_vector_store(self):
        """保存向量存储"""
        with open(self.vector_store_path, 'w', encoding='utf-8') as f:
            json.dump(self.vector_store, f, ensure_ascii=False, indent=2)
        # 重建缓存
        self._build_vector_cache()
    
    def add_vector(self, text, vector):
        """添加向量"""
        vector_item = {
            "id": len(self.vector_store) + 1,
            "text": text,
            "vector": vector
        }
        self.vector_store.append(vector_item)
        self.save_vector_store()
        return vector_item
    
    @lru_cache(maxsize=100)  # 缓存向量生成
    def _get_vector_hash(self, query_vector_tuple):
        """获取向量哈希值用于缓存"""
        return hash(query_vector_tuple)
    
    def search_vectors(self, query_vector, limit=5):
        """搜索向量（优化版）"""
        if not self.vectors_cache:
            return []
        
        # 预计算查询向量的模
        query_norm = math.sqrt(sum(a ** 2 for a in query_vector))
        if query_norm == 0:
            return []
        
        # 批量计算相似度
        similarities = []
        for i, vector in enumerate(self.vectors_cache):
            if len(vector) == len(query_vector):
                similarity = self._cosine_similarity_fast(query_vector, vector, query_norm)
                if similarity > 0.1:  # 设置最小相似度阈值
                    similarities.append((self.texts_cache[i], similarity))
        
        # 按相似度排序
        similarities.sort(key=lambda x: x[1], reverse=True)
        return [{"text": text} for text, _ in similarities[:limit]]
    
    def _cosine_similarity_fast(self, vector1, vector2, norm1):
        """快速计算余弦相似度"""
        dot_product = sum(a * b for a, b in zip(vector1, vector2))
        norm2 = math.sqrt(sum(b ** 2 for b in vector2))
        
        if norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def cosine_similarity(self, vector1, vector2):
        """计算余弦相似度"""
        if len(vector1) != len(vector2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vector1, vector2))
        norm1 = math.sqrt(sum(a ** 2 for a in vector1))
        norm2 = math.sqrt(sum(b ** 2 for b in vector2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def get_vector_count(self):
        """获取向量数量"""
        return len(self.vector_store)
    
    def clear_vector_store(self):
        """清空向量存储"""
        self.vector_store = []
        self.vectors_cache = []
        self.texts_cache = []
        self.save_vector_store()