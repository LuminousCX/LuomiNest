"""JSON → SQLite 幂等迁移器。

设计要点：
- 用 `_migration_meta` 表标记每个数据源是否已迁移（**非行数判断**，空库也可能已迁移）
- 每个数据源独立 try/except，失败不阻塞其他
- 旧文件不删除（用户可手动清理），仅标记已迁移
- 迁移范围：data/store/*.json、data/config/user_config.json、data/conversations/*.json、
  data/model_config.json、data/main_agent.json

入口：`async def migrate_all_json_to_sqlite() -> dict[str, int]`
返回 `{source_name: migrated_count}`，-1 表示失败。
"""
import asyncio
import json
import os
from typing import Callable

from loguru import logger

from app.core.utils import utc_now
from app.core.constants.colors import DEFAULT_AGENT_COLOR

from app.core.config import settings
from app.infrastructure.database.facades.json_store_facade import (
    agents_store,
    groups_store,
    platforms_store,
    repo_sources_store,
)
from app.infrastructure.database.facades.marketplace_stats_store import marketplace_stats_store
from app.infrastructure.database.config_store import luominest_config_store
from app.infrastructure.database.usage_store import usage_store
from app.infrastructure.database.conversation_store import conversation_store
from app.infrastructure.database.facades.main_agent_config import save_luominest_main_agent_config
from app.infrastructure.database.migration.conversation_domain_migrator import (
    migrate_conversation_domains,
)
from app.infrastructure.database.models.migration_meta import MigrationMeta
from app.infrastructure.database.repositories.usage_repository import UsageRepository
from app.infrastructure.database.session import sync_session_factory


# ──────────────────────────────────────────────────────────────────
# _migration_meta 标记表辅助函数
# ──────────────────────────────────────────────────────────────────

def _is_migrated(source: str) -> bool:
    """检查数据源是否已迁移。"""
    with sync_session_factory() as session:
        return session.get(MigrationMeta, source) is not None


def _mark_migrated(source: str, record_count: int) -> None:
    """标记数据源为已迁移。"""
    now = utc_now()
    with sync_session_factory() as session:
        meta = session.get(MigrationMeta, source)
        if meta is None:
            session.add(MigrationMeta(source=source, migrated_at=now, record_count=record_count))
        else:
            meta.migrated_at = now
            meta.record_count = record_count
        session.commit()


def _read_json_file(path: str):
    """安全读取 JSON 文件，失败返回 None。"""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"[Migration] Failed to read {path}: {e}")
        return None


# ──────────────────────────────────────────────────────────────────
# 通用 JsonStore 格式迁移（dict[pk, value]）
# ──────────────────────────────────────────────────────────────────

def _migrate_json_store_source(source: str, filename: str, store) -> int:
    """迁移 data/store/{filename} 格式的 JsonStore 数据。

    格式：{key: value_dict, ...}
    """
    if _is_migrated(source):
        logger.debug(f"[Migration] {source} already migrated, skipping")
        return 0

    path = os.path.join(settings.DATA_DIR, "store", filename)
    data = _read_json_file(path)
    if data is None:
        _mark_migrated(source, 0)
        logger.info(f"[Migration] {source}: no JSON file found, marked as migrated (0 records)")
        return 0

    count = 0
    for key, value in data.items():
        if not isinstance(value, dict):
            continue
        store.set(key, value)
        count += 1

    _mark_migrated(source, count)
    logger.success(f"[Migration] {source}: migrated {count} records")
    return count


# ──────────────────────────────────────────────────────────────────
# 各数据源迁移函数
# ──────────────────────────────────────────────────────────────────

def _migrate_agents() -> int:
    return _migrate_json_store_source("agents", "agents.json", agents_store)


def _migrate_groups() -> int:
    return _migrate_json_store_source("groups", "groups.json", groups_store)


def _migrate_platforms() -> int:
    return _migrate_json_store_source("platforms", "platforms.json", platforms_store)


def _migrate_repo_sources() -> int:
    return _migrate_json_store_source("repo_sources", "repo_sources.json", repo_sources_store)


def _migrate_marketplace_stats() -> int:
    """迁移 marketplace_stats.json。

    旧格式与 ORM 模型字段名不同，需转换：
    - downloadCount → download_count
    - likeCount → like_count
    - __likes__.liked_ids → liked_by
    - 跳过 __user_likes__（全局用户喜欢列表，非 per-item 统计）
    """
    if _is_migrated("marketplace_stats"):
        return 0

    path = os.path.join(settings.DATA_DIR, "store", "marketplace_stats.json")
    data = _read_json_file(path)
    if data is None:
        _mark_migrated("marketplace_stats", 0)
        return 0

    count = 0
    for item_id, stat in data.items():
        # 跳过全局用户喜欢列表（非 per-item 统计）
        if item_id == "__user_likes__":
            continue
        if not isinstance(stat, dict):
            continue

        likes_meta = stat.get("__likes__", {})
        liked_by = likes_meta.get("liked_ids", []) if isinstance(likes_meta, dict) else []

        transformed = {
            "item_id": item_id,
            "type": stat.get("type", ""),
            "download_count": stat.get("downloadCount", 0),
            "like_count": stat.get("likeCount", 0),
            "liked_by": liked_by,
        }
        marketplace_stats_store.set(item_id, transformed)
        count += 1

    _mark_migrated("marketplace_stats", count)
    logger.success(f"[Migration] marketplace_stats: migrated {count} records")
    return count


def _migrate_usage_records() -> int:
    """迁移 usage_records.json（JSON 数组格式，非 JsonStore dict）。"""
    if _is_migrated("usage_records"):
        return 0

    path = os.path.join(settings.DATA_DIR, "store", "usage_records.json")
    data = _read_json_file(path)
    if data is None:
        _mark_migrated("usage_records", 0)
        return 0

    # 旧格式为 JSON 数组 [{...}, ...]
    if not isinstance(data, list):
        logger.warning(f"[Migration] usage_records: expected list, got {type(data).__name__}")
        _mark_migrated("usage_records", 0)
        return 0

    repo = UsageRepository()
    count = repo.bulk_import(data)
    _mark_migrated("usage_records", count)
    logger.success(f"[Migration] usage_records: migrated {count} records")
    return count


def _migrate_user_config() -> int:
    """迁移 user_config.json（flat KV dict，跳过 __updated_at 元数据键）。"""
    if _is_migrated("user_config"):
        return 0

    path = os.path.join(settings.DATA_DIR, "config", "user_config.json")
    data = _read_json_file(path)
    if data is None:
        _mark_migrated("user_config", 0)
        return 0

    count = 0
    for key, value in data.items():
        # 跳过 __updated_at 元数据键（时间戳，非配置数据）
        if key.endswith("__updated_at"):
            continue
        luominest_config_store.set(key, value)
        count += 1

    _mark_migrated("user_config", count)
    logger.success(f"[Migration] user_config: migrated {count} keys")
    return count


def _migrate_main_agent() -> int:
    """迁移 main_agent.json → config_items['main_agent.config']。"""
    if _is_migrated("main_agent"):
        return 0

    path = os.path.join(settings.DATA_DIR, "main_agent.json")
    data = _read_json_file(path)
    if data is None:
        _mark_migrated("main_agent", 0)
        return 0

    if not isinstance(data, dict):
        _mark_migrated("main_agent", 0)
        return 0

    save_luominest_main_agent_config(data)
    _mark_migrated("main_agent", 1)
    logger.success(f"[Migration] main_agent: migrated config")
    return 1


def _migrate_model_config() -> int:
    """迁移 model_config.json → config_items['model_config']。

    存为单个 JSON 值（与 main_agent.config 同模式），供 Phase 6 apply_model_config_from_db() 读取。
    """
    if _is_migrated("model_config"):
        return 0

    path = os.path.join(settings.DATA_DIR, "model_config.json")
    data = _read_json_file(path)
    if data is None:
        _mark_migrated("model_config", 0)
        return 0

    if not isinstance(data, dict):
        _mark_migrated("model_config", 0)
        return 0

    luominest_config_store.set("model_config", data)
    _mark_migrated("model_config", 1)
    logger.success(f"[Migration] model_config: migrated config")
    return 1


def _migrate_conversations() -> int:
    """迁移对话数据。

    处理两种旧格式：
    1. store/conversations.json — 合并 dict {conv_id: full_conv}
    2. conversations/{conv_id}.json + _index.json — per-file 格式

    两者可能同时存在，migrate_from_json_store 幂等（已存在则跳过）。
    """
    if _is_migrated("conversations"):
        return 0

    # 收集所有对话数据（合并两种来源）
    all_convs: dict[str, dict] = {}

    # 来源 1：store/conversations.json（合并 dict）
    merged_path = os.path.join(settings.DATA_DIR, "store", "conversations.json")
    merged_data = _read_json_file(merged_path)
    if isinstance(merged_data, dict):
        for conv_id, conv in merged_data.items():
            if isinstance(conv, dict) and conv_id != "__user_likes__":
                all_convs[conv_id] = conv

    # 来源 2：conversations/{conv_id}.json（per-file）
    conv_dir = os.path.join(settings.DATA_DIR, "conversations")
    if os.path.isdir(conv_dir):
        for filename in os.listdir(conv_dir):
            if not filename.endswith(".json") or filename == "_index.json":
                continue
            conv_path = os.path.join(conv_dir, filename)
            conv_data = _read_json_file(conv_path)
            if isinstance(conv_data, dict) and "id" in conv_data:
                conv_id = conv_data["id"]
                # per-file 格式优先（含完整 messages），不覆盖已有
                if conv_id not in all_convs:
                    all_convs[conv_id] = conv_data

    if not all_convs:
        _mark_migrated("conversations", 0)
        logger.info("[Migration] conversations: no data found, marked as migrated (0 records)")
        return 0

    # 用 ConversationFacade.migrate_from_json_store 的幂等逻辑逐条写入
    count = 0
    for conv_id, conv in all_convs.items():
        # 幂等：已存在则跳过
        if conversation_store.get(conv_id) is not None:
            continue
        conversation_store.set(conv_id, conv)
        count += 1

    _mark_migrated("conversations", count)
    logger.success(f"[Migration] conversations: migrated {count} records (of {len(all_convs)} total)")
    return count


def _migrate_providers_from_config_items() -> int:
    """迁移 config_items 中 llm.providers.* 旧格式数据到 providers + provider_credentials 表。

    旧系统将每个 provider 的每个字段存为独立的 config_item（如 llm.providers.ollama.name），
    新系统使用 providers 表和 provider_credentials 表（凭证加密存储）。

    幂等设计：
    - 已存在于 providers 表的 provider 跳过（不覆盖）
    - 已存在于 provider_credentials 的凭证跳过
    - 使用独立迁移 key providers_from_config_items（与旧的 providers_config 无关）
    """
    if _is_migrated("providers_from_config_items"):
        return 0

    from sqlalchemy import select as sa_select
    from app.infrastructure.database.models.config_item import ConfigItem
    from app.infrastructure.database.models.provider import Provider
    from app.infrastructure.database.models.provider_credential import ProviderCredential
    from app.security.crypto.aes_cipher import get_cipher
    import hashlib
    import uuid

    # 1. 读取所有 llm.providers.* config_items
    with sync_session_factory() as session:
        items = session.execute(
            sa_select(ConfigItem).where(ConfigItem.key.like("llm.providers.%"))
        ).scalars().all()

        if not items:
            _mark_migrated("providers_from_config_items", 0)
            logger.info("[Migration] providers_from_config_items: no legacy entries found")
            return 0

    # 2. 按 provider_id 分组
    provider_data: dict[str, dict[str, str]] = {}
    for item in items:
        # key 格式: llm.providers.{provider_id}.{field}
        parts = item.key.split(".", 3)  # ['llm', 'providers', '{id}', '{field}']
        if len(parts) != 4:
            continue
        provider_id = parts[2]
        field = parts[3]
        if provider_id not in provider_data:
            provider_data[provider_id] = {}
        # 反序列化值（config_items 存的是 JSON 编码的字符串）
        try:
            value = json.loads(item.value) if item.value else ""
        except (json.JSONDecodeError, TypeError):
            value = item.value or ""
        provider_data[provider_id][field] = value

    # 3. 逐个 provider 写入 providers 表 + provider_credentials 表
    count = 0
    cipher = get_cipher()

    for provider_id, fields in provider_data.items():
        name = fields.get("name", provider_id)
        vendor = fields.get("vendor", "openai_compatible")
        base_url = fields.get("base_url", "")
        default_model = fields.get("default_model", "")
        is_default_raw = fields.get("is_default", False)
        is_default = is_default_raw is True or (isinstance(is_default_raw, str) and is_default_raw.lower() == "true")
        description = fields.get("description", "")
        api_key_encrypted = fields.get("api_key", "")  # 已加密的 api_key

        with sync_session_factory() as session:
            # 检查 providers 表是否已有该 provider
            existing = session.get(Provider, provider_id)
            if existing is None:
                now = utc_now()
                provider = Provider(
                    id=provider_id,
                    name=name,
                    vendor=vendor,
                    base_url=base_url,
                    default_model=default_model,
                    is_default=is_default,
                    selected_models=[],
                    enabled=True,
                    sort_order=count,
                    created_at=now,
                    updated_at=now,
                )
                session.add(provider)
                logger.info(f"[Migration] Created provider: {provider_id} ({name})")
            else:
                logger.debug(f"[Migration] Provider {provider_id} already exists, skipping")

            # 迁移 api_key 到 provider_credentials
            if api_key_encrypted and len(api_key_encrypted) > 10:
                # 检查是否已有凭证
                existing_cred = session.execute(
                    sa_select(ProviderCredential).where(
                        ProviderCredential.provider_id == provider_id,
                        ProviderCredential.is_active == True,  # noqa: E712
                    )
                ).scalars().first()

                if existing_cred is None:
                    # 解密旧 api_key
                    try:
                        api_key_plain = cipher.decrypt(api_key_encrypted)
                    except Exception:
                        api_key_plain = ""

                    if api_key_plain:
                        # 计算前缀和 hash
                        if len(api_key_plain) > 10:
                            prefix = api_key_plain[:6] + "..." + api_key_plain[-4:]
                        else:
                            prefix = api_key_plain[:4] + "..."
                        key_hash = hashlib.sha256(api_key_plain.encode("utf-8")).hexdigest()

                        cred = ProviderCredential(
                            id=uuid.uuid4().hex,
                            provider_id=provider_id,
                            api_key_encrypted=cipher.encrypt(api_key_plain),
                            api_key_prefix=prefix,
                            api_key_hash=key_hash,
                            label="",
                            is_active=True,
                            last_used_at="",
                            created_at=utc_now(),
                        )
                        session.add(cred)
                        logger.info(f"[Migration] Migrated credential for provider: {provider_id}")

            session.commit()
        count += 1

    _mark_migrated("providers_from_config_items", count)
    logger.success(f"[Migration] providers_from_config_items: migrated {count} providers")
    return count


def _migrate_agents_json_file() -> int:
    """补充迁移：将 agents.json 中缺失的 agent 写入 agents 表。

    原始 agents 迁移使用 agents_store facade（已指向 SQLite），
    但部分环境下 JSON 文件数据可能未完全同步到 DB。
    本函数直接读取 JSON 文件，将缺失的 agent 插入 DB（幂等：已存在则跳过）。
    """
    if _is_migrated("agents_json_file"):
        return 0

    from app.infrastructure.database.models.agent import Agent

    path = os.path.join(settings.DATA_DIR, "store", "agents.json")
    data = _read_json_file(path)
    if not data or not isinstance(data, dict):
        _mark_migrated("agents_json_file", 0)
        logger.info("[Migration] agents_json_file: no JSON data found")
        return 0

    count = 0
    for agent_id, agent_data in data.items():
        if not isinstance(agent_data, dict) or not agent_id:
            continue
        with sync_session_factory() as session:
            existing = session.get(Agent, agent_id)
            if existing is not None:
                continue
            now = utc_now()
            agent = Agent(
                id=agent_id,
                name=agent_data.get("name", "Unknown"),
                description=agent_data.get("description", ""),
                system_prompt=agent_data.get("system_prompt", ""),
                model=agent_data.get("model"),
                provider=agent_data.get("provider"),
                color=agent_data.get("color", DEFAULT_AGENT_COLOR),
                avatar=agent_data.get("avatar"),
                capabilities=agent_data.get("capabilities", ["chat"]),
                memory_access=agent_data.get("memory_access", "none"),
                is_active=agent_data.get("is_active", True),
                is_main=agent_data.get("is_main", False),
                created_at=agent_data.get("created_at", now),
                updated_at=agent_data.get("updated_at", now),
            )
            session.add(agent)
            session.commit()
            logger.info(f"[Migration] Created agent from JSON: {agent_id} ({agent.name})")
        count += 1

    _mark_migrated("agents_json_file", count)
    logger.success(f"[Migration] agents_json_file: migrated {count} agents")
    return count


def _migrate_scheduled_tasks() -> int:
    """迁移 scheduled_tasks.json → scheduled_tasks 表。

    旧调度器将任务存储在 JSON 文件中，新系统使用 scheduled_tasks 表。
    迁移时将 JSON 中的 cron 字段拼接后写入 DB，并标记 is_active=True。

    幂等设计：已存在于 DB 的 task_id 跳过。
    """
    if _is_migrated("scheduled_tasks"):
        return 0

    from app.infrastructure.database.models.scheduled_task import ScheduledTaskORM

    path = os.path.join(settings.DATA_DIR, "scheduled_tasks.json")
    data = _read_json_file(path)
    if not data or not isinstance(data, dict):
        _mark_migrated("scheduled_tasks", 0)
        logger.info("[Migration] scheduled_tasks: no JSON file found")
        return 0

    tasks = data.get("tasks", [])
    if not isinstance(tasks, list) or not tasks:
        _mark_migrated("scheduled_tasks", 0)
        logger.info("[Migration] scheduled_tasks: empty task list")
        return 0

    count = 0
    for task_data in tasks:
        if not isinstance(task_data, dict):
            continue
        task_id = task_data.get("id", "")
        if not task_id:
            continue

        # 跳过已完成/已移除的任务
        status = task_data.get("status", "")
        if status in ("completed", "removed"):
            continue

        # 构建 cron 表达式
        cron_parts = [
            task_data.get("cron_minute") or "*",
            task_data.get("cron_hour") or "*",
            task_data.get("cron_day") or "*",
            task_data.get("cron_month") or "*",
            task_data.get("cron_day_of_week") or "*",
        ]
        schedule_cron = " ".join(cron_parts)

        # 确定调度类型
        task_type = task_data.get("task_type", "cron")
        schedule_type = task_type if task_type in ("cron", "interval", "date") else "cron"

        # 提取 action（从 payload.instruction）
        payload = task_data.get("payload", {})
        action = payload.get("instruction", "") if isinstance(payload, dict) else ""
        context = payload.get("context", "") if isinstance(payload, dict) else ""

        with sync_session_factory() as session:
            existing = session.get(ScheduledTaskORM, task_id)
            if existing is not None:
                continue
            task = ScheduledTaskORM(
                task_id=task_id,
                name=task_data.get("name", ""),
                schedule_cron=schedule_cron,
                schedule_type=schedule_type,
                action=action,
                description=task_data.get("description", ""),
                context=context,
                created_from=task_data.get("source", "main_agent"),
                is_active=True,
                created_at=utc_now(),
            )
            session.add(task)
            session.commit()
            logger.info(f"[Migration] Created scheduled task: {task_id} ({task.name})")
        count += 1

    _mark_migrated("scheduled_tasks", count)
    logger.success(f"[Migration] scheduled_tasks: migrated {count} tasks")
    return count


# ──────────────────────────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────────────────────────

def _migrate_from_standalone_db() -> int:
    """从独立后端 DB 迁移数据到 Electron DB（跨数据目录迁移）。

    场景：用户先通过 `python main.py`（standalone）运行后端并完成了 JSON→SQLite 迁移，
    然后通过 Electron 启动应用。Electron 使用不同的 DATA_DIR（%APPDATA%/luominest-desktop/Data/backend/），
    其 DB 是空的，需要把 standalone DB 的数据复制过来。

    幂等设计：检查当前 DB 是否已有 providers/conversations 数据，
    若已有则跳过（避免覆盖 Electron 模式下的新数据）。
    """
    if _is_migrated("standalone_db"):
        return 0

    # 定位 standalone DB 路径
    # 当前 DATA_DIR 是 Electron 模式时，standalone DB 在项目根目录 backend/data/ 下
    current_data_dir = os.path.normpath(settings.DATA_DIR)
    # 尝试多个可能的 standalone 数据目录
    candidates = []
    # 1. 项目根目录下的 backend/data（开发模式）
    # 从当前文件向上查找
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = script_dir
    for _ in range(10):  # 最多向上 10 级
        if os.path.exists(os.path.join(project_root, "backend", "data", "luominest.db")):
            candidates.append(os.path.join(project_root, "backend", "data", "luominest.db"))
            break
        parent = os.path.dirname(project_root)
        if parent == project_root:
            break
        project_root = parent
    # 2. 相对路径（兜底）
    candidates.append(os.path.join("backend", "data", "luominest.db"))

    standalone_db = None
    for candidate in candidates:
        abs_candidate = os.path.abspath(candidate)
        if os.path.exists(abs_candidate) and os.path.normpath(abs_candidate) != current_data_dir:
            # 确认不是同一个文件
            if not os.path.samefile(abs_candidate, os.path.join(current_data_dir, "luominest.db")):
                standalone_db = abs_candidate
                break

    if not standalone_db:
        logger.debug("[Migration] standalone_db: no standalone DB found, skipping")
        _mark_migrated("standalone_db", 0)
        return 0

    logger.info(f"[Migration] Found standalone DB: {standalone_db}")

    # 检查当前 DB 是否已有数据（如果有数据则跳过，避免覆盖）
    import sqlite3
    try:
        with sync_session_factory() as session:
            from sqlalchemy import text as sa_text
            result = session.execute(sa_text("SELECT COUNT(*) FROM providers")).scalar()
            if result and result > 0:
                logger.info(f"[Migration] standalone_db: current DB already has {result} providers, skipping")
                _mark_migrated("standalone_db", 0)
                return 0
    except Exception:
        logger.warning("[Migration] standalone_db: 现库数据量预检失败，继续执行复制流程", exc_info=True)

    # 从 standalone DB 复制数据
    import sqlite3
    count = 0
    try:
        src = sqlite3.connect(standalone_db)
        src.row_factory = sqlite3.Row

        # 需要复制的表列表（按依赖顺序）
        tables_to_copy = [
            "providers",
            "provider_credentials",
            "agents",
            "conversations",
            "config_items",
            "platform_instances",
            "scheduled_tasks",
            "usage_records",
            "workflow_sessions",
            "workflow_nodes",
            "groups",
            "repo_sources",
            "marketplace_stats",
            "tool_call_records",
            "audit_logs",
        ]

        with sync_session_factory() as dst_session:
            from sqlalchemy import text as sa_text
            for table in tables_to_copy:
                try:
                    # 检查源表是否有数据
                    src_rows = src.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                    if not src_rows or src_rows[0] == 0:
                        continue

                    # 检查目标表是否已有数据
                    dst_count = dst_session.execute(sa_text(f"SELECT COUNT(*) FROM {table}")).scalar()
                    if dst_count and dst_count > 0:
                        logger.debug(f"[Migration] standalone_db: {table} already has {dst_count} rows, skipping")
                        continue

                    # 获取列名
                    cols_info = src.execute(f"PRAGMA table_info({table})").fetchall()
                    col_names = [c[1] for c in cols_info]

                    # 读取源数据
                    rows = src.execute(f"SELECT * FROM {table}").fetchall()

                    # 逐行插入
                    for row in rows:
                        placeholders = ", ".join(["?" for _ in col_names])
                        col_list = ", ".join(col_names)
                        values = tuple(row[c] for c in range(len(col_names)))
                        dst_session.execute(
                            sa_text(f"INSERT OR IGNORE INTO {table} ({col_list}) VALUES ({placeholders})"),
                            dict(zip(col_names, values))
                        )
                    dst_session.commit()
                    migrated = len(rows)
                    count += migrated
                    logger.info(f"[Migration] standalone_db: copied {migrated} rows from {table}")
                except Exception as e:
                    logger.warning(f"[Migration] standalone_db: failed to copy {table}: {e}")

        src.close()
    except Exception as e:
        logger.error(f"[Migration] standalone_db: failed to open standalone DB: {e}")
        _mark_migrated("standalone_db", -1)
        return -1

    _mark_migrated("standalone_db", count)
    logger.success(f"[Migration] standalone_db: migrated {count} total records from standalone DB")
    return count


def _migrate_plugin_states() -> int:
    """迁移 cx_plugin_states.json → config_items['plugins.states']。

    JSON 文件为 JsonStore 格式（{"disabled_plugins": [...]}），提取禁用 id 列表写入，
    与 CxPluginLifecycle 运行时写入的形状（list）保持一致；已有值时取并集，不覆盖。
    """
    if _is_migrated("plugin_states"):
        return 0

    path = os.path.join(settings.DATA_DIR, "store", "cx_plugin_states.json")
    data = _read_json_file(path)
    if data is None:
        _mark_migrated("plugin_states", 0)
        logger.info("[Migration] plugin_states: no JSON file found, marked as migrated (0 records)")
        return 0

    raw = data.get("disabled_plugins", []) if isinstance(data, dict) else []
    legacy_ids = [str(i) for i in raw] if isinstance(raw, list) else []

    existing = luominest_config_store.get("plugins.states")
    existing_ids = [str(i) for i in existing] if isinstance(existing, list) else []
    merged = existing_ids + [i for i in legacy_ids if i not in existing_ids]

    luominest_config_store.set("plugins.states", merged)
    _mark_migrated("plugin_states", len(merged))
    logger.success("[Migration] plugin_states: migrated to config_items['plugins.states']")
    return len(merged)


def _migrate_skill_disabled() -> int:
    """迁移 cx_skill_disabled.json → config_items['skills.disabled_ids']。

    JSON 文件为 JsonStore 格式（{"disabled_ids": [...]}），提取禁用 id 列表写入，
    与 CxSkillService 运行时写入的形状（list）保持一致；已有值时取并集，不覆盖。
    """
    if _is_migrated("skill_disabled"):
        return 0

    path = os.path.join(settings.DATA_DIR, "store", "cx_skill_disabled.json")
    data = _read_json_file(path)
    if data is None:
        _mark_migrated("skill_disabled", 0)
        logger.info("[Migration] skill_disabled: no JSON file found, marked as migrated (0 records)")
        return 0

    raw = data.get("disabled_ids", []) if isinstance(data, dict) else []
    legacy_ids = [str(i) for i in raw] if isinstance(raw, list) else []

    existing = luominest_config_store.get("skills.disabled_ids")
    existing_ids = [str(i) for i in existing] if isinstance(existing, list) else []
    merged = existing_ids + [i for i in legacy_ids if i not in existing_ids]

    luominest_config_store.set("skills.disabled_ids", merged)
    _mark_migrated("skill_disabled", len(merged))
    logger.success("[Migration] skill_disabled: migrated to config_items['skills.disabled_ids']")
    return len(merged)


# 数据源注册表：(名称, 迁移函数)
_MIGRATION_SOURCES: list[tuple[str, Callable[[], int]]] = [
    ("standalone_db", _migrate_from_standalone_db),  # 最先执行：跨 DB 数据迁移
    ("agents", _migrate_agents),
    ("agents_json_file", _migrate_agents_json_file),
    ("groups", _migrate_groups),
    ("platforms", _migrate_platforms),
    ("repo_sources", _migrate_repo_sources),
    ("marketplace_stats", _migrate_marketplace_stats),
    ("usage_records", _migrate_usage_records),
    ("user_config", _migrate_user_config),
    ("main_agent", _migrate_main_agent),
    ("model_config", _migrate_model_config),
    ("conversations", _migrate_conversations),
    # 对话域回填（§5.4）：须在 conversations/standalone_db 迁移之后执行，依赖平台会话映射
    ("conversation_domains", migrate_conversation_domains),
    ("providers_from_config_items", _migrate_providers_from_config_items),
    ("scheduled_tasks", _migrate_scheduled_tasks),
    ("plugin_states", _migrate_plugin_states),
    ("skill_disabled", _migrate_skill_disabled),
]


async def migrate_all_json_to_sqlite() -> dict[str, int]:
    """幂等迁移所有 JSON 数据源到 SQLite。

    每个数据源独立 try/except，失败不阻塞其他。
    返回 {source_name: migrated_count}，-1 表示该源失败。
    已迁移的源返回 0（跳过）。
    """
    logger.info("[Migration] Starting JSON → SQLite migration...")
    results: dict[str, int] = {}

    for source_name, migrate_fn in _MIGRATION_SOURCES:
        try:
            results[source_name] = await asyncio.to_thread(migrate_fn)
        except Exception as e:
            logger.error(f"[Migration] {source_name} failed: {e}")
            results[source_name] = -1

    total = sum(v for v in results.values() if v > 0)
    logger.info(f"[Migration] Completed: {total} records migrated. Results: {results}")
    return results
