"""ProviderModelRepository — 供应商模型元信息仓储。

提供按 provider 查询、批量保存、按模型 ID 更新等能力。
"""
import asyncio
import uuid
from typing import Optional

from sqlalchemy import select

from app.infrastructure.database.models.provider_model import ProviderModel
from app.infrastructure.database.repositories.base import BaseRepository, orm_to_dict, utcnow_iso
from app.infrastructure.database.session import sync_session_factory


class ProviderModelRepository(BaseRepository):
    """供应商模型元信息仓储。"""

    model = ProviderModel
    pk = "id"

    def get_by_provider(self, provider_id: str) -> list[dict]:
        """返回某供应商下的所有模型。"""
        with sync_session_factory() as session:
            objs = session.execute(
                select(ProviderModel)
                .where(ProviderModel.provider_id == provider_id)
                .order_by(ProviderModel.name, ProviderModel.model_id)
            ).scalars().all()
            return [orm_to_dict(o) for o in objs]

    def get_by_provider_model(self, provider_id: str, model_id: str) -> Optional[dict]:
        """返回指定 provider + model 的记录。"""
        with sync_session_factory() as session:
            obj = session.execute(
                select(ProviderModel)
                .where(ProviderModel.provider_id == provider_id)
                .where(ProviderModel.model_id == model_id)
            ).scalars().first()
            return orm_to_dict(obj)

    def save_models(self, provider_id: str, models: list[dict]) -> list[dict]:
        """批量保存/更新模型列表；返回保存后的记录。

        幂等：相同 (provider_id, model_id) 会更新 name / max_context_tokens，
        但不会覆盖用户已设置的 enabled 值。
        """
        if not models:
            return []

        now = utcnow_iso()
        saved = []
        with sync_session_factory() as session:
            for m in models:
                model_id = m.get("id") or m.get("model_id", "")
                if not model_id:
                    continue
                name = m.get("name") or model_id
                max_context = int(m.get("max_context_tokens", 0) or 0)

                existing = session.execute(
                    select(ProviderModel)
                    .where(ProviderModel.provider_id == provider_id)
                    .where(ProviderModel.model_id == model_id)
                ).scalars().first()

                if existing is not None:
                    existing.name = name
                    if max_context > 0:
                        existing.max_context_tokens = max_context
                    existing.updated_at = now
                    session.commit()
                    session.refresh(existing)
                    saved.append(orm_to_dict(existing))
                else:
                    obj = ProviderModel(
                        id=uuid.uuid4().hex,
                        provider_id=provider_id,
                        model_id=model_id,
                        name=name,
                        enabled=True,
                        max_context_tokens=max_context,
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(obj)
                    session.commit()
                    session.refresh(obj)
                    saved.append(orm_to_dict(obj))
        return saved

    def update_by_provider_model(
        self,
        provider_id: str,
        model_id: str,
        updates: dict,
    ) -> Optional[dict]:
        """按 provider_id + model_id 更新模型配置。"""
        with sync_session_factory() as session:
            obj = session.execute(
                select(ProviderModel)
                .where(ProviderModel.provider_id == provider_id)
                .where(ProviderModel.model_id == model_id)
            ).scalars().first()
            if obj is None:
                return None
            for k, v in updates.items():
                if k in {"provider_id", "model_id", "id"}:
                    continue
                setattr(obj, k, v)
            obj.updated_at = utcnow_iso()
            session.commit()
            session.refresh(obj)
            return orm_to_dict(obj)

    def delete_by_provider(self, provider_id: str) -> int:
        """删除某供应商下的所有模型记录，返回删除数量。"""
        from sqlalchemy import delete as sa_delete
        with sync_session_factory() as session:
            count = session.execute(
                select(self.model).where(self.model.provider_id == provider_id)  # type: ignore[attr-defined]
            ).scalars().all()
            session.execute(sa_delete(self.model).where(self.model.provider_id == provider_id))  # type: ignore[attr-defined]
            session.commit()
            return len(count)

    # ── Async wrappers ──

    async def get_by_provider_async(self, provider_id: str) -> list[dict]:
        return await asyncio.to_thread(self.get_by_provider, provider_id)

    async def get_by_provider_model_async(self, provider_id: str, model_id: str) -> Optional[dict]:
        return await asyncio.to_thread(self.get_by_provider_model, provider_id, model_id)

    async def save_models_async(self, provider_id: str, models: list[dict]) -> list[dict]:
        return await asyncio.to_thread(self.save_models, provider_id, models)

    async def update_by_provider_model_async(
        self,
        provider_id: str,
        model_id: str,
        updates: dict,
    ) -> Optional[dict]:
        return await asyncio.to_thread(self.update_by_provider_model, provider_id, model_id, updates)

    async def delete_by_provider_async(self, provider_id: str) -> int:
        return await asyncio.to_thread(self.delete_by_provider, provider_id)
