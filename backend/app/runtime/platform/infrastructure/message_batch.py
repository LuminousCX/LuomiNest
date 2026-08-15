"""文本批量聚合器。

将快速连续到达的短文本聚合为一条完整消息，
防止消息碎片化（如用户快速分段发送的内容）。
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field

from loguru import logger


@dataclass
class _BufferEntry:
    """单个发送者的文本缓冲区。"""

    sender_id: str
    fragments: list[str] = field(default_factory=list)
    first_arrival: float = 0.0
    last_arrival: float = 0.0


class TextBatchAggregator:
    """文本批量聚合器。

    将同一发送者在聚合窗口内的多条短文本合并为一条完整消息。
    当窗口超时或达到最大长度时，返回聚合后的文本。

    Attributes:
        aggregation_window: 聚合窗口时间（秒），默认 1.5 秒。
        max_length: 单条聚合结果的最大字符数，0 表示不限制。
    """

    def __init__(
        self,
        aggregation_window: float = 1.5,
        max_length: int = 0,
    ) -> None:
        """初始化聚合器。

        Args:
            aggregation_window: 聚合窗口时间（秒），窗口内连续文本会被合并。
            max_length: 聚合结果最大字符数，0 表示不限制。
        """
        self.aggregation_window = aggregation_window
        self.max_length = max_length
        self._buffers: dict[str, _BufferEntry] = {}
        self._lock = threading.Lock()

    def add_message(self, sender_id: str, text: str) -> str | None:
        """添加一条文本片段。

        如果聚合窗口已过期，先刷新之前的缓冲，再开始新的聚合。
        返回聚合后的文本，或 None 表示仍在等待更多片段。

        Args:
            sender_id: 发送者标识。
            text: 文本内容。

        Returns:
            聚合后的完整文本（窗口过期时），或 None（仍在聚合中）。
        """
        now = time.monotonic()

        with self._lock:
            entry = self._buffers.get(sender_id)

            if entry is None:
                # 新发送者，开始聚合
                self._buffers[sender_id] = _BufferEntry(
                    sender_id=sender_id,
                    fragments=[text],
                    first_arrival=now,
                    last_arrival=now,
                )
                logger.debug(
                    f"[BatchAgg] 开始聚合: sender={sender_id}, fragment=1"
                )
                return None

            elapsed = now - entry.last_arrival

            if elapsed > self.aggregation_window:
                # 窗口已过期，刷新旧缓冲并开始新聚合
                result = self._build_text(entry)
                entry.fragments = [text]
                entry.first_arrival = now
                entry.last_arrival = now
                logger.debug(
                    f"[BatchAgg] 窗口过期，刷新: sender={sender_id}, "
                    f"fragments={len(entry.fragments)}"
                )
                return result

            # 窗口内，追加片段
            entry.fragments.append(text)
            entry.last_arrival = now

            # 检查是否达到最大长度
            if self.max_length > 0:
                total_len = sum(len(f) for f in entry.fragments)
                if total_len >= self.max_length:
                    result = self._build_text(entry)
                    del self._buffers[sender_id]
                    return result

            return None

    def flush(self, sender_id: str) -> str | None:
        """强制刷新指定发送者的缓冲区。

        Args:
            sender_id: 发送者标识。

        Returns:
            聚合后的文本，或 None 表示缓冲区为空。
        """
        with self._lock:
            entry = self._buffers.pop(sender_id, None)
            if entry is None:
                return None

            result = self._build_text(entry)
            logger.debug(
                f"[BatchAgg] 手动刷新: sender={sender_id}, "
                f"fragments={len(entry.fragments)}"
            )
            return result

    def flush_all(self) -> dict[str, str]:
        """强制刷新所有发送者的缓冲区。

        Returns:
            发送者标识到聚合文本的映射。
        """
        with self._lock:
            results: dict[str, str] = {}
            for sender_id, entry in list(self._buffers.items()):
                text = self._build_text(entry)
                if text:
                    results[sender_id] = text
            self._buffers.clear()
            if results:
                logger.debug(f"[BatchAgg] 全部刷新: {len(results)} 个发送者")
            return results

    def get_buffered(self, sender_id: str) -> str | None:
        """获取指定发送者当前缓冲的文本（不刷新）。

        Args:
            sender_id: 发送者标识。

        Returns:
            当前缓冲的文本，或 None 表示无缓冲。
        """
        with self._lock:
            entry = self._buffers.get(sender_id)
            if entry is None:
                return None
            return self._build_text(entry)

    def _build_text(self, entry: _BufferEntry) -> str:
        """将缓冲区片段合并为完整文本。"""
        return "".join(entry.fragments)

    @property
    def active_senders(self) -> list[str]:
        """当前正在聚合的发送者列表。"""
        with self._lock:
            return list(self._buffers.keys())

    def cleanup_expired(self) -> int:
        """清理所有已过期的缓冲区。

        Returns:
            被清理的发送者数量。
        """
        now = time.monotonic()
        cleaned = 0
        with self._lock:
            expired = [
                session_id for session_id, entry in self._buffers.items()
                if now - entry.last_arrival > self.aggregation_window
            ]
            for session_id in expired:
                del self._buffers[session_id]
                cleaned += 1
        if cleaned:
            logger.debug(f"[BatchAgg] 清理 {cleaned} 个过期缓冲")
        return cleaned
