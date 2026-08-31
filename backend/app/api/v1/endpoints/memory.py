import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.utils import ok
from app.engines.memory import get_memory_engine
from app.engines.memory.memory_engine import FactItem, FACT_CATEGORIES, _engines
from app.api.v1.deps import get_agents_store, get_conversation_store

router = APIRouter(prefix="/memory", tags=["Memory"])


class AppendRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    date: str | None = None
    conversation_id: str | None = None


class UpdateContentRequest(BaseModel):
    content: str = Field(..., min_length=1)


class DistillRequest(BaseModel):
    messages: list[dict] = Field(..., min_length=1)


class CreateFactRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)
    category: str = Field(default="context")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    source_error: str = Field(default="")


class UpdateFactRequest(BaseModel):
    content: str | None = None
    category: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


@router.get("/")
async def get_memory(agent_id: str | None = None):
    engine = get_memory_engine(agent_id)
    data = engine.load_data()
    return ok({
        "memory": engine.load_memory(),
        "profile": engine.parse_profile(),
        "facts": [f.model_dump() for f in data.facts],
    })


@router.put("/")
async def update_memory(request: UpdateContentRequest, agent_id: str | None = None):
    engine = get_memory_engine(agent_id)
    engine.save_memory(request.content)
    return ok()


@router.get("/data")
async def get_memory_data(agent_id: str | None = None):
    engine = get_memory_engine(agent_id)
    data = engine.load_data()
    return ok(json_compat(data.model_dump()))


@router.get("/knowledge")
async def get_knowledge(agent_id: str | None = None):
    engine = get_memory_engine(agent_id)
    content = engine.load_knowledge()
    sections = engine.parse_knowledge()
    return ok({"content": content, "sections": sections})


@router.put("/knowledge")
async def update_knowledge(request: UpdateContentRequest, agent_id: str | None = None):
    engine = get_memory_engine(agent_id)
    engine.save_knowledge(request.content)
    return ok()


@router.get("/summary")
async def get_summary(agent_id: str | None = None):
    engine = get_memory_engine(agent_id)
    content = engine.load_summary()
    sections = engine.parse_summary()
    return ok({"content": content, "sections": sections})


@router.put("/summary")
async def update_summary(request: UpdateContentRequest, agent_id: str | None = None):
    engine = get_memory_engine(agent_id)
    engine.save_summary(request.content)
    return ok()


@router.post("/distill")
async def distill_conversation(request: DistillRequest, agent_id: str | None = None):
    engine = get_memory_engine(agent_id)
    result = await engine.distill_conversation(request.messages)
    if result:
        return ok({"summary": result, "changed": True})
    return ok({"changed": False})


@router.get("/facts")
async def get_facts(
    category: str | None = None,
    agent_id: str | None = None,
    conversation_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    engine = get_memory_engine(agent_id)
    facts = engine.get_facts(category)

    # 合并对话级facts
    if conversation_id:
        from app.engines.memory.memory_engine import get_conversation_store
        conv_store = get_conversation_store(agent_id, conversation_id)
        conv_data = conv_store.load_data()
        conv_facts = conv_data.facts or []
        if category:
            conv_facts = [f for f in conv_facts if f.category == category]
        facts.extend(conv_facts)
    else:
        # 无指定对话时，只合并有 facts 的对话（限制扫描量）
        conv_ids = engine.list_conversation_dailies()
        for cid in conv_ids[offset:offset + limit]:
            from app.engines.memory.memory_engine import get_conversation_store
            conv_store = get_conversation_store(agent_id, cid)
            conv_data = conv_store.load_data()
            conv_facts = conv_data.facts or []
            if category:
                conv_facts = [f for f in conv_facts if f.category == category]
            facts.extend(conv_facts)

    # 去重（按id）
    seen = set()
    unique_facts = []
    for f in facts:
        if f.id not in seen:
            seen.add(f.id)
            unique_facts.append(f)

    # 分页
    total = len(unique_facts)
    unique_facts = unique_facts[offset:offset + limit]

    return ok({"facts": [f.model_dump() for f in unique_facts], "total": total, "limit": limit, "offset": offset})


@router.post("/facts")
async def create_fact(request: CreateFactRequest, agent_id: str | None = None):
    if request.category not in FACT_CATEGORIES:
        raise BadRequestError(f"Invalid category. Must be one of: {FACT_CATEGORIES}", code="MEMORY_CATEGORY_INVALID")
    engine = get_memory_engine(agent_id)
    fact = FactItem(
        content=request.content,
        category=request.category,
        confidence=request.confidence,
        source_error=request.source_error,
        source="manual",
    )
    engine.add_fact(fact)
    return ok({"fact": fact.model_dump()})


@router.delete("/facts/{fact_id}")
async def delete_fact(fact_id: str, agent_id: str | None = None):
    engine = get_memory_engine(agent_id)
    if engine.remove_fact(fact_id):
        return ok()
    raise NotFoundError("Fact not found", code="MEMORY_FACT_NOT_FOUND")


@router.patch("/facts/{fact_id}")
async def update_fact(fact_id: str, request: UpdateFactRequest, agent_id: str | None = None):
    if request.category is not None and request.category not in FACT_CATEGORIES:
        raise BadRequestError(f"Invalid category. Must be one of: {FACT_CATEGORIES}", code="MEMORY_CATEGORY_INVALID")
    engine = get_memory_engine(agent_id)
    if engine.update_fact(fact_id, request.content, request.category, request.confidence):
        return ok()
    raise NotFoundError("Fact not found", code="MEMORY_FACT_NOT_FOUND")


@router.get("/daily")
async def get_daily(date: str | None = None, agent_id: str | None = None, conversation_id: str | None = None):
    engine = get_memory_engine(agent_id)
    return ok({"date": date or "today", "content": engine.load_daily(date, conversation_id)})


@router.post("/daily")
async def append_daily(request: AppendRequest, agent_id: str | None = None):
    engine = get_memory_engine(agent_id)
    engine.append_daily(request.content, request.date, conversation_id=request.conversation_id)
    return ok()


@router.get("/dailies")
async def list_dailies(agent_id: str | None = None, conversation_id: str | None = None):
    engine = get_memory_engine(agent_id)
    return ok({"dailies": engine.list_dailies(conversation_id)})


@router.get("/conversation-dailies")
async def list_conversation_dailies(
    agent_id: str | None = None,
    conversation_store=Depends(get_conversation_store),
):
    """列出所有有 daily 记录的 conversation_id 及其标题。"""
    engine = get_memory_engine(agent_id)
    conv_ids = engine.list_conversation_dailies()

    result = []
    for conv_id in conv_ids:
        conv = conversation_store.get(conv_id)
        title = conv.get("title", "New Conversation") if conv else "Unknown"
        result.append({"id": conv_id, "title": title})
    
    return ok({"conversations": result})


@router.get("/recent-facts")
async def get_recent_facts(agent_id: str | None = None, since: float = 30):
    """获取最近 N 秒内新增的事实（用于聊天中展示记忆提取结果）。"""
    from datetime import datetime, timezone, timedelta
    engine = get_memory_engine(agent_id)
    data = engine.load_data()
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=since)
    recent = []
    for f in data.facts:
        try:
            created = datetime.fromisoformat(f.created_at.replace("Z", "+00:00"))
            if created >= cutoff:
                recent.append(f.model_dump())
        except (ValueError, TypeError):
            pass
    return ok({"facts": recent})


@router.get("/inject")
async def get_injection_content(agent_id: str | None = None, conversation_id: str | None = None, query: str | None = None):
    engine = get_memory_engine(agent_id)
    content = engine.build_context(query=query or "", conversation_id=conversation_id)
    return ok({"content": content, "has_memory": bool(content.strip())})


@router.get("/profile")
async def get_profile(agent_id: str | None = None):
    engine = get_memory_engine(agent_id)
    return ok(engine.parse_profile())


@router.get("/debug/inject")
async def debug_inject(agent_id: str | None = None):
    engine = get_memory_engine(agent_id)
    ctx = engine.build_context()
    data = engine.load_data()
    return ok({
        "memory_file": str(engine._memory_file()),
        # 记忆已迁入 SQLite（memory_profiles/memory_facts 表）；文件路径仅作兼容展示
        "memory_exists": bool(data.profile.name or data.facts),
        "knowledge_exists": bool(engine.load_knowledge().strip()),
        "daily_count": len(engine.list_dailies()),
        "fact_count": len(data.facts),
        "context_length": len(ctx),
        "context_preview": ctx[:500] if ctx else "",
    })


@router.get("/health")
async def memory_health(agent_id: str | None = None):
    engine = get_memory_engine(agent_id)
    data = engine.load_data()
    return ok({
        "status": "ok" if data.profile.name else "warning",
        "profile": engine.parse_profile(),
        "fact_count": len(data.facts),
        # 记忆已迁入 SQLite 单库；字段语义改为"是否存在记忆数据"
        "memory_file_exists": bool(data.profile.name or data.facts),
        "knowledge_exists": bool(engine.load_knowledge().strip()),
        "daily_files": engine.list_dailies(),
    })


@router.get("/agents")
async def list_memory_agents(agents_store=Depends(get_agents_store)):
    """列出 owner 轨道（主人/各 Agent）中有记忆数据的条目（SQLite 行级统计）。"""
    from sqlalchemy import func, select

    from app.infrastructure.database.models.memory import MemoryFact, MemoryProfile
    from app.infrastructure.database.session import sync_session_factory

    result = []
    with sync_session_factory() as session:
        profile_rows = session.execute(
            select(MemoryProfile.owner_key, MemoryProfile.name).where(
                MemoryProfile.owner_key.like("owner:%")
            )
        ).all()
        fact_counts = dict(
            session.execute(
                select(MemoryFact.owner_key, func.count())
                .where(MemoryFact.owner_key.like("owner:%"))
                .group_by(MemoryFact.owner_key)
            ).all()
        )
    names = {owner_key: name for owner_key, name in profile_rows}
    owner_keys = sorted(set(names.keys()) | set(fact_counts.keys()))

    for owner_key in owner_keys:
        agent_id = owner_key[len("owner:"):]
        if agent_id == "_default":
            continue
        agent = await agents_store.get_async(agent_id)
        name = agent.get("name", agent_id) if agent else agent_id
        result.append({
            "id": agent_id,
            "name": name,
            "fact_count": fact_counts.get(owner_key, 0),
            "has_profile": bool(names.get(owner_key)),
            "profile_name": names.get(owner_key, ""),
        })

    return ok({"agents": result})


@router.get("/agents/{agent_id}/stats")
async def get_agent_memory_stats(agent_id: str):
    engine = get_memory_engine(agent_id)
    data = engine.load_data()
    return ok({
        "fact_count": len(data.facts),
        "has_profile": bool(data.profile.name),
        "has_knowledge": bool(engine.load_knowledge().strip()),
        "has_summary": any(s.summary for s in [
            data.summaries.user_profile, data.summaries.preferences,
            data.summaries.recent_state, data.summaries.timeline,
        ]),
        "daily_count": len(engine.list_dailies()),
    })


@router.delete("/agents/{agent_id}")
async def delete_agent_memory(agent_id: str):
    """删除指定 Agent 的全部记忆（SQLite 行 + 旧文件布局），含对话级数据与向量索引。"""
    from sqlalchemy import delete as sa_delete

    from app.infrastructure.database.models.memory import (
        MemoryDaily,
        MemoryFact,
        MemoryKnowledge,
        MemoryProfile,
        MemorySummary,
        MemoryVector,
    )
    from app.infrastructure.database.session import sync_session_factory

    owner_key = f"owner:{agent_id}"
    with sync_session_factory() as session:
        for table in (MemoryFact, MemorySummary, MemoryProfile, MemoryKnowledge, MemoryDaily, MemoryVector):
            session.execute(sa_delete(table).where(table.owner_key == owner_key))
        session.commit()
    # 清理旧文件布局（迁移前遗留，兼容保留）
    agent_dir = Path(settings.DATA_DIR) / "memory" / "agents" / agent_id
    if agent_dir.exists():
        shutil.rmtree(agent_dir)
    key = agent_id
    _engines.pop(key, None)
    return ok()


@router.delete("/facts")
async def clear_facts(agent_id: str | None = None):
    """清空所有事实"""
    engine = get_memory_engine(agent_id)
    engine.clear_facts()
    return ok()


@router.delete("/knowledge")
async def clear_knowledge(agent_id: str | None = None):
    """清空知识记忆"""
    engine = get_memory_engine(agent_id)
    engine.clear_knowledge()
    return ok()


@router.delete("/dailies")
async def clear_dailies(agent_id: str | None = None):
    """清空所有近期对话记录"""
    engine = get_memory_engine(agent_id)
    engine.clear_dailies()
    return ok()


@router.delete("/summary")
async def clear_summary(agent_id: str | None = None):
    """重置AI总结"""
    engine = get_memory_engine(agent_id)
    engine.clear_summaries()
    return ok()


@router.delete("/reset-all")
async def reset_all_memory(
    agent_id: str | None = None,
    conversation_store=Depends(get_conversation_store),
):
    """重置全部记忆到出厂状态（同时删除该 Agent 的所有对话记录）"""
    # 删除记忆数据
    engine = get_memory_engine(agent_id)
    engine.reset_all()
    
    # 删除该 Agent 的所有对话记录
    conversation_store.delete_by_agent_id(agent_id or "_default")
    
    # 清除缓存
    key = agent_id or "_default"
    _engines.pop(key, None)
    return ok()


def json_compat(obj):
    if isinstance(obj, dict):
        return {k: json_compat(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_compat(v) for v in obj]
    if isinstance(obj, float):
        return round(obj, 4)
    return obj
