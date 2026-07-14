import uuid
from fastapi import APIRouter
from pydantic import BaseModel, Field
from loguru import logger

from app.core.utils import utc_now, sse_response, sse_data, require_store, to_camel_case, ok
from app.core.exceptions import ValidationError
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





@router.get("/groups")
async def list_groups():
    logger.info("[API] GET /social/groups - Listing groups")
    groups = await groups_store.values_async()
    result = []
    for g in groups:
        members = g.get("members", [])
        ai_count = sum(1 for m in members if m.get("type") == "agent")
        messages = g.get("messages", [])
        last_msg = messages[-1]["content"][:50] if messages else None
        result.append(to_camel_case({
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
        }))
    return ok(result)


@router.post("/groups")
async def create_group(request: GroupCreate):
    logger.info(f"[API] POST /social/groups - Creating group: {request.name}")
    group_id = str(uuid.uuid4())
    now = utc_now()
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
    await groups_store.set_async(group_id, group)
    return ok(to_camel_case(group))
    

@router.get("/groups/{group_id}")
async def get_group(group_id: str):
    logger.info(f"[API] GET /social/groups/{group_id} - Fetching group")
    group = await require_store(groups_store, group_id, "Group")

    group_data = to_camel_case(dict(group))
    return ok(group_data)


@router.patch("/groups/{group_id}")
async def update_group(group_id: str, request: GroupUpdate):
    logger.info(f"[API] PATCH /social/groups/{group_id} - Updating group")
    group = await require_store(groups_store, group_id, "Group")
    update_data = request.model_dump(exclude_unset=True)
    group.update(update_data)
    group["updated_at"] = utc_now()
    await groups_store.set_async(group_id, group)
    return ok(to_camel_case(group))
    

@router.delete("/groups/{group_id}")
async def delete_group(group_id: str):
    logger.info(f"[API] DELETE /social/groups/{group_id} - Deleting group")
    await groups_store.delete_async(group_id)
    return ok({"deleted": True})


@router.post("/groups/{group_id}/members")
async def add_group_member(group_id: str, request: GroupMemberAdd):
    logger.info(f"[API] POST /social/groups/{group_id}/members - Adding member")
    group = await require_store(groups_store, group_id, "Group")

    agent = await require_store(agents_store, request.agent_id, "Agent")

    members = group.get("members", [])
    if any(m.get("agent_id") == request.agent_id for m in members):
        raise ValidationError(f"Agent {request.agent_id} is already a member")

    members.append({
        "agent_id": request.agent_id,
        "name": agent["name"],
        "type": "agent",
        "role": request.role,
        "color": agent.get("color", "#0d9488"),
    })
    group["members"] = members
    group["updated_at"] = utc_now()
    await groups_store.set_async(group_id, group)
    return ok(to_camel_case(group))
    

@router.delete("/groups/{group_id}/members/{agent_id}")
async def remove_group_member(group_id: str, agent_id: str):
    logger.info(f"[API] DELETE /social/groups/{group_id}/members/{agent_id} - Removing member")
    group = await require_store(groups_store, group_id, "Group")

    members = group.get("members", [])
    group["members"] = [m for m in members if m.get("agent_id") != agent_id]
    group["updated_at"] = utc_now()
    await groups_store.set_async(group_id, group)
    return ok(to_camel_case(group))
    

@router.post("/groups/{group_id}/messages")
async def send_group_message(group_id: str, request: GroupMessageSend):
    logger.info(f"[API] POST /social/groups/{group_id}/messages - Sending message (stream)")
    group = await require_store(groups_store, group_id, "Group")

    if request.sender_id != "user":
        members = group.get("members", [])
        is_member = any(
            m.get("agent_id") == request.sender_id or m.get("id") == request.sender_id
            for m in members
        )
        if not is_member:
            raise ValidationError(f"Sender {request.sender_id} is not a member of group {group_id}")

    if not request.content or not request.content.strip():
        raise ValidationError("Message content cannot be empty")

    async def message_stream():
        async for event in _group_manager.send_group_message_stream(
            group_id=group_id,
            sender_id=request.sender_id,
            sender_type="user" if request.sender_id == "user" else "agent",
            content=request.content,
        ):
            yield sse_data(event)

    return sse_response(
        message_stream(),
    )


@router.post("/groups/{group_id}/collaborate")
async def collaborate(group_id: str, request: CollaborationRequest):
    logger.info(f"[API] POST /social/groups/{group_id}/collaborate - Multi-agent collaboration")
    group = await require_store(groups_store, group_id, "Group")

    if request.stream:
        async def event_stream():
            async for event in agent_orchestrator.orchestrate_stream(
                group_id=group_id,
                user_message=request.content,
                sender_id=request.sender_id,
            ):
                yield sse_data(event)

        return sse_response(
            event_stream(),
        )

    session = await agent_orchestrator.orchestrate(
        group_id=group_id,
        user_message=request.content,
        sender_id=request.sender_id,
    )

    return {
        "error": None,
        "data": to_camel_case({
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
        }),
    }


@router.get("/agent-roles")
async def list_agent_roles():
    logger.info("[API] GET /social/agent-roles - Listing agent roles")
    roles = AgentRoleRegistry.list_worker_roles()
    return {
        "error": None,
        "data": [
            to_camel_case({
                "role_id": r.role_id,
                "name": r.name,
                "description": r.description,
                "capabilities": r.capabilities,
                "execution_mode": r.execution_mode,
                "max_concurrent_tasks": r.max_concurrent_tasks,
                "timeout_seconds": r.timeout_seconds,
                "color": r.color,
            })
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
    return ok(results)





@router.get("/agents")
async def list_available_agents():
    logger.info("[API] GET /social/agents - Listing available agents for social")
    agents = await agents_store.values_async()
    safe_agents = []
    for a in agents:
        safe_agents.append({
            "id": a.get("id", ""),
            "name": a.get("name", ""),
            "description": a.get("description", ""),
            "color": a.get("color", "#0d9488"),
            "avatar": a.get("avatar"),
            "is_main": a.get("is_main", False),
        })
    return ok(safe_agents)
