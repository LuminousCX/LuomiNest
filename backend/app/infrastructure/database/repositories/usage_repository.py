"""UsageRepository — LLM 用量记录（替代 usage_records.json）。

聚合统计用 SQL GROUP BY（替代 Python 全表扫描）。
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import delete as sa_delete, func, select

from app.core.utils import local_date_to_utc_boundary, utc_now, utc_now_dt
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
        conversation_id: Optional[str] = None,
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
            conv_id=conversation_id,  # ORM/DB 列名为 conv_id（迁移需 review，保持不动）
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
                cutoff = (utc_now_dt() - timedelta(days=days)).isoformat()
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

    @staticmethod
    def _resolve_time_range(
        days: Optional[int],
        start: Optional[str],
        end: Optional[str],
    ) -> tuple[Optional[str], Optional[str]]:
        """解析查询窗口：返回 (下界 cutoff, 互斥上界 end_exclusive)。

        - start/end 为 "YYYY-MM-DD" 的**本地日历日**闭区间（用户在界面上选的
          "今天/昨天/上个月"即本地日期），按本机系统时区换算成 UTC 边界过滤；
          给出时优先于 days；
        - days 为"最近 N 天"，滚动窗口与时区无关，行为与历史版本一致。
        """
        if start is not None or end is not None:
            cutoff = None
            end_exclusive = None
            if start is not None:
                cutoff = local_date_to_utc_boundary(
                    datetime.strptime(start, "%Y-%m-%d").date()
                )
            if end is not None:
                end_exclusive = local_date_to_utc_boundary(
                    datetime.strptime(end, "%Y-%m-%d").date() + timedelta(days=1)
                )
            return cutoff, end_exclusive
        if days is not None:
            return (utc_now_dt() - timedelta(days=days)).isoformat(), None
        return None, None

    def get_summary(
        self,
        days: Optional[int] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> dict:
        """SQL GROUP BY 聚合统计。

        days 与 start/end 二选一（start/end 优先，见 _resolve_time_range）；
        返回新增 tokens_by_day（按天 token 求和），by_day 结构保持 {day: count} 不变。
        按天聚合使用**本机系统时区**（SQLite localtime 修饰符），与前端
        "今天/昨天"等本地日期口径一致；历史版本按 UTC 日期前缀分组。
        """
        cutoff, end_exclusive = self._resolve_time_range(days, start, end)

        def _in_range(stmt):
            if cutoff is not None:
                stmt = stmt.where(UsageRecord.timestamp >= cutoff)
            if end_exclusive is not None:
                stmt = stmt.where(UsageRecord.timestamp < end_exclusive)
            return stmt

        with sync_session_factory() as session:
            # 汇总
            total_stmt = select(
                func.count().label("total_requests"),
                func.sum(UsageRecord.prompt_tokens).label("total_prompt"),
                func.sum(UsageRecord.completion_tokens).label("total_completion"),
                func.sum(UsageRecord.total_tokens).label("total_tokens"),
            )
            total_stmt = _in_range(total_stmt)
            total = session.execute(total_stmt).one()

            # 按 provider 聚合
            provider_stmt = select(
                UsageRecord.provider.label("name"),
                func.count().label("requests"),
                func.sum(UsageRecord.prompt_tokens).label("prompt_tokens"),
                func.sum(UsageRecord.completion_tokens).label("completion_tokens"),
                func.sum(UsageRecord.total_tokens).label("total_tokens"),
            ).group_by(UsageRecord.provider)
            provider_stmt = _in_range(provider_stmt)
            provider_rows = session.execute(provider_stmt).all()

            # 按天聚合（同一条 GROUP BY 同时求每天 count 与 token 求和）。
            # timestamp 存的是 UTC ISO 串，datetime(..., 'localtime') 按本机系统时区
            # 转换后再取日期，保证"哪一天的用量"与用户本地日历一致。
            local_day = func.substr(
                func.datetime(UsageRecord.timestamp, "localtime"), 1, 10
            )
            day_stmt = select(
                local_day.label("day"),
                func.count().label("count"),
                func.sum(UsageRecord.total_tokens).label("tokens"),
            ).group_by(local_day)
            day_stmt = _in_range(day_stmt)
            day_rows = session.execute(day_stmt).all()

            # 最近记录：最近 20 条，按时间倒序（最新在前）
            # 注：原 UsageStore 用 recent[-20:] 实为取最旧 20 条，与"最近"语义矛盾，此处修正
            recent_stmt = select(UsageRecord).order_by(UsageRecord.timestamp.desc()).limit(20)
            recent_stmt = _in_range(recent_stmt)
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
                "tokens_by_day": {r.day: (r.tokens or 0) for r in day_rows},
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

    async def get_summary_async(
        self,
        days: Optional[int] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> dict:
        return await asyncio.to_thread(self.get_summary, days, start, end)

    async def clear_all_async(self) -> int:
        return await asyncio.to_thread(self.clear_all)

    async def trim_async(self, max_records: int) -> int:
        return await asyncio.to_thread(self.trim, max_records)
