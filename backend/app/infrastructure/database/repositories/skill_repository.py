"""SkillRepository — skills 表持久化索引（洋葱架构 §11.1）。

skills 表是 SKILL.md 文件体系的附加索引（文件为权威源）：
- loader 每次启动全量 upsert（§16.1 风险缓解：表与文件不一致时以文件为准）
- 提供列表过滤查询（category/keyword/enabled），供工具与后续 API 使用
"""
import asyncio
import json
from typing import Optional

from sqlalchemy import delete as sa_delete
from sqlalchemy import select

from app.infrastructure.database.models.skill import SkillORM
from app.infrastructure.database.repositories.base import BaseRepository, orm_to_dict, utcnow_iso
from app.infrastructure.database.session import sync_session_factory


class SkillRepository(BaseRepository):
    """skills 表 Repository。主键为 skill_id（业务 ID，kebab-case）。"""

    model = SkillORM
    pk = "id"

    # ── upsert（保留 created_at，刷新 updated_at）──

    def upsert_skill(self, skill_id: str, data: dict) -> dict:
        """upsert 单条技能索引：存在则更新（保留 created_at），不存在则插入。"""
        now = utcnow_iso()
        with sync_session_factory() as session:
            obj = session.get(SkillORM, skill_id)
            if obj is None:
                obj = SkillORM(id=skill_id, created_at=now)
                session.add(obj)
            for k, v in data.items():
                if k not in (self.pk, "created_at"):
                    setattr(obj, k, v)
            obj.updated_at = now
            session.commit()
            session.refresh(obj)
            return orm_to_dict(obj)

    async def upsert_skill_async(self, skill_id: str, data: dict) -> dict:
        return await asyncio.to_thread(self.upsert_skill, skill_id, data)

    # ── 查询 ──

    def list_filtered(
        self,
        category: Optional[str] = None,
        keyword: Optional[str] = None,
        enabled_only: bool = False,
    ) -> list[dict]:
        """按条件过滤技能索引。

        Args:
            category: 精确匹配 category（大小写不敏感）
            keyword: 子串匹配 id/name/description/tags（大小写不敏感）
            enabled_only: 仅返回 enabled=1 的行
        """
        with sync_session_factory() as session:
            objs = session.execute(select(SkillORM)).scalars().all()
            rows = [orm_to_dict(o) for o in objs]

        if enabled_only:
            rows = [r for r in rows if r.get("enabled")]
        if category:
            category_lower = category.casefold()
            rows = [r for r in rows if (r.get("category") or "").casefold() == category_lower]
        if keyword:
            kw = keyword.casefold()

            def _hit(r: dict) -> bool:
                if kw in (r.get("id") or "").casefold():
                    return True
                if kw in (r.get("name") or "").casefold():
                    return True
                if kw in (r.get("description") or "").casefold():
                    return True
                try:
                    tags = json.loads(r.get("tags") or "[]")
                except (TypeError, ValueError):
                    tags = []
                return any(kw in str(t).casefold() for t in tags)

            rows = [r for r in rows if _hit(r)]
        return rows

    async def list_filtered_async(
        self,
        category: Optional[str] = None,
        keyword: Optional[str] = None,
        enabled_only: bool = False,
    ) -> list[dict]:
        return await asyncio.to_thread(self.list_filtered, category, keyword, enabled_only)

    # ── 清理（文件为权威源：表中多余行删除）──

    def prune_stale(self, keep_ids: set[str]) -> int:
        """删除不在 keep_ids 中的行（文件已不存在的技能索引），返回删除数量。"""
        with sync_session_factory() as session:
            objs = session.execute(select(SkillORM)).scalars().all()
            stale = [o for o in objs if o.id not in keep_ids]
            for obj in stale:
                session.delete(obj)
            session.commit()
            return len(stale)

    async def prune_stale_async(self, keep_ids: set[str]) -> int:
        return await asyncio.to_thread(self.prune_stale, keep_ids)

    def delete_all_rows(self) -> int:
        """删除全部行，返回删除数量。"""
        with sync_session_factory() as session:
            objs = session.execute(select(SkillORM)).scalars().all()
            session.execute(sa_delete(SkillORM))
            session.commit()
            return len(objs)


# 全局单例
skill_repository = SkillRepository()
