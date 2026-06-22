from .models import (
    MemoryData,
    ProfileData,
    FactItem,
    SummaryData,
    SummarySection,
    FACT_CATEGORIES,
)
from .memory_engine import MemoryEngine, get_memory_engine, get_conversation_store, _engines


async def init_memory() -> None:
    """初始化记忆引擎

    预加载默认 Agent 的记忆引擎，并执行遗留数据迁移。
    """
    # 触发遗留数据迁移并预加载默认引擎
    get_memory_engine("_default")
    # 预加载主 Agent 引擎（如果存在配置）
    try:
        from app.infrastructure.database.json_store import agents_store
        agents = await agents_store.get_async("agents") if hasattr(agents_store, "get_async") else []
        if isinstance(agents, list):
            for agent in agents:
                agent_id = agent.get("id") if isinstance(agent, dict) else None
                if agent_id and agent_id != "_default":
                    get_memory_engine(agent_id)
    except Exception:
        # 预加载失败不影响启动
        pass


async def shutdown_memory() -> None:
    """关闭记忆引擎，保存未持久化的数据"""
    for engine in _engines.values():
        try:
            if engine._vector_manager is not None:
                engine._vector_manager.save()
        except Exception:
            pass


__all__ = [
    "MemoryEngine",
    "MemoryData",
    "ProfileData",
    "FactItem",
    "SummaryData",
    "SummarySection",
    "FACT_CATEGORIES",
    "get_memory_engine",
    "get_conversation_store",
    "init_memory",
    "shutdown_memory",
]
