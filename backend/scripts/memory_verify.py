# -*- coding: utf-8 -*-
"""记忆系统准确性验证脚本（改进后回归验证，可反复运行）。

验证「问的问题 → 是否记住」的完整链路，以及本次改进引入/涉及的全部
正确性行为。LLM 在适配器边界被替换为固定应答（模拟真实提取结果），
embedding 用确定性批量伪实现；其余全部走真实生产代码路径。

用法：cd backend && .venv/Scripts/python.exe scripts/memory_verify.py
"""
import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

# 与 tests/conftest.py 相同的隔离方式：任何 app 导入前指向临时 DATA_DIR
_TMP_DATA = tempfile.mkdtemp(prefix="lumi-verify-data-")
os.environ["LUOMINEST_DATA_DIR"] = _TMP_DATA
os.environ["DATABASE_URL"] = ""

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    mark = "✓" if cond else "✗"
    print(f"  [{mark}] {name}" + (f" —— {detail}" if detail else ""))
    if cond:
        PASS += 1
    else:
        FAIL += 1


# ── 测试替身 ──────────────────────────────────────────────────────────────

class FakeChatAdapter:
    """模拟 LLM chat：按 prompt 关键词返回固定提取 JSON（与真实提取格式一致）。"""

    def __init__(self, payload: str):
        self.payload = payload
        self.calls = 0

    async def chat(self, messages, **kw):
        self.calls += 1
        return self.payload


class FakeBatchEmbedding:
    """确定性批量伪嵌入（批量协议）：关键词 → 单位基向量，同词同向异词正交。"""

    dim = 64
    _BASIS = {"咖啡": 0, "拿铁": 1, "代码": 2, "编辑器": 3, "游戏": 4, "天气": 5, "音乐": 6}

    async def embed(self, texts):
        out = []
        for t in texts:
            vec = np.zeros(self.dim, dtype=np.float32)
            hit = False
            for token, idx in self._BASIS.items():
                if token in t:
                    vec[idx] = 1.0
                    hit = True
            if not hit:
                vec[self.dim - 1] = 1.0
            out.append(vec.tolist())
        return out


EXTRACT_PAYLOAD = json.dumps({
    "profile_name": "洛米",
    "facts": [
        {"content": "喜欢喝拿铁咖啡", "category": "preference", "confidence": 0.9},
        {"content": "正在验证记忆系统", "category": "context", "confidence": 0.85},
    ],
}, ensure_ascii=False)


# ── 各验证项 ──────────────────────────────────────────────────────────────

async def t1_end_to_end_remember(tmp: Path):
    """① 端到端：说话 → 提取入库 → 提问时记忆注入（关键词路径 + 向量路径）。"""
    from app.engines.memory.memory_engine import MemoryEngine

    engine = MemoryEngine(
        storage_path=tmp / "t1_agent", agent_id="t1_agent",
        embedding_provider=FakeBatchEmbedding(),
    )
    result = await engine.update_profile_from_message(
        "我叫洛米，我喜欢喝拿铁咖啡，现在正在验证记忆系统。",
        llm_adapter=FakeChatAdapter(EXTRACT_PAYLOAD),
        conversation_id="conv-1",
    )
    data = engine.load_data()
    check("档案姓名被记住", data.profile.name == "洛米", f"name={data.profile.name!r}")
    agent_contents = [f.content for f in data.facts]
    check("Agent级事实（偏好）入库", "喜欢喝拿铁咖啡" in agent_contents)

    conv_store = engine._get_conv_store("conv-1")
    conv_contents = [f.content for f in conv_store.load_data().facts]
    check("对话级事实（context）落在对话轨", "正在验证记忆系统" in conv_contents)

    ctx = engine.build_context_sync(query="咖啡")
    check("提问『咖啡』→ 记忆注入包含拿铁", "拿铁" in ctx)
    ctx2 = engine.build_context_sync(query="验证", conversation_id="conv-1")
    check("对话内提问 → 对话级事实注入", "正在验证记忆系统" in ctx2)

    hits = await engine.vector_retrieve("咖啡", k=5)
    top_contents = [engine.load_data().facts and f.fact_id for f in hits]
    data_facts = {f.id: f.content for f in data.facts}
    top_texts = [data_facts.get(fid, "") for fid in top_contents]
    check("向量检索『咖啡』命中咖啡事实", any("咖啡" in t for t in top_texts), f"top={top_texts[:2]}")


async def t2_production_wiring(tmp: Path):
    """② 生产装配链路：真实 OpenAICompatibleProvider + 批量 embeddings 响应
    → 向量形状 (1536,)，且 HTTP 调用收敛为 1 次（旧链路为 N+1 且全部标量化）。"""
    import httpx
    import app.engines.memory.memory_engine as me_mod
    import app.engines.memory.vector_store as vs_mod
    from app.runtime.provider.llm.adapters.chat_completions import OpenAICompatibleProvider
    from app.engines.memory.memory_engine import MemoryEngine
    from app.engines.memory.models import FactItem

    calls = {"n": 0}
    DIM = 1536

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        texts = body["input"] if isinstance(body["input"], list) else [body["input"]]
        calls["n"] += 1
        return httpx.Response(200, json={
            "data": [{"embedding": [0.01] * DIM, "index": i} for i in range(len(texts))]
        })

    async def fake_get_client(self):
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=30.0)

    chat_provider = OpenAICompatibleProvider(
        base_url="https://api.openai.com/v1", api_key="sk-test", default_model="gpt-4o"
    )
    engine = MemoryEngine(storage_path=tmp / "t2_agent", agent_id="t2_agent")

    orig_gc = vs_mod.LLMEmbeddingProvider._get_client
    orig_gp = me_mod.llm_adapter.get_provider
    vs_mod.LLMEmbeddingProvider._get_client = fake_get_client
    me_mod.llm_adapter.get_provider = lambda name=None: chat_provider
    try:
        facts = [FactItem(content=f"生产装配验证事实{i}", category="preference") for i in range(5)]
        await engine.vector_dedup(facts)
        shapes = {e.vector.shape for e in engine._vector_manager._store._cache.values()}
        check("生产装配向量形状为 (1536,)（非标量）", shapes == {(DIM,)}, f"shapes={shapes}")
        check("5 条事实仅 1 次 HTTP 调用（旧链路 6 次）", calls["n"] == 1, f"calls={calls['n']}")
    finally:
        vs_mod.LLMEmbeddingProvider._get_client = orig_gc
        me_mod.llm_adapter.get_provider = orig_gp


async def t3_contract_guard(tmp: Path):
    """③ 契约防护：错误协议 provider（单文本返回一个向量）现在 fail-loud。"""
    from app.engines.memory.vector_store import VectorStore, VectorEntry

    class WrongProtocolProvider:
        dim = 8

        async def embed(self, text):  # 单文本协议：只返回一个向量
            return [0.1] * 8

    (tmp / "t3_vec").mkdir(parents=True, exist_ok=True)
    store = VectorStore(tmp / "t3_vec", WrongProtocolProvider(), owner_key="t3:owner")
    raised = False
    try:
        await store.batch_add([VectorEntry(fact_id="f1", content="x", category="preference")])
    except ValueError:
        raised = True
    check("错误协议触发 ValueError（旧版静默产出 () 标量）", raised)
    store.close()


async def t4_stale_vector_cleanup(tmp: Path):
    """④ 存量垃圾清洗：历史 bug 写入的标量/错维向量在冷启动时被剔除。"""
    from app.engines.memory.vector_store import VectorStore, VectorEntry

    vec_dir = tmp / "t4_vec"
    vec_dir.mkdir(parents=True)
    good = np.ones(8, dtype=np.float32)
    store = VectorStore(vec_dir, FakeBatchEmbedding(), owner_key="t4:owner")
    await store.batch_add([VectorEntry(fact_id="good", content="咖啡", category="preference",
                                       vector=good)])
    # 直接写入坏行：标量（历史错配产物）与错维（换模型残留）
    with store._db.session() as session:
        from app.infrastructure.database.models.memory import MemoryVector
        session.add(MemoryVector(fact_id="scalar_garbage", owner_key="t4:owner", content="x",
                                 category="preference", scope="agent", conversation_id="",
                                 vector=np.float32(0.5).tobytes()))
        session.add(MemoryVector(fact_id="wrong_dim", owner_key="t4:owner", content="y",
                                 category="preference", scope="agent", conversation_id="",
                                 vector=np.ones(99, dtype=np.float32).tobytes()))
        session.commit()
    store.close()

    store2 = VectorStore(vec_dir, FakeBatchEmbedding(), owner_key="t4:owner")
    await store2._ensure_loaded()
    ids = set(store2._cache.keys())
    check("冷启动剔除标量与错维垃圾行", ids == {"good"}, f"剩余={ids}")
    hits = await store2.search("咖啡", k=10)
    check("清洗后检索只返回有效事实", [h.fact_id for h in hits] == ["good"])
    store2.close()


async def t5_dedup_and_contradiction(tmp: Path):
    """⑤ 合并语义：重复入库不翻倍；同类别矛盾替代（归档）；LLM correction 降置信度。"""
    from app.engines.memory.memory_engine import MemoryEngine
    from app.engines.memory.models import FactItem

    engine = MemoryEngine(storage_path=tmp / "t5_agent", agent_id="t5_agent")
    engine.add_fact(FactItem(content="喜欢喝拿铁咖啡", category="preference", confidence=0.9))
    engine.add_fact(FactItem(content="喜欢喝拿铁咖啡", category="preference", confidence=0.9))
    data = engine.load_data()
    same = [f for f in data.facts if "拿铁" in f.content]
    check("重复内容不重复入库", len(same) == 1, f"count={len(same)}")

    # 同类别矛盾（tier-3：共享核心词 + 矛盾关键词对）→ 归档旧事实
    engine.add_fact(FactItem(content="使用Windows系统工作", category="context", confidence=0.9))
    engine.add_fact(FactItem(content="停止使用Windows系统", category="context", confidence=0.9))
    data = engine.load_data()
    old = next((f for f in data.facts if f.content == "使用Windows系统工作"), None)
    new = next((f for f in data.facts if f.content == "停止使用Windows系统"), None)
    check("同类别矛盾：旧事实被归档（is_latest=False）", old is not None and not old.is_latest)
    check("同类别矛盾：旧事实保留历史版本", old is not None and len(old.history) >= 1)
    check("同类别矛盾：新事实为最新", new is not None and new.is_latest)

    # correction 走 LLM 合并路径（merge_facts）：按 source_error 匹配降置信度
    payload = json.dumps({
        "profile_name": "",
        "facts": [{
            "content": "不再喝拿铁咖啡，改喝茶",
            "category": "correction",
            "confidence": 0.95,
            "source_error": "喜欢喝拿铁咖啡",
        }],
    }, ensure_ascii=False)
    await engine.update_profile_from_message("纠正一下", llm_adapter=FakeChatAdapter(payload))
    data = engine.load_data()
    coffee = next((f for f in data.facts if f.content == "喜欢喝拿铁咖啡"), None)
    corrected = next((f for f in data.facts if "改喝茶" in f.content), None)
    check("LLM correction：旧事实置信度被降（≤0.3）", coffee is not None and coffee.confidence <= 0.3)
    check("LLM correction：新事实入库", corrected is not None)
    check("有效事实过滤后归档事实不注入",
          all(f.is_latest for f in engine.get_facts()))


async def t6_supersedes_consolidation(tmp: Path):
    """⑥ supersedes 收口：K 条 supersedes 不再是 K 次全量 save。"""
    from app.engines.memory.memory_engine import MemoryEngine

    engine = MemoryEngine(storage_path=tmp / "t6_agent", agent_id="t6_agent")
    from app.engines.memory.models import FactItem
    engine.add_fact(FactItem(content="住在上海", category="context", confidence=0.9))
    engine.add_fact(FactItem(content="用Windows系统", category="knowledge", confidence=0.9))
    engine.add_fact(FactItem(content="喜欢打篮球", category="preference", confidence=0.9))

    payload = json.dumps({
        "profile_name": "",
        "facts": [
            {"content": "搬到北京了", "category": "knowledge", "confidence": 0.9,
             "supersedes": "住在上海"},
            {"content": "换成Mac系统", "category": "knowledge", "confidence": 0.9,
             "supersedes": "用Windows系统"},
            {"content": "改踢足球", "category": "preference", "confidence": 0.9,
             "supersedes": "喜欢打篮球"},
        ],
    }, ensure_ascii=False)

    saves = {"n": 0}
    orig_save = engine._store.save_data
    engine._store.save_data = lambda d: (saves.__setitem__("n", saves["n"] + 1), orig_save(d))[1]

    await engine.update_profile_from_message("我要纠正几条信息", llm_adapter=FakeChatAdapter(payload))
    engine._store.save_data = orig_save

    data = engine.load_data()
    superseded = [f for f in data.facts if not f.is_latest]
    check("3 条 supersedes 全部生效", len(superseded) == 3, f"superseded={len(superseded)}")
    check("全流程 save 次数 ≤ 2（旧版 ≥ 4：1 merge + 3 逐条）", saves["n"] <= 2, f"saves={saves['n']}")


async def t7_conversation_isolation(tmp: Path):
    """⑦ 对话隔离：对话级事实不串到其他对话。"""
    from app.engines.memory.memory_engine import MemoryEngine
    from app.engines.memory.models import FactItem

    engine = MemoryEngine(storage_path=tmp / "t7_agent", agent_id="t7_agent")
    conv_a = engine._get_conv_store("conv-a")
    d = conv_a.load_data()
    from app.engines.memory.models import MemoryData
    d.facts.append(FactItem(content="对话A的临时上下文", category="context", confidence=0.8))
    conv_a.save_data(d)

    ctx_b = engine.build_context_sync(query="上下文", conversation_id="conv-b")
    check("对话B看不到对话A的事实", "对话A的临时上下文" not in ctx_b)
    ctx_a = engine.build_context_sync(query="上下文", conversation_id="conv-a")
    check("对话A能看到自己的事实", "对话A的临时上下文" in ctx_a)


async def t8_group_member_block(tmp: Path):
    """⑧ 群友画像块：多成员轨读取 + 排除说话成员。"""
    from app.engines.memory import build_group_members_block, get_track_engine
    from app.core.domain_policy import TRACK_USERS as TU
    from app.engines.memory.models import FactItem

    for key, name in (("qq_onebot_inst1_10001", "小明"), ("qq_onebot_inst1_10002", "小红")):
        eng = get_track_engine(TU, key)
        d = eng.load_data()
        d.facts.append(FactItem(content=f"{name}喜欢打羽毛球", category="preference", confidence=0.9))
        eng.save_data(d)

    members = [
        {"sender_id": "10001", "sender_name": "小明", "user_key": "qq_onebot_inst1_10001"},
        {"sender_id": "10002", "sender_name": "小红", "user_key": "qq_onebot_inst1_10002"},
    ]
    block = await asyncio.to_thread(build_group_members_block, members)
    check("画像块包含两位群友", "小明" in block and "小红" in block)
    block2 = await asyncio.to_thread(
        build_group_members_block, members, exclude_keys={"qq_onebot_inst1_10001"}
    )
    check("排除说话成员生效", "小明" not in block2 and "小红" in block2)


async def t9_forget_action(tmp: Path):
    """⑨ 自然语言 forget：匹配事实被遗忘（置信度降 + 非最新）。"""
    from app.engines.memory.memory_engine import MemoryEngine
    from app.engines.memory.models import FactItem
    from app.services.context_service import ContextService

    engine = MemoryEngine(storage_path=tmp / "t9_agent", agent_id="t9_agent")
    engine.add_fact(FactItem(content="喜欢喝拿铁咖啡", category="preference", confidence=0.9))
    engine.add_fact(FactItem(content="喜欢打篮球", category="preference", confidence=0.9))

    await ContextService.execute_memory_action(engine, {"action": "forget", "target": "咖啡"})
    data = engine.load_data()
    coffee = next(f for f in data.facts if "咖啡" in f.content)
    basketball = next(f for f in data.facts if "篮球" in f.content)
    check("forget：咖啡事实被遗忘", not coffee.is_latest and coffee.confidence == 0.1)
    check("forget：无关事实不受影响", basketball.is_latest and basketball.confidence == 0.9)


async def t10_concurrent_writes(tmp: Path):
    """⑩ 并发写：20 个并发 update 经写锁后零丢失（旧版存在读-改-写覆盖窗口）。"""
    from app.engines.memory.memory_engine import MemoryEngine
    from app.engines.memory.models import FactItem

    engine = MemoryEngine(storage_path=tmp / "t10_agent", agent_id="t10_agent")
    for i in range(20):
        engine.add_fact(FactItem(content=f"并发验证事实{i}", category="context", confidence=0.5))
    fact_ids = [f.id for f in engine.load_data().facts]

    async def bump(fid):
        async with engine.write_lock:
            await asyncio.to_thread(engine.update_fact, fid, confidence=0.95)

    await asyncio.gather(*[bump(fid) for fid in fact_ids])
    data = engine.load_data()
    lost = [f for f in data.facts if f.confidence != 0.95]
    check("20 路并发更新零丢失", len(lost) == 0, f"丢失={len(lost)}")


async def t11_rebuild_clears_stale(tmp: Path):
    """⑪ 重建索引清旧：删除事实后 rebuild，向量索引不再召回已删事实。"""
    from app.engines.memory.memory_engine import MemoryEngine
    from app.engines.memory.models import FactItem

    engine = MemoryEngine(
        storage_path=tmp / "t11_agent", agent_id="t11_agent",
        embedding_provider=FakeBatchEmbedding(),
    )
    engine.add_fact(FactItem(content="喜欢喝拿铁咖啡", category="preference", confidence=0.9))
    engine.add_fact(FactItem(content="喜欢玩游戏", category="preference", confidence=0.9))
    await engine.vector_dedup(engine.load_data().facts)

    game = next(f for f in engine.load_data().facts if "游戏" in f.content)
    engine.remove_fact(game.id)
    await engine.vector_rebuild()

    hits = await engine.vector_retrieve("游戏", k=10)
    data_facts = {f.id: f.content for f in engine.load_data().facts}
    hit_texts = [data_facts.get(h.fact_id, "?") for h in hits]
    check("rebuild 后已删事实不再被召回", all(h.fact_id != game.id for h in hits),
          f"hits={hit_texts}")
    coffee = next(f for f in engine.load_data().facts if "咖啡" in f.content)
    hits2 = await engine.vector_retrieve("咖啡", k=10)
    check("rebuild 后存留事实仍可召回", any(h.fact_id == coffee.id for h in hits2))


async def t12_fact_content_guard(tmp: Path):
    """⑫ 入库防护：超长内容截断、越界置信度夹取、低置信度丢弃。"""
    from app.engines.memory.memory_engine import MemoryEngine

    engine = MemoryEngine(storage_path=tmp / "t12_agent", agent_id="t12_agent")
    payload = json.dumps({
        "profile_name": "",
        "facts": [
            {"content": "超" * 2000, "category": "preference", "confidence": 5.0},
            {"content": "低置信度事实", "category": "preference", "confidence": 0.3},
        ],
    }, ensure_ascii=False)
    await engine.update_profile_from_message("测试防护", llm_adapter=FakeChatAdapter(payload))
    data = engine.load_data()
    long_facts = [f for f in data.facts if f.content.startswith("超")]
    check("超长内容截断到 500 字符", all(len(f.content) <= 500 for f in long_facts),
          f"max_len={max((len(f.content) for f in long_facts), default=0)}")
    check("越界置信度夹取到 [0,1]", all(f.confidence <= 1.0 for f in data.facts))
    check("低于阈值(0.7)的事实被丢弃", not any("低置信度" in f.content for f in data.facts))


async def t13_fact_vector_lifecycle(tmp: Path):
    """⑬ 事实↔向量生命周期联动：手动创建立即可检索；删除即时不再召回；更新重嵌。"""
    from app.engines.memory.memory_engine import MemoryEngine
    from app.engines.memory.models import FactItem

    engine = MemoryEngine(
        storage_path=tmp / "t13_agent", agent_id="t13_agent",
        embedding_provider=FakeBatchEmbedding(),
    )

    # 创建：remember_fact 写库 + 向量入库，无需 rebuild 立即可检索
    fact = FactItem(content="喜欢喝拿铁咖啡", category="preference", confidence=0.9)
    await engine.remember_fact(fact)
    hits = await engine.vector_retrieve("咖啡", k=5)
    check("手动创建事实后立即可检索（无需 rebuild）",
          any(h.fact_id == fact.id for h in hits), f"hits={[h.fact_id for h in hits]}")

    # 删除：forget_fact_vector 即时摘除向量
    await asyncio.to_thread(engine.remove_fact, fact.id)
    await engine.forget_fact_vector(fact.id)
    hits2 = await engine.vector_retrieve("咖啡", k=5)
    check("删除事实后向量不再召回", all(h.fact_id != fact.id for h in hits2),
          f"hits={[h.fact_id for h in hits2]}")

    # 更新：sync_fact_vector 先摘旧再按新内容重嵌
    fact2 = FactItem(content="喜欢喝拿铁咖啡", category="preference", confidence=0.9)
    await engine.remember_fact(fact2)
    updated = engine.update_fact(fact2.id, content="喜欢喝燕麦拿铁")
    check("更新事实成功", updated)
    data = engine.load_data()
    fact2_new = next(f for f in data.facts if f.id == fact2.id)
    await engine.sync_fact_vector(fact2_new)
    hits3 = await engine.vector_retrieve("拿铁", k=5)
    check("更新后向量按新内容重嵌", any(h.fact_id == fact2.id for h in hits3),
          f"hits={[h.fact_id for h in hits3]}")


async def main():
    tmp = Path(tempfile.mkdtemp(prefix="lumi-verify-"))
    print("=" * 72)
    print("记忆系统准确性验证（改进后）")
    print("=" * 72)
    # 对话轨/用户轨解析到 DATA_DIR/memory 下走全局库，先按生产路径建表
    from app.infrastructure.database import init_db, dispose_db
    await init_db()
    try:
        for name, fn in [
            ("① 端到端记忆：说话→入库→提问注入", t1_end_to_end_remember),
            ("② 生产装配：批量协议+单次HTTP+正确维度", t2_production_wiring),
            ("③ 契约防护：错误协议 fail-loud", t3_contract_guard),
            ("④ 存量标量垃圾冷启动清洗", t4_stale_vector_cleanup),
            ("⑤ 去重与矛盾替代语义", t5_dedup_and_contradiction),
            ("⑥ supersedes 收口（K条→≤2次save）", t6_supersedes_consolidation),
            ("⑦ 对话级隔离", t7_conversation_isolation),
            ("⑧ 群友画像块", t8_group_member_block),
            ("⑨ 自然语言 forget", t9_forget_action),
            ("⑩ 并发写零丢失", t10_concurrent_writes),
            ("⑪ rebuild 清旧索引", t11_rebuild_clears_stale),
            ("⑫ 内容限长/置信度夹取/阈值过滤", t12_fact_content_guard),
            ("⑬ 事实↔向量生命周期联动", t13_fact_vector_lifecycle),
        ]:
            print(f"\n── {name} ──")
            try:
                await fn(tmp)
            except Exception as e:
                check("执行无异常", False, f"{type(e).__name__}: {e}")
    finally:
        try:
            await dispose_db()
        except Exception:
            pass
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(_TMP_DATA, ignore_errors=True)

    print("\n" + "=" * 72)
    print(f"结果：{PASS} 通过 / {FAIL} 失败")
    print("=" * 72)
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    asyncio.run(main())
