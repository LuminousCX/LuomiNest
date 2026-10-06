"""ConversationRepository 回归测试（临时 SQLite，走真实建表与 SQL 层逻辑）。

覆盖：
- get_paginated：keyset 分页（seq 游标 + limit）、has_more、total_messages、页内时间正序
- 非法 before_id 兜底为"最新一页"
- append_message：O(1) 追加 + search_text/last_message 增量维护 + search 命中与 snippet
- count_messages：JOIN 聚合 + 软删除排除
"""

import pytest
from sqlalchemy import delete as sa_delete, select

from app.infrastructure.database.models.conversation import Conversation
from app.infrastructure.database.models.conversation_message import ConversationMessage
from app.infrastructure.database.repositories import ConversationRepository
from app.infrastructure.database.session import sync_session_factory


@pytest.fixture
def repo(_init_test_db):
    r = ConversationRepository()
    yield r
    # 清空对话与消息行，保证用例间/两遍运行互不污染
    with sync_session_factory() as session:
        session.execute(sa_delete(ConversationMessage))
        session.execute(sa_delete(Conversation))
        session.commit()


def _messages(n: int) -> list[dict]:
    return [
        {"id": f"m{i}", "role": "user" if i % 2 == 0 else "assistant", "content": f"消息{i}"}
        for i in range(n)
    ]


def test_keyset_pagination_semantics(repo):
    repo.save("conv-page", {"title": "分页", "messages": _messages(7)})

    # 默认游标：最新 3 条，页内按时间正序
    page1 = repo.get_paginated("conv-page", limit=3)
    assert [m["id"] for m in page1["messages"]] == ["m4", "m5", "m6"]
    assert page1["total_messages"] == 7
    assert page1["has_more"] is True

    # 以本页最早一条的 id 为游标，取更早一页
    page2 = repo.get_paginated("conv-page", limit=3, before_id="m4")
    assert [m["id"] for m in page2["messages"]] == ["m1", "m2", "m3"]
    assert page2["has_more"] is True

    page3 = repo.get_paginated("conv-page", limit=3, before_id="m1")
    assert [m["id"] for m in page3["messages"]] == ["m0"]
    assert page3["has_more"] is False

    # 三页拼起来恰好是完整历史（页序从新到旧），无重叠
    ids = [m["id"] for m in page3["messages"] + page2["messages"] + page1["messages"]]
    assert ids == [f"m{i}" for i in range(7)]


def test_pagination_invalid_before_id_falls_back_to_latest(repo):
    repo.save("conv-cursor", {"title": "游标", "messages": _messages(5)})

    # 游标 id 不存在：按"最新一页"处理（has_more 按 total > limit 判定）
    page = repo.get_paginated("conv-cursor", limit=2, before_id="not-exist-id")
    assert [m["id"] for m in page["messages"]] == ["m3", "m4"]
    assert page["has_more"] is True

    # limit 覆盖全量时 has_more 为 False
    full = repo.get_paginated("conv-cursor", limit=10)
    assert len(full["messages"]) == 5
    assert full["has_more"] is False


def test_append_message_updates_search_text_and_search(repo):
    repo.save("conv-append", {"title": "咖啡偏好", "messages": []})

    assert repo.append_message(
        "conv-append", {"id": "a1", "role": "user", "content": "我喜欢喝咖啡"}
    ) is True
    assert repo.append_message(
        "conv-append", {"id": "a2", "role": "assistant", "content": "记住了，你喜欢咖啡"}
    ) is True

    conv = repo.get("conv-append")
    # get() 不回传 search_text 重列，从 DB 直查增量维护结果
    from sqlalchemy import select

    with sync_session_factory() as session:
        search_text = session.execute(
            select(Conversation.search_text).where(Conversation.id == "conv-append")
        ).scalar_one()
    assert "我喜欢喝咖啡" in search_text
    assert "你喜欢咖啡" in search_text
    # last_message 取最后一条前 50 字
    assert conv["last_message"] == "记住了，你喜欢咖啡"

    # 搜索命中并给出 snippet
    hits = repo.search("咖啡")
    assert [h["id"] for h in hits] == ["conv-append"]
    assert "咖啡" in hits[0]["snippet"]

    # 空关键词不参与搜索
    assert repo.search("") == []

    # 不存在的对话：追加失败返回 False，而不是静默建会话
    assert repo.append_message("conv-ghost", {"role": "user", "content": "hi"}) is False


def test_count_messages_join_aggregates_and_skips_soft_deleted(repo):
    repo.save("conv-a", {"title": "A", "agent_id": "agent-1", "messages": _messages(3)})
    repo.save("conv-b", {"title": "B", "agent_id": "agent-1", "messages": _messages(2)})
    repo.save("conv-c", {"title": "C", "agent_id": "agent-2", "messages": _messages(5)})

    assert repo.count_messages() == 10
    assert repo.count_messages(agent_id="agent-1") == 5
    assert repo.count_messages(agent_id="agent-2") == 5

    # 软删除后聚合排除该对话（JOIN conversations.deleted_at IS NULL）
    assert repo.soft_delete("conv-c") is True
    assert repo.count_messages() == 5
    assert repo.count_messages(agent_id="agent-2") == 0


def test_user_message_id_roundtrip_and_delete_by_id(repo):
    """user 消息持久 id 回归（链路审查 P1-6）：落库行 mid/data.id 同一 uuid、
    读回带出；按 id 删除（DELETE /messages/{id} → 全量替换重建行）后消失。"""
    repo.save("conv-id", {"title": "ID", "messages": []})
    assert repo.append_message(
        "conv-id", {"id": "user-uuid-1", "role": "user", "content": "带 id 用户消息"}
    ) is True

    # 读回：消息 dict 带原 id（data JSON 与 mid 列一致）
    conv = repo.get("conv-id")
    assert [m["id"] for m in conv["messages"]] == ["user-uuid-1"]
    # 分页游标（before_id）按 user 消息 id 定位
    page = repo.get_paginated("conv-id", limit=10, before_id="user-uuid-1")
    assert page["messages"] == []

    # 删除端点语义：按 id 过滤后全量替换 → 消息行重建，目标行消失
    conv["messages"] = [m for m in conv["messages"] if m["id"] != "user-uuid-1"]
    repo.save("conv-id", conv)
    assert repo.get("conv-id")["messages"] == []
    with sync_session_factory() as session:
        remain = session.execute(
            select(ConversationMessage).where(ConversationMessage.conversation_id == "conv-id")
        ).scalars().all()
    assert remain == []
