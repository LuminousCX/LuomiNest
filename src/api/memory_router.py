"""记忆系统 API 路由。

提供记忆的存储、检索、查询、删除、清空等接口。
所有接口按 agent_id 完全隔离记忆空间。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from typing_extensions import Annotated

from src.schema.common_schema import ApiResponse
from src.schema.memory_schema import (
    EntityListResponse,
    EntityResponse,
    MemoryClearResponse,
    MemoryListResponse,
    MemoryResponse,
    MemoryRetrieveRequest,
    MemoryRetrieveResponse,
    MemoryStoreRequest,
)
from src.service.memory_service import MemoryService
from src.utils.logger import get_logger

logger = get_logger()

router = APIRouter(prefix="/memory", tags=["记忆系统"])


def get_memory_service() -> MemoryService:
    """获取 MemoryService 实例（依赖注入）。"""
    from src.api.deps import get_services
    return get_services()["memory_service"]


@router.post("/memorize", summary="写入记忆")
async def memorize(
    request: MemoryStoreRequest,
    memory_service: Annotated[MemoryService, Depends(get_memory_service)],
) -> ApiResponse[dict]:
    """将对话写入记忆系统。"""
    user_chunk_id, assistant_chunk_id = await memory_service.memorize(
        agent_id=request.agent_id,
        user_msg=request.user_msg,
        assistant_msg=request.assistant_msg,
    )
    data = {
        "user_chunk_id": user_chunk_id,
        "assistant_chunk_id": assistant_chunk_id,
    }
    return ApiResponse.success(data=data, message="记忆写入成功")


@router.post("/retrieve", summary="检索记忆")
async def retrieve(
    request: MemoryRetrieveRequest,
    memory_service: Annotated[MemoryService, Depends(get_memory_service)],
) -> ApiResponse[MemoryRetrieveResponse]:
    """根据查询检索最相关的记忆。"""
    memories = memory_service.retrieve(
        agent_id=request.agent_id,
        query=request.query,
        top_k=request.top_k,
    )
    content_list = [m.get("content", "") for m in memories]
    data = MemoryRetrieveResponse(memories=content_list, total=len(memories))
    return ApiResponse.success(data=data)


@router.get("/{agent_id}/memories", summary="获取记忆列表")
async def list_memories(
    agent_id: int,
    limit: int = 100,
    offset: int = 0,
    memory_service: Annotated[MemoryService, Depends(get_memory_service)],
) -> ApiResponse[MemoryListResponse]:
    """获取指定 Agent 的记忆列表。"""
    chunks = memory_service.get_memories_by_agent(agent_id, limit, offset)
    total = memory_service.count_memories(agent_id)

    memory_responses = [
        MemoryResponse(
            id=c.id,
            content=c.content,
            chunk_type=c.chunk_type,
            agent_id=c.agent_id,
            confidence=c.confidence,
            is_expired=c.is_expired,
            merge_count=c.merge_count,
            created_at=c.created_at,
        )
        for c in chunks
    ]

    data = MemoryListResponse(memories=memory_responses, total=total)
    return ApiResponse.success(data=data)


@router.get("/{agent_id}/entities", summary="获取实体知识列表")
async def list_entities(
    agent_id: int,
    limit: int = 100,
    offset: int = 0,
    memory_service: Annotated[MemoryService, Depends(get_memory_service)],
) -> ApiResponse[EntityListResponse]:
    """获取指定 Agent 的实体知识列表。"""
    entities = memory_service.get_entities_by_agent(agent_id, limit, offset)
    total = memory_service.count_entities(agent_id)

    entity_responses = [
        EntityResponse(
            id=e.id,
            name=e.name,
            type=e.type,
            description=e.description,
            agent_id=e.agent_id,
            count=e.count,
            last_seen_at=e.last_seen_at,
        )
        for e in entities
    ]

    data = EntityListResponse(entities=entity_responses, total=total)
    return ApiResponse.success(data=data)


@router.delete("/{agent_id}/clear", summary="清空所有记忆")
async def clear_memories(
    agent_id: int,
    memory_service: Annotated[MemoryService, Depends(get_memory_service)],
) -> ApiResponse[MemoryClearResponse]:
    """清空指定 Agent 的所有记忆和实体知识。"""
    deleted_chunks, deleted_entities = memory_service.clear(agent_id)
    data = MemoryClearResponse(
        deleted_chunks=deleted_chunks,
        deleted_entities=deleted_entities,
    )
    return ApiResponse.success(data=data, message="记忆清空成功")


@router.delete("/chunk/{memory_id}", summary="删除单条记忆")
async def delete_memory(
    memory_id: int,
    memory_service: Annotated[MemoryService, Depends(get_memory_service)],
) -> ApiResponse[None]:
    """删除指定的单条记忆。"""
    memory_service.delete_memory(memory_id)
    return ApiResponse.success(message="记忆删除成功")


@router.get("/{agent_id}/stats", summary="获取记忆统计信息")
async def get_memory_stats(
    agent_id: int,
    memory_service: Annotated[MemoryService, Depends(get_memory_service)],
) -> ApiResponse[dict]:
    """获取指定 Agent 的记忆统计信息。"""
    memory_count = memory_service.count_memories(agent_id)
    entity_count = memory_service.count_entities(agent_id)
    data = {
        "memory_count": memory_count,
        "entity_count": entity_count,
    }
    return ApiResponse.success(data=data)
