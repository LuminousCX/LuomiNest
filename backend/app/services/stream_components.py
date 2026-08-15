"""
流式管线基础组件 —— 从 chat_service.py 抽出的无状态流处理组件。

独立成模块的原因：chat_service 顶层导入 StreamProcessor，
而 StreamProcessor 又需要本模块的两个组件；若组件留在 chat_service
内会形成 chat_service ↔ stream_processor 循环导入，只能靠
__init__ 内延迟导入掩盖。抽离后依赖变为单向：

    chat_service → stream_processor → stream_components
"""
import time


class StreamCoalescer:
    """流式 chunk 合并器 - 合并小 chunk 减少 UI 更新频率。

    借鉴 DeepTutor 的 stream_coalesce_chars / stream_coalesce_seconds 设计。
    """

    def __init__(self, coalesce_chars: int = 64, coalesce_seconds: float = 0.04):
        self.coalesce_chars = coalesce_chars
        self.coalesce_seconds = coalesce_seconds
        self._buffer: str = ""
        self._last_flush_time: float = 0

    async def feed(self, token: str) -> str | None:
        """输入一个 token，返回合并后的 chunk（如果达到阈值），否则返回 None。"""
        self._buffer += token
        now = time.monotonic()
        if len(self._buffer) >= self.coalesce_chars or \
           (now - self._last_flush_time) >= self.coalesce_seconds:
            return self.flush()
        return None

    def flush(self) -> str:
        """强制输出缓冲区内容。"""
        result = self._buffer
        self._buffer = ""
        self._last_flush_time = time.monotonic()
        return result


class ThinkingTagManager:
    """Thinking 标签管理器 - 在流式中检测 <think>/</think> 标签并正确分流。"""

    def __init__(self):
        self._in_thinking = False
        self._tag_buffer = ""  # 用于处理标签跨 chunk 的情况

    def process(self, text: str) -> tuple[str, str]:
        """处理文本，返回 (content_text, reasoning_text)。"""
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        i = 0
        combined = self._tag_buffer + text
        self._tag_buffer = ""

        while i < len(combined):
            if not self._in_thinking:
                think_start = combined.find("<think>", i)
                if think_start == -1:
                    content_parts.append(combined[i:])
                    break
                else:
                    content_parts.append(combined[i:think_start])
                    self._in_thinking = True
                    i = think_start + len("<think>")
            else:
                think_end = combined.find("</think>", i)
                if think_end == -1:
                    # 检查是否是不完整的标签在末尾
                    remaining = combined[i:]
                    if remaining.endswith("<") or remaining.endswith("</") or \
                       remaining.endswith("</t") or remaining.endswith("</th") or \
                       remaining.endswith("</thi") or remaining.endswith("</thin") or \
                       remaining.endswith("</think"):
                        # 可能是不完整标签，缓存等待下一个 chunk
                        self._tag_buffer = remaining
                        break
                    reasoning_parts.append(remaining)
                    break
                else:
                    reasoning_parts.append(combined[i:think_end])
                    self._in_thinking = False
                    i = think_end + len("</think>")

        return "".join(content_parts), "".join(reasoning_parts)
