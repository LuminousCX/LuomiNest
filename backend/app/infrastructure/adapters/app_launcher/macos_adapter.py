"""macOS 应用启动适配器。

搜索来源：
1. /Applications 目录下的 .app 包
2. ~/Applications 目录下的 .app 包

启动方式：subprocess.run(["open", "-a", name])

模糊匹配：.app 名称包含关键词（case-insensitive）。
"""
from __future__ import annotations

import hashlib
import subprocess
import time
from pathlib import Path

from loguru import logger

from app.core.ports.app_launcher import AppInfo


# 搜索超时保护（秒）
_SEARCH_TIMEOUT = 5.0


def _app_id_from_path(path: str) -> str:
    """根据路径生成稳定的 app_id（MD5 前 12 位）。"""
    return hashlib.md5(path.lower().encode("utf-8")).hexdigest()[:12]


class MacOSAdapter:
    """macOS 应用启动适配器。

    搜索 /Applications 和 ~/Applications 下的 .app 包，
    使用 `open -a` 命令启动应用。

    Usage:
        adapter = MacOSAdapter()
        if adapter.available():
            apps = adapter.search_apps("safari")
            adapter.launch(apps[0]["app_id"])
    """

    def __init__(self) -> None:
        self._cache: dict[str, AppInfo] = {}

    def _scan_applications_dir(self, search_dir: Path, keyword_lower: str, limit: int, deadline: float) -> list[AppInfo]:
        """扫描指定目录下的 .app 包。

        仅搜索顶层和一层子目录（如 /Applications/Utilities/Safari.app）。
        """
        results: list[AppInfo] = []

        if not search_dir.is_dir():
            return results

        try:
            for item in search_dir.iterdir():
                if time.monotonic() > deadline:
                    logger.warning(f"[MacOSAdapter] 扫描 {search_dir} 超时")
                    break
                if len(results) >= limit:
                    break

                if item.suffix == ".app" and item.is_dir():
                    app_name = item.stem
                    if keyword_lower in app_name.lower():
                        app_path = str(item)
                        app_id = _app_id_from_path(app_path)

                        if app_id not in self._cache:
                            info: AppInfo = {
                                "app_id": app_id,
                                "name": app_name,
                                "path": app_path,
                                "source": "applications",
                            }
                            self._cache[app_id] = info
                            results.append(info)

                # 一层子目录（如 /Applications/Utilities/）
                elif item.is_dir() and item.suffix != ".app":
                    try:
                        for sub_item in item.iterdir():
                            if time.monotonic() > deadline:
                                break
                            if len(results) >= limit:
                                break

                            if sub_item.suffix == ".app" and sub_item.is_dir():
                                app_name = sub_item.stem
                                if keyword_lower in app_name.lower():
                                    app_path = str(sub_item)
                                    app_id = _app_id_from_path(app_path)

                                    if app_id not in self._cache:
                                        info = {
                                            "app_id": app_id,
                                            "name": app_name,
                                            "path": app_path,
                                            "source": "applications",
                                        }
                                        self._cache[app_id] = info
                                        results.append(info)
                    except PermissionError:
                        continue

        except PermissionError as e:
            logger.debug(f"[MacOSAdapter] 权限不足: {e}")

        return results

    def search_apps(self, keyword: str, limit: int = 20) -> list[AppInfo]:
        """按关键词搜索已安装的 .app 应用。"""
        if not keyword or not keyword.strip():
            return []

        logger.info(f"[MacOSAdapter] 搜索应用: keyword={keyword!r}, limit={limit}")

        self._cache.clear()
        keyword_lower = keyword.lower()
        deadline = time.monotonic() + _SEARCH_TIMEOUT
        results: list[AppInfo] = []

        # 搜索 /Applications
        results.extend(
            self._scan_applications_dir(Path("/Applications"), keyword_lower, limit, deadline)
        )

        # 搜索 ~/Applications
        if len(results) < limit and time.monotonic() < deadline:
            user_apps = Path.home() / "Applications"
            results.extend(
                self._scan_applications_dir(user_apps, keyword_lower, limit - len(results), deadline)
            )

        logger.info(f"[MacOSAdapter] 返回 {len(results)} 条结果")
        return results[:limit]

    def launch(self, app_id: str) -> bool:
        """启动指定应用（通过 open -a）。"""
        info = self._cache.get(app_id)
        if not info:
            logger.warning(f"[MacOSAdapter] 未找到 app_id={app_id}，请先执行 search_apps")
            return False

        app_name = info.get("name", "")
        app_path = info.get("path", "")

        try:
            # 使用 open -a 通过应用名启动（比路径更可靠）
            result = subprocess.run(
                ["open", "-a", app_name],
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                logger.info(f"[MacOSAdapter] 已启动: {app_name}")
                return True
            else:
                # 回退：用路径启动
                result = subprocess.run(
                    ["open", app_path],
                    capture_output=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    logger.info(f"[MacOSAdapter] 已启动（路径回退）: {app_path}")
                    return True
                logger.warning(f"[MacOSAdapter] open 返回非零: {result.stderr.decode(errors='replace')[:200]}")
                return False

        except subprocess.TimeoutExpired:
            logger.error(f"[MacOSAdapter] 启动超时: {app_name}")
            return False
        except Exception as e:
            logger.error(f"[MacOSAdapter] 启动失败: {e}", exc_info=True)
            return False

    def available(self) -> bool:
        """macOS 平台可用。"""
        import sys
        return sys.platform == "darwin"
