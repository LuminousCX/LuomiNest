"""跨平台系统与 Linux 发行版识别模块.

提供统一的平台信息采集：操作系统家族、Linux 发行版（区分 deb 系 / rpm 系 /
arch 系 / suse 系 / alpine 系）、包管理器、内核版本、架构等.
所有检测均有 try/except 保护，不因缺少某个文件或命令而崩溃.

发行版家族划分：
- deb: Debian / Ubuntu / Linux Mint / Pop!_OS / Kali / elementary OS 等
- rpm-enterprise: RHEL / CentOS / Rocky Linux / AlmaLinux / Oracle Linux / Amazon Linux
- rpm-fedora: Fedora（滚动演进，独立于企业版家族）
- arch: Arch Linux / Manjaro / EndeavourOS
- suse: openSUSE / SUSE Linux Enterprise
- alpine: Alpine Linux
"""

import platform
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from loguru import logger


@dataclass
class LinuxDistro:
    """Linux 发行版信息."""

    id: str  # 发行版 id，如 ubuntu / centos / rocky
    name: str  # 发行版显示名称
    version: str  # 版本号
    family: str  # deb / rpm-enterprise / rpm-fedora / arch / suse / alpine / unknown
    pretty_name: str = ""  # /etc/os-release 中的 PRETTY_NAME
    version_id: str = ""  # VERSION_ID 原始值


@dataclass
class SystemInfo:
    """聚合的系统信息（供设置页 /system/info 与日志展示）."""

    os_name: str  # Windows / Linux / macOS / FreeBSD / ...
    os_family: str  # windows / linux / macos / bsd / unknown
    distro: LinuxDistro | None = None  # 仅 Linux 有值
    kernel_version: str = ""
    machine: str = ""  # 硬件架构（x86_64 / aarch64 / arm64）
    python_version: str = ""
    package_manager: str = ""  # apt / dnf / yum / pacman / zypper / apk / brew / choco / winget / scoop
    is_frozen: bool = False  # 是否 PyInstaller 打包态

    def to_dict(self) -> dict:
        base = {
            "os_name": self.os_name,
            "os_family": self.os_family,
            "kernel_version": self.kernel_version,
            "machine": self.machine,
            "python_version": self.python_version,
            "package_manager": self.package_manager,
            "is_frozen": self.is_frozen,
        }
        if self.distro is not None:
            base["distro"] = {
                "id": self.distro.id,
                "name": self.distro.name,
                "version": self.distro.version,
                "family": self.distro.family,
                "pretty_name": self.distro.pretty_name,
                "version_id": self.distro.version_id,
            }
        return base


# (family, 文件路径, 是否需要内容匹配)
_LINUX_MARKER_FILES: list[tuple[str, Path, bool]] = [
    ("arch", Path("/etc/arch-release"), False),
    ("alpine", Path("/etc/alpine-release"), False),
    ("deb", Path("/etc/debian_version"), False),
    ("rpm-enterprise", Path("/etc/redhat-release"), False),
]

# 发行版 id -> family（os-release 的 ID / ID_LIKE 命中时）
_ID_FAMILY_MAP: dict[str, str] = {
    "debian": "deb", "ubuntu": "deb", "linuxmint": "deb", "pop": "deb",
    "kali": "deb", "elementary": "deb", "neon": "deb", "raspbian": "deb",
    "zorin": "deb", "deepin": "deb", "uos": "deb", "kylin": "deb",
    "fedora": "rpm-fedora",
    "rhel": "rpm-enterprise", "centos": "rpm-enterprise", "rocky": "rpm-enterprise",
    "almalinux": "rpm-enterprise", "ol": "rpm-enterprise", "amzn": "rpm-enterprise",
    "arch": "arch", "manjaro": "arch", "endeavouros": "arch",
    "opensuse": "suse", "opensuse-leap": "suse", "opensuse-tumbleweed": "suse",
    "sles": "suse",
    "alpine": "alpine",
}

# rpm 家族中属于企业级发行版（RHEL / CentOS / Rocky / Alma 等）的关键词
_RPM_ENTERPRISE_KEYWORDS = ("red hat", "centos", "rocky", "alma", "oracle", "amazon")

# 包管理器 -> 可执行文件（按优先级排列）
_PACKAGE_MANAGERS: list[tuple[str, str]] = [
    ("apt", "apt-get"), ("dnf", "dnf"), ("yum", "yum"),
    ("zypper", "zypper"), ("pacman", "pacman"), ("apk", "apk"),
    ("brew", "brew"), ("choco", "choco"), ("winget", "winget"), ("scoop", "scoop"),
]


def _parse_os_release() -> dict[str, str]:
    """解析 /etc/os-release（或 /usr/lib/os-release），返回键值对."""
    fields: dict[str, str] = {}
    for candidate in ("/etc/os-release", "/usr/lib/os-release"):
        try:
            content = Path(candidate).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in content.splitlines():
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip().strip('"').strip("'")
            if key:
                fields[key] = value
        break
    return fields


def _parse_redhat_release() -> dict[str, str]:
    """解析 /etc/redhat-release（如 'CentOS Linux release 7.9.2009 (Core)'）."""
    try:
        content = Path("/etc/redhat-release").read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return {}
    lower = content.lower()
    if "fedora" in lower:
        return {"id": "fedora", "name": "Fedora", "family": "rpm-fedora", "pretty_name": content}
    if "centos" in lower:
        return {"id": "centos", "name": "CentOS", "family": "rpm-enterprise", "pretty_name": content}
    if "rocky" in lower:
        return {"id": "rocky", "name": "Rocky Linux", "family": "rpm-enterprise", "pretty_name": content}
    if "alma" in lower:
        return {"id": "almalinux", "name": "AlmaLinux", "family": "rpm-enterprise", "pretty_name": content}
    if "oracle" in lower:
        return {"id": "ol", "name": "Oracle Linux", "family": "rpm-enterprise", "pretty_name": content}
    if "amazon" in lower:
        return {"id": "amzn", "name": "Amazon Linux", "family": "rpm-enterprise", "pretty_name": content}
    if "red hat" in lower:
        return {"id": "rhel", "name": "Red Hat Enterprise Linux", "family": "rpm-enterprise", "pretty_name": content}
    return {"id": "unknown", "name": content, "family": "rpm-enterprise", "pretty_name": content}


def _classify_family(distro_id: str, id_like: str) -> str:
    """根据 ID / ID_LIKE 判断发行版家族."""
    candidates = [distro_id] + [part.strip() for part in id_like.split() if part.strip()]
    for cid in candidates:
        family = _ID_FAMILY_MAP.get(cid.lower())
        if family:
            return family
    return "unknown"


def detect_linux_distro() -> LinuxDistro | None:
    """检测当前 Linux 发行版信息（仅 Linux 有效）."""
    if platform.system() != "Linux":
        return None

    os_release = _parse_os_release()
    distro_id = os_release.get("ID", "")
    id_like = os_release.get("ID_LIKE", "")
    family = _classify_family(distro_id, id_like)

    # 优先 os-release 的完整信息
    if distro_id:
        return LinuxDistro(
            id=distro_id,
            name=os_release.get("NAME", distro_id),
            version=os_release.get("VERSION_ID", os_release.get("VERSION", "")),
            family=family,
            pretty_name=os_release.get("PRETTY_NAME", ""),
            version_id=os_release.get("VERSION_ID", ""),
        )

    # os-release 缺失时回退到 /etc/redhat-release 等标记文件
    redhat = _parse_redhat_release()
    if redhat:
        return LinuxDistro(
            id=redhat["id"],
            name=redhat["name"],
            version=_extract_release_version(redhat.get("pretty_name", "")),
            family=redhat["family"],
            pretty_name=redhat.get("pretty_name", ""),
            version_id="",
        )

    for family, marker, _needs_content in _LINUX_MARKER_FILES:
        if marker.exists():
            version = marker.read_text(encoding="utf-8", errors="replace").strip()
            return LinuxDistro(
                id=family, name=family.capitalize(), version=version,
                family=family, pretty_name=f"{family} {version}", version_id=version,
            )

    return LinuxDistro(
        id="unknown", name=platform.system() + " (未知发行版)",
        version="", family="unknown", pretty_name="", version_id="",
    )


def _extract_release_version(pretty_name: str) -> str:
    """从发行版显示名称中提取版本号（如 'CentOS Linux release 7.9.2009 (Core)' -> 7.9.2009）."""
    import re

    match = re.search(r"(\d+(?:\.\d+)*)", pretty_name)
    return match.group(1) if match else ""


def detect_package_manager(distro: LinuxDistro | None) -> str:
    """检测系统包管理器.

    优先根据发行版家族推断，再按 PATH 中的可执行文件确认.
    """
    if distro is not None and distro.family:
        if distro.family == "deb":
            return "apt" if shutil.which("apt-get") or shutil.which("apt") else ""
        if distro.family in ("rpm-fedora", "rpm-enterprise"):
            if shutil.which("dnf"):
                return "dnf"
            if shutil.which("yum"):
                return "yum"
        if distro.family == "arch":
            return "pacman" if shutil.which("pacman") else ""
        if distro.family == "suse":
            return "zypper" if shutil.which("zypper") else ""
        if distro.family == "alpine":
            return "apk" if shutil.which("apk") else ""

    # 家族未知或非 Linux：按可执行文件兜底探测
    for name, executable in _PACKAGE_MANAGERS:
        if shutil.which(executable):
            return name
    return ""


def _detect_kernel_version() -> str:
    """检测内核版本（Windows 返回 OS 版本，Linux/macOS 返回 uname -r）."""
    try:
        if platform.system() == "Windows":
            return platform.version() or platform.release()
        return platform.release()
    except Exception:
        return ""


def _detect_machine() -> str:
    """检测硬件架构."""
    try:
        return platform.machine() or platform.processor() or ""
    except Exception:
        return ""


def _detect_python_version() -> str:
    """返回 Python 运行版本."""
    try:
        return platform.python_version()
    except Exception:
        return sys.version.split()[0] if sys.version else ""


def get_system_info() -> SystemInfo:
    """采集当前系统的完整信息（带缓存，首次调用后复用）."""
    global _system_info
    if _system_info is not None:
        return _system_info

    system = platform.system()
    if system == "Windows":
        os_family = "windows"
    elif system == "Linux":
        os_family = "linux"
    elif system == "Darwin":
        os_family = "macos"
    elif system.startswith(("FreeBSD", "OpenBSD", "NetBSD")):
        os_family = "bsd"
    else:
        os_family = "unknown"

    distro = detect_linux_distro() if system == "Linux" else None

    _system_info = SystemInfo(
        os_name=system,
        os_family=os_family,
        distro=distro,
        kernel_version=_detect_kernel_version(),
        machine=_detect_machine(),
        python_version=_detect_python_version(),
        package_manager=detect_package_manager(distro),
        is_frozen=bool(getattr(sys, "frozen", False)),
    )
    return _system_info


_system_info: SystemInfo | None = None


def log_system_info() -> None:
    """输出系统信息到日志（启动时调用）."""
    info = get_system_info()
    try:
        if info.distro is not None and info.distro.pretty_name:
            os_desc = f"{info.os_name} ({info.distro.pretty_name})"
        else:
            os_desc = info.os_name
        logger.info(
            f"[LuomiNest] 系统信息: OS={os_desc}, 家族={info.os_family}, "
            f"发行版={info.distro.id if info.distro else '-'} (family={info.distro.family if info.distro else '-'}), "
            f"内核={info.kernel_version}, 架构={info.machine}, "
            f"Python={info.python_version}, 包管理器={info.package_manager or '无'}"
        )
    except Exception as e:
        logger.debug(f"[LuomiNest] log_system_info failed: {e}")
