"""Windows 应用启动适配器。

搜索来源（按优先级）：
1. 注册表 App Paths（HKLM + HKCU，更可靠）
2. 开始菜单 .lnk 快捷方式（用户 + 公共）

启动方式：os.startfile(path)

模糊匹配策略：应用名包含关键词（case-insensitive）。

注意：
- .lnk 解析不依赖 win32com，采用纯 Python 读取 Shell Link 结构的 LocalBasePath
- 如果 .lnk 解析失败，静默跳过（不影响注册表搜索结果）
- 搜索有超时保护（目录遍历限时）
"""
from __future__ import annotations

import hashlib
import os
import struct
import time
from pathlib import Path

from loguru import logger

from app.core.ports.app_launcher import AppInfo


# 搜索超时保护（秒）
_SEARCH_TIMEOUT = 5.0


def _app_id_from_path(path: str) -> str:
    """根据路径生成稳定的 app_id（MD5 前 12 位）。"""
    return hashlib.md5(path.lower().encode("utf-8")).hexdigest()[:12]


def _parse_lnk_target(lnk_path: Path) -> str | None:
    """纯 Python 解析 .lnk 文件获取目标路径（LocalBasePath）。

    参考 MS-SHLLINK 规范：
    - offset 0x00: HeaderSize (4 bytes, 必须为 0x4C)
    - offset 0x14: LinkFlags (4 bytes)
    - 若 HasLinkInfo 标志位 (bit 0) 为 1，则 LinkInfo 紧跟 Header
    - LinkInfo 结构中 offset 0x10 处为 LocalBasePathOffset

    这不是一个完整的解析器，但对大多数常规 .lnk 文件有效。
    解析失败时返回 None。
    """
    try:
        data = lnk_path.read_bytes()
        if len(data) < 0x50:
            return None

        # Header size 必须为 0x4C
        header_size = struct.unpack_from("<I", data, 0x00)[0]
        if header_size != 0x4C:
            return None

        link_flags = struct.unpack_from("<I", data, 0x14)[0]

        # HasLinkInfo (bit 0)
        if not (link_flags & 0x01):
            return None

        # LinkInfo 从 offset 0x4C 开始
        link_info_offset = 0x4C
        if len(data) < link_info_offset + 0x1C:
            return None

        link_info_size = struct.unpack_from("<I", data, link_info_offset)[0]
        link_info_header_size = struct.unpack_from("<I", data, link_info_offset + 0x04)[0]
        link_info_flags = struct.unpack_from("<I", data, link_info_offset + 0x08)[0]

        # VolumeIDAndLocalBasePath (bit 0)
        if not (link_info_flags & 0x01):
            return None

        local_base_path_offset = struct.unpack_from("<I", data, link_info_offset + 0x10)[0]
        abs_path_start = link_info_offset + local_base_path_offset

        if abs_path_start >= len(data):
            return None

        # 读取 null-terminated ANSI 字符串
        end = data.index(b"\x00", abs_path_start) if b"\x00" in data[abs_path_start:] else len(data)
        raw_path = data[abs_path_start:end]

        # 尝试解码（优先 UTF-8，退化 GBK）
        try:
            return raw_path.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return raw_path.decode("gbk")
            except UnicodeDecodeError:
                return None

    except Exception:
        return None


class WindowsAdapter:
    """Windows 应用启动适配器。

    搜索来源：
    1. 注册表 HKLM/HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths
    2. 开始菜单 .lnk 快捷方式

    启动方式：os.startfile(path)

    Usage:
        adapter = WindowsAdapter()
        if adapter.available():
            apps = adapter.search_apps("chrome")
            adapter.launch(apps[0]["app_id"])
    """

    def __init__(self) -> None:
        # app_id -> AppInfo 缓存（搜索时构建，启动时查找）
        self._cache: dict[str, AppInfo] = {}

    # ------------------------------------------------------------------
    # 注册表搜索
    # ------------------------------------------------------------------

    def _search_registry(self, keyword: str, limit: int) -> list[AppInfo]:
        """从注册表 App Paths 搜索应用。

        搜索 HKLM 和 HKCU 的 SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths 子键。
        每个子键名通常是可执行文件名（如 chrome.exe），默认值为完整路径。
        """
        try:
            import winreg
        except ImportError:
            logger.warning("[WindowsAdapter] winreg 不可用（非 Windows 环境）")
            return []

        keyword_lower = keyword.lower()
        results: list[AppInfo] = []

        search_roots = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        ]

        for hive, subkey in search_roots:
            try:
                key = winreg.OpenKey(hive, subkey)
            except FileNotFoundError:
                continue
            except OSError as e:
                logger.debug(f"[WindowsAdapter] 打开注册表失败: {e}")
                continue

            try:
                count = winreg.QueryInfoKey(key)[0]
                for i in range(count):
                    if len(results) >= limit:
                        break

                    try:
                        app_name = winreg.EnumKey(key, i)
                    except OSError:
                        continue

                    if keyword_lower not in app_name.lower():
                        continue

                    # 读取默认值（可执行文件路径）
                    try:
                        app_key = winreg.OpenKey(key, app_name)
                        exe_path, _ = winreg.QueryValueEx(app_key, "")
                        winreg.CloseKey(app_key)
                    except (OSError, FileNotFoundError):
                        continue

                    if not exe_path or not Path(exe_path).exists():
                        continue

                    display_name = Path(app_name).stem
                    app_id = _app_id_from_path(exe_path)

                    info: AppInfo = {
                        "app_id": app_id,
                        "name": display_name,
                        "path": exe_path,
                        "source": "registry",
                    }
                    self._cache[app_id] = info
                    results.append(info)

                winreg.CloseKey(key)
            except OSError as e:
                logger.debug(f"[WindowsAdapter] 注册表遍历异常: {e}")
                try:
                    winreg.CloseKey(key)
                except Exception:
                    # 句柄可能已失效，属预期清理情况
                    logger.debug("[WindowsAdapter] 注册表句柄关闭异常（忽略）", exc_info=True)

        return results

    # ------------------------------------------------------------------
    # 开始菜单 .lnk 搜索
    # ------------------------------------------------------------------

    def _search_start_menu(self, keyword: str, limit: int) -> list[AppInfo]:
        """从开始菜单 .lnk 快捷方式搜索应用。"""
        keyword_lower = keyword.lower()
        results: list[AppInfo] = []

        start_menu_dirs: list[Path] = []

        # 用户开始菜单
        appdata = os.environ.get("APPDATA")
        if appdata:
            user_menu = Path(appdata) / "Microsoft" / "Windows" / "Start Menu"
            if user_menu.is_dir():
                start_menu_dirs.append(user_menu)

        # 公共开始菜单
        programdata = os.environ.get("ProgramData")
        if programdata:
            public_menu = Path(programdata) / "Microsoft" / "Windows" / "Start Menu"
            if public_menu.is_dir():
                start_menu_dirs.append(public_menu)

        if not start_menu_dirs:
            logger.debug("[WindowsAdapter] 未找到开始菜单目录")
            return results

        deadline = time.monotonic() + _SEARCH_TIMEOUT

        for menu_dir in start_menu_dirs:
            if time.monotonic() > deadline:
                logger.warning("[WindowsAdapter] 开始菜单搜索超时")
                break

            try:
                for lnk_path in menu_dir.rglob("*.lnk"):
                    if time.monotonic() > deadline:
                        break
                    if len(results) >= limit:
                        break

                    lnk_name = lnk_path.stem.lower()
                    if keyword_lower not in lnk_name:
                        continue

                    # 解析 .lnk 获取目标路径
                    target = _parse_lnk_target(lnk_path)
                    if not target or not Path(target).exists():
                        continue

                    # 跳过卸载程序
                    target_lower = target.lower()
                    if "uninstall" in target_lower or "uninst" in target_lower:
                        continue

                    display_name = lnk_path.stem
                    app_id = _app_id_from_path(target)

                    # 去重（注册表可能已添加）
                    if app_id in self._cache:
                        continue

                    info: AppInfo = {
                        "app_id": app_id,
                        "name": display_name,
                        "path": target,
                        "source": "start_menu",
                    }
                    self._cache[app_id] = info
                    results.append(info)

            except OSError as e:
                logger.debug(f"[WindowsAdapter] 开始菜单遍历异常: {e}")

        return results

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def search_apps(self, keyword: str, limit: int = 20) -> list[AppInfo]:
        """按关键词搜索已安装应用。

        搜索顺序：注册表（快且可靠）-> 开始菜单 .lnk（补充）。
        """
        if not keyword or not keyword.strip():
            return []

        logger.info(f"[WindowsAdapter] 搜索应用: keyword={keyword!r}, limit={limit}")

        self._cache.clear()
        results: list[AppInfo] = []

        # 1. 注册表搜索
        registry_results = self._search_registry(keyword, limit)
        results.extend(registry_results)

        # 2. 开始菜单搜索（补充）
        if len(results) < limit:
            menu_results = self._search_start_menu(keyword, limit - len(results))
            results.extend(menu_results)

        logger.info(f"[WindowsAdapter] 返回 {len(results)} 条结果")
        return results[:limit]

    def launch(self, app_id: str) -> bool:
        """启动指定应用（通过 os.startfile）。"""
        info = self._cache.get(app_id)
        if not info:
            logger.warning(f"[WindowsAdapter] 未找到 app_id={app_id}，请先执行 search_apps")
            return False

        path = info.get("path", "")
        if not path or not Path(path).exists():
            logger.error(f"[WindowsAdapter] 应用路径不存在: {path}")
            return False

        try:
            os.startfile(path)
            logger.info(f"[WindowsAdapter] 已启动: {info.get('name', '')} ({path})")
            return True
        except OSError as e:
            logger.error(f"[WindowsAdapter] 启动失败: {path} - {e}")
            return False

    def available(self) -> bool:
        """Windows 平台始终可用。"""
        return os.name == "nt"
