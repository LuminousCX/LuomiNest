from loguru import logger
from app.infrastructure.database.usage_store import usage_store
from app.infrastructure.database.conversation_store import conversation_store
from app.infrastructure.database.json_store import agents_store


class UsageTracker:
    @staticmethod
    def record_usage(
        provider: str,
        model: str,
        usage: dict | None = None,
        agent_id: str | None = None,
        conv_id: str | None = None,
        is_stream: bool = False,
    ):
        if not usage:
            usage_store.record(
                provider=provider, model=model,
                agent_id=agent_id, conv_id=conv_id, is_stream=is_stream,
            )
            return
        prompt_tokens = usage.get("prompt_tokens") or usage.get("promptTokens") or 0
        completion_tokens = usage.get("completion_tokens") or usage.get("completionTokens") or 0
        total_tokens = usage.get("total_tokens") or usage.get("totalTokens") or 0
        if total_tokens == 0 and (prompt_tokens > 0 or completion_tokens > 0):
            total_tokens = prompt_tokens + completion_tokens
        usage_store.record(
            provider=provider, model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            agent_id=agent_id, conv_id=conv_id, is_stream=is_stream,
        )

    @staticmethod
    def get_full_stats(days: int | None = None, agent_id: str | None = None) -> dict:
        usage_summary = usage_store.get_summary(days)

        conv_list = conversation_store.list_conversations(agent_id)
        total_conversations = len(conv_list)

        total_messages = 0
        for meta in conv_list:
            conv = conversation_store.get(meta.get("id", ""))
            if conv:
                total_messages += len(conv.get("messages", []))

        agents_count = agents_store.count()

        memory_stats: dict = {}
        try:
            from app.engines.memory import get_memory_engine
            engine = get_memory_engine()
            data = engine.load_data()
            dailies = engine.list_dailies()
            memory_stats = {
                "has_memory": bool(data.profile.name or data.facts),
                "fact_count": len(data.facts),
                "daily_count": len(dailies),
            }
        except Exception as e:
            logger.warning(f"[UsageTracker] Failed to get memory stats: {e}")
            memory_stats = {
                "has_memory": False,
                "fact_count": 0,
                "daily_count": 0,
            }

        return {
            "usage": usage_summary,
            "conversations": total_conversations,
            "messages": total_messages,
            "agents_count": agents_count,
            "memory": memory_stats,
        }


usage_tracker = UsageTracker()
