from fastapi import APIRouter, Query
from loguru import logger

from app.services.usage_tracker import usage_tracker

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/overview")
async def get_stats_overview(days: int | None = Query(None, ge=1, le=365)):
    logger.info(f"[API] GET /stats/overview - days={days}")
    stats = usage_tracker.get_full_stats(days=days)
    return stats


@router.get("/usage")
async def get_usage_stats(days: int | None = Query(None, ge=1, le=365)):
    logger.info(f"[API] GET /stats/usage - days={days}")
    from app.infrastructure.database.usage_store import usage_store
    return usage_store.get_summary(days)


@router.get("/usage/daily")
async def get_daily_usage(days: int = Query(7, ge=1, le=90)):
    logger.info(f"[API] GET /stats/usage/daily - days={days}")
    from app.infrastructure.database.usage_store import usage_store
    summary = usage_store.get_summary(days)
    return {"by_day": summary.get("by_day", {})}


@router.get("/usage/compare")
async def get_usage_compare(days: int = Query(7, ge=1, le=90)):
    logger.info(f"[API] GET /stats/usage/compare - days={days}")
    from app.infrastructure.database.usage_store import usage_store

    current_summary = usage_store.get_summary(days)
    previous_summary = usage_store.get_summary(days * 2)

    current_days = set(current_summary.get("by_day", {}).keys())
    previous_by_day = {
        day: value
        for day, value in previous_summary.get("by_day", {}).items()
        if day not in current_days
    }

    return {
        "current": {
            "total_requests": current_summary.get("total_requests", 0),
            "total_tokens": current_summary.get("total_tokens", 0),
            "by_day": current_summary.get("by_day", {}),
        },
        "previous": {
            "total_requests": previous_summary.get("total_requests", 0) - current_summary.get("total_requests", 0),
            "total_tokens": previous_summary.get("total_tokens", 0) - current_summary.get("total_tokens", 0),
            "by_day": previous_by_day,
        },
    }
