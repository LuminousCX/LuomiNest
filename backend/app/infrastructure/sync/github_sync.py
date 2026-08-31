"""
GitHub 仓库同步服务
- 从 GitHub 仓库拉取 manifest.json 并解析为市场条目
- 支持缓存策略（内存缓存 + 磁盘持久化）
- 支持 GitHub Token 认证
- 完善的错误处理
"""

import hashlib
import os
import time
import asyncio
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import httpx
from loguru import logger

from app.core.utils import utc_now
from app.core.constants.colors import TAG_COLOR_NEUTRAL
from app.infrastructure.database.json_store import JsonStore
from app.infrastructure.sync.schemas import GitHubMarketplaceEntry, ManifestItem

# ---------------------------------------------------------------------------
# 缓存 Store
# ---------------------------------------------------------------------------
# 有意保留文件存储：可重建缓存，不入库 —— 内容为远程 GitHub 仓库 manifest 的同步快照，
# 30 分钟 TTL，可从远程仓库完全重建，不含用户状态
_sync_cache_store = JsonStore("repo_sync_cache.json")

# ---------------------------------------------------------------------------
# GitHub API 常量
# ---------------------------------------------------------------------------
GITHUB_RAW_BASE = "https://raw.githubusercontent.com"
GITHUB_API_BASE = "https://api.github.com"

# manifest 文件名（仓库根目录下的索引文件）
MANIFEST_FILENAME = "manifest.json"

# 默认缓存 TTL（秒）: 30 分钟
DEFAULT_CACHE_TTL = 30 * 60

# 请求超时
REQUEST_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# 数据模型（ManifestItem / 输出条目见 sync/schemas.py，alias 序列化统一映射）
# ---------------------------------------------------------------------------

def _parse_manifest_item(data: dict) -> ManifestItem:
    """解析 manifest.json 条目：已知 key 入模型字段，未知 key 归入 extra。"""
    known_keys = {f.alias or name for name, f in ManifestItem.model_fields.items()}
    extra = {k: v for k, v in data.items() if k not in known_keys}
    return ManifestItem(**data, extra=extra)


class SyncResult:
    """同步操作的结果"""
    def __init__(
        self,
        source_id: str,
        sub_market_id: str,
        items: list[dict],
        total: int,
        synced_at: str,
        from_cache: bool = False,
        error: Optional[str] = None,
    ):
        self.source_id = source_id
        self.sub_market_id = sub_market_id
        self.items = items
        self.total = total
        self.synced_at = synced_at
        self.from_cache = from_cache
        self.error = error

    def to_dict(self) -> dict:
        return {
            "sourceId": self.source_id,
            "subMarketId": self.sub_market_id,
            "items": self.items,
            "total": self.total,
            "syncedAt": self.synced_at,
            "fromCache": self.from_cache,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# GitHub 仓库 URL 解析
# ---------------------------------------------------------------------------

def parse_github_url(url: str) -> Optional[tuple[str, str]]:
    """
    解析 GitHub 仓库 URL，返回 (owner, repo) 或 None。
    支持格式:
      - https://github.com/owner/repo
      - https://github.com/owner/repo.git
      - git@github.com:owner/repo.git
    """
    url = url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]

    if url.startswith("git@github.com:"):
        parts = url[len("git@github.com:"):].split("/")
        if len(parts) >= 2:
            return parts[0], parts[1]

    parsed = urlparse(url)
    if "github.com" in (parsed.hostname or ""):
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 2:
            return parts[0], parts[1]

    return None


# ---------------------------------------------------------------------------
# GitHub Token 管理
# ---------------------------------------------------------------------------

def get_github_token() -> Optional[str]:
    """从环境变量或配置获取 GitHub Token"""
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        return token
    try:
        from app.core.config import settings
        token = getattr(settings, "GITHUB_TOKEN", "")
    except Exception as e:
        logger.debug(f"[GitHubSync] Failed to read GITHUB_TOKEN from settings: {e}")
    return token or None


# ---------------------------------------------------------------------------
# 核心同步逻辑
# ---------------------------------------------------------------------------

async def fetch_manifest_from_github(
    owner: str,
    repo: str,
    branch: str = "main",
    token: Optional[str] = None,
) -> dict:
    """
    从 GitHub 仓库拉取 manifest.json 文件内容。
    优先使用 raw.githubusercontent.com，失败后回退到 GitHub API。
    """
    headers: dict[str, str] = {
        "Accept": "application/vnd.github.v3+json",
    }
    if token:
        headers["Authorization"] = f"token {token}"

    # 尝试 raw URL（更快、无 API 速率限制）
    raw_url = f"{GITHUB_RAW_BASE}/{owner}/{repo}/{branch}/{MANIFEST_FILENAME}"
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        try:
            resp = await client.get(raw_url, headers=headers)
            if resp.status_code == 200:
                logger.debug(f"[GitHubSync] Fetched manifest via raw URL: {raw_url}")
                return resp.json()
            logger.debug(f"[GitHubSync] Raw URL returned {resp.status_code}, trying API...")
        except Exception as e:
            logger.debug(f"[GitHubSync] Raw URL failed: {e}, trying API...")

        # 回退到 GitHub API（支持私有仓库 + Token）
        api_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{MANIFEST_FILENAME}?ref={branch}"
        try:
            resp = await client.get(api_url, headers=headers)
            if resp.status_code == 200:
                import base64
                data = resp.json()
                content = data.get("content", "")
                if data.get("encoding") == "base64" and content:
                    decoded = base64.b64decode(content).decode("utf-8")
                    import json
                    return json.loads(decoded)
            logger.warning(f"[GitHubSync] API returned {resp.status_code} for {api_url}")
            raise Exception(f"GitHub API returned {resp.status_code}")
        except Exception as e:
            logger.error(f"[GitHubSync] Failed to fetch manifest from {owner}/{repo}: {e}")
            raise


async def fetch_repo_tree(
    owner: str,
    repo: str,
    branch: str = "main",
    token: Optional[str] = None,
) -> list[dict]:
    """
    当仓库没有 manifest.json 时，回退到扫描仓库目录结构。
    查找每个子目录中的 item.json 或 meta.json 作为条目定义。
    """
    headers: dict[str, str] = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    tree_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        try:
            resp = await client.get(tree_url, headers=headers)
            if resp.status_code == 200:
                return resp.json().get("tree", [])
            logger.warning(f"[GitHubSync] Tree API returned {resp.status_code}")
            return []
        except Exception as e:
            logger.error(f"[GitHubSync] Failed to fetch repo tree: {e}")
            return []


def parse_manifest_to_items(manifest: dict, repo_url: str) -> list[dict]:
    """
    将 manifest.json 解析为标准化的市场条目列表。
    manifest.json 格式:
    {
      "version": "1.0",
      "items": [
        {
          "id": "my-plugin",
          "name": "My Plugin",
          "type": "plugin",
          "summary": "...",
          ...
        }
      ]
    }
    """
    items = manifest.get("items", [])
    if not items and isinstance(manifest, list):
        items = manifest

    result = []
    now = utc_now()
    for raw in items:
        if not isinstance(raw, dict):
            continue
        item = _parse_manifest_item(raw)
        # 补全必要字段（使用确定性哈希，包含仓库信息避免跨源碰撞）
        if not item.id:
            item.id = f"{item.type}-{hashlib.md5((repo_url + item.name).encode()).hexdigest()[:6]}"
        if not item.created_at:
            item.created_at = now
        if not item.updated_at:
            item.updated_at = now
        if not item.repository:
            item.repository = repo_url

        result.append(GitHubMarketplaceEntry(
            id=item.id,
            name=item.name,
            type=item.type,
            summary=item.summary,
            description=item.description,
            icon=item.icon,
            category=item.category,
            tags=_normalize_tags(item.tags),
            version=item.version,
            author=_normalize_author(item.author),
            homepage=item.homepage,
            repository=item.repository,
            license=item.license,
            rating=item.rating or 0.0,
            download_count=item.download_count or 0,
            installed_count=item.installed_count or 0,
            featured=item.featured or False,
            screenshots=item.screenshots,
            versions=item.versions,
            size=item.size,
            min_app_version=item.min_app_version,
            created_at=item.created_at,
            updated_at=item.updated_at,
            download_url=item.download_url,
            extra=item.extra,
        ).model_dump(by_alias=True))
    return result


# ---------------------------------------------------------------------------
# 缓存管理
# ---------------------------------------------------------------------------

def get_cached_items(source_id: str, sub_market_id: str) -> Optional[SyncResult]:
    """从磁盘缓存读取同步结果"""
    cache_key = f"{source_id}::{sub_market_id}"
    cached = _sync_cache_store.get(cache_key)
    if not cached:
        return None

    # 检查 TTL
    synced_at = cached.get("syncedAt", "")
    if synced_at:
        try:
            synced_time = datetime.fromisoformat(synced_at)
            elapsed = (datetime.now(timezone.utc) - synced_time).total_seconds()
            if elapsed > DEFAULT_CACHE_TTL:
                logger.debug(f"[GitHubSync] Cache expired for {cache_key}")
                return None
        except Exception as e:
            logger.debug(f"[GitHubSync] Cache TTL check failed for {cache_key}: {e}")

    return SyncResult(
        source_id=cached.get("sourceId", source_id),
        sub_market_id=cached.get("subMarketId", sub_market_id),
        items=cached.get("items", []),
        total=cached.get("total", 0),
        synced_at=cached.get("syncedAt", ""),
        from_cache=True,
    )


def save_to_cache(result: SyncResult):
    """将同步结果保存到磁盘缓存"""
    cache_key = f"{result.source_id}::{result.sub_market_id}"
    _sync_cache_store.set(cache_key, result.to_dict())
    logger.debug(f"[GitHubSync] Cached {len(result.items)} items for {cache_key}")


# ---------------------------------------------------------------------------
# 主同步入口
# ---------------------------------------------------------------------------

async def fetch_dir_listing(
    owner: str,
    repo: str,
    path: str = "",
    branch: str = "main",
    token: Optional[str] = None,
) -> list[dict]:
    """获取仓库指定路径下的目录列表"""
    headers: dict[str, str] = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}?ref={branch}"
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception as e:
            logger.error(f"[GitHubSync] Failed to fetch dir listing: {e}")
            return []


async def fetch_sub_manifest(
    owner: str,
    repo: str,
    sub_dir: str,
    branch: str = "main",
    token: Optional[str] = None,
) -> Optional[dict]:
    """拉取子目录中的 manifest.json"""
    headers: dict[str, str] = {
        "Accept": "application/vnd.github.v3+json",
    }
    if token:
        headers["Authorization"] = f"token {token}"

    # 先尝试 raw URL
    raw_url = f"{GITHUB_RAW_BASE}/{owner}/{repo}/{branch}/{sub_dir}/{MANIFEST_FILENAME}"
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        try:
            resp = await client.get(raw_url, headers=headers)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.debug(f"[GitHubSync] Raw URL fetch failed for {owner}/{repo}: {e}")

        # 回退到 API
        api_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{sub_dir}/{MANIFEST_FILENAME}?ref={branch}"
        try:
            resp = await client.get(api_url, headers=headers)
            if resp.status_code == 200:
                import base64, json
                data = resp.json()
                content = data.get("content", "")
                if data.get("encoding") == "base64" and content:
                    decoded = base64.b64decode(content).decode("utf-8")
                    return json.loads(decoded)
        except Exception as e:
            logger.debug(f"[GitHubSync] API fetch failed for {owner}/{repo}: {e}")

    return None


def _normalize_author(author_data) -> dict:
    """将 author 字段规范化为前端期望的 {id, name, verified} 格式"""
    if isinstance(author_data, dict):
        return {
            "id": author_data.get("id", author_data.get("name", "unknown")),
            "name": author_data.get("name", "unknown"),
            "avatar": author_data.get("avatar", ""),
            "verified": author_data.get("verified", False),
        }
    if isinstance(author_data, str) and author_data:
        return {
            "id": author_data.lower().replace(" ", "-"),
            "name": author_data,
            "avatar": "",
            "verified": False,
        }
    return {"id": "unknown", "name": "未知", "avatar": "", "verified": False}


def _normalize_tags(tags_data) -> list[dict]:
    """将 tags 字段规范化为前端期望的 [{id, name, color}] 格式"""
    result = []
    if isinstance(tags_data, list):
        for i, tag in enumerate(tags_data):
            if isinstance(tag, dict):
                result.append({
                    "id": tag.get("id", f"tag-{i}"),
                    "name": tag.get("name", str(tag)),
                    "color": tag.get("color", TAG_COLOR_NEUTRAL),
                })
            elif isinstance(tag, str) and tag:
                result.append({
                    "id": f"tag-{tag}",
                    "name": tag,
                    "color": TAG_COLOR_NEUTRAL,
                })
    return result


def parse_single_manifest(manifest: dict, repo_url: str) -> Optional[dict]:
    """
    将单个子目录的 manifest.json 解析为一个市场条目。
    单个 manifest 格式：
    {
      "id": "cooking-assistant",
      "type": "skill",
      "name": "烹饪助手",
      ...
    }
    """
    if not isinstance(manifest, dict):
        return None

    item = _parse_manifest_item(manifest)
    now = utc_now()

    if not item.id:
        return None
    if not item.created_at:
        item.created_at = now
    if not item.updated_at:
        item.updated_at = now
    if not item.repository:
        item.repository = repo_url

    return GitHubMarketplaceEntry(
        id=item.id,
        name=item.name,
        type=item.type,
        summary=item.summary,
        description=item.description,
        icon=item.icon,
        category=item.category,
        tags=_normalize_tags(item.tags),
        version=item.version,
        author=_normalize_author(item.author),
        homepage=item.homepage,
        repository=item.repository,
        license=item.license,
        rating=item.rating or 0.0,
        download_count=item.download_count or 0,
        installed_count=item.installed_count or 0,
        featured=item.featured or False,
        screenshots=item.screenshots,
        versions=item.versions,
        size=item.size,
        min_app_version=item.min_app_version,
        created_at=item.created_at,
        updated_at=item.updated_at,
        download_url=item.download_url,
        extra=item.extra,
    ).model_dump(by_alias=True)


async def sync_sub_market(
    source_id: str,
    sub_market_id: str,
    sub_market_url: str,
    force: bool = False,
) -> SyncResult:
    """
    同步单个子市场的内容。

    支持两种仓库结构：
    1. 根目录有 manifest.json（包含所有条目）
    2. 每个子目录有独立的 manifest.json（每个子目录是一个条目）

    Args:
        source_id: 仓库来源 ID
        sub_market_id: 子市场 ID
        sub_market_url: 子市场 GitHub URL
        force: 是否强制刷新（忽略缓存）

    Returns:
        SyncResult
    """
    # 1. 检查缓存
    if not force:
        cached = get_cached_items(source_id, sub_market_id)
        if cached and cached.items:
            logger.info(f"[GitHubSync] Using cached data for {sub_market_id}")
            return cached

    # 2. 解析 GitHub URL
    parsed = parse_github_url(sub_market_url)
    if not parsed:
        error_msg = f"Invalid GitHub URL: {sub_market_url}"
        logger.error(f"[GitHubSync] {error_msg}")
        return SyncResult(
            source_id=source_id,
            sub_market_id=sub_market_id,
            items=[],
            total=0,
            synced_at=utc_now(),
            error=error_msg,
        )

    owner, repo = parsed
    token = get_github_token()
    now = utc_now()

    # 3. 先尝试根目录的 manifest.json
    try:
        manifest = await fetch_manifest_from_github(owner, repo, token=token)
        items = parse_manifest_to_items(manifest, sub_market_url)
        if items:
            result = SyncResult(
                source_id=source_id,
                sub_market_id=sub_market_id,
                items=items,
                total=len(items),
                synced_at=now,
            )
            save_to_cache(result)
            logger.success(f"[GitHubSync] Synced {len(items)} items from root manifest of {owner}/{repo}")
            return result
    except Exception as e:
        logger.debug(f"[GitHubSync] Root manifest not found for {owner}/{repo}: {e}")

    # 4. 根目录没有 manifest，扫描子目录
    logger.info(f"[GitHubSync] No root manifest, scanning sub-directories of {owner}/{repo}")
    try:
        dir_listing = await fetch_dir_listing(owner, repo, token=token)
    except Exception as e:
        error_msg = f"Failed to scan repo directory: {e}"
        logger.error(f"[GitHubSync] {error_msg}")
        cached = get_cached_items(source_id, sub_market_id)
        if cached and cached.items:
            return cached
        return SyncResult(
            source_id=source_id,
            sub_market_id=sub_market_id,
            items=[],
            total=0,
            synced_at=now,
            error=error_msg,
        )

    # 过滤出子目录
    sub_dirs = [d["name"] for d in dir_listing if d.get("type") == "dir" and not d["name"].startswith(".")]
    if not sub_dirs:
        error_msg = f"No sub-directories found in {owner}/{repo}"
        logger.warning(f"[GitHubSync] {error_msg}")
        return SyncResult(
            source_id=source_id,
            sub_market_id=sub_market_id,
            items=[],
            total=0,
            synced_at=now,
            error=error_msg,
        )

    # 5. 并发拉取每个子目录的 manifest.json
    items = []
    errors = []
    fetch_tasks = []
    for d in sub_dirs:
        fetch_tasks.append(fetch_sub_manifest(owner, repo, d, token=token))

    manifest_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

    for i, mr in enumerate(manifest_results):
        if isinstance(mr, Exception):
            errors.append(f"{sub_dirs[i]}: {mr}")
            continue
        if mr is None:
            logger.debug(f"[GitHubSync] No manifest in {sub_dirs[i]}")
            continue
        item = parse_single_manifest(mr, sub_market_url)
        if item:
            items.append(item)

    error_msg = "; ".join(errors) if errors else None
    result = SyncResult(
        source_id=source_id,
        sub_market_id=sub_market_id,
        items=items,
        total=len(items),
        synced_at=now,
        error=error_msg,
    )
    save_to_cache(result)

    logger.success(f"[GitHubSync] Synced {len(items)} items from {len(sub_dirs)} sub-dirs of {owner}/{repo}")
    return result


async def sync_source(source_id: str, source_data: dict, force: bool = False) -> list[SyncResult]:
    """
    同步整个仓库来源（包含所有已链接的子市场）。

    Args:
        source_id: 仓库来源 ID
        source_data: 仓库来源数据（包含 sub_markets）
        force: 是否强制刷新

    Returns:
        所有子市场的同步结果列表
    """
    sub_markets = source_data.get("sub_markets", [])
    linked_sub_markets = [sm for sm in sub_markets if sm.get("linked", True)]

    if not linked_sub_markets:
        logger.info(f"[GitHubSync] No linked sub-markets for source {source_id}")
        return []

    results = []
    # 并发同步所有子市场
    tasks = []
    for sm in linked_sub_markets:
        sm_url = sm.get("url", "")
        if not sm_url:
            continue
        tasks.append(sync_sub_market(source_id, sm["id"], sm_url, force=force))

    sync_results = await asyncio.gather(*tasks, return_exceptions=True)

    for i, r in enumerate(sync_results):
        if isinstance(r, Exception):
            sm = linked_sub_markets[i]
            logger.error(f"[GitHubSync] Sync failed for {sm.get('id')}: {r}")
            results.append(SyncResult(
                source_id=source_id,
                sub_market_id=sm.get("id", ""),
                items=[],
                total=0,
                synced_at=utc_now(),
                error=str(r),
            ))
        else:
            results.append(r)

    return results


def get_all_cached_items(source_id: str, source_data: dict) -> list[dict]:
    """
    获取某个仓库来源下所有已缓存的市场条目（不触发网络请求）。
    用于快速加载已缓存的内容。
    """
    all_items = []
    sub_markets = source_data.get("sub_markets", [])

    for sm in sub_markets:
        if not sm.get("linked", True):
            continue
        cached = get_cached_items(source_id, sm.get("id", ""))
        if cached and cached.items:
            all_items.extend(cached.items)

    return all_items


def clear_cache(source_id: Optional[str] = None, sub_market_id: Optional[str] = None):
    """清除缓存"""
    if source_id and sub_market_id:
        cache_key = f"{source_id}::{sub_market_id}"
        _sync_cache_store.delete(cache_key)
    elif source_id:
        # 仅清除该 source_id 下的所有子市场缓存
        prefix = f"{source_id}::"
        for key in list(_sync_cache_store.list_all().keys()):
            if key.startswith(prefix):
                _sync_cache_store.delete(key)
    else:
        _sync_cache_store.clear()
    logger.info(f"[GitHubSync] Cache cleared for source={source_id}, sub_market={sub_market_id}")
