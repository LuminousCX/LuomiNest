"""插件注册表远程同步模块 — 从 GitHub 索引仓库拉取最新插件目录。

架构：
  远程索引仓库 (cxp-registry/index.json)
    ↓ 定时/手动拉取
  本地缓存 (registry_cache.json)
    ↓ 合并
  市场 API /items 返回完整列表
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from app.core.config import settings
from app.infrastructure.database.json_store import JsonStore

# 远程索引 URL
REGISTRY_URL = "https://raw.githubusercontent.com/luminous-ChenXi/LuomiNest-cxp-registry/main/index.json"

# 缓存刷新间隔（秒），默认 6 小时
CACHE_TTL_SECONDS = 6 * 60 * 60

# 本地缓存存储
_registry_cache_store = JsonStore("registry_cache.json")


def _get_cache() -> dict[str, Any]:
    """读取本地缓存。"""
    data = _registry_cache_store.get("registry")
    return data if isinstance(data, dict) else {}


def _set_cache(data: dict[str, Any]) -> None:
    """写入本地缓存。"""
    _registry_cache_store.set("registry", data)


def is_cache_fresh() -> bool:
    """检查本地缓存是否仍在有效期内。"""
    cache = _get_cache()
    fetched_at = cache.get("fetchedAt", 0)
    return (time.time() - fetched_at) < CACHE_TTL_SECONDS


async def sync_registry(force: bool = False) -> dict[str, list[dict[str, Any]]]:
    """从远程索引仓库拉取最新插件和技能目录。

    Args:
        force: 是否强制刷新（忽略缓存有效期）

    Returns:
        {"plugins": [...], "skills": [...]}
    """
    # 缓存未过期且非强制刷新时直接返回
    if not force and is_cache_fresh():
        cache = _get_cache()
        return {
            "plugins": cache.get("plugins", []),
            "skills": cache.get("skills", []),
        }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(REGISTRY_URL)
            resp.raise_for_status()
            data = resp.json()

        plugins = data.get("plugins", [])
        skills = data.get("skills", [])
        logger.info(
            f"[RegistrySync] Fetched {len(plugins)} plugins, "
            f"{len(skills)} skills from remote registry"
        )

        # 写入缓存
        _set_cache({
            "fetchedAt": time.time(),
            "version": data.get("version", ""),
            "updatedAt": data.get("updatedAt", ""),
            "plugins": plugins,
            "skills": skills,
        })

        return {"plugins": plugins, "skills": skills}

    except httpx.HTTPStatusError as e:
        logger.warning(f"[RegistrySync] HTTP error fetching registry: {e.response.status_code}")
    except httpx.RequestError as e:
        logger.warning(f"[RegistrySync] Network error fetching registry: {e}")
    except Exception as e:
        logger.warning(f"[RegistrySync] Unexpected error syncing registry: {e}")

    # 拉取失败时返回缓存数据（可能过期）
    cache = _get_cache()
    return {
        "plugins": cache.get("plugins", []),
        "skills": cache.get("skills", []),
    }


def merge_remote_with_local(
    remote_plugins: list[dict[str, Any]],
    local_plugins: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """合并远程插件与本地静态目录。

    远程插件优先（id 相同时覆盖本地），本地独有的保留。

    Args:
        remote_plugins: 从远程索引拉取的插件列表
        local_plugins: 本地 marketplace_catalog.py 中的静态插件列表

    Returns:
        合并后的完整插件列表
    """
    # 以 id 为 key 建立索引
    merged: dict[str, dict[str, Any]] = {}

    # 先放入本地静态数据
    for item in local_plugins:
        merged[item["id"]] = item

    # 远程数据覆盖/新增
    for item in remote_plugins:
        item_id = item.get("id", "")
        if not item_id:
            continue
        # 标准化远程条目格式，使其与前端期望对齐
        normalized = _normalize_remote_item(item)
        merged[item_id] = normalized

    return list(merged.values())


def _normalize_remote_item(item: dict[str, Any]) -> dict[str, Any]:
    """将远程索引条目标准化为前端期望的格式。

    远程 index.json 中的字段可能与本地 CATALOG_PLUGINS 格式略有差异，
    此函数负责补齐缺失字段、统一 author 结构等。
    """
    # 处理 author 字段（远程可能是 string 或 object）
    author = item.get("author", "")
    if isinstance(author, str):
        author_obj = {"id": "", "name": author, "avatar": "", "verified": False}
    elif isinstance(author, dict):
        author_obj = {
            "id": author.get("id", ""),
            "name": author.get("name", ""),
            "avatar": author.get("avatar", ""),
            "verified": author.get("verified", False),
        }
    else:
        author_obj = {"id": "", "name": "Unknown", "avatar": "", "verified": False}

    # 处理 tags（远程可能是 string[] 或 object[]）
    raw_tags = item.get("tags", [])
    if raw_tags and isinstance(raw_tags[0], str):
        tags = [{"id": t, "name": t, "color": "#888"} for t in raw_tags]
    else:
        tags = raw_tags

    description = item.get("description", "")
    return {
        "id": item.get("id", ""),
        "type": "plugin",
        "name": item.get("name", item.get("id", "")),
        "description": description,
        "summary": item.get("summary", description[:60] + "..." if len(description) > 60 else description),
        "version": item.get("version", "0.0.0"),
        "author": author_obj,
        "category": item.get("category", ""),
        "tags": tags,
        "icon": item.get("icon", ""),
        "license": item.get("license", ""),
        "platform": item.get("platform", "backend"),
        "minAppVersion": item.get("minAppVersion", ""),
        "repo": item.get("repo", ""),
        "downloadUrl": item.get("downloadUrl", ""),
        "homepage": item.get("homepage", item.get("repo", "")),
        "createdAt": item.get("createdAt", ""),
        "updatedAt": item.get("updatedAt", ""),
        "installStatus": "none",
        "isFavorite": False,
        "featured": item.get("featured", False),
        "rating": item.get("rating", 0.0),
        "ratingCount": item.get("ratingCount", 0),
        "downloadCount": item.get("downloadCount", 0),
        "installedCount": item.get("installedCount", 0),
        "likeCount": item.get("likeCount", 0),
        "versions": item.get("versions", []),
        "screenshots": item.get("screenshots", []),
        "source": "remote",
    }
