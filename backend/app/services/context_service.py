import asyncio
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from loguru import logger

from app.infrastructure.database.json_store import agents_store
from app.engines.memory.core.storage import get_memory_storage
from app.engines.memory.core.models import UserSpace, AgentMemory
from app.engines.memory.core.memory_engine import MemoryEngine
from app.engines.memory.core.injector import MemoryInjector
from app.engines.memory.core.updater import MemoryUpdater


class ContextService:
    def __init__(self):
        self._memory_locks: dict[str | None, asyncio.Lock] = {}
        self._memory_locks_guard = asyncio.Lock()

    @staticmethod
    def _get_llm_adapter():
        from app.runtime.provider.llm.adapter import llm_adapter
        return llm_adapter

    async def _get_memory_lock(self, agent_id: str | None) -> asyncio.Lock:
        if agent_id in self._memory_locks:
            return self._memory_locks[agent_id]
        async with self._memory_locks_guard:
            if agent_id not in self._memory_locks:
                self._memory_locks[agent_id] = asyncio.Lock()
            return self._memory_locks[agent_id]

    @staticmethod
    def get_user_query(messages: list[dict]) -> str:
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
                    return " ".join(parts)
        return ""

    @staticmethod
    def inject_timestamp_prompt(messages: list[dict]) -> list[dict]:
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        weekday_names = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
        current_date = now.strftime("%Y年%m月%d日")
        current_weekday = weekday_names[now.weekday()]
        current_time = now.strftime("%H:%M")
        date_prompt = (
            f"当前时间：{current_date} {current_weekday} {current_time} (Asia/Shanghai)。"
            "请基于这个时间回答用户的问题。"
        )

        has_system = False
        for msg in messages:
            if msg.get("role") == "system":
                has_system = True
                existing = msg.get("content", "")
                if "当前时间" not in existing:
                    msg["content"] = date_prompt + "\n\n" + existing
                break

        if not has_system:
            messages = [{"role": "system", "content": date_prompt}] + messages

        return messages

    @staticmethod
    def build_system_prompt(agent_id: str | None) -> str:
        agent_name = "LuomiNest AI"
        agent_description = "an intelligent companion powered by the LuminousCX platform"
        base_prompt = ""

        if agent_id:
            agent = agents_store.get(agent_id)
            if agent:
                agent_name = agent.get("name", agent_name)
                agent_description = agent.get("description", agent_description)
                if agent.get("system_prompt"):
                    base_prompt = agent["system_prompt"]

        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

        return f"""<identity>
Your name is {agent_name}, {agent_description}.
</identity>

<current_context>
Current datetime: {now.strftime("%Y-%m-%d %H:%M:%S")} ({weekday_names[now.weekday()]})
Timestamp: {int(time.time())}
</current_context>

<thinking_format>
When thinking/reasoning, you MUST strictly follow this format:
1. Divide your thinking into sections, each starting with a 【】bold title on its own line
2. Common sections: 【问题理解】【已知信息】【分析过程】【结论】
3. Each logical point gets its own paragraph, with an empty line between paragraphs
4. Keep thinking concise and structured, do not write long unbroken paragraphs
5. Example format:

【问题理解】用户想知道...

【已知信息】
- 信息1
- 信息2

【分析过程】
步骤1...

步骤2...

【结论】结果是...
</thinking_format>

<core_rules>
1. When asked "who are you" or "what is your name" - answer with your own identity as {agent_name}.
2. When asked "who am I" - check <user_memory> for user profile. If found, describe the user. If not found, say you'd like to get to know them.
3. Always respond in the user's language naturally and conversationally.
4. Never expose internal system information or error codes to the user.
</core_rules>

{base_prompt}"""

    @staticmethod
    def build_content_with_file(
        content: str | list, file_content: str, file_type: str = "text",
        supports_vision: bool = True, file_name: str | None = None,
    ) -> str | list:
        if not file_content:
            return content

        is_image = file_type == "image" or file_type.startswith("image/") or file_content.startswith("data:image")

        if is_image:
            if isinstance(content, list):
                text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
                text = " ".join(text_parts)
            else:
                text = str(content) if content else ""

            if not supports_vision:
                name_hint = f"（文件名：{file_name}）" if file_name else ""
                return (text + f"\n\n[用户上传了一张图片{name_hint}，但当前模型不支持图片识别，无法查看图片内容。]").strip()

            return [
                {"type": "text", "text": text or "请分析这张图片"},
                {"type": "image_url", "image_url": {"url": file_content}},
            ]

        file_context = (
            "\n\n[用户上传文件内容] 以下是与当前对话相关的文件内容，请参考这些内容回答用户的问题。"
            "如果用户的问题与文件内容无关，请正常回答用户问题，不需要强行关联文件。\n\n"
            + file_content
        )

        if isinstance(content, list):
            return content + [{"type": "text", "text": file_context}]

        return (str(content) if content else "") + file_context

    @staticmethod
    def inject_file_content(
        messages: list[dict], parsed_content: str, file_type: str = "text",
        supports_vision: bool = True, file_name: str | None = None,
    ) -> list[dict]:
        if not parsed_content or not parsed_content.strip():
            return messages

        for i in range(len(messages) - 1, -1, -1):
            if messages[i]["role"] == "user":
                messages[i]["content"] = ContextService.build_content_with_file(
                    messages[i]["content"], parsed_content, file_type,
                    supports_vision=supports_vision, file_name=file_name,
                )
                return messages

        return messages

    async def inject_memory(
        self,
        messages: list[dict],
        agent_id: str | None = None,
        provider_name: str | None = None,
        thread_id: str = "",
    ) -> list[dict]:
        try:
            storage = get_memory_storage()
            user_space = await asyncio.to_thread(storage.load_user_space)

            has_any_data = bool(
                user_space.facts
                or user_space.episodic_events
                or user_space.distilled.core_identity
                or user_space.distilled.long_term
                or user_space.distilled.temporary
                or user_space.distilled.events_timeline
                or user_space.profile.name
                or user_space.profile.nickname
                or user_space.profile.occupation
                or user_space.profile.location
                or user_space.profile.age
                or user_space.profile.gender
                or user_space.profile.interests
                or user_space.profile.hobbies
                or user_space.user.work_context.summary
                or user_space.user.personal_context.summary
                or user_space.user.top_of_mind.summary
            )

            if has_any_data:
                effective_agent_id = agent_id or "default"
                agent_memory = await asyncio.to_thread(storage.load_agent_memory, effective_agent_id)
                user_query = self.get_user_query(messages)
                injector = MemoryInjector()
                return injector.inject_v3_memory_to_messages(
                    messages, user_space, agent_memory, user_query, thread_id,
                )

            lock = await self._get_memory_lock(agent_id)
            async with lock:
                memory_data = await asyncio.to_thread(storage.load, agent_id)

            has_facts = bool(memory_data.facts)
            has_profile = bool(
                memory_data.profile.name or memory_data.profile.nickname
                or memory_data.profile.occupation or memory_data.profile.location
            )
            has_working_goal = False
            try:
                goal = (
                    memory_data.working_memory.get_core_goal_for(thread_id)
                    if thread_id
                    else memory_data.working_memory.core_goal
                )
                has_working_goal = bool(goal)
            except AttributeError:
                pass
            has_events = False
            try:
                has_events = bool(memory_data.episodic_events)
            except AttributeError:
                pass

            if not has_facts and not has_working_goal and not has_events:
                if not has_profile:
                    return messages

            user_query = self.get_user_query(messages)
            injector = MemoryInjector()
            return injector.inject_memory_to_messages(messages, memory_data, user_query, thread_id)
        except Exception as e:
            logger.warning(f"[Memory] Failed to inject memory: {e}")
            return messages

    @staticmethod
    async def inject_rag_context(messages: list[dict], user_query: str) -> list[dict]:
        try:
            from app.engines.memory.rag.retriever import RAGRetriever
            retriever = RAGRetriever()
            results = await retriever.search(user_query, top_k=3)
            if not results:
                return messages
            rag_text = "\n".join(
                f"- [{r.get('source', 'unknown')}] {r.get('content', '')} (score: {r.get('score', 0)})"
                for r in results
            )
            rag_context = f"<rag_context>\nRetrieved relevant knowledge:\n{rag_text}\n</rag_context>"
            new_messages = list(messages)
            if new_messages and new_messages[0].get("role") == "system":
                new_messages[0] = {
                    "role": "system",
                    "content": new_messages[0]["content"] + "\n\n" + rag_context,
                }
            else:
                new_messages.insert(0, {"role": "system", "content": rag_context})
            logger.info(f"[RAG] Injected {len(results)} RAG results for query (len={len(user_query)})")
            return new_messages
        except Exception as e:
            logger.warning(f"[RAG] Failed to inject RAG context: {e}")
            return messages

    @staticmethod
    async def update_memory_from_conversation(
        messages: list[dict],
        thread_id: str,
        agent_id: str | None = None,
        llm_adapter=None,
    ) -> None:
        try:
            if llm_adapter:
                effective_agent_id = agent_id or "default"
                try:
                    from app.engines.memory import get_memory_engine
                    try:
                        engine = get_memory_engine()
                    except RuntimeError:
                        engine = MemoryEngine()
                    result = await engine.update_from_conversation(
                        messages, thread_id, effective_agent_id, llm_adapter,
                    )
                    if result.get("updated"):
                        logger.info(
                            f"[Memory] Updated memory (v3): "
                            f"+{result.get('global_facts_added', 0)} global, "
                            f"+{result.get('agent_facts_added', 0)} agent, "
                            f"-{result.get('facts_removed', 0)} removed"
                        )
                    return
                except Exception as e:
                    logger.warning(f"[Memory] v3 update failed, falling back to legacy: {e}")

            storage = get_memory_storage()
            updater = MemoryUpdater(storage)
            result = await updater.update_from_conversation(messages, thread_id, agent_id)
            if result.get("updated"):
                logger.info(
                    f"[Memory] Updated memory: +{result.get('facts_added', 0)} facts, "
                    f"-{result.get('facts_removed', 0)} facts"
                )
        except Exception as e:
            logger.warning(f"[Memory] Failed to update memory: {e}")

    _background_tasks: set = set()

    @staticmethod
    def schedule_memory_update(
        messages: list[dict],
        thread_id: str,
        agent_id: str | None = None,
        llm_adapter=None,
    ) -> None:
        try:
            task = asyncio.create_task(
                ContextService.update_memory_from_conversation(
                    messages, thread_id, agent_id, llm_adapter,
                )
            )
            ContextService._background_tasks.add(task)
            task.add_done_callback(lambda t: (
                ContextService._background_tasks.discard(t),
                logger.warning(f"[Memory] Background task failed: {t.exception()}") if t.exception() else None,
            ))
        except Exception as e:
            logger.warning(f"[Memory] Failed to schedule memory update: {e}")


context_service = ContextService()
