import json
import os
import re
import threading
from loguru import logger
from app.core.config import settings
from app.runtime.provider.llm.adapter import llm_adapter


def tokenize(text: str) -> set[str]:
    tokens = set()
    text_lower = text.lower()
    words = re.findall(r"[a-zA-Z]+", text_lower)
    tokens.update(words)
    chinese_chars = re.findall(r"[\u4e00-\u9fff]+", text_lower)
    for chars in chinese_chars:
        tokens.update(chars)
        if len(chars) > 1:
            for i in range(len(chars) - 1):
                tokens.add(chars[i:i + 2])
    numbers = re.findall(r"\d+", text_lower)
    tokens.update(numbers)
    return tokens


class RAGRetriever:
    _global_lock = threading.Lock()
    _expected_dim: int | None = None

    def __init__(self):
        self._index_dir = os.path.join(settings.DATA_DIR, "rag", "index")
        os.makedirs(self._index_dir, exist_ok=True)

    def _load_chunks(self) -> list[dict]:
        index_file = os.path.join(self._index_dir, "chunks.json")
        if not os.path.exists(index_file):
            return []
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[RAG] Failed to load index: {e}")
            return []

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        if not query or not query.strip():
            logger.warning("[RAG] Empty query, returning empty results")
            return []

        logger.info(f"[RAG] Searching for: '{query}', top_k={top_k}")

        query_embedding = None
        try:
            query_embedding = await llm_adapter.embed(query)
            if query_embedding:
                if self._expected_dim is None:
                    self._expected_dim = len(query_embedding)
                elif len(query_embedding) != self._expected_dim:
                    logger.warning(
                        f"[RAG] Query embedding dimension mismatch: expected {self._expected_dim}, got {len(query_embedding)}"
                    )
                    query_embedding = None
        except Exception as e:
            logger.warning(f"[RAG] Embedding failed, falling back to keyword search: {e}")

        with self._global_lock:
            chunks = self._load_chunks()
            if not chunks:
                logger.info("[RAG] No index file found, returning empty results")
                return []

            scored = []
            for chunk in chunks:
                embedding = chunk.get("embedding", [])
                if query_embedding and embedding and len(embedding) == len(query_embedding):
                    score = self._cosine_similarity(query_embedding, embedding)
                else:
                    score = self._keyword_score(query, chunk.get("content", ""))
                scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, chunk in scored[:top_k]:
            results.append({
                "content": chunk.get("content", ""),
                "source": chunk.get("source", ""),
                "score": round(score, 4),
                "metadata": chunk.get("metadata", {}),
            })

        logger.success(f"[RAG] Found {len(results)} results for query: '{query}'")
        return results

    async def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        vector_weight: float = 0.7,
    ) -> list[dict]:
        if not query or not query.strip():
            return []

        query_embedding = None
        try:
            query_embedding = await llm_adapter.embed(query)
        except Exception as e:
            logger.warning(f"[RAG] Embedding failed for hybrid search: {e}")

        with self._global_lock:
            chunks = self._load_chunks()
            if not chunks:
                return []

            scored = []
            for chunk in chunks:
                vector_score = 0.0
                keyword_score = 0.0

                embedding = chunk.get("embedding", [])
                if query_embedding and embedding and len(embedding) == len(query_embedding):
                    vector_score = self._cosine_similarity(query_embedding, embedding)

                keyword_score = self._keyword_score(query, chunk.get("content", ""))
                combined = vector_weight * vector_score + (1 - vector_weight) * keyword_score
                scored.append((combined, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "content": c.get("content", ""),
                "source": c.get("source", ""),
                "score": round(s, 4),
                "metadata": c.get("metadata", {}),
            }
            for s, c in scored[:top_k]
        ]

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _keyword_score(query: str, content: str) -> float:
        query_tokens = tokenize(query)
        content_tokens = tokenize(content)
        if not query_tokens:
            return 0.0
        overlap = len(query_tokens & content_tokens)
        return overlap / len(query_tokens)
