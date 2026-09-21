import hashlib
import re
import shutil
import sqlite3
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

from app.core.config import settings
from app.core.utils import utc_now

from app.core.domain_policy import MAIN_AGENT_ID, TRACK_OWNER, TRACK_USERS, TRACK_GROUPS
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
    """校验并返回路径安全的 user_key；非法时抛 ValueError（防路径穿越）。

    白名单为字母数字与 -_.；额外拒绝 "." / ".." 整段（白名单正则会放行
    纯点段，导致 users/.. 逃逸到上级目录）。群成员轨键由
    domain_policy.group_member_user_key 构造，段级已保证不会产生纯点段。
    """
    key = (user_key or "").strip()
    if key in (".", "..") or not _USER_KEY_ALLOWED.match(key):
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
    if track == TRACK_GROUPS:
        return base / "groups" / sanitize_track_key(user_key)
    raise ValueError(f"Unknown memory track: {track!r}")


def store_path_for_owner_key(
    owner_key: str,
    conversation_id: str = "",
    memory_root: Path | None = None,
) -> Path:
    """owner_key（+对话级）→ 规范存储目录（SQLite 行级隔离键的路径映射）。

    用于从 DB 反向枚举（如清理任务）：owner:{key} → memory/agents/{key}，
    users:{key} → memory/users/{key}，groups:{key} → memory/groups/{key}；tmp: 测试轨不映射（抛 ValueError）。
    """
    root = Path(memory_root) if memory_root else Path(settings.DATA_DIR) / "memory"
    if owner_key.startswith(OWNER_PREFIX):
        base = root / "agents" / owner_key[len(OWNER_PREFIX):]
    elif owner_key.startswith("users:"):
        base = root / "users" / owner_key[len("users:"):]
    elif owner_key.startswith("groups:"):
        base = root / "groups" / owner_key[len("groups:"):]
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
    - {DATA_DIR}/memory/groups/{key}/...   → groups:{key}
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
    if parts and parts[0] == "groups" and len(parts) > 1:
        return f"groups:{parts[1]}"
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


# ──────────────────────────────────────────────────────────────
# SQLite FTS5 BM25 腿（W5-4）：检索时按需同步的影子全文索引
# ──────────────────────────────────────────────────────────────
# 设计取舍（对修改书 W5-4 的落地报告，最终未用 external content + 触发器）：
#
# 1. 未采用「external content 虚表 + 触发器」首选方案，原因有二：
#    a) 分词器受限：触发器只能搬 NEW.content 原文，FTS5 内置分词器里
#       trigram 查询侧要求 ≥3 字（「生日」这类高频中文词无法命中），
#       unicode61 又把连续 CJK 并成单 token（整句一词、无法子串检索）；
#       中文可用的分词必须走 Python 侧预分词（复用 fact_manager 的
#       双字词+单字切分），触发器做不到。
#    b) 写法匹配差：memory_facts.id 是 TEXT 主键且 save_data 走「整轨
#       delete + 重插」写法，external content 的 rowid 映射每次保存全部
#       轮换；contentful 触发器影子表虽可行，但触发器挂在全局库共享表上，
#       对既有写入路径有侵入。
# 2. 最终方案：contentful 影子虚表（unicode61 分词，content 列存 Python
#    预分词后的空格连接文本），**检索时按需同步**——每次 BM25 检索前对本
#    作用域 (owner_key, conversation_id) 做事实集合 diff（新增/内容变更/
#    已删除），只同步差异行。事实 ≤ MAX_FACTS(100) 每作用域，diff 为两次
#    轻量 SELECT；检索语义上恒为最新（索引是纯派生物，不承担存储职责）。
# 3. FTS5 不可用的运行时（能力探针失败）→ 不建虚表，BM25 腿自动关闭，
#    检索退回向量/关键词路径，主体功能不受影响。
# 4. 分词/查询词项均复用 fact_manager._TOKEN_RE 与 _extract_content_words
#    （索引侧保停用词，查询侧经 _extract_content_words 去停用词）。

_FTS_TABLE = "memory_facts_fts"

_FTS_DDL = (
    f"CREATE VIRTUAL TABLE IF NOT EXISTS {_FTS_TABLE} USING fts5("
    "content, fact_id UNINDEXED, owner_key UNINDEXED, conversation_id UNINDEXED, "
    "tokenize='unicode61')"
)

# FTS5 能力探针（进程级一次；SQLite 构建缺 FTS5 时置 False）
_fts_capable: bool | None = None
# 已完成 DDL 的数据库标识（local 模式按 DB 路径；global 模式单一键），防重复执行
_fts_ddl_done: set[str] = set()
_fts_ddl_lock = threading.Lock()


def _probe_fts5() -> bool:
    """探测运行时 SQLite 是否带 FTS5（内存库一次性试建）。"""
    global _fts_capable
    if _fts_capable is None:
        conn = None
        try:
            conn = sqlite3.connect(":memory:")
            conn.execute("CREATE VIRTUAL TABLE probe_fts5 USING fts5(x)")
            _fts_capable = True
        except Exception as e:
            _fts_capable = False
            logger.warning(f"[Memory] SQLite FTS5 unavailable, BM25 leg disabled: {e}")
        finally:
            if conn is not None:
                conn.close()
    return _fts_capable


def ensure_fts_schema(engine) -> bool:
    """在给定 SQLAlchemy engine 的库上创建 FTS5 影子虚表（幂等）。

    供 _MemoryDB（local 模式）与全局库（首个 MemoryStore 初始化时）调用。
    FTS5 不可用或 DDL 失败时返回 False（BM25 腿关闭，不影响主流程）。
    """
    if not _probe_fts5():
        return False
    key = str(getattr(engine, "url", None) or id(engine))
    with _fts_ddl_lock:
        if key in _fts_ddl_done:
            return True
        try:
            from sqlalchemy import text

            with engine.begin() as conn:
                conn.execute(text(_FTS_DDL))
            _fts_ddl_done.add(key)
            return True
        except Exception as e:
            logger.warning(f"[Memory] FTS5 schema creation failed, BM25 leg disabled: {e}")
            return False


def ensure_global_fts_schema() -> bool:
    """全局库（与对话同库）的 FTS DDL：首个 MemoryStore 初始化时执行一次。"""
    from sqlalchemy import text

    from app.infrastructure.database.session import sync_session_factory

    if not _probe_fts5():
        return False
    key = "global"
    with _fts_ddl_lock:
        if key in _fts_ddl_done:
            return True
        try:
            with sync_session_factory() as session:
                session.execute(text(_FTS_DDL))
                session.commit()
            _fts_ddl_done.add(key)
            return True
        except Exception as e:
            logger.warning(f"[Memory] FTS5 schema creation failed, BM25 leg disabled: {e}")
            return False


def _fts_index_text(text: str) -> str:
    """索引侧预分词：fact_manager 的双字词/英文词/单汉字切分，空格连接。

    延迟导入规避 store ↔ fact_manager 循环依赖（fact_manager 顶层 import
    MemoryStore）；导入失败兜底为逐汉字切分，保证索引不至于全空。
    """
    try:
        from .fact_manager import _TOKEN_RE

        tokens = _TOKEN_RE.findall(text or "")
    except Exception:
        tokens = re.findall(r"[A-Za-z]+|[\u4e00-\u9fff]", text or "")
    return " ".join(tokens)


def build_fts_match_query(query: str) -> str:
    """查询文本 → FTS5 MATCH 表达式（OR 连接词项，与索引侧同源分词）。

    查询词项经 _extract_content_words 过滤停用词/无意义单字符；全部词项
    被过滤（如纯标点）时返回空串（调用方跳过 BM25 腿）。双引号剥离防
    MATCH 语法注入。
    """
    from .fact_manager import _extract_content_words

    words = _extract_content_words((query or "").casefold())
    terms = [w.replace('"', "") for w in words if w.replace('"', "")]
    return " OR ".join(f'"{t}"' for t in sorted(terms))


class _MemoryDB:
    """记忆/向量 SQLite 后端统一封装。

    - 全局模式：复用 sync_session_factory（与对话同一 luominest.db → 单备份单元）
    - 本地模式：storage_path 不在 DATA_DIR/memory 下时（测试/临时目录），
      在 storage_path/memory.db 建独立库，互不串扰
    """

    def __init__(self, storage_path: Path):
        self._is_global = False
        self._local_engine: Engine | None = None
        self.fts_enabled = False
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
            # FTS5 BM25 腿（W5-4）：本地模式建表后立即补虚表与触发器
            self.fts_enabled = ensure_fts_schema(self._local_engine)

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
        # FTS5 BM25 腿（W5-4）：local 模式在 _MemoryDB 内建；global 模式在此补一次
        # DDL（幂等，进程级只执行一次）。不可用时 False → BM25 腿自动关闭。
        if hasattr(self._db, "fts_enabled"):
            self.fts_enabled = bool(self._db.fts_enabled)
        else:
            self.fts_enabled = ensure_global_fts_schema()

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

    # ── 格式迁移：文件 → SQLite 由 migration.memory_to_sqlite_migrator 统一执行 ──

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
                            distilled_turns=int(profile_row.distilled_turns or 0),
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

    def mutate(self, fn):
        """读-改-写原子化：在 store 锁内 load → fn(data) → save，返回 fn 的返回值。

        FactManager 的单条写操作（add/remove/update/clear）原先为
        load→改→save 三步无锁序列，并发调用会相互覆盖（后写者整体覆盖
        先写者的修改）。收进同一锁段后序列化执行。
        """
        with self._lock:
            data = self.load_data()
            result = fn(data)
            self.save_data(data)
            return result

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
                    profile.distilled_turns = int(data.profile.distilled_turns or 0)
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
            pinned=fact.pinned,
            scope=getattr(fact, "scope", "global") or "global",
            group_id=getattr(fact, "group_id", "") or "",
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
            "pinned": bool(getattr(row, "pinned", False)),
            "scope": getattr(row, "scope", "global") or "global",
            "group_id": getattr(row, "group_id", "") or "",
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

    # --- FTS5 BM25 检索（W5-4 两路召回的 BM25 腿） ---

    def _sync_fts_scope(self, session) -> int:
        """检索前按需同步：本作用域 (owner_key, conversation_id) 事实集合
        与影子 FTS 行做 diff（新增 / 内容变更 / 已删除），只同步差异行。

        Returns:
            同步的行数（0 = 影子索引已最新）。
        """
        from sqlalchemy import func, select, text

        live_rows = session.execute(
            select(MemoryFact.id, MemoryFact.content).where(
                MemoryFact.owner_key == self._owner_key,
                MemoryFact.conversation_id == self._conversation_id,
            )
        ).all()
        live: dict[str, str] = {fid: content or "" for fid, content in live_rows}

        indexed_rows = session.execute(
            text(
                f"SELECT fact_id, content FROM {_FTS_TABLE} "
                "WHERE owner_key = :o AND conversation_id = :c"
            ),
            {"o": self._owner_key, "c": self._conversation_id},
        ).all()
        indexed: dict[str, str] = {fid: content or "" for fid, content in indexed_rows}

        stale_ids = [fid for fid in indexed if fid not in live or indexed[fid] != _fts_index_text(live[fid])]
        new_rows = [
            (fid, content) for fid, content in live.items()
            if fid not in indexed or indexed[fid] != _fts_index_text(content)
        ]
        if not stale_ids and not new_rows:
            return 0

        for fid in stale_ids:
            session.execute(
                text(f"DELETE FROM {_FTS_TABLE} WHERE fact_id = :f"), {"f": fid}
            )
        for fid, content in new_rows:
            session.execute(
                text(
                    f"INSERT INTO {_FTS_TABLE}(content, fact_id, owner_key, conversation_id) "
                    "VALUES (:content, :fid, :o, :c)"
                ),
                {
                    "content": _fts_index_text(content),
                    "fid": fid,
                    "o": self._owner_key,
                    "c": self._conversation_id,
                },
            )
        session.commit()
        return len(stale_ids) + len(new_rows)

    def _ensure_fts_enabled(self) -> bool:
        """fts_enabled 为 False 时惰性重试一次 DDL 并自愈。

        场景：全局库首个 MemoryStore 初始化早于建表（如测试未先跑 init_db、
        或生产侧装配顺序异常）时，ensure_global_fts_schema 曾失败但引擎实例
        已缓存；表就绪后的首次 BM25 检索经此处重试恢复 BM25 腿。
        """
        if getattr(self, "fts_enabled", False):
            return True
        if self._db._local_engine is not None:
            self.fts_enabled = ensure_fts_schema(self._db._local_engine)
        else:
            self.fts_enabled = ensure_global_fts_schema()
        return bool(self.fts_enabled)

    def search_facts_bm25(self, query: str, k: int = 10) -> list[tuple[str, float]]:
        """BM25 全文召回本 store 作用域的事实，返回 [(fact_id, bm25_rank)]。

        bm25() 值越小越相关（FTS5 约定），调用方按顺序使用即可（RRF 只看排名）。
        FTS5 不可用 / 查询无可匹配词项 / 查询异常时返回 []（由上层融合逻辑
        自动落到向量腿或关键词兜底，不抛异常）。
        """
        if not self._ensure_fts_enabled():
            return []
        match_expr = build_fts_match_query(query)
        if not match_expr:
            return []
        with self._lock:
            try:
                from sqlalchemy import text

                with self._db.session() as session:
                    self._sync_fts_scope(session)
                    rows = session.execute(
                        text(
                            f"SELECT fact_id, bm25({_FTS_TABLE}) AS rank FROM {_FTS_TABLE} "
                            f"WHERE {_FTS_TABLE} MATCH :match "
                            "AND owner_key = :o AND conversation_id = :c "
                            "ORDER BY rank LIMIT :k"
                        ),
                        {
                            "match": match_expr,
                            "o": self._owner_key,
                            "c": self._conversation_id,
                            "k": int(k),
                        },
                    ).all()
                    return [(str(fid), float(rank)) for fid, rank in rows]
            except Exception as e:
                logger.warning(f"[Memory] FTS5 BM25 search failed (degrade): {e}")
                return []

    def close(self) -> None:
        self._db.close()


def query_stored_users(session: Session) -> list[dict]:
    """从 SQLite 中直接聚合所有 users:* 轨道的信息（淘汰旧文件扫描）。
    
    返回包含 user_key, name, static_facts_count, fact_count, private_fact_count, updated_at 等字典列表。
    """
    from sqlalchemy import func

    profiles = session.execute(
        select(MemoryProfile).where(
            MemoryProfile.owner_key.like("users:%"),
            MemoryProfile.conversation_id == "",
        )
    ).scalars().all()
    profile_map = {p.owner_key: p for p in profiles}

    fact_counts = dict(
        session.execute(
            select(MemoryFact.owner_key, func.count())
            .where(
                MemoryFact.owner_key.like("users:%"),
                MemoryFact.is_latest == 1,
            )
            .group_by(MemoryFact.owner_key)
        ).all()
    )

    private_counts = dict(
        session.execute(
            select(MemoryFact.owner_key, func.count())
            .where(
                MemoryFact.owner_key.like("users:%"),
                MemoryFact.scope == "private",
                MemoryFact.is_latest == 1,
            )
            .group_by(MemoryFact.owner_key)
        ).all()
    )

    all_keys = sorted(set(profile_map.keys()) | set(fact_counts.keys()))
    results = []
    for o_key in all_keys:
        user_key = o_key[len("users:"):]
        prof = profile_map.get(o_key)
        name = prof.name if prof else ""
        static_facts = prof.static_facts if prof and prof.static_facts else []
        updated_at = prof.updated_at if prof else ""

        platform = ""
        if "_" in user_key:
            parts = user_key.split("_")
            if len(parts) >= 2 and parts[1] in ("onebot", "official", "gewechat", "itchat", "comwechat"):
                platform = f"{parts[0]}_{parts[1]}"
            else:
                platform = parts[0]

        results.append({
            "user_key": user_key,
            "name": name or user_key,
            "platform": platform,
            "fact_count": fact_counts.get(o_key, 0),
            "private_fact_count": private_counts.get(o_key, 0),
            "static_facts_count": len(static_facts),
            "updated_at": updated_at,
        })
    return results


def query_stored_groups(session: Session) -> list[dict]:
    """从 SQLite 中直接聚合所有 groups:* 轨道的信息。"""
    from sqlalchemy import func

    profiles = session.execute(
        select(MemoryProfile).where(
            MemoryProfile.owner_key.like("groups:%"),
            MemoryProfile.conversation_id == "",
        )
    ).scalars().all()
    profile_map = {p.owner_key: p for p in profiles}

    fact_counts = dict(
        session.execute(
            select(MemoryFact.owner_key, func.count())
            .where(
                MemoryFact.owner_key.like("groups:%"),
                MemoryFact.is_latest == 1,
            )
            .group_by(MemoryFact.owner_key)
        ).all()
    )

    all_keys = sorted(set(profile_map.keys()) | set(fact_counts.keys()))
    results = []
    for o_key in all_keys:
        group_key = o_key[len("groups:"):]
        prof = profile_map.get(o_key)
        name = prof.name if prof else ""
        updated_at = prof.updated_at if prof else ""

        platform = ""
        if "_" in group_key:
            parts = group_key.split("_")
            if len(parts) >= 2 and parts[1] in ("onebot", "official", "gewechat", "itchat", "comwechat"):
                platform = f"{parts[0]}_{parts[1]}"
            else:
                platform = parts[0]

        results.append({
            "group_key": group_key,
            "name": name or group_key,
            "platform": platform,
            "fact_count": fact_counts.get(o_key, 0),
            "updated_at": updated_at,
        })
    return results
