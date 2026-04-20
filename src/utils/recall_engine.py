"""记忆召回引擎。

实现 2026 顶级 RAG 检索流水线：
1. 并行 BM25（FTS5）+ 向量余弦相似度搜索
2. RRF 倒数排名融合
3. MMR 最大边际相关性重排序
4. 时间语义衰减（TSM 指数衰减）
5. 置信度过滤
6. 自适应记忆优先级（AdaMem）

优化特性：
- 批量查询替换 N+1 查询
- 真正的并行搜索（线程池）
- RRF 分数归一化
- 完整集成 AdaMem 优先级计算
"""

from __future__ import annotations

import concurrent.futures
from datetime import datetime, timedelta
from typing import Optional

import numpy as np

from src.config.settings import get_settings
from src.utils.datetime_utils import now_beijing
from src.utils.logger import get_logger

logger = get_logger()


def vector_to_blob(vector: np.ndarray) -> bytes:
    """将 numpy 向量转换为 BLOB 字节数据。

    Args:
        vector: numpy 数组。

    Returns:
        字节数据。
    """
    return vector.astype(np.float32).tobytes()


def blob_to_vector(blob_data: bytes) -> np.ndarray:
    """将 BLOB 字节数据转换为 numpy 向量。

    Args:
        blob_data: 字节数据。

    Returns:
        numpy 数组。
    """
    return np.frombuffer(blob_data, dtype=np.float32).copy()


def rrf_fusion(
    bm25_results: list[tuple[int, float]],
    vector_results: list[tuple[int, float]],
    k: int = 60,
) -> dict[int, float]:
    """RRF 倒数排名融合算法。

    基于 Reciprocal Rank Fusion 论文实现，
    无需归一化，直接使用排名的倒数加权。

    Args:
        bm25_results: BM25 搜索结果 [(chunk_id, score), ...]。
        vector_results: 向量搜索结果 [(chunk_id, score), ...]。
        k: RRF 常数，默认 60。

    Returns:
        {chunk_id: rrf_score} 字典。
    """
    fused_scores: dict[int, float] = {}

    for rank, (chunk_id, _) in enumerate(bm25_results, start=1):
        fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + 1.0 / (k + rank)

    for rank, (chunk_id, _) in enumerate(vector_results, start=1):
        fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + 1.0 / (k + rank)

    return fused_scores


def normalize_scores(scores: dict[int, float]) -> dict[int, float]:
    """分数归一化到 [0, 1] 区间。

    Args:
        scores: {chunk_id: score} 分数字典。

    Returns:
        归一化后的 {chunk_id: normalized_score} 字典。
    """
    if not scores:
        return {}
    max_score = max(scores.values())
    if max_score < 1e-10:
        return {k: 0.0 for k in scores}
    return {k: v / max_score for k, v in scores.items()}


def mmr_rerank(
    candidates: list[tuple[int, float]],
    embeddings: dict[int, np.ndarray],
    query_vector: np.ndarray,
    lambda_param: float = 0.5,
    top_k: int = 10,
) -> list[tuple[int, float]]:
    """最大边际相关性重排序。

    平衡相关性和多样性，避免返回内容过于相似的记忆。

    Args:
        candidates: 候选结果 [(chunk_id, score), ...]。
        embeddings: {chunk_id: vector} 向量字典。
        query_vector: 查询向量。
        lambda_param: 相关性/多样性平衡参数，0~1。
        top_k: 返回数量。

    Returns:
        重排序后的 [(chunk_id, score), ...] 列表。
    """
    if not candidates:
        return []

    selected: list[tuple[int, float]] = []
    remaining = list(candidates)

    query_norm = np.linalg.norm(query_vector)
    if query_norm < 1e-10:
        return candidates[:top_k]

    while len(selected) < top_k and remaining:
        best_idx = 0
        best_score = float("-inf")

        for i, (chunk_id, relevance) in enumerate(remaining):
            vec = embeddings.get(chunk_id)
            if vec is None:
                continue

            vec_norm = np.linalg.norm(vec)
            if vec_norm < 1e-10:
                continue

            sim_to_query = float(np.dot(query_vector, vec) / (query_norm * vec_norm))

            max_sim_to_selected = 0.0
            for sel_id, _ in selected:
                sel_vec = embeddings.get(sel_id)
                if sel_vec is None:
                    continue
                sel_norm = np.linalg.norm(sel_vec)
                if sel_norm < 1e-10:
                    continue
                sim = float(np.dot(vec, sel_vec) / (vec_norm * sel_norm))
                max_sim_to_selected = max(max_sim_to_selected, sim)

            mmr_score = (
                lambda_param * sim_to_query
                - (1 - lambda_param) * max_sim_to_selected
            )
            adjusted_score = relevance * 0.3 + mmr_score * 0.7

            if adjusted_score > best_score:
                best_score = adjusted_score
                best_idx = i

        if best_idx < len(remaining):
            selected.append(remaining.pop(best_idx))
        else:
            break

    return selected


def apply_time_decay(
    scores: dict[int, float],
    created_times: dict[int, datetime],
    half_life_days: float = 30.0,
) -> dict[int, float]:
    """时间语义衰减（TSM）。

    基于指数衰减函数，半衰期越短，旧记忆衰减越快。
    参考 TSM（Time-Semantic Memory）论文。

    Args:
        scores: {chunk_id: score} 分数字典。
        created_times: {chunk_id: created_at} 时间字典。
        half_life_days: 半衰期天数，默认 30 天。

    Returns:
        衰减后的 {chunk_id: score} 字典。
    """
    now = now_beijing()
    if now.tzinfo is not None:
        now = now.replace(tzinfo=None)
    decayed: dict[int, float] = {}

    for chunk_id, score in scores.items():
        created_at = created_times.get(chunk_id)
        if created_at is None:
            decayed[chunk_id] = score
            continue

        if created_at.tzinfo is not None:
            created_at = created_at.replace(tzinfo=None)

        delta_days = (now - created_at).total_seconds() / 86400.0
        decay_factor = 2.0 ** (-delta_days / half_life_days)
        decayed[chunk_id] = score * decay_factor

    return decayed


def compute_adaptive_memory_score(
    chunk_id: int,
    base_score: float,
    confidence: float,
    merge_count: int,
    access_count: int,
    entity_count: int = 0,
    recency: float = 1.0,
) -> float:
    """自适应记忆优先级计算（AdaMem）。

    综合考虑基础分数、置信度、合并次数、访问频率、实体关联数和新鲜度，
    动态调整记忆优先级。

    Args:
        chunk_id: Chunk ID。
        base_score: 基础召回分数。
        confidence: 置信度。
        merge_count: 合并次数。
        access_count: 访问次数。
        entity_count: 关联实体数量。
        recency: 新鲜度因子（0~1）。

    Returns:
        自适应优先级分数。
    """
    weights = {
        "base": 0.3,
        "confidence": 0.25,
        "merge_count": 0.15,
        "access_count": 0.15,
        "entity_count": 0.1,
        "recency": 0.05,
    }

    merge_factor = min(1.0, merge_count / 10.0)
    access_factor = min(1.0, access_count / 5.0)
    entity_factor = min(1.0, entity_count / 3.0)

    adaptive_score = (
        weights["base"] * base_score
        + weights["confidence"] * confidence
        + weights["merge_count"] * merge_factor
        + weights["access_count"] * access_factor
        + weights["entity_count"] * entity_factor
        + weights["recency"] * recency
    )

    return adaptive_score


class RecallEngine:
    """记忆召回引擎。

    实现完整的五步召回流水线：
    1. 并行 BM25 + 向量搜索
    2. RRF 融合
    3. MMR 重排序
    4. 时间衰减
    5. 阈值过滤
    6. AdaMem 自适应优先级

    Attributes:
        chunk_dao: Chunk DAO 实例。
        embedding_dao: Embedding DAO 实例。
    """

    def __init__(self, chunk_dao, embedding_dao) -> None:
        self.chunk_dao = chunk_dao
        self.embedding_dao = embedding_dao
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

    def recall(
        self,
        agent_id: int,
        query: str,
        query_vector: np.ndarray,
        top_k: int = 10,
    ) -> list[tuple[int, float]]:
        """执行完整的召回流水线。

        Args:
            agent_id: Agent ID。
            query: 查询文本。
            query_vector: 查询向量。
            top_k: 返回数量。

        Returns:
            [(chunk_id, final_score), ...] 列表。
        """
        settings = get_settings()

        # 1. 并行执行 BM25 和向量搜索
        bm25_future = self._executor.submit(
            self._safe_bm25_search, agent_id, query
        )
        vector_future = self._executor.submit(
            self._safe_vector_search, agent_id, query_vector
        )

        bm25_results = bm25_future.result()
        vector_results = vector_future.result()

        if not bm25_results and not vector_results:
            return []

        # 2. RRF 融合 + 归一化
        fused_scores = rrf_fusion(
            bm25_results, vector_results, k=settings.memory_rrf_k
        )
        normalized_scores = normalize_scores(fused_scores)

        # 3. 准备候选集和批量加载
        candidate_ids = list(normalized_scores.keys())
        if not candidate_ids:
            return []

        # 批量加载向量
        embeddings = self.embedding_dao.get_vectors_by_chunk_ids(candidate_ids)
        if not embeddings:
            return []

        # 4. MMR 重排序
        candidates = sorted(
            normalized_scores.items(), key=lambda x: x[1], reverse=True
        )
        mmr_limit = min(top_k * 3, len(candidates))
        reranked = mmr_rerank(
            candidates[:mmr_limit], embeddings, query_vector,
            lambda_param=settings.memory_mmr_lambda,
            top_k=top_k * 2,
        )

        # 5. 时间衰减
        reranked_ids = [cid for cid, _ in reranked]
        created_times = self.chunk_dao.get_created_times(reranked_ids)
        decayed_scores = apply_time_decay(
            {cid: score for cid, score in reranked},
            created_times,
            half_life_days=settings.memory_half_life_days,
        )

        # 6. 批量获取统计信息（用于 AdaMem）
        chunk_stats = self.chunk_dao.get_chunk_stats(reranked_ids)

        # 7. AdaMem 自适应优先级
        adaptive_scores: dict[int, float] = {}
        for chunk_id, score in decayed_scores.items():
            stats = chunk_stats.get(chunk_id, {})
            adaptive_score = compute_adaptive_memory_score(
                chunk_id=chunk_id,
                base_score=score,
                confidence=stats.get("confidence", 1.0),
                merge_count=stats.get("merge_count", 0),
                access_count=stats.get("access_count", 0),
            )
            adaptive_scores[chunk_id] = adaptive_score

        # 8. 阈值过滤
        filtered = {k: v for k, v in adaptive_scores.items() 
                   if v > settings.memory_recall_threshold}

        # 9. 排序并返回 Top-K
        result = sorted(filtered.items(), key=lambda x: x[1], reverse=True)
        top_results = result[:top_k]

        # 10. 批量增加访问次数
        accessed_ids = [cid for cid, _ in top_results]
        self.chunk_dao.increment_access_counts(accessed_ids)

        return top_results

    def _safe_bm25_search(
        self, agent_id: int, query: str
    ) -> list[tuple[int, float]]:
        """安全执行 BM25 搜索，捕获异常。"""
        try:
            return self.chunk_dao.search_bm25(agent_id, query, limit=20)
        except Exception as e:
            logger.warning(f"BM25 搜索失败: {e}")
            return []

    def _safe_vector_search(
        self, agent_id: int, query_vector: np.ndarray
    ) -> list[tuple[int, float]]:
        """安全执行向量搜索，捕获异常。"""
        try:
            return self.embedding_dao.search_cosine_similarity(
                agent_id, query_vector, limit=20
            )
        except Exception as e:
            logger.warning(f"向量搜索失败: {e}")
            return []

    def shutdown(self) -> None:
        """关闭线程池。"""
        self._executor.shutdown(wait=True)
