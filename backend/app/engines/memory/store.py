import hashlib
import re
import shutil
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy import create_engine, delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.utils import utc_now

from app.core.config import settings
from app.core.domain_policy import MAIN_AGENT_ID, TRACK_OWNER, TRACK_USERS
from app.infrastructure.database.base import Base
from app.infrastructure.database.models.memory import (
    MemoryDaily,
    MemoryFact,
    MemoryKnowledge,
    MemoryProfile,
    MemorySummary,
    MemoryVector,
)
from app.infrastructure.database.session import sync_session_factory
from .models import (
    ArchivedFact,
    FactItem,
    MemoryData,
    ProfileData,
    SummaryData,
)

# 记忆/向量模型表（本地独立库建表用，全局库由 create_all 统一创建）
_MEMORY_TABLES = [
    MemoryProfile.__table__,
    MemoryFact.__table__,
    MemorySummary.__table__,
    MemoryKnowledge.__table__,
    MemoryDaily.__table__,
    MemoryVector.__table__,
]

# 每日记录展示时区
_TZ = ZoneInfo("Asia/Shanghai")


# ──────────────────────────────────────────────────────────────
# 双轨目录解析（洋葱架构 §8.5.2 / §13 B18）
# ──────────────────────────────────────────────────────────────

# user_key 路径白名单：字母数字与 -_.（形如 qq_onebot_10001）
_USER_KEY_ALLOWED = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

# 历史版本 owner 数据所在目录（按优先级兜底；M2=B 零迁移过渡）
_LEGACY_OWNER_KEYS = ("main", "_default")

# SQLite 行级隔离键前缀（owner 轨道）：owner:{agent_key}
OWNER_PREFIX = "owner:"


def owner_key_for(owner: str) -> str:
    """owner 标识 → SQLite 行级隔离键（owner:{owner}）。"""
    return f"{OWNER_PREFIX}{owner}"


def agents_root() -> Path:
    """记忆双轨 agents 根目录：{DATA_DIR}/memory/agents。"""
    return Path(settings.DATA_DIR) / "memory" / "agents"


def agent_memory_dir(agent_id: str) -> Path:
    """Agent 记忆目录：{DATA_DIR}/memory/agents/{agent_id}。"""
    return agents_root() / agent_id


def remove_agent_memory(agent_id: str) -> bool:
    """删除 Agent 的旧文件布局记忆目录（存在才删）。

    Returns:
        是否实际执行了删除（目录不存在时返回 False，与既有调用点行为一致）。
    """
    agent_dir = agent_memory_dir(agent_id)
    if agent_dir.exists():
        shutil.rmtree(agent_dir)
        return True
    return False


def sanitize_track_key(user_key: str) -> str:
    """校验并返回路径安全的 user_key；非法时抛 ValueError（防路径穿越）。"""
    key = (user_key or "").strip()
    if not _USER_KEY_ALLOWED.match(key):
        raise ValueError(f"Invalid user_key for memory track: {user_key!r}")
    return key


def resolve_owner_agent_key(base_dir: Path | None = None) -> str:
    """解析主人轨道对应的 agents/ 子目录名（M2=B：owner 为 agents/ 的别名）。

    规范目录为 ``agents/{MAIN_AGENT_ID}``；不存在时按优先级回退到历史
    目录（main / _default），保证存量数据零迁移可读；均不存在时返回规范名。
    """
    agents_dir = Path(base_dir) if base_dir else agents_root()
    if (agents_dir / MAIN_AGENT_ID).exists():
        return MAIN_AGENT_ID
    for legacy_key in _LEGACY_OWNER_KEYS:
        if (agents_dir / legacy_key).exists():
            return legacy_key
    return MAIN_AGENT_ID


def resolve_track_dir(track: str, user_key: str = "", base_dir: Path | None = None) -> Path:
    """轨道 → 目录定位（§8.5.2）。读写逻辑由 MemoryStore 复用，此处只做路径解析。

    - owner            → memory/agents/{owner_key}/（owner ≙ 主 Agent 目录，别名过渡）
    - users + user_key → memory/users/{user_key}/

    Args:
        track: TRACK_OWNER / TRACK_USERS
        user_key: users 轨道必填（私聊用户标识，群聊为空时不应调用）
        base_dir: memory 根目录（缺省 settings.DATA_DIR/memory）
    """
    base = Path(base_dir) if base_dir else Path(settings.DATA_DIR) / "memory"
    if track == TRACK_OWNER:
        return base / "agents" / resolve_owner_agent_key(base / "agents")
    if track == TRACK_USERS:
        return base / "users" / sanitize_track_key(user_key)
    raise ValueError(f"Unknown memory track: {track!r}")


def store_path_for_owner_key(
    owner_key: str,
    conversation_id: str = "",
    memory_root: Path | None = None,
) -> Path:
    """owner_key（+对话级）→ 规范存储目录（SQLite 行级隔离键的路径映射）。

    用于从 DB 反向枚举（如清理任务）：owner:{key} → memory/agents/{key}，
    users:{key} → memory/users/{key}；tmp: 测试轨不映射（抛 ValueError）。
    """
    root = Path(memory_root) if memory_root else Path(settings.DATA_DIR) / "memory"
    if owner_key.startswith(OWNER_PREFIX):
        base = root / "agents" / owner_key[len(OWNER_PREFIX):]
    elif owner_key.startswith("users:"):
        base = root / "users" / owner_key[len("users:"):]
    else:
        raise ValueError(f"owner_key not mappable to a store path: {owner_key!r}")
    if conversation_id:
        base = base / "conversations" / conversation_id
    return base


# ──────────────────────────────────────────────────────────────
# SQLite 后端：全局库（与对话同库，统一备份）或独立文件（临时目录）
# ──────────────────────────────────────────────────────────────

def _derive_owner_key(storage_path: Path) -> str:
    """从存储路径推导 owner_key（SQLite 行级隔离键）。

    - {DATA_DIR}/memory/agents/{key}/...   → owner:{key}
    - {DATA_DIR}/memory/users/{key}/...    → users:{key}
    - 其他路径（测试/临时目录）            → tmp:{sha1[:12]}
    """
    p = Path(storage_path).resolve()
    root = (Path(settings.DATA_DIR) / "memory").resolve()
    try:
        rel = p.relative_to(root)
    except ValueError:
        digest = hashlib.sha1(str(p).encode("utf-8")).hexdigest()[:12]
        return f"tmp:{digest}"
    parts = rel.parts
    if parts and parts[0] == "users" and len(parts) > 1:
        return f"users:{parts[1]}"
    if parts and parts[0] == "agents" and len(parts) > 1:
        return owner_key_for(parts[1])
    if parts and parts[0] == "agents":
        return owner_key_for(MAIN_AGENT_ID)
    # 旧布局根目录（memory/memory.json 时代）兜底
    return owner_key_for(MAIN_AGENT_ID)


def _derive_conversation_id(storage_path: Path) -> str:
    """从存储路径推导对话级隔离键（路径含 conversations/{id} 时返回该 id，否则空串）。"""
    p = Path(storage_path).resolve()
    root = (Path(settings.DATA_DIR) / "memory").resolve()
    try:
        parts = p.relative_to(root).parts
    except ValueError:
        parts = ()
    if "conversations" in parts:
        idx = parts.index("conversations")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return ""


class _MemoryDB:
    """记忆/向量 SQLite 后端统一封装。

    - 全局模式：复用 sync_session_factory（与对话同一 luominest.db → 单备份单元）
    - 本地模式：storage_path 不在 DATA_DIR/memory 下时（测试/临时目录），
      在 storage_path/memory.db 建独立库，互不串扰
    """

    def __init__(self, storage_path: Path):
        self._is_global = False
        self._local_engine: Engine | None = None
        root = (Path(settings.DATA_DIR) / "memory").resolve()
        try:
            Path(storage_path).resolve().relative_to(root)
            self._is_global = True
        except ValueError:
            local_db = Path(storage_path) / "memory.db"
            self._local_engine = create_engine(
                f"sqlite:///{local_db}",
                connect_args={"timeout": 30, "check_same_thread": False},
                poolclass=NullPool,
            )
            Base.metadata.create_all(self._local_engine, tables=_MEMORY_TABLES)

    @contextmanager
    def session(self) -> Iterator[Session]:
        if self._is_global:
            with sync_session_factory() as session:
                yield session
        else:
            with Session(self._local_engine) as session:  # type: ignore[union-attr]
                yield session

    def close(self) -> None:
        if self._local_engine is not None:
            self._local_engine.dispose()
            self._local_engine = None


class MemoryStore:
    """纯存储层：SQLite 读写（单库单事务）、缓存、线程锁、格式迁移。

    公开 API 与旧文件实现保持一致（load_data/save_data/load_knowledge/
    append_daily/...），便于 MemoryEngine 与调用方零改动切换。
    """

    def __init__(self, storage_path: Path):
        self._path = Path(storage_path)
        self._path.mkdir(parents=True, exist_ok=True)
        # 兼容旧代码/测试对 daily 目录的依赖（SQLite 下不再写入，仅保留占位）
        (self._path / "daily").mkdir(exist_ok=True)
        # NOTE: 使用 threading.RLock 而非 asyncio.Lock，原因：
        # MemoryStore 的所有数据读写方法（load_data, save_data 等）均为同步方法，
        # 在 async 上下文中通过 asyncio.to_thread 包装调用，to_thread 在独立线程中执行，
        # threading.RLock 在此场景下是正确的选择（asyncio.Lock 不能在非 async 函数中使用）。
        self._lock = threading.RLock()
        self._cache: MemoryData | None = None
        self._owner_key = _derive_owner_key(self._path)
        self._conversation_id = _derive_conversation_id(self._path)
        self._db = _MemoryDB(self._path)
        self._auto_migrate()

    @classmethod
    def for_track(cls, track: str, user_key: str = "", base_dir: Path | None = None) -> "MemoryStore":
        """按记忆轨道构造 MemoryStore（§8.5.2 双轨）。

        路径解析即目录定位（resolve_track_dir）；owner_key 由路径推导
        （owner:agent_key / users:user_key），保证主人记忆与平台用户记忆
        在 SQLite 中行级隔离、互不串扰。
        """
        return cls(resolve_track_dir(track, user_key, base_dir))

    @property
    def owner_key(self) -> str:
        """行级隔离键（owner:… / users:… / tmp:…），向量索引与记忆共用。"""
        return self._owner_key

    # ── 兼容旧文件布局的虚拟路径（历史 API/端点仍引用） ──

    def _memory_file(self) -> Path:
        return self._path / "memory.json"

    def _knowledge_file(self) -> Path:
        return self._path / "knowledge.md"

    @staticmethod
    def _safe_conversation_id(conversation_id: str) -> str:
        """校验并返回路径安全的 conversation_id（防路径遍历）。"""
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in conversation_id)
        if safe_id != conversation_id:
            raise ValueError(f"Invalid conversation_id: {conversation_id!r}")
        return safe_id

    def _daily_file(self, date: str | None = None, conversation_id: str | None = None) -> Path:
        """兼容旧布局的虚拟路径（SQLite 下仅作展示/迁移参考，不再读写）。"""
        if date is not None:
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
                raise ValueError(f"Invalid date format: {date!r}, expected YYYY-MM-DD")
        else:
            date = datetime.now(_TZ).strftime("%Y-%m-%d")
        if conversation_id:
            safe_id = self._safe_conversation_id(conversation_id)
            return self._path / "conversations" / safe_id / "daily" / f"{date}.md"
        return self._path / "daily" / f"{date}.md"

    def _legacy_daily_file(self, date: str, conversation_id: str) -> Path:
        """旧布局（历史数据兜底）：{path}/daily/{conversation_id}/{date}.md。"""
        return self._path / "daily" / conversation_id / f"{date}.md"

    # --- 格式迁移（文件 → SQLite 由 migration.memory_to_sqlite_migrator 统一执行） ---

    def _auto_migrate(self) -> None:
        # 旧实现在此处把 MEMORY.md/summary.md 迁移到 memory.json；
        # SQLite 化后文件级迁移统一收敛到 DB 迁移器（幂等，见
        # app/infrastructure/database/migration/memory_to_sqlite_migrator.py），
        # 此处不再需要 per-store 文件迁移。
        return

    def _migrate_summary_sections(self, raw: dict) -> None:
        # 兼容旧逻辑：preferences → interests 分区改名（历史 memory.json 兜底）
        summaries = raw.get("summaries", {})
        if not summaries:
            return
        if "preferences" in summaries and "interests" not in summaries:
            old_prefs = summaries["preferences"]
            if isinstance(old_prefs, dict) and old_prefs.get("summary"):
                summaries["interests"] = {
                    "summary": old_prefs["summary"],
                    "updated_at": old_prefs.get("updated_at", ""),
                }
                summaries["preferences"] = {"summary": "", "updated_at": ""}
                logger.info("[Memory] Migrated '兴趣偏好' to '兴趣目标'")

    # --- 数据读写（SQLite） ---

    def load_data(self) -> MemoryData:
        with self._lock:
            if self._cache is not None:
                return self._cache
            data = MemoryData()
            try:
                with self._db.session() as session:
                    profile_row = session.get(
                        MemoryProfile, (self._owner_key, self._conversation_id)
                    )
                    if profile_row is not None:
                        data.profile = ProfileData(
                            name=profile_row.name or "",
                            updated_at=profile_row.updated_at or "",
                            static_facts=list(profile_row.static_facts or []),
                            dynamic_context=list(profile_row.dynamic_context or []),
                        )
                    fact_rows = (
                        session.execute(
                            select(MemoryFact)
                            .where(
                                MemoryFact.owner_key == self._owner_key,
                                MemoryFact.conversation_id == self._conversation_id,
                            )
                            .order_by(MemoryFact.created_at.asc(), MemoryFact.id.asc())
                        )
                        .scalars()
                        .all()
                    )
                    data.facts = [self._fact_from_row(r) for r in fact_rows]
                    summary_rows = (
                        session.execute(
                            select(MemorySummary).where(
                                MemorySummary.owner_key == self._owner_key,
                                MemorySummary.conversation_id == self._conversation_id,
                            )
                        )
                        .scalars()
                        .all()
                    )
                    data.summaries = self._summaries_from_rows(summary_rows)
            except Exception as e:
                logger.warning(f"[Memory] Failed to load memory data from SQLite: {e}")
            self._cache = data
            return data

    def save_data(self, data: MemoryData) -> None:
        with self._lock:
            data.last_updated = utc_now()
            try:
                with self._db.session() as session:
                    profile = session.get(
                        MemoryProfile, (self._owner_key, self._conversation_id)
                    )
                    if profile is None:
                        profile = MemoryProfile(
                            owner_key=self._owner_key,
                            conversation_id=self._conversation_id,
                        )
                        session.add(profile)
                    profile.name = data.profile.name or ""
                    profile.static_facts = data.profile.static_facts or []
                    profile.dynamic_context = data.profile.dynamic_context or []
                    profile.updated_at = data.profile.updated_at or utc_now()

                    # 事实全量替换（单事务；事实集合量级小，替换语义最稳）
                    session.execute(
                        delete(MemoryFact).where(
                            MemoryFact.owner_key == self._owner_key,
                            MemoryFact.conversation_id == self._conversation_id,
                        )
                    )
                    for fact in data.facts:
                        session.add(self._fact_to_row(fact))

                    # 摘要分区 upsert
                    for section_name, section in data.summaries.model_dump().items():
                        summary_row = session.get(
                            MemorySummary,
                            (self._owner_key, self._conversation_id, section_name),
                        )
                        if summary_row is None:
                            summary_row = MemorySummary(
                                owner_key=self._owner_key,
                                conversation_id=self._conversation_id,
                                section=section_name,
                            )
                            session.add(summary_row)
                        summary_row.summary = section.get("summary", "") or ""
                        summary_row.updated_at = section.get("updated_at", "") or ""

                    session.commit()
            except Exception as e:
                logger.error(f"[Memory] Failed to save memory data to SQLite: {e}")
                raise
            self._cache = data

    def _fact_to_row(self, fact: FactItem) -> MemoryFact:
        return MemoryFact(
            id=fact.id,
            owner_key=self._owner_key,
            conversation_id=self._conversation_id,
            content=fact.content,
            category=fact.category,
            confidence=fact.confidence,
            created_at=fact.created_at,
            source=fact.source,
            source_error=fact.source_error,
            expires_at=fact.expires_at,
            is_latest=1 if fact.is_latest else 0,
            supersedes_id=fact.supersedes_id,
            source_conversation_id=fact.source_conversation_id,
            source_message=fact.source_message,
            history=[a.model_dump() for a in fact.history],
        )

    @staticmethod
    def _fact_from_row(row: MemoryFact) -> FactItem:
        return FactItem.model_validate({
            "id": row.id,
            "content": row.content,
            "category": row.category,
            "confidence": row.confidence,
            "created_at": row.created_at,
            "source": row.source,
            "source_error": row.source_error,
            "expires_at": row.expires_at,
            "is_latest": bool(row.is_latest),
            "supersedes_id": row.supersedes_id,
            "source_conversation_id": row.source_conversation_id,
            "source_message": row.source_message,
            "history": [ArchivedFact.model_validate(h) for h in (row.history or [])],
        })

    @staticmethod
    def _summaries_from_rows(rows) -> SummaryData:
        data = SummaryData()
        for row in rows:
            section = getattr(data, row.section, None)
            if section is not None:
                section.summary = row.summary or ""
                section.updated_at = row.updated_at or ""
        return data

    # --- 知识 ---

    def load_knowledge(self) -> str:
        with self._lock:
            try:
                with self._db.session() as session:
                    row = session.get(
                        MemoryKnowledge, (self._owner_key, self._conversation_id)
                    )
                    return row.content if row is not None else ""
            except Exception as e:
                logger.warning(f"[Memory] Failed to load knowledge: {e}")
                return ""

    def save_knowledge(self, content: str) -> None:
        with self._lock:
            try:
                with self._db.session() as session:
                    row = session.get(
                        MemoryKnowledge, (self._owner_key, self._conversation_id)
                    )
                    if row is None:
                        row = MemoryKnowledge(
                            owner_key=self._owner_key,
                            conversation_id=self._conversation_id,
                        )
                        session.add(row)
                    row.content = content or ""
                    row.updated_at = utc_now()
                    session.commit()
            except Exception as e:
                logger.error(f"[Memory] Failed to save knowledge: {e}")
                raise

    def export_knowledge(self, path: Path | None = None) -> Path:
        """把 SQLite 中的知识库导出为 Markdown 文件（knowledge.md 的导出视图）。

        供迁移器/管理端使用；不指定 path 时导出到存储目录下 knowledge.md。
        """
        target = Path(path) if path else self._knowledge_file()
        content = self.load_knowledge()
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(content or "", encoding="utf-8")
        tmp.replace(target)
        return target

    def parse_knowledge(self) -> list[dict[str, str]]:
        content = self.load_knowledge()
        if not content.strip():
            return []
        sections: list[dict[str, str]] = []
        lines = content.split("\n")
        current_title = ""
        current_lines: list[str] = []
        for line in lines:
            if line.startswith("## "):
                if current_title and current_lines:
                    sections.append(
                        {"title": current_title, "content": "\n".join(current_lines)}
                    )
                current_title = line.replace("## ", "").strip()
                current_lines = []
            elif line.strip().startswith("- "):
                current_lines.append(line.strip())
        if current_title and current_lines:
            sections.append({"title": current_title, "content": "\n".join(current_lines)})
        return sections

    # --- 每日记录（行式追加，替代读-改-写整文件） ---

    @staticmethod
    def _today() -> str:
        return datetime.now(_TZ).strftime("%Y-%m-%d")

    @staticmethod
    def _now_hhmm() -> str:
        return datetime.now(_TZ).strftime("%H:%M")

    def append_daily(self, content: str, date: str | None = None, conversation_id: str | None = None) -> None:
        with self._lock:
            actual_date = date or self._today()
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", actual_date):
                raise ValueError(f"Invalid date format: {actual_date!r}, expected YYYY-MM-DD")
            conv_id = conversation_id or self._conversation_id
            try:
                with self._db.session() as session:
                    session.add(MemoryDaily(
                        owner_key=self._owner_key,
                        conversation_id=conv_id,
                        date=actual_date,
                        created_at=self._now_hhmm(),
                        content=content,
                    ))
                    session.commit()
            except Exception as e:
                logger.error(f"[Memory] Failed to append daily: {e}")
                raise

    def load_daily(self, date: str | None = None, conversation_id: str | None = None) -> str:
        """加载每日记录（格式化回 Markdown 文本，与旧文件布局展示一致）。"""
        with self._lock:
            actual_date = date or self._today()
            conv_id = conversation_id if conversation_id is not None else self._conversation_id
            try:
                with self._db.session() as session:
                    stmt = select(MemoryDaily).where(
                        MemoryDaily.owner_key == self._owner_key,
                        MemoryDaily.date == actual_date,
                    )
                    if conv_id:
                        stmt = stmt.where(MemoryDaily.conversation_id == conv_id)
                    rows = (
                        session.execute(
                            stmt.order_by(
                                MemoryDaily.conversation_id.asc(),
                                MemoryDaily.id.asc(),
                            )
                        )
                        .scalars()
                        .all()
                    )
            except Exception as e:
                logger.warning(f"[Memory] Failed to load daily: {e}")
                return ""
            if not rows:
                return ""
            parts = [f"# {actual_date}", ""]
            for row in rows:
                parts.append(f"- [{row.created_at}] {row.content}")
            return "\n".join(parts)

    def list_dailies(self, conversation_id: str | None = None) -> list[str]:
        """列出有记录的日期（YYYY-MM-DD，升序）。"""
        conv_id = conversation_id if conversation_id is not None else self._conversation_id
        try:
            with self._db.session() as session:
                stmt = select(MemoryDaily.date).where(MemoryDaily.owner_key == self._owner_key)
                if conv_id:
                    stmt = stmt.where(MemoryDaily.conversation_id == conv_id)
                dates = set(session.execute(stmt.distinct()).scalars().all())
                return sorted(d for d in dates if d)
        except Exception as e:
            logger.warning(f"[Memory] Failed to list dailies: {e}")
            return []

    def list_conversation_dailies(self) -> list[str]:
        """列出所有有 daily 记录的 conversation_id。"""
        try:
            with self._db.session() as session:
                rows = session.execute(
                    select(MemoryDaily.conversation_id)
                    .where(
                        MemoryDaily.owner_key == self._owner_key,
                        MemoryDaily.conversation_id != "",
                    )
                    .distinct()
                ).scalars().all()
                return sorted(rows)
        except Exception as e:
            logger.warning(f"[Memory] Failed to list conversation dailies: {e}")
            return []

    # --- 清空操作 ---

    def clear_knowledge(self) -> None:
        with self._lock:
            try:
                with self._db.session() as session:
                    session.execute(
                        delete(MemoryKnowledge).where(
                            MemoryKnowledge.owner_key == self._owner_key,
                            MemoryKnowledge.conversation_id == self._conversation_id,
                        )
                    )
                    session.commit()
            except Exception as e:
                logger.error(f"[Memory] Failed to clear knowledge: {e}")
                raise

    def clear_daily(self, conversation_id: str, date: str | None = None) -> None:
        """清除指定对话的 daily 记录。指定 date 只清当天，否则清全部。"""
        conv_id = conversation_id or self._conversation_id
        with self._lock:
            try:
                with self._db.session() as session:
                    stmt = delete(MemoryDaily).where(
                        MemoryDaily.owner_key == self._owner_key,
                        MemoryDaily.conversation_id == conv_id,
                    )
                    if date:
                        stmt = stmt.where(MemoryDaily.date == date)
                    session.execute(stmt)
                    session.commit()
            except Exception as e:
                logger.error(f"[Memory] Failed to clear daily: {e}")
                raise

    def clear_dailies(self) -> None:
        with self._lock:
            try:
                with self._db.session() as session:
                    session.execute(
                        delete(MemoryDaily).where(MemoryDaily.owner_key == self._owner_key)
                    )
                    session.commit()
            except Exception as e:
                logger.error(f"[Memory] Failed to clear dailies: {e}")
                raise

    def reset_all(self) -> None:
        """清空本 store 的全部数据（profile/facts/summaries/knowledge/daily）。"""
        with self._lock:
            try:
                with self._db.session() as session:
                    for table, where in (
                        (MemoryFact, (MemoryFact.owner_key == self._owner_key, MemoryFact.conversation_id == self._conversation_id)),
                        (MemorySummary, (MemorySummary.owner_key == self._owner_key, MemorySummary.conversation_id == self._conversation_id)),
                        (MemoryProfile, (MemoryProfile.owner_key == self._owner_key, MemoryProfile.conversation_id == self._conversation_id)),
                        (MemoryKnowledge, (MemoryKnowledge.owner_key == self._owner_key, MemoryKnowledge.conversation_id == self._conversation_id)),
                        (MemoryDaily, (MemoryDaily.owner_key == self._owner_key,)),
                    ):
                        session.execute(delete(table).where(*where))
                    session.commit()
            except Exception as e:
                logger.error(f"[Memory] Failed to reset memory store: {e}")
                raise
            self._cache = None

    def close(self) -> None:
        self._db.close()
