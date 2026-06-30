"""AgentRepository — 智能体配置（替代 agents.json）。"""
import asyncio
from typing import Optional

from sqlalchemy import select

from app.infrastructure.database.models.agent import Agent
from app.infrastructure.database.repositories.base import BaseRepository
from app.infrastructure.database.session import sync_session_factory


class AgentRepository(BaseRepository):
    model = Agent
    pk = "id"

    def get_all_non_main(self) -> list[dict]:
        """返回所有非主 Agent（is_main=False 或 NULL）。"""
        from app.infrastructure.database.repositories.base import orm_to_dict
        with sync_session_factory() as session:
            objs = session.execute(select(Agent).where(Agent.is_main == False)).scalars().all()
            return [orm_to_dict(o) for o in objs]

    def exists_by_name(self, name: str, exclude_id: Optional[str] = None) -> bool:
        with sync_session_factory() as session:
            stmt = select(Agent).where(Agent.name == name)
            if exclude_id:
                stmt = stmt.where(Agent.id != exclude_id)
            return session.execute(stmt).first() is not None

    async def get_all_non_main_async(self) -> list[dict]:
        return await asyncio.to_thread(self.get_all_non_main)

    async def exists_by_name_async(self, name: str, exclude_id: Optional[str] = None) -> bool:
        return await asyncio.to_thread(self.exists_by_name, name, exclude_id)
