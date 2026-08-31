"""平台会话映射 — 平台会话 (instance_id + session_id) → 主 Agent conversation。

持久化：会话映射存储在 config_items 表（通过 luominest_config_store，SQLite），
键命名空间 ``platform.sessions.*``，单键格式
``platform.sessions.<instance_id>:<session_id>``（每条会话映射一行）。

该映射属于用户绑定的会话状态：平台实例运行时并不持有它，无法从运行时状态
重建；丢失会导致该平台会话下一条消息被创建全新 conversation，对话上下文断裂
（用户可感知），因此迁入 config_items，参与 AES 加密与统一备份链路。
遗留 JSON 文件 platform_sessions.json 仅在首次迁移时幂等合并一次，不删除。
"""
import os
import uuid
from loguru import logger

from app.core.utils import utc_now
from app.core.domain_policy import MAIN_AGENT_ID, LEGACY_MAIN_AGENT_ID
from app.infrastructure.database.conversation_store import conversation_store
from app.infrastructure.database.config_store import luominest_config_store

# 主 Agent 唯一标识（canonical 在 app.core.domain_policy，此处兼容再导出）
# 注意：旧数据中 agent_id 为 "main"（LEGACY_MAIN_AGENT_ID），
# context_service.is_main_agent() 已做兼容

# config_items 键前缀（会话映射命名空间）
_SESSIONS_KEY_PREFIX = "platform.sessions."

# 遗留 JSON 文件（DATA_DIR/store/）—— 收敛后仅在迁移时读取一次，不再写入，也不删除文件本身
_LEGACY_JSON_FILENAME = "platform_sessions.json"
# _migration_meta 标记源名：与 json_to_sqlite_migrator 共用同一标记表，谁先执行谁标记，避免重复合并
_MIGRATION_SOURCE = "platform_sessions"
_legacy_merged = False


def _session_key(instance_id: str, session_id: str) -> str:
    return f"{instance_id}:{session_id}"


def _config_key(instance_id: str, session_id: str) -> str:
    """config_items 存储键：platform.sessions.<instance_id>:<session_id>。"""
    return f"{_SESSIONS_KEY_PREFIX}{_session_key(instance_id, session_id)}"


def _build_user_key(platform_name: str, session_id: str, is_group: bool) -> str:
    """构造 user_key（洋葱架构 §8.5）：私聊 {Platform}_{User_ID}，群聊为空。

    私聊时 session_id 即 User_ID（§8.1）；群聊成员记忆走消息级 sender_id，
    与 conversation 解耦，故群聊 user_key 留空。元数据不完整时留空，
    待远期账号绑定（Internal_User_ID）归一化。
    """
    if is_group:
        return ""
    if not platform_name or not session_id:
        return ""
    return f"{platform_name}_{session_id}"


def _merge_legacy_json() -> None:
    """幂等合并遗留 JSON 文件（platform_sessions.json）到 config_items。

    参照 json_to_sqlite_migrator 的 _migration_meta 标记模式：
    - 已标记迁移 → 直接跳过（重跑不重复合并）
    - JSON 文件不存在 → 仅记录标记
    - JSON 文件存在 → config_items 为权威源，遗留条目仅补缺（已存在的键不覆盖）
    遗留 JSON 文件是用户数据：仅迁移时读取，不删除文件本身。
    """
    global _legacy_merged
    if _legacy_merged:
        return

    try:
        from app.core.config import settings
        from app.infrastructure.database.migration.json_to_sqlite_migrator import (
            _is_migrated,
            _mark_migrated,
            _read_json_file,
        )

        if _is_migrated(_MIGRATION_SOURCE):
            _legacy_merged = True
            return

        path = os.path.join(settings.DATA_DIR, "store", _LEGACY_JSON_FILENAME)
        data = _read_json_file(path)
        count = 0
        if isinstance(data, dict):
            for key, value in data.items():
                if not isinstance(value, dict):
                    continue
                # 遗留 JsonStore 的键已是 instance_id:session_id 格式，直接加命名空间前缀
                config_key = f"{_SESSIONS_KEY_PREFIX}{key}"
                if luominest_config_store.get(config_key) is None:
                    luominest_config_store.set(config_key, value)
                    count += 1

        _mark_migrated(_MIGRATION_SOURCE, count)
        _legacy_merged = True
        if count:
            logger.info(
                f"[PlatformSession] Merged legacy JSON into config_items: "
                f"{count} session mapping(s)"
            )
    except Exception as e:
        logger.warning(f"[PlatformSession] Legacy JSON merge skipped: {e}")


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
    _merge_legacy_json()
    key = _config_key(instance_id, session_id)
    mapping = luominest_config_store.get(key, {})
    if not isinstance(mapping, dict):
        mapping = {}

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
        # 对话域（洋葱架构 §5/§8.1）：每个平台实例一域，决定列表隔离边界
        "domain": f"platform:{instance_id}",
        "scene": "platform",
        # user_key（§8.5）：私聊 {Platform}_{User_ID}，群聊为空
        "user_key": _build_user_key(platform_name, session_id, is_group),
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

    luominest_config_store.set(key, {
        "conversation_id": conv_id,
        "instance_id": instance_id,
        "session_id": session_id,
        "platform_name": platform_name,
        "sender_name": sender_name,
        "is_group": is_group,
        "created_at": now,
        "updated_at": now,
    })
    logger.info(f"[PlatformSession] Created conversation {conv_id} for {_session_key(instance_id, session_id)}")
    return conv_id


async def get_conversation_id(instance_id: str, session_id: str) -> str | None:
    """获取平台会话对应的 conversation_id（不创建）。"""
    _merge_legacy_json()
    mapping = luominest_config_store.get(_config_key(instance_id, session_id), {})
    if not isinstance(mapping, dict):
        return None
    return mapping.get("conversation_id")


def list_platform_sessions(instance_id: str | None = None) -> list[dict]:
    """列出平台会话映射。"""
    _merge_legacy_json()
    all_sessions = [
        v for v in luominest_config_store.get_namespace(_SESSIONS_KEY_PREFIX).values()
        if isinstance(v, dict)
    ]
    # 按创建时间排序，保证返回顺序稳定（SQLite 行序不确定）
    all_sessions.sort(key=lambda s: str(s.get("created_at", "")))
    if instance_id:
        return [s for s in all_sessions if s.get("instance_id") == instance_id]
    return all_sessions


async def create_new_conversation(instance_id: str, session_id: str) -> dict:
    """为指定的平台实例和会话创建全新的对话（/new 命令）。

    清除旧的会话映射，创建新的 conversation，返回新对话信息。
    """
    _merge_legacy_json()
    key = _config_key(instance_id, session_id)
    old_mapping = luominest_config_store.get(key, {})
    if not isinstance(old_mapping, dict):
        old_mapping = {}

    # 从旧映射中保留平台元信息
    platform_name = old_mapping.get("platform_name", "unknown")
    sender_name = old_mapping.get("sender_name", "")
    is_group = old_mapping.get("is_group", False)

    conv_id = f"plat-{uuid.uuid4().hex[:12]}"
    now = utc_now()
    title_prefix = "群聊" if is_group else "私聊"
    title = f"[{platform_name}] {title_prefix} {sender_name or session_id}"[:60]

    conv = {
        "id": conv_id,
        "title": title,
        "agent_id": MAIN_AGENT_ID,
        # 对话域（洋葱架构 §5/§8.1）：每个平台实例一域，决定列表隔离边界
        "domain": f"platform:{instance_id}",
        "scene": "platform",
        # user_key（§8.5）：私聊 {Platform}_{User_ID}，群聊为空
        "user_key": _build_user_key(platform_name, session_id, is_group),
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

    luominest_config_store.set(key, {
        "conversation_id": conv_id,
        "instance_id": instance_id,
        "session_id": session_id,
        "platform_name": platform_name,
        "sender_name": sender_name,
        "is_group": is_group,
        "created_at": now,
        "updated_at": now,
    })
    logger.info(f"[PlatformSession] Created new conversation {conv_id} for {_session_key(instance_id, session_id)} (replacing old mapping)")
    return {
        "id": conv_id,
        "title": title,
        "created_at": now,
    }


def remove_platform_session(instance_id: str, session_id: str) -> bool:
    """移除平台会话映射（不删除 conversation）。"""
    _merge_legacy_json()
    return luominest_config_store.delete(_config_key(instance_id, session_id))
