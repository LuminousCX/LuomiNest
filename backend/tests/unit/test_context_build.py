"""记忆上下文同步组装回归测试（build_context_sync / 事件循环同步回退分支）。

覆盖：
- build_context_sync 纯文本注入：档案/事实进上下文，全程不触发 embedding
  （llm_adapter.get_provider 不被调用 → 无向量管理器/HTTP 往返）
- 在运行中的事件循环内调用 build_context 自动走同步回退分支（与
  build_context_sync 结果一致；旧实现此处 asyncio.run 会直接抛错）
- 空库返回空串
- ContextService.inject_memory 组装 <user_memory> 块（to_thread 包裹同步组装）
"""

from unittest.mock import MagicMock

import pytest

from app.engines.memory import memory_engine as memory_engine_module
from app.engines.memory.memory_engine import MemoryEngine
from app.engines.memory.models import FactItem
from app.services import context_service as context_service_module


@pytest.fixture
def engine(tmp_path):
    return MemoryEngine(storage_path=tmp_path / "mem", agent_id="test-agent")


async def test_build_context_sync_pure_text_without_embedding(engine, monkeypatch):
    data = engine.load_data()
    data.profile.name = "小明"
    data.facts.append(FactItem(content="我喜欢咖啡", category="preference", confidence=0.9))
    engine.save_data(data)

    # 哨兵：一旦上下文组装走到向量/embedding 路径就会被调用
    get_provider = MagicMock()
    monkeypatch.setattr(memory_engine_module.llm_adapter, "get_provider", get_provider)

    ctx = engine.build_context_sync(query="咖啡")

    # 档案与事实均被纯文本注入
    assert "用户名字：小明" in ctx
    assert "我喜欢咖啡" in ctx
    assert "记忆事实" in ctx
    # 全程不触发 embedding provider 获取（同步回退分支不含向量召回）
    assert get_provider.call_count == 0


async def test_build_context_falls_back_to_sync_inside_event_loop(engine):
    data = engine.load_data()
    data.profile.name = "小红"
    engine.save_data(data)

    # asyncio_mode=auto 下测试运行于事件循环内：build_context 必须走同步回退分支，
    # 与 build_context_sync 结果一致（若误走 asyncio.run 会抛 RuntimeError）
    ctx = engine.build_context(query="")
    assert ctx == engine.build_context_sync(query="")
    assert "用户名字：小红" in ctx


def test_build_context_sync_empty_memory_returns_empty_string(tmp_path):
    eng = MemoryEngine(storage_path=tmp_path / "empty-mem", agent_id="empty-agent")
    assert eng.build_context_sync() == ""


async def test_inject_memory_builds_user_memory_block(_init_test_db, monkeypatch):
    from app.core.domain_policy import MAIN_AGENT_ID
    from app.engines.memory.memory_engine import get_memory_engine
    from app.services.context_service import ContextService

    engine = get_memory_engine(MAIN_AGENT_ID)
    engine.reset_all()
    data = engine.load_data()
    data.profile.name = "小明"
    engine.save_data(data)

    get_provider = MagicMock()
    monkeypatch.setattr(memory_engine_module.llm_adapter, "get_provider", get_provider)
    monkeypatch.setattr(context_service_module.llm_adapter, "get_provider", get_provider)

    svc = ContextService()
    messages = [{"role": "user", "content": "我叫什么名字？"}]
    out = await svc.inject_memory(
        messages, MAIN_AGENT_ID, "openai", thread_id="conv-inject", llm_adapter=None
    )

    # workbench 域注入 owner 轨：system 消息带 <user_memory> 块，含档案名
    assert out[0]["role"] == "system"
    assert "<user_memory>" in out[0]["content"]
    assert "小明" in out[0]["content"]
    assert out[1] == messages[0]  # 原消息保留
    # 注入走纯文本同步组装（to_thread），不触发 embedding
    assert get_provider.call_count == 0

    # 清理，避免污染全局引擎注册表中的主 Agent 记忆
    engine.reset_all()
