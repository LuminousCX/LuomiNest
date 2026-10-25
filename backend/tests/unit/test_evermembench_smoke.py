"""EverMemBench smoke（2026-10-25 拍板⑤立项，G0-E 绑定批）。

定位：检索质量的回归门槛 smoke——不是完整评测集（EverMemBench 正式数据接入
后置 G1，随 L1 daily 向量化一起做）。验收口径：混合检索主路径在「中文事实、
语义改述、跨天追问」三类查询上保持可召回；embedding 离线时 BM25 单腿降级
承诺不破（G0-E 切注入主路径后，注入质量不高于此门槛即回归）。

洁净室说明：只借"评测驱动"思想，不抄任何基准数据/代码。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.engines.memory.hybrid_search import hybrid_search
from app.engines.memory.memory_engine import MemoryEngine
from app.engines.memory.models import FactItem


@pytest.fixture
def bench_engine():
    """临时目录独立库引擎（local 模式，FTS5 影子索引在位）。"""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        engine = MemoryEngine(storage_path=Path(tmpdir))
        # 事实语料：覆盖偏好/事实/目标/关系四类，含时间与数字锚点
        corpus = [
            FactItem(content="主人喜欢喝美式咖啡，每天早晨都要来一杯", category="preference", confidence=0.9),
            FactItem(content="用户的生日是3月12日，记得准备蛋糕", category="context", confidence=0.95),
            FactItem(content="主人正在筹备敦煌旅行，计划住四天", category="goal", confidence=0.85),
            FactItem(content="用户养了一只叫团子的橘猫，今年两岁", category="context", confidence=0.9),
            FactItem(content="主人对花生过敏，外卖备注要写清楚", category="preference", confidence=0.95),
            FactItem(content="用户的妹妹在上高中，周末会来家里吃饭", category="relationship", confidence=0.8),
        ]
        for f in corpus:
            engine.add_fact(f)
        yield engine


# (查询, 期望命中事实的关键词) —— 语义改述类查询检验 BM25 分词 + 融合排序
_SMOKE_CASES = [
    ("早上喝什么咖啡", "美式咖啡"),
    ("生日什么时候", "生日"),
    ("旅游计划去哪里", "敦煌"),
    ("养的宠物叫什么", "橘猫"),
    ("吃什么东西会过敏", "花生"),
]


@pytest.mark.asyncio
async def test_hybrid_main_path_recall(bench_engine):
    """主路径：混合检索三类查询 ≥80% 命中（smoke 门槛 5 中 4）。"""
    hits = 0
    for query, expect in _SMOKE_CASES:
        results, meta = await hybrid_search(bench_engine, query, k=5)
        contents = []
        for r in results:
            fact = next(
                (f for f in bench_engine.load_data().facts if f.id == r.fact_id), None,
            )
            if fact:
                contents.append(fact.content)
        if any(expect in c for c in contents):
            hits += 1
    assert hits >= 4, f"EverMemBench smoke 门槛未达：{hits}/{len(_SMOKE_CASES)} 命中"


@pytest.mark.asyncio
async def test_bm25_degrade_promise(bench_engine):
    """降级承诺：embedding 腿离线时纯 BM25 仍可召回（G0-E 注入主路径不可断）。"""
    async def _offline(query, k=10):
        raise RuntimeError("embedding offline (smoke)")

    bench_engine.vector_retrieve = _offline
    results, meta = await hybrid_search(bench_engine, "对花生过敏要注意什么", k=5)
    assert meta.mode == "bm25"
    facts = {f.id: f.content for f in bench_engine.load_data().facts}
    assert len(results) >= 1
    assert any("花生" in facts.get(r.fact_id, "") for r in results)


@pytest.mark.asyncio
async def test_injection_main_path_uses_hybrid(bench_engine):
    """G0-E 接线：retrieve_relevant_ids 返回的相关事实 ID 用于注入排序——
    相关事实必须排在无关事实之前（context_builder 的 vector_relevance 排序）。"""
    relevant_ids = await bench_engine.retrieve_relevant_ids("主人喝什么咖啡", k=3)
    assert relevant_ids, "混合召回不应为空"

    ctx = await asyncio_build_ctx(bench_engine, query="主人喝什么咖啡", relevant_ids=relevant_ids)
    coffee_pos = ctx.find("美式咖啡")
    cat_pos = ctx.find("橘猫")
    assert coffee_pos != -1
    # 相关事实（咖啡）应先于无关事实（猫）出现或猫不在预算内
    assert cat_pos == -1 or coffee_pos < cat_pos


async def asyncio_build_ctx(engine, query, relevant_ids):
    """经 build_context_sync（注入主路径同款）组装上下文文本。"""
    import asyncio

    return await asyncio.to_thread(
        engine.build_context_sync,
        query=query,
        relevant_fact_ids=relevant_ids,
    )


@pytest.mark.asyncio
async def test_retrieve_ids_empty_query_safe(bench_engine):
    """空查询不触发检索，返回空集（不抛异常）。"""
    assert await bench_engine.retrieve_relevant_ids("") == set()
    assert await bench_engine.retrieve_relevant_ids("   ") == set()
