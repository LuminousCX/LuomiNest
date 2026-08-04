"""插件注册表远程同步模块 — 从 GitHub 索引仓库拉取最新插件目录。

架构：
  远程索引仓库 (cxp-registry/index.json)
    ↓ 定时/手动拉取
  本地缓存 (registry_cache.json)
    ↓ 合并
  市场 API /items 返回完整列表

附加能力：
  - publish_local_plugins: 将本地 backend/plugins/ 中的插件元数据
    推送到 cxp-registry 仓库的 index.json（需要 GitHub Token）
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

import httpx
import yaml
from loguru import logger

from app.core.config import settings
from app.infrastructure.database.json_store import JsonStore
from app.infrastructure.sync.registry_sources import build_registry_url, get_active_source_id

# 缓存刷新间隔（秒），默认 6 小时
CACHE_TTL_SECONDS = 6 * 60 * 60

# cxp-registry 仓库的 GitHub API 写入端点（用于 publish_local_plugins 推送 index.json）
# 命名规则：每个插件一个独立 GitHub 仓库 LuomiNest-cxp-<plugin-name>，
# registry 仓库仅维护 index.json 聚合元数据。
REGISTRY_REPO_OWNER = settings.REGISTRY_REPO_OWNER
REGISTRY_REPO_NAME = settings.REGISTRY_REPO_NAME
REGISTRY_INDEX_PATH = settings.REGISTRY_INDEX_PATH
REGISTRY_BRANCH = settings.REGISTRY_BRANCH

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


def get_cached_plugins() -> list[dict[str, Any]]:
    """读取本地缓存中的插件列表（不触发远程拉取）。

    供 marketplace API 在不需要等待远程同步的场景下快速返回缓存数据。
    """
    return list(_get_cache().get("plugins", []))


def get_cached_skills() -> list[dict[str, Any]]:
    """读取本地缓存中的技能列表（不触发远程拉取）。"""
    return list(_get_cache().get("skills", []))


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

    registry_url = build_registry_url()
    source_id = get_active_source_id()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(registry_url)
            resp.raise_for_status()
            data = resp.json()

        plugins = data.get("plugins", [])
        skills = data.get("skills", [])
        logger.info(
            f"[RegistrySync] Fetched {len(plugins)} plugins, "
            f"{len(skills)} skills from source={source_id}"
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


# ---------------------------------------------------------------------------
# 本地插件元数据采集（用于 publish_local_plugins）
# ---------------------------------------------------------------------------


def _collect_local_plugin_metadata(plugin_dir: str) -> list[dict[str, Any]]:
    """扫描 backend/plugins/ 下所有插件的 manifest.json，组装 registry 索引条目。

    仅采集"源码即元数据"的字段：id/name/version/description/author/category/tags/
    icon/platform/license/minAppVersion。不采集 downloadCount/ratingCount 等动态
    统计字段（由 marketplace_stats_store 单独维护）。

    Args:
        plugin_dir: 插件根目录（settings.PLUGIN_DIR）

    Returns:
        registry 索引 plugins 数组中的条目列表
    """
    items: list[dict[str, Any]] = []
    if not os.path.isdir(plugin_dir):
        return items

    for entry in sorted(os.listdir(plugin_dir)):
        if entry.startswith(".") or entry.startswith("_"):
            continue
        entry_path = os.path.join(plugin_dir, entry)
        if not os.path.isdir(entry_path):
            continue
        manifest_path = os.path.join(entry_path, "manifest.json")
        if not os.path.isfile(manifest_path):
            continue
        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception as e:
            logger.warning(f"[RegistrySync] Failed to load manifest {manifest_path}: {e}")
            continue

        plugin_id = str(manifest.get("id", entry))
        # 跳过 p7 这种占位/测试插件（无 main.py 或 manifest 缺关键字段）
        if not manifest.get("name") or not manifest.get("version"):
            continue
        # 至少需要一个 entry 文件（main.py 或 manifest.entry 指定的文件）
        entry_field = str(manifest.get("entry", "main"))
        entry_file = os.path.join(entry_path, f"{entry_field}.py")
        if not os.path.isfile(entry_file):
            logger.debug(f"[RegistrySync] Skipping {plugin_id}: entry file {entry_file} not found")
            continue

        # 跳过占位/自动生成的 manifest（如 "plugin package: my-plugin"）
        description = str(manifest.get("description", ""))
        if description.startswith("plugin package:") or description.startswith("skill package:"):
            logger.debug(
                f"[RegistrySync] Skipping placeholder plugin {plugin_id}: "
                f"auto-generated manifest"
            )
            continue

        # 推导 GitHub 仓库与下载 URL（遵循 docs/development/plugin-system.md 命名规范）
        # 仓库名: LuomiNest-cxp-<plugin_id 去掉 cxp- 前缀>
        # downloadUrl: https://github.com/{owner}/{repo}/releases/latest/download/{plugin_id}.zip
        repo_name_suffix = plugin_id[4:] if plugin_id.startswith("cxp-") else plugin_id
        repo_name = f"LuomiNest-cxp-{repo_name_suffix}"
        repo_url = f"https://github.com/{REGISTRY_REPO_OWNER}/{repo_name}"
        download_url = (
            f"https://github.com/{REGISTRY_REPO_OWNER}/{repo_name}"
            f"/releases/latest/download/{plugin_id}.zip"
        )

        # author 标准化为 object（与 _normalize_remote_item 反向兼容）
        raw_author = manifest.get("author", "")
        if isinstance(raw_author, str):
            author_obj = {"name": raw_author, "url": ""}
        elif isinstance(raw_author, dict):
            author_obj = {
                "name": raw_author.get("name", ""),
                "url": raw_author.get("url", ""),
            }
        else:
            author_obj = {"name": "", "url": ""}

        today = time.strftime("%Y-%m-%d", time.gmtime())
        items.append({
            "id": plugin_id,
            "name": str(manifest.get("name", plugin_id)),
            "version": str(manifest.get("version", "0.0.0")),
            "description": str(manifest.get("description", "")),
            "author": author_obj,
            "category": str(manifest.get("category", "tool")),
            "tags": list(manifest.get("tags", [])),
            "icon": str(manifest.get("icon", "")),
            "platform": str(manifest.get("platform", "backend")),
            "license": str(manifest.get("license", "")),
            "minAppVersion": str(manifest.get("minAppVersion", "")),
            "repo": repo_url,
            "downloadUrl": download_url,
            "createdAt": "",
            "updatedAt": today,
        })

    return items


def _collect_local_skill_metadata(skill_dir: str) -> list[dict[str, Any]]:
    """扫描 backend/skills/ 下所有技能，组装 registry 索引条目。

    支持 SKILL.md（YAML frontmatter）与 manifest.json 两种格式。
    """
    items: list[dict[str, Any]] = []
    if not os.path.isdir(skill_dir):
        return items

    for entry in sorted(os.listdir(skill_dir)):
        if entry.startswith(".") or entry.startswith("_"):
            continue
        entry_path = os.path.join(skill_dir, entry)
        if not os.path.isdir(entry_path):
            continue

        skill_md_path = os.path.join(entry_path, "SKILL.md")
        manifest_path = os.path.join(entry_path, "manifest.json")
        meta: dict[str, Any] = {}

        if os.path.isfile(skill_md_path):
            try:
                with open(skill_md_path, encoding="utf-8") as f:
                    content = f.read()
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        fm = yaml.safe_load(parts[1])
                        if not isinstance(fm, dict):
                            logger.warning(
                                f"[RegistrySync] SKILL.md frontmatter 非字典: {skill_md_path} "
                                f"(type={type(fm).__name__})，跳过该技能"
                            )
                            continue
                        meta = fm
            except Exception as e:
                logger.warning(f"[RegistrySync] Failed to parse SKILL.md {skill_md_path}: {e}")
                continue
        elif os.path.isfile(manifest_path):
            try:
                with open(manifest_path, encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception as e:
                logger.warning(f"[RegistrySync] Failed to parse manifest {manifest_path}: {e}")
                continue
        else:
            continue

        skill_id = str(meta.get("id", entry))
        if not meta.get("name") or not meta.get("version"):
            continue

        # 跳过占位/自动生成的 manifest（如 "skill package: skill-docx"）
        # 这类 manifest 由 install_service._create_simulated_package 自动生成，
        # 不是真正可分发的技能，不应进入 cxp-registry。
        description = str(meta.get("description", ""))
        if description.startswith("skill package:") or description.startswith("plugin package:"):
            logger.debug(
                f"[RegistrySync] Skipping placeholder skill {skill_id}: "
                f"auto-generated manifest"
            )
            continue

        # 技能集合仓库模式：所有技能在 LuomiNest-cxp-skills 仓库下，子目录为技能 id
        repo_url = f"https://github.com/{REGISTRY_REPO_OWNER}/LuomiNest-cxp-skills"
        download_url = (
            f"https://github.com/{REGISTRY_REPO_OWNER}/LuomiNest-cxp-skills"
            f"/releases/latest/download/skill-{skill_id}.zip"
        )

        raw_author = meta.get("author", "")
        if isinstance(raw_author, str):
            author_obj = {"name": raw_author, "url": ""}
        elif isinstance(raw_author, dict):
            author_obj = {
                "name": raw_author.get("name", ""),
                "url": raw_author.get("url", ""),
            }
        else:
            author_obj = {"name": "", "url": ""}

        today = time.strftime("%Y-%m-%d", time.gmtime())
        items.append({
            "id": skill_id,
            "name": str(meta.get("name", skill_id)),
            "version": str(meta.get("version", "0.0.0")),
            "description": str(meta.get("description", "")),
            "author": author_obj,
            "category": str(meta.get("category", "")),
            "tags": list(meta.get("tags", [])),
            "icon": str(meta.get("icon", "")),
            "license": str(meta.get("license", "")),
            "repo": repo_url,
            "downloadUrl": download_url,
            "createdAt": "",
            "updatedAt": today,
        })

    return items


def build_registry_index(
    plugins: Optional[list[dict[str, Any]]] = None,
    skills: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """根据本地 plugins/skills 目录构建 index.json 内容。

    Args:
        plugins: 可选，已采集的插件元数据列表。未提供时从 settings.PLUGIN_DIR 扫描。
        skills:  可选，已采集的技能元数据列表。未提供时从 settings.SKILL_DIR 扫描。

    Returns:
        与 docs/development/plugin-system.md 中 index.json 格式一致的 dict，
        可直接 json.dump 写入 LuomiNest-cxp-registry/index.json。
    """
    if plugins is None:
        plugins = _collect_local_plugin_metadata(settings.PLUGIN_DIR)
    if skills is None:
        skills = _collect_local_skill_metadata(settings.SKILL_DIR)

    return {
        "version": "1.0.0",
        "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "plugins": plugins,
        "skills": skills,
    }


def write_local_index_snapshot(output_path: Optional[str] = None) -> str:
    """生成一份本地 index.json 快照，写入指定路径（默认 backend/app/data/cxp-registry-index.json）。

    用于：
    1. 开发者本地预览将要推送到远程仓库的 index.json 内容
    2. CI/CD 在 release 时自动生成并提交到 cxp-registry 仓库
    3. 离线场景下作为本地 fallback 数据源

    Args:
        output_path: 输出文件路径。None 则使用默认路径。

    Returns:
        实际写入的文件绝对路径
    """
    if output_path is None:
        # 默认放到 backend/app/data/ 下，与 avatar-manifest.json、marketplace_catalog.py 同级
        output_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "cxp-registry-index.json")
        output_path = os.path.abspath(output_path)

    index_data = build_registry_index()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)
    logger.info(
        f"[RegistrySync] Local index snapshot written: {output_path} "
        f"({len(index_data['plugins'])} plugins, {len(index_data['skills'])} skills)"
    )
    return output_path


def _preserve_created_at(
    local_item: dict[str, Any],
    remote_item: Optional[dict[str, Any]],
) -> None:
    """合并时保留远程条目已有的 createdAt，避免每次发布用当天时间重置。

    - 远程已有 createdAt → 覆盖本地值（本地采集时留空）
    - 远程无/不存在且本地也缺失 → 以本次发布时间回填（全新插件）
    """
    remote_created = (remote_item or {}).get("createdAt", "")
    if remote_created:
        local_item["createdAt"] = remote_created
    elif not local_item.get("createdAt"):
        local_item["createdAt"] = time.strftime("%Y-%m-%d", time.gmtime())


async def publish_local_plugins_to_registry(
    github_token: Optional[str] = None,
    bump_updated_at: bool = True,
) -> dict[str, Any]:
    """将本地 plugins/skills 元数据推送到远程 cxp-registry 仓库的 index.json。

    流程：
      1. 扫描本地 settings.PLUGIN_DIR 与 settings.SKILL_DIR
      2. 合并现有远程 index.json（保留非本地条目，按 id 覆盖本地条目）
      3. 通过 GitHub Contents API PUT 更新 index.json

    需要 GitHub Token（PAT）有 cxp-registry 仓库的 contents:write 权限。
    Token 来源优先级：参数 > settings.GITHUB_TOKEN > 环境变量 LUOMINEST_GITHUB_TOKEN。

    Args:
        github_token: GitHub Personal Access Token（需要 repo 权限或 fine-grained contents:write）
        bump_updated_at: 是否更新 index.json 顶层 updatedAt 字段为当前时间

    Returns:
        {"success": bool, "message": str, "commit_sha"?: str, "url"?: str}
    """
    token = github_token or settings.GITHUB_TOKEN or os.environ.get("LUOMINEST_GITHUB_TOKEN", "")
    if not token:
        return {
            "success": False,
            "message": (
                "未配置 GitHub Token。请在 settings.GITHUB_TOKEN 或环境变量 "
                "LUOMINEST_GITHUB_TOKEN 中设置有 cxp-registry 仓库写入权限的 PAT。"
            ),
        }

    # 1. 采集本地元数据
    local_plugins = _collect_local_plugin_metadata(settings.PLUGIN_DIR)
    local_skills = _collect_local_skill_metadata(settings.SKILL_DIR)
    logger.info(
        f"[RegistrySync] Publishing {len(local_plugins)} plugins, "
        f"{len(local_skills)} skills to remote registry"
    )

    # 2. 拉取现有远程 index.json（保留非本地条目，避免误删第三方插件）
    api_base = f"https://api.github.com/repos/{REGISTRY_REPO_OWNER}/{REGISTRY_REPO_NAME}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {token}",
    }

    existing_index: dict[str, Any] = {"plugins": [], "skills": []}
    existing_sha: Optional[str] = None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{api_base}/contents/{REGISTRY_INDEX_PATH}?ref={REGISTRY_BRANCH}",
                headers=headers,
            )
            if resp.status_code == 200:
                data = resp.json()
                existing_sha = data.get("sha")
                download_url = data.get("download_url")
                if download_url:
                    content_resp = await client.get(download_url)
                    if content_resp.status_code == 200:
                        existing_index = content_resp.json()
            elif resp.status_code == 404:
                logger.info("[RegistrySync] Remote index.json not found, creating new file")
            else:
                return {
                    "success": False,
                    "message": f"GitHub API 返回 {resp.status_code}: {resp.text[:200]}",
                }
    except Exception as e:
        return {"success": False, "message": f"拉取远程 index.json 失败: {e}"}

    # 3. 合并：本地条目覆盖远程（按 id 索引），保留远程独有的条目
    merged_plugins: dict[str, dict[str, Any]] = {
        p.get("id", ""): p for p in existing_index.get("plugins", []) if p.get("id")
    }
    for p in local_plugins:
        _preserve_created_at(p, merged_plugins.get(p["id"]))
        merged_plugins[p["id"]] = p

    merged_skills: dict[str, dict[str, Any]] = {
        s.get("id", ""): s for s in existing_index.get("skills", []) if s.get("id")
    }
    for s in local_skills:
        _preserve_created_at(s, merged_skills.get(s["id"]))
        merged_skills[s["id"]] = s

    new_index = {
        "version": existing_index.get("version", "1.0.0"),
        "updatedAt": (
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            if bump_updated_at else existing_index.get("updatedAt", "")
        ),
        "plugins": list(merged_plugins.values()),
        "skills": list(merged_skills.values()),
    }

    # 4. 本地写一份快照备份（便于排查）
    try:
        write_local_index_snapshot()
    except Exception as e:
        logger.warning(f"[RegistrySync] Failed to write local snapshot: {e}")

    # 5. PUT 到 GitHub Contents API
    import base64
    content_bytes = json.dumps(new_index, ensure_ascii=False, indent=2).encode("utf-8")
    content_b64 = base64.b64encode(content_bytes).decode("ascii")

    payload = {
        "message": f"chore(registry): sync local plugins/skills ({len(local_plugins)}+{len(local_skills)})",
        "content": content_b64,
        "branch": REGISTRY_BRANCH,
        "committer": {
            "name": "LuomiNest Registry Sync",
            "email": "luominest-bot@users.noreply.github.com",
        },
    }
    if existing_sha:
        payload["sha"] = existing_sha

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.put(
                f"{api_base}/contents/{REGISTRY_INDEX_PATH}",
                headers=headers,
                json=payload,
            )
        if resp.status_code in (200, 201):
            data = resp.json()
            commit = data.get("commit", {})
            logger.success(
                f"[RegistrySync] Published index.json: "
                f"sha={commit.get('sha', '')[:8]}, "
                f"plugins={len(new_index['plugins'])}, skills={len(new_index['skills'])}"
            )
            return {
                "success": True,
                "message": "发布成功",
                "commit_sha": commit.get("sha", ""),
                "url": commit.get("html_url", ""),
                "plugins_count": len(new_index["plugins"]),
                "skills_count": len(new_index["skills"]),
            }
        return {
            "success": False,
            "message": f"GitHub PUT 失败: {resp.status_code} {resp.text[:300]}",
        }
    except Exception as e:
        return {"success": False, "message": f"PUT index.json 异常: {e}"}

