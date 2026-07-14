"""UsageRepository — LLM 用量记录（替代 usage_records.json）。

聚合统计用 SQL GROUP BY（替代 Python 全表扫描）。
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete as sa_delete, func, select

from app.core.utils import utc_now
from app.infrastructure.database.models.usage_record import UsageRecord
from app.infrastructure.database.session import sync_session_factory


class UsageRepository:
    """用量记录 Repository。"""

    model = UsageRecord

    def record(
        self,
        provider: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        agent_id: Optional[str] = None,
        conv_id: Optional[str] = None,
        is_stream: bool = False,
    ) -> dict:
        """记录一次用量。"""
        entry = UsageRecord(
            timestamp=utc_now(),
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            agent_id=agent_id,
            conv_id=conv_id,
            is_stream=is_stream,
        )
        with sync_session_factory() as session:
            session.add(entry)
            session.commit()
            session.refresh(entry)
            from app.infrastructure.database.repositories.base import orm_to_dict
            return orm_to_dict(entry)

    def get_records(self, days: Optional[int] = None) -> list[dict]:
        with sync_session_factory() as session:
            stmt = select(UsageRecord)
            if days is not None:
                cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
                stmt = stmt.where(UsageRecord.timestamp >= cutoff)
            objs = session.execute(stmt).scalars().all()
            from app.infrastructure.database.repositories.base import orm_to_dict
            return [orm_to_dict(o) for o in objs]

    def bulk_import(self, records: list[dict]) -> int:
        """批量导入用量记录（保留原始 timestamp，供迁移器使用）。返回导入条数。"""
        if not records:
            return 0
        with sync_session_factory() as session:
            for rec in records:
                entry = UsageRecord(
                    timestamp=rec.get("timestamp", utc_now()),
                    provider=rec.get("provider", ""),
                    model=rec.get("model", ""),
                    prompt_tokens=rec.get("prompt_tokens", 0),
                    completion_tokens=rec.get("completion_tokens", 0),
                    total_tokens=rec.get("total_tokens", 0),
                    agent_id=rec.get("agent_id"),
                    conv_id=rec.get("conv_id"),
                    is_stream=rec.get("is_stream", False),
                )
                session.add(entry)
            session.commit()
            return len(records)

    def clear_all(self) -> int:
        """清空所有用量记录（管理重置用）。返回删除条数。"""
        with sync_session_factory() as session:
            count = session.execute(select(func.count()).select_from(UsageRecord)).scalar() or 0
            session.execute(sa_delete(UsageRecord))
            session.commit()
            return count

    def trim(self, max_records: int) -> int:
        """保留最新 max_records 条记录，删除超出的旧记录。返回删除条数。"""
        with sync_session_factory() as session:
            total = session.execute(select(func.count()).select_from(UsageRecord)).scalar() or 0
            if total <= max_records:
                return 0
            # 找出要保留的记录 ID（按时间倒序取前 max_records 条）
            keep_ids = select(UsageRecord.id).order_by(UsageRecord.timestamp.desc()).limit(max_records)
            # 删除不在保留列表中的记录
            result = session.execute(
                sa_delete(UsageRecord).where(UsageRecord.id.not_in(keep_ids))
            )
            session.commit()
            return result.rowcount or 0

    def get_summary(self, days: Optional[int] = None) -> dict:
        """SQL GROUP BY 聚合统计。"""
        cutoff = None
        if days is not None:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        with sync_session_factory() as session:
            # 汇总
            total_stmt = select(
                func.count().label("total_requests"),
                func.sum(UsageRecord.prompt_tokens).label("total_prompt"),
                func.sum(UsageRecord.completion_tokens).label("total_completion"),
                func.sum(UsageRecord.total_tokens).label("total_tokens"),
            )
            if cutoff:
                total_stmt = total_stmt.where(UsageRecord.timestamp >= cutoff)
            total = session.execute(total_stmt).one()

            # 按 provider 聚合
            provider_stmt = select(
                UsageRecord.provider.label("name"),
                func.count().label("requests"),
                func.sum(UsageRecord.prompt_tokens).label("prompt_tokens"),
                func.sum(UsageRecord.completion_tokens).label("completion_tokens"),
                func.sum(UsageRecord.total_tokens).label("total_tokens"),
            ).group_by(UsageRecord.provider)
            if cutoff:
                provider_stmt = provider_stmt.where(UsageRecord.timestamp >= cutoff)
            provider_rows = session.execute(provider_stmt).all()

            # 按天聚合
            day_stmt = select(
                func.substr(UsageRecord.timestamp, 1, 10).label("day"),
                func.count().label("count"),
            ).group_by("day")
            if cutoff:
                day_stmt = day_stmt.where(UsageRecord.timestamp >= cutoff)
            day_rows = session.execute(day_stmt).all()

            # 最近记录：最近 20 条，按时间倒序（最新在前）
            # 注：原 UsageStore 用 recent[-20:] 实为取最旧 20 条，与"最近"语义矛盾，此处修正
            recent_stmt = select(UsageRecord).order_by(UsageRecord.timestamp.desc()).limit(20)
            if cutoff:
                recent_stmt = recent_stmt.where(UsageRecord.timestamp >= cutoff)
            recent_objs = session.execute(recent_stmt).scalars().all()
            recent_list = list(recent_objs)

            return {
                "total_requests": total.total_requests or 0,
                "total_prompt_tokens": total.total_prompt or 0,
                "total_completion_tokens": total.total_completion or 0,
                "total_tokens": total.total_tokens or 0,
                "by_provider": [
                    {
                        "name": r.name or "unknown",
                        "requests": r.requests,
                        "prompt_tokens": r.prompt_tokens or 0,
                        "completion_tokens": r.completion_tokens or 0,
                        "total_tokens": r.total_tokens or 0,
                    }
                    for r in provider_rows
                ],
                "by_day": {r.day: r.count for r in day_rows},
                "recent": [
                    {
                        "timestamp": r.timestamp,
                        "provider": r.provider,
                        "model": r.model,
                        "total_tokens": r.total_tokens,
                        "conv_id": r.conv_id,
                    }
                    for r in recent_list
                ],
            }

    # ── Async wrappers ──

    async def record_async(self, **kwargs) -> dict:
        return await asyncio.to_thread(self.record, **kwargs)

    async def get_records_async(self, days: Optional[int] = None) -> list[dict]:
        return await asyncio.to_thread(self.get_records, days)

    async def get_summary_async(self, days: Optional[int] = None) -> dict:
        return await asyncio.to_thread(self.get_summary, days)

    async def clear_all_async(self) -> int:
        return await asyncio.to_thread(self.clear_all)

    async def trim_async(self, max_records: int) -> int:
        return await asyncio.to_thread(self.trim, max_records)
