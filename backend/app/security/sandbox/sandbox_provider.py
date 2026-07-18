"""SandboxProvider — 线程安全的沙盒生命周期管理器。

使用 LRU 缓存（maxsize=256）管理每个 session 的沙盒实例。
首次 acquire 时自动通过 LocalSandboxProvider 创建 LocalSandbox。
"""

import logging
import threading
from collections import OrderedDict
from typing import ClassVar

from app.security.sandbox.local_sandbox import LocalSandbox
from app.security.sandbox.local_sandbox_provider import LocalSandboxProvider
from app.security.sandbox.sandbox import Sandbox

logger = logging.getLogger(__name__)

# LRU 缓存默认上限
_DEFAULT_MAX_CACHED_SANDBOXES = 256


class SandboxProvider:
    """线程安全的沙盒提供者（单例模式）。

    管理每个 session 的沙盒实例，使用 LRU 缓存控制内存占用。
    首次 acquire 某 session 时自动创建 LocalSandbox。

    用法::

        provider = SandboxProvider.get_instance()
        sandbox = provider.acquire("session-abc")
        # ... 使用 sandbox ...
        provider.release("session-abc")  # 不立即销毁，由 LRU 管理
    """

    _instance: ClassVar["SandboxProvider | None"] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, max_cached: int = _DEFAULT_MAX_CACHED_SANDBOXES) -> None:
        self._local_provider = LocalSandboxProvider()
        self._sandboxes: OrderedDict[str, LocalSandbox] = OrderedDict()
        self._max_cached = max_cached
        self._internal_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "SandboxProvider":
        """获取 SandboxProvider 单例（线程安全）。"""
        if cls._instance is not None:
            return cls._instance
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
                logger.info("SandboxProvider 单例已创建")
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例（用于测试或配置变更）。"""
        with cls._lock:
            if cls._instance is not None:
                cls._instance._shutdown()
                cls._instance = None
                logger.info("SandboxProvider 单例已重置")

    def acquire(self, session_id: str) -> Sandbox:
        """获取指定 session 的沙盒实例。

        如果缓存中已存在，直接返回（并更新 LRU 顺序）。
        如果不存在，通过 LocalSandboxProvider 创建新实例。

        Args:
            session_id: 会话标识符。

        Returns:
            Sandbox 实例（实际类型为 LocalSandbox）。
        """
        with self._internal_lock:
            cached = self._sandboxes.get(session_id)
            if cached is not None:
                # 更新 LRU 顺序
                self._sandboxes.move_to_end(session_id)
                return cached

        # 创建新沙盒（在锁外执行，因为涉及文件系统操作）
        sandbox = self._local_provider.create_sandbox(session_id)

        with self._internal_lock:
            # 双重检查：可能在锁外期间已被其他线程创建
            cached = self._sandboxes.get(session_id)
            if cached is not None:
                self._sandboxes.move_to_end(session_id)
                return cached

            self._sandboxes[session_id] = sandbox
            self._evict_if_needed()

        return sandbox

    def release(self, session_id: str) -> None:
        """释放指定 session 的沙盒。

        当前实现不立即销毁沙盒，而是保留在 LRU 缓存中。
        当缓存超限时，最久未使用的沙盒会被自动淘汰。

        Args:
            session_id: 会话标识符。
        """
        # LRU 管理：不立即删除，由 _evict_if_needed 处理
        pass

    def get(self, session_id: str) -> Sandbox | None:
        """获取已缓存的沙盒实例（不创建新的）。

        Args:
            session_id: 会话标识符。

        Returns:
            Sandbox 实例，如果不存在则返回 None。
        """
        with self._internal_lock:
            sandbox = self._sandboxes.get(session_id)
            if sandbox is not None:
                self._sandboxes.move_to_end(session_id)
            return sandbox

    def get_or_create(self, session_id: str) -> Sandbox:
        """获取或创建沙盒实例。

        等同于 acquire，但语义更明确。

        Args:
            session_id: 会话标识符。

        Returns:
            Sandbox 实例。
        """
        return self.acquire(session_id)

    def _evict_if_needed(self) -> None:
        """如果缓存超限，淘汰最久未使用的条目。

        调用方必须持有 self._internal_lock。
        """
        while len(self._sandboxes) > self._max_cached:
            evicted_id, _ = self._sandboxes.popitem(last=False)
            logger.info(
                f"LRU 淘汰沙盒 session='{evicted_id}' "
                f"(缓存大小: {len(self._sandboxes)}/{self._max_cached})"
            )

    def _shutdown(self) -> None:
        """关闭所有缓存的沙盒实例。"""
        with self._internal_lock:
            self._sandboxes.clear()
            logger.info("SandboxProvider 已关闭所有沙盒实例")

    @property
    def active_count(self) -> int:
        """当前活跃的沙盒数量。"""
        with self._internal_lock:
            return len(self._sandboxes)
