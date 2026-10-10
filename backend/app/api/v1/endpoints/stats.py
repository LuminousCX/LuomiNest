from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from loguru import logger

from app.api.v1.deps import get_usage_store
from app.services.usage_tracker import usage_tracker

router = APIRouter(prefix="/stats", tags=["stats"])

# start_date / end_date 的 "YYYY-MM-DD" 格式约束
DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


def _summary_kwargs(days: int | None, start_date: str | None, end_date: str | None) -> dict:
    """组装 get_summary kwargs：给出 start_date/end_date 时优先（days 忽略），否则保持 days 语义不变。"""
    if start_date is not None or end_date is not None:
        return {"days": None, "start": start_date, "end": end_date}
    return {"days": days, "start": None, "end": None}


@router.get("/overview")
async def get_stats_overview(days: int | None = Query(None, ge=1, le=365)):
    logger.info(f"[API] GET /stats/overview - days={days}")
    stats = usage_tracker.get_full_stats(days=days)
    return stats


@router.get("/usage")
async def get_usage_stats(
    days: int | None = Query(None, ge=1, le=365),
    start_date: str | None = Query(None, pattern=DATE_PATTERN),
    end_date: str | None = Query(None, pattern=DATE_PATTERN),
    usage_store=Depends(get_usage_store),
):
    logger.info(f"[API] GET /stats/usage - days={days} start={start_date} end={end_date}")
    return usage_store.get_summary(**_summary_kwargs(days, start_date, end_date))


@router.get("/usage/daily")
async def get_daily_usage(
    days: int = Query(7, ge=1, le=400),
    start_date: str | None = Query(None, pattern=DATE_PATTERN),
    end_date: str | None = Query(None, pattern=DATE_PATTERN),
    usage_store=Depends(get_usage_store),
):
    logger.info(f"[API] GET /stats/usage/daily - days={days} start={start_date} end={end_date}")
    summary = usage_store.get_summary(**_summary_kwargs(days, start_date, end_date))
    return {
        "by_day": summary.get("by_day", {}),
        "tokens_by_day": summary.get("tokens_by_day", {}),
    }


@router.get("/usage/compare")
async def get_usage_compare(
    days: int = Query(7, ge=1, le=90),
    start_date: str | None = Query(None, pattern=DATE_PATTERN),
    end_date: str | None = Query(None, pattern=DATE_PATTERN),
    usage_store=Depends(get_usage_store),
):
    logger.info(f"[API] GET /stats/usage/compare - days={days} start={start_date} end={end_date}")

    if start_date is not None and end_date is not None:
        # 任意区间：previous 取等长的前一个相邻窗口
        start_d = date.fromisoformat(start_date)
        end_d = date.fromisoformat(end_date)
        window_len = (end_d - start_d).days + 1
        prev_end_d = start_d - timedelta(days=1)
        prev_start_d = prev_end_d - timedelta(days=window_len - 1)

        current_summary = usage_store.get_summary(start=start_date, end=end_date)
        previous_summary = usage_store.get_summary(
            start=prev_start_d.isoformat(), end=prev_end_d.isoformat()
        )
        previous_by_day = previous_summary.get("by_day", {})
        previous_requests = previous_summary.get("total_requests", 0)
        previous_tokens = previous_summary.get("total_tokens", 0)
    else:
        current_summary = usage_store.get_summary(days)
        previous_summary = usage_store.get_summary(days * 2)

        current_days = set(current_summary.get("by_day", {}).keys())
        previous_by_day = {
            day: value
            for day, value in previous_summary.get("by_day", {}).items()
            if day not in current_days
        }
        # 保持历史行为：previous = 最近 2N 天总量 - 最近 N 天总量
        previous_requests = previous_summary.get("total_requests", 0) - current_summary.get("total_requests", 0)
        previous_tokens = previous_summary.get("total_tokens", 0) - current_summary.get("total_tokens", 0)

    return {
        "current": {
            "total_requests": current_summary.get("total_requests", 0),
            "total_tokens": current_summary.get("total_tokens", 0),
            "by_day": current_summary.get("by_day", {}),
        },
        "previous": {
            "total_requests": previous_requests,
            "total_tokens": previous_tokens,
            "by_day": previous_by_day,
        },
    }
