"""
市场内容安装/卸载/下载/统计 API
"""
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from loguru import logger

from app.infrastructure.install.install_service import (
    download_item,
    uninstall_item,
    get_installed_items,
    get_installed_item,
    is_installed,
    get_download_status,
    get_all_install_status,
)
from app.infrastructure.database.json_store import marketplace_stats_store
from app.data.marketplace_catalog import (
    get_catalog_by_type,
    get_all_catalog_items,
    get_categories_by_type,
    get_catalog_item,
    COMMON_TAGS,
)
from app.security.net.safe_url import assert_url_safe, UnsafeUrlError

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


# ─── 目录查询接口（静态目录数据源） ─────────────────────────────


@router.get("/items")
async def list_catalog_items(
    type: Optional[str] = Query(None, description="按类型过滤: plugin / skill / agent"),
    category: Optional[str] = Query(None, description="按分类过滤"),
    featured: Optional[bool] = Query(None, description="仅返回精选条目"),
    search: Optional[str] = Query(None, description="搜索关键词"),
):
    """
    获取市场目录条目列表。

    支持按 type / category / featured / search 过滤。
    返回的 installStatus 会与本地安装状态合并，确保前端展示一致。
    """
    if type and type in ("plugin", "skill", "agent"):
        items = get_catalog_by_type(type)
    else:
        items = get_all_catalog_items()

    # 合并本地安装状态
    installed_records = get_installed_items()
    installed_map = {r.get("itemId"): r for r in installed_records if r.get("itemId")}

    result = []
    for item in items:
        # 合并安装状态
        item_id = item["id"]
        if item_id in installed_map:
            item = {**item, "installStatus": "installed"}

        # 应用过滤
        if category and item.get("category") != category:
            # 检查子分类
            parent_match = False
            cats = get_categories_by_type(item["type"])
            for cat in cats:
                if cat["id"] == category and any(
                    c["id"] == item.get("category") for c in cat.get("children", [])
                ):
                    parent_match = True
                    break
            if not parent_match:
                continue

        if featured is not None and item.get("featured") != featured:
            continue

        if search:
            q = search.lower().strip()
            if not (
                q in item["name"].lower()
                or q in item["description"].lower()
                or q in item["summary"].lower()
                or any(q in t["name"].lower() for t in item.get("tags", []))
                or q in item["author"]["name"].lower()
            ):
                continue

        result.append(item)

    return {"items": result, "total": len(result)}


@router.get("/items/{item_id}")
async def get_catalog_item_by_id(item_id: str):
    """按 ID 获取单个目录条目，合并本地安装状态。"""
    item = get_catalog_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"条目 {item_id} 不存在")

    # 合并安装状态
    if is_installed(item_id):
        item = {**item, "installStatus": "installed"}

    return item


@router.get("/categories")
async def list_categories(
    type: Optional[str] = Query(None, description="按类型过滤: plugin / skill / agent"),
):
    """获取分类列表，支持按类型过滤。"""
    if type and type in ("plugin", "skill", "agent"):
        cats = get_categories_by_type(type)
        return {"categories": cats, "total": len(cats)}

    all_cats = {
        "plugin": get_categories_by_type("plugin"),
        "skill": get_categories_by_type("skill"),
        "agent": get_categories_by_type("agent"),
    }
    return {"categories": all_cats, "total": sum(len(c) for c in all_cats.values())}


@router.get("/tags")
async def list_tags():
    """获取所有公共标签。"""
    return {"tags": COMMON_TAGS, "total": len(COMMON_TAGS)}


# ─── 安装/卸载接口 ─────────────────────────────────────────────


class InstallRequest(BaseModel):
    itemId: str
    itemType: str  # plugin / skill / agent
    itemName: str
    version: str = "1.0.0"
    downloadUrl: Optional[str] = None


class UninstallRequest(BaseModel):
    itemId: str


async def _do_install(req: InstallRequest):
    """后台执行下载安装"""
    try:
        if req.downloadUrl:
            await assert_url_safe(req.downloadUrl)
        result = await download_item(
            item_id=req.itemId,
            download_url=req.downloadUrl,
            item_type=req.itemType,
            item_name=req.itemName,
            version=req.version,
        )
        # 仅在安装成功后增加下载计数
        if result.get("status") == "installed":
            await _increment_download_count(req.itemId, req.itemType)
    except Exception as e:
        logger.error(f"[MarketplaceAPI] Install failed for {req.itemId}: {e}")
        # 更新任务状态为失败，防止进度轮询永久返回 queued
        from app.infrastructure.install.install_service import _active_downloads
        if req.itemId in _active_downloads:
            _active_downloads[req.itemId]["status"] = "error"
            _active_downloads[req.itemId]["message"] = str(e)
            _active_downloads[req.itemId]["error"] = str(e)


@router.post("/install")
async def install_marketplace_item(req: InstallRequest, background_tasks: BackgroundTasks):
    """
    启动下载并安装市场内容（异步后台执行）。
    立即返回初始状态，前端通过轮询 download-progress 获取进度。
    """
    # 检查是否已安装
    if is_installed(req.itemId):
        raise HTTPException(status_code=409, detail=f"条目 {req.itemId} 已安装")

    # 检查是否正在下载/安装中
    current = get_download_status(req.itemId)
    if current and current.get("status") in ("downloading", "installing", "queued"):
        return current

    # 原子标记为排队中，防止并发请求创建重复后台任务
    from app.infrastructure.install.install_service import _active_downloads
    if req.itemId in _active_downloads:
        return _active_downloads[req.itemId]
    _active_downloads[req.itemId] = {
        "itemId": req.itemId,
        "status": "queued",
        "progress": 0,
        "message": "排队等待中...",
        "speed": 0,
        "eta": 0,
        "downloadedBytes": 0,
        "totalBytes": 0,
        "startTime": __import__("time").time(),
    }

    # 在后台启动下载安装任务
    background_tasks.add_task(_do_install, req)

    # 立即返回初始状态
    return _active_downloads[req.itemId]


@router.post("/uninstall")
async def uninstall_marketplace_item(req: UninstallRequest):
    """卸载已安装的市场内容"""
    result = await uninstall_item(req.itemId)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "卸载失败"))
    return result


@router.get("/install-status")
async def get_install_statuses():
    """获取所有条目的安装状态"""
    installed = get_all_install_status()
    return {"statuses": installed}


@router.get("/install-status/{item_id}")
async def get_item_install_status(item_id: str):
    """获取单个条目的安装状态"""
    record = get_installed_item(item_id)
    if record:
        return {"itemId": item_id, "status": "installed", "record": record}

    download = get_download_status(item_id)
    if download:
        return {"itemId": item_id, "status": download.get("status", "unknown"), "download": download}

    return {"itemId": item_id, "status": "none"}


@router.get("/download-progress/{item_id}")
async def get_download_progress(item_id: str):
    """获取下载进度（用于轮询）"""
    status = get_download_status(item_id)
    if not status:
        # 检查是否已安装
        if is_installed(item_id):
            return {"itemId": item_id, "status": "installed", "progress": 100}
        return {"itemId": item_id, "status": "none", "progress": 0}
    return status


@router.get("/installed")
async def list_installed_items(
    type: Optional[str] = Query(None, description="按类型过滤"),
):
    """列出所有已安装的条目"""
    items = get_installed_items()
    if type and type in ("plugin", "skill", "agent"):
        items = [i for i in items if i.get("type") == type]
    return {"items": items, "total": len(items)}


# ─── 统计功能 ───────────────────────────────────────────────


async def _get_item_stats(item_id: str) -> dict:
    """获取单个条目的统计数据，不存在则初始化"""
    stats = await marketplace_stats_store.get_async(item_id)
    if stats is None:
        stats = {"downloadCount": 0, "likeCount": 0, "type": ""}
        await marketplace_stats_store.set_async(item_id, stats)
    return stats


async def _increment_download_count(item_id: str, item_type: str):
    """增加下载计数（原子操作，由 JsonStore.mutate_async 锁保护）"""
    def _updater(stats):
        if stats is None:
            stats = {"downloadCount": 0, "likeCount": 0, "type": ""}
        stats["downloadCount"] = stats.get("downloadCount", 0) + 1
        if item_type:
            stats["type"] = item_type
        return stats

    stats = await marketplace_stats_store.mutate_async(item_id, _updater)
    logger.info(f"[MarketplaceStats] Download count incremented: {item_id} -> {stats['downloadCount']}")


class LikeRequest(BaseModel):
    itemId: str
    itemType: str = ""
    userId: str = ""  # 可选用户标识，桌面单用户场景下为空


def _get_likes_key(user_id: str = "") -> str:
    """获取用户专属或全局喜欢列表的存储键"""
    return f"__user_likes__:{user_id}" if user_id else "__user_likes__"


@router.post("/stats/like")
async def toggle_like(req: LikeRequest) -> dict:
    """切换喜欢状态，返回当前是否喜欢及喜欢计数（原子操作）"""
    likes_key = _get_likes_key(req.userId)

    # 使用单个 mutate 完成点赞状态切换 + 计数更新，避免竞态
    def _toggle_updater(stats):
        if stats is None:
            stats = {"downloadCount": 0, "likeCount": 0, "type": ""}
        if req.itemType:
            stats["type"] = req.itemType
        # 确保 likes_key 存在于同一个存储中
        likes_data = stats.get("__likes__", {})
        user_likes: set = set(likes_data.get("liked_ids", []))
        is_liked = req.itemId in user_likes

        if is_liked:
            user_likes.discard(req.itemId)
            stats["likeCount"] = max(0, stats.get("likeCount", 0) - 1)
        else:
            user_likes.add(req.itemId)
            stats["likeCount"] = stats.get("likeCount", 0) + 1

        stats["__likes__"] = {"liked_ids": list(user_likes)}
        return stats

    stats = await marketplace_stats_store.mutate_async(req.itemId, _toggle_updater)

    # 独立维护按用户的喜欢列表 key（兼容旧查询）
    likes_store_data = await marketplace_stats_store.get_async(likes_key) or {}
    user_likes: set = set(likes_store_data.get("liked_ids", []))
    is_liked = req.itemId in user_likes
    if is_liked:
        user_likes.discard(req.itemId)
    else:
        user_likes.add(req.itemId)
    await marketplace_stats_store.set_async(likes_key, {"liked_ids": list(user_likes)})

    return {
        "itemId": req.itemId,
        "isLiked": not is_liked,
        "likeCount": stats["likeCount"],
    }


@router.get("/stats/{item_id}")
async def get_item_stats(item_id: str, userId: str = ""):
    """获取单个条目的统计数据"""
    stats = await _get_item_stats(item_id)
    likes_key = _get_likes_key(userId)
    likes_store_data = await marketplace_stats_store.get_async(likes_key) or {}
    user_likes: set = set(likes_store_data.get("liked_ids", []))
    return {
        "itemId": item_id,
        "downloadCount": stats.get("downloadCount", 0),
        "likeCount": stats.get("likeCount", 0),
        "isLiked": item_id in user_likes,
    }


@router.get("/stats")
async def get_all_stats(
    type: Optional[str] = Query(None, description="按类型过滤"),
    userId: str = "",
):
    """获取所有条目的统计数据"""
    all_stats = await marketplace_stats_store.list_all_async()
    likes_key = _get_likes_key(userId)
    likes_store_data = await marketplace_stats_store.get_async(likes_key) or {}
    user_likes: set = set(likes_store_data.get("liked_ids", []))
    result = []
    for item_id, stats in all_stats.items():
        if item_id.startswith("__"):
            continue
        if type and stats.get("type") != type:
            continue
        result.append({
            "itemId": item_id,
            "downloadCount": stats.get("downloadCount", 0),
            "likeCount": stats.get("likeCount", 0),
            "isLiked": item_id in user_likes,
            "type": stats.get("type", ""),
        })
    return {"stats": result, "total": len(result)}


@router.get("/leaderboard")
async def get_leaderboard(
    type: Optional[str] = Query(None, description="按类型过滤 (plugin/skill/agent)"),
    sort_by: str = Query("composite", description="排序方式: downloads / likes / composite"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
):
    """
    获取排行榜，基于下载次数和喜欢次数综合排序。
    composite = downloadCount * 1 + likeCount * 3 (喜欢权重更高)
    """
    all_stats = await marketplace_stats_store.list_all_async()
    items = []
    for item_id, stats in all_stats.items():
        if item_id.startswith("__"):
            continue
        if type and stats.get("type") != type:
            continue
        dl = stats.get("downloadCount", 0)
        lk = stats.get("likeCount", 0)
        items.append({
            "itemId": item_id,
            "downloadCount": dl,
            "likeCount": lk,
            "type": stats.get("type", ""),
            "score": dl + lk * 3,
        })

    if sort_by == "downloads":
        items.sort(key=lambda x: x["downloadCount"], reverse=True)
    elif sort_by == "likes":
        items.sort(key=lambda x: x["likeCount"], reverse=True)
    else:
        items.sort(key=lambda x: x["score"], reverse=True)

    return {"leaderboard": items[:limit], "total": len(items)}
