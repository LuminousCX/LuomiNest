from __future__ import annotations

from pathlib import Path

from loguru import logger

from app.core.config import settings
from app.engines.memory.core.memory_engine import MemoryEngine
from app.engines.memory.core.event_bus import MemoryEventBus

_engine: MemoryEngine | None = None
_event_bus: MemoryEventBus | None = None


def get_memory_engine() -> MemoryEngine:
    if _engine is None:
        raise RuntimeError("Memory engine not initialized. Call init_memory() first.")
    return _engine


def get_event_bus() -> MemoryEventBus:
    if _event_bus is None:
        raise RuntimeError("Memory event bus not initialized. Call init_memory() first.")
    return _event_bus


async def init_memory(
    memory_root: str | None = None,
    enable_semantic: bool = False,
) -> MemoryEngine:
    global _engine, _event_bus

    if _engine is not None:
        return _engine

    from app.engines.memory.core.storage import MemoryStorage
    from app.engines.memory.core.distiller import MemoryDistiller
    from app.engines.memory.search.memory_search import MemorySearchEngine

    root = memory_root or str(Path(settings.DATA_DIR) / "memory")
    storage = MemoryStorage(root)

    _event_bus = MemoryEventBus()
    await _event_bus.start()

    distiller = MemoryDistiller()
    search_engine = MemorySearchEngine(storage)

    _engine = MemoryEngine(
        storage=storage,
        distiller=distiller,
        event_bus=_event_bus,
    )

    if not (Path(root) / "user_space.json").exists():
        legacy_files = list(Path(root).glob("memory_*.json"))
        if legacy_files:
            logger.info("[Memory] Found legacy v2 data, running migration...")
            from app.engines.memory.core.migration import migrate_v2_to_v3
            await migrate_v2_to_v3()

    if enable_semantic:
        try:
            await search_engine.rebuild_index()
        except Exception as e:
            logger.warning(f"[Memory] Semantic index rebuild failed: {e}")

    logger.info("[Memory] Engine initialized")
    return _engine


async def shutdown_memory() -> None:
    global _engine, _event_bus
    if _event_bus:
        await _event_bus.stop()
    _engine = None
    _event_bus = None
    logger.info("[Memory] Engine shut down")
