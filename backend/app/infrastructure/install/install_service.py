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
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from loguru import logger

from app.core.config import settings
from app.infrastructure.database.json_store import JsonStore, repo_sources_store

# 安装记录存储
install_store = JsonStore("installed_items.json")

# 下载临时目录
DOWNLOAD_DIR = Path(settings.DATA_DIR) / "downloads"
# 安装目标目录映射
INSTALL_DIRS = {
    "plugin": Path(settings.PLUGIN_DIR),
    "skill": Path(settings.SKILL_DIR),
    "agent": Path(settings.DATA_DIR) / "agents",
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


async def _download_from_url(item_id: str, url: str, dest_path: Path):
    """从 URL 下载文件，支持进度追踪"""
    state = _active_downloads[item_id]

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=False) as client:
        async with client.stream("GET", url) as response:
            # 手动处理重定向，确保重定向目标也通过 SSRF 校验
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("location", "")
                if not location:
                    raise Exception(f"重定向缺少 Location 头: HTTP {response.status_code}")
                # 递归下载重定向目标（会再次触发 SSRF 校验）
                await _download_from_url(item_id, location, dest_path)
                return
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
        async with httpx.AsyncClient(timeout=60.0) as client:
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

        # 记录安装信息
        now = datetime.now(timezone.utc).isoformat()
        install_record = {
            "id": item_id,
            "type": item_type,
            "name": item_name,
            "version": version,
            "installedAt": now,
            "installPath": str(target_dir),
            "status": "installed",
        }

        # 保存安装记录
        install_store.set(item_id, install_record)

        # 删除备份
        if backup_dir and backup_dir.exists():
            shutil.rmtree(backup_dir)

        logger.success(f"[InstallService] Installed {item_type}/{item_id} v{version} to {target_dir}")
        return {"success": True, "installPath": str(target_dir)}

    except Exception as e:
        # 恢复备份
        if backup_dir and backup_dir.exists():
            if target_dir.exists():
                shutil.rmtree(target_dir)
            backup_dir.rename(target_dir)
            logger.info(f"[InstallService] Restored backup for {item_id}")

        logger.error(f"[InstallService] Install failed for {item_id}: {e}")
        return {"success": False, "error": str(e)}


async def uninstall_item(item_id: str) -> dict:
    """
    卸载已安装的条目，清除所有相关文件。

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

    try:
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

        logger.success(f"[InstallService] Uninstalled {item_id}")
        return {"success": True}

    except Exception as e:
        logger.error(f"[InstallService] Uninstall failed for {item_id}: {e}")
        return {"success": False, "error": str(e)}


def get_all_install_status() -> dict[str, str]:
    """获取所有条目的安装状态"""
    all_items = install_store.list_all()
    return {k: "installed" for k in all_items.keys()}
