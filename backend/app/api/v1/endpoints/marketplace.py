"""
市场内容安装/卸载/下载/统计 API
"""
import json
import os

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
    get_installed_records_resolved,
)
from app.infrastructure.database.json_store import marketplace_stats_store
from app.data.marketplace_catalog import (
    get_catalog_by_type,
    get_all_catalog_items,
    get_categories_by_type,
    get_catalog_item,
    CATALOG_PLUGINS,
    COMMON_TAGS,
)
from app.infrastructure.sync.registry_sync import (
    sync_registry,
    merge_remote_with_local,
    get_cached_plugins,
    get_cached_skills,
    is_cache_fresh,
    publish_local_plugins_to_registry,
    write_local_index_snapshot,
    build_registry_index,
)
from app.infrastructure.sync.registry_sources import (
    get_registry_sources,
    get_active_source_id,
    set_active_source_id,
    ping_all_sources,
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
    插件类型会自动合并远程注册表数据（缓存 6 小时）。
    """
    if type and type in ("plugin", "skill", "agent"):
        items = list(get_catalog_by_type(type))
    else:
        items = get_all_catalog_items()

    # 插件类型：合并远程注册表数据（远程拉取失败时降级到本地缓存/静态目录）
    if not type or type == "plugin":
        try:
            sync_result = await sync_registry()  # 缓存未过期时直接返回
            # sync_registry 返回 {"plugins": [...], "skills": [...]}，
            # 此处仅需插件列表；空列表视为无远程插件（跳过合并）
            remote_plugins = (
                sync_result.get("plugins") if isinstance(sync_result, dict) else None
            )
        except Exception as e:
            logger.warning(f"[MarketplaceAPI] sync_registry failed, falling back to local: {e}")
            remote_plugins = None

        if remote_plugins:
            local_plugins = list(CATALOG_PLUGINS)
            merged = merge_remote_with_local(remote_plugins, local_plugins)
            # 替换 items 中的插件部分
            if type == "plugin":
                items = merged
            else:
                # 全量查询时，替换 items 中的插件
                non_plugin_items = [i for i in items if i.get("type") != "plugin"]
                items = merged + non_plugin_items

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


@router.get("/local-items")
async def list_local_items(
    type: Optional[str] = Query(None, description="按类型过滤: plugin / skill"),
):
    """扫描本地 skills/ 与 plugins/ 目录，返回本地已存在的条目列表。

    与远程市场目录不同，本地条目直接来自文件系统扫描，便于用户发现
    手动放入目录的 skill/plugin。返回的条目会合并注册表运行时状态
    （loaded/disabled 等），便于前端展示当前是否生效。
    """
    from app.core.config import settings
    from app.runtime.plugin.skill.registry import cx_skill_registry
    from app.runtime.plugin.cxplugin.registry import cx_plugin_registry

    items: list[dict] = []

    # 扫描 skills 目录
    if not type or type == "skill":
        skill_dir = settings.SKILL_DIR
        if os.path.isdir(skill_dir):
            for entry in os.listdir(skill_dir):
                entry_path = os.path.join(skill_dir, entry)
                if not os.path.isdir(entry_path):
                    continue
                if entry.startswith(".") or entry.startswith("_"):
                    continue
                skill_md_path = os.path.join(entry_path, "SKILL.md")
                manifest_json_path = os.path.join(entry_path, "manifest.json")
                if not os.path.isfile(skill_md_path) and not os.path.isfile(manifest_json_path):
                    continue
                item = _scan_local_skill(entry, entry_path)
                if item:
                    items.append(item)

    # 扫描 plugins 目录
    if not type or type == "plugin":
        plugin_dir_root = settings.PLUGIN_DIR
        if os.path.isdir(plugin_dir_root):
            for entry in os.listdir(plugin_dir_root):
                entry_path = os.path.join(plugin_dir_root, entry)
                if not os.path.isdir(entry_path):
                    continue
                if entry.startswith(".") or entry.startswith("_"):
                    continue
                manifest_json_path = os.path.join(entry_path, "manifest.json")
                if not os.path.isfile(manifest_json_path):
                    continue
                item = _scan_local_plugin(entry, entry_path)
                if item:
                    items.append(item)

    return {"items": items, "total": len(items)}


def _scan_local_skill(skill_id: str, skill_dir: str) -> Optional[dict]:
    """扫描单个本地 skill 目录，返回条目字典。"""
    from app.runtime.plugin.skill.registry import cx_skill_registry
    from app.runtime.plugin.skill.models import SkillStatus

    skill = cx_skill_registry.get(skill_id)
    runtime_status = skill.status.value if skill else "not_loaded"

    # 尝试读取 SKILL.md / manifest.json 提取元数据
    name = skill_id
    description = ""
    version = "0.0.0"
    author = ""
    license_str = ""
    tags: list = []
    category = ""
    icon = ""
    trigger_keywords: list = []

    skill_md_path = os.path.join(skill_dir, "SKILL.md")
    manifest_json_path = os.path.join(skill_dir, "manifest.json")

    # 优先从已加载的注册表读取
    if skill is not None:
        name = skill.name or skill_id
        description = skill.description
        version = skill.version
        author = skill.author
        license_str = skill.license
        tags = skill.tags
        category = skill.category
        icon = skill.icon
        trigger_keywords = skill.trigger_keywords
    else:
        # 未加载时尝试解析文件
        try:
            if os.path.isfile(skill_md_path):
                import yaml
                with open(skill_md_path, encoding="utf-8") as f:
                    content = f.read()
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        fm = yaml.safe_load(parts[1]) or {}
                        if isinstance(fm, dict):
                            name = str(fm.get("name") or name)
                            description = str(fm.get("description") or "")
                            version = str(fm.get("version") or version)
                            author = str(fm.get("author") or "")
                            license_str = str(fm.get("license") or "")
                            tags = fm.get("tags") or []
                            category = str(fm.get("category") or "")
                            icon = str(fm.get("icon") or "")
                            trigger_keywords = fm.get("trigger_keywords") or []
            elif os.path.isfile(manifest_json_path):
                with open(manifest_json_path, encoding="utf-8") as f:
                    data = json.load(f)
                name = str(data.get("name") or name)
                description = str(data.get("description") or "")
                version = str(data.get("version") or version)
                author = str(data.get("author") or "")
                license_str = str(data.get("license") or "")
                tags = data.get("tags") or []
                category = str(data.get("category") or "")
                icon = str(data.get("icon") or "")
        except Exception as e:
            logger.warning(f"[MarketplaceAPI] Failed to scan local skill {skill_id}: {e}")

    return {
        "id": skill_id,
        "type": "skill",
        "name": name,
        "description": description,
        "summary": description[:60] + "..." if len(description) > 60 else description,
        "version": version,
        "author": {"id": "local", "name": author or "本地", "avatar": "", "verified": False},
        "category": category,
        "tags": [{"id": t, "name": t, "color": "#888"} for t in tags],
        "icon": icon,
        "license": license_str,
        "localPath": skill_dir,
        "runtimeStatus": runtime_status,
        "installStatus": "installed",
        "source": "local",
        "trigger_keywords": trigger_keywords,
    }


def _scan_local_plugin(plugin_id: str, plugin_dir: str) -> Optional[dict]:
    """扫描单个本地 plugin 目录，返回条目字典。"""
    from app.runtime.plugin.cxplugin.registry import cx_plugin_registry

    meta = cx_plugin_registry.get_plugin(plugin_id)
    runtime_status = meta.status.value if meta else "not_loaded"

    name = plugin_id
    description = ""
    version = "0.0.0"
    author = ""
    license_str = ""
    tags: list = []
    category = ""
    icon = ""
    capabilities: list = []
    permissions: list = []

    manifest_json_path = os.path.join(plugin_dir, "manifest.json")
    try:
        if os.path.isfile(manifest_json_path):
            with open(manifest_json_path, encoding="utf-8") as f:
                data = json.load(f)
            name = str(data.get("name") or plugin_id)
            description = str(data.get("description") or "")
            version = str(data.get("version") or version)
            author = str(data.get("author") or "")
            license_str = str(data.get("license") or "")
            tags = data.get("tags") or []
            category = str(data.get("category") or "")
            icon = str(data.get("icon") or "")
            capabilities = data.get("capabilities") or []
            permissions = data.get("permissions") or []
    except Exception as e:
        logger.warning(f"[MarketplaceAPI] Failed to scan local plugin {plugin_id}: {e}")

    return {
        "id": plugin_id,
        "type": "plugin",
        "name": name,
        "description": description,
        "summary": description[:60] + "..." if len(description) > 60 else description,
        "version": version,
        "author": {"id": "local", "name": author or "本地", "avatar": "", "verified": False},
        "category": category,
        "tags": [{"id": t, "name": t, "color": "#888"} for t in tags],
        "icon": icon,
        "license": license_str,
        "localPath": plugin_dir,
        "runtimeStatus": runtime_status,
        "installStatus": "installed",
        "source": "local",
        "capabilities": capabilities,
        "permissions": permissions,
    }


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
    return {"code": 0, "message": "ok", "error": None, "data": result}


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
    """列出所有已安装的条目。

    返回字段包含 source（builtin/remote）、frontendBuiltin、localPath（相对路径，
    如 "plugins/cxp-pdf-reader"）以及 installPath（按当前运行模式解析后的绝对路径）。
    前端可据此区分内置插件启用与远程下载安装，并展示「已安装」徽章。
    dev 与打包模式下 install_store 物理路径不同（DATA_DIR 不同），
    但 localPath 可移植，跨模式迁移时仍可正确解析。
    """
    items = get_installed_records_resolved()
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


# ─── 远程注册表同步与发布 ────────────────────────────────────


@router.post("/registry/sync")
async def force_sync_registry(
    background_tasks: BackgroundTasks,
):
    """强制刷新远程注册表缓存。

    立即返回当前缓存内容，后台异步触发 sync_registry(force=True)。
    前端可轮询 /marketplace/items 或 /marketplace/registry/cached 拉取最新数据。
    """
    async def _do_sync():
        try:
            await sync_registry(force=True)
        except Exception as e:
            logger.error(f"[MarketplaceAPI] Force sync registry failed: {e}")

    background_tasks.add_task(_do_sync)
    return {
        "code": 0,
        "message": "syncing in background",
        "cached_plugins": len(get_cached_plugins()),
        "cached_skills": len(get_cached_skills()),
        "cache_fresh": is_cache_fresh(),
    }


@router.get("/registry/cached")
async def get_cached_registry():
    """返回本地缓存的远程注册表条目（不触发远程拉取）。

    供前端"已安装 vs 可更新"对比、离线场景下展示远程条目。
    """
    return {
        "plugins": get_cached_plugins(),
        "skills": get_cached_skills(),
        "cache_fresh": is_cache_fresh(),
    }


@router.post("/registry/publish-local")
async def publish_local_registry(
    background_tasks: BackgroundTasks,
    github_token: Optional[str] = Query(None, description="可选 GitHub Token，覆盖 settings.GITHUB_TOKEN"),
):
    """将本地 backend/plugins 与 backend/skills 中的插件/技能元数据推送到远程
    cxp-registry 仓库的 index.json。

    需要 GitHub PAT 有 luminous-ChenXi/LuomiNest-cxp-registry 仓库的 contents:write 权限。
    异步后台执行，立即返回任务 ID 供前端轮询。

    安全说明：token 仅在本次请求中使用，不持久化。
    """
    async def _do_publish():
        try:
            result = await publish_local_plugins_to_registry(github_token=github_token)
            logger.info(f"[MarketplaceAPI] Publish result: {result}")
        except Exception as e:
            logger.error(f"[MarketplaceAPI] Publish local registry failed: {e}")

    background_tasks.add_task(_do_publish)
    return {
        "code": 0,
        "message": "publishing in background",
        "note": (
            "后台正在将本地插件/技能元数据推送到 LuomiNest-cxp-registry/index.json。"
            "需在 settings.GITHUB_TOKEN 或 LUOMINEST_GITHUB_TOKEN 环境变量配置有写入权限的 PAT。"
        ),
    }


@router.post("/registry/build-snapshot")
async def build_local_snapshot():
    """根据本地 plugins/skills 目录生成 index.json 快照文件。

    输出位置：backend/app/data/cxp-registry-index.json
    用于：
    1. 本地预览将要推送到远程的 index.json 内容
    2. CI/CD 在 release 时自动生成并提交到 cxp-registry 仓库
    3. 离线场景作为本地 fallback
    """
    try:
        output_path = write_local_index_snapshot()
        index_data = build_registry_index()
        return {
            "code": 0,
            "message": "snapshot built",
            "output_path": output_path,
            "plugins_count": len(index_data["plugins"]),
            "skills_count": len(index_data["skills"]),
        }
    except Exception as e:
        logger.error(f"[MarketplaceAPI] Build snapshot failed: {e}")
        raise HTTPException(status_code=500, detail=f"生成快照失败: {e}")


@router.get("/registry/sources")
async def list_registry_sources(
    ping: bool = Query(True, description="是否并发测试每个发布源的延迟"),
    timeout: float = Query(5.0, ge=1.0, le=30.0, description="单个源延迟测试超时时间（秒）"),
):
    """获取插件市场发布源列表，可选并发测试延迟。

    返回每个源的基础信息 + 当前活跃状态 + 延迟/健康状态。
    不可用的源（healthy=False 或 enabled=False）不应在前端被选中。
    """
    if ping:
        try:
            sources = await ping_all_sources(timeout=timeout)
        except Exception as e:
            logger.error(f"[MarketplaceAPI] Ping registry sources failed: {e}")
            sources = [
                {**s, "latencyMs": 9999, "healthy": False, "statusCode": None, "error": f"测试失败: {e}"}
                for s in get_registry_sources()
            ]
    else:
        sources = [
            {**s, "latencyMs": -1, "healthy": True, "statusCode": None, "error": None}
            for s in get_registry_sources()
        ]
        active_id = get_active_source_id()
        for s in sources:
            s["active"] = s["id"] == active_id

    return {
        "activeSourceId": get_active_source_id(),
        "sources": sources,
    }


@router.post("/registry/source/{source_id}")
async def switch_registry_source(source_id: str):
    """切换当前活跃的插件市场发布源。

    仅允许切换到 enabled=True 且实际可访问的源。
    切换成功后会影响后续 /marketplace/items 中远程条目的拉取 URL。
    """
    from app.infrastructure.sync.registry_sources import get_source_by_id, ping_source

    source = get_source_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"发布源 {source_id} 不存在")
    if not source.get("enabled"):
        raise HTTPException(status_code=400, detail=f"发布源 {source_id} 已禁用，无法切换")

    # 切换前快速 ping 一次，避免切到不可用的源
    ping = await ping_source(source, timeout=3.0)
    if not ping["healthy"]:
        raise HTTPException(
            status_code=400,
            detail=f"发布源 {source_id} 当前不可用: {ping.get('error') or ping.get('statusCode')}",
        )

    if not set_active_source_id(source_id):
        raise HTTPException(status_code=500, detail=f"切换发布源 {source_id} 失败")

    return {
        "code": 0,
        "message": "source switched",
        "activeSourceId": source_id,
        "latencyMs": ping["latencyMs"],
    }
