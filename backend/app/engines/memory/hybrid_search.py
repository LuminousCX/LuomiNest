"""两路召回 + RRF 融合检索（W5-4，自研演进路线，Mem0 v3 多信号检索模式）。

- 向量腿：engine.vector_retrieve（自研向量索引，embedding 在线时可用）
- BM25 腿：MemoryStore.search_facts_bm25（SQLite FTS5 触发器同步影子索引，
  零网络依赖，解决「无外网 embedding 记忆检索不可用」）
- 融合：Reciprocal Rank Fusion（k=60），两腿排名倒数求和，无需分数归一化；
- 降级链：embedding 异常 → 自动纯 BM25；BM25 无可匹配词项/FTS5 不可用 →
  向量单腿；两者皆不可用 → 关键词 Jaccard 兜底（复用 fact_manager 分词）。

图谱腿（GraphRAG）按修改书约定后置到独立里程碑。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime

from loguru import logger

from app.core.utils import utc_now_dt

from .fact_manager import _extract_content_words
from .models import FactItem
from .vector_store import ScoredFact

# RRF 常数（论文推荐值 60：平滑排名差异，头部结果权重不至于碾压）
RRF_K = 60

# 模式常量（供工具/端点在响应中标注召回路径）
MODE_HYBRID = "hybrid"
MODE_VECTOR = "vector"
MODE_BM25 = "bm25"
MODE_KEYWORD = "keyword"


@dataclass
class HybridSearchMeta:
    """一次混合检索的召回路径元信息。"""

    mode: str = MODE_HYBRID
    vector_ok: bool = True
    bm25_ok: bool = True
    note: str = ""


def _rrf_fuse(ranked_legs: list[list[tuple[str, float]]], k: int) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion：score(d) = Σ_legs 1/(RRF_K + rank_leg(d))。

    各腿输入已按相关度降序（rank 从 1 开始）；只取各腿前 k 名参与融合。
    返回按融合分降序的前 k 名 [(fact_id, rrf_score)]。
    """
    scores: dict[str, float] = {}
    for leg in ranked_legs:
        for rank, (fact_id, _raw) in enumerate(leg[:k], start=1):
            scores[fact_id] = scores.get(fact_id, 0.0) + 1.0 / (RRF_K + rank)
    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return fused[:k]


def _keyword_fallback(
    facts: list[FactItem], query: str, k: int
) -> list[ScoredFact]:
    """关键词 Jaccard 兜底（向量与 BM25 双双不可用时，保持检索可用）。"""
    q_words = _extract_content_words(query.casefold())
    if not q_words:
        return []
    scored: list[tuple[str, float, str]] = []
    for f in facts:
        f_words = _extract_content_words(f.content.casefold())
        if not f_words:
            continue
        overlap = len(q_words & f_words) / max(len(q_words | f_words), 1)
        if overlap > 0:
            scored.append((f.id, overlap, f.category))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [ScoredFact(fact_id=fid, score=s, category=cat) for fid, s, cat in scored[:k]]


def filter_valid_facts(
    facts: list[FactItem],
    category: str | None = None,
    allowed_scopes: set[str] | None = None,
) -> list[FactItem]:
    """检索结果统一闸门：is_latest + 分类 + 作用域 + 未过期。

    allowed_scopes 为 None 表示不限制（owner 轨全量）；群/用户轨防泄露由
    调用方传入 {"global", "group"} 收窄（严禁 private 出群，§8.5.10）。
    """
    now = utc_now_dt()
    valid: list[FactItem] = []
    cat_lower = (category or "").strip().lower()
    for fact in facts:
        if not fact.is_latest:
            continue
        if cat_lower and fact.category.lower() != cat_lower:
            continue
        if allowed_scopes is not None and getattr(fact, "scope", "global") not in allowed_scopes:
            continue
        if not fact.pinned and fact.expires_at:
            try:
                exp_time = datetime.fromisoformat(fact.expires_at.replace("Z", "+00:00"))
                if exp_time <= now:
                    continue
            except (ValueError, TypeError):
                pass
        valid.append(fact)
    return valid


async def hybrid_search(
    engine,
    query: str,
    k: int = 5,
    category: str | None = None,
    allowed_scopes: set[str] | None = None,
) -> tuple[list[ScoredFact], HybridSearchMeta]:
    """对单个记忆引擎执行「向量 + BM25」两路召回与 RRF 融合。

    Args:
        engine: MemoryEngine（owner/users/groups 任一轨）
        query: 检索查询
        k: 返回条数上限
        category: 记忆分类过滤（可选）
        allowed_scopes: 作用域白名单（None=不限；防泄露场景传 {"global","group"}）

    Returns:
        (ScoredFact 列表, HybridSearchMeta 召回路径元信息)
    """
    fetch_k = max(k * 3, 15)

    # ── 腿 1：向量语义召回（embedding 不可用时降级，不阻断） ──
    vector_ok = True
    vector_leg: list[ScoredFact] = []
    try:
        vector_leg = await engine.vector_retrieve(query, k=fetch_k)
    except Exception as e:
        vector_ok = False
        logger.warning(f"[HybridSearch] Vector leg failed (degrade to BM25): {e}")

    # ── 腿 2：SQLite FTS5 BM25 召回（同步 SQLite 读，to_thread 执行） ──
    # search_facts_bm25 内部自带惰性自愈（DDL 曾失败的场景会在检索时重试）；
    # 调用后按 store 实际 fts_enabled 状态判定腿可用性。
    bm25_ok = True
    bm25_leg: list[tuple[str, float]] = []
    try:
        bm25_leg = await asyncio.to_thread(engine._store.search_facts_bm25, query, fetch_k)
        if not getattr(engine._store, "fts_enabled", False):
            bm25_ok = False  # FTS5 腿未启用（运行时缺 FTS5 或显式关闭）
    except Exception as e:
        bm25_ok = False
        logger.warning(f"[HybridSearch] BM25 leg failed: {e}")

    # ── 统一闸门过滤（两腿共用同一有效事实集合，防过期/分类/泄露穿透） ──
    data = await asyncio.to_thread(engine.load_data)
    valid = filter_valid_facts(data.facts, category=category, allowed_scopes=allowed_scopes)
    valid_map = {f.id: f for f in valid}
    vec_ranked = [(s.fact_id, float(s.score)) for s in vector_leg if s.fact_id in valid_map]
    bm_ranked = [(fid, rank) for fid, rank in bm25_leg if fid in valid_map]

    meta = HybridSearchMeta(vector_ok=vector_ok, bm25_ok=bm25_ok)

    # ── 降级决策链（mode 标注实际生效的召回路径） ──
    if vec_ranked and bm_ranked and vector_ok and bm25_ok:
        meta.mode = MODE_HYBRID
        return _to_scored(_rrf_fuse([vec_ranked, bm_ranked], k), valid_map), meta

    if bm_ranked and not vector_ok:
        # 核心降级承诺：embedding 异常 → 自动纯 BM25
        meta.mode = MODE_BM25
        meta.note = "embedding_failed_pure_bm25"
        return _to_scored(bm_ranked[:k], valid_map), meta

    if vec_ranked:
        meta.mode = MODE_VECTOR
        meta.note = "bm25_no_match" if bm25_ok else "bm25_unavailable"
        return _to_scored(vec_ranked[:k], valid_map), meta

    if bm_ranked:
        meta.mode = MODE_BM25
        meta.note = "vector_no_match" if vector_ok else "embedding_failed_pure_bm25"
        return _to_scored(bm_ranked[:k], valid_map), meta

    # 两腿皆空：腿不可用（embedding 挂 / FTS5 缺失）时关键词兜底，否则真空结果
    if not vector_ok or not bm25_ok:
        meta.mode = MODE_KEYWORD
        meta.note = "embedding_failed_and_bm25_unavailable" if not vector_ok and not bm25_ok else (
            "vector_failed_keyword_fallback" if not vector_ok else "bm25_failed_keyword_fallback"
        )
        return _keyword_fallback(valid, query, k), meta

    meta.note = "legs_empty"
    return [], meta


def _to_scored(ranked: list[tuple[str, float]], valid_map: dict[str, FactItem]) -> list[ScoredFact]:
    """融合排名 → ScoredFact（category 反查自有效事实表）。"""
    out: list[ScoredFact] = []
    for fid, score in ranked:
        fact = valid_map.get(fid)
        if fact is None:
            continue
        out.append(ScoredFact(fact_id=fid, score=float(score), category=fact.category))
    return out
