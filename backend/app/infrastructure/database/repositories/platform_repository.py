"""PlatformRepository — 平台实例（替代 platforms.json）。"""
from app.infrastructure.database.models.platform_instance import PlatformInstance
from app.infrastructure.database.repositories.base import BaseRepository


class PlatformRepository(BaseRepository):
    model = PlatformInstance
    pk = "id"
