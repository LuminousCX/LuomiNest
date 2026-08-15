"""Linux 应用启动适配器。

搜索来源：
1. /usr/share/applications/*.desktop 文件（解析 Name= 和 Exec= 行）
2. /usr/local/share/applications/*.desktop
3. ~/.local/share/applications/*.desktop
4. which 命令查找可执行文件

启动方式：
- .desktop 应用：gtk-launch（优先）或 xdg-open
- which 结果：直接执行

模糊匹配：Name 包含关键词（case-insensitive）。
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import time
from pathlib import Path

from loguru import logger

from app.core.ports.app_launcher import AppInfo


# 搜索超时保护（秒）
_SEARCH_TIMEOUT = 5.0

# .desktop 文件搜索路径（按优先级）
_DESKTOP_FILE_DIRS = [
    Path("/usr/share/applications"),
    Path("/usr/local/share/applications"),
    Path.home() / ".local" / "share" / "applications",
]


def _app_id_from_path(path: str) -> str:
    """根据路径生成稳定的 app_id（MD5 前 12 位）。"""
    return hashlib.md5(path.lower().encode("utf-8")).hexdigest()[:12]


def _parse_desktop_file(desktop_path: Path) -> tuple[str | None, str | None, str | None]:
    """解析 .desktop 文件，提取 Name / Exec / Icon。

    只读取 [Desktop Entry] 段中的相关字段。
    返回 (name, exec_command, icon)。
    """
    name: str | None = None
    exec_cmd: str | None = None
    icon: str | None = None

    try:
        with open(desktop_path, "r", encoding="utf-8", errors="replace") as f:
            in_desktop_entry = False
            for line in f:
                line = line.strip()

                if line == "[Desktop Entry]":
                    in_desktop_entry = True
                    continue
                elif line.startswith("["):
                    # 进入其他段，停止解析
                    if in_desktop_entry:
                        break
                    continue

                if not in_desktop_entry:
                    continue

                if line.startswith("Name=") and name is None:
                    name = line[5:].strip()
                elif line.startswith("Exec=") and exec_cmd is None:
                    exec_cmd = line[5:].strip()
                elif line.startswith("Icon=") and icon is None:
                    icon = line[5:].strip()

                # 三个字段都找到了，提前退出
                if name and exec_cmd and icon:
                    break

    except (OSError, UnicodeDecodeError) as e:
        logger.debug(f"[LinuxAdapter] 解析 {desktop_path} 失败: {e}")

    return name, exec_cmd, icon


def _clean_exec_command(exec_cmd: str) -> str:
    """清理 Exec= 值，去除 %f / %F / %u / %U 等占位符。

    参考 freedesktop Desktop Entry Spec。
    """
    # 去除常见的 field codes
    parts = exec_cmd.split()
    cleaned = [p for p in parts if not p.startswith("%")]
    return " ".join(cleaned).strip()


class LinuxAdapter:
    """Linux 应用启动适配器。

    搜索 .desktop 文件和 which 命令，使用 gtk-launch 或 xdg-open 启动。

    Usage:
        adapter = LinuxAdapter()
        if adapter.available():
            apps = adapter.search_apps("firefox")
            adapter.launch(apps[0]["app_id"])
    """

    def __init__(self) -> None:
        self._cache: dict[str, AppInfo] = {}

    def _search_desktop_files(self, keyword: str, limit: int) -> list[AppInfo]:
        """从 .desktop 文件搜索应用。"""
        keyword_lower = keyword.lower()
        results: list[AppInfo] = []
        deadline = time.monotonic() + _SEARCH_TIMEOUT

        for search_dir in _DESKTOP_FILE_DIRS:
            if time.monotonic() > deadline:
                logger.warning("[LinuxAdapter] .desktop 搜索超时")
                break
            if len(results) >= limit:
                break

            if not search_dir.is_dir():
                continue

            try:
                for desktop_file in search_dir.glob("*.desktop"):
                    if time.monotonic() > deadline:
                        break
                    if len(results) >= limit:
                        break

                    name, exec_cmd, icon = _parse_desktop_file(desktop_file)
                    if not name or not exec_cmd:
                        continue

                    # 跳过 NoDisplay 和隐藏条目（简化：只检查文件名中是否包含常见系统条目）
                    if keyword_lower not in name.lower():
                        continue

                    clean_exec = _clean_exec_command(exec_cmd)
                    if not clean_exec:
                        continue

                    app_id = _app_id_from_path(str(desktop_file))

                    if app_id in self._cache:
                        continue

                    info: AppInfo = {
                        "app_id": app_id,
                        "name": name,
                        "path": clean_exec,
                        "source": "applications",
                    }
                    if icon:
                        info["icon"] = icon

                    self._cache[app_id] = info
                    results.append(info)

            except PermissionError as e:
                logger.debug(f"[LinuxAdapter] 权限不足: {search_dir} - {e}")
            except OSError as e:
                logger.debug(f"[LinuxAdapter] 遍历异常: {search_dir} - {e}")

        return results

    def _search_which(self, keyword: str, limit: int) -> list[AppInfo]:
        """通过 which 命令查找可执行文件（补充搜索）。"""
        keyword_lower = keyword.lower()
        results: list[AppInfo] = []

        which_result = shutil.which(keyword_lower)
        if which_result:
            app_id = _app_id_from_path(which_result)
            if app_id not in self._cache:
                info: AppInfo = {
                    "app_id": app_id,
                    "name": keyword_lower,
                    "path": which_result,
                    "source": "which",
                }
                self._cache[app_id] = info
                results.append(info)

        return results

    def search_apps(self, keyword: str, limit: int = 20) -> list[AppInfo]:
        """按关键词搜索已安装应用。

        搜索顺序：.desktop 文件 -> which 命令（补充）。
        """
        if not keyword or not keyword.strip():
            return []

        logger.info(f"[LinuxAdapter] 搜索应用: keyword={keyword!r}, limit={limit}")

        self._cache.clear()
        results: list[AppInfo] = []

        # 1. .desktop 文件搜索
        results.extend(self._search_desktop_files(keyword, limit))

        # 2. which 补充搜索
        if len(results) < limit:
            results.extend(self._search_which(keyword, limit - len(results)))

        logger.info(f"[LinuxAdapter] 返回 {len(results)} 条结果")
        return results[:limit]

    def launch(self, app_id: str) -> bool:
        """启动指定应用。

        优先使用 gtk-launch（.desktop 应用），回退到 xdg-open，最后直接执行。
        """
        info = self._cache.get(app_id)
        if not info:
            logger.warning(f"[LinuxAdapter] 未找到 app_id={app_id}，请先执行 search_apps")
            return False

        app_name = info.get("name", "")
        app_path = info.get("path", "")
        source = info.get("source", "")

        # 对 .desktop 来源，优先用 gtk-launch
        if source == "applications":
            # 从路径中提取 .desktop 文件名
            desktop_name = Path(app_path).name if app_path.endswith(".desktop") else None

            # 尝试 gtk-launch
            for launcher in ["gtk-launch", "xdg-open"]:
                try:
                    cmd = [launcher]
                    if launcher == "gtk-launch" and desktop_name:
                        cmd.append(desktop_name)
                    else:
                        cmd.append(app_path)

                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        timeout=10,
                    )
                    if result.returncode == 0:
                        logger.info(f"[LinuxAdapter] 已启动 ({launcher}): {app_name}")
                        return True
                    logger.debug(f"[LinuxAdapter] {launcher} 返回 {result.returncode}")
                except FileNotFoundError:
                    continue
                except subprocess.TimeoutExpired:
                    logger.warning(f"[LinuxAdapter] {launcher} 启动超时: {app_name}")
                    continue

        # 回退：直接执行命令
        try:
            parts = app_path.split()
            subprocess.Popen(
                parts,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            logger.info(f"[LinuxAdapter] 已启动（直接执行）: {app_name}")
            return True
        except Exception as e:
            logger.error(f"[LinuxAdapter] 启动失败: {app_path} - {e}", exc_info=True)
            return False

    def available(self) -> bool:
        """Linux 平台可用。"""
        import sys
        return sys.platform.startswith("linux")
