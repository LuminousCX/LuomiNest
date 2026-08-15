"""对话域（domain/scene/user_key）存量回填迁移器（洋葱架构 §5.4 / §12.1）。

旧对话无对话域字段，按 §5.4 规则推导并回填：

    if conv.platform 存在（platform 会话映射元数据） → domain = platform:{instance_id}
    elif agent_id == MAIN_AGENT_ID                    → domain = workbench
    else                                              → domain = agent:{agent_id}（agent_id 缺失时兜底 workbench）

实现说明：
- conversations 表无 platform 列，平台会话的元数据权威源是 config_items 的
  ``platform.sessions.*`` 会话映射（runtime/platform/session.py 维护），
  迁移前先触发遗留 platform_sessions.json 的幂等合并，保证映射完整。
- user_key（§8.5）仅私聊可推导：{Platform}_{User_ID}（私聊时 session_id 即 User_ID，§8.1）；
  群聊留空（群内成员记忆走消息级 sender_id）。
- 幂等：_migration_meta 标记防重跑（非行数判断）；仅处理 domain 为空/NULL 的行。
- 审计日志：输出各域回填条数。

入口：``def migrate_conversation_domains() -> int``（注册于 json_to_sqlite_migrator._MIGRATION_SOURCES）。
"""
from loguru import logger
from sqlalchemy import or_, select

from app.infrastructure.database.models.conversation import Conversation
from app.infrastructure.database.session import sync_session_factory

# 与 services/context_service.py 保持一致（含旧数据 "main" 兼容）
MAIN_AGENT_ID = "luominest_main_agent"
_LEGACY_MAIN_AGENT_ID = "main"

# _migration_meta 标记源名（与 json_to_sqlite_migrator 共用标记表）
MIGRATION_SOURCE = "conversation_domain_backfill"

# 平台会话映射命名空间（runtime/platform/session.py 的 _SESSIONS_KEY_PREFIX）
_PLATFORM_SESSIONS_PREFIX = "platform.sessions."


def _load_platform_session_index() -> dict[str, dict]:
    """构建 conversation_id → 平台会话映射 的索引。

    映射来自 config_items 的 platform.sessions.*（含遗留 JSON 合并后的条目）。
    """
    from app.infrastructure.database.config_store import luominest_config_store

    index: dict[str, dict] = {}
    try:
        namespace = luominest_config_store.get_namespace(_PLATFORM_SESSIONS_PREFIX)
    except Exception as e:
        logger.warning(f"[Migration] conversation_domains: failed to load platform sessions: {e}")
        return index
    for value in namespace.values():
        if not isinstance(value, dict):
            continue
        conv_id = value.get("conversation_id")
        if conv_id and value.get("instance_id"):
            index[conv_id] = value
    return index


def _derive_user_key(mapping: dict) -> str:
    """按 §8.5 推导 user_key：私聊 {Platform}_{User_ID}，群聊为空。

    私聊时 session_id 即 User_ID（§8.1）；元数据不完整时留空，待远期账号绑定归一化。
    """
    if mapping.get("is_group"):
        return ""
    platform_name = str(mapping.get("platform_name") or "")
    session_id = str(mapping.get("session_id") or "")
    if not platform_name or not session_id:
        return ""
    return f"{platform_name}_{session_id}"


def migrate_conversation_domains() -> int:
    """存量会话回填 domain/scene/user_key（幂等）。返回回填条数。"""
    # 延迟导入，避免与 json_to_sqlite_migrator 的模块级循环依赖
    from app.infrastructure.database.migration.json_to_sqlite_migrator import (
        _is_migrated,
        _mark_migrated,
    )

    if _is_migrated(MIGRATION_SOURCE):
        logger.debug("[Migration] conversation_domains: already migrated, skipping")
        return 0

    # 前置：确保遗留 platform_sessions.json 已合并进 config_items（映射完整性的依赖）
    try:
        from app.runtime.platform.session import _merge_legacy_json
        _merge_legacy_json()
    except Exception as e:
        logger.warning(f"[Migration] conversation_domains: legacy platform sessions merge skipped: {e}")

    platform_index = _load_platform_session_index()

    stats = {"platform": 0, "workbench": 0, "agent": 0, "user_key_filled": 0}
    total = 0

    with sync_session_factory() as session:
        rows = session.execute(
            select(Conversation).where(
                or_(Conversation.domain.is_(None), Conversation.domain == "")
            )
        ).scalars().all()

        for obj in rows:
            mapping = platform_index.get(obj.id)
            if mapping is not None:
                # 规则 1（§5.4）：platform 会话映射存在 → platform:{instance_id}
                obj.domain = f"platform:{mapping.get('instance_id')}"
                obj.scene = "platform"
                user_key = _derive_user_key(mapping)
                if user_key:
                    obj.user_key = user_key
                    stats["user_key_filled"] += 1
                stats["platform"] += 1
            elif obj.agent_id in (MAIN_AGENT_ID, _LEGACY_MAIN_AGENT_ID):
                # 规则 2（§5.4）：主 Agent → workbench（"main" 为旧数据兼容，同 is_main_agent）
                obj.domain = "workbench"
                if not obj.scene:
                    obj.scene = "workbench"
                stats["workbench"] += 1
            elif obj.agent_id:
                # 规则 3（§5.4）：联系人 Agent → agent:{agent_id}
                obj.domain = f"agent:{obj.agent_id}"
                if not obj.scene:
                    obj.scene = "workbench"
                stats["agent"] += 1
            else:
                # agent_id 缺失的兜底：归入 workbench（避免产生无效域 agent:）
                obj.domain = "workbench"
                if not obj.scene:
                    obj.scene = "workbench"
                stats["workbench"] += 1
            total += 1

        session.commit()

    _mark_migrated(MIGRATION_SOURCE, total)
    logger.success(
        f"[Migration] conversation_domains: backfilled {total} conversations "
        f"(platform={stats['platform']}, workbench={stats['workbench']}, "
        f"agent={stats['agent']}, user_key_filled={stats['user_key_filled']})"
    )
    return total
