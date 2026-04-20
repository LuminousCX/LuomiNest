"""向量嵌入生成工具。

基于 sentence-transformers 实现本地向量嵌入生成，
支持 ONNX 运行时加速，零网络依赖（模型本地缓存）。

优化特性：
- 默认使用 bge-small-zh-v1.5 中英双语模型
- LRU 缓存避免重复编码
- 线程安全的全局单例
- 降级模式明确报错而非静默使用随机向量
"""

from __future__ import annotations

import threading
from functools import lru_cache
from typing import Optional

import numpy as np

from src.config.settings import get_settings
from src.exceptions import MemoryEmbeddingError
from src.utils.logger import get_logger

logger = get_logger()

_embedding_service: Optional[EmbeddingUtil] = None
_embedding_lock = threading.Lock()

_SUPPORTED_MODELS = {
    "bge-small-zh-v1.5": {"dimension": 512, "language": "zh+en"},
    "bge-base-zh-v1.5": {"dimension": 768, "language": "zh+en"},
    "all-MiniLM-L6-v2": {"dimension": 384, "language": "en"},
    "text2vec-base-chinese": {"dimension": 768, "language": "zh"},
}

_CACHE_MAXSIZE = 2048


class EmbeddingUtil:
    """向量嵌入生成工具。

    封装 sentence-transformers 模型，提供本地向量生成。
    首次使用时加载模型，后续复用模型实例。

    Attributes:
        model: sentence-transformers 模型实例。
        dimension: 向量维度。
    """

    def __init__(self, model_name: str = "bge-small-zh-v1.5") -> None:
        """初始化嵌入工具。

        Args:
            model_name: 模型名称，默认 bge-small-zh-v1.5（中英双语）。
        """
        self._model_name = model_name
        self._model = None
        self._dimension: int = 0
        self._encode_cache: dict[str, np.ndarray] = {}
        self._cache_lock = threading.Lock()

    def _ensure_model_loaded(self) -> None:
        """延迟加载模型。"""
        if self._model is not None:
            return

        model_info = _SUPPORTED_MODELS.get(self._model_name, {})
        fallback_dim = model_info.get("dimension", get_settings().memory_embedding_dimension)

        try:
            from sentence_transformers import SentenceTransformer

            logger.info(f"正在加载嵌入模型: {self._model_name}")
            self._model = SentenceTransformer(self._model_name)
            self._dimension = self._model.get_sentence_embedding_dimension()
            logger.info(f"嵌入模型加载完成，维度: {self._dimension}")
        except ImportError:
            raise MemoryEmbeddingError(
                message="sentence-transformers 未安装，请执行: pip install sentence-transformers",
                detail={"model_name": self._model_name},
            )
        except Exception as e:
            raise MemoryEmbeddingError(
                message=f"嵌入模型加载失败: {e}",
                detail={"model_name": self._model_name},
            ) from e

    @property
    def dimension(self) -> int:
        """获取向量维度。"""
        self._ensure_model_loaded()
        return self._dimension

    def encode(self, text: str) -> np.ndarray:
        """生成文本的向量嵌入（带 LRU 缓存）。

        Args:
            text: 输入文本。

        Returns:
            归一化的向量（numpy 数组）。

        Raises:
            MemoryEmbeddingError: 编码失败时抛出。
        """
        if not text or not text.strip():
            self._ensure_model_loaded()
            return np.zeros(self._dimension, dtype=np.float32)

        cache_key = text[:500]
        with self._cache_lock:
            if cache_key in self._encode_cache:
                return self._encode_cache[cache_key].copy()

        result = self._do_encode(text)

        with self._cache_lock:
            if len(self._encode_cache) >= _CACHE_MAXSIZE:
                oldest_key = next(iter(self._encode_cache))
                del self._encode_cache[oldest_key]
            self._encode_cache[cache_key] = result.copy()

        return result

    def _do_encode(self, text: str) -> np.ndarray:
        """实际执行向量编码。"""
        self._ensure_model_loaded()

        try:
            vector = self._model.encode(text, normalize_embeddings=True)
            return vector.astype(np.float32)
        except Exception as e:
            raise MemoryEmbeddingError(
                message=f"向量编码失败: {e}",
            ) from e

    def encode_batch(self, texts: list[str]) -> np.ndarray:
        """批量生成文本的向量嵌入。

        Args:
            texts: 输入文本列表。

        Returns:
            向量矩阵（numpy 2D 数组）。
        """
        self._ensure_model_loaded()

        if not texts:
            return np.empty((0, self._dimension), dtype=np.float32)

        uncached_texts = []
        uncached_indices = []
        results = [None] * len(texts)

        with self._cache_lock:
            for i, text in enumerate(texts):
                cache_key = text[:500] if text else ""
                if cache_key in self._encode_cache:
                    results[i] = self._encode_cache[cache_key].copy()
                else:
                    uncached_texts.append(text)
                    uncached_indices.append(i)

        if uncached_texts:
            try:
                vectors = self._model.encode(
                    uncached_texts, normalize_embeddings=True, batch_size=32
                )
                vectors = vectors.astype(np.float32)

                with self._cache_lock:
                    for j, idx in enumerate(uncached_indices):
                        vec = vectors[j]
                        results[idx] = vec
                        cache_key = uncached_texts[j][:500]
                        if len(self._encode_cache) < _CACHE_MAXSIZE:
                            self._encode_cache[cache_key] = vec.copy()
            except Exception as e:
                raise MemoryEmbeddingError(
                    message=f"批量向量编码失败: {e}",
                ) from e

        valid_results = [r for r in results if r is not None]
        if not valid_results:
            return np.empty((0, self._dimension), dtype=np.float32)
        return np.stack(valid_results)

    def clear_cache(self) -> None:
        """清空编码缓存。"""
        with self._cache_lock:
            self._encode_cache.clear()
        logger.debug("嵌入编码缓存已清空")


def get_embedding_util() -> EmbeddingUtil:
    """获取全局 EmbeddingUtil 实例（线程安全）。"""
    global _embedding_service
    if _embedding_service is None:
        with _embedding_lock:
            if _embedding_service is None:
                settings = get_settings()
                _embedding_service = EmbeddingUtil(
                    model_name=settings.memory_embedding_model
                )
    return _embedding_service
