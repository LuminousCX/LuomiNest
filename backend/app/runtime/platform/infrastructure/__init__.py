"""系统级基础设施模块。

为所有平台适配器提供通用能力组件：

- retry: 指数退避重试器
- dedup: 消息去重器
- reconnect: 统一重连框架
- message_batch: 文本批量聚合器
- sanitizer: 日志敏感信息脱敏
- truncation: 消息长度安全截断

所有模块相互独立，无循环依赖。
"""

from app.runtime.platform.infrastructure.retry import (
    RetryConfig,
    async_retry,
)
from app.runtime.platform.infrastructure.dedup import (
    MessageDeduplicator,
)
from app.runtime.platform.infrastructure.reconnect import (
    ReconnectMixin,
    ReconnectState,
    ReconnectStrategy,
)
from app.runtime.platform.infrastructure.message_batch import (
    TextBatchAggregator,
)
from app.runtime.platform.infrastructure.sanitizer import (
    LogSanitizer,
    sanitize,
)
from app.runtime.platform.infrastructure.truncation import (
    MessageTruncator,
    TruncateMode,
    truncate,
)

__all__ = [
    # retry
    "RetryConfig",
    "async_retry",
    # dedup
    "MessageDeduplicator",
    # reconnect
    "ReconnectMixin",
    "ReconnectState",
    "ReconnectStrategy",
    # message_batch
    "TextBatchAggregator",
    # sanitizer
    "LogSanitizer",
    "sanitize",
    # truncation
    "MessageTruncator",
    "TruncateMode",
    "truncate",
]
