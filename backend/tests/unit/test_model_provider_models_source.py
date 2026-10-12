"""GET /models/providers/{id}/models 返回体 source 标记测试。

背景：在线拉取 {base_url}/models 失败/为空时端点会回退数据库已存列表。
旧实现静默回退且照样返回裸数组，前端无法区分"在线拿到"还是"旧数据"，
用户看到"刷新不生效"。现要求返回体携带 source（live / db_fallback），
回退时附 warning 人类可读键，models 数组键始终存在（向后兼容）。

覆盖：
- live：适配器在线返回模型 → source=live、无 warning、模型持久化到 DB
- 空回退：适配器返回空列表 → source=db_fallback + warning，models 取自 DB
- 异常回退：适配器抛异常 → source=db_fallback + warning，不 500
- 空库回退：DB 无记录 → models 为空数组但 source/warning 照常标记
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.deps import get_llm_adapter
from app.api.v1.endpoints.model import router as model_router
from app.infrastructure.database.repositories.provider_model_repository import (
    ProviderModelRepository,
)

# 每用例独立 provider id，避免会话级临时 SQLite 中用例间相互污染
PROVIDER_ID = "test-provider-source"


class _FakeAdapter:
    """可编程 mock：list_models 返回可配置结果或抛异常。"""

    def __init__(self, models: list[dict] | None = None, error: Exception | None = None):
        self.models = models
        self.error = error

    async def list_models(self, provider_name: str | None = None) -> list[dict]:
        if self.error:
            raise self.error
        return list(self.models or [])


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(model_router)
    return application


@pytest.fixture
def _db(_init_test_db):
    """确保临时 SQLite 已建表（含 provider_models）。"""


@pytest.fixture
def seeded_models(_db):
    """向临时 SQLite 预置该供应商的历史模型行，用例结束清理。"""
    repo = ProviderModelRepository()
    repo.save_models(PROVIDER_ID, [
        {"id": "saved-model-a", "name": "Saved A", "max_context_tokens": 8192},
        {"id": "saved-model-b", "name": "Saved B", "max_context_tokens": 0},
    ])
    yield repo
    for m in repo.get_by_provider(PROVIDER_ID):
        repo.delete(m["id"])


def _override(app: FastAPI, adapter: _FakeAdapter) -> None:
    app.dependency_overrides[get_llm_adapter] = lambda: adapter


async def _get_models(app: FastAPI) -> dict[str, Any]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/models/providers/{PROVIDER_ID}/models")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0
    return body["data"]


class TestListProviderModelsSource:
    async def test_live_fetch_marks_source_live_and_persists(self, app: FastAPI, seeded_models) -> None:
        _override(app, _FakeAdapter(models=[
            {"id": "live-model-1", "name": "Live 1", "owned_by": "org"},
        ]))
        data = await _get_models(app)
        assert data["source"] == "live"
        assert "warning" not in data
        assert [m["id"] for m in data["models"]] == ["live-model-1"]
        # live 成功才会持久化（现状语义，不得破坏）
        assert any(m["model_id"] == "live-model-1" for m in seeded_models.get_by_provider(PROVIDER_ID))

    async def test_empty_fetch_falls_back_with_warning(self, app: FastAPI, seeded_models) -> None:
        _override(app, _FakeAdapter(models=[]))
        data = await _get_models(app)
        assert data["source"] == "db_fallback"
        assert "warning" in data and data["warning"]
        assert {m["id"] for m in data["models"]} == {"saved-model-a", "saved-model-b"}

    async def test_adapter_exception_falls_back_instead_of_500(self, app: FastAPI, seeded_models) -> None:
        _override(app, _FakeAdapter(error=RuntimeError("connection refused")))
        data = await _get_models(app)
        assert data["source"] == "db_fallback"
        assert "connection refused" in data["warning"]
        assert {m["id"] for m in data["models"]} == {"saved-model-a", "saved-model-b"}

    async def test_empty_db_fallback_keeps_models_key(self, app: FastAPI, _db) -> None:
        _override(app, _FakeAdapter(models=[]))
        data = await _get_models(app)
        assert data["source"] == "db_fallback"
        assert data["models"] == []
        assert data["warning"]
