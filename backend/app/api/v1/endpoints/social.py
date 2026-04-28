import uuid
import json
from datetime import datetime, timezone
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from loguru import logger

from app.infrastructure.database.json_store import groups_store, agents_store
from app.domains.social.group_chat import GroupChatManager
from app.domains.social.ai_to_ai_chat import AIToAIChat
from app.domains.social.agent_orchestrator import agent_orchestrator
from app.domains.social.agent_role_registry import AgentRoleRegistry

router = APIRouter(prefix="/social", tags=["social"])

_group_manager = GroupChatManager()


class GroupCreate(BaseModel):
    name: str
    description: str = ""
    type: str = "mixed"


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class GroupMemberAdd(BaseModel):
    agent_id: str
    role: str = "成员"


class GroupMemberRemove(BaseModel):
    agent_id: str


class GroupMessageSend(BaseModel):
    content: str
    sender_id: str = "user"


class CollaborationRequest(BaseModel):
    content: str
    sender_id: str = "user"
    stream: bool = True


class AIChatRequest(BaseModel):
    agent_a_id: str
    agent_b_id: str
    topic: str
    rounds: int = 3


class RAGIndexRequest(BaseModel):
    content: str
    source: str
    metadata: dict | None = None


class RAGSearchRequest(BaseModel):
    query: str
    top_k: int = 5


@router.get("/groups")
async def list_groups():
    logger.info("[API] GET /social/groups - Listing groups")
    groups = groups_store.values()
    result = []
    for g in groups:
        members = g.get("members", [])
        ai_count = sum(1 for m in members if m.get("type") == "agent")
        messages = g.get("messages", [])
        last_msg = messages[-1]["content"][:50] if messages else None
        result.append({
            "id": g["id"],
            "name": g["name"],
            "description": g.get("description", ""),
            "type": g.get("type", "mixed"),
            "members": members,
            "member_count": len(members),
            "ai_count": ai_count,
            "last_message": last_msg,
            "created_at": g.get("created_at", ""),
            "updated_at": g.get("updated_at", ""),
        })
    return {"error": None, "data": result}


@router.post("/groups")
async def create_group(request: GroupCreate):
    logger.info(f"[API] POST /social/groups - Creating group: {request.name}")
    group_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    group = {
        "id": group_id,
        "name": request.name,
        "description": request.description,
        "type": request.type,
        "members": [],
        "messages": [],
        "created_at": now,
        "updated_at": now,
    }
    groups_store.set(group_id, group)
    return {"error": None, "data": group}


@router.get("/groups/{group_id}")
async def get_group(group_id: str):
    logger.info(f"[API] GET /social/groups/{group_id} - Fetching group")
    group = groups_store.get(group_id)
    if not group:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Group {group_id} not found")
    return {"error": None, "data": group}


@router.patch("/groups/{group_id}")
async def update_group(group_id: str, request: GroupUpdate):
    logger.info(f"[API] PATCH /social/groups/{group_id} - Updating group")
    group = groups_store.get(group_id)
    if not group:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Group {group_id} not found")
    update_data = request.model_dump(exclude_unset=True)
    group.update(update_data)
    group["updated_at"] = datetime.now(timezone.utc).isoformat()
    groups_store.set(group_id, group)
    return {"error": None, "data": group}


@router.delete("/groups/{group_id}")
async def delete_group(group_id: str):
    logger.info(f"[API] DELETE /social/groups/{group_id} - Deleting group")
    groups_store.delete(group_id)
    return {"error": None, "data": {"deleted": True}}


@router.post("/groups/{group_id}/members")
async def add_group_member(group_id: str, request: GroupMemberAdd):
    logger.info(f"[API] POST /social/groups/{group_id}/members - Adding member")
    group = groups_store.get(group_id)
    if not group:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Group {group_id} not found")

    agent = agents_store.get(request.agent_id)
    if not agent:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Agent {request.agent_id} not found")

    members = group.get("members", [])
    if any(m.get("agent_id") == request.agent_id for m in members):
        from app.core.exceptions import ValidationError
        raise ValidationError(f"Agent {request.agent_id} is already a member")

    members.append({
        "agent_id": request.agent_id,
        "name": agent["name"],
        "type": "agent",
        "role": request.role,
        "color": agent.get("color", "#0d9488"),
    })
    group["members"] = members
    group["updated_at"] = datetime.now(timezone.utc).isoformat()
    groups_store.set(group_id, group)
    return {"error": None, "data": group}


@router.delete("/groups/{group_id}/members/{agent_id}")
async def remove_group_member(group_id: str, agent_id: str):
    logger.info(f"[API] DELETE /social/groups/{group_id}/members/{agent_id} - Removing member")
    group = groups_store.get(group_id)
    if not group:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Group {group_id} not found")

    members = group.get("members", [])
    group["members"] = [m for m in members if m.get("agent_id") != agent_id]
    group["updated_at"] = datetime.now(timezone.utc).isoformat()
    groups_store.set(group_id, group)
    return {"error": None, "data": group}


@router.post("/groups/{group_id}/messages")
async def send_group_message(group_id: str, request: GroupMessageSend):
    logger.info(f"[API] POST /social/groups/{group_id}/messages - Sending message")
    group = groups_store.get(group_id)
    if not group:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Group {group_id} not found")

    results = await _group_manager.send_group_message(
        group_id=group_id,
        sender_id=request.sender_id,
        sender_type="user" if request.sender_id == "user" else "agent",
        content=request.content,
    )
    return {"error": None, "data": results}


@router.post("/groups/{group_id}/collaborate")
async def collaborate(group_id: str, request: CollaborationRequest):
    logger.info(f"[API] POST /social/groups/{group_id}/collaborate - Multi-agent collaboration")
    group = groups_store.get(group_id)
    if not group:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Group {group_id} not found")

    if request.stream:
        async def event_stream():
            async for event in agent_orchestrator.orchestrate_stream(
                group_id=group_id,
                user_message=request.content,
                sender_id=request.sender_id,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    session = await agent_orchestrator.orchestrate(
        group_id=group_id,
        user_message=request.content,
        sender_id=request.sender_id,
    )

    return {
        "error": None,
        "data": {
            "session_id": session.session_id,
            "phase": session.phase.value,
            "plan": session.plan,
            "sub_tasks": [
                {
                    "task_id": t.task_id,
                    "role_id": t.role_id,
                    "agent_id": t.agent_id,
                    "description": t.description,
                    "status": t.status.value,
                    "result": t.result,
                    "error": t.error,
                }
                for t in session.sub_tasks
            ],
            "final_result": session.final_result,
            "coordinator_response": session.coordinator_response,
        },
    }


@router.get("/agent-roles")
async def list_agent_roles():
    logger.info("[API] GET /social/agent-roles - Listing agent roles")
    roles = AgentRoleRegistry.list_roles()
    return {
        "error": None,
        "data": [
            {
                "role_id": r.role_id,
                "name": r.name,
                "description": r.description,
                "capabilities": r.capabilities,
                "execution_mode": r.execution_mode,
                "max_concurrent_tasks": r.max_concurrent_tasks,
                "timeout_seconds": r.timeout_seconds,
                "color": r.color,
            }
            for r in roles
        ],
    }


@router.post("/ai-chat")
async def ai_to_ai_chat(request: AIChatRequest):
    logger.info(f"[API] POST /social/ai-chat - AI to AI chat")
    results = await AIToAIChat.converse(
        agent_a_id=request.agent_a_id,
        agent_b_id=request.agent_b_id,
        topic=request.topic,
        rounds=request.rounds,
    )
    return {"error": None, "data": results}


@router.post("/rag/index")
async def index_rag_content(request: RAGIndexRequest):
    logger.info(f"[API] POST /social/rag/index - Indexing content")
    from app.engines.memory.rag.indexer import RAGIndexer
    indexer = RAGIndexer()
    count = await indexer.index_text(
        content=request.content,
        source=request.source,
        metadata=request.metadata,
    )
    return {"error": None, "data": {"indexed_chunks": count}}


@router.post("/rag/search")
async def search_rag(request: RAGSearchRequest):
    logger.info(f"[API] POST /social/rag/search - Searching: {request.query}")
    from app.engines.memory.rag.retriever import RAGRetriever
    retriever = RAGRetriever()
    results = await retriever.search(request.query, top_k=request.top_k)
    return {"error": None, "data": results}


@router.get("/agents")
async def list_available_agents():
    logger.info("[API] GET /social/agents - Listing available agents for social")
    agents = agents_store.values()
    return {"error": None, "data": list(agents)}
