import uuid
from loguru import logger

from app.core.utils import utc_now
from app.infrastructure.database.conversation_store import conversation_store
from app.infrastructure.database.json_store import JsonStore

MAIN_AGENT_ID = "main"

_platform_sessions_store = JsonStore("platform_sessions.json")


def _session_key(instance_id: str, session_id: str) -> str:
    return f"{instance_id}:{session_id}"


async def get_or_create_conversation(
    instance_id: str,
    session_id: str,
    platform_name: str,
    sender_name: str = "",
    is_group: bool = False,
) -> str:
    """获取或创建平台会话对应的 conversation_id。

    每个平台实例 + 平台会话标识（user_id 或 group_id）映射到主 Agent 的一个独立 conversation。
    所有平台会话共享主 Agent 的记忆（agent_id=MAIN_AGENT_ID）。
    """
    key = _session_key(instance_id, session_id)
    mapping = _platform_sessions_store.get(key, {})

    conv_id = mapping.get("conversation_id")
    if conv_id:
        conv = await conversation_store.get_async(conv_id)
        if conv:
            return conv_id

    conv_id = f"plat-{uuid.uuid4().hex[:12]}"
    now = utc_now()
    title_prefix = "群聊" if is_group else "私聊"
    title = f"[{platform_name}] {title_prefix} {sender_name or session_id}"[:60]

    conv = {
        "id": conv_id,
        "title": title,
        "agent_id": MAIN_AGENT_ID,
        "messages": [],
        "created_at": now,
        "updated_at": now,
        "platform": {
            "instance_id": instance_id,
            "session_id": session_id,
            "platform_name": platform_name,
            "sender_name": sender_name,
            "is_group": is_group,
        },
    }
    await conversation_store.set_async(conv_id, conv)

    _platform_sessions_store.set(key, {
        "conversation_id": conv_id,
        "instance_id": instance_id,
        "session_id": session_id,
        "platform_name": platform_name,
        "sender_name": sender_name,
        "is_group": is_group,
        "created_at": now,
        "updated_at": now,
    })
    logger.info(f"[PlatformSession] Created conversation {conv_id} for {key}")
    return conv_id


async def get_conversation_id(instance_id: str, session_id: str) -> str | None:
    """获取平台会话对应的 conversation_id（不创建）。"""
    key = _session_key(instance_id, session_id)
    mapping = _platform_sessions_store.get(key, {})
    return mapping.get("conversation_id")


def list_platform_sessions(instance_id: str | None = None) -> list[dict]:
    """列出平台会话映射。"""
    all_sessions = _platform_sessions_store.values()
    if instance_id:
        return [s for s in all_sessions if s.get("instance_id") == instance_id]
    return all_sessions


def remove_platform_session(instance_id: str, session_id: str) -> bool:
    """移除平台会话映射（不删除 conversation）。"""
    key = _session_key(instance_id, session_id)
    if _platform_sessions_store.get(key):
        _platform_sessions_store.delete(key)
        return True
    return False
