"""插件市场发布源管理模块。

负责：
- 维护默认发布源列表（GitHub Raw / jsDelivr / Gcore / 自定义）
- 持久化用户选择的活跃源
- 根据 source 的 urlPattern 构造 index.json 下载 URL
- 提供延迟测试接口（供后端 API 调用）

持久化：活跃源选择与自定义源覆盖属于用户配置（不可重建），存储在 config_items
表（通过 luominest_config_store，SQLite），参与统一备份链路。注意与 repo_sources_store
（用户添加的 GitHub 仓库来源，独立 SQLite 表）无关，二者数据不重叠。
遗留 JSON 文件 registry_source.json 仅在首次迁移时幂等合并一次，不删除。
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Optional

import httpx
from loguru import logger

from app.core.config import settings
from app.infrastructure.database.config_store import luominest_config_store

# config_items 存储键（config_items 为唯一权威源）
_KEY_ACTIVE_SOURCE_ID = "registry_source.active_source_id"
_KEY_CUSTOM_SOURCES = "registry_source.custom_sources"

# 遗留 JSON 文件（DATA_DIR/store/）—— 收敛后仅在迁移时读取一次，不再写入，也不删除文件本身
_LEGACY_JSON_FILENAME = "registry_source.json"
# _migration_meta 标记源名：与 json_to_sqlite_migrator 共用同一标记表，谁先执行谁标记，避免重复合并
_MIGRATION_SOURCE = "registry_source"
_legacy_merged = False

# 发布源默认字段（用于补全缺失字段）
_DEFAULT_SOURCE_KEYS = {"type", "baseUrl", "urlPattern", "enabled"}


def _merge_legacy_json() -> None:
    """幂等合并遗留 JSON 文件（registry_source.json）到 config_items。

    参照 json_to_sqlite_migrator 的 _migration_meta 标记模式：
    - 已标记迁移 → 直接跳过（重跑不重复合并）
    - JSON 文件不存在 → 仅记录标记
    - JSON 文件存在 → config_items 为权威源，遗留值仅补缺（已有键不覆盖）
    遗留 JSON 文件是用户数据：仅迁移时读取，不删除文件本身。
    """
    global _legacy_merged
    if _legacy_merged:
        return

    try:
        from app.infrastructure.database.migration.json_to_sqlite_migrator import (
            _is_migrated,
            _mark_migrated,
            _read_json_file,
        )

        if _is_migrated(_MIGRATION_SOURCE):
            _legacy_merged = True
            return

        path = os.path.join(settings.DATA_DIR, "store", _LEGACY_JSON_FILENAME)
        data = _read_json_file(path)
        count = 0
        if isinstance(data, dict):
            legacy_active = data.get("active_source_id")
            if (
                isinstance(legacy_active, str)
                and legacy_active
                and not luominest_config_store.get(_KEY_ACTIVE_SOURCE_ID)
            ):
                luominest_config_store.set(_KEY_ACTIVE_SOURCE_ID, legacy_active)
                count += 1
            legacy_custom = data.get("custom_sources")
            if (
                isinstance(legacy_custom, list)
                and legacy_custom
                and luominest_config_store.get(_KEY_CUSTOM_SOURCES) is None
            ):
                luominest_config_store.set(_KEY_CUSTOM_SOURCES, legacy_custom)
                count += 1

        _mark_migrated(_MIGRATION_SOURCE, count)
        _legacy_merged = True
        if count:
            logger.info(
                f"[RegistrySource] Merged legacy JSON into config_items: {count} key(s)"
            )
    except Exception as e:
        logger.warning(f"[RegistrySource] Legacy JSON merge skipped: {e}")


def get_registry_sources() -> list[dict[str, Any]]:
    """获取配置中的发布源列表，并补全缺失字段。

    自定义发布源（custom-cdn）的 baseUrl 会从持久化存储中合并，
    方便开发者在不修改配置文件的情况下测试自建 CDN。
    """
    _merge_legacy_json()
    sources = list(settings.REGISTRY_SOURCES or [])
    custom_overrides = luominest_config_store.get(_KEY_CUSTOM_SOURCES) or []
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
    _merge_legacy_json()
    stored = luominest_config_store.get(_KEY_ACTIVE_SOURCE_ID)
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
    _merge_legacy_json()
    source = get_source_by_id(source_id)
    if not source:
        logger.warning(f"[RegistrySource] Invalid source id: {source_id}")
        return False
    if not source.get("enabled"):
        logger.warning(f"[RegistrySource] Source disabled, cannot activate: {source_id}")
        return False
    luominest_config_store.set(_KEY_ACTIVE_SOURCE_ID, source_id)
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

    仅持久化 custom-cdn 条目的覆盖值，不写入其他默认源，确保后续配置升级
    或修改 settings.REGISTRY_SOURCES 时默认源地址能正常生效。
    """
    _merge_legacy_json()
    clean_url = base_url.strip().rstrip("/")
    # 读取已有的持久化覆盖列表（仅 custom-cdn 及未来其他自定义源）
    custom_overrides = luominest_config_store.get(_KEY_CUSTOM_SOURCES) or []
    if not isinstance(custom_overrides, list):
        custom_overrides = []
    # 移除旧的 custom-cdn 条目，保留其他自定义源覆盖
    others = [s for s in custom_overrides if isinstance(s, dict) and s.get("id") != "custom-cdn"]
    others.append({"id": "custom-cdn", "baseUrl": clean_url})
    luominest_config_store.set(_KEY_CUSTOM_SOURCES, others)
    logger.info(f"[RegistrySource] Custom CDN baseUrl updated: {clean_url}")
    return True


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
    """并发测试所有发布源（含已禁用）的延迟。

    与 ``get_registry_sources()`` 行为一致，返回完整列表供 marketplace.py 展示与选择；
    前端依据 ``enabled`` / ``healthy`` 字段决定是否可选。
    """
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
