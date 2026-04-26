import json
import os
from loguru import logger
from app.core.config import settings
from app.runtime.provider.llm.adapter import llm_adapter


class RAGIndexer:
    def __init__(self):
        self._index_dir = os.path.join(settings.DATA_DIR, "rag", "index")
        os.makedirs(self._index_dir, exist_ok=True)

    async def index_text(self, content: str, source: str, metadata: dict | None = None, chunk_size: int = 500, overlap: int = 50) -> int:
        logger.info(f"[RAG] Indexing text from source: {source}, content_len={len(content)}")
        chunks = self._chunk_text(content, chunk_size, overlap)
        indexed = []

        for i, chunk in enumerate(chunks):
            try:
                embedding = await llm_adapter.embed(chunk)
            except Exception as e:
                logger.warning(f"[RAG] Embedding failed for chunk {i}, storing without embedding: {e}")
                embedding = []

            indexed.append({
                "content": chunk,
                "source": source,
                "chunk_index": i,
                "embedding": embedding,
                "metadata": metadata or {},
            })

        index_file = os.path.join(self._index_dir, "chunks.json")
        existing = []
        if os.path.exists(index_file):
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                existing = []

        existing.extend(indexed)
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

        logger.success(f"[RAG] Indexed {len(indexed)} chunks from {source}")
        return len(indexed)

    async def index_file(self, file_path: str, metadata: dict | None = None) -> int:
        logger.info(f"[RAG] Indexing file: {file_path}")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return await self.index_text(content, source=file_path, metadata=metadata)
        except Exception as e:
            logger.error(f"[RAG] Failed to index file {file_path}: {e}")
            return 0

    def clear_index(self):
        index_file = os.path.join(self._index_dir, "chunks.json")
        if os.path.exists(index_file):
            os.remove(index_file)
            logger.info("[RAG] Index cleared")

    @staticmethod
    def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]

            if end < len(text):
                last_period = chunk.rfind("。")
                last_newline = chunk.rfind("\n")
                last_space = chunk.rfind(" ")
                split_at = max(last_period, last_newline, last_space)
                if split_at > chunk_size * 0.5:
                    chunk = text[start:start + split_at + 1]
                    end = start + split_at + 1

            chunks.append(chunk.strip())
            start = end - overlap

        return [c for c in chunks if c]
