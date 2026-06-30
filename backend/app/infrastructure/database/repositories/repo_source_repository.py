"""RepoSourceRepository — 仓库源（替代 repo_sources.json）。"""
from app.infrastructure.database.models.repo_source import RepoSource
from app.infrastructure.database.repositories.base import BaseRepository


class RepoSourceRepository(BaseRepository):
    model = RepoSource
    pk = "id"
