from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from typing import Any
import asyncio

from app.engines.memory.core import (
    MemoryStorage,
    MemoryInjector,
    get_memory_storage,
)
from app.engines.memory.rag.indexer import RAGIndexer
from app.engines.memory.rag.retriever import RAGRetriever

router = APIRouter(prefix="/memory", tags=["Memory"])


class AddFactRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    category: str = Field(default="context", pattern="^(preference|knowledge|context|behavior|goal|correction)$")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    agent_id: str | None = None
    source: str = Field(default="manual")


class UpdateFactRequest(BaseModel):
    content: str | None = Field(None, min_length=1, max_length=2000)
    category: str | None = Field(None, pattern="^(preference|knowledge|context|behavior|goal|correction)$")
    confidence: float | None = Field(None, ge=0.0, le=1.0)


class UpdateContextRequest(BaseModel):
    work_context: str | None = None
    personal_context: str | None = None
    top_of_mind: str | None = None


class IndexTextRequest(BaseModel):
    content: str = Field(..., min_length=1)
    source: str = Field(default="manual")
    metadata: dict[str, Any] | None = None
    chunk_size: int = Field(default=500, ge=100, le=2000)
    overlap: int = Field(default=50, ge=0, le=200)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


def _get_storage() -> MemoryStorage:
    return get_memory_storage()


@router.get("/")
async def get_memory(agent_id: str | None = Query(None, description="Agent ID for isolated memory")):
    storage = _get_storage()
    memory = await asyncio.to_thread(storage.load, agent_id)
    injector = MemoryInjector()
    return {
        "memory": memory.to_dict(),
        "summary": injector.get_memory_summary(memory),
    }


@router.delete("/")
async def clear_memory(agent_id: str | None = Query(None)):
    storage = _get_storage()
    await asyncio.to_thread(storage.clear, agent_id)
    return {"status": "success", "message": "Memory cleared"}


@router.get("/summary")
async def get_memory_summary(agent_id: str | None = Query(None)):
    storage = _get_storage()
    memory = await asyncio.to_thread(storage.load, agent_id)
    injector = MemoryInjector()
    return injector.get_memory_summary(memory)


@router.post("/facts")
async def add_fact(request: AddFactRequest):
    storage = _get_storage()
    memory = await asyncio.to_thread(
        storage.add_fact,
        content=request.content,
        category=request.category,
        confidence=request.confidence,
        agent_id=request.agent_id,
        source=request.source,
    )
    return {"status": "success", "fact_id": memory.facts[-1].id, "total_facts": len(memory.facts)}


@router.delete("/facts/{fact_id}")
async def delete_fact(fact_id: str, agent_id: str | None = Query(None)):
    storage = _get_storage()
    memory = await asyncio.to_thread(storage.delete_fact, fact_id, agent_id)
    return {"status": "success", "total_facts": len(memory.facts)}


@router.patch("/facts/{fact_id}")
async def update_fact(fact_id: str, request: UpdateFactRequest, agent_id: str | None = Query(None)):
    storage = _get_storage()
    memory = await asyncio.to_thread(
        storage.update_fact,
        fact_id=fact_id,
        content=request.content,
        category=request.category,
        confidence=request.confidence,
        agent_id=agent_id,
    )
    return {"status": "success", "total_facts": len(memory.facts)}


@router.put("/context")
async def update_context(request: UpdateContextRequest, agent_id: str | None = Query(None)):
    from app.engines.memory.core.models import utc_now_iso_z
    storage = _get_storage()
    memory = await asyncio.to_thread(storage.load, agent_id)
    now = utc_now_iso_z()
    if request.work_context is not None:
        memory.user.work_context.summary = request.work_context
        memory.user.work_context.updated_at = now
    if request.personal_context is not None:
        memory.user.personal_context.summary = request.personal_context
        memory.user.personal_context.updated_at = now
    if request.top_of_mind is not None:
        memory.user.top_of_mind.summary = request.top_of_mind
        memory.user.top_of_mind.updated_at = now
    await asyncio.to_thread(storage.save, memory, agent_id)
    return {"status": "success"}


@router.post("/inject")
async def get_injection_content(agent_id: str | None = Query(None)):
    storage = _get_storage()
    memory = await asyncio.to_thread(storage.load, agent_id)
    injector = MemoryInjector()
    content = injector.format_memory_for_injection(memory)
    return {"content": content, "has_memory": bool(content.strip())}


@router.post("/index/text")
async def index_text(request: IndexTextRequest):
    indexer = RAGIndexer()
    count = await indexer.index_text(
        content=request.content,
        source=request.source,
        metadata=request.metadata,
        chunk_size=request.chunk_size,
        overlap=request.overlap,
    )
    return {"status": "success", "chunks_indexed": count}


@router.get("/index/stats")
async def get_index_stats():
    indexer = RAGIndexer()
    return await indexer.get_stats()


@router.delete("/index")
async def clear_index():
    indexer = RAGIndexer()
    await indexer.clear_index()
    return {"status": "success", "message": "RAG index cleared"}


@router.delete("/index/source")
async def remove_index_by_source(source: str = Query(..., description="Source to remove")):
    indexer = RAGIndexer()
    removed = await indexer.remove_by_source(source)
    return {"status": "success", "chunks_removed": removed}


@router.post("/search")
async def search_memory(request: SearchRequest):
    retriever = RAGRetriever()
    results = await retriever.search(query=request.query, top_k=request.top_k)
    return {"results": results, "total": len(results)}


@router.post("/search/hybrid")
async def hybrid_search_memory(request: SearchRequest, vector_weight: float = Query(0.7, ge=0.0, le=1.0)):
    retriever = RAGRetriever()
    results = await retriever.hybrid_search(
        query=request.query,
        top_k=request.top_k,
        vector_weight=vector_weight,
    )
    return {"results": results, "total": len(results)}
