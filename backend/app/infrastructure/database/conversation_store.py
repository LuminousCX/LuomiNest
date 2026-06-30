"""对话存储 shim — 实际实现已迁移至 Facade 层。

保留导入兼容性：
`from app.infrastructure.database.conversation_store import conversation_store` 零改动。

底层委托 ConversationRepository + conversations 表（SQLite），替代原
data/conversations/*.json + _index.json 的 per-conv 文件方案。
- messages 用 JSON 列存储（不拆表）
- search_text 用 LIKE 搜索
- deleted_at 软删除（回收站）
- migrate_from_json_store() 供 Phase 5 迁移器调用
"""
from app.infrastructure.database.facades.conversation_store import ConversationFacade, conversation_store

__all__ = ["ConversationFacade", "conversation_store"]
