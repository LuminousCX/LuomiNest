"""记忆系统相关请求/响应参数校验模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.model.chunk import ChunkType
from src.model.entity import EntityType


class MemoryStoreRequest(BaseModel):
    """记忆存储请求。"""

    agent_id: int = Field(..., ge=1, description="Agent ID")
    user_msg: str = Field(..., min_length=1, max_length=5000, description="用户消息")
    assistant_msg: str = Field(..., min_length=1, max_length=5000, description="助手回复")


class MemoryRetrieveRequest(BaseModel):
    """记忆检索请求。"""

    agent_id: int = Field(..., ge=1, description="Agent ID")
    query: str = Field(..., min_length=1, max_length=2000, description="查询文本")
    top_k: int = Field(default=10, ge=1, le=50, description="返回数量")


class MemoryResponse(BaseModel):
    """记忆条目响应。"""

    id: int = Field(description="记忆ID")
    content: str = Field(description="记忆内容")
    chunk_type: ChunkType = Field(description="记忆类型")
    agent_id: int = Field(description="Agent ID")
    confidence: float = Field(description="置信度")
    is_expired: bool = Field(description="是否过期")
    merge_count: int = Field(description="合并次数")
    created_at: datetime = Field(description="创建时间")


class MemoryRetrieveResponse(BaseModel):
    """记忆检索响应。"""

    memories: list[str] = Field(default_factory=list, description="召回的记忆内容列表")
    total: int = Field(default=0, description="召回数量")


class MemoryListResponse(BaseModel):
    """记忆列表响应。"""

    memories: list[MemoryResponse] = Field(default_factory=list, description="记忆列表")
    total: int = Field(default=0, description="总数")


class EntityResponse(BaseModel):
    """实体知识响应。"""

    id: int = Field(description="实体ID")
    name: str = Field(description="实体名称")
    type: EntityType = Field(description="实体类型")
    description: Optional[str] = Field(default=None, description="实体描述")
    agent_id: int = Field(description="Agent ID")
    count: int = Field(description="出现次数")
    last_seen_at: datetime = Field(description="最后出现时间")


class EntityListResponse(BaseModel):
    """实体知识列表响应。"""

    entities: list[EntityResponse] = Field(default_factory=list, description="实体列表")
    total: int = Field(default=0, description="总数")


class MemoryClearResponse(BaseModel):
    """记忆清空响应。"""

    deleted_chunks: int = Field(default=0, description="删除的记忆数")
    deleted_entities: int = Field(default=0, description="删除的实体数")
