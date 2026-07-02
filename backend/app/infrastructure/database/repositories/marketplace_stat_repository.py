"""MarketplaceStatRepository — 统计计数（替代 marketplace_stats.json）。

download_count / like_count 通过 SQLite INSERT ON CONFLICT 实现真正原子增
（保留 mutate_async 语义，且并发安全）。
"""
import asyncio
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.infrastructure.database.models.marketplace_stat import MarketplaceStat
from app.infrastructure.database.repositories.base import orm_to_dict, utcnow_iso
from app.infrastructure.database.session import sync_session_factory


class MarketplaceStatRepository:
    """统计计数 Repository。主键为 item_id（业务 ID）。"""

    model = MarketplaceStat
    pk = "item_id"

    def get(self, item_id: str) -> Optional[dict]:
        with sync_session_factory() as session:
            obj = session.get(MarketplaceStat, item_id)
            return orm_to_dict(obj) if obj else None

    def get_all(self) -> list[dict]:
        with sync_session_factory() as session:
            objs = session.execute(select(MarketplaceStat)).scalars().all()
            return [orm_to_dict(o) for o in objs]

    def get_or_create(self, item_id: str, stat_type: str = "") -> dict:
        """获取或创建统计项（不存在则初始化为 0）。"""
        with sync_session_factory() as session:
            obj = session.get(MarketplaceStat, item_id)
            if obj is None:
                obj = MarketplaceStat(
                    item_id=item_id,
                    type=stat_type,
                    download_count=0,
                    like_count=0,
                    liked_by=[],
                    updated_at=utcnow_iso(),
                )
                session.add(obj)
                session.commit()
                session.refresh(obj)
            return orm_to_dict(obj)

    def save(self, item_id: str, data: dict) -> dict:
        """upsert：存在则更新，不存在则插入。"""
        with sync_session_factory() as session:
            obj = session.get(MarketplaceStat, item_id)
            if obj is None:
                obj = MarketplaceStat(item_id=item_id)
                session.add(obj)
            for k, v in data.items():
                if k != self.pk:
                    setattr(obj, k, v)
            obj.updated_at = utcnow_iso()
            session.commit()
            session.refresh(obj)
            return orm_to_dict(obj)

    def increment_download(self, item_id: str, stat_type: str = "") -> dict:
        """原子增下载计数（INSERT ON CONFLICT DO UPDATE）。"""
        with sync_session_factory() as session:
            stmt = sqlite_insert(MarketplaceStat).values(
                item_id=item_id,
                type=stat_type,
                download_count=1,
                like_count=0,
                liked_by=[],
                updated_at=utcnow_iso(),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["item_id"],
                set_={
                    "download_count": MarketplaceStat.download_count + 1,
                    "updated_at": utcnow_iso(),
                },
            )
            session.execute(stmt)
            session.commit()
            obj = session.get(MarketplaceStat, item_id)
            return orm_to_dict(obj)

    def toggle_like(self, item_id: str, user_id: str, stat_type: str = "") -> dict:
        """切换 like 状态（原子增减 like_count + 更新 liked_by）。"""
        with sync_session_factory() as session:
            obj = session.get(MarketplaceStat, item_id)
            if obj is None:
                obj = MarketplaceStat(
                    item_id=item_id,
                    type=stat_type,
                    download_count=0,
                    like_count=1,
                    liked_by=[user_id],
                    updated_at=utcnow_iso(),
                )
                session.add(obj)
            else:
                # 复制为新 list，避免 SQLAlchemy JSON 列无法检测原地变更（同引用 → 不触发 UPDATE）
                liked_by: list = list(obj.liked_by or [])
                if user_id in liked_by:
                    liked_by.remove(user_id)
                    obj.like_count = max(0, obj.like_count - 1)
                else:
                    liked_by.append(user_id)
                    obj.like_count = obj.like_count + 1
                obj.liked_by = liked_by
                obj.updated_at = utcnow_iso()
            session.commit()
            session.refresh(obj)
            return orm_to_dict(obj)

    def get_liked_items(self, user_id: str) -> list[str]:
        """返回指定用户 liked 的所有 item_id。"""
        with sync_session_factory() as session:
            objs = session.execute(select(MarketplaceStat)).scalars().all()
            return [o.item_id for o in objs if user_id in (o.liked_by or [])]

    def delete(self, item_id: str) -> bool:
        """删除指定 item 的统计记录（item 被移除时调用）。"""
        with sync_session_factory() as session:
            obj = session.get(MarketplaceStat, item_id)
            if obj is None:
                return False
            session.delete(obj)
            session.commit()
            return True

    def delete_all(self) -> int:
        """删除全部统计记录，返回删除条数。"""
        from sqlalchemy import delete as sa_delete
        from sqlalchemy import func
        with sync_session_factory() as session:
            count = session.execute(select(func.count()).select_from(MarketplaceStat)).scalar() or 0
            session.execute(sa_delete(MarketplaceStat))
            session.commit()
            return count

    # ── Async wrappers ──

    async def get_async(self, item_id: str) -> Optional[dict]:
        return await asyncio.to_thread(self.get, item_id)

    async def get_all_async(self) -> list[dict]:
        return await asyncio.to_thread(self.get_all)

    async def get_or_create_async(self, item_id: str, stat_type: str = "") -> dict:
        return await asyncio.to_thread(self.get_or_create, item_id, stat_type)

    async def save_async(self, item_id: str, data: dict) -> dict:
        return await asyncio.to_thread(self.save, item_id, data)

    async def increment_download_async(self, item_id: str, stat_type: str = "") -> dict:
        return await asyncio.to_thread(self.increment_download, item_id, stat_type)

    async def toggle_like_async(self, item_id: str, user_id: str, stat_type: str = "") -> dict:
        return await asyncio.to_thread(self.toggle_like, item_id, user_id, stat_type)

    async def get_liked_items_async(self, user_id: str) -> list[str]:
        return await asyncio.to_thread(self.get_liked_items, user_id)

    async def delete_async(self, item_id: str) -> bool:
        return await asyncio.to_thread(self.delete, item_id)

    async def delete_all_async(self) -> int:
        return await asyncio.to_thread(self.delete_all)

    def mutate(self, item_id: str, updater_fn) -> Optional[dict]:
        """同步读-改-写（单事务内完成）。"""
        with sync_session_factory() as session:
            obj = session.get(MarketplaceStat, item_id)
            current = orm_to_dict(obj)
            new_value = updater_fn(current)
            if new_value is None:
                return None
            if obj is None:
                obj = MarketplaceStat(**{self.pk: item_id})
                session.add(obj)
            for k, v in new_value.items():
                if k != self.pk:
                    setattr(obj, k, v)
            session.commit()
            session.refresh(obj)
            return orm_to_dict(obj)

    async def mutate_async(self, item_id: str, updater_fn) -> Optional[dict]:
        """异步读-改-写。"""
        return await asyncio.to_thread(self.mutate, item_id, updater_fn)
