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

from app.core.config import settings
from app.infrastructure.database.facades.json_store_facade import (
    agents_store,
    groups_store,
    platforms_store,
    repo_sources_store,
)
from app.infrastructure.database.facades.marketplace_stats_store import marketplace_stats_store
from app.infrastructure.database.config_store import lumi_config_store
from app.infrastructure.database.usage_store import usage_store
from app.infrastructure.database.conversation_store import conversation_store
from app.infrastructure.database.facades.main_agent_config import save_luominest_main_agent_config
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
        lumi_config_store.set(key, value)
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

    lumi_config_store.set("model_config", data)
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


# ──────────────────────────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────────────────────────

# 数据源注册表：(名称, 迁移函数)
_MIGRATION_SOURCES: list[tuple[str, Callable[[], int]]] = [
    ("agents", _migrate_agents),
    ("groups", _migrate_groups),
    ("platforms", _migrate_platforms),
    ("repo_sources", _migrate_repo_sources),
    ("marketplace_stats", _migrate_marketplace_stats),
    ("usage_records", _migrate_usage_records),
    ("user_config", _migrate_user_config),
    ("main_agent", _migrate_main_agent),
    ("model_config", _migrate_model_config),
    ("conversations", _migrate_conversations),
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
