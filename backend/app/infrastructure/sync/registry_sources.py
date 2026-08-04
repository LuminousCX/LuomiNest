"""插件市场发布源管理模块。

负责：
- 维护默认发布源列表（GitHub Raw / jsDelivr / Gcore / 自定义）
- 持久化用户选择的活跃源
- 根据 source 的 urlPattern 构造 index.json 下载 URL
- 提供延迟测试接口（供后端 API 调用）
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

import httpx
from loguru import logger

from app.core.config import settings
from app.infrastructure.database.json_store import JsonStore

# 持久化存储当前活跃源
_source_store = JsonStore("registry_source.json")

# 发布源默认字段（用于补全缺失字段）
_DEFAULT_SOURCE_KEYS = {"type", "baseUrl", "urlPattern", "enabled"}


def get_registry_sources() -> list[dict[str, Any]]:
    """获取配置中的发布源列表，并补全缺失字段。

    自定义发布源（custom-cdn）的 baseUrl 会从持久化存储中合并，
    方便开发者在不修改配置文件的情况下测试自建 CDN。
    """
    sources = list(settings.REGISTRY_SOURCES or [])
    custom_overrides = _source_store.get("custom_sources") or []
    override_map = {s.get("id"): s for s in custom_overrides if isinstance(s, dict) and s.get("id")}

    result = []
    for s in sources:
        normalized = {
            "id": str(s.get("id", "")),
            "name": str(s.get("name", "未命名")),
            "type": str(s.get("type", "github")),
            "baseUrl": str(s.get("baseUrl", "")),
            "urlPattern": str(s.get("urlPattern", "raw")),
            "enabled": bool(s.get("enabled", True)),
        }
        # 合并持久化的自定义源覆盖
        if normalized["id"] in override_map:
            override = override_map[normalized["id"]]
            if "baseUrl" in override:
                normalized["baseUrl"] = str(override["baseUrl"]).strip().rstrip("/")
            if "urlPattern" in override:
                normalized["urlPattern"] = str(override["urlPattern"])
        # custom 源没有 baseUrl 时默认 disabled
        if normalized["id"] == "custom-cdn" and not normalized["baseUrl"].strip():
            normalized["enabled"] = False
        result.append(normalized)
    return result


def get_active_source_id() -> str:
    """获取当前活跃发布源 ID（先从持久化读取， fallback 到默认）。"""
    stored = _source_store.get("active_source_id")
    if isinstance(stored, str) and stored:
        # 确认该源存在于配置中
        if any(s["id"] == stored for s in get_registry_sources()):
            return stored
    return settings.REGISTRY_ACTIVE_SOURCE_ID


def set_active_source_id(source_id: str) -> bool:
    """设置当前活跃发布源 ID 并持久化。

    Returns:
        True if source_id is valid and persisted, False otherwise.
    """
    source = get_source_by_id(source_id)
    if not source:
        logger.warning(f"[RegistrySource] Invalid source id: {source_id}")
        return False
    if not source.get("enabled"):
        logger.warning(f"[RegistrySource] Source disabled, cannot activate: {source_id}")
        return False
    _source_store.set("active_source_id", source_id)
    logger.info(f"[RegistrySource] Active source switched to: {source_id}")
    return True


def get_source_by_id(source_id: str) -> Optional[dict[str, Any]]:
    """按 ID 获取发布源配置。"""
    for s in get_registry_sources():
        if s["id"] == source_id:
            return s
    return None


def build_registry_url(source: Optional[dict[str, Any]] = None) -> str:
    """根据发布源构造 index.json 下载 URL。

    Args:
        source: 发布源配置。None 则使用当前活跃源。

    Returns:
        完整的 index.json URL 字符串。
    """
    if source is None:
        source = get_source_by_id(get_active_source_id())
    if source is None:
        # fallback 到 github raw
        source = get_source_by_id("github-raw") or {"baseUrl": "https://raw.githubusercontent.com", "urlPattern": "raw"}

    base_url = source.get("baseUrl", "").rstrip("/")
    pattern = source.get("urlPattern", "raw")
    owner = settings.REGISTRY_REPO_OWNER
    repo = settings.REGISTRY_REPO_NAME
    branch = settings.REGISTRY_BRANCH
    path = settings.REGISTRY_INDEX_PATH.lstrip("/")

    if pattern == "gh":
        # jsDelivr 风格: {baseUrl}/{owner}/{repo}@{branch}/{path}
        return f"{base_url}/{owner}/{repo}@{branch}/{path}"
    # raw 风格: {baseUrl}/{owner}/{repo}/{branch}/{path}
    return f"{base_url}/{owner}/{repo}/{branch}/{path}"


def set_custom_source_base_url(base_url: str) -> bool:
    """设置自定义发布源的 baseUrl（仅开发者/高级用户）。

    不启用该源，仅更新配置中的 URL。启用仍需要手动切换。
    """
    sources = get_registry_sources()
    updated = False
    for s in sources:
        if s["id"] == "custom-cdn":
            s["baseUrl"] = base_url.strip().rstrip("/")
            # 没有 URL 时保持 disabled
            s["enabled"] = bool(s["baseUrl"])
            updated = True
            break
    if updated:
        _source_store.set("custom_sources", sources)
        logger.info(f"[RegistrySource] Custom CDN baseUrl updated: {base_url}")
    return updated


async def ping_source(source: dict[str, Any], timeout: float = 5.0) -> dict[str, Any]:
    """测试单个发布源的延迟和可用性。

    使用 HEAD 请求访问 index.json，记录响应时间。HEAD 失败时降级为 GET。

    Returns:
        {"latencyMs": int, "healthy": bool, "statusCode": int|None, "error": str|None}
    """
    url = build_registry_url(source)
    start = time.perf_counter()
    latency_ms = -1
    status_code: Optional[int] = None
    error_msg: Optional[str] = None
    healthy = False

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            # 先尝试 HEAD，很多 CDN 支持
            try:
                resp = await client.head(url, timeout=timeout)
                status_code = resp.status_code
                if resp.status_code < 400:
                    healthy = True
            except Exception:
                # HEAD 不支持时降级 GET（只读前几个字节）
                resp = await client.get(url, timeout=timeout)
                status_code = resp.status_code
                if resp.status_code < 400:
                    healthy = True
        latency_ms = int((time.perf_counter() - start) * 1000)
    except httpx.TimeoutException:
        latency_ms = int((time.perf_counter() - start) * 1000) if latency_ms < 0 else 9999
        error_msg = "请求超时"
    except httpx.RequestError as e:
        latency_ms = int((time.perf_counter() - start) * 1000) if latency_ms < 0 else 9999
        error_msg = f"网络错误: {e}"
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000) if latency_ms < 0 else 9999
        error_msg = f"异常: {e}"

    if latency_ms < 0:
        latency_ms = 9999

    return {
        "latencyMs": latency_ms,
        "healthy": healthy,
        "statusCode": status_code,
        "error": error_msg,
    }


async def ping_all_sources(timeout: float = 5.0) -> list[dict[str, Any]]:
    """并发测试所有启用的发布源延迟。"""
    sources = get_registry_sources()

    async def _wrap(s: dict[str, Any]) -> dict[str, Any]:
        ping = await ping_source(s, timeout=timeout)
        return {
            **s,
            "latencyMs": ping["latencyMs"],
            "healthy": ping["healthy"],
            "statusCode": ping["statusCode"],
            "error": ping["error"],
            "active": s["id"] == get_active_source_id(),
        }

    results = await asyncio.gather(*[_wrap(s) for s in sources])
    # 按延迟排序（健康的在前）
    results.sort(key=lambda x: (not x["healthy"], x["latencyMs"]))
    return results
