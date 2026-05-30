from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Any
import asyncio

from loguru import logger

from app.engines.memory.core.storage import get_memory_storage
from app.engines.memory.core.models import (
    UserSpace,
    AgentMemory,
    MemoryFact,
    utc_now_iso_z,
)
from app.engines.memory.core.memory_engine import MemoryEngine
from app.engines.memory.export import MemoryExporter
from app.engines.memory.export.markdown_parser import MarkdownParser
from app.engines.memory.rag.indexer import RAGIndexer
from app.engines.memory.rag.retriever import RAGRetriever

router = APIRouter(prefix="/memory", tags=["Memory"])


class AddFactRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    category: str = Field(default="context", pattern="^(preference|knowledge|context|behavior|goal|correction)$")
    tier: str = Field(default="temporary_context", pattern="^(core_identity|long_term_preference|temporary_context)$")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    layer: str = Field(default="user", pattern="^(user|agent|working)$")
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


class UpdateProfileRequest(BaseModel):
    name: str | None = None
    nickname: str | None = None
    age: str | None = None
    gender: str | None = None
    occupation: str | None = None
    location: str | None = None
    language: str | None = None
    interests: list[str] | None = None
    hobbies: list[str] | None = None


class ImportMarkdownRequest(BaseModel):
    markdown: str = Field(..., min_length=1)
    agent_id: str | None = None


class IndexTextRequest(BaseModel):
    content: str = Field(..., min_length=1)
    source: str = Field(default="manual")
    metadata: dict[str, Any] | None = None
    chunk_size: int = Field(default=500, ge=100, le=2000)
    overlap: int = Field(default=50, ge=0, le=200)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


@router.get("/")
async def get_memory(agent_id: str | None = Query(None)):
    storage = get_memory_storage()
    user_space = await asyncio.to_thread(storage.load_user_space)
    has_v3 = bool(
        user_space.facts or user_space.episodic_events
        or user_space.profile.name or user_space.profile.occupation
        or user_space.distilled.core_identity or user_space.distilled.long_term
    )
    if has_v3:
        effective_agent_id = agent_id or "default"
        agent_memory = await asyncio.to_thread(storage.load_agent_memory, effective_agent_id)
        return {
            "version": "3.0",
            "user_space": user_space.to_dict(),
            "agent_memory": agent_memory.to_dict(),
        }
    memory_data = await asyncio.to_thread(storage.load, agent_id)
    return {
        "version": "2.0",
        "memory": memory_data.to_dict(),
    }


@router.delete("/")
async def clear_memory(agent_id: str | None = Query(None)):
    storage = get_memory_storage()
    await asyncio.to_thread(storage.clear, agent_id)
    return {"status": "success", "message": "Memory cleared"}


@router.get("/user-space")
async def get_user_space():
    storage = get_memory_storage()
    user_space = await asyncio.to_thread(storage.load_user_space)
    return {"user_space": user_space.to_dict()}


@router.put("/user-space/profile")
async def update_profile(request: UpdateProfileRequest):
    storage = get_memory_storage()
    user_space = await asyncio.to_thread(storage.load_user_space)
    now = utc_now_iso_z()
    if request.name is not None:
        user_space.profile.name = request.name
    if request.nickname is not None:
        user_space.profile.nickname = request.nickname
    if request.age is not None:
        user_space.profile.age = request.age
    if request.gender is not None:
        user_space.profile.gender = request.gender
    if request.occupation is not None:
        user_space.profile.occupation = request.occupation
    if request.location is not None:
        user_space.profile.location = request.location
    if request.language is not None:
        user_space.profile.language = request.language
    if request.interests is not None:
        user_space.profile.interests = request.interests
    if request.hobbies is not None:
        user_space.profile.hobbies = request.hobbies
    user_space.profile.updated_at = now
    await asyncio.to_thread(storage.save_user_space, user_space)
    return {"status": "success"}


@router.get("/agent/{agent_id}")
async def get_agent_memory(agent_id: str):
    storage = get_memory_storage()
    agent_memory = await asyncio.to_thread(storage.load_agent_memory, agent_id)
    return {"agent_memory": agent_memory.to_dict()}


@router.get("/summary")
async def get_memory_summary(agent_id: str | None = Query(None)):
    storage = get_memory_storage()
    user_space = await asyncio.to_thread(storage.load_user_space)

    facts_by_tier: dict[str, int] = {}
    for fact in user_space.facts:
        facts_by_tier[fact.tier] = facts_by_tier.get(fact.tier, 0) + 1

    profile = user_space.profile
    has_profile = bool(
        profile.name or profile.nickname or profile.occupation
        or profile.location or profile.interests or profile.hobbies
    )

    result = {
        "version": "3.0",
        "has_profile": has_profile,
        "total_user_facts": len(user_space.facts),
        "total_user_events": len(user_space.episodic_events),
        "total_archived": len(user_space.archived_facts),
        "facts_by_tier": facts_by_tier,
        "has_distilled": bool(
            user_space.distilled.core_identity
            or user_space.distilled.long_term
            or user_space.distilled.temporary
        ),
        "last_updated": user_space.last_updated,
    }

    if agent_id:
        agent_memory = await asyncio.to_thread(storage.load_agent_memory, agent_id)
        result["agent_facts"] = len(agent_memory.agent_facts)
        result["agent_events"] = len(agent_memory.agent_events)
        result["has_domain_summary"] = bool(agent_memory.domain_summary)

    return result


@router.post("/facts")
async def add_fact(request: AddFactRequest):
    storage = get_memory_storage()
    fact = await asyncio.to_thread(
        storage.add_fact,
        content=request.content,
        category=request.category,
        confidence=request.confidence,
        agent_id=request.agent_id if request.layer == "agent" else None,
        source=request.source,
    )
    return {"status": "success", "fact_id": fact.id}


@router.delete("/facts/{fact_id}")
async def delete_fact(fact_id: str, agent_id: str | None = Query(None)):
    storage = get_memory_storage()
    result = await asyncio.to_thread(storage.delete_fact, fact_id, agent_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Fact with id '{fact_id}' not found")
    return {"status": "success"}


@router.patch("/facts/{fact_id}")
async def update_fact(fact_id: str, request: UpdateFactRequest, agent_id: str | None = Query(None)):
    storage = get_memory_storage()
    result = await asyncio.to_thread(
        storage.update_fact,
        fact_id=fact_id,
        content=request.content,
        category=request.category,
        confidence=request.confidence,
        agent_id=agent_id,
    )
    if not result:
        raise HTTPException(status_code=404, detail=f"Fact with id '{fact_id}' not found")
    return {"status": "success"}


@router.put("/context")
async def update_context(request: UpdateContextRequest, agent_id: str | None = Query(None)):
    storage = get_memory_storage()
    now = utc_now_iso_z()

    user_space = await asyncio.to_thread(storage.load_user_space)
    if request.work_context is not None:
        user_space.user.work_context.summary = request.work_context
        user_space.user.work_context.updated_at = now
    if request.personal_context is not None:
        user_space.user.personal_context.summary = request.personal_context
        user_space.user.personal_context.updated_at = now
    if request.top_of_mind is not None:
        user_space.user.top_of_mind.summary = request.top_of_mind
        user_space.user.top_of_mind.updated_at = now
    await asyncio.to_thread(storage.save_user_space, user_space)

    return {"status": "success"}


@router.post("/inject")
async def get_injection_content(agent_id: str | None = Query(None)):
    storage = get_memory_storage()
    user_space = await asyncio.to_thread(storage.load_user_space)
    effective_agent_id = agent_id or "default"
    agent_memory = await asyncio.to_thread(storage.load_agent_memory, effective_agent_id)

    from app.engines.memory.core.injector import MemoryInjector
    injector = MemoryInjector()
    content = injector.inject_v3_memory_to_messages(
        [{"role": "system", "content": ""}],
        user_space, agent_memory,
    )
    injected = content[0].get("content", "") if content else ""
    return {"content": injected, "has_memory": bool(injected.strip())}


@router.get("/export")
async def export_memory(agent_id: str | None = Query(None)):
    storage = get_memory_storage()
    exporter = MemoryExporter(storage)
    md = exporter.export_full_memory(agent_id)
    return {"markdown": md}


@router.post("/import")
async def import_memory(request: ImportMarkdownRequest):
    storage = get_memory_storage()
    user_space = await asyncio.to_thread(storage.load_user_space)
    parser = MarkdownParser()
    stats = parser.parse_and_update(request.markdown, user_space, request.agent_id)
    await asyncio.to_thread(storage.save_user_space, user_space)
    return {"status": "success", "stats": stats}


@router.post("/search")
async def search_memory(request: SearchRequest):
    storage = get_memory_storage()
    engine = MemoryEngine(storage=storage)
    results = await engine.search_facts(request.query, top_k=request.top_k)
    return {
        "results": [
            {
                "id": f.id,
                "content": f.content,
                "category": f.category,
                "tier": f.tier,
                "layer": f.layer,
                "confidence": f.confidence,
            }
            for f in results
        ],
        "total": len(results),
    }


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


@router.post("/search/hybrid")
async def hybrid_search_memory(request: SearchRequest, vector_weight: float = Query(0.7, ge=0.0, le=1.0)):
    retriever = RAGRetriever()
    results = await retriever.hybrid_search(
        query=request.query,
        top_k=request.top_k,
        vector_weight=vector_weight,
    )
    return {"results": results, "total": len(results)}
