"""
市场内容安装/卸载服务

负责从远程下载内容包、安装到本地、管理安装状态、卸载清理等。
"""
import asyncio
import json
import os
import shutil
import time
import zipfile
from pathlib import Path
from typing import Optional

import httpx
from loguru import logger

from app.core.config import settings
from app.core.utils import utc_now
from app.infrastructure.database.config_namespace_store import ConfigNamespaceStore
from app.infrastructure.database.json_store import repo_sources_store
from app.security.net.safe_url import assert_url_safe, create_safe_async_client, UnsafeUrlError

# 安装记录存储（config_items 为唯一权威源；遗留 installed_items.json
# 首次访问时幂等并集合并，旧文件保留不删除）
install_store = ConfigNamespaceStore(
    "install.items",
    legacy_source="installed_items",
    legacy_filename="installed_items.json",
)

# 下载临时目录
DOWNLOAD_DIR = Path(settings.DATA_DIR) / "downloads"
# 安装目标目录映射
INSTALL_DIRS = {
    "plugin": Path(settings.PLUGIN_DIR),
    "skill": Path(settings.SKILL_DIR),
    "agent": Path(settings.DATA_DIR) / "agents",
}

# localPath 前缀映射（与 resolve_install_path 的 base_map 保持一致）
# 用于在安装记录中写入可移植的相对路径，如 "plugins/cxp-pdf-reader"
_LOCAL_PATH_PREFIX = {
    "plugin": "plugins",
    "skill": "skills",
    "agent": "agents",
}

# 内存中的下载任务状态
_active_downloads: dict[str, dict] = {}


def _ensure_dirs():
    """确保必要目录存在"""
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    for d in INSTALL_DIRS.values():
        d.mkdir(parents=True, exist_ok=True)


def get_installed_items() -> list[dict]:
    """获取所有已安装条目列表"""
    return install_store.all()


def get_installed_item(item_id: str) -> Optional[dict]:
    """获取单个已安装条目"""
    return install_store.get(item_id)


def is_installed(item_id: str) -> bool:
    """检查条目是否已安装"""
    return get_installed_item(item_id) is not None


def get_download_status(item_id: str) -> Optional[dict]:
    """获取下载任务状态，错误状态超过60秒自动清理"""
    status = _active_downloads.get(item_id)
    if status and status.get("status") == "error":
        start_time = status.get("startTime", 0)
        if time.time() - start_time > 60:
            del _active_downloads[item_id]
            return None
    return status


def get_download(item_id: str) -> Optional[dict]:
    """获取下载任务的原始状态（纯读取，不做错误状态过期清理）。

    与 get_download_status 的区别：本函数不清理过期错误状态，
    供需要原始状态判断的场景使用（如 install 端点的并发去重检查）。
    """
    return _active_downloads.get(item_id)


def register_download(item_id: str) -> dict:
    """注册新的下载任务（queued 初始状态）并返回状态字典。

    get-or-create 语义：同 ID 任务已存在时直接返回现有状态、
    不覆盖，供 install 端点防止并发请求创建重复后台任务。
    """
    if item_id in _active_downloads:
        return _active_downloads[item_id]
    _active_downloads[item_id] = {
        "itemId": item_id,
        "status": "queued",
        "progress": 0,
        "message": "排队等待中...",
        "speed": 0,
        "eta": 0,
        "downloadedBytes": 0,
        "totalBytes": 0,
        "startTime": time.time(),
    }
    return _active_downloads[item_id]


def update_download_state(item_id: str, **fields) -> Optional[dict]:
    """更新下载任务的任意状态字段（仅对已存在的任务生效）。

    任务不存在时不创建、静默忽略并返回 None；存在则原地更新
    并返回状态字典。
    """
    state = _active_downloads.get(item_id)
    if state is None:
        return None
    state.update(fields)
    return state


async def download_item(
    item_id: str,
    download_url: str,
    item_type: str,
    item_name: str,
    version: str = "1.0.0",
) -> dict:
    """
    下载市场内容包。

    Args:
        item_id: 条目 ID
        download_url: 下载 URL
        item_type: 条目类型 (plugin/skill/agent)
        item_name: 条目名称
        version: 版本号

    Returns:
        下载结果字典
    """
    _ensure_dirs()

    # 本地内置插件短路:不走下载流程,直接走"启用"路径。
    # 前端 builtin 插件由 MarketView 调用 enableFrontendPlugin 启用,
    # 后端插件由 luominest_plugin_loader.load_single + lifecycle.enable_plugin 启用。
    from app.data.marketplace_catalog import get_local_builtin_plugin
    local_entry = get_local_builtin_plugin(item_id)
    if local_entry is not None:
        return await install_local_builtin_plugin(
            item_id=item_id,
            item_name=item_name or local_entry.get("name", item_id),
            version=version or local_entry.get("version", "1.0.0"),
            local_entry=local_entry,
        )

    # 如果已在下载中，返回当前状态
    if item_id in _active_downloads and _active_downloads[item_id].get("status") == "downloading":
        return _active_downloads[item_id]

    # 初始化下载状态
    download_state = {
        "itemId": item_id,
        "status": "downloading",
        "progress": 0,
        "message": "正在下载...",
        "speed": 0,
        "eta": 0,
        "downloadedBytes": 0,
        "totalBytes": 0,
        "startTime": time.time(),
    }
    _active_downloads[item_id] = download_state

    try:
        # 确定下载目标路径
        filename = f"{item_id}-{version}.zip"
        dest_path = DOWNLOAD_DIR / filename
        temp_path = DOWNLOAD_DIR / f"{filename}.tmp"

        # 如果有 download_url，从远程下载
        if download_url:
            await _download_from_url(item_id, download_url, temp_path)
        else:
            # 没有 download_url，从 GitHub 仓库源构建
            await _download_from_github_source(item_id, item_type, temp_path)

        # 下载完成，重命名临时文件
        if temp_path.exists():
            if dest_path.exists():
                dest_path.unlink()
            temp_path.rename(dest_path)

        # 更新状态为安装中
        _active_downloads[item_id]["status"] = "installing"
        _active_downloads[item_id]["progress"] = 0
        _active_downloads[item_id]["message"] = "正在安装..."

        # 执行安装
        install_result = await install_from_archive(item_id, dest_path, item_type, item_name, version)

        if install_result.get("success"):
            _active_downloads[item_id]["status"] = "installed"
            _active_downloads[item_id]["progress"] = 100
            _active_downloads[item_id]["message"] = "安装完成"

            # 清理下载文件
            if dest_path.exists():
                dest_path.unlink()
        else:
            _active_downloads[item_id]["status"] = "error"
            _active_downloads[item_id]["message"] = install_result.get("error", "安装失败")
            _active_downloads[item_id]["error"] = install_result.get("error", "安装失败")

        return _active_downloads[item_id]

    except Exception as e:
        logger.error(f"[InstallService] Download/install failed for {item_id}: {e}")
        _active_downloads[item_id]["status"] = "error"
        _active_downloads[item_id]["message"] = f"下载失败: {str(e)}"
        _active_downloads[item_id]["error"] = str(e)
        return _active_downloads[item_id]


async def install_local_builtin_plugin(
    item_id: str,
    item_name: str,
    version: str,
    local_entry: dict,
) -> dict:
    """安装本地内置插件 — 不下载,仅启用后端 + 写入安装记录。

    用于 LOCAL_PLUGIN_REPO 中 source="local" 且 frontendBuiltin=True 的插件。
    后端插件目录已存在于 settings.PLUGIN_DIR/{item_id},此处只需:
    1. 调用 luominest_plugin_loader.load_single 加载后端插件
    2. 调用 luominest_plugin_lifecycle.enable_plugin 启用
    3. 写入 install_store 记录,标记 source="builtin" 与 frontendBuiltin=True
    4. 同步 _active_downloads 状态,前端轮询 download-progress 时能拿到 installed

    Args:
        item_id: 插件 ID
        item_name: 插件名称(用于日志与安装记录)
        version: 版本号
        local_entry: LOCAL_PLUGIN_REPO 中的条目 dict

    Returns:
        与 download_item 相同结构的进度 dict,但 status 直接为 installed
    """
    from app.core.config import settings
    from app.runtime.plugin.cxplugin.loader import luominest_plugin_loader
    from app.runtime.plugin.cxplugin.registry import luominest_plugin_registry
    from app.runtime.plugin.cxplugin.lifecycle import luominest_plugin_lifecycle

    # 初始化进度状态(供前端轮询)
    # frontendBuiltin 从 local_entry 读取，决定前端是否同步启用 builtin 视图
    _frontend_builtin = bool(local_entry.get("frontendBuiltin", True))
    _active_downloads[item_id] = {
        "itemId": item_id,
        "status": "installing",
        "progress": 30,
        "message": "正在启用本地插件...",
        "speed": 0,
        "eta": 0,
        "downloadedBytes": 0,
        "totalBytes": 0,
        "startTime": time.time(),
        "frontendBuiltin": _frontend_builtin,
    }

    plugin_dir = Path(settings.PLUGIN_DIR) / item_id
    try:
        # 后端插件若未加载,先 load_single
        if luominest_plugin_registry.get_plugin(item_id) is None:
            ok = await luominest_plugin_loader.load_single(str(plugin_dir))
            if not ok:
                logger.warning(
                    f"[InstallService] Builtin plugin load_single failed: {item_id} "
                    f"(dir={plugin_dir}). 仅启用前端,后端可能未提供。"
                )

        # 启用插件(若已加载)
        if luominest_plugin_registry.get_plugin(item_id) is not None:
            await luominest_plugin_lifecycle.enable_plugin(item_id)
            # 动态挂载插件 API 路由到运行中的 app（必须先 load_single 成功）
            # 未挂载时前端调用 /api/v1/plugins/{id}/extract 会 404
            try:
                applied = luominest_plugin_loader.apply_routes_for_plugin(item_id)
                if applied > 0:
                    logger.info(
                        f"[InstallService] Builtin plugin routes applied: "
                        f"{item_id} ({applied} routes)"
                    )
            except Exception as route_err:
                logger.warning(
                    f"[InstallService] apply_routes_for_plugin failed for {item_id}: "
                    f"{route_err}. 插件 API 暂不可用,需重启后端。"
                )

        # 写入安装记录（source="builtin" + frontendBuiltin 标记，
        # localPath 从 local_entry 读取，便于支持 backend-only 本地插件）
        now = utc_now()
        # localPath 优先取 LOCAL_PLUGIN_REPO 条目中的值（如 "plugins/weather-query"），
        # 兜底为 "plugins/{item_id}"（builtin 当前只支持 plugin 类型）
        local_path = local_entry.get("localPath") or f"plugins/{item_id}"
        # frontendBuiltin 从 local_entry 读取：fullstack/frontend 插件为 True，
        # 纯 backend 插件（如 weather-query）为 False，前端据此决定是否启用 builtin 视图
        frontend_builtin = bool(local_entry.get("frontendBuiltin", True))
        install_record = {
            "id": item_id,
            "type": "plugin",
            "name": item_name,
            "version": version,
            "installedAt": now,
            "installPath": str(plugin_dir),
            "localPath": local_path,
            "status": "installed",
            "source": "builtin",
            "frontendBuiltin": frontend_builtin,
        }
        install_store.set(item_id, install_record)

        _active_downloads[item_id]["status"] = "installed"
        _active_downloads[item_id]["progress"] = 100
        _active_downloads[item_id]["message"] = "安装完成"
        logger.success(
            f"[InstallService] Builtin plugin enabled: {item_id} v{version} at {plugin_dir}"
        )
    except Exception as e:
        logger.error(f"[InstallService] Builtin plugin install failed for {item_id}: {e}")
        _active_downloads[item_id]["status"] = "error"
        _active_downloads[item_id]["message"] = f"启用失败: {e}"
        _active_downloads[item_id]["error"] = str(e)

    return _active_downloads[item_id]


async def _download_from_url(item_id: str, url: str, dest_path: Path):
    """从 URL 下载文件，支持进度追踪"""
    state = _active_downloads[item_id]

    # SSRF 预校验：快速拒绝不安全 URL（实际连接时的 DNS Rebinding 防护由 SafeAsyncHTTPTransport 提供）
    await assert_url_safe(url)

    async with create_safe_async_client(timeout=120.0) as client:
        async with client.stream("GET", url) as response:
            if response.status_code != 200:
                raise Exception(f"下载失败: HTTP {response.status_code}")

            total = int(response.headers.get("content-length", 0))
            state["totalBytes"] = total
            downloaded = 0
            last_time = time.time()
            last_bytes = 0

            with open(dest_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    state["downloadedBytes"] = downloaded

                    # 计算速度和剩余时间
                    now = time.time()
                    elapsed = now - last_time
                    if elapsed >= 0.5:  # 每 0.5 秒更新一次速度
                        speed = (downloaded - last_bytes) / elapsed
                        state["speed"] = round(speed, 1)
                        if speed > 0 and total > 0:
                            remaining = (total - downloaded) / speed
                            state["eta"] = round(remaining, 1)
                        last_time = now
                        last_bytes = downloaded

                    # 更新进度
                    if total > 0:
                        state["progress"] = round((downloaded / total) * 100, 1)
                    else:
                        # 无 content-length 时使用估算
                        state["progress"] = min(round(downloaded / 1024 / 10, 1), 95)

    state["progress"] = 100
    state["speed"] = 0
    state["eta"] = 0


async def _create_simulated_package(item_id: str, item_type: str, dest_path: Path):
    """为没有远程来源的条目创建模拟安装包"""
    import json

    state = _active_downloads[item_id]
    state["message"] = "正在准备安装包..."

    # 模拟下载进度
    for pct in [20, 40, 60, 80, 100]:
        await asyncio.sleep(0.3)
        state["progress"] = pct
        state["speed"] = 1024 * 100  # 100KB/s 模拟速度
        state["eta"] = max(0, (100 - pct) * 0.3)

    # 创建包含 manifest.json 的 zip 包
    manifest = {
        "id": item_id,
        "type": item_type,
        "name": item_id,
        "version": "1.0.0",
        "description": f"{item_type} package: {item_id}",
    }

    temp_dir = DOWNLOAD_DIR / f"{item_id}_sim_tmp"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True)

    try:
        manifest_path = temp_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in temp_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(temp_dir)
                    zf.write(file_path, arcname)
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

    state["speed"] = 0
    state["eta"] = 0


async def _download_from_github_source(item_id: str, item_type: str, dest_path: Path):
    """从 GitHub 仓库源下载条目内容（打包为 zip）。
    如果找不到 GitHub 来源，则创建模拟安装包。"""
    from app.infrastructure.sync.github_sync import get_all_cached_items, get_github_token

    # 从缓存中找到该条目的来源信息
    token = get_github_token()
    source_info = _find_item_source(item_id, item_type)

    if not source_info:
        # 没有 GitHub 来源，创建模拟安装包
        logger.info(f"[InstallService] No GitHub source for {item_id}, creating simulated package")
        await _create_simulated_package(item_id, item_type, dest_path)
        return

    owner, repo, sub_path = source_info
    branch = "main"

    # 使用 GitHub API 下载子目录内容
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    state = _active_downloads[item_id]

    # 创建临时目录
    temp_dir = DOWNLOAD_DIR / f"{item_id}_tmp"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True)

    try:
        async with create_safe_async_client(timeout=60.0) as client:
            await _download_github_dir(client, owner, repo, sub_path, branch, headers, temp_dir, state)

        # 打包为 zip
        with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in temp_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(temp_dir)
                    zf.write(file_path, arcname)
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

    state["progress"] = 100


async def _download_github_dir(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    path: str,
    branch: str,
    headers: dict,
    target_dir: Path,
    state: dict,
):
    """递归下载 GitHub 仓库目录内容（支持子目录）"""
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"
    resp = await client.get(api_url, headers=headers)
    if resp.status_code != 200:
        error_detail = resp.text[:200] if resp.text else ""
        raise Exception(f"获取仓库内容失败: HTTP {resp.status_code} - {error_detail}")

    contents = resp.json()
    if not isinstance(contents, list):
        contents = [contents]

    for content_item in contents:
        item_type = content_item.get("type", "")
        item_name = content_item.get("name", "")
        if item_type == "dir":
            # 递归下载子目录
            sub_target = target_dir / item_name
            sub_target.mkdir(parents=True, exist_ok=True)
            sub_path = f"{path}/{item_name}" if path else item_name
            await _download_github_dir(client, owner, repo, sub_path, branch, headers, sub_target, state)
        elif item_type == "file":
            file_url = content_item.get("download_url")
            if not file_url:
                continue
            file_resp = await client.get(file_url, headers=headers)
            if file_resp.status_code != 200:
                raise Exception(f"下载文件失败: {item_name} HTTP {file_resp.status_code}")
            file_path = target_dir / item_name
            file_path.write_bytes(file_resp.content)
            state["downloaded"] = state.get("downloaded", 0) + 1


def _find_item_source(item_id: str, item_type: str) -> Optional[tuple]:
    """从缓存中查找条目的 GitHub 仓库来源，返回 (owner, repo, sub_path)"""
    from app.infrastructure.sync.github_sync import parse_github_url, _sync_cache_store

    sources = repo_sources_store.list_all()
    cache = _sync_cache_store.list_all()

    for source_id, source in sources.items():
        if source.get("type") != "github":
            continue
        sub_markets = source.get("sub_markets", [])
        for sm in sub_markets:
            sm_id = sm.get("id", "")
            cache_key = f"{source_id}::{sm_id}"
            cached = cache.get(cache_key, {})
            items = cached.get("items", [])
            for item in items:
                if item.get("id") == item_id:
                    url = sm.get("url", "")
                    parsed = parse_github_url(url)
                    if parsed:
                        # 返回仓库的子路径（基于 downloadUrl 推导或留空使用仓库根目录）
                        download_url = item.get("downloadUrl", "")
                        sub_path = ""
                        if download_url and "github.com" in download_url:
                            # 从 downloadUrl 中提取仓库内的路径部分
                            try:
                                from urllib.parse import urlparse
                                du = urlparse(download_url)
                                parts = du.path.strip("/").split("/")
                                # 格式: owner/repo/tree/branch/path...
                                if len(parts) > 4 and parts[2] in ("tree", "blob"):
                                    sub_path = "/".join(parts[4:])
                            except Exception as e:
                                # 非关键解析失败时保持 sub_path 为空，继续使用仓库根目录
                                logger.debug(f"解析 downloadUrl 子路径失败: {download_url}, error: {e}")
                        return parsed[0], parsed[1], sub_path

    return None


async def install_from_archive(
    item_id: str,
    archive_path: Path,
    item_type: str,
    item_name: str,
    version: str = "1.0.0",
) -> dict:
    """
    从 zip 归档安装内容。

    Args:
        item_id: 条目 ID
        archive_path: zip 文件路径
        item_type: 条目类型
        item_name: 条目名称
        version: 版本号

    Returns:
        安装结果
    """
    install_dir = INSTALL_DIRS.get(item_type)
    if not install_dir:
        return {"success": False, "error": f"不支持的类型: {item_type}"}

    target_dir = install_dir / item_id

    # 校验 item_id 是否为合法路径组件，防止路径遍历
    resolved_install = install_dir.resolve()
    resolved_target = target_dir.resolve()
    if not resolved_target.is_relative_to(resolved_install):
        return {"success": False, "error": f"非法的条目 ID: {item_id}"}

    try:
        # 如果已存在，先备份
        backup_dir = None
        if target_dir.exists():
            backup_dir = install_dir / f"{item_id}.bak"
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            target_dir.rename(backup_dir)

        # 安全解压安装（防止路径遍历 + 资源耗尽攻击）
        target_dir.mkdir(parents=True, exist_ok=True)
        resolved_target = target_dir.resolve()
        MAX_DECOMPRESSED_SIZE = 500 * 1024 * 1024  # 500MB 总解压上限
        MAX_ENTRY_SIZE = 100 * 1024 * 1024  # 单文件 100MB 上限
        MAX_ENTRY_COUNT = 10000  # 最大文件数
        total_size = 0
        entry_count = 0
        with zipfile.ZipFile(archive_path, "r") as zf:
            for entry in zf.infolist():
                entry_count += 1
                if entry_count > MAX_ENTRY_COUNT:
                    logger.warning(f"[InstallService] Exceeded max entry count ({MAX_ENTRY_COUNT}), skipping rest")
                    break
                dest_path = (resolved_target / entry.filename).resolve()
                # 拒绝绝对路径和父目录遍历
                if not dest_path.is_relative_to(resolved_target):
                    logger.warning(f"[InstallService] Skipped suspicious entry: {entry.filename}")
                    continue
                # 检查单文件大小
                if entry.file_size > MAX_ENTRY_SIZE:
                    logger.warning(f"[InstallService] Skipped oversized entry: {entry.filename} ({entry.file_size}B)")
                    continue
                total_size += entry.file_size
                if total_size > MAX_DECOMPRESSED_SIZE:
                    logger.warning(f"[InstallService] Exceeded total decompressed size limit, aborting")
                    break
                if entry.is_dir():
                    dest_path.mkdir(parents=True, exist_ok=True)
                else:
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(entry) as src, open(dest_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)

        # 写入安装记录（含 source/frontendBuiltin/localPath，便于前端区分
        # builtin 启用与远程下载，且 localPath 为相对路径，dev/打包版均可移植）
        now = utc_now()
        # 计算 localPath：带类型前缀的相对路径（如 "plugins/cxp-pdf-reader"）
        # 与 install_local_builtin_plugin 的 "plugins/{item_id}" 格式保持一致，
        # 使 get_installed_records_resolved → resolve_install_path 能跨 dev/打包模式解析。
        prefix = _LOCAL_PATH_PREFIX.get(item_type, item_type)
        relative_path = f"{prefix}/{item_id}"
        install_record = {
            "id": item_id,
            "type": item_type,
            "name": item_name,
            "version": version,
            "installedAt": now,
            "installPath": str(target_dir),
            "localPath": relative_path,
            "status": "installed",
            "source": "remote",  # 远程 zip 下载安装
            "frontendBuiltin": False,
        }

        # 保存安装记录
        install_store.set(item_id, install_record)

        # 删除备份
        if backup_dir and backup_dir.exists():
            shutil.rmtree(backup_dir)

        # 安装后自动 reload 对应的注册表
        reload_result = await _post_install_reload(item_id, item_type, str(target_dir))

        logger.success(f"[InstallService] Installed {item_type}/{item_id} v{version} to {target_dir}")
        return {
            "success": True,
            "installPath": str(target_dir),
            "reload_result": reload_result,
        }

    except Exception as e:
        # 恢复备份
        if backup_dir and backup_dir.exists():
            if target_dir.exists():
                shutil.rmtree(target_dir)
            backup_dir.rename(target_dir)
            logger.info(f"[InstallService] Restored backup for {item_id}")

        logger.error(f"[InstallService] Install failed for {item_id}: {e}")
        return {"success": False, "error": str(e)}


async def _post_install_reload(item_id: str, item_type: str, install_path: str) -> dict:
    """安装成功后自动 reload 对应的注册表，让新内容立即生效。

    Args:
        item_id: 条目 id
        item_type: 条目类型（plugin/skill/agent）
        install_path: 安装目录绝对路径

    Returns:
        reload 结果字典
    """
    result = {"attempted": False, "success": False, "error": ""}
    try:
        if item_type == "skill":
            result["attempted"] = True
            from app.runtime.plugin.skill.loader import luominest_skill_loader
            # 若已加载，先卸载
            if item_id in luominest_skill_loader.get_loaded_ids():
                await luominest_skill_loader.unload_single(item_id)
            ok = await luominest_skill_loader.load_single(install_path)
            result["success"] = ok
            if ok:
                logger.info(f"[InstallService] Auto-reloaded skill: {item_id}")
            else:
                result["error"] = "load_single returned False"
        elif item_type == "plugin":
            result["attempted"] = True
            from app.runtime.plugin.cxplugin.loader import luominest_plugin_loader
            from app.runtime.plugin.cxplugin.registry import luominest_plugin_registry
            # 若已加载，先卸载
            if luominest_plugin_registry.get_plugin(item_id) is not None:
                await luominest_plugin_loader.unload_single(item_id)
            ok = await luominest_plugin_loader.load_single(install_path)
            result["success"] = ok
            if ok:
                logger.info(f"[InstallService] Auto-reloaded plugin: {item_id}")
                # 动态挂载插件 API 路由到运行中的 app
                try:
                    applied = luominest_plugin_loader.apply_routes_for_plugin(item_id)
                    if applied > 0:
                        logger.info(
                            f"[InstallService] Plugin routes applied: "
                            f"{item_id} ({applied} routes)"
                        )
                except Exception as route_err:
                    logger.warning(
                        f"[InstallService] apply_routes_for_plugin failed for {item_id}: "
                        f"{route_err}. 插件 API 暂不可用,需重启后端。"
                    )
            else:
                result["error"] = "load_single returned False"
        # agent 类型暂无运行时注册表，跳过
    except Exception as e:
        result["error"] = str(e)
        logger.warning(f"[InstallService] Post-install reload failed for {item_type}/{item_id}: {e}")
    return result


async def uninstall_item(item_id: str) -> dict:
    """
    卸载已安装的条目，清除所有相关文件。

    对于本地内置插件(source="builtin"),仅禁用 + 移除安装记录,
    不删除插件目录文件(避免破坏随发行版分发的源码)。

    Args:
        item_id: 条目 ID

    Returns:
        卸载结果
    """
    record = get_installed_item(item_id)
    if not record:
        return {"success": False, "error": f"条目 {item_id} 未安装"}

    install_path = record.get("installPath")
    item_type = record.get("type", "")
    is_builtin = record.get("source") == "builtin" or record.get("frontendBuiltin") is True

    try:
        if is_builtin:
            # 内置插件:仅禁用后端插件,不删除文件,不卸载注册表
            try:
                from app.runtime.plugin.cxplugin.lifecycle import luominest_plugin_lifecycle
                await luominest_plugin_lifecycle.disable_plugin(item_id)
            except Exception as e:
                logger.warning(f"[InstallService] Builtin disable failed for {item_id}: {e}")
            logger.info(f"[InstallService] Builtin plugin disabled (files kept): {item_id}")
        else:
            # 先从注册表卸载（避免文件被删后引用悬空）
            await _post_uninstall_unload(item_id, item_type)

            # 删除安装目录
            if install_path and Path(install_path).exists():
                shutil.rmtree(Path(install_path))
                logger.info(f"[InstallService] Removed install dir: {install_path}")

            # 也尝试从标准安装目录删除
            install_dir = INSTALL_DIRS.get(item_type)
            if install_dir:
                std_path = install_dir / item_id
                if std_path.exists():
                    shutil.rmtree(std_path)

        # 删除安装记录
        install_store.delete(item_id)

        # 清理下载状态
        if item_id in _active_downloads:
            del _active_downloads[item_id]

        # 清理可能残留的下载文件
        for f in DOWNLOAD_DIR.glob(f"{item_id}*"):
            if f.is_file():
                f.unlink()

        logger.success(f"[InstallService] Uninstalled {item_id} (builtin={is_builtin})")
        return {"success": True, "builtin": is_builtin}

    except Exception as e:
        logger.error(f"[InstallService] Uninstall failed for {item_id}: {e}")
        return {"success": False, "error": str(e)}


async def _post_uninstall_unload(item_id: str, item_type: str) -> dict:
    """卸载前从对应注册表移除条目。

    Args:
        item_id: 条目 id
        item_type: 条目类型

    Returns:
        unload 结果字典
    """
    result = {"attempted": False, "success": False, "error": ""}
    try:
        if item_type == "skill":
            result["attempted"] = True
            from app.runtime.plugin.skill.loader import luominest_skill_loader
            if item_id in luominest_skill_loader.get_loaded_ids():
                ok = await luominest_skill_loader.unload_single(item_id)
                result["success"] = ok
                logger.info(f"[InstallService] Unloaded skill before uninstall: {item_id}")
        elif item_type == "plugin":
            result["attempted"] = True
            from app.runtime.plugin.cxplugin.loader import luominest_plugin_loader
            from app.runtime.plugin.cxplugin.registry import luominest_plugin_registry
            if luominest_plugin_registry.get_plugin(item_id) is not None:
                ok = await luominest_plugin_loader.unload_single(item_id)
                result["success"] = ok
                logger.info(f"[InstallService] Unloaded plugin before uninstall: {item_id}")
    except Exception as e:
        result["error"] = str(e)
        logger.warning(f"[InstallService] Pre-uninstall unload failed for {item_type}/{item_id}: {e}")
    return result


def get_all_install_status() -> dict[str, str]:
    """获取所有条目的安装状态"""
    all_items = install_store.list_all()
    return {k: "installed" for k in all_items.keys()}


def resolve_install_path(local_path: str) -> str:
    """将相对 localPath（如 "plugins/cxp-pdf-reader"）解析为绝对路径。

    用于跨 dev/打包模式还原安装目录：
    - dev 模式: settings.PLUGIN_DIR = backend/plugins/，解析为 backend/plugins/cxp-pdf-reader/
    - 打包模式: settings.PLUGIN_DIR = %APPDATA%/.../Data/backend/plugins/，
      解析为 %APPDATA%/.../Data/backend/plugins/cxp-pdf-reader/

    Args:
        local_path: 相对路径，形如 "plugins/{id}" 或 "skills/{id}"

    Returns:
        绝对路径字符串；无法识别时返回空字符串
    """
    if not local_path:
        return ""
    parts = Path(local_path).parts
    if not parts:
        return ""
    # 第一段为 "plugins" / "skills" / "agents"
    top = parts[0]
    sub = "/".join(parts[1:]) if len(parts) > 1 else ""
    base_map = {
        "plugins": settings.PLUGIN_DIR,
        "skills": settings.SKILL_DIR,
        "agents": str(Path(settings.DATA_DIR) / "agents"),
    }
    base = base_map.get(top)
    if not base:
        return ""
    return str(Path(base) / sub) if sub else str(base)


def get_installed_records_resolved() -> list[dict]:
    """返回所有已安装条目，installPath 已根据当前运行模式重新解析。

    用于前端展示「已安装插件列表」时，即使从其他模式迁移过来的 install_store
    也能返回当前模式下有效的绝对路径，避免悬空引用。
    """
    items = install_store.all()
    result = []
    for record in items:
        local_path = record.get("localPath", "")
        if local_path:
            resolved = resolve_install_path(local_path)
            if resolved:
                record = {**record, "installPath": resolved}
        result.append(record)
    return result
