import asyncio
import uuid
from datetime import datetime, timezone
from loguru import logger

from app.core.config import settings
from app.runtime.provider.llm.adapter import llm_adapter
from app.runtime.provider.llm.providers import LLMResponse
from app.infrastructure.database.conversation_store import conversation_store
from app.schemas.chat import ChatStreamChunk
from app.services.context_service import ContextService
from app.services.suggestion_service import SuggestionService

from fastapi.responses import StreamingResponse


class ChatService:
    def __init__(self, context: ContextService, suggestions: SuggestionService):
        self._llm_semaphore = asyncio.Semaphore(settings.LLM_MAX_CONCURRENT_REQUESTS)
        self._context = context
        self._suggestions = suggestions

    @staticmethod
    def persist_conv(conv_id: str, conv: dict) -> None:
        conv["updated_at"] = datetime.now(timezone.utc).isoformat()
        conversation_store.set(conv_id, conv)

    @staticmethod
    def save_user_message(
        conv: dict,
        content: str,
        file_content: str | None = None,
        file_name: str | None = None,
        file_type: str | None = None,
    ) -> None:
        if not content and not file_content and not file_name:
            return
        entry: dict = {"role": "user", "content": content}
        if file_content:
            entry["file_content"] = file_content
        if file_name:
            entry["file_name"] = file_name
        if file_type:
            entry["file_type"] = file_type
        if file_content and file_name:
            entry["files"] = [{"name": file_name, "type": file_type, "content": file_content}]
        last = conv["messages"][-1] if conv["messages"] else None
        if last and last.get("role") == "user":
            for key in ("file_content", "file_name", "file_type", "files"):
                if key in entry:
                    last[key] = entry[key]
            if not last.get("content"):
                last["content"] = content
        else:
            conv["messages"].append(entry)

    @staticmethod
    def save_assistant_message(conv: dict, state: dict, versions: list[dict] | None = None) -> None:
        content = state["content"] or "[已中断]"
        reasoning = state["reasoning"] or None
        interrupted = state["aborted"]
        entry: dict = {"role": "assistant", "content": content, "id": str(uuid.uuid4())}
        if reasoning:
            entry["reasoning_content"] = reasoning
        if interrupted:
            entry["interrupted"] = True
        if versions:
            new_version: dict = {"content": content, "id": str(uuid.uuid4())}
            if reasoning:
                new_version["reasoning_content"] = reasoning
            if state.get("model"):
                new_version["model"] = state["model"]
            if state.get("provider"):
                new_version["provider"] = state["provider"]
            if state.get("suggested_questions"):
                new_version["suggested_questions"] = state["suggested_questions"]
            all_versions = list(versions) + [new_version]
            entry["versions"] = all_versions
            entry["current_version"] = len(all_versions) - 1
        last = conv["messages"][-1] if conv["messages"] else None
        if not last or last.get("id") != entry.get("id"):
            conv["messages"].append(entry)

        default_titles = {"新对话", "New Conversation"}
        if conv.get("title") in default_titles and len(conv["messages"]) >= 2:
            first_user_message = None
            for msg in conv["messages"]:
                if msg.get("role") == "user":
                    first_user_message = msg.get("content", "")
                    break

            if first_user_message:
                conv["title"] = first_user_message[:30].strip()
                if len(first_user_message) > 30:
                    conv["title"] += "..."

    async def non_stream_generate(
        self,
        state: dict,
        all_messages: list[dict],
        provider: str,
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
    ) -> None:
        try:
            async with self._llm_semaphore:
                raw = await llm_adapter.chat(
                    messages=all_messages,
                    provider_name=provider,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                )
            if isinstance(raw, dict):
                state["content"] = raw.get("content", "")
                if raw.get("reasoning"):
                    state["reasoning"] = raw["reasoning"]
            else:
                state["content"] = raw
        except Exception as e:
            logger.error(f"[API] Non-stream error: {e}", exc_info=True)
            state["aborted"] = True
            state["content"] = "[Error] An internal error occurred"

    async def stream_chat(
        self,
        messages: list[dict],
        request,
        provider: str,
        model: str,
    ):
        chat_id = str(uuid.uuid4())
        try:
            async with self._llm_semaphore:
                async for chunk in llm_adapter.chat_stream(
                    messages=messages,
                    provider_name=provider,
                    model=model,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    top_p=request.top_p,
                ):
                    content = chunk.data.get("content", "")
                    rc = chunk.data.get("reasoning", "")
                    data = ChatStreamChunk(
                        id=chat_id, content=content,
                        reasoning_content=rc, model=model, provider=provider,
                    )
                    yield f"data: {data.model_dump_json()}\n\n"
        except Exception as e:
            logger.error(f"[STREAM] stream_chat error: {e}", exc_info=True)
            yield (
                f"data: {ChatStreamChunk(id=chat_id, content='[Error] An internal error occurred', model=model, provider=provider).model_dump_json()}\n\n"
            )
        finally:
            done_data = ChatStreamChunk(id=chat_id, content="", model=model, provider=provider, done=True)
            yield f"data: {done_data.model_dump_json()}\n\n"

    async def stream_response(
        self,
        conv_id: str,
        conv: dict,
        request,
        all_messages: list,
        provider: str,
        model: str,
        agent_id: str | None,
        state: dict,
        start_time: float,
        versions: list[dict] | None = None,
    ):
        chat_id = str(uuid.uuid4())

        async def generator():
            suggested_questions: list[str] = []
            try:
                async with self._llm_semaphore:
                    async for chunk in llm_adapter.chat_stream(
                        messages=all_messages,
                        provider_name=provider,
                        model=model,
                        temperature=request.temperature or 0.7,
                        max_tokens=request.max_tokens or 4096,
                        top_p=request.top_p or 0.9,
                    ):
                        content = chunk.data.get("content", "")
                        rc = chunk.data.get("reasoning", "")
                        if content:
                            state["content"] += content
                        if rc:
                            state["reasoning"] += rc
                        yield self._sse(chat_id, content, provider, model, rc)

            except Exception as e:
                state["aborted"] = True
                logger.error(f"[STREAM] Aborted: conv={conv_id}, error={e}", exc_info=True)
                yield self._sse(chat_id, "[Error] An internal error occurred", provider, model)

            finally:
                try:
                    if not state["aborted"] and state["content"]:
                        try:
                            suggested_questions = await self._suggestions.generate_suggestions_for_conv(
                                conv_id=conv_id,
                                messages=[dict(m) for m in conv["messages"]],
                                agent_id=agent_id,
                                provider=provider,
                                model=model,
                            )
                        except Exception as sq_err:
                            logger.warning(f"[STREAM] Suggested questions failed: conv={conv_id}, error={sq_err}")
                        state["suggested_questions"] = suggested_questions if suggested_questions else None

                    persist_state = dict(state)
                    if persist_state["aborted"] and persist_state["content"].startswith("[Error]"):
                        persist_state["content"] = ""
                    self.save_assistant_message(conv, persist_state, versions=versions)
                    self.persist_conv(conv_id, conv)
                except Exception as persist_err:
                    logger.error(f"[STREAM] Persist failed: conv={conv_id}, error={persist_err}")

                try:
                    yield self._sse_done(chat_id, provider, model, suggested_questions or None)
                except Exception as done_err:
                    logger.debug(f"[STREAM] Done event send failed (client may have disconnected): {done_err}")

                try:
                    self._context.schedule_memory_update(
                        [dict(m) for m in conv["messages"]], conv_id, agent_id,
                        llm_adapter=llm_adapter,
                    )
                except Exception as schedule_err:
                    logger.warning(f"[STREAM] Memory update scheduling failed: {schedule_err}")

        return StreamingResponse(
            generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    @staticmethod
    def _sse(cid: str, content: str, provider: str, model: str, reasoning: str = "") -> str:
        return (
            f"data: {ChatStreamChunk(id=cid, content=content, reasoning_content=reasoning, model=model, provider=provider).model_dump_json()}\n\n"
        )

    @staticmethod
    def _sse_done(
        cid: str,
        provider: str,
        model: str,
        suggested_questions: list[str] | None = None,
    ) -> str:
        return (
            f"data: {ChatStreamChunk(id=cid, content='', model=model, provider=provider, done=True, suggested_questions=suggested_questions).model_dump_json()}\n\n"
        )
