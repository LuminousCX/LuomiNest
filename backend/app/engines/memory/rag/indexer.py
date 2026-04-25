import asyncio
import hashlib
import json
import os
import re
import threading
from loguru import logger
from app.core.config import settings
from app.runtime.provider.llm.adapter import llm_adapter


class RAGIndexer:
    _global_lock = threading.Lock()

    def __init__(self):
        self._index_dir = os.path.join(settings.DATA_DIR, "rag", "index")
        os.makedirs(self._index_dir, exist_ok=True)
        self._embedding_dim: int | None = None

    def _get_content_hash(self, content: str) -> str:
        return hashlib.md5(content.strip().encode()).hexdigest()[:16]

    def _load_existing_chunks_sync(self) -> tuple[list[dict], set[str]]:
        index_file = os.path.join(self._index_dir, "chunks.json")
        existing = []
        existing_hashes = set()
        if os.path.exists(index_file):
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                for chunk in existing:
                    content_hash = chunk.get("content_hash")
                    if content_hash:
                        existing_hashes.add(content_hash)
                    else:
                        existing_hashes.add(self._get_content_hash(chunk.get("content", "")))
            except Exception as e:
                logger.warning(f"[RAG] Failed to load existing chunks: {e}")
                existing = []
        return existing, existing_hashes

    async def _load_existing_chunks(self) -> tuple[list[dict], set[str]]:
        return await asyncio.to_thread(self._load_existing_chunks_sync)

    async def index_text(
        self,
        content: str,
        source: str,
        metadata: dict | None = None,
        chunk_size: int = 500,
        overlap: int = 50,
        skip_duplicates: bool = True,
    ) -> int:
        if not content or not content.strip():
            logger.warning("[RAG] Empty content, skipping indexing")
            return 0

        content = content.strip()
        if len(content) > 10_000_000:
            logger.warning(f"[RAG] Content too large ({len(content)} chars), truncating to 10M chars")
            content = content[:10_000_000]

        logger.info(f"[RAG] Indexing text from source: {source}, content_len={len(content)}")
        chunks = self._chunk_text(content, chunk_size, overlap)

        existing, existing_hashes = await self._load_existing_chunks()
        indexed = []
        skipped = 0

        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue

            content_hash = self._get_content_hash(chunk)
            if skip_duplicates and content_hash in existing_hashes:
                skipped += 1
                continue

            try:
                embedding = await llm_adapter.embed(chunk)
                if embedding:
                    if self._embedding_dim is None:
                        self._embedding_dim = len(embedding)
                    elif len(embedding) != self._embedding_dim:
                        logger.warning(
                            f"[RAG] Embedding dimension mismatch: expected {self._embedding_dim}, got {len(embedding)}"
                        )
                        embedding = []
            except Exception as e:
                logger.warning(f"[RAG] Embedding failed for chunk {i}: {e}")
                embedding = []

            indexed.append({
                "content": chunk,
                "content_hash": content_hash,
                "source": source,
                "chunk_index": i,
                "embedding": embedding,
                "metadata": metadata or {},
            })
            existing_hashes.add(content_hash)

        if not indexed:
            logger.info(f"[RAG] No new chunks to index (skipped {skipped} duplicates)")
            return 0

        existing.extend(indexed)
        await self._save_chunks(existing)

        logger.success(f"[RAG] Indexed {len(indexed)} chunks from {source} (skipped {skipped} duplicates)")
        return len(indexed)

    def _save_chunks_sync(self, chunks: list[dict]) -> None:
        with self._global_lock:
            index_file = os.path.join(self._index_dir, "chunks.json")
            temp_file = index_file + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(chunks, f, ensure_ascii=False, indent=2)
            os.replace(temp_file, index_file)

    async def _save_chunks(self, chunks: list[dict]) -> None:
        await asyncio.to_thread(self._save_chunks_sync, chunks)

    async def index_file(self, file_path: str, metadata: dict | None = None, max_size_mb: int = 100) -> int:
        logger.info(f"[RAG] Indexing file: {file_path}")
        try:
            file_size = await asyncio.to_thread(os.path.getsize, file_path)
            max_size = max_size_mb * 1024 * 1024
            if file_size > max_size:
                logger.warning(f"[RAG] File too large ({file_size} bytes), skipping")
                return 0

            content = await asyncio.to_thread(
                lambda: open(file_path, "r", encoding="utf-8").read()
            )
            return await self.index_text(content, source=file_path, metadata=metadata)
        except Exception as e:
            logger.error(f"[RAG] Failed to index file {file_path}: {e}")
            return 0

    def clear_index_sync(self):
        with self._global_lock:
            index_file = os.path.join(self._index_dir, "chunks.json")
            if os.path.exists(index_file):
                os.remove(index_file)
                logger.info("[RAG] Index cleared")

    async def clear_index(self):
        await asyncio.to_thread(self.clear_index_sync)

    async def remove_by_source(self, source: str) -> int:
        existing, _ = await self._load_existing_chunks()
        original_count = len(existing)
        filtered = [c for c in existing if c.get("source") != source]
        removed = original_count - len(filtered)

        if removed > 0:
            await self._save_chunks(filtered)
            logger.info(f"[RAG] Removed {removed} chunks from source: {source}")

        return removed

    async def get_stats(self) -> dict:
        existing, _ = await self._load_existing_chunks()
        sources = set()
        total_with_embedding = 0
        for chunk in existing:
            sources.add(chunk.get("source", "unknown"))
            if chunk.get("embedding"):
                total_with_embedding += 1
        return {
            "total_chunks": len(existing),
            "chunks_with_embedding": total_with_embedding,
            "unique_sources": len(sources),
            "sources": list(sources),
        }

    @staticmethod
    def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
        if len(text) <= chunk_size:
            return [text] if text.strip() else []

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
