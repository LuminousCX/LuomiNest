"""P0-2 上下文压缩修复回归测试（跨会话串扰 + 摘要不落库）。

覆盖：
- 会话隔离：不同 conv_id 经 get_context_manager 取到独立压缩器实例，
  摘要 prompt 与水位线互不串扰（mock LLM 摘要调用）
- 摘要持久化 round-trip：增量摘要完成后 {summary, watermark} 写入
  config_items（键 conv.<id>.context_summary，走 luominest_config_store
  facade + 临时 SQLite）；全新实例（模拟进程重启）读回恢复水位线，
  无新增消息时零 LLM 调用复用旧摘要
- conv_id=None 兼容：缓存 key 与旧行为一致（共享单例、纯内存、不触库）
"""

import pytest

from app.core.config import settings
from app.core.context.compressors import LLMSummaryCompressor
from app.core.context.manager import (
    ContextManager,
    _context_managers,
    get_context_manager,
    invalidate_context_cache,
)


# ── 测试辅助 ──────────────────────────────────────────────────


class SummaryCallRecorder:
    """替换 _call_llm_for_summary 的桩：记录每次摘要 prompt 并返回固定摘要文本。"""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[str] = []

    async def __call__(self, llm_payload: list[dict], max_tokens: int) -> str:
        self.calls.append(llm_payload[0]["content"])
        return self.reply


class FakeConfigStore:
    """替换 luominest_config_store 的内存桩（异步接口与 facade 一致）。"""

    def __init__(self) -> None:
        self.data: dict = {}

    async def get_async(self, key: str, default=None):
        return self.data.get(key, default)

    async def set_async(self, key: str, value) -> None:
        self.data[key] = value


def _make_messages(pairs: int, prefix: str = "普通") -> list[dict]:
    """构造一段超过 keep_recent 的伪对话（system + pairs 轮 user/assistant）。"""
    msgs = [{"role": "system", "content": "你是助手。"}]
    for i in range(pairs):
        msgs.append({"role": "user", "content": f"{prefix}问题{i}：" + "x" * 60})
        msgs.append({"role": "assistant", "content": f"{prefix}回答{i}：" + "y" * 60})
    return msgs


@pytest.fixture(autouse=True)
def _clean_context_cache():
    """模块级缓存逐测试清空，避免用例间共享压缩器实例。"""
    invalidate_context_cache()
    yield
    invalidate_context_cache()


@pytest.fixture
def fake_store(monkeypatch) -> FakeConfigStore:
    """把 config_store 单例换成内存桩（懒导入在调用期解析模块属性，替换生效）。"""
    store = FakeConfigStore()
    monkeypatch.setattr(
        "app.infrastructure.database.config_store.luominest_config_store", store
    )
    return store


# ── 会话隔离 ──────────────────────────────────────────────────


async def test_different_conv_ids_get_isolated_managers(monkeypatch):
    """不同 conv_id 持有独立 ContextManager/压缩器实例；conv_id=None 共享旧单例。"""
    monkeypatch.setattr(settings, "LLM_COMPRESS_ENABLED", True)
    monkeypatch.setattr(settings, "LLM_CONTEXT_WINDOW_SIZE", 8192)

    mgr_a = get_context_manager("openai", "gpt-test", conv_id="conv-A")
    mgr_b = get_context_manager("openai", "gpt-test", conv_id="conv-B")
    assert mgr_a is not mgr_b
    assert mgr_a.compressor is not mgr_b.compressor

    # 同一会话重复获取命中缓存
    assert get_context_manager("openai", "gpt-test", conv_id="conv-A") is mgr_a


async def test_compression_state_isolated_between_conv_ids(fake_store, monkeypatch):
    """两个会话交替压缩：摘要 prompt、摘要内容、水位线互不串扰。"""
    comp_a = LLMSummaryCompressor()
    rec_a = SummaryCallRecorder("这是会话A的摘要")
    monkeypatch.setattr(comp_a, "_call_llm_for_summary", rec_a)

    comp_b = LLMSummaryCompressor()
    rec_b = SummaryCallRecorder("这是会话B的摘要")
    monkeypatch.setattr(comp_b, "_call_llm_for_summary", rec_b)

    msgs_a = _make_messages(6, prefix="会话A专属")
    msgs_b = _make_messages(6, prefix="会话B专属")

    await comp_a.compress(msgs_a, conv_id="conv-A")
    await comp_b.compress(msgs_b, conv_id="conv-B")

    # A 的历史只进 A 的摘要 prompt，B 同理
    assert any("会话A专属" in c for c in rec_a.calls)
    assert all("会话A专属" not in c for c in rec_b.calls)
    assert any("会话B专属" in c for c in rec_b.calls)
    assert all("会话B专属" not in c for c in rec_a.calls)

    # 摘要按会话各写各的 config_items 键
    assert fake_store.data["conv.conv-A.context_summary"]["summary"] == "这是会话A的摘要"
    assert fake_store.data["conv.conv-B.context_summary"]["summary"] == "这是会话B的摘要"

    # 水位线各推各的（内容不同 → 消息 id 不同）
    watermark_a = fake_store.data["conv.conv-A.context_summary"]["watermark"]
    watermark_b = fake_store.data["conv.conv-B.context_summary"]["watermark"]
    assert watermark_a == comp_a._summary_up_to_msg_id
    assert watermark_b == comp_b._summary_up_to_msg_id
    assert watermark_a != watermark_b


async def test_context_manager_process_passes_conv_id(fake_store, monkeypatch):
    """ContextManager.process(conv_id=...) 端到端：压缩触发 + 摘要落库。"""
    mgr = ContextManager(max_context_tokens=100000, llm_compress=True, context_window=8192)
    assert isinstance(mgr.compressor, LLMSummaryCompressor)

    rec = SummaryCallRecorder("经理层的摘要")
    monkeypatch.setattr(mgr.compressor, "_call_llm_for_summary", rec)

    result = await mgr.process(
        _make_messages(6, prefix="经理层会话"),
        trusted_token_usage=99999,  # 超阈值触发压缩
        conv_id="conv-mgr",
    )

    assert any("[对话历史摘要]" in m.get("content", "") for m in result["messages"])
    assert fake_store.data["conv.conv-mgr.context_summary"]["summary"] == "经理层的摘要"


# ── 持久化 round-trip（真实 config_store + 临时 SQLite）────────


async def test_summary_persisted_and_restored_across_restart(_init_test_db, monkeypatch):
    """压缩后 {summary, watermark} 写入 config_items；新实例（模拟重启）读回恢复。"""
    from app.infrastructure.database.config_store import luominest_config_store

    # 第一轮：全新压缩器完成首次摘要并落库
    comp1 = LLMSummaryCompressor()
    rec1 = SummaryCallRecorder("第一轮摘要")
    monkeypatch.setattr(comp1, "_call_llm_for_summary", rec1)

    msgs = _make_messages(6)
    out1 = await comp1.compress(msgs, conv_id="conv-rt")
    assert "[对话历史摘要] 第一轮摘要" in out1[1]["content"]

    record = await luominest_config_store.get_async("conv.conv-rt.context_summary")
    assert record["summary"] == "第一轮摘要"
    assert record["watermark"] == comp1._summary_up_to_msg_id

    # 第二轮：全新实例（内存水位线为空，模拟进程重启），消息不变 →
    # 恢复水位线后无新增消息，零 LLM 调用直接复用持久化摘要
    comp2 = LLMSummaryCompressor()
    rec2 = SummaryCallRecorder("不应被调用")
    monkeypatch.setattr(comp2, "_call_llm_for_summary", rec2)

    out2 = await comp2.compress(msgs, conv_id="conv-rt")
    assert rec2.calls == []
    assert "[对话历史摘要] 第一轮摘要" in out2[1]["content"]

    # 第三轮：追加两轮新消息使原 recent 段跨过 keep_recent 边界进入待摘要范围 →
    # 增量摘要，prompt 以恢复的旧摘要为基础（关闭防漂移使路径确定）
    monkeypatch.setattr(settings, "LLM_ANTI_DRIFT_ENABLED", False)
    rec3 = SummaryCallRecorder("第二轮增量摘要")
    monkeypatch.setattr(comp2, "_call_llm_for_summary", rec3)

    new_msgs = msgs + [
        {"role": "user", "content": "追加的新问题一"},
        {"role": "assistant", "content": "追加的新回答一"},
        {"role": "user", "content": "追加的新问题二"},
        {"role": "assistant", "content": "追加的新回答二"},
    ]
    await comp2.compress(new_msgs, conv_id="conv-rt")

    assert len(rec3.calls) == 1
    assert "第一轮摘要" in rec3.calls[0]  # 旧摘要作为增量基础，而非从头全量
    assert "普通问题4" in rec3.calls[0]  # 新跨入摘要范围的增量消息

    # 落库的水位线已推进
    record_after = await luominest_config_store.get_async("conv.conv-rt.context_summary")
    assert record_after["summary"] == "第二轮增量摘要"
    assert record_after["watermark"] == comp2._summary_up_to_msg_id


# ── conv_id=None 兼容（旧行为不变）────────────────────────────


async def test_none_conv_id_keeps_legacy_behavior(fake_store, monkeypatch):
    """conv_id=None：缓存 key 沿用旧格式（共享单例）、纯内存状态、不触达 config_items。"""
    m1 = get_context_manager("openai", "gpt-test")
    m2 = get_context_manager("openai", "gpt-test")
    assert m1 is m2

    # 旧版 key 原样保留（不含 conv 段），既有内部路径/测试不受影响
    monkeypatch.setattr(settings, "LLM_COMPRESS_ENABLED", False)
    invalidate_context_cache()
    get_context_manager("openai", "gpt-test")
    assert "openai:gpt-test:t0.7:c0:struncate" in _context_managers

    # 压缩器层面：无 conv_id 时仅进程内存，不读写 config_items
    comp = LLMSummaryCompressor()
    rec = SummaryCallRecorder("旧版摘要")
    monkeypatch.setattr(comp, "_call_llm_for_summary", rec)

    msgs = _make_messages(6)
    out = await comp.compress(msgs)
    assert "[对话历史摘要] 旧版摘要" in out[1]["content"]
    assert comp._state_restored_for is None
    assert fake_store.data == {}

    # 二次压缩（无新增消息）复用内存缓存，依旧不触库
    rec2 = SummaryCallRecorder("不应被调用")
    monkeypatch.setattr(comp, "_call_llm_for_summary", rec2)
    await comp.compress(msgs)
    assert rec2.calls == []
    assert fake_store.data == {}
