"""用量统计本地时区口径测试。

按天聚合（by_day/tokens_by_day）与 start/end 过滤必须使用本机系统时区
（用户在 OS 里设置的时区），而非 UTC——否则 UTC+8 的凌晨 0~8 点数据
会被算到"昨天"。预期值统一用 `astimezone(local_tz())` 独立推导，任何
时区的机器上跑结果都一致。
"""
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import delete as sa_delete

from app.core.utils import local_date_to_utc_boundary, local_tz
from app.infrastructure.database.models.usage_record import UsageRecord
from app.infrastructure.database.repositories.usage_repository import UsageRepository
from app.infrastructure.database.session import sync_session_factory


@pytest.fixture
def repo(_init_test_db):
    r = UsageRepository()
    yield r
    with sync_session_factory() as session:
        session.execute(sa_delete(UsageRecord))
        session.commit()


def _insert(ts_utc: datetime, provider: str) -> None:
    with sync_session_factory() as session:
        session.add(
            UsageRecord(
                timestamp=ts_utc.isoformat(),
                provider=provider,
                model="test-model",
                prompt_tokens=1,
                completion_tokens=1,
                total_tokens=2,
            )
        )
        session.commit()


def _local_midnight_utc() -> datetime:
    """本地"今天 0 点"对应的 UTC 时刻。"""
    local_now = datetime.now(local_tz())
    return local_now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(
        timezone.utc
    )


def _local_date(ts_utc: datetime) -> str:
    return ts_utc.astimezone(local_tz()).date().isoformat()


def test_local_date_boundary_roundtrip():
    """本地日 0 点的 UTC 边界串，换回本地时区必须恰好落在当天 00:00。"""
    boundary = local_date_to_utc_boundary(date(2026, 1, 10))
    dt = datetime.fromisoformat(boundary).astimezone(local_tz())
    assert (dt.year, dt.month, dt.day) == (2026, 1, 10)
    assert dt.hour == 0 and dt.minute == 0 and dt.second == 0


def test_by_day_groups_by_local_date(repo):
    """跨本地日界的两条记录必须分属两个本地日期（旧 UTC 口径会并到一天）。"""
    midnight = _local_midnight_utc()
    before = midnight - timedelta(hours=2)  # 本地昨天 22:00
    after = midnight + timedelta(hours=2)  # 本地今天 02:00
    _insert(before, "tz-day-before")
    _insert(after, "tz-day-after")

    summary = repo.get_summary(days=10)
    d_before, d_after = _local_date(before), _local_date(after)
    assert d_before != d_after
    assert summary["by_day"].get(d_before, 0) >= 1
    assert summary["by_day"].get(d_after, 0) >= 1
    assert summary["tokens_by_day"].get(d_after, 0) >= 2


def test_start_end_filter_uses_local_dates(repo):
    """start/end 是本地日历日：本地今天的记录命中，本地昨天的排除。"""
    midnight = _local_midnight_utc()
    inside = midnight + timedelta(hours=2)  # 本地今天
    outside = midnight - timedelta(hours=2)  # 本地昨天
    _insert(inside, "tz-filter-in")
    _insert(outside, "tz-filter-out")

    d_inside = _local_date(inside)
    summary = repo.get_summary(start=d_inside, end=d_inside)
    providers = {p["name"] for p in summary["by_provider"]}
    assert "tz-filter-in" in providers
    assert "tz-filter-out" not in providers
