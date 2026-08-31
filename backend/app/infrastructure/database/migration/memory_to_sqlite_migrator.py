"""记忆系统文件 → SQLite 幂等迁移器（前端后端项目锐评 · 高优先级 #2/#3）。

旧实现在 SQLite 之外维护 memory.json / knowledge.md / daily/*.md 与
vectors.npz + vectors_meta.json（无事务、不随 DB 备份、全量重写）。
本迁移器把这些存量文件一次性导入 memory_* 表与 memory_vectors 表：

- memory.json（agents/ 主人轨、users/ 平台用户轨、conversations/ 对话级、旧根布局）
  → memory_profiles / memory_facts / memory_summaries（按 owner_key 行级隔离）
- knowledge.md → memory_knowledge
- daily/*.md（规范布局 + 旧布局 daily/{conv}/{date}.md）→ memory_daily（逐行）
- vectors/vectors.npz + vectors_meta.json → memory_vectors（BLOB 按行）

设计：
- 幂等：_migration_meta 标记源 ``memory_files``，防重跑；旧文件不删除（用户可手动清理）。
- 目标 store 已有数据时跳过该文件（防覆盖新写入）。
- 依赖 init_db 完成（表已建）后执行，注册于 json_to_sqlite_migrator._MIGRATION_SOURCES。
"""
import json
import re
from pathlib import Path

from loguru import logger

from app.core.config import settings
from app.engines.memory.models import MemoryData
from app.engines.memory.store import MemoryStore, _derive_owner_key

# _migration_meta 标记源名
MIGRATION_SOURCE = "memory_files"

_DAILY_LINE = re.compile(r"^-\s*\[([^\]]+)\]\s*(.*)$")


def _is_migrated(source: str) -> bool:
    from app.infrastructure.database.migration.json_to_sqlite_migrator import (
        _is_migrated as _inner,
    )
    return _inner(source)


def _mark_migrated(source: str, record_count: int) -> None:
    from app.infrastructure.database.migration.json_to_sqlite_migrator import (
        _mark_migrated as _inner,
    )
    _inner(source, record_count)


def _migrate_summary_sections(raw: dict) -> None:
    """兼容旧逻辑：preferences → interests 分区改名。"""
    summaries = raw.get("summaries", {})
    if not isinstance(summaries, dict):
        return
    if "preferences" in summaries and "interests" not in summaries:
        old_prefs = summaries.get("preferences")
        if isinstance(old_prefs, dict) and old_prefs.get("summary"):
            summaries["interests"] = {
                "summary": old_prefs["summary"],
                "updated_at": old_prefs.get("updated_at", ""),
            }
            summaries["preferences"] = {"summary": "", "updated_at": ""}


def _import_memory_json(memory_file: Path) -> int:
    """导入单个 memory.json 到目标 store（已有数据则跳过）。"""
    store = MemoryStore(memory_file.parent)
    existing = store.load_data()
    if existing.profile.name or existing.facts:
        return 0
    try:
        raw = json.loads(memory_file.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return 0
        _migrate_summary_sections(raw)
        data = MemoryData.model_validate(raw)
    except Exception as e:
        logger.warning(f"[MemoryMigrate] Parse failed: {memory_file}: {e}")
        return 0
    store.save_data(data)
    return 1


def _import_knowledge(knowledge_file: Path) -> int:
    """导入 knowledge.md 到目标 store（已有内容则跳过）。"""
    store = MemoryStore(knowledge_file.parent)
    if store.load_knowledge().strip():
        return 0
    try:
        content = knowledge_file.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"[MemoryMigrate] Read failed: {knowledge_file}: {e}")
        return 0
    if content.strip():
        store.save_knowledge(content)
        return 1
    return 0


def _import_daily_file(daily_file: Path) -> int:
    """导入单个 daily/{date}.md（含旧布局 daily/{conv}/{date}.md）。"""
    parent = daily_file.parent
    legacy_conv = None
    if parent.name == "daily":
        store_root = parent.parent
    else:
        # 旧布局：{store}/daily/{conv_id}/{date}.md
        store_root = parent.parent.parent
        legacy_conv = parent.name
    store = MemoryStore(store_root)
    try:
        content = daily_file.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"[MemoryMigrate] Read failed: {daily_file}: {e}")
        return 0
    date = daily_file.stem
    count = 0
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = _DAILY_LINE.match(line)
        if match:
            entry = match.group(2).strip()
        elif line.startswith("- "):
            entry = line[2:].strip()
        else:
            entry = line
        if entry:
            try:
                if legacy_conv:
                    store.append_daily(entry, date=date, conversation_id=legacy_conv)
                else:
                    store.append_daily(entry, date=date)
                count += 1
            except Exception as e:
                logger.warning(f"[MemoryMigrate] Append daily failed ({daily_file}): {e}")
                return count
    return count


def _import_vectors(npz_file: Path) -> int:
    """导入 vectors/vectors.npz + vectors_meta.json 到 memory_vectors。"""
    import numpy as np

    from app.infrastructure.database.models.memory import MemoryVector
    from app.infrastructure.database.session import sync_session_factory

    vectors_dir = npz_file.parent
    store_root = vectors_dir.parent  # 轨道目录
    owner_key = _derive_owner_key(store_root)
    meta_path = vectors_dir / "vectors_meta.json"
    meta = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"[MemoryMigrate] vectors_meta.json parse failed: {e}")

    try:
        data = np.load(npz_file, allow_pickle=False)
        ids = [str(x) for x in data["ids"]]
        vectors = data["vectors"]
    except Exception as e:
        logger.warning(f"[MemoryMigrate] npz load failed: {npz_file}: {e}")
        return 0

    imported = 0
    with sync_session_factory() as session:
        for i, fid in enumerate(ids):
            if session.get(MemoryVector, fid) is not None:
                continue
            m = meta.get(fid, {})
            session.add(MemoryVector(
                fact_id=fid,
                owner_key=owner_key,
                content=m.get("content", ""),
                category=m.get("category", ""),
                scope=m.get("scope", ""),
                conversation_id=m.get("conversation_id", ""),
                vector=np.asarray(vectors[i], dtype=np.float32).tobytes(),
            ))
            imported += 1
        session.commit()
    return imported


def migrate_memory_files_to_sqlite() -> int:
    """幂等迁移 memory 文件体系 → SQLite。返回导入的"文件/记录"计数。"""
    if _is_migrated(MIGRATION_SOURCE):
        logger.debug("[MemoryMigrate] already migrated, skipping")
        return 0

    memory_root = Path(settings.DATA_DIR) / "memory"
    if not memory_root.exists():
        _mark_migrated(MIGRATION_SOURCE, 0)
        logger.info("[MemoryMigrate] no memory dir found, marked as migrated (0 records)")
        return 0

    total = 0

    # 1) memory.json
    json_files = sorted(memory_root.rglob("memory.json"))
    for f in json_files:
        try:
            total += _import_memory_json(f)
        except Exception as e:
            logger.warning(f"[MemoryMigrate] memory.json import failed ({f}): {e}")

    # 2) knowledge.md
    knowledge_files = sorted(memory_root.rglob("knowledge.md"))
    for f in knowledge_files:
        try:
            total += _import_knowledge(f)
        except Exception as e:
            logger.warning(f"[MemoryMigrate] knowledge.md import failed ({f}): {e}")

    # 3) daily/*.md（规范布局 + 旧布局 daily/{conv}/{date}.md）
    daily_files = set(memory_root.rglob("daily/*.md")) | set(memory_root.rglob("daily/*/*.md"))
    for f in sorted(daily_files):
        try:
            total += _import_daily_file(f)
        except Exception as e:
            logger.warning(f"[MemoryMigrate] daily import failed ({f}): {e}")

    # 4) vectors.npz
    npz_files = sorted(memory_root.rglob("vectors.npz"))
    for f in npz_files:
        try:
            total += _import_vectors(f)
        except Exception as e:
            logger.warning(f"[MemoryMigrate] vectors import failed ({f}): {e}")

    _mark_migrated(MIGRATION_SOURCE, total)
    logger.success(
        f"[MemoryMigrate] Imported memory files → SQLite: "
        f"memory.json={len(json_files)}, knowledge.md={len(knowledge_files)}, "
        f"daily={len(daily_files)}, vectors.npz={len(npz_files)}, records={total}"
    )
    return total
