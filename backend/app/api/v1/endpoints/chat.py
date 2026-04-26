import uuid
import time
from datetime import datetime, timezone
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from loguru import logger

from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatStreamChunk,
    ConversationCreate,
    ConversationResponse,
    ConversationListResponse,
)
from app.runtime.provider.llm.adapter import llm_adapter
from app.infrastructure.database.json_store import conversations_store, agents_store
from app.runtime.plugin.skill.executor import SkillExecutor
from app.runtime.plugin.skill.registry import SkillRegistry

router = APIRouter(prefix="/chat", tags=["chat"])

_skill_executor = SkillExecutor()


def _build_system_prompt_with_tools(agent_id: str | None) -> str:
    base_prompt = ""
    if agent_id:
        agent = agents_store.get(agent_id)
        if agent and agent.get("system_prompt"):
            base_prompt = agent["system_prompt"]

    available_skills = SkillRegistry.list_skills()
    if not available_skills:
        return base_prompt

    tools_section = "\n\n## 可用工具\n\n你可以使用以下工具来帮助用户：\n\n"
    for skill in available_skills:
        if skill.get("is_active", True):
            tools_section += f"### {skill['name']}\n{skill.get('description', '')}\n"
            params = skill.get("parameters", {})
            if params:
                tools_section += "参数:\n"
                for pname, pinfo in params.items():
                    tools_section += f"- {pname}: {pinfo.get('description', '')} ({pinfo.get('type', 'string')})\n"
            tools_section += "\n"

    tools_section += "\n## 工具调用格式\n\n当需要使用工具时，请在回复中使用以下XML格式：\n\n<tool_call name=\"工具名\">\n{\"param1\": \"value1\", \"param2\": \"value2\"}\n</tool_call]\n\n你可以同时调用多个工具。调用工具后，系统会返回结果，你可以基于结果继续回答。\n如果不需要使用工具，直接回复用户即可。\n"

    return base_prompt + tools_section


def _parse_tool_calls(content: str) -> list[dict]:
    import re
    pattern = r'<tool_call\s+name="([^"]+)">\s*(.*?)\s*</tool_call'
    matches = re.findall(pattern, content, re.DOTALL)
    results = []
    for name, args_str in matches:
        try:
            import json
            args = json.loads(args_str) if args_str.strip() else {}
        except json.JSONDecodeError:
            args = {"raw_input": args_str}
        results.append({"name": name, "arguments": args})
    return results


async def _execute_tool_calls(tool_calls: list[dict], agent_id: str | None = None) -> list[dict]:
    results = []
    for call in tool_calls:
        try:
            result = await _skill_executor.execute(
                skill_name=call["name"],
                arguments=call["arguments"],
                agent_id=agent_id,
            )
            results.append({
                "tool": call["name"],
                "result": result,
                "status": "success",
            })
        except Exception as e:
            results.append({
                "tool": call["name"],
                "result": str(e),
                "status": "error",
            })
    return results


@router.post("/completions")
async def chat_completions(request: ChatRequest):
    start_time = time.time()
    resolved_provider = request.provider or llm_adapter.default_provider
    resolved_model = request.model or llm_adapter.get_provider(resolved_provider).default_model
    logger.info(f"[API] POST /chat/completions - provider={resolved_provider}, model={resolved_model}, stream={request.stream}")

    system_prompt = _build_system_prompt_with_tools(request.agent_id)
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.extend([{"role": m.role, "content": m.content} for m in request.messages])
    logger.debug(f"[API] POST /chat/completions - Message count: {len(messages)}")

    if request.stream:
        logger.info(f"[API] POST /chat/completions - Starting stream response")
        return StreamingResponse(
            _stream_chat(messages, request, resolved_provider, resolved_model),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    try:
        result = await llm_adapter.chat(
            messages=messages,
            provider_name=resolved_provider,
            model=resolved_model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_p=request.top_p,
            tools=request.tools,
        )

        tool_calls = _parse_tool_calls(result)
        if tool_calls:
            tool_results = await _execute_tool_calls(tool_calls, request.agent_id)
            tool_result_text = "\n\n".join(
                f"[Tool: {r['tool']}] {r['result']}" for r in tool_results
            )
            messages.append({"role": "assistant", "content": result})
            messages.append({"role": "user", "content": f"工具执行结果：\n{tool_result_text}\n\n请基于以上工具结果回答用户的问题。"})

            result = await llm_adapter.chat(
                messages=messages,
                provider_name=resolved_provider,
                model=resolved_model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                top_p=request.top_p,
            )

        elapsed = time.time() - start_time
        logger.success(f"[API] POST /chat/completions - Success: elapsed={elapsed:.2f}s, response_len={len(result)}")
        return ChatResponse(
            id=str(uuid.uuid4()),
            content=result,
            model=resolved_model,
            provider=resolved_provider,
        )
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[API] POST /chat/completions - Failed: elapsed={elapsed:.2f}s, error={e}")
        raise


async def _stream_chat(messages: list[dict], request: ChatRequest, provider: str, model: str):
    start_time = time.time()
    chat_id = str(uuid.uuid4())
    chunk_count = 0
    full_content = ""

    logger.info(f"[STREAM] Starting stream: chat_id={chat_id}, provider={provider}, model={model}")

    try:
        async for chunk in llm_adapter.chat_stream(
            messages=messages,
            provider_name=provider,
            model=model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_p=request.top_p,
            tools=request.tools,
        ):
            full_content += chunk
            chunk_count += 1
            data = ChatStreamChunk(
                id=chat_id,
                content=chunk,
                model=model,
                provider=provider,
            )
            yield f"data: {data.model_dump_json()}\n\n"

        tool_calls = _parse_tool_calls(full_content)
        if tool_calls:
            tool_results = await _execute_tool_calls(tool_calls, request.agent_id)
            for tr in tool_results:
                result_chunk = ChatStreamChunk(
                    id=chat_id,
                    content=f"\n\n[Tool: {tr['tool']}] {tr['result']}\n\n",
                    model=model,
                    provider=provider,
                )
                yield f"data: {result_chunk.model_dump_json()}\n\n"

        done_data = ChatStreamChunk(
            id=chat_id,
            content="",
            model=model,
            provider=provider,
            done=True,
        )
        yield f"data: {done_data.model_dump_json()}\n\n"
        elapsed = time.time() - start_time
        logger.success(f"[STREAM] Stream completed: chat_id={chat_id}, chunks={chunk_count}, elapsed={elapsed:.2f}s")
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[STREAM] Stream failed: chat_id={chat_id}, elapsed={elapsed:.2f}s, error={e}")
        error_data = ChatStreamChunk(
            id=chat_id,
            content=f"[Error] {str(e)}",
            model=model,
            provider=provider,
            done=True,
        )
        yield f"data: {error_data.model_dump_json()}\n\n"


@router.get("/conversations", response_model=list[ConversationListResponse])
async def list_conversations(agent_id: str | None = None):
    logger.info(f"[API] GET /chat/conversations - Listing conversations, agent_id={agent_id}")
    result = []
    for conv_id, conv in conversations_store.items():
        if agent_id and conv.get("agent_id") != agent_id:
            continue
        messages = conv.get("messages", [])
        last_msg = messages[-1]["content"][:50] if messages else None
        result.append(ConversationListResponse(
            id=conv_id,
            title=conv.get("title", "New Conversation"),
            agent_id=conv.get("agent_id"),
            model=conv.get("model"),
            provider=conv.get("provider"),
            last_message=last_msg,
            created_at=conv.get("created_at", ""),
            updated_at=conv.get("updated_at", ""),
        ))
    result.sort(key=lambda x: x.updated_at, reverse=True)
    logger.success(f"[API] GET /chat/conversations - Success: returned {len(result)} conversations")
    return result


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(request: ConversationCreate):
    logger.info(f"[API] POST /chat/conversations - Creating conversation: title={request.title}, agent_id={request.agent_id}")
    conv_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conv = {
        "id": conv_id,
        "title": request.title or "New Conversation",
        "agent_id": request.agent_id,
        "model": request.model,
        "provider": request.provider,
        "messages": [],
        "created_at": now,
        "updated_at": now,
    }
    conversations_store.set(conv_id, conv)
    logger.success(f"[API] POST /chat/conversations - Conversation created: id={conv_id}")
    return ConversationResponse(**conv)


@router.get("/conversations/{conv_id}", response_model=ConversationResponse)
async def get_conversation(conv_id: str):
    logger.info(f"[API] GET /chat/conversations/{conv_id} - Fetching conversation")
    conv = conversations_store.get(conv_id)
    if not conv:
        logger.error(f"[API] GET /chat/conversations/{conv_id} - Conversation not found")
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Conversation {conv_id} not found")
    logger.success(f"[API] GET /chat/conversations/{conv_id} - Success: title={conv['title']}, messages={len(conv.get('messages', []))}")
    return ConversationResponse(**conv)


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    logger.info(f"[API] DELETE /chat/conversations/{conv_id} - Deleting conversation")
    conv = conversations_store.get(conv_id)
    if conv:
        conv_title = conv.get("title", "unknown")
        conversations_store.delete(conv_id)
        logger.success(f"[API] DELETE /chat/conversations/{conv_id} - Conversation deleted: title={conv_title}")
    else:
        logger.warning(f"[API] DELETE /chat/conversations/{conv_id} - Conversation not found")
    return {"error": None, "data": {"deleted": True}}


@router.post("/conversations/{conv_id}/messages")
async def add_message(conv_id: str, request: ChatRequest):
    start_time = time.time()
    logger.info(f"[API] POST /chat/conversations/{conv_id}/messages - Adding message")
    conv = conversations_store.get(conv_id)
    if not conv:
        logger.error(f"[API] POST /chat/conversations/{conv_id}/messages - Conversation not found")
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Conversation {conv_id} not found")

    existing_count = len(conv["messages"])
    for m in request.messages:
        msg_entry = {"role": m.role, "content": m.content}
        if conv["messages"] and conv["messages"][-1] == msg_entry:
            continue
        conv["messages"].append(msg_entry)
    new_msg_count = len(conv["messages"]) - existing_count
    conv["updated_at"] = datetime.now(timezone.utc).isoformat()
    logger.debug(f"[API] POST /chat/conversations/{conv_id}/messages - Added {new_msg_count} new messages")

    resolved_provider = request.provider or conv.get("provider") or llm_adapter.default_provider
    resolved_model = request.model or conv.get("model") or llm_adapter.get_provider(resolved_provider).default_model

    system_prompt = _build_system_prompt_with_tools(conv.get("agent_id"))
    all_messages = []
    if system_prompt:
        all_messages.append({"role": "system", "content": system_prompt})
    all_messages.extend([{"role": m["role"], "content": m["content"]} for m in conv["messages"]])

    if request.stream:
        logger.info(f"[API] POST /chat/conversations/{conv_id}/messages - Starting stream response")

        async def stream_with_save():
            accumulated = ""
            chat_id = str(uuid.uuid4())
            chunk_count = 0
            try:
                async for chunk in llm_adapter.chat_stream(
                    messages=all_messages,
                    provider_name=resolved_provider,
                    model=resolved_model,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    top_p=request.top_p,
                    tools=request.tools,
                ):
                    accumulated += chunk
                    chunk_count += 1
                    data = ChatStreamChunk(
                        id=chat_id,
                        content=chunk,
                        model=resolved_model,
                        provider=resolved_provider,
                    )
                    yield f"data: {data.model_dump_json()}\n\n"

                tool_calls = _parse_tool_calls(accumulated)
                if tool_calls:
                    tool_results = await _execute_tool_calls(tool_calls, conv.get("agent_id"))
                    for tr in tool_results:
                        result_chunk = ChatStreamChunk(
                            id=chat_id,
                            content=f"\n\n[Tool: {tr['tool']}] {tr['result']}\n\n",
                            model=resolved_model,
                            provider=resolved_provider,
                        )
                        yield f"data: {result_chunk.model_dump_json()}\n\n"
                        accumulated += f"\n\n[Tool: {tr['tool']}] {tr['result']}\n\n"

                done_data = ChatStreamChunk(
                    id=chat_id,
                    content="",
                    model=resolved_model,
                    provider=resolved_provider,
                    done=True,
                )
                yield f"data: {done_data.model_dump_json()}\n\n"

                conv["messages"].append({"role": "assistant", "content": accumulated})
                conv["updated_at"] = datetime.now(timezone.utc).isoformat()
                conversations_store.set(conv_id, conv)
                elapsed = time.time() - start_time
                logger.success(f"[STREAM] Stream completed & saved: conv={conv_id}, chunks={chunk_count}, elapsed={elapsed:.2f}s")
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"[STREAM] Stream failed: conv={conv_id}, elapsed={elapsed:.2f}s, error={e}")
                error_data = ChatStreamChunk(
                    id=chat_id,
                    content=f"[Error] {str(e)}",
                    model=resolved_model,
                    provider=resolved_provider,
                    done=True,
                )
                yield f"data: {error_data.model_dump_json()}\n\n"

        return StreamingResponse(
            stream_with_save(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    result = await llm_adapter.chat(
        messages=all_messages,
        provider_name=resolved_provider,
        model=resolved_model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        top_p=request.top_p,
        tools=request.tools,
    )

    tool_calls = _parse_tool_calls(result)
    if tool_calls:
        tool_results = await _execute_tool_calls(tool_calls, conv.get("agent_id"))
        tool_result_text = "\n\n".join(
            f"[Tool: {r['tool']}] {r['result']}" for r in tool_results
        )
        all_messages.append({"role": "assistant", "content": result})
        all_messages.append({"role": "user", "content": f"工具执行结果：\n{tool_result_text}\n\n请基于以上工具结果回答用户的问题。"})

        result = await llm_adapter.chat(
            messages=all_messages,
            provider_name=resolved_provider,
            model=resolved_model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_p=request.top_p,
        )

    conv["messages"].append({"role": "assistant", "content": result})
    conv["updated_at"] = datetime.now(timezone.utc).isoformat()
    conversations_store.set(conv_id, conv)

    elapsed = time.time() - start_time
    logger.success(f"[API] POST /chat/conversations/{conv_id}/messages - Success: elapsed={elapsed:.2f}s, response_len={len(result)}")

    return ChatResponse(
        id=str(uuid.uuid4()),
        content=result,
        model=resolved_model,
        provider=resolved_provider,
    )
