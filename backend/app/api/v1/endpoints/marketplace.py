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

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


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
        await download_item(
            item_id=req.itemId,
            download_url=req.downloadUrl or "",
            item_type=req.itemType,
            item_name=req.itemName,
            version=req.version,
        )
        # 安装成功后自动增加下载计数
        _increment_download_count(req.itemId, req.itemType)
    except Exception:
        pass


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
    if current and current.get("status") in ("downloading", "installing"):
        return current

    # 在后台启动下载安装任务
    background_tasks.add_task(_do_install, req)

    # 立即返回初始状态
    return {
        "itemId": req.itemId,
        "status": "downloading",
        "progress": 0,
        "message": "正在准备下载...",
        "speed": 0,
        "eta": 0,
        "downloadedBytes": 0,
        "totalBytes": 0,
    }


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


def _get_item_stats(item_id: str) -> dict:
    """获取单个条目的统计数据，不存在则初始化"""
    stats = marketplace_stats_store.get(item_id)
    if stats is None:
        stats = {"downloadCount": 0, "likeCount": 0, "type": ""}
        marketplace_stats_store.set(item_id, stats)
    return stats


def _increment_download_count(item_id: str, item_type: str):
    """增加下载计数（线程安全，由 JsonStore lock 保护）"""
    stats = _get_item_stats(item_id)
    stats["downloadCount"] = stats.get("downloadCount", 0) + 1
    if item_type:
        stats["type"] = item_type
    marketplace_stats_store.set(item_id, stats)
    logger.info(f"[MarketplaceStats] Download count incremented: {item_id} -> {stats['downloadCount']}")


class LikeRequest(BaseModel):
    itemId: str
    itemType: str = ""


@router.post("/stats/like")
async def toggle_like(req: LikeRequest):
    """切换喜欢状态，返回当前是否喜欢及喜欢计数"""
    stats = _get_item_stats(req.itemId)
    if req.itemType:
        stats["type"] = req.itemType

    # 从 store 中获取当前用户的喜欢列表
    likes_store_data = marketplace_stats_store.get("__user_likes__") or {}
    user_likes: set = set(likes_store_data.get("liked_ids", []))

    is_liked = req.itemId in user_likes

    if is_liked:
        user_likes.discard(req.itemId)
        stats["likeCount"] = max(0, stats.get("likeCount", 0) - 1)
    else:
        user_likes.add(req.itemId)
        stats["likeCount"] = stats.get("likeCount", 0) + 1

    marketplace_stats_store.set(req.itemId, stats)
    marketplace_stats_store.set("__user_likes__", {"liked_ids": list(user_likes)})

    return {
        "itemId": req.itemId,
        "isLiked": not is_liked,
        "likeCount": stats["likeCount"],
    }


@router.get("/stats/{item_id}")
async def get_item_stats(item_id: str):
    """获取单个条目的统计数据"""
    stats = _get_item_stats(item_id)
    likes_store_data = marketplace_stats_store.get("__user_likes__") or {}
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
):
    """获取所有条目的统计数据"""
    all_stats = marketplace_stats_store.list_all()
    likes_store_data = marketplace_stats_store.get("__user_likes__") or {}
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
    all_stats = marketplace_stats_store.list_all()
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
