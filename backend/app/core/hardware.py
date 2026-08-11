"""全局硬件检测模块.

检测 CPU 核心数、系统内存总量、GPU 类型，提供统一的 HardwareProfile 数据类.
所有检测均有 try/except 保护，不因缺少某个库而崩溃.
内存检测优先使用 psutil（跨平台统一），psutil 缺失时回退 OS 原生命令
（PowerShell Get-CimInstance、/proc/meminfo、sysctl）.
"""

import os
import platform
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from loguru import logger


class GpuType(str, Enum):
    CUDA = "cuda"
    MPS = "mps"
    CPU_ONLY = "cpu_only"


@dataclass
class GpuDevice:
    """单个 GPU 设备信息（平台原生检测，不依赖 PyTorch）."""

    name: str
    vendor: str  # nvidia / amd / intel / apple / unknown
    is_virtual: bool = False


@dataclass
class HardwareProfile:
    cpu_count: int
    total_memory_gb: float
    gpu_type: GpuType
    is_low_end: bool
    gpu_count: int = 0
    gpu_names: list[str] = None  # type: ignore[assignment]


_hardware_profile: HardwareProfile | None = None


def _detect_cpu_count() -> int:
    """检测 CPU 核心数."""
    try:
        count = os.cpu_count()
        return count if count and count > 0 else 1
    except Exception:
        return 1


def _detect_total_memory_gb() -> float:
    """检测系统内存总量（GB）.

    优先使用 psutil（跨平台统一，Windows/Linux/macOS 均可靠）；
    psutil 不可用时回退 OS 原生命令（PowerShell、/proc/meminfo、sysctl）.
    """
    # 方法 1：psutil（跨平台）
    try:
        import psutil

        total_bytes = psutil.virtual_memory().total
        if total_bytes > 0:
            return round(total_bytes / (1024 ** 3), 2)
    except ImportError:
        logger.debug("[Hardware] psutil not installed, falling back to native commands")
    except Exception as e:
        logger.debug(f"[Hardware] psutil memory detection failed: {e}")

    # 方法 2：平台原生命令回退
    system = platform.system()

    if system == "Windows":
        return _detect_memory_windows()
    elif system == "Linux":
        return _detect_memory_linux()
    elif system == "Darwin":
        return _detect_memory_macos()
    else:
        # 其他系统：尝试通用方法
        return _detect_memory_fallback()


def _detect_memory_windows() -> float:
    """Windows 内存检测：优先 PowerShell Get-CimInstance，回退 wmic（兼容旧系统）."""
    # 方法 1：PowerShell Get-CimInstance Win32_ComputerSystem（Windows 10/11 通用）
    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory",
            ],
            capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            if output and output.isdigit():
                bytes_val = int(output)
                return round(bytes_val / (1024 ** 3), 2)
    except Exception as e:
        logger.debug(f"[Hardware] PowerShell memory detection failed: {e}")

    # 方法 2：PowerShell Get-CimInstance Win32_OperatingSystem（备选方案）
    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                "(Get-CimInstance Win32_OperatingSystem).TotalVisibleMemorySize",
            ],
            capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            if output and output.isdigit():
                kb = int(output)
                return round(kb / (1024 ** 2), 2)
    except Exception as e:
        logger.debug(f"[Hardware] PowerShell OS memory detection failed: {e}")

    # 方法 3：wmic（兼容 Windows 7/8 及旧版 Server）
    try:
        result = subprocess.run(
            ["wmic", "os", "get", "TotalVisibleMemorySize", "/Value"],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                line = line.strip()
                if line.startswith("TotalVisibleMemorySize="):
                    kb = int(line.split("=")[1])
                    return round(kb / (1024 ** 2), 2)
    except Exception as e:
        logger.debug(f"[Hardware] wmic memory detection failed: {e}")

    logger.warning("[Hardware] Windows memory detection failed, defaulting to 8.0 GB")
    return 8.0


def _detect_memory_linux() -> float:
    """Linux 内存检测：读取 /proc/meminfo."""
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return round(kb / (1024 ** 2), 2)
    except Exception as e:
        logger.debug(f"[Hardware] /proc/meminfo detection failed: {e}")

    # 回退：free 命令
    try:
        result = subprocess.run(
            ["free", "-b"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.startswith("Mem:"):
                    parts = line.split()
                    if len(parts) >= 2:
                        bytes_val = int(parts[1])
                        return round(bytes_val / (1024 ** 3), 2)
    except Exception as e:
        logger.debug(f"[Hardware] free command detection failed: {e}")

    logger.warning("[Hardware] Linux memory detection failed, defaulting to 8.0 GB")
    return 8.0


def _detect_memory_macos() -> float:
    """macOS 内存检测：sysctl hw.memsize."""
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            bytes_val = int(result.stdout.strip())
            return round(bytes_val / (1024 ** 3), 2)
    except Exception as e:
        logger.debug(f"[Hardware] sysctl memory detection failed: {e}")

    logger.warning("[Hardware] macOS memory detection failed, defaulting to 8.0 GB")
    return 8.0


def _detect_memory_fallback() -> float:
    """通用回退内存检测."""
    # 尝试 /proc/meminfo（某些 Unix 也有）
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return round(kb / (1024 ** 2), 2)
    except Exception:
        pass

    logger.warning("[Hardware] Memory detection failed on unknown OS, defaulting to 8.0 GB")
    return 8.0


def _infer_vendor(name: str) -> str:
    """根据 GPU 名称推断厂商."""
    lower = name.lower()
    if any(k in lower for k in ("nvidia", "geforce", "rtx", "gtx", "quadro", "tesla")):
        return "nvidia"
    if any(k in lower for k in ("amd", "radeon", "vega", "firepro", "instinct")):
        return "amd"
    if any(k in lower for k in ("intel", "arc", "iris", "uhd graphics", "hd graphics")):
        return "intel"
    if "apple" in lower or "mps" in lower:
        return "apple"
    return "unknown"


def _is_virtual_gpu(name: str, pnp_id: str = "") -> bool:
    """过滤虚拟显示适配器（远程桌面/串流工具等），避免误报为真实 GPU."""
    lower = name.lower()
    virtual_markers = (
        "virtual", "remote", "basic display", "microsoft basic",
        "todesk", "sunlogin", "anydesk", "parsec", "displaylink",
        "virtual display", "rdp",
    )
    if any(m in lower for m in virtual_markers):
        return True
    return "root\\" in pnp_id.lower()


def _detect_gpus_windows() -> list[GpuDevice]:
    """Windows GPU 检测：PowerShell Get-CimInstance Win32_VideoController."""
    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                "Get-CimInstance Win32_VideoController | ForEach-Object { \"$($_.Name)|$($_.PNPDeviceID)\" }",
            ],
            capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode != 0:
            return []
        gpus: list[GpuDevice] = []
        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if not line or "|" not in line:
                continue
            name, pnp_id = line.split("|", 1)
            name = name.strip()
            pnp_id = pnp_id.strip()
            if not name or _is_virtual_gpu(name, pnp_id):
                continue
            gpus.append(GpuDevice(name=name, vendor=_infer_vendor(name), is_virtual=False))
        return gpus
    except Exception as e:
        logger.debug(f"[Hardware] Windows GPU detection failed: {e}")
        return []


def _detect_gpus_linux() -> list[GpuDevice]:
    """Linux GPU 检测.

    主路径：lspci 匹配 VGA / 3D / Display controller（需要 pciutils）.
    回退路径：遍历 /sys/class/drm/card*/device 读取 vendor/device 名称，
    并在 /sys/bus/pci/drivers/nvidia/ 存在时识别 NVIDIA 设备.
    """
    gpus = _detect_gpus_linux_lspci()
    if gpus:
        return gpus
    return _detect_gpus_linux_drm()


def _detect_gpus_linux_lspci() -> list[GpuDevice]:
    """Linux GPU 检测主路径：lspci."""
    try:
        result = subprocess.run(
            ["lspci", "-nn"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return []
        gpus: list[GpuDevice] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not any(tag in line.lower() for tag in ("vga compatible", "3d controller", "display controller")):
                continue
            # 提取厂商与型号（去掉方括号内的 PCI ID 与驱动编号）
            if ":" in line:
                line = line.split(":", 1)[1].strip()
            if "[" in line:
                line = line.split("[", 1)[0].strip()
            # 去掉尾部的 " (rev xx)"
            if "(" in line:
                line = line.split("(", 1)[0].strip()
            if not line:
                continue
            gpus.append(GpuDevice(name=line, vendor=_infer_vendor(line), is_virtual=False))
        return gpus
    except Exception as e:
        logger.debug(f"[Hardware] Linux lspci GPU detection failed: {e}")
        return []


def _detect_gpus_linux_drm() -> list[GpuDevice]:
    """Linux GPU 检测回退路径：/sys/class/drm（无 lspci 的容器/精简系统）."""
    try:
        drm_dir = Path("/sys/class/drm")
        if not drm_dir.is_dir():
            return []
        seen: set[str] = set()
        gpus: list[GpuDevice] = []
        for entry in sorted(drm_dir.iterdir()):
            if not entry.name.startswith("card") or entry.name.endswith("-"):
                continue
            device_dir = entry / "device"
            try:
                vendor_id = (device_dir / "vendor").read_text().strip()
                # 读取 DRM 设备名（如 i915 / amdgpu / nvidia-drm / vc4）
                name = (device_dir / "uevent").read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if not vendor_id or vendor_id in seen:
                continue
            seen.add(vendor_id)
            label = _drm_vendor_label(vendor_id, name)
            if label:
                gpus.append(GpuDevice(name=label, vendor=_infer_vendor(label), is_virtual=False))
        return gpus
    except Exception as e:
        logger.debug(f"[Hardware] Linux DRM GPU detection failed: {e}")
        return []


def _drm_vendor_label(vendor_id: str, uevent: str = "") -> str:
    """根据 PCI vendor id 与 uevent 内容生成 GPU 名称."""
    vendor_map = {
        "0x10de": "NVIDIA GPU",
        "0x1002": "AMD GPU (Radeon)",
        "0x8086": "Intel GPU (iGPU)",
        "0x1a03": "ASPEED GPU (BMC 虚拟)",
        "0x1414": "Microsoft Basic Display Adapter (虚拟)",
    }
    # 尝试从 uevent 的 DRIVER 字段细化名称
    driver = ""
    for line in uevent.splitlines():
        if line.startswith("DRIVER="):
            driver = line.split("=", 1)[1].strip()
            break
    vendor_lower = vendor_id.strip().lower()
    label = vendor_map.get(vendor_lower)
    if label and driver and driver.lower() not in ("nvidia", "amdgpu", "i915"):
        label = f"{label} ({driver})"
    return label or ""


def _detect_gpus_macos() -> list[GpuDevice]:
    """macOS GPU 检测：system_profiler SPDisplaysDataType."""
    try:
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType"],
            capture_output=True, text=True, timeout=20,
        )
        if result.returncode != 0:
            return []
        gpus: list[GpuDevice] = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if "Chipset Model:" in line:
                name = line.split("Chipset Model:", 1)[1].strip()
                if name:
                    gpus.append(GpuDevice(name=name, vendor=_infer_vendor(name), is_virtual=False))
        return gpus
    except Exception as e:
        logger.debug(f"[Hardware] macOS GPU detection failed: {e}")
        return []


def _detect_gpus_native() -> list[GpuDevice]:
    """平台原生 GPU 检测（不依赖 PyTorch），返回真实（非虚拟）GPU 列表."""
    system = platform.system()
    try:
        if system == "Windows":
            return _detect_gpus_windows()
        if system == "Linux":
            return _detect_gpus_linux()
        if system == "Darwin":
            return _detect_gpus_macos()
    except Exception as e:
        logger.debug(f"[Hardware] Native GPU detection failed on {system}: {e}")
    return []


def detect_gpus() -> list[GpuDevice]:
    """检测 GPU 列表：优先 PyTorch（CUDA/MPS），回退平台原生检测."""
    gpus: list[GpuDevice] = []
    try:
        import torch

        if torch.cuda.is_available():
            gpus = [
                GpuDevice(name=torch.cuda.get_device_name(i), vendor="nvidia", is_virtual=False)
                for i in range(torch.cuda.device_count())
            ]
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            gpus = [GpuDevice(name="Apple Silicon (MPS)", vendor="apple", is_virtual=False)]
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"[Hardware] torch GPU detection failed: {e}")

    if gpus:
        return gpus

    # torch 不可用或未检测到加速设备，回退平台原生检测
    native = _detect_gpus_native()
    if native:
        return native

    return []


def _detect_gpu_type() -> GpuType:
    """检测 GPU 类型.

    优先使用 PyTorch（CUDA / MPS）；PyTorch 未安装或为 CPU 版时，
    回退到平台原生硬件检测（PowerShell / lspci / system_profiler），
    只要存在真实 GPU 即视为可用硬件。
    """
    try:
        import torch

        # CUDA (NVIDIA / AMD via ROCm)
        if torch.cuda.is_available():
            logger.info(f"[Hardware] CUDA detected: {torch.cuda.get_device_name(0)}")
            return GpuType.CUDA

        # MPS (Apple Silicon)
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            logger.info("[Hardware] MPS (Apple Silicon) detected")
            return GpuType.MPS
    except ImportError:
        logger.debug("[Hardware] PyTorch not installed, GPU detection skipped")
    except Exception as e:
        logger.debug(f"[Hardware] GPU detection error: {e}")

    native_gpus = _detect_gpus_native()
    if native_gpus:
        logger.info(f"[Hardware] Native GPU detected: {', '.join(g.name for g in native_gpus)}")
        return GpuType.CUDA

    return GpuType.CPU_ONLY


def _detect_hardware() -> HardwareProfile:
    """执行完整硬件检测."""
    cpu_count = _detect_cpu_count()
    total_memory_gb = _detect_total_memory_gb()
    gpu_type = _detect_gpu_type()
    gpu_devices = detect_gpus()

    # 低端设备判定：内存 < 8GB 或 CPU < 4 核
    is_low_end = total_memory_gb < 8.0 or cpu_count < 4

    return HardwareProfile(
        cpu_count=cpu_count,
        total_memory_gb=total_memory_gb,
        gpu_type=gpu_type,
        is_low_end=is_low_end,
        gpu_count=len(gpu_devices),
        gpu_names=[g.name for g in gpu_devices],
    )


def get_hardware_profile() -> HardwareProfile:
    """获取硬件概况（单例，首次调用时检测）."""
    global _hardware_profile
    if _hardware_profile is None:
        _hardware_profile = _detect_hardware()
    return _hardware_profile


def is_low_end_device() -> bool:
    """判断当前设备是否为低端设备（内存 < 8GB 或 CPU < 4 核）."""
    return get_hardware_profile().is_low_end


def detect_compute_device() -> dict:
    """Detect compute device availability for TTS/STT.

    Prefers PyTorch (CUDA/MPS, gives CUDA version); when PyTorch is missing
    or is a CPU-only build, falls back to OS-native GPU detection
    (PowerShell / lspci / /sys/class/drm / system_profiler) so real hardware
    is still reported.
    Note: current local TTS engines (pyttsx3, sherpa-onnx CPU) run on CPU only;
    this info informs the frontend and future GPU-based engines.
    """
    device = {
        "type": "cpu",
        "name": platform.processor() or "Unknown CPU",
        "vendor": None,
        "gpu_count": 0,
        "cuda_available": False,
        "cuda_version": None,
        "torch_available": False,
        "note": "未检测到可用 GPU，本地 TTS 使用 CPU 推理",
    }

    # 1) PyTorch 检测（可拿到 CUDA 版本）
    try:
        import torch

        device["torch_available"] = True
        if torch.cuda.is_available():
            device.update(
                {
                    "type": "gpu",
                    "name": torch.cuda.get_device_name(0),
                    "vendor": "nvidia",
                    "gpu_count": torch.cuda.device_count(),
                    "cuda_available": True,
                    "cuda_version": torch.version.cuda or "unknown",
                    "note": "PyTorch CUDA 检测",
                }
            )
            return device
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device.update(
                {
                    "type": "gpu",
                    "name": "Apple Silicon (MPS)",
                    "vendor": "apple",
                    "gpu_count": 1,
                    "note": "PyTorch MPS 检测",
                }
            )
            return device
    except ImportError:
        device["torch_available"] = False
    except Exception as dev_err:
        logger.debug(f"[Hardware] Compute device detection (torch) failed: {dev_err}")

    # 2) 回退：平台原生硬件检测（不依赖 PyTorch）
    try:
        gpus = detect_gpus()
        if gpus:
            primary = gpus[0]
            device.update(
                {
                    "type": "gpu",
                    "name": primary.name,
                    "vendor": primary.vendor,
                    "gpu_count": len(gpus),
                    "note": (
                        "系统硬件检测（未安装 PyTorch）。"
                        "本地 TTS 当前仍为 CPU 推理，GPU 可用于未来 GPU 加速引擎"
                        if not device["torch_available"]
                        else "系统硬件检测"
                    ),
                }
            )
    except Exception as native_err:
        logger.debug(f"[Hardware] Compute device detection (native) failed: {native_err}")

    return device
