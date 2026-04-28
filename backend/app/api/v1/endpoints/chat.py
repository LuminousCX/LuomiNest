import asyncio
import json
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
    ToolCallResult,
)
from app.runtime.provider.llm.adapter import llm_adapter
from app.runtime.provider.llm.providers import LLMResponse
from app.infrastructure.database.json_store import conversations_store, agents_store
from app.runtime.plugin.skill.executor import SkillExecutor
from app.runtime.plugin.skill.registry import SkillRegistry
from app.engines.memory.core import (
    get_memory_storage,
    MemoryUpdater,
    MemoryInjector,
)
from app.core.config import settings

router = APIRouter(prefix="/chat", tags=["chat"])

_skill_executor = SkillExecutor()

MAX_TOOL_LOOP_ROUNDS = 5


def _get_timestamp() -> float:
    return time.time()


def _inject_memory_to_messages(messages: list[dict], agent_id: str | None) -> list[dict]:
    try:
        storage = get_memory_storage()
        global_memory = storage.load(None)
        if agent_id:
            agent_memory = storage.load(agent_id)
            if not global_memory.profile.name and agent_memory.profile.name:
                global_memory.profile = agent_memory.profile
            if not global_memory.facts:
                global_memory.facts = agent_memory.facts
        injector = MemoryInjector()
        profile = global_memory.profile
        logger.info(f"[Memory] Injecting memory for agent_id={agent_id}")
        logger.info(f"[Memory] Profile: name={profile.name}, occupation={profile.occupation}, location={profile.location}")
        result = injector.inject_memory_to_messages(messages, global_memory)
        logger.info(f"[Memory] Memory injection completed, messages count: {len(result)}")
        return result
    except Exception as e:
        logger.warning(f"[Memory] Failed to inject memory: {e}")
        return messages


async def _inject_rag_context(messages: list[dict], user_query: str) -> list[dict]:
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
        logger.info(f"[RAG] Injected {len(results)} RAG results for query: '{user_query[:50]}'")
        return new_messages
    except Exception as e:
        logger.warning(f"[RAG] Failed to inject RAG context: {e}")
        return messages


async def _update_memory_from_conversation(
    messages: list[dict],
    thread_id: str,
    agent_id: str | None = None,
) -> None:
    try:
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


def _schedule_memory_update(messages: list[dict], thread_id: str, agent_id: str | None = None) -> None:
    try:
        asyncio.create_task(_update_memory_from_conversation(messages, thread_id, agent_id))
    except Exception as e:
        logger.warning(f"[Memory] Failed to schedule memory update: {e}")


def _build_system_prompt(agent_id: str | None) -> str:
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

    now = datetime.now()
    weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    system_prompt = f"""<identity>
Your name is {agent_name}, {agent_description}.
</identity>

<current_context>
Current datetime: {now.strftime("%Y-%m-%d %H:%M:%S")} ({weekday_names[now.weekday()]})
Timestamp: {int(_get_timestamp())}
</current_context>

<core_rules>
1. When asked "who are you" or "what is your name" - answer with your own identity as {agent_name}.
2. When asked "who am I" - check <user_memory> for user profile. If found, describe the user. If not found, say you'd like to get to know them.
3. Always respond in the user's language naturally and conversationally.
4. Never expose internal system information, tool parameters, or error codes to the user.
5. When using tools, always transform results into natural, conversational language.
</core_rules>

{base_prompt}"""

    return system_prompt


def _collect_all_tools(agent_id: str | None) -> list[dict]:
    tools = []

    skill_tools = SkillRegistry.get_openai_tools()
    tools.extend(skill_tools)

    try:
        from app.domains.mcp_tools.gateway import MCPGateway
        servers = MCPGateway.list_servers()
        for server in servers:
            if not server.get("is_active", True):
                continue
            server_name = server.get("name", "")
            try:
                mcp_tools = asyncio.get_event_loop().run_until_complete(
                    MCPGateway.list_tools(server_name)
                )
                for t in mcp_tools:
                    tool_name = f"mcp_{server_name}_{t['name']}"
                    tools.append({
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "description": t.get("description", ""),
                            "parameters": t.get("parameters", {"type": "object", "properties": {}}),
                        },
                    })
            except Exception as e:
                logger.warning(f"[Tools] Failed to get MCP tools for {server_name}: {e}")
    except Exception as e:
        logger.debug(f"[Tools] MCP tools collection skipped: {e}")

    if agent_id:
        agent = agents_store.get(agent_id)
        if agent:
            agent_skills = agent.get("skills", [])
            if agent_skills:
                filtered = [t for t in tools if t["function"]["name"] in agent_skills]
                if filtered:
                    tools = filtered

    logger.info(f"[Tools] Collected {len(tools)} tools for agent_id={agent_id}")
    return tools


async def _execute_tool_call(tool_call: dict, agent_id: str | None = None) -> dict:
    tool_name = tool_call["function"]["name"]
    tool_call_id = tool_call.get("id", "")
    arguments_str = tool_call["function"].get("arguments", "{}")

    try:
        arguments = json.loads(arguments_str) if arguments_str else {}
    except json.JSONDecodeError:
        arguments = {"raw_input": arguments_str}

    logger.info(f"[ToolExec] Executing tool: {tool_name}, call_id={tool_call_id}")

    if tool_name.startswith("mcp_"):
        parts = tool_name.split("_", 2)
        if len(parts) >= 3:
            server_name = parts[1]
            actual_tool_name = parts[2]
            try:
                from app.domains.mcp_tools.tool_executor import MCPToolExecutor
                mcp_executor = MCPToolExecutor()
                result = await mcp_executor.execute(
                    server_name=server_name,
                    tool_name=actual_tool_name,
                    arguments=arguments,
                )
                return {
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "result": str(result),
                    "status": "success",
                }
            except Exception as e:
                logger.error(f"[ToolExec] MCP tool error: {tool_name}, error: {e}")
                return {
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "result": f"Tool execution error: {e}",
                    "status": "error",
                }

    try:
        skill_data = SkillRegistry.get_skill(tool_name)
        if not skill_data or not skill_data.get("is_active", True):
            return {
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "result": "This tool is currently unavailable. Please try a different approach.",
                "status": "error",
            }

        result = await _skill_executor.execute(
            skill_name=tool_name,
            arguments=arguments,
            agent_id=agent_id,
        )
        return {
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "result": str(result),
            "status": "success",
        }
    except Exception as e:
        logger.error(f"[ToolExec] Tool execution failed: {tool_name}, error: {e}", exc_info=True)
        error_msg = (
            f"Tool execution error: {str(e)}"
            if settings.DEBUG
            else "Tool execution encountered an issue. Please try again or use a different approach."
        )
        return {
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "result": error_msg,
            "status": "error",
        }


async def _execute_tool_calls(tool_calls: list[dict], agent_id: str | None = None) -> list[dict]:
    results = []
    for call in tool_calls:
        result = await _execute_tool_call(call, agent_id)
        results.append(result)
    return results


def _build_tool_result_messages(
    assistant_content: str | None,
    tool_calls: list[dict],
    tool_results: list[dict],
) -> list[dict]:
    messages = []
    assistant_msg = {"role": "assistant", "content": assistant_content or ""}
    if tool_calls:
        assistant_msg["tool_calls"] = tool_calls
    messages.append(assistant_msg)

    for result in tool_results:
        messages.append({
            "role": "tool",
            "content": result["result"],
            "tool_call_id": result["tool_call_id"],
            "name": result["tool_name"],
        })

    return messages


async def _run_agent_loop(
    messages: list[dict],
    tools: list[dict],
    provider: str,
    model: str,
    agent_id: str | None,
    temperature: float | None,
    max_tokens: int | None,
    top_p: float | None,
) -> LLMResponse:
    current_messages = list(messages)
    all_tool_results = []
    all_tool_calls_info = []

    for round_num in range(MAX_TOOL_LOOP_ROUNDS):
        logger.info(f"[AgentLoop] Round {round_num + 1}/{MAX_TOOL_LOOP_ROUNDS}")

        llm_response = await llm_adapter.chat(
            messages=current_messages,
            tools=tools if round_num == 0 else tools,
            provider_name=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )

        if not llm_response.has_tool_calls():
            if all_tool_results:
                llm_response.tool_results = all_tool_results
            return llm_response

        logger.info(f"[AgentLoop] LLM requested {len(llm_response.tool_calls)} tool calls")

        tool_results = await _execute_tool_calls(llm_response.tool_calls, agent_id)
        all_tool_results.extend(tool_results)
        all_tool_calls_info.extend(llm_response.tool_calls)

        tool_messages = _build_tool_result_messages(
            llm_response.content,
            llm_response.tool_calls,
            tool_results,
        )
        current_messages.extend(tool_messages)

    final_response = await llm_adapter.chat(
        messages=current_messages,
        tools=None,
        provider_name=provider,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
    )
    final_response.tool_results = all_tool_results
    return final_response


@router.post("/completions")
async def chat_completions(request: ChatRequest):
    start_time = time.time()
    resolved_provider = request.provider or llm_adapter.default_provider
    resolved_model = request.model or llm_adapter.get_provider(resolved_provider).default_model
    request_ts = request.timestamp or _get_timestamp()
    logger.info(f"[API] POST /chat/completions - provider={resolved_provider}, model={resolved_model}, stream={request.stream}, ts={request_ts}")

    system_prompt = _build_system_prompt(request.agent_id)
    messages = [{"role": "system", "content": system_prompt}]

    for m in request.messages:
        if m.role == "system":
            continue
        msg_dict = {"role": m.role, "content": m.content}
        if m.tool_calls:
            msg_dict["tool_calls"] = m.tool_calls
        if m.tool_call_id:
            msg_dict["tool_call_id"] = m.tool_call_id
        if m.name:
            msg_dict["name"] = m.name
        messages.append(msg_dict)

    messages = _inject_memory_to_messages(messages, request.agent_id)

    user_query = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            content = m.get("content", "")
            user_query = content if isinstance(content, str) else str(content)
            break
    if user_query:
        messages = await _inject_rag_context(messages, user_query)

    tools = _collect_all_tools(request.agent_id)
    if not tools:
        tools = None

    if request.stream:
        logger.info(f"[API] POST /chat/completions - Starting stream response")
        return StreamingResponse(
            _stream_chat(messages, tools, request, resolved_provider, resolved_model, request.agent_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    try:
        result = await _run_agent_loop(
            messages=messages,
            tools=tools,
            provider=resolved_provider,
            model=resolved_model,
            agent_id=request.agent_id,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_p=request.top_p,
        )

        thread_id = str(uuid.uuid4())
        conversation_messages = [
            {"role": m.role, "content": m.content if isinstance(m.content, str) else str(m.content)}
            for m in request.messages
        ] + [{"role": "assistant", "content": result.content}]
        _schedule_memory_update(conversation_messages, thread_id, request.agent_id)

        elapsed = time.time() - start_time
        logger.success(f"[API] POST /chat/completions - Success: elapsed={elapsed:.2f}s, response_len={len(result.content)}")

        tool_calls_data = None
        if result.tool_calls:
            tool_calls_data = [
                {
                    "id": tc["id"],
                    "type": tc.get("type", "function"),
                    "function": tc["function"],
                }
                for tc in result.tool_calls
            ]

        tool_results_data = None
        if result.tool_results:
            tool_results_data = [
                {"tool_call_id": r["tool_call_id"], "tool_name": r["tool_name"], "result": r["result"], "status": r["status"]}
                for r in result.tool_results
            ]

        return ChatResponse(
            id=str(uuid.uuid4()),
            content=result.content,
            model=resolved_model,
            provider=resolved_provider,
            tool_calls=tool_calls_data,
            tool_results=tool_results_data,
            usage=result.usage,
            timestamp=_get_timestamp(),
        )
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[API] POST /chat/completions - Failed: elapsed={elapsed:.2f}s, error={e}")
        raise


async def _stream_chat(
    messages: list[dict],
    tools: list[dict] | None,
    request: ChatRequest,
    provider: str,
    model: str,
    agent_id: str | None,
):
    start_time = time.time()
    chat_id = str(uuid.uuid4())
    chunk_count = 0

    logger.info(f"[STREAM] Starting stream: chat_id={chat_id}, provider={provider}, model={model}")

    try:
        current_messages = list(messages)
        all_tool_results = []
        all_tool_calls_info = []

        for round_num in range(MAX_TOOL_LOOP_ROUNDS):
            tool_calls_map: dict[int, dict] = {}
            content_parts = []

            async for event in llm_adapter.chat_stream(
                messages=current_messages,
                tools=tools,
                provider_name=provider,
                model=model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                top_p=request.top_p,
            ):
                if event.type == "content":
                    content_parts.append(event.data.get("content", ""))
                    chunk_count += 1
                    data = ChatStreamChunk(
                        id=chat_id,
                        content=event.data.get("content", ""),
                        model=model,
                        provider=provider,
                        timestamp=_get_timestamp(),
                    )
                    yield f"data: {data.model_dump_json()}\n\n"

                elif event.type == "tool_call_delta":
                    idx = event.data.get("index", 0)
                    if idx not in tool_calls_map:
                        tool_calls_map[idx] = {
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }
                    tc = tool_calls_map[idx]
                    if event.data.get("tool_call_id"):
                        tc["id"] = event.data["tool_call_id"]
                    fn = tc["function"]
                    if event.data.get("function_name"):
                        fn["name"] += event.data["function_name"]
                    if event.data.get("function_arguments"):
                        fn["arguments"] += event.data["function_arguments"]

                elif event.type == "usage":
                    pass

                elif event.type == "done":
                    break

            accumulated_content = "".join(content_parts)
            tool_calls_list = list(tool_calls_map.values()) if tool_calls_map else None

            if not tool_calls_list:
                final_answer = accumulated_content
                break

            logger.info(f"[STREAM] Round {round_num + 1}: LLM requested {len(tool_calls_list)} tool calls")

            tool_results = await _execute_tool_calls(tool_calls_list, agent_id)
            all_tool_results.extend(tool_results)
            all_tool_calls_info.extend(tool_calls_list)

            for r in tool_results:
                tr_data = ChatStreamChunk(
                    id=chat_id,
                    content="",
                    model=model,
                    provider=provider,
                    tool_results=[ToolCallResult(
                        tool_call_id=r["tool_call_id"],
                        tool_name=r["tool_name"],
                        result=r["result"],
                        status=r["status"],
                    )],
                    timestamp=_get_timestamp(),
                )
                yield f"data: {tr_data.model_dump_json()}\n\n"

            tool_messages = _build_tool_result_messages(
                accumulated_content,
                tool_calls_list,
                tool_results,
            )
            current_messages.extend(tool_messages)
        else:
            final_answer = accumulated_content

        done_data = ChatStreamChunk(
            id=chat_id,
            content="",
            model=model,
            provider=provider,
            done=True,
            timestamp=_get_timestamp(),
        )
        if all_tool_results:
            done_data.tool_results = [
                ToolCallResult(
                    tool_call_id=r["tool_call_id"],
                    tool_name=r["tool_name"],
                    result=r["result"],
                    status=r["status"],
                )
                for r in all_tool_results
            ]
        yield f"data: {done_data.model_dump_json()}\n\n"

        conversation_messages = [
            {"role": m.role, "content": m.content if isinstance(m.content, str) else str(m.content)}
            for m in request.messages
        ] + [{"role": "assistant", "content": final_answer}]
        _schedule_memory_update(conversation_messages, chat_id, agent_id)

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
            timestamp=_get_timestamp(),
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
    request_ts = request.timestamp or _get_timestamp()
    logger.info(f"[API] POST /chat/conversations/{conv_id}/messages - Adding message, ts={request_ts}")
    conv = conversations_store.get(conv_id)
    if not conv:
        logger.error(f"[API] POST /chat/conversations/{conv_id}/messages - Conversation not found")
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Conversation {conv_id} not found")

    last_user_msg = None
    for m in reversed(request.messages):
        if m.role == "user":
            last_user_msg = m
            break

    if last_user_msg:
        msg_entry = {"role": "user", "content": last_user_msg.content, "timestamp": request_ts}
        if not conv["messages"] or conv["messages"][-1] != msg_entry:
            conv["messages"].append(msg_entry)

    conv["updated_at"] = datetime.now(timezone.utc).isoformat()

    resolved_provider = request.provider or conv.get("provider") or llm_adapter.default_provider
    resolved_model = request.model or conv.get("model") or llm_adapter.get_provider(resolved_provider).default_model

    system_prompt = _build_system_prompt(conv.get("agent_id"))
    all_messages = [{"role": "system", "content": system_prompt}]

    for m in conv["messages"]:
        all_messages.append({"role": m["role"], "content": m["content"]})

    all_messages = _inject_memory_to_messages(all_messages, conv.get("agent_id"))

    user_query = ""
    for m in reversed(all_messages):
        if m.get("role") == "user":
            content = m.get("content", "")
            user_query = content if isinstance(content, str) else str(content)
            break
    if user_query:
        all_messages = await _inject_rag_context(all_messages, user_query)

    tools = _collect_all_tools(conv.get("agent_id"))
    if not tools:
        tools = None

    if request.stream:
        logger.info(f"[API] POST /chat/conversations/{conv_id}/messages - Starting stream response")

        async def stream_with_save():
            chat_id = str(uuid.uuid4())
            chunk_count = 0
            current_messages = list(all_messages)
            all_tool_results = []

            try:
                for round_num in range(MAX_TOOL_LOOP_ROUNDS):
                    tool_calls_map: dict[int, dict] = {}
                    content_parts = []

                    async for event in llm_adapter.chat_stream(
                        messages=current_messages,
                        tools=tools,
                        provider_name=resolved_provider,
                        model=resolved_model,
                        temperature=request.temperature,
                        max_tokens=request.max_tokens,
                        top_p=request.top_p,
                    ):
                        if event.type == "content":
                            content_parts.append(event.data.get("content", ""))
                            chunk_count += 1
                            data = ChatStreamChunk(
                                id=chat_id,
                                content=event.data.get("content", ""),
                                model=resolved_model,
                                provider=resolved_provider,
                                timestamp=_get_timestamp(),
                            )
                            yield f"data: {data.model_dump_json()}\n\n"

                        elif event.type == "tool_call_delta":
                            idx = event.data.get("index", 0)
                            if idx not in tool_calls_map:
                                tool_calls_map[idx] = {
                                    "id": "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
                            tc = tool_calls_map[idx]
                            if event.data.get("tool_call_id"):
                                tc["id"] = event.data["tool_call_id"]
                            fn = tc["function"]
                            if event.data.get("function_name"):
                                fn["name"] += event.data["function_name"]
                            if event.data.get("function_arguments"):
                                fn["arguments"] += event.data["function_arguments"]

                        elif event.type == "done":
                            break

                accumulated_content = "".join(content_parts)
                tool_calls_list = list(tool_calls_map.values()) if tool_calls_map else None

                if tool_calls_list:
                    logger.info(f"[STREAM] Round {round_num + 1}: LLM requested {len(tool_calls_list)} tool calls")
                    tool_results = await _execute_tool_calls(tool_calls_list, conv.get("agent_id"))
                    all_tool_results.extend(tool_results)

                    for r in tool_results:
                        tr_data = ChatStreamChunk(
                            id=chat_id,
                            content="",
                            model=resolved_model,
                            provider=resolved_provider,
                            tool_results=[ToolCallResult(
                                tool_call_id=r["tool_call_id"],
                                tool_name=r["tool_name"],
                                result=r["result"],
                                status=r["status"],
                            )],
                            timestamp=_get_timestamp(),
                        )
                        yield f"data: {tr_data.model_dump_json()}\n\n"

                    tool_messages = _build_tool_result_messages(
                        accumulated_content,
                        tool_calls_list,
                        tool_results,
                    )
                    current_messages.extend(tool_messages)

                    final_response = await llm_adapter.chat(
                        messages=current_messages,
                        tools=None,
                        provider_name=resolved_provider,
                        model=resolved_model,
                        temperature=request.temperature,
                        max_tokens=request.max_tokens,
                        top_p=request.top_p,
                    )
                    final_answer = final_response.content
                    for i in range(0, len(final_answer), 10):
                        chunk = final_answer[i:i+10]
                        data = ChatStreamChunk(
                            id=chat_id,
                            content=chunk,
                            model=resolved_model,
                            provider=resolved_provider,
                            timestamp=_get_timestamp(),
                        )
                        yield f"data: {data.model_dump_json()}\n\n"
                else:
                    final_answer = accumulated_content

                done_data = ChatStreamChunk(
                    id=chat_id,
                    content="",
                    model=resolved_model,
                    provider=resolved_provider,
                    done=True,
                    timestamp=_get_timestamp(),
                )
                if all_tool_results:
                    done_data.tool_results = [
                        ToolCallResult(
                            tool_call_id=r["tool_call_id"],
                            tool_name=r["tool_name"],
                            result=r["result"],
                            status=r["status"],
                        )
                        for r in all_tool_results
                    ]
                yield f"data: {done_data.model_dump_json()}\n\n"

                assistant_msg = {"role": "assistant", "content": final_answer}
                if not conv["messages"] or conv["messages"][-1] != assistant_msg:
                    conv["messages"].append(assistant_msg)
                    conv["updated_at"] = datetime.now(timezone.utc).isoformat()
                    conversations_store.set(conv_id, conv)

                _schedule_memory_update(
                    conv["messages"],
                    conv_id,
                    conv.get("agent_id"),
                )

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
                    timestamp=_get_timestamp(),
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

    result = await _run_agent_loop(
        messages=all_messages,
        tools=tools,
        provider=resolved_provider,
        model=resolved_model,
        agent_id=conv.get("agent_id"),
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        top_p=request.top_p,
    )

    assistant_msg = {"role": "assistant", "content": result.content}
    if not conv["messages"] or conv["messages"][-1] != assistant_msg:
        conv["messages"].append(assistant_msg)
        conv["updated_at"] = datetime.now(timezone.utc).isoformat()
        conversations_store.set(conv_id, conv)

    _schedule_memory_update(
        conv["messages"],
        conv_id,
        conv.get("agent_id"),
    )

    elapsed = time.time() - start_time
    logger.success(f"[API] POST /chat/conversations/{conv_id}/messages - Success: elapsed={elapsed:.2f}s, response_len={len(result.content)}")

    tool_calls_data = None
    if result.tool_calls:
        tool_calls_data = [
            {
                "id": tc["id"],
                "type": tc.get("type", "function"),
                "function": tc["function"],
            }
            for tc in result.tool_calls
        ]

    tool_results_data = None
    if result.tool_results:
        tool_results_data = [
            {"tool_call_id": r["tool_call_id"], "tool_name": r["tool_name"], "result": r["result"], "status": r["status"]}
            for r in result.tool_results
        ]

    return ChatResponse(
        id=str(uuid.uuid4()),
        content=result.content,
        model=resolved_model,
        provider=resolved_provider,
        tool_calls=tool_calls_data,
        tool_results=tool_results_data,
        usage=result.usage,
        timestamp=_get_timestamp(),
    )
