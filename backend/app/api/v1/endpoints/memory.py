import asyncio

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.exceptions import BadRequestError, NotFoundError
from app.core.config import settings
from app.core.utils import ok
from app.core.domain_policy import MAIN_AGENT_ID
from app.engines.memory import get_memory_engine
from app.engines.memory.memory_engine import FactItem, FACT_CATEGORIES, remove_engine
from app.engines.memory.store import OWNER_PREFIX
from app.api.v1.deps import get_agents_store, get_conversation_store

router = APIRouter(prefix="/memory", tags=["Memory"])


class AppendRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    date: str | None = None
    conversation_id: str | None = None


class UpdateContentRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)  # 与 AppendRequest 上限一致（审计 B4-4）


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
async def get_memory(agent_id: str | None = None, track: str = "owner", user_key: str = ""):
    engine = _resolve_engine(agent_id, track, user_key)
    data = engine.load_data()
    return ok({
        "memory": engine.load_memory(),
        "profile": engine.parse_profile(),
        "facts": [f.model_dump() for f in data.facts],
    })


@router.get("/knowledge")
async def get_knowledge(agent_id: str | None = None, track: str = "owner", user_key: str = ""):
    engine = _resolve_engine(agent_id, track, user_key)
    content = engine.load_knowledge()
    sections = engine.parse_knowledge()
    return ok({"content": content, "sections": sections})


@router.put("/knowledge")
async def update_knowledge(request: UpdateContentRequest, agent_id: str | None = None):
    engine = get_memory_engine(agent_id)
    engine.save_knowledge(request.content)
    return ok()


@router.get("/summary")
async def get_summary(agent_id: str | None = None, track: str = "owner", user_key: str = ""):
    engine = _resolve_engine(agent_id, track, user_key)
    content = engine.load_summary()
    sections = engine.parse_summary()
    return ok({"content": content, "sections": sections})


@router.put("/summary")
async def update_summary(request: UpdateContentRequest, agent_id: str | None = None):
    engine = get_memory_engine(agent_id)
    engine.save_summary(request.content)
    return ok()


@router.get("/facts")
async def get_facts(
    category: str | None = None,
    agent_id: str | None = None,
    track: str = "owner",
    user_key: str = "",
    conversation_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    engine = _resolve_engine(agent_id, track, user_key)
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
    # 引擎写锁：与蒸馏/画像更新的读-改-写序列互斥，避免并发覆盖
    async with engine.write_lock:
        await engine.remember_fact(fact)
    return ok({"fact": fact.model_dump()})


@router.delete("/facts/{fact_id}")
async def delete_fact(fact_id: str, agent_id: str | None = None):
    engine = get_memory_engine(agent_id)
    async with engine.write_lock:
        removed = await asyncio.to_thread(engine.remove_fact, fact_id)
        if removed:
            await engine.forget_fact_vector(fact_id)
    if removed:
        return ok()
    raise NotFoundError("Fact not found", code="MEMORY_FACT_NOT_FOUND")


@router.patch("/facts/{fact_id}")
async def update_fact(fact_id: str, request: UpdateFactRequest, agent_id: str | None = None):
    if request.category is not None and request.category not in FACT_CATEGORIES:
        raise BadRequestError(f"Invalid category. Must be one of: {FACT_CATEGORIES}", code="MEMORY_CATEGORY_INVALID")
    engine = get_memory_engine(agent_id)
    async with engine.write_lock:
        updated = await asyncio.to_thread(
            engine.update_fact, fact_id, request.content, request.category, request.confidence
        )
        if updated:
            data = await asyncio.to_thread(engine.load_data)
            fact = next((f for f in data.facts if f.id == fact_id), None)
            if fact is not None:
                await engine.sync_fact_vector(fact)
    if updated:
        return ok()
    raise NotFoundError("Fact not found", code="MEMORY_FACT_NOT_FOUND")


class FactPinRequest(BaseModel):
    pinned: bool


@router.post("/facts/{fact_id}/pin")
async def set_fact_pin(fact_id: str, request: FactPinRequest, agent_id: str | None = None):
    """置顶/取消置顶一条记忆事实（陪伴场景关键信息必注入）。"""
    engine = get_memory_engine(agent_id)
    async with engine.write_lock:
        changed = await asyncio.to_thread(engine.set_fact_pinned, fact_id, request.pinned)
    if not changed:
        raise NotFoundError("Fact not found", code="MEMORY_FACT_NOT_FOUND")
    return ok({"fact_id": fact_id, "pinned": request.pinned})


def _resolve_engine(agent_id: str | None, track: str = "owner", user_key: str = ""):
    """按轨道解析记忆引擎：owner=主轨（默认），users=用户轨（需 user_key）。"""
    if track == "users":
        if not user_key:
            raise BadRequestError("user_key is required for users track", code="MEMORY_USER_KEY_REQUIRED")
        from app.engines.memory.memory_engine import get_track_engine, TRACK_USERS

        return get_track_engine(TRACK_USERS, user_key)
    return get_memory_engine(agent_id)


@router.get("/tracks")
async def list_memory_tracks():
    """列出可用的记忆轨道：主 Agent/子 Agent 轨 + 用户轨（users/{key}）。"""
    from app.engines.memory.store import agents_root, sanitize_track_key

    agents: list[dict] = []
    agents_dir = agents_root()
    if agents_dir.exists():
        for d in sorted(agents_dir.iterdir()):
            if d.is_dir():
                agents.append({"track": "owner", "key": d.name})

    user_keys: list[str] = []
    users_dir = agents_dir.parent / "users"
    if users_dir.exists():
        for d in sorted(users_dir.iterdir()):
            if d.is_dir():
                try:
                    user_keys.append(sanitize_track_key(d.name))
                except ValueError:
                    continue  # 畸形目录名跳过，不让单个坏目录打挂整个列表

    return ok({"agents": agents, "user_keys": user_keys})


@router.get("/daily")
async def get_daily(date: str | None = None, agent_id: str | None = None, track: str = "owner", user_key: str = "", conversation_id: str | None = None):
    engine = _resolve_engine(agent_id, track, user_key)
    return ok({"date": date or "today", "content": engine.load_daily(date, conversation_id)})


@router.post("/daily")
async def append_daily(request: AppendRequest, agent_id: str | None = None):
    engine = get_memory_engine(agent_id)
    engine.append_daily(request.content, request.date, conversation_id=request.conversation_id)
    return ok()


@router.get("/dailies")
async def list_dailies(agent_id: str | None = None, track: str = "owner", user_key: str = "", conversation_id: str | None = None):
    engine = _resolve_engine(agent_id, track, user_key)
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
                MemoryProfile.owner_key.like(f"{OWNER_PREFIX}%")
            )
        ).all()
        fact_counts = dict(
            session.execute(
                select(MemoryFact.owner_key, func.count())
                .where(MemoryFact.owner_key.like(f"{OWNER_PREFIX}%"))
                .group_by(MemoryFact.owner_key)
            ).all()
        )
    names = {owner_key: name for owner_key, name in profile_rows}
    owner_keys = sorted(set(names.keys()) | set(fact_counts.keys()))

    for owner_key in owner_keys:
        agent_id = owner_key[len(OWNER_PREFIX):]
        # 主工作台与迁移遗留占位符排除（前端已固定置顶「主工作台」项）
        if agent_id in ("_default", "main", MAIN_AGENT_ID):
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


@router.delete("/facts")
async def clear_facts(agent_id: str | None = None):
    """清空所有事实"""
    engine = get_memory_engine(agent_id)
    async with engine.write_lock:
        await asyncio.to_thread(engine.clear_facts)
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
    remove_engine(agent_id)
    return ok()


# ─── 晨间简报 / 主动关心（记忆的消费形态，陪伴定位） ─────────────


@router.get("/briefing")
async def get_morning_briefing(agent_id: str | None = None):
    """当日晨间简报：懒生成 + 当日缓存（每日记忆 + 置顶/高置信事实 + 待办任务）。"""
    from app.services.proactive_service import proactive_care_service

    if not settings.PROACTIVE_CARE_ENABLED:
        return ok({"date": "", "content": "", "enabled": False})
    payload = await proactive_care_service.get_briefing(agent_id)
    return ok({**payload, "enabled": True})


@router.post("/briefing/refresh")
async def refresh_morning_briefing(agent_id: str | None = None):
    """强制重新生成当日简报。"""
    from app.services.proactive_service import proactive_care_service

    if not settings.PROACTIVE_CARE_ENABLED:
        return ok({"date": "", "content": "", "enabled": False})
    payload = await proactive_care_service.refresh_briefing(agent_id)
    return ok({**payload, "enabled": True})
