# -*- coding: utf-8 -*-
"""记忆系统性能基准（改进后 vs 改进前基线，同机对照）。

改进前基线为 2026-09-16 上午在改动前的代码上实测（同一台机器、同一
.venv），数据硬编码于 BASELINE 中；本脚本在改动后的代码上重测同名指标，
并额外复刻旧 dedup_and_add 算法（逐条 dedup_check + batch_add 重嵌入）
在同一新存储层上跑对照——两者只差调用模式，对比公平。

网络 RTT 用 asyncio.sleep 模拟（无法打真实 API，已逐处标注）；
SQLite/CPU 指标全部为真实代码实测。

用法：cd backend && .venv/Scripts/python.exe scripts/memory_benchmark.py
"""
import asyncio
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

_TMP_DATA = tempfile.mkdtemp(prefix="lumi-bench-data-")
os.environ["LUOMINEST_DATA_DIR"] = _TMP_DATA
os.environ["DATABASE_URL"] = ""

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from loguru import logger  # noqa: E402
logger.remove()

# ── 改动前基线（2026-09-16 上午实测，改动前代码，同机同 venv） ─────────────
BASELINE = {
    "dedup_n30_rtt50": {"calls": 31, "texts": 60, "wall_ms": 1931.4},
    "dedup_n30_rtt200": {"calls": 31, "texts": 60, "wall_ms": 6330.8},
    "merge_100_50_ms": 130.41,
    "save_data_100_ms": 17.75,
    "load_cold_100_ms": 7.11,
    "rank_100_ms": 0.633,
    "rank_1000_ms": 4.901,
    "load_1000_vectors_ms": 28.14,
}

DIM = 1536


class RttBatchProvider:
    """批量协议伪嵌入：每文本确定性随机单位向量（互不相似，避免误判重），
    每次 embed() 计一次 HTTP 调用并模拟 RTT。"""

    def __init__(self, rtt_ms=0):
        self.rtt = rtt_ms / 1000.0
        self.calls = 0
        self.texts = 0

    @property
    def dim(self):
        return DIM

    async def embed(self, texts):
        self.calls += 1
        self.texts += len(texts)
        if self.rtt:
            await asyncio.sleep(self.rtt)
        out = []
        for t in texts:
            seed = int(hashlib.sha256(t.encode()).hexdigest()[:8], 16)
            rng = np.random.default_rng(seed)
            v = rng.standard_normal(DIM).astype(np.float32)
            out.append((v / np.linalg.norm(v)).tolist())
        return out


def make_facts(n):
    from app.engines.memory.models import FactItem
    return [
        FactItem(content=f"基准事实第{i}条：用户偏好的工具是示例软件{i}号", category="preference")
        for i in range(n)
    ]


def fresh(name):
    d = Path(tempfile.mkdtemp(prefix=f"lumi-bench-{name}-"))
    return d


# ── A. 向量索引：新实现 vs 旧算法复刻 ─────────────────────────────────────

async def bench_new(n, rtt_ms):
    from app.engines.memory.vector_manager import VectorSearchManager
    prov = RttBatchProvider(rtt_ms)
    tmp = fresh("new")
    try:
        mgr = VectorSearchManager("bench", prov, storage_path=tmp / "vectors", owner_key="b:owner")
        facts = make_facts(n)
        t0 = time.perf_counter()
        await mgr.dedup_and_add(facts)
        wall = (time.perf_counter() - t0) * 1000
        return {"calls": prov.calls, "texts": prov.texts, "wall_ms": wall,
                "indexed": len(mgr._store._cache)}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


async def bench_old_algo(n, rtt_ms):
    """复刻旧 dedup_and_add：逐条 dedup_check（每条 1 次 embed）+ batch_add
    重新 embed 一遍。存储层为新代码（对比只隔离调用模式差异）。"""
    from app.engines.memory.vector_manager import VectorSearchManager
    from app.engines.memory.vector_store import VectorEntry
    from app.engines.memory.models import FACT_SCOPE_CONVERSATION
    prov = RttBatchProvider(rtt_ms)
    tmp = fresh("old")
    try:
        mgr = VectorSearchManager("bench", prov, storage_path=tmp / "vectors", owner_key="b:owner")
        facts = make_facts(n)
        t0 = time.perf_counter()
        entries = []
        seen = {}
        for f in facts:
            if f.id in mgr._store._cache:
                continue
            key = (f.category, hashlib.sha256(f.content.encode()).hexdigest())
            if key in seen:
                continue
            seen[key] = f.id
            dup = await mgr._store.dedup_check(f.content, f.category)  # 逐条 embed
            if dup:
                continue
            scope = "conversation" if f.category in FACT_SCOPE_CONVERSATION else "agent"
            entries.append(VectorEntry(fact_id=f.id, content=f.content,
                                       category=f.category, scope=scope))
        await mgr._store.batch_add(entries)  # 再 embed 一遍
        wall = (time.perf_counter() - t0) * 1000
        return {"calls": prov.calls, "texts": prov.texts, "wall_ms": wall,
                "indexed": len(mgr._store._cache)}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── B/C. 本地 SQLite/CPU 指标（与基线同口径） ─────────────────────────────

def build_data(n):
    from app.engines.memory.models import MemoryData, FactItem
    data = MemoryData()
    data.profile.name = "基准用户"
    data.profile.static_facts = [f"稳定属性{i}" for i in range(10)]
    data.facts = [
        FactItem(content=f"用户偏好第{i}类工具是测试软件{i}号，日常用于编写示例项目",
                 category="preference", confidence=0.8)
        for i in range(n)
    ]
    return data


def bench_local():
    from app.engines.memory.store import MemoryStore
    from app.engines.memory.fact_manager import FactManager
    from app.engines.memory.models import FactItem
    out = {}
    tmp = fresh("local")
    try:
        store = MemoryStore(tmp / "users" / "bench")
        data = build_data(100)
        store.save_data(data)
        t0 = time.perf_counter()
        for _ in range(20):
            store.save_data(data)
        out["save_data_100_ms"] = (time.perf_counter() - t0) * 1000 / 20

        store.close()
        store2 = MemoryStore(tmp / "users" / "bench")
        t0 = time.perf_counter()
        store2.load_data()
        out["load_cold_100_ms"] = (time.perf_counter() - t0) * 1000

        fm = FactManager(store2)
        merged = build_data(100)
        new_facts = [
            FactItem(content=f"用户最近开始学习第{i}门编程语言示例语言{i}并完成练习项目",
                     category="goal", confidence=0.85)
            for i in range(50)
        ]
        t0 = time.perf_counter()
        fm.merge_facts(merged, new_facts)
        out["merge_100_50_ms"] = (time.perf_counter() - t0) * 1000
        store2.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


async def bench_rank_and_load():
    from app.engines.memory.vector_store import VectorStore, VectorEntry
    out = {}
    tmp = fresh("rank")
    try:
        store = VectorStore(tmp / "vectors", RttBatchProvider(0), owner_key="b:owner")

        async def fill(n):
            rng = np.random.default_rng(7)
            entries = []
            for i in range(n):
                e = VectorEntry(fact_id=f"f{i}", content=f"条目{i}", category="preference")
                e.vector = rng.standard_normal(DIM).astype(np.float32)
                entries.append(e)
            await store.batch_add(entries, pre_vectors=[e.vector for e in entries])

        await fill(100)
        q = np.random.default_rng(7).standard_normal(DIM).astype(np.float32)
        cands = set(store._cache.keys())
        t0 = time.perf_counter()
        for _ in range(20):
            store._rank_candidates(q, cands, 0.0)
        out["rank_100_ms"] = (time.perf_counter() - t0) * 1000 / 20

        await fill(1000)
        cands = set(store._cache.keys())
        t0 = time.perf_counter()
        for _ in range(20):
            store._rank_candidates(q, cands, 0.0)
        out["rank_1000_ms"] = (time.perf_counter() - t0) * 1000 / 20

        t0 = time.perf_counter()
        store2 = VectorStore(tmp / "vectors", RttBatchProvider(0), owner_key="b:owner")
        await store2._ensure_loaded()
        out["load_1000_vectors_ms"] = (time.perf_counter() - t0) * 1000
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


# ── D. 端到端记忆写入/注入链路（LLM 即时应答，embedding 可配 RTT） ─────────

class InstantChat:
    async def chat(self, messages, **kw):
        return json.dumps({
            "profile_name": "基准用户",
            "facts": [
                {"content": "喜欢喝拿铁咖啡", "category": "preference", "confidence": 0.9},
                {"content": "正在跑记忆基准", "category": "context", "confidence": 0.85},
            ],
        }, ensure_ascii=False)


async def bench_e2e(rtt_ms):
    from app.engines.memory.memory_engine import MemoryEngine
    engine = MemoryEngine(
        storage_path=fresh("e2e") / "agent", agent_id="e2e_agent",
        embedding_provider=RttBatchProvider(rtt_ms),
    )
    t0 = time.perf_counter()
    await engine.update_profile_from_message(
        "我叫基准用户，喜欢喝拿铁咖啡", llm_adapter=InstantChat(), conversation_id="conv-1"
    )
    write_ms = (time.perf_counter() - t0) * 1000

    # 读路径：注入构建（含向量召回 = 1 次 query embed）
    t0 = time.perf_counter()
    ctx = await engine.build_context_async(query="咖啡", conversation_id="conv-1")
    inject_ms = (time.perf_counter() - t0) * 1000
    return {"write_ms": write_ms, "inject_ms": inject_ms, "ctx_len": len(ctx)}


# ── E. 响应路径专项（回复关键路径上的记忆耗时） ─────────────────────────────

async def bench_inject_path(rtt_ms):
    """E1. 注入延迟（读路径，LLM 调用前内联）：含 1 次查询向量 embed。"""
    from app.engines.memory.memory_engine import MemoryEngine
    engine = MemoryEngine(
        storage_path=fresh("inj") / "agent", agent_id="inj_agent",
        embedding_provider=RttBatchProvider(rtt_ms),
    )
    # 预置 100 条事实（真实注入预算场景）
    data = build_data(100)
    engine.save_data(data)
    t0 = time.perf_counter()
    ctx = await engine.build_context_async(query="用户偏好什么工具", conversation_id=None)
    cold_ms = (time.perf_counter() - t0) * 1000
    # 稳态：引擎已热（缓存就绪、线程池已启动）后的第二次注入
    t0 = time.perf_counter()
    ctx = await engine.build_context_async(query="用户最近在忙什么", conversation_id="conv-1")
    warm_ms = (time.perf_counter() - t0) * 1000
    return {"inject_ms": cold_ms, "warm_ms": warm_ms, "ctx_len": len(ctx)}


async def bench_loop_stall():
    """E2. 写入期间事件循环停顿：update_profile 全链路跑在后台任务，
    采样循环 tick 间隔。旧版 merge_facts（130ms 纯 CPU）在事件循环线程
    裸跑，会冻结全部并发请求；新版已 to_thread。"""
    from app.engines.memory.memory_engine import MemoryEngine

    class EightFactsChat:
        async def chat(self, messages, **kw):
            return json.dumps({
                "profile_name": "基准用户",
                "facts": [
                    {"content": f"新提取事实{i}：偏好示例软件{i}号", "category": "preference",
                     "confidence": 0.9}
                    for i in range(8)
                ],
            }, ensure_ascii=False)

    engine = MemoryEngine(
        storage_path=fresh("stall") / "agent", agent_id="stall_agent",
        embedding_provider=RttBatchProvider(0),
    )
    engine.save_data(build_data(100))  # 100 条存量，merge 负载与 B 段一致

    stop = asyncio.Event()
    gaps: list[float] = []

    async def sampler():
        last = time.perf_counter()
        while not stop.is_set():
            await asyncio.sleep(0.005)
            now = time.perf_counter()
            gaps.append((now - last) * 1000)
            last = now

    sampler_task = asyncio.create_task(sampler())
    # 预热默认线程池：排除首次 to_thread 拉起线程的一次性开销
    await asyncio.to_thread(int)
    t0 = time.perf_counter()
    await engine.update_profile_from_message(
        "一批新偏好", llm_adapter=EightFactsChat(), conversation_id="conv-stall"
    )
    total_ms = (time.perf_counter() - t0) * 1000
    stop.set()
    await sampler_task
    return {"write_total_ms": total_ms, "max_stall_ms": max(gaps),
            "p99_stall_ms": sorted(gaps)[int(len(gaps) * 0.99)] if gaps else 0}


async def bench_connection_reuse():
    """E3. 连接复用收益（回环 TCP 无 TLS —— 真实远端 TLS 握手 100-300ms
    无法离线实测，此为下界）：逐次新建 AsyncClient vs 共享连接池。"""
    import httpx

    async def handle(reader, writer):
        try:
            await reader.read(65536)
            body = json.dumps({"data": [{"embedding": [0.1] * 8}]}).encode()
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
                + body
            )
            await writer.drain()
        finally:
            writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    url = f"http://127.0.0.1:{port}/embeddings"
    N = 30

    t0 = time.perf_counter()
    for _ in range(N):
        async with httpx.AsyncClient(timeout=10.0) as client:  # 旧版 embed 模式
            await client.post(url, json={"input": ["x"]})
    per_call_ms = (time.perf_counter() - t0) * 1000 / N

    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=10.0) as client:  # 新版共享模式
        for _ in range(N):
            await client.post(url, json={"input": ["x"]})
    shared_ms = (time.perf_counter() - t0) * 1000 / N

    server.close()
    await server.wait_closed()
    return {"per_call_client_ms": per_call_ms, "shared_client_ms": shared_ms}


async def main():
    print("=" * 78)
    print("记忆系统性能基准（改进后代码；RTT 为模拟值，SQLite/CPU 为真实实测）")
    print("=" * 78)
    # e2e 段的对话级 store 解析到 DATA_DIR/memory 下走全局库，先按生产路径建表
    from app.infrastructure.database import init_db, dispose_db
    await init_db()

    print("\nA. 向量索引 dedup_and_add：N=30（RTT 模拟；HTTP 调用数为真实计数）")
    print(f"{'场景':<26}{'HTTP调用':>9}{'embed文本':>10}{'墙钟ms':>10}")
    for rtt, tag in ((50, "RTT=50ms"), (200, "RTT=200ms")):
        old = await bench_old_algo(30, rtt)
        new = await bench_new(30, rtt)
        b = BASELINE["dedup_n30_rtt50" if rtt == 50 else "dedup_n30_rtt200"]
        print(f"  改动前基线 {tag:<14}{b['calls']:>8}{b['texts']:>10}{b['wall_ms']:>10.1f}")
        print(f"  旧算法复刻 {tag:<14}{old['calls']:>8}{old['texts']:>10}{old['wall_ms']:>10.1f}")
        print(f"  新实现     {tag:<14}{new['calls']:>8}{new['texts']:>10}{new['wall_ms']:>10.1f}"
              f"   ← 入库{new['indexed']}条")
        speedup = old["wall_ms"] / max(new["wall_ms"], 0.001)
        print(f"  提速: {speedup:.1f}x（调用 {old['calls']}→{new['calls']} 次）")

    print("\nB/C. 本地指标（真实 SQLite/CPU，与改动前基线同口径）")
    loc = bench_local()
    rnk = await bench_rank_and_load()
    rows = [
        ("merge_facts 100存量+50新增", "merge_100_50_ms", loc),
        ("save_data 全量替换 100条", "save_data_100_ms", loc),
        ("load_data 冷启动 100条", "load_cold_100_ms", loc),
        ("_rank_candidates 100向量", "rank_100_ms", rnk),
        ("_rank_candidates 1000向量", "rank_1000_ms", rnk),
        ("_load 冷启动 1000向量", "load_1000_vectors_ms", rnk),
    ]
    for name, key, src in rows:
        base, now = BASELINE[key], src[key]
        delta = (now - base) / base * 100 if base else 0
        flag = "✓ 无回归" if now <= base * 1.5 else "⚠ 变慢"
        if key == "merge_100_50_ms":
            flag = f"✓ 提速 {base / now:.1f}x" if now < base else flag
        print(f"  {name:<28} 基线 {base:>8.2f}ms → 现在 {now:>8.2f}ms  ({delta:+.0f}%)  {flag}")

    print("\nD. 端到端链路（LLM 提取即时返回；embedding RTT 为模拟值）")
    for rtt in (0, 200):
        r = await bench_e2e(rtt)
        print(f"  embedding RTT={rtt}ms:  写入(提取+合并+落库+向量化) {r['write_ms']:.1f}ms"
              f" | 注入(含向量召回) {r['inject_ms']:.1f}ms | 注入长度 {r['ctx_len']} 字符")

    print("\nE. 响应路径专项（回复关键路径上的记忆耗时）")
    print("  E1. 注入延迟（读路径，LLM 调用前内联；100 条存量事实）")
    for rtt in (0, 50, 200):
        r = await bench_inject_path(rtt)
        print(f"    embedding RTT={rtt:>3}ms: 冷启动注入 {r['inject_ms']:.1f}ms"
              f" | 稳态注入 {r['warm_ms']:.1f}ms（含 1 次 embed RTT，本地部分 ≈ 稳态-{rtt}ms）")
    print("  E2. 写入期间事件循环停顿（旧版 merge 130ms 纯 CPU 裸跑在循环线程）")
    s = await bench_loop_stall()
    print(f"    写入总耗时 {s['write_total_ms']:.1f}ms | 事件循环最大停顿 {s['max_stall_ms']:.1f}ms"
          f" | p99 停顿 {s['p99_stall_ms']:.1f}ms  ← 旧版基线约 130ms 冻结")
    print("  E3. 连接复用收益（回环 TCP 无 TLS，真实 TLS 握手为其 10-100 倍，此为下界）")
    c = await bench_connection_reuse()
    print(f"    逐次新建 client {c['per_call_client_ms']:.2f}ms/次（旧 embed 模式）"
          f" vs 共享连接池 {c['shared_client_ms']:.2f}ms/次（新实现）")

    print("\n" + "=" * 78)
    print("注：改动前基线中向量索引相关行（31 次调用 / 6331ms）产出的全是 () 标量垃圾，")
    print("    新实现 1 次调用且产出 (1536,) 有效向量——速度与正确性同时修复。")
    print("=" * 78)
    try:
        await dispose_db()
    except Exception:
        pass
    shutil.rmtree(_TMP_DATA, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
