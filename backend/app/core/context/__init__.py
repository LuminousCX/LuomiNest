"""LuomiNest 上下文管理包。

原实现（约 790 行）集中在本文件，现按职责拆分为同包内模块：

- constants.py     : Token 估算与上下文预算常量
- token_counter.py : TokenCounter（token 估算、模型上下文窗口查询）
- truncator.py     : ContextTruncator（消息截断/修复）
- compressors.py   : TruncateByTurnsCompressor / LLMSummaryCompressor / split_history
- manager.py       : ContextManager 与 get_context_manager / invalidate_context_cache 缓存

本文件仅负责 re-export，全库继续使用 `from app.core.context import X`，
导入路径与行为与拆分前完全一致。
"""

from app.core.context.constants import (
    DEFAULT_CONTEXT_WINDOW,
    FALLBACK_CONTEXT_WINDOW,
    IMAGE_TOKEN_ESTIMATE,
    REBUILD_BUDGET_RATIO,
    SUMMARY_TEMPERATURE,
    TOKEN_WEIGHT_CHINESE,
    TOKEN_WEIGHT_OTHER,
)
from app.core.context.token_counter import TokenCounter
from app.core.context.truncator import ContextTruncator
from app.core.context.compressors import (
    LLMSummaryCompressor,
    TruncateByTurnsCompressor,
    split_history,
)
from app.core.context.manager import (
    ContextManager,
    get_context_manager,
    invalidate_context_cache,
)
