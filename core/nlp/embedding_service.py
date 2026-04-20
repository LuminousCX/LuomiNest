"""
嵌入服务 - 文本向量化
"""

from typing import List, Optional
import hashlib


class EmbeddingService:
    """嵌入服务"""
    
    def __init__(self):
        self._use_real_embeddings = False
        self._vector_dim = 52
    
    def encode(self, text: str) -> List[float]:
        """编码文本为向量"""
        if not text:
            return [0.0] * self._vector_dim
        
        vector = []
        text_lower = text.lower()
        
        for char in 'abcdefghijklmnopqrstuvwxyz':
            count = text_lower.count(char)
            vector.append(count / len(text) if text else 0)
        
        for char in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            count = text.count(char)
            vector.append(count / len(text) if text else 0)
        
        return vector
    
    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """批量编码文本"""
        return [self.encode(text) for text in texts]
    
    def similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算两个向量的相似度"""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def is_using_real_embeddings(self) -> bool:
        """是否使用真实嵌入"""
        return self._use_real_embeddings


_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """获取嵌入服务单例"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


def encode_text(text: str) -> List[float]:
    """编码文本"""
    return get_embedding_service().encode(text)
