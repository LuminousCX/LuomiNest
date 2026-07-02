"""GroupRepository — 群组配置（替代 groups.json）。"""
from app.infrastructure.database.models.group import Group
from app.infrastructure.database.repositories.base import BaseRepository


class GroupRepository(BaseRepository):
    model = Group
    pk = "id"
