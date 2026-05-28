import asyncio
import re
from loguru import logger

from app.runtime.provider.llm.adapter import llm_adapter


class SuggestionService:
    SUGGESTED_QUESTIONS_PROMPT = """基于以下对话内容，生成3个用户可能想问的后续问题。

要求：
1. 问题要具体、有针对性，与对话内容紧密相关
2. 问题要简洁明了，每个不超过30个字
3. 问题应该引导用户深入探讨对话中的话题
4. 只返回问题列表，每行一个，不要编号，不要其他内容

对话内容：
{conversation}"""

    def __init__(self):
        self._pending_tasks: dict[str, asyncio.Task] = {}

    async def generate_suggested_questions(
        self,
        messages: list[dict],
        agent_id: str | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> list[str]:
        try:
            recent_messages = messages[-6:]
            conversation_text = ""
            for msg in recent_messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if isinstance(content, list):
                    text_parts = [
                        p.get("text", "")
                        for p in content
                        if isinstance(p, dict) and p.get("type") == "text"
                    ]
                    content = " ".join(text_parts)
                if role == "user":
                    conversation_text += f"用户: {content}\n"
                elif role == "assistant":
                    if len(content) > 500:
                        content = content[:500] + "..."
                    conversation_text += f"助手: {content}\n"

            if not conversation_text.strip():
                return []

            prompt = self.SUGGESTED_QUESTIONS_PROMPT.format(conversation=conversation_text)

            resolved_provider = provider or llm_adapter.default_provider
            resolved_model = model or llm_adapter.get_provider(resolved_provider).default_model

            result = await llm_adapter.chat(
                messages=[{"role": "user", "content": prompt}],
                provider_name=resolved_provider,
                model=resolved_model,
                temperature=0.7,
                max_tokens=200,
            )

            if isinstance(result, dict):
                text = result.get("content", "")
            else:
                text = str(result)

            questions: list[str] = []
            for line in text.strip().split("\n"):
                line = line.strip()
                line = re.sub(r'^[\d]+[.、)\]]\s*', '', line)
                if line and len(line) <= 50:
                    questions.append(line)

            return questions[:3]

        except Exception as e:
            logger.warning(f"[SuggestedQuestions] Failed to generate: {e}")
            return []

    async def generate_suggestions_for_conv(
        self,
        conv_id: str,
        messages: list[dict],
        agent_id: str | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> list[str]:
        old_task = self._pending_tasks.get(conv_id)
        if old_task and not old_task.done():
            old_task.cancel()
            logger.debug(f"[SuggestedQuestions] Cancelled previous task for conv={conv_id}")

        task = asyncio.create_task(
            self.generate_suggested_questions(messages, agent_id, provider, model)
        )
        self._pending_tasks[conv_id] = task

        try:
            result = await task
            return result
        except asyncio.CancelledError:
            logger.debug(f"[SuggestedQuestions] Task cancelled for conv={conv_id}")
            return []
        except Exception as e:
            logger.warning(f"[SuggestedQuestions] Task failed for conv={conv_id}: {e}")
            return []
        finally:
            if self._pending_tasks.get(conv_id) is task:
                del self._pending_tasks[conv_id]


suggestion_service = SuggestionService()
