"""VectorStore 回归测试（to_thread 化后：临时 SQLite + 伪嵌入，零 HTTP）。

覆盖：
- add 自动向量化 + 单行落库；新实例冷启动 _load（to_thread 路径）从 SQLite 恢复索引
- search：余弦降序、min_score 过滤、top_k 截断、category 索引过滤
- dedup_check：同类别相似命中 / 跨类别隔离 / 低相似不判重
- remove：内存索引与 SQLite 行同步删除
- 边界：空库检索、零向量余弦为 0、显式携带向量不再触发 embed
"""

import numpy as np
import pytest

from app.engines.memory.vector_store import VectorEntry, VectorStore


class FakeEmbeddingProvider:
    """确定性伪嵌入：关键词命中 → 单位基向量（同词同向、异词正交）。"""

    dim = 8
    _BASIS = {"咖啡": 0, "天气": 1, "tea": 2}

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vec = np.zeros(self.dim, dtype=np.float32)
            for token, idx in self._BASIS.items():
                if token in text:
                    vec[idx] = 1.0
            if not vec.any():
                vec[3] = 1.0  # 未命中词表时的兜底方向
            vectors.append(vec.tolist())
        return vectors


class CountingProvider:
    """包装 provider，统计 embed 调用次数。"""

    def __init__(self, inner: FakeEmbeddingProvider):
        self._inner = inner
        self.calls = 0
        self.dim = inner.dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return await self._inner.embed(texts)


@pytest.fixture
def vec_dir(tmp_path):
    # 生产中 vectors 目录由记忆目录树预先创建，_MemoryDB 本地模式不会自建目录
    d = tmp_path / "vectors"
    d.mkdir()
    return d


@pytest.fixture
def provider():
    return FakeEmbeddingProvider()


async def test_add_persists_and_cold_load_restores(vec_dir, provider):
    store = VectorStore(vec_dir, provider)
    entry = VectorEntry(fact_id="f1", content="我喜欢咖啡", category="preference")
    await store.add(entry)

    # add 自动向量化并写入内存索引
    assert entry.vector.size == provider.dim
    assert "f1" in store._cache
    store.close()

    # 新实例冷启动：从 SQLite 读回（to_thread 路径），无需重新 embed
    store2 = VectorStore(vec_dir, provider)
    hits = await store2.search("咖啡")
    assert [h.fact_id for h in hits] == ["f1"]
    assert hits[0].score == pytest.approx(1.0)
    assert hits[0].category == "preference"
    store2.close()


async def test_search_orders_filters_and_truncates(vec_dir, provider):
    store = VectorStore(vec_dir, provider)
    await store.add(VectorEntry(fact_id="coffee", content="我喜欢咖啡", category="preference"))
    await store.add(VectorEntry(fact_id="weather", content="今天天气不错", category="context"))

    # 与 query 同词的事实排第一（分数 1.0），正交向量得 0 分垫底
    hits = await store.search("咖啡", k=10)
    assert [h.fact_id for h in hits] == ["coffee", "weather"]
    assert hits[0].score == pytest.approx(1.0)

    # min_score 过滤正交项
    hits = await store.search("咖啡", k=10, min_score=0.5)
    assert [h.fact_id for h in hits] == ["coffee"]

    # top_k 截断
    hits = await store.search("咖啡", k=1)
    assert len(hits) == 1

    # category 过滤：候选集与类别索引取交集
    assert [h.fact_id for h in await store.search("咖啡", k=10, category="preference", min_score=0.5)] == ["coffee"]
    assert await store.search("咖啡", k=10, category="context", min_score=0.5) == []


async def test_dedup_check_scoped_by_category(vec_dir, provider):
    store = VectorStore(vec_dir, provider)
    await store.add(VectorEntry(fact_id="f-coffee", content="我喜欢咖啡", category="preference"))

    # 同类别 + 相同内容：命中（余弦 1.0 ≥ 0.85）
    assert await store.dedup_check("我喜欢咖啡", "preference") == "f-coffee"
    # 相同内容但不同类别：类别索引隔离，不判重
    assert await store.dedup_check("我喜欢咖啡", "context") is None
    # 同类别但内容无关（正交向量得 0 分，低于阈值）：不判重
    assert await store.dedup_check("今天天气不错", "preference") is None


async def test_remove_deletes_from_memory_and_sqlite(vec_dir, provider):
    store = VectorStore(vec_dir, provider)
    await store.add(VectorEntry(fact_id="f1", content="我喜欢咖啡", category="preference"))

    await store.remove("f1")
    assert await store.search("咖啡") == []
    store.close()

    # SQLite 行已删除，冷启动实例不再可见
    store2 = VectorStore(vec_dir, provider)
    assert await store2.search("咖啡") == []
    store2.close()


async def test_empty_store_and_zero_vector_edges(vec_dir, provider):
    store = VectorStore(vec_dir, provider)

    # 空库检索 / 判重
    assert await store.search("咖啡") == []
    assert await store.dedup_check("咖啡", "preference") is None

    # 零向量余弦恒为 0（除零保护）
    zero = np.zeros(provider.dim, dtype=np.float32)
    ones = np.ones(provider.dim, dtype=np.float32)
    assert VectorStore._cosine(zero, ones) == 0.0

    # 显式携带向量的 entry：add 不再触发 embed（零 embed 调用），检索按分数过滤
    counting = CountingProvider(provider)
    zero_dir = vec_dir.parent / "vectors-zero"
    zero_dir.mkdir()
    store2 = VectorStore(zero_dir, counting)
    await store2.add(VectorEntry(fact_id="zero", content="咖啡", category="preference", vector=zero))
    assert counting.calls == 0

    hits = await store2.search("咖啡", min_score=0.0)
    assert [h.fact_id for h in hits] == ["zero"]
    assert hits[0].score == 0.0
    assert await store2.search("咖啡", min_score=0.1) == []
    store2.close()
