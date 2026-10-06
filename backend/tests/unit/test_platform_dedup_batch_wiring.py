"""平台链路「接线债」P1-1 回归锁：全局消息去重 + TextBatchAggregator 批聚合接线。

覆盖（对照任务验收项）：
- 同键重推只回一次：同 message_id+同载荷的重复推送在 router 入口被丢弃
  （微信系 5s 无响应重推 / QQ 官方事件重发 / Discord Resume 重放的兜底）；
- 不同消息正常通过：不同 message_id（或弱 id 但载荷不同）均放行；
- 缓存有界：MessageDeduplicator 超过 max_size 后条目数不增长（LRU 淘汰），
  TTL 过期后同键可再次通过；
- 聚合窗口合并多条：message_batch_enabled 开启后，同一发送者窗口期内
  的连续短文本合并为一次路由、一次回复；默认关闭时行为不变。
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.runtime.platform.base import PlatformMessage, PlatformResponse
from app.runtime.platform.infrastructure.dedup import MessageDeduplicator
from app.runtime.platform.infrastructure.message_batch import TextBatchAggregator
from app.runtime.platform.platform_logger import platform_logger
from app.services.platform_router import (
    MESSAGE_BATCH_ENABLED_KEY,
    LuomiNestPlatformRouter,
)
import app.services.platform_router as platform_router_module


# ------------------------------------------------------------------
# 公共夹具
# ------------------------------------------------------------------


def _msg(
    content: str = "你好",
    message_id: str = "m1",
    user_id: str = "u100",
    session_id: str = "s1",
    instance_key: str = "",
    image_urls: list[str] | None = None,
) -> PlatformMessage:
    return PlatformMessage(
        platform="qq_onebot",
        user_id=user_id,
        content=content,
        session_id=session_id,
        message_id=message_id,
        sender_name="测试用户",
        image_urls=image_urls or [],
    )


@pytest.fixture()
def router(monkeypatch):
    """构造干净的 router：打桩 get_instance / 人设加载 / LLM 路由，隔离重 IO。"""
    r = LuomiNestPlatformRouter()
    monkeypatch.setattr(platform_router_module, "get_instance", lambda instance_id: None)
    monkeypatch.setattr(
        platform_router_module, "load_luominest_main_agent_config",
        lambda: {"name": "主Agent"},
    )
    r._route_to_main_agent = AsyncMock(return_value=PlatformResponse(content="ok"))
    yield r
    r._deduplicator.clear()


def _patch_batch_enabled(monkeypatch, enabled: bool):
    """将 get_instance 替换为返回携带批聚合并关配置的桩实例。"""
    monkeypatch.setattr(
        platform_router_module,
        "get_instance",
        lambda instance_id: SimpleNamespace(
            adapter_type="qq_onebot",
            config={MESSAGE_BATCH_ENABLED_KEY: enabled},
        ),
    )


def _cleanup_logs(instance_id: str) -> None:
    platform_logger.clear_logs(instance_id)


# ------------------------------------------------------------------
# 1. 去重接线：同键重推只回一次
# ------------------------------------------------------------------


async def test_duplicate_push_routed_once(router):
    inst_id = "inst_dup_once"
    msg = _msg(message_id="wx_msg_1")

    first = await router.handle_platform_message(msg, inst_id)
    second = await router.handle_platform_message(msg, inst_id)  # 平台 5s 重推同一载荷

    assert first is not None and first.content == "ok"
    assert second is None, "重复推送应被丢弃，不再触发第二次回复"
    assert router._route_to_main_agent.await_count == 1

    events = [e["event"] for e in platform_logger.get_logs(inst_id)["entries"]]
    assert "duplicate_dropped" in events
    _cleanup_logs(inst_id)


async def test_same_id_different_payload_both_pass(router):
    """弱回退 id（如 minecraft ss_{秒级时间戳}）撞 id 但载荷不同：不得误杀。"""
    inst_id = "inst_dup_weakid"
    m1 = _msg(content="截图", message_id="ss_1728000000")
    m2 = _msg(content="帮我看下这个", message_id="ss_1728000000")

    r1 = await router.handle_platform_message(m1, inst_id)
    r2 = await router.handle_platform_message(m2, inst_id)

    assert r1 is not None and r2 is not None
    assert router._route_to_main_agent.await_count == 2
    _cleanup_logs(inst_id)


async def test_different_messages_pass_through(router):
    inst_id = "inst_dup_diff"
    r1 = await router.handle_platform_message(_msg(message_id="m1"), inst_id)
    r2 = await router.handle_platform_message(_msg(message_id="m2", content="在吗"), inst_id)

    assert r1 is not None and r2 is not None
    assert router._route_to_main_agent.await_count == 2
    assert not any(
        e["event"] == "duplicate_dropped"
        for e in platform_logger.get_logs(inst_id)["entries"]
    )
    _cleanup_logs(inst_id)


async def test_empty_message_id_skips_dedup(router):
    """message_id 为空的适配器不参与去重（无法构造可靠键，保持原语义）。"""
    inst_id = "inst_dup_empty"
    r1 = await router.handle_platform_message(_msg(message_id=""), inst_id)
    r2 = await router.handle_platform_message(_msg(message_id=""), inst_id)

    assert r1 is not None and r2 is not None
    assert router._route_to_main_agent.await_count == 2
    _cleanup_logs(inst_id)


async def test_same_id_across_instances_both_pass(router):
    """去重键含实例前缀：不同实例的同名消息 id 互不影响。"""
    msg = _msg(message_id="shared_id")
    r1 = await router.handle_platform_message(msg, "inst_a")
    r2 = await router.handle_platform_message(msg, "inst_b")

    assert r1 is not None and r2 is not None
    assert router._route_to_main_agent.await_count == 2
    _cleanup_logs("inst_a")
    _cleanup_logs("inst_b")


# ------------------------------------------------------------------
# 2. 去重缓存有界（超限不涨）+ TTL 过期
# ------------------------------------------------------------------


def test_dedup_cache_bounded_by_max_size():
    d = MessageDeduplicator(max_size=3, ttl=60.0)
    for i in range(5):
        assert d.check_and_mark(f"m{i}") is False  # 均为新消息

    assert d.size == 3, "缓存超过 max_size 后条目数不应继续增长"
    # 最旧的 m0/m1 已被 LRU 淘汰：可再次作为新消息通过
    assert d.check_and_mark("m0") is False
    assert d.size == 3


def test_dedup_same_key_within_ttl_is_duplicate():
    d = MessageDeduplicator(max_size=10, ttl=60.0)
    assert d.check_and_mark("m1") is False
    assert d.check_and_mark("m1") is True
    assert d.check_and_mark("m2") is False
    assert d.check_and_mark("m2") is True


def test_dedup_key_reusable_after_ttl_expiry():
    d = MessageDeduplicator(max_size=10, ttl=0.05)
    assert d.check_and_mark("m1") is False
    assert d.check_and_mark("m1") is True
    asyncio.run(asyncio.sleep(0.06))
    assert d.check_and_mark("m1") is False, "TTL 过期后同键应视为新消息"


def test_dedup_empty_key_never_marked():
    d = MessageDeduplicator(max_size=10, ttl=60.0)
    assert d.check_and_mark("") is False
    assert d.check_and_mark("") is False
    assert d.size == 0


# ------------------------------------------------------------------
# 3. 批聚合：窗口合并多条（默认关闭）
# ------------------------------------------------------------------


async def test_batch_aggregation_merges_fragments(monkeypatch, router):
    _patch_batch_enabled(monkeypatch, True)
    router._batch_aggregator = TextBatchAggregator(aggregation_window=0.2)

    m1 = _msg(content="你好", message_id="b1")
    m2 = _msg(content="在吗", message_id="b2")
    results = await asyncio.gather(
        router.handle_platform_message(m1, "inst_batch"),
        router.handle_platform_message(m2, "inst_batch"),
    )

    # 一个批次恰好一次回复，聚合文本按到达顺序拼接
    assert router._route_to_main_agent.await_count == 1
    routed_msg = router._route_to_main_agent.await_args.args[0]
    assert routed_msg.content == "你好在吗"
    replies = [r for r in results if r is not None]
    assert len(replies) == 1 and replies[0].content == "ok"

    events = [e["event"] for e in platform_logger.get_logs("inst_batch")["entries"]]
    assert "messages_aggregated" in events
    _cleanup_logs("inst_batch")


async def test_batch_disabled_by_default_routes_individually(monkeypatch, router):
    """默认关闭：同样的两条消息各自独立回复（行为与接线前一致）。"""
    _patch_batch_enabled(monkeypatch, False)

    m1 = _msg(content="你好", message_id="c1")
    m2 = _msg(content="在吗", message_id="c2")
    await asyncio.gather(
        router.handle_platform_message(m1, "inst_batch_off"),
        router.handle_platform_message(m2, "inst_batch_off"),
    )

    assert router._route_to_main_agent.await_count == 2
    contents = [call.args[0].content for call in router._route_to_main_agent.await_args_list]
    assert sorted(contents) == ["你好", "在吗"]
    _cleanup_logs("inst_batch_off")


async def test_batch_skips_commands_and_images(monkeypatch, router):
    """命令与图片消息不参与聚合，立即按原内容路由。"""
    _patch_batch_enabled(monkeypatch, True)
    router._batch_aggregator = TextBatchAggregator(aggregation_window=30.0)

    cmd = _msg(content="/status", message_id="cmd1")
    img = _msg(content="看这张", message_id="img1", image_urls=["https://example.com/a.png"])

    r1 = await router.handle_platform_message(cmd, "inst_batch_skip")
    r2 = await router.handle_platform_message(img, "inst_batch_skip")

    assert r1 is not None and r2 is not None
    assert router._route_to_main_agent.await_count == 2
    routed_contents = [c.args[0].content for c in router._route_to_main_agent.await_args_list]
    assert routed_contents == ["/status", "看这张"]
    _cleanup_logs("inst_batch_skip")


# ------------------------------------------------------------------
# 4. TextBatchAggregator 语义（窗口过期 / max_length 触发）
# ------------------------------------------------------------------


def test_aggregator_flush_joins_fragments():
    agg = TextBatchAggregator(aggregation_window=60.0)
    assert agg.add_message("u1", "你好") is None
    assert agg.add_message("u1", "在吗") is None
    assert agg.flush("u1") == "你好在吗"
    assert agg.flush("u1") is None  # 已取走，不重复


def test_aggregator_window_expiry_returns_previous_batch():
    agg = TextBatchAggregator(aggregation_window=0.05)
    assert agg.add_message("u1", "第一条") is None
    asyncio.run(asyncio.sleep(0.06))
    # 窗口已过期：add 直接刷新旧缓冲并返回旧批次，"第二条" 开启新批次
    assert agg.add_message("u1", "第二条") == "第一条"
    assert agg.flush("u1") == "第二条"


def test_aggregator_max_length_triggers_early_flush():
    agg = TextBatchAggregator(aggregation_window=60.0, max_length=5)
    assert agg.add_message("u1", "123") is None
    assert agg.add_message("u1", "45") == "12345"  # 达到 max_length 立即返回
    assert agg.flush("u1") is None
