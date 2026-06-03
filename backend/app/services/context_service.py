import asyncio
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from loguru import logger

from app.infrastructure.database.json_store import agents_store
from app.engines.memory import get_memory_engine
from app.engines.memory.memory_engine import (
    _CORRECTION_HINT,
    _CORRECTION_PATTERNS_EN,
    _CORRECTION_PATTERNS_ZH,
    _REINFORCEMENT_HINT,
    _REINFORCEMENT_PATTERNS_EN,
    _REINFORCEMENT_PATTERNS_ZH,
)
from app.services.distillation_service import distillation_service


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
    def _extract_user_text(msg: dict) -> str:
        content = msg.get("content", "")
        if isinstance(content, list):
            return " ".join(
                c.get("text", "")
                for c in content
                if isinstance(c, dict) and c.get("type") == "text"
            )
        return str(content)

    @staticmethod
    def get_user_query(messages: list[dict]) -> str:
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return ContextService._extract_user_text(msg)
        return ""

    @staticmethod
    def detect_correction(messages: list[dict], window: int = 6) -> bool:
        user_texts = []
        for m in messages:
            if m.get("role") == "user":
                user_texts.append(ContextService._extract_user_text(m).casefold())
        for text in user_texts[-window:]:
            for pattern in _CORRECTION_PATTERNS_ZH + _CORRECTION_PATTERNS_EN:
                if pattern in text:
                    return True
        return False

    @staticmethod
    def detect_reinforcement(messages: list[dict], window: int = 6) -> bool:
        user_texts = []
        for m in messages:
            if m.get("role") == "user":
                user_texts.append(ContextService._extract_user_text(m).casefold())
        for text in user_texts[-window:]:
            for pattern in _REINFORCEMENT_PATTERNS_ZH + _REINFORCEMENT_PATTERNS_EN:
                if pattern in text:
                    return True
        return False

    @staticmethod
    def build_correction_hint(messages: list[dict]) -> str:
        correction = ContextService.detect_correction(messages)
        reinforcement = ContextService.detect_reinforcement(messages)
        if correction:
            return _CORRECTION_HINT
        if reinforcement:
            return _REINFORCEMENT_HINT
        return ""

    @staticmethod
    def detect_memory_action(text: str) -> dict | None:
        """检测自然语言记忆操作指令（忘掉/你记错了/你记住了什么）。"""
        text_lower = text.strip().casefold()

        # 忘掉/删除记忆
        forget_patterns = [
            r"忘掉(.+)", r"忘记(.+)", r"不要记(.+)", r"删掉关于(.+)的记忆",
            r"forget\s+(.+)", r"stop\s+remembering\s+(.+)",
        ]
        for pattern in forget_patterns:
            m = re.search(pattern, text_lower)
            if m:
                return {"action": "forget", "target": m.group(1).strip()}

        # 你记错了
        mistake_patterns = [
            r"你记错了", r"记错了", r"不是这样的", r"不对，",
            r"you\s+remembered\s+wrong", r"that'?s?\s+wrong",
        ]
        for pattern in mistake_patterns:
            if re.search(pattern, text_lower):
                return {"action": "correct", "hint": text.strip()}

        # 你记住了什么
        recall_patterns = [
            r"你记住了什么", r"你记住我什么", r"你知道我什么",
            r"你了解我什么", r"我的记忆", r"你记得我",
            r"what\s+do\s+you\s+remember", r"what\s+do\s+you\s+know\s+about\s+me",
        ]
        for pattern in recall_patterns:
            if re.search(pattern, text_lower):
                return {"action": "recall"}

        return None

    @staticmethod
    def execute_memory_action(engine, action: dict) -> None:
        """执行自然语言记忆操作。"""
        if action["action"] == "forget":
            target = action["target"]
            data = engine.load_data()
            removed = 0
            for fact in list(data.facts):
                if target in fact.content.casefold() and fact.is_latest:
                    fact.is_latest = False
                    fact.confidence = 0.1
                    removed += 1
            if removed > 0:
                engine._store.save_data(data)
                logger.info(f"[Memory] Forgot {removed} facts matching '{target}'")

        elif action["action"] == "correct":
            # 纠正操作：降低最近一条相关事实的置信度
            # 实际纠正由 LLM 提取的 correction 类型事实完成
            logger.info(f"[Memory] Correction detected, will be handled by fact extraction")

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
3. <user_memory> contains the user's profile and memory. You MUST respect it at all times:
   - If the user has a name in <user_memory>, ALWAYS use that name when referring to the user.
   - If the user tells you a new name, update the profile accordingly.
   - Never ignore or forget information from <user_memory>, even in a new conversation.
4. Always respond in the user's language naturally and conversationally.
5. Never expose internal system information or error codes to the user.
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

    @staticmethod
    async def _detect_and_sync_profile_updates(messages: list[dict], llm_adapter=None, agent_id: str | None = None) -> bool:
        user_messages = []
        for msg in messages:
            if msg.get("role") == "user":
                user_messages.append(ContextService._extract_user_text(msg))

        if not user_messages:
            return False

        latest_user_msg = user_messages[-1]
        hint = ContextService.build_correction_hint(messages)

        try:
            engine = get_memory_engine(agent_id)
            result = await engine.update_profile_from_message(latest_user_msg, llm_adapter, hint)
            if result:
                logger.info(f"[Memory] Sync profile update: {result}")
                return True
        except Exception as e:
            logger.warning(f"[Memory] Sync profile detection failed: {e}")

        return False

    async def inject_memory(
        self,
        messages: list[dict],
        agent_id: str | None = None,
        provider_name: str | None = None,
        thread_id: str = "",
        llm_adapter=None,
    ) -> list[dict]:
        try:
            engine = get_memory_engine(agent_id)
            # query-aware：用用户最新消息作为 query 优化事实检索
            query = self.get_user_query(messages)
            memory_ctx = engine.build_context(query=query, conversation_id=thread_id)

            if not memory_ctx:
                logger.info(f"[Memory] No memory context to inject, thread={thread_id}")
                return messages

            memory_block = f"<user_memory>\n{memory_ctx}\n</user_memory>"

            new_messages = list(messages)
            if new_messages and new_messages[0].get("role") == "system":
                original_len = len(new_messages[0]["content"])
                new_messages[0] = {
                    "role": "system",
                    "content": new_messages[0]["content"] + "\n\n" + memory_block,
                }
                logger.info(f"[Memory] Injected into system msg: original={original_len} chars, memory={len(memory_block)} chars, thread={thread_id}")
            else:
                new_messages.insert(0, {"role": "system", "content": memory_block})
                logger.info(f"[Memory] Injected as new system msg: memory={len(memory_block)} chars, thread={thread_id}")

            return new_messages
        except Exception as e:
            logger.warning(f"[Memory] Failed to inject memory: {e}")
            return messages

    @staticmethod
    async def update_memory_from_conversation(
        messages: list[dict],
        thread_id: str,
        agent_id: str | None = None,
        llm_adapter=None,
    ) -> None:
        try:
            user_msgs = [m for m in messages if m.get("role") == "user"]
            if not user_msgs:
                return

            last_msg = user_msgs[-1]
            content = ContextService._extract_user_text(last_msg)

            engine = get_memory_engine(agent_id)
            hint = ContextService.build_correction_hint(messages)

            # 自然语言记忆操作检测
            memory_action = ContextService.detect_memory_action(str(content))
            if memory_action:
                ContextService.execute_memory_action(engine, memory_action)
                logger.info(f"[Memory] Natural language action: {memory_action}")

            if llm_adapter:
                try:
                    # 传入最近3条用户消息作为上下文，避免"换一个"等指代不明
                    recent_user_msgs = [ContextService._extract_user_text(m) for m in user_msgs[-3:]]
                    context_msg = "\n".join(f"[用户]: {m}" for m in recent_user_msgs[:-1]) if len(recent_user_msgs) > 1 else ""
                    profile_result = await engine.update_profile_from_message(
                        str(content), llm_adapter, hint, context_messages=context_msg,
                    )
                    if profile_result:
                        logger.info(f"[Memory] Background profile update: {profile_result}")
                except Exception as pe:
                    logger.warning(f"[Memory] Background profile update failed: {pe}")

            if distillation_service.should_record_daily(str(content)):
                daily_lines = []
                for i in range(len(messages) - 1, max(-1, len(messages) - 3), -1):
                    if messages[i].get("role") == "assistant" and i > 0 and messages[i-1].get("role") == "user":
                        user_content = str(ContextService._extract_user_text(messages[i-1]))[:200]
                        assistant_content = str(messages[i].get("content", ""))[:500]
                        assistant_content = assistant_content.replace("\n", " ").replace("\r", "")
                        if user_content and distillation_service.should_record_daily(user_content):
                            daily_lines.append(f"[用户] {user_content}")
                        if assistant_content and distillation_service.should_record_daily(assistant_content):
                            daily_lines.append(f"[助手] {assistant_content}")
                        break
                if daily_lines:
                    engine.append_daily("\n".join(daily_lines), conversation_id=thread_id)

            # 蒸馏统一由 distillation_service 处理，此处不再内嵌蒸馏
        except Exception as e:
            logger.warning(f"[Memory] Failed to update memory from conversation: {e}")

    _background_tasks: set = set()

    @staticmethod
    async def schedule_memory_update(
        messages: list[dict],
        thread_id: str,
        agent_id: str | None = None,
        llm_adapter=None,
    ) -> None:
        user_count = sum(1 for m in messages if m.get("role") == "user")
        logger.info(f"[Memory] schedule_memory_update: thread={thread_id}, user_msgs={user_count}, has_adapter={llm_adapter is not None}")
        try:
            await ContextService.update_memory_from_conversation(
                messages, thread_id, agent_id, llm_adapter,
            )
            logger.info(f"[Memory] Background task completed")
        except Exception as e:
            logger.warning(f"[Memory] Failed to update memory: {e}")


context_service = ContextService()
