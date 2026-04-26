import json
import os
from loguru import logger
from app.core.config import settings
from app.runtime.provider.llm.adapter import llm_adapter


class RAGRetriever:
    def __init__(self):
        self._index_dir = os.path.join(settings.DATA_DIR, "rag", "index")
        os.makedirs(self._index_dir, exist_ok=True)

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        logger.info(f"[RAG] Searching for: '{query}', top_k={top_k}")
        try:
            query_embedding = await llm_adapter.embed(query)
        except Exception as e:
            logger.warning(f"[RAG] Embedding failed, falling back to keyword search: {e}")
            return await self._keyword_search(query, top_k)

        index_file = os.path.join(self._index_dir, "chunks.json")
        if not os.path.exists(index_file):
            logger.info("[RAG] No index file found, returning empty results")
            return []

        try:
            with open(index_file, "r", encoding="utf-8") as f:
                chunks = json.load(f)
        except Exception as e:
            logger.error(f"[RAG] Failed to load index: {e}")
            return []

        scored = []
        for chunk in chunks:
            embedding = chunk.get("embedding", [])
            if embedding:
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
                "score": score,
                "metadata": chunk.get("metadata", {}),
            })

        logger.success(f"[RAG] Found {len(results)} results for query: '{query}'")
        return results

    async def _keyword_search(self, query: str, top_k: int) -> list[dict]:
        index_file = os.path.join(self._index_dir, "chunks.json")
        if not os.path.exists(index_file):
            return []

        try:
            with open(index_file, "r", encoding="utf-8") as f:
                chunks = json.load(f)
        except Exception:
            return []

        query_lower = query.lower()
        query_words = set(query_lower.split())
        scored = []
        for chunk in chunks:
            content = chunk.get("content", "").lower()
            words = set(content.split())
            overlap = len(query_words & words)
            if overlap > 0:
                scored.append((overlap / max(len(query_words), 1), chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"content": c.get("content", ""), "source": c.get("source", ""), "score": s, "metadata": c.get("metadata", {})}
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
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())
        if not query_words:
            return 0.0
        overlap = len(query_words & content_words)
        return overlap / len(query_words)
