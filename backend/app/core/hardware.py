"""全局硬件检测模块.

检测 CPU 核心数、系统内存总量、GPU 类型，提供统一的 HardwareProfile 数据类.
所有检测均有 try/except 保护，不因缺少某个库而崩溃.
内存检测使用 OS 原生命令（PowerShell Get-CimInstance、/proc/meminfo、sysctl），不依赖 psutil.
"""

import os
import platform
import subprocess
from dataclasses import dataclass
from enum import Enum

from loguru import logger


class GpuType(str, Enum):
    CUDA = "cuda"
    MPS = "mps"
    CPU_ONLY = "cpu_only"


@dataclass
class HardwareProfile:
    cpu_count: int
    total_memory_gb: float
    gpu_type: GpuType
    is_low_end: bool


_hardware_profile: HardwareProfile | None = None


def _detect_cpu_count() -> int:
    """检测 CPU 核心数."""
    try:
        count = os.cpu_count()
        return count if count and count > 0 else 1
    except Exception:
        return 1


def _detect_total_memory_gb() -> float:
    """检测系统内存总量（GB），使用 OS 原生命令，不依赖 psutil."""
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


def _detect_gpu_type() -> GpuType:
    """检测 GPU 类型."""
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

    return GpuType.CPU_ONLY


def _detect_hardware() -> HardwareProfile:
    """执行完整硬件检测."""
    cpu_count = _detect_cpu_count()
    total_memory_gb = _detect_total_memory_gb()
    gpu_type = _detect_gpu_type()

    # 低端设备判定：内存 < 8GB 或 CPU < 4 核
    is_low_end = total_memory_gb < 8.0 or cpu_count < 4

    return HardwareProfile(
        cpu_count=cpu_count,
        total_memory_gb=total_memory_gb,
        gpu_type=gpu_type,
        is_low_end=is_low_end,
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
