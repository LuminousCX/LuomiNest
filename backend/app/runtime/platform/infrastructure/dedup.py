"""消息去重器。

基于 TTL 缓存的 LRU 消息去重，防止平台重复推送导致重复处理。
使用 collections.OrderedDict 实现 O(1) 的 LRU + TTL 淘汰。
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict

from loguru import logger


class MessageDeduplicator:
    """基于 TTL 缓存的消息去重器。

    内部维护一个 OrderedDict，键为 message_id，值为首次看到的时间戳。
    当缓存超过 max_size 或条目 TTL 过期时自动淘汰。

    Attributes:
        max_size: 缓存最大条目数。
        ttl: 条目存活时间（秒）。
    """

    def __init__(self, max_size: int = 2000, ttl: float = 300.0) -> None:
        """初始化去重器。

        Args:
            max_size: 缓存最大条目数，超出后淘汰最久未访问的条目。
            ttl: 条目存活时间（秒），超过后视为过期。
        """
        self.max_size = max_size
        self.ttl = ttl
        self._cache: OrderedDict[str, float] = OrderedDict()
        self._lock = threading.Lock()

    def is_duplicate(self, message_id: str) -> bool:
        """判断消息是否重复。

        如果 message_id 已存在且未过期，则视为重复。
        同时会将该条目移到最近访问位置（LRU 更新）。

        Args:
            message_id: 消息唯一标识。

        Returns:
            True 表示消息重复（已见过且未过期），False 表示新消息。
        """
        if not message_id:
            return False

        now = time.monotonic()
        with self._lock:
            if message_id in self._cache:
                seen_at = self._cache[message_id]
                if now - seen_at < self.ttl:
                    # 移到最近访问位置
                    self._cache.move_to_end(message_id)
                    return True
                # 已过期，删除旧条目
                del self._cache[message_id]

            return False

    def mark_seen(self, message_id: str) -> None:
        """标记消息为已见。

        如果缓存已满，先淘汰最久未访问的条目。
        同时触发定期清理。

        Args:
            message_id: 消息唯一标识。
        """
        if not message_id:
            return

        now = time.monotonic()
        with self._lock:
            # 如果已存在，更新位置
            if message_id in self._cache:
                self._cache.move_to_end(message_id)
                self._cache[message_id] = now
                return

            # 淘汰过期条目
            self._evict_expired(now)

            # 淘汰最久未访问的条目直到有空间
            while len(self._cache) >= self.max_size:
                evicted_id, evicted_time = self._cache.popitem(last=False)
                logger.debug(
                    f"[Dedup] LRU 淘汰: message_id={evicted_id}, "
                    f"age={now - evicted_time:.1f}s"
                )

            self._cache[message_id] = now

    def _evict_expired(self, now: float) -> None:
        """清理所有过期条目（需在持有锁时调用）。"""
        expired_keys = [
            mid for mid, seen_at in self._cache.items()
            if now - seen_at >= self.ttl
        ]
        for mid in expired_keys:
            del self._cache[mid]
        if expired_keys:
            logger.debug(f"[Dedup] TTL 清理 {len(expired_keys)} 条过期记录")

    def cleanup(self) -> int:
        """手动触发清理过期条目。

        Returns:
            被清理的条目数。
        """
        now = time.monotonic()
        with self._lock:
            before = len(self._cache)
            self._evict_expired(now)
            return before - len(self._cache)

    @property
    def size(self) -> int:
        """当前缓存中的条目数。"""
        with self._lock:
            return len(self._cache)

    def clear(self) -> None:
        """清空所有缓存。"""
        with self._lock:
            self._cache.clear()
