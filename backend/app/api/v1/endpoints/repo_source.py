import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from loguru import logger

from app.infrastructure.database.json_store import repo_sources_store

router = APIRouter(prefix="/repo-sources", tags=["repo-sources"])


class SubMarketCreate(BaseModel):
    name: str
    type: str = Field(..., pattern=r"^(plugin|skill|agent)$")
    url: str
    description: str = ""


class SubMarketUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    linked: Optional[bool] = None


class SubMarketResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    id: str
    name: str
    type: str
    url: str
    description: str = ""
    linked: bool = True


class RepoSourceCreate(BaseModel):
    type: str = Field(..., pattern=r"^(github|cloud|cdn|custom)$")
    name: str
    url: str = ""
    description: str = ""
    enabled: bool = True
    sub_markets: list[SubMarketCreate] = Field(default_factory=list)


class RepoSourceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    sub_markets: Optional[list[SubMarketCreate]] = None


class RepoSourceResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    id: str
    type: str
    name: str
    url: str = ""
    description: str = ""
    enabled: bool = True
    sub_markets: list[SubMarketResponse] = Field(alias="subMarkets", default_factory=list)
    last_synced_at: str = Field(alias="lastSyncedAt", default="")
    status: str = "idle"
    error_message: str = Field(alias="errorMessage", default="")


DEFAULT_GITHUB_SUB_MARKETS = [
    {"id": "gh-skills", "name": "Skills 市场", "type": "skill", "url": "https://github.com/LuminousCX/skills", "description": "LuminousCX 官方技能仓库", "linked": True},
    {"id": "gh-agents", "name": "Agents 市场", "type": "agent", "url": "https://github.com/LuminousCX/agents", "description": "LuminousCX 官方智能体仓库", "linked": True},
    {"id": "gh-plugins", "name": "Plugins 市场", "type": "plugin", "url": "https://github.com/LuminousCX/plugins", "description": "LuminousCX 官方插件仓库", "linked": True},
]

DEFAULT_REPO_SOURCES = [
    {
        "id": "github-official",
        "type": "github",
        "name": "GitHub 官方仓库",
        "url": "https://github.com/LuminousCX",
        "description": "LuminousCX 官方 GitHub 仓库，包含技能、智能体和插件",
        "enabled": True,
        "sub_markets": DEFAULT_GITHUB_SUB_MARKETS,
        "last_synced_at": "",
        "status": "idle",
        "error_message": "",
    },
    {
        "id": "cloud-official",
        "type": "cloud",
        "name": "云端仓库",
        "url": "",
        "description": "LuminousCX 云端托管仓库",
        "enabled": False,
        "sub_markets": [],
        "last_synced_at": "",
        "status": "idle",
        "error_message": "",
    },
    {
        "id": "cdn-official",
        "type": "cdn",
        "name": "CDN 仓库",
        "url": "",
        "description": "CDN 加速分发仓库",
        "enabled": False,
        "sub_markets": [],
        "last_synced_at": "",
        "status": "idle",
        "error_message": "",
    },
]


def _ensure_defaults():
    existing = repo_sources_store.all()
    if not existing:
        for source in DEFAULT_REPO_SOURCES:
            repo_sources_store.set(source["id"], source)
        logger.info("[RepoSources] Initialized default repo sources")


_ensure_defaults()


def _to_response(source: dict) -> RepoSourceResponse:
    sub_markets = [
        SubMarketResponse(
            id=sm.get("id", ""),
            name=sm.get("name", ""),
            type=sm.get("type", "plugin"),
            url=sm.get("url", ""),
            description=sm.get("description", ""),
            linked=sm.get("linked", True),
        )
        for sm in source.get("sub_markets", [])
    ]
    return RepoSourceResponse(
        id=source.get("id", ""),
        type=source.get("type", "github"),
        name=source.get("name", ""),
        url=source.get("url", ""),
        description=source.get("description", ""),
        enabled=source.get("enabled", True),
        sub_markets=sub_markets,
        last_synced_at=source.get("last_synced_at", ""),
        status=source.get("status", "idle"),
        error_message=source.get("error_message", ""),
    )


@router.get("", response_model=list[RepoSourceResponse])
async def list_repo_sources():
    logger.info("[API] GET /repo-sources - Listing all repo sources")
    sources = repo_sources_store.all()
    return [_to_response(s) for s in sources]


@router.post("", response_model=RepoSourceResponse)
async def create_repo_source(request: RepoSourceCreate):
    logger.info(f"[API] POST /repo-sources - Creating repo source: name={request.name}")
    source_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    sub_markets = []
    for sm in request.sub_markets:
        sub_markets.append({
            "id": str(uuid.uuid4())[:8],
            "name": sm.name,
            "type": sm.type,
            "url": sm.url,
            "description": sm.description,
            "linked": True,
        })
    source = {
        "id": source_id,
        "type": request.type,
        "name": request.name,
        "url": request.url,
        "description": request.description,
        "enabled": request.enabled,
        "sub_markets": sub_markets,
        "last_synced_at": "",
        "status": "idle",
        "error_message": "",
        "created_at": now,
        "updated_at": now,
    }
    repo_sources_store.set(source_id, source)
    logger.success(f"[API] POST /repo-sources - Created: id={source_id}")
    return _to_response(source)


@router.get("/{source_id}", response_model=RepoSourceResponse)
async def get_repo_source(source_id: str):
    logger.info(f"[API] GET /repo-sources/{source_id}")
    source = repo_sources_store.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Repo source {source_id} not found")
    return _to_response(source)


@router.patch("/{source_id}", response_model=RepoSourceResponse)
async def update_repo_source(source_id: str, request: RepoSourceUpdate):
    logger.info(f"[API] PATCH /repo-sources/{source_id}")
    source = repo_sources_store.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Repo source {source_id} not found")

    update_data = request.model_dump(exclude_unset=True)
    if "sub_markets" in update_data and update_data["sub_markets"] is not None:
        existing_sms = source.get("sub_markets", [])
        update_data["sub_markets"] = [
            {
                "id": existing_sms[i]["id"] if i < len(existing_sms) else str(uuid.uuid4())[:8],
                "name": sm["name"],
                "type": sm["type"],
                "url": sm["url"],
                "description": sm.get("description", ""),
                "linked": True,
            }
            for i, sm in enumerate(update_data["sub_markets"])
        ]
    source.update(update_data)
    source["updated_at"] = datetime.now(timezone.utc).isoformat()
    repo_sources_store.set(source_id, source)
    logger.success(f"[API] PATCH /repo-sources/{source_id} - Updated")
    return _to_response(source)


@router.delete("/{source_id}")
async def delete_repo_source(source_id: str):
    logger.info(f"[API] DELETE /repo-sources/{source_id}")
    source = repo_sources_store.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Repo source {source_id} not found")
    repo_sources_store.delete(source_id)
    logger.success(f"[API] DELETE /repo-sources/{source_id} - Deleted")
    return {"error": None, "data": {"deleted": True}}


@router.post("/{source_id}/toggle", response_model=RepoSourceResponse)
async def toggle_repo_source(source_id: str):
    logger.info(f"[API] POST /repo-sources/{source_id}/toggle")
    source = repo_sources_store.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Repo source {source_id} not found")
    source["enabled"] = not source.get("enabled", True)
    source["updated_at"] = datetime.now(timezone.utc).isoformat()
    repo_sources_store.set(source_id, source)
    logger.success(f"[API] POST /repo-sources/{source_id}/toggle - enabled={source['enabled']}")
    return _to_response(source)


@router.patch("/{source_id}/sub-markets/{sub_market_id}/unlink")
async def unlink_sub_market(source_id: str, sub_market_id: str):
    logger.info(f"[API] PATCH /repo-sources/{source_id}/sub-markets/{sub_market_id}/unlink")
    source = repo_sources_store.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Repo source {source_id} not found")

    sub_markets = source.get("sub_markets", [])
    found = False
    for sm in sub_markets:
        if sm.get("id") == sub_market_id:
            sm["linked"] = False
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail=f"Sub-market {sub_market_id} not found")

    source["sub_markets"] = sub_markets
    source["updated_at"] = datetime.now(timezone.utc).isoformat()
    repo_sources_store.set(source_id, source)
    logger.success(f"[API] Unlinked sub-market {sub_market_id}")
    return _to_response(source)


@router.patch("/{source_id}/sub-markets/{sub_market_id}/link")
async def link_sub_market(source_id: str, sub_market_id: str):
    logger.info(f"[API] PATCH /repo-sources/{source_id}/sub-markets/{sub_market_id}/link")
    source = repo_sources_store.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Repo source {source_id} not found")

    sub_markets = source.get("sub_markets", [])
    found = False
    for sm in sub_markets:
        if sm.get("id") == sub_market_id:
            sm["linked"] = True
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail=f"Sub-market {sub_market_id} not found")

    source["sub_markets"] = sub_markets
    source["updated_at"] = datetime.now(timezone.utc).isoformat()
    repo_sources_store.set(source_id, source)
    logger.success(f"[API] Linked sub-market {sub_market_id}")
    return _to_response(source)


@router.post("/{source_id}/sync", response_model=RepoSourceResponse)
async def sync_repo_source(source_id: str, force: bool = False):
    logger.info(f"[API] POST /repo-sources/{source_id}/sync")
    source = repo_sources_store.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Repo source {source_id} not found")

    source["status"] = "loading"
    source["error_message"] = ""
    repo_sources_store.set(source_id, source)

    try:
        from app.infrastructure.sync.github_sync import sync_source
        results = await sync_source(source_id, source, force=force)

        # 检查是否有错误
        errors = [r.error for r in results if r.error]
        if errors and len(errors) == len(results):
            # 所有子市场都失败
            source["status"] = "error"
            source["error_message"] = "; ".join(errors)
        elif errors:
            # 部分失败
            source["status"] = "loaded"
            source["error_message"] = f"部分子市场同步失败: {'; '.join(errors)}"
        else:
            source["status"] = "loaded"
            source["error_message"] = ""

        source["last_synced_at"] = datetime.now(timezone.utc).isoformat()
        source["updated_at"] = datetime.now(timezone.utc).isoformat()
        repo_sources_store.set(source_id, source)
        logger.success(f"[API] POST /repo-sources/{source_id}/sync - Success ({len(results)} sub-markets)")
    except Exception as e:
        source["status"] = "error"
        source["error_message"] = str(e)
        repo_sources_store.set(source_id, source)
        logger.error(f"[API] POST /repo-sources/{source_id}/sync - Error: {e}")

    return _to_response(source)


@router.post("/{source_id}/sub-markets/{sub_market_id}/sync")
async def sync_sub_market(source_id: str, sub_market_id: str, force: bool = False):
    """同步单个子市场"""
    logger.info(f"[API] POST /repo-sources/{source_id}/sub-markets/{sub_market_id}/sync")
    source = repo_sources_store.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Repo source {source_id} not found")

    sub_market = None
    for sm in source.get("sub_markets", []):
        if sm.get("id") == sub_market_id:
            sub_market = sm
            break
    if not sub_market:
        raise HTTPException(status_code=404, detail=f"Sub-market {sub_market_id} not found")

    try:
        from app.infrastructure.sync.github_sync import sync_sub_market as do_sync
        result = await do_sync(source_id, sub_market_id, sub_market.get("url", ""), force=force)
        return result.to_dict()
    except Exception as e:
        logger.error(f"[API] Sync sub-market failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{source_id}/items")
async def get_source_items(source_id: str, type: Optional[str] = None):
    """获取仓库来源下的所有已缓存市场条目"""
    logger.info(f"[API] GET /repo-sources/{source_id}/items")
    source = repo_sources_store.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Repo source {source_id} not found")

    from app.infrastructure.sync.github_sync import get_all_cached_items
    items = get_all_cached_items(source_id, source)

    # 按类型过滤
    if type and type in ("plugin", "skill", "agent"):
        items = [i for i in items if i.get("type") == type]

    return {"items": items, "total": len(items), "sourceId": source_id}


@router.get("/{source_id}/sub-markets/{sub_market_id}/items")
async def get_sub_market_items(source_id: str, sub_market_id: str):
    """获取子市场下的已缓存市场条目"""
    source = repo_sources_store.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Repo source {source_id} not found")

    from app.infrastructure.sync.github_sync import get_cached_items
    cached = get_cached_items(source_id, sub_market_id)
    if cached:
        return {"items": cached.items, "total": cached.total, "sourceId": source_id, "subMarketId": sub_market_id, "syncedAt": cached.synced_at, "fromCache": cached.from_cache}
    return {"items": [], "total": 0, "sourceId": source_id, "subMarketId": sub_market_id}


@router.delete("/{source_id}/cache")
async def clear_source_cache(source_id: str, sub_market_id: Optional[str] = None):
    """清除仓库来源的缓存"""
    source = repo_sources_store.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Repo source {source_id} not found")

    from app.infrastructure.sync.github_sync import clear_cache
    clear_cache(source_id=source_id, sub_market_id=sub_market_id)
    return {"error": None, "data": {"cleared": True}}
