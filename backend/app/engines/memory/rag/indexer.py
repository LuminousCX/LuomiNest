import asyncio
import hashlib
import json
import os
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
        return hashlib.sha256(content.strip().encode()).hexdigest()

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

    def _update_chunks_atomic(self, callback) -> list[dict]:
        with self._global_lock:
            existing, existing_hashes = self._load_existing_chunks_sync()
            result = callback(existing, existing_hashes)
            index_file = os.path.join(self._index_dir, "chunks.json")
            temp_file = index_file + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
            os.replace(temp_file, index_file)
            return result

    def _save_chunks_sync(self, chunks: list[dict]) -> None:
        with self._global_lock:
            index_file = os.path.join(self._index_dir, "chunks.json")
            temp_file = index_file + ".tmp"
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(chunks, f, ensure_ascii=False, indent=2)
            os.replace(temp_file, index_file)

    async def _save_chunks(self, chunks: list[dict]) -> None:
        await asyncio.to_thread(self._save_chunks_sync, chunks)

    def _validate_chunk_params(self, chunk_size: int, overlap: int) -> tuple[int, int]:
        if chunk_size <= 0:
            logger.error(f"[RAG] Invalid chunk_size={chunk_size}, must be > 0")
            chunk_size = 500
        if overlap < 0:
            logger.error(f"[RAG] Invalid overlap={overlap}, must be >= 0")
            overlap = 0
        if overlap >= chunk_size:
            logger.error(f"[RAG] overlap={overlap} >= chunk_size={chunk_size}, adjusting overlap to {chunk_size - 1}")
            overlap = chunk_size - 1
        return chunk_size, overlap

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

        chunk_size, overlap = self._validate_chunk_params(chunk_size, overlap)

        content = content.strip()
        if len(content) > 10_000_000:
            logger.warning(f"[RAG] Content too large ({len(content)} chars), truncating to 10M chars")
            content = content[:10_000_000]

        logger.info(f"[RAG] Indexing text from source: {source}, content_len={len(content)}")
        chunks = self._chunk_text(content, chunk_size, overlap)

        pre_existing, pre_existing_hashes = await self._load_existing_chunks()
        indexed = []
        skipped = 0

        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue

            content_hash = self._get_content_hash(chunk)
            if skip_duplicates and content_hash in pre_existing_hashes:
                is_true_duplicate = any(
                    c.get("content_hash") == content_hash and c.get("content") == chunk
                    for c in pre_existing
                )
                if is_true_duplicate:
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

        if not indexed:
            logger.info(f"[RAG] No new chunks to index (skipped {skipped} duplicates)")
            return 0

        def _atomic_append(existing: list[dict], existing_hashes: set[str]) -> list[dict]:
            for item in indexed:
                item_hash = item["content_hash"]
                if skip_duplicates and item_hash in existing_hashes:
                    if any(c.get("content_hash") == item_hash and c.get("content") == item["content"] for c in existing):
                        continue
                existing.append(item)
                existing_hashes.add(item_hash)
            return existing

        await asyncio.to_thread(self._update_chunks_atomic, _atomic_append)

        logger.success(f"[RAG] Indexed {len(indexed)} chunks from {source} (skipped {skipped} duplicates)")
        return len(indexed)

    async def index_file(self, file_path: str, metadata: dict | None = None, max_size_mb: int = 100) -> int:
        logger.info(f"[RAG] Indexing file: {os.path.basename(file_path)}")
        try:
            file_size = await asyncio.to_thread(os.path.getsize, file_path)
            max_size = max_size_mb * 1024 * 1024
            if file_size > max_size:
                logger.warning(f"[RAG] File too large ({file_size} bytes), skipping")
                return 0

            def _read_file(path: str) -> str:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()

            content = await asyncio.to_thread(_read_file, file_path)
            return await self.index_text(content, source=file_path, metadata=metadata)
        except Exception as e:
            logger.error(f"[RAG] Failed to index file {os.path.basename(file_path)}: {e}")
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
        def _atomic_remove(existing: list[dict], existing_hashes: set[str]) -> list[dict]:
            original_count = len(existing)
            to_remove_hashes = set()
            filtered = []
            for c in existing:
                if c.get("source") == source:
                    to_remove_hashes.add(c.get("content_hash"))
                else:
                    filtered.append(c)
            existing_hashes.difference_update(to_remove_hashes)
            existing.clear()
            existing.extend(filtered)
            return original_count - len(existing)

        removed = await asyncio.to_thread(self._update_chunks_atomic, _atomic_remove)
        if removed > 0:
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
