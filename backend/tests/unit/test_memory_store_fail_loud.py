"""MemoryStore load 失败 fail-loud 回归测试（04 审查 P0-3）。

修复前行为：load 异常被吞 + 空 MemoryData 入缓存 → 后续任意
mutate/save_data 以空 facts 整轨 DELETE+INSERT 覆盖 → 该轨记忆全灭。

修复后行为：
- 读路径降级：load 失败返回空数据但不缓存（下次重试）
- 写路径拒绝：未成功加载状态下 mutate/save_data 抛 MemoryStoreLoadError
- 库恢复后重新加载成功 → 写路径自动解锁，原有数据完好
"""

import sqlite3

import pytest

from app.engines.memory.models import FactItem, MemoryData
from app.engines.memory.store import MemoryStore, MemoryStoreLoadError


@pytest.fixture
def store(tmp_path):
    """本地模式 store（路径在 DATA_DIR/memory 之外 → 独立 memory.db）。"""
    return MemoryStore(tmp_path / "track")


class _ExplodingDB:
    """模拟底层库故障：任何 session 打开即失败（损坏/锁死/IO 错误）。"""

    def session(self):
        raise sqlite3.OperationalError("database disk image is malformed")


def _seed_fact(store: MemoryStore, content: str) -> None:
    store.mutate(lambda d: d.facts.append(
        FactItem(content=content, category="preference", confidence=0.9)
    ))


def _simulate_broken_db_on_fresh_start(store: MemoryStore):
    """把 store 置于 P0-3 现场后端持有故障库的状态。

    P0-3 的事故现场是"进程启动后首次 load 即失败"（无可用缓存）：
    预写数据后需清掉 _cache 再换故障 DB，等价于重启后首连即损坏。
    返回真实 _MemoryDB 供恢复用。
    """
    real_db = store._db
    store._cache = None
    store._db = _ExplodingDB()
    return real_db


def test_load_failure_does_not_cache_empty_data(store):
    _seed_fact(store, "keep me")
    real_db = _simulate_broken_db_on_fresh_start(store)
    try:
        data1 = store.load_data()
        data2 = store.load_data()
        # 读路径降级为空数据，但不缓存：两次返回各自新建的空对象
        assert data1.facts == [] and data2.facts == []
        assert data1 is not data2
        assert store._cache is None
    finally:
        store._db = real_db

    # 库恢复后重新加载拿到真实数据（未发生空数据污染）
    recovered = store.load_data()
    assert [f.content for f in recovered.facts] == ["keep me"]


def test_load_failure_blocks_destructive_writes(store):
    _seed_fact(store, "keep me")
    real_db = _simulate_broken_db_on_fresh_start(store)
    try:
        # load 一次置失败标记（模拟故障期间的读访问）
        store.load_data()
        with pytest.raises(MemoryStoreLoadError):
            store.mutate(lambda d: d.facts.clear())
        with pytest.raises(MemoryStoreLoadError):
            store.save_data(MemoryData())
    finally:
        store._db = real_db

    # 拒绝写入期间底层数据未被破坏
    assert [f.content for f in store.load_data().facts] == ["keep me"]


def test_write_unlocks_after_recovery(store):
    _seed_fact(store, "keep me")
    real_db = _simulate_broken_db_on_fresh_start(store)
    try:
        store.load_data()
        with pytest.raises(MemoryStoreLoadError):
            store.mutate(lambda d: d.facts.append(
                FactItem(content="during outage", category="context", confidence=0.5)
            ))
    finally:
        store._db = real_db

    # 重新加载成功 → 写路径解锁，新增事实与原有事实共存
    store.mutate(lambda d: d.facts.append(
        FactItem(content="after recovery", category="context", confidence=0.8)
    ))
    contents = [f.content for f in store.load_data().facts]
    assert contents == ["keep me", "after recovery"]


def test_write_blocked_only_until_successful_load(store):
    """从未失败过的 store（正常缓存命中路径）写入不受影响。"""
    _seed_fact(store, "normal")
    # 缓存命中（_cache 非 None）→ 守卫不触发
    store.mutate(lambda d: d.facts.append(
        FactItem(content="normal-2", category="context", confidence=0.8)
    ))
    assert [f.content for f in store.load_data().facts] == ["normal", "normal-2"]
