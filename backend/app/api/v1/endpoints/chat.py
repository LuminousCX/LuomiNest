import asyncio
import json
import uuid
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from collections.abc import AsyncIterator
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
from app.infrastructure.database.json_store import agents_store
from app.infrastructure.database.conversation_store import conversation_store
from app.core.config import settings
from app.utils.intent_gateway import classify_request, RequestType
from app.utils.tool_lazy_loader import get_matched_tools
from app.utils.tool_result_processor import process_tool_result
from app.utils.local_handler import handle_local_tool_request
from app.utils.tool_executor import execute_tool_chain, build_tool_summary, execute_single_tool
from app.core.context import get_context_manager

router = APIRouter(prefix="/chat", tags=["chat"])

_memory_locks: dict[str | None, asyncio.Lock] = {}
_memory_locks_guard = asyncio.Lock()
_llm_semaphore = asyncio.Semaphore(1)

MAX_TOOL_LOOP_ROUNDS = 5
TOOL_EXECUTION_TIMEOUT = 60
MAX_TOOL_RESULT_CHARS = 50_000
SSE_HEARTBEAT_INTERVAL = 15

async def _get_memory_lock(agent_id: str | None) -> asyncio.Lock:
    if agent_id in _memory_locks:
        return _memory_locks[agent_id]
    async with _memory_locks_guard:
        if agent_id not in _memory_locks:
            _memory_locks[agent_id] = asyncio.Lock()
        return _memory_locks[agent_id]

_loop_detection: dict[str, list[str]] = {}
LOOP_DETECTION_MAX_HISTORY = 20
LOOP_DETECTION_HARD_LIMIT = 5


def _get_timestamp() -> float:
    return time.time()

def _resolve_tools(user_message: str, request_type: RequestType) -> list[dict] | None:
    """按需解析工具定义 —— 仅 TOOL_CALL 类型才注入匹配场景的工具

    GENERAL_CHAT 和 LOCAL_TOOL 请求绝不注入任何工具，从根源杜绝工具乱触发。

    异常安全：
        懒加载异常时返回空列表 []（不注入任何工具），避免全量注入导致工具乱触发。
        GENERAL_CHAT 和 LOCAL_TOOL 请求始终返回 None。

    参数:
        user_message: 用户原始消息文本
        request_type: classify_request 返回的请求类型

    返回:
        - TOOL_CALL 且命中场景：OpenAI Function Calling 格式工具列表
        - TOOL_CALL 但无匹配场景：空列表 []（等效不注入工具）
        - 其他类型：None（不注入工具）
        - 异常：空列表 []（安全降级，不注入工具）
    """
    if request_type != RequestType.TOOL_CALL:
        return None

    try:
        tools = get_matched_tools(user_message)
        return tools if tools else []
    except Exception as e:
        logger.warning(f"[Chat] 工具懒加载异常，降级返回空列表（不注入工具）: {e}")
        return []


def _inject_system_prompt(messages: list[dict]) -> list[dict]:
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    weekday_names = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
    current_date = now.strftime("%Y年%m月%d日")
    current_weekday = weekday_names[now.weekday()]
    current_time = now.strftime("%H:%M")
    date_prompt = f"当前时间：{current_date} {current_weekday} {current_time} (Asia/Shanghai)。请基于这个时间回答用户的问题。当用户问「距离XX还有几天」时，你需要先用工具查询目标日期，然后用当前时间计算差值。"

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


def _inject_file_content(messages: list[dict], parsed_content: str, file_type: str = "text") -> list[dict]:
    if not parsed_content or not parsed_content.strip():
        return messages

    # 根据文件类型判断是否是图片
    is_image = file_type == "image" or parsed_content.startswith("data:image")
    
    if is_image:
        # 找到最后一条用户消息，将图片内容附加到该消息
        for i in range(len(messages) - 1, -1, -1):
            if messages[i]["role"] == "user":
                # 提取文字内容和图片
                text_content = messages[i]["content"]
                # 移除 [图片附件] 标记后的内容
                if "[图片附件]" in text_content:
                    text_content = text_content.split("[图片附件]")[0].strip()

                # 构建多模态消息格式
                messages[i]["content"] = [
                    {"type": "text", "text": text_content or "请分析这张图片"},
                    {"type": "image_url", "image_url": {"url": parsed_content}},
                ]
                return messages
        return messages

    # 普通文本内容
    context_text = (
        "[用户上传文件内容] 以下是与当前对话相关的文件内容，请参考这些内容回答用户的问题。"
        "如果用户的问题与文件内容无关，请正常回答用户问题，不需要强行关联文件。\n\n"
        + parsed_content
    )
    return [{"role": "user", "content": context_text}] + messages


async def _inject_memory(messages: list[dict], agent_id: str | None = None, provider_name: str | None = None) -> list[dict]:
    try:
        storage = get_memory_storage()
        lock = await _get_memory_lock(agent_id)
        async with lock:
            memory_data = await asyncio.to_thread(storage.load, agent_id)

        has_facts = bool(memory_data.facts)
        has_profile = bool(
            memory_data.profile.name or memory_data.profile.nickname
            or memory_data.profile.occupation or memory_data.profile.location
        )
        has_working_goal = False
        try:
            has_working_goal = bool(memory_data.working_memory.core_goal)
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

        user_query = _get_user_query(messages)
        injector = MemoryInjector()
        return injector.inject_memory_to_messages(messages, global_memory)
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


async def _collect_all_tools(agent_id: str | None) -> list[dict]:
    cache_key = agent_id or "__global__"
    now = time.time()
    if cache_key in _tools_cache and now - _tools_cache_ts.get(cache_key, 0) < TOOLS_CACHE_TTL:
        logger.debug(f"[Tools] Using cached tools for {cache_key}")
        return _tools_cache[cache_key]

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
                mcp_tools = await MCPGateway.list_tools(server_name)
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

    _tools_cache[cache_key] = tools
    _tools_cache_ts[cache_key] = now
    logger.info(f"[Tools] Collected {len(tools)} tools for agent_id={agent_id} (cached)")
    return tools


def _truncate_tool_result(result: str, max_chars: int = MAX_TOOL_RESULT_CHARS) -> str:
    if len(result) <= max_chars:
        return result
    preview = result[:max_chars]
    return f"{preview}\n\n[Truncated: tool response was {len(result):,} chars, showing first {max_chars:,} chars]"


def _check_loop(thread_id: str, tool_calls: list[dict]) -> str | None:
    if thread_id not in _loop_detection:
        _loop_detection[thread_id] = []

    history = _loop_detection[thread_id]
    call_sig = "|".join(
        tc["function"]["name"] + ":" + tc["function"].get("arguments", "{}")[:100]
        for tc in tool_calls
    )
    history.append(call_sig)
    if len(history) > LOOP_DETECTION_MAX_HISTORY:
        _loop_detection[thread_id] = history[-LOOP_DETECTION_MAX_HISTORY:]

    count = history.count(call_sig)
    if count >= LOOP_DETECTION_HARD_LIMIT:
        logger.warning(f"[LoopDetection] Loop detected for thread {thread_id}: {call_sig[:80]} repeated {count} times")
        return f"Loop detected: the same tool calls have been repeated {count} times. Please provide a direct response instead."
    return None


def _cleanup_loop_detection(thread_id: str):
    _loop_detection.pop(thread_id, None)


async def _execute_tool_call(tool_call: dict, agent_id: str | None = None) -> dict:
    tool_name = tool_call["function"]["name"]
    tool_call_id = tool_call.get("id", "")
    arguments_str = tool_call["function"].get("arguments", "{}")

    try:
        arguments = json.loads(arguments_str) if arguments_str else {}
    except json.JSONDecodeError:
        repaired = _repair_tool_call_arguments(arguments_str, tool_name)
        try:
            arguments = json.loads(repaired)
        except json.JSONDecodeError:
            arguments = {"raw_input": arguments_str}

    logger.info(f"[ToolExec] Executing tool: {tool_name}, call_id={tool_call_id}")

    if tool_name.startswith("mcp_"):
        parts = tool_name.split("_", 2)
        if len(parts) >= 3:
            server_name = parts[1]
            actual_tool_name = parts[2]
            try:
                async with _llm_semaphore:
                    lock = await _get_memory_lock(agent_id)
                    async with lock:
                        await updater.update_from_conversation(messages_snapshot, conv_id, agent_id)
            except Exception as e:
                logger.error(f"[ToolExec] MCP tool error: {tool_name}, error: {e}")
                return {
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "result": f"Tool execution error: {type(e).__name__}: {str(e)[:200]}. Continue with available context, or choose an alternative tool.",
                    "status": "error",
                }

    try:
        skill_data = SkillRegistry.get_skill(tool_name)
        if not skill_data or not skill_data.get("is_active", True):
            return {
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "result": f"Tool '{tool_name}' is currently unavailable. Available tools can be listed on request. Choose an alternative approach.",
                "status": "error",
            }

        task = asyncio.create_task(_do_update())
        task.add_done_callback(lambda t: None if t.exception() is None else logger.warning(f"[Memory] Update task error: {t.exception()}"))
    except Exception as e:
        logger.error(f"[ToolExec] Tool execution failed: {tool_name}, error: {e}", exc_info=True)
        error_msg = (
            f"Tool '{tool_name}' failed: {type(e).__name__}: {str(e)[:200]}. Continue with available context, or choose an alternative tool."
            if settings.DEBUG
            else "Tool execution encountered an issue. Please try again or use a different approach."
        )
        return {
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "result": error_msg,
            "status": "error",
        }


async def _execute_tool_calls_parallel(tool_calls: list[dict], agent_id: str | None = None) -> list[dict]:
    if len(tool_calls) <= 1:
        return [await _execute_tool_call(tool_calls[0], agent_id)] if tool_calls else []

    tasks = [_execute_tool_call(tc, agent_id) for tc in tool_calls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    final_results = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            tc = tool_calls[i]
            final_results.append({
                "tool_call_id": tc.get("id", ""),
                "tool_name": tc["function"]["name"],
                "result": f"Tool execution error: {type(r).__name__}: {str(r)[:200]}. Continue with available context, or choose an alternative tool.",
                "status": "error",
            })
        else:
            final_results.append(r)
    return final_results


def _build_tool_result_messages(
    assistant_content: str | None,
    tool_calls: list[dict],
    tool_results: list[dict],
) -> list[dict]:
    messages = []
    assistant_msg: dict = {"role": "assistant", "content": assistant_content or ""}
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
    thread_id: str | None = None,
) -> LLMResponse:
    current_messages = list(messages)
    all_tool_results: list[dict] = []

    for round_num in range(MAX_TOOL_LOOP_ROUNDS):
        logger.info(f"[AgentLoop] Round {round_num + 1}/{MAX_TOOL_LOOP_ROUNDS}")

        llm_response = await llm_adapter.chat(
            messages=current_messages,
            tools=tools,
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

        if thread_id:
            loop_warning = _check_loop(thread_id, llm_response.tool_calls)
            if loop_warning:
                logger.warning(f"[AgentLoop] {loop_warning}")
                current_messages.append({"role": "user", "content": loop_warning})
                llm_response = await llm_adapter.chat(
                    messages=current_messages,
                    tools=None,
                    provider_name=provider,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                )
                if all_tool_results:
                    llm_response.tool_results = all_tool_results
                return llm_response

        tool_results = await _execute_tool_calls_parallel(llm_response.tool_calls, agent_id)
        all_tool_results.extend(tool_results)

        tool_messages = _build_tool_result_messages(
            llm_response.content,
            llm_response.tool_calls,
            tool_results,
        )
        current_messages.extend(tool_messages)

    logger.warning(f"[AgentLoop] Reached max iterations ({MAX_TOOL_LOOP_ROUNDS})")
    summary_prompt = (
        "You've reached the maximum number of tool-calling iterations. "
        "Please provide a final response summarizing what you've found or done so far."
    )
    current_messages.append({"role": "user", "content": summary_prompt})
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


def _persist_conv(conv_id: str, conv: dict) -> None:
    conv["updated_at"] = datetime.now(timezone.utc).isoformat()
    conversation_store.set(conv_id, conv)


def _append_user_msg(conv: dict, content: str, file_content: str | None = None) -> dict:
    entry: dict = {"role": "user", "content": content}
    if file_content:
        entry["file_content"] = file_content
    last = conv["messages"][-1] if conv["messages"] else None
    if not last or last != entry:
        conv["messages"].append(entry)
        return entry
    return last


def _append_assistant_msg(conv: dict, content: str, reasoning: str | None = None, interrupted: bool = False) -> dict:
    entry: dict = {"role": "assistant", "content": content}
    if reasoning:
        entry["reasoning_content"] = reasoning
    if interrupted:
        entry["interrupted"] = True
    last = conv["messages"][-1] if conv["messages"] else None
    if not last or last.get("content") != content or (reasoning and last.get("reasoning_content") != reasoning):
        conv["messages"].append(entry)
        return entry
    return last


@router.post("/completions")
async def chat_completions(request: ChatRequest):
    start_time = time.time()
    resolved_provider = request.provider or llm_adapter.default_provider
    resolved_model = request.model or llm_adapter.get_provider(resolved_provider).default_model
    request_ts = request.timestamp or _get_timestamp()
    logger.info(f"[API] POST /chat/completions - provider={resolved_provider}, model={resolved_model}, stream={request.stream}, ts={request_ts}")

    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    messages = _inject_system_prompt(messages)
    messages = await _inject_memory(messages, request.agent_id, resolved_provider)

    ctx_mgr = get_context_manager(resolved_provider, resolved_model)
    messages = await ctx_mgr.process(messages)

    # 意图分类 + 按需工具加载（仅 TOOL_CALL 类型注入匹配场景的工具）
    user_query = _get_user_query(messages)
    request_type = classify_request(user_query)
    tools = _resolve_tools(user_query, request_type)
    tools_count = len(tools) if tools else 0
    logger.info(f"[API] 意图分类: type={request_type.value}, tools_injected={tools_count}")

    # LOCAL_TOOL：本地工具直接处理，不走 LLM
    if request_type == RequestType.LOCAL_TOOL:
        result = await handle_local_tool_request(user_query)
        if result is None:
            async with _llm_semaphore:
                raw = await llm_adapter.chat(
                    messages=messages,
                    provider_name=resolved_provider,
                    model=resolved_model,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    top_p=request.top_p,
                )
            result_content = raw.get("content") if isinstance(raw, dict) else raw
            result_reasoning = raw.get("reasoning") if isinstance(raw, dict) else None
        else:
            result_content = result.get("content") if isinstance(result, dict) else result
            result_reasoning = result.get("reasoning") if isinstance(result, dict) else None
        elapsed = time.time() - start_time
        logger.success(f"[API] POST /chat/completions [LOCAL_TOOL] - Success: elapsed={elapsed:.2f}s")

        if request.stream:
            chat_id = str(uuid.uuid4())
            data = ChatStreamChunk(id=chat_id, content=result_content, reasoning_content=result_reasoning or "", model=resolved_model, provider=resolved_provider)
            done_data = ChatStreamChunk(id=chat_id, content="", model=resolved_model, provider=resolved_provider, done=True)

            async def _local_tool_stream():
                yield f"data: {data.model_dump_json()}\n\n"
                yield f"data: {done_data.model_dump_json()}\n\n"

            return StreamingResponse(_local_tool_stream(), media_type="text/event-stream")

        return ChatResponse(
            id=str(uuid.uuid4()),
            content=result_content,
            model=resolved_model,
            provider=resolved_provider,
        )

    # TOOL_CALL：先走本地工具快速路径，未匹配则 Tool Loop / 规则驱动
    if request_type == RequestType.TOOL_CALL:
        local_result = await handle_local_tool_request(user_query)
        if local_result is not None:
            local_result_content = local_result.get("content") if isinstance(local_result, dict) else local_result
            local_result_reasoning = local_result.get("reasoning") if isinstance(local_result, dict) else None
            elapsed = time.time() - start_time
            logger.success(f"[API] POST /chat/completions [TOOL local] - Success: elapsed={elapsed:.2f}s")

            if request.stream:
                chat_id = str(uuid.uuid4())
                data = ChatStreamChunk(id=chat_id, content=local_result_content, reasoning_content=local_result_reasoning or "", model=resolved_model, provider=resolved_provider)
                done_data = ChatStreamChunk(id=chat_id, content="", model=resolved_model, provider=resolved_provider, done=True)

                async def _tool_local_stream():
                    yield f"data: {data.model_dump_json()}\n\n"
                    yield f"data: {done_data.model_dump_json()}\n\n"

                return StreamingResponse(_tool_local_stream(), media_type="text/event-stream")

            return ChatResponse(
                id=str(uuid.uuid4()),
                content=local_result_content,
                model=resolved_model,
                provider=resolved_provider,
            )

        tool_results = await execute_tool_chain(
            user_query,
            agent_id=request.agent_id,
            external_search_results=request.search_results,
        )
        if tool_results:
            summary_prompt = build_tool_summary(user_query, tool_results)
            summary_messages = [{"role": "user", "content": summary_prompt}]

            if request.stream:
                async def _tool_chain_stream():
                    chat_id = str(uuid.uuid4())
                    try:
                        yield f"data: {ChatStreamChunk(id=chat_id, content='', reasoning_content='正在查询所需信息…', model=resolved_model, provider=resolved_provider).model_dump_json()}\n\n"
                        async with _llm_semaphore:
                            async for chunk in llm_adapter.chat_stream(
                                messages=summary_messages, provider_name=resolved_provider, model=resolved_model,
                                temperature=request.temperature or 0.7,
                                max_tokens=request.max_tokens or 4096, top_p=request.top_p or 0.9,
                            ):
                                yield f"data: {ChatStreamChunk(id=chat_id, content=chunk.get('content', ''), reasoning_content=chunk.get('reasoning', ''), model=resolved_model, provider=resolved_provider).model_dump_json()}\n\n"
                    except Exception as e:
                        logger.error(f"[STREAM] Tool chain stream error: {e}")
                        yield f"data: {ChatStreamChunk(id=chat_id, content=f'[Error] {str(e)}', model=resolved_model, provider=resolved_provider).model_dump_json()}\n\n"
                    finally:
                        yield f"data: {ChatStreamChunk(id=chat_id, content='', model=resolved_model, provider=resolved_provider, done=True).model_dump_json()}\n\n"

                elapsed = time.time() - start_time
                logger.success(f"[API] POST /chat/completions [TOOL chain stream] - Success: elapsed={elapsed:.2f}s")
                return StreamingResponse(_tool_chain_stream(), media_type="text/event-stream")

            async with _llm_semaphore:
                raw = await llm_adapter.chat(
                    messages=summary_messages, provider_name=resolved_provider, model=resolved_model,
                    temperature=request.temperature or 0.7,
                    max_tokens=request.max_tokens or 4096, top_p=request.top_p or 0.9,
                )
            result = raw.get("content") if isinstance(raw, dict) else raw
            elapsed = time.time() - start_time
            logger.success(f"[API] POST /chat/completions [TOOL chain] - Success: elapsed={elapsed:.2f}s")
            return ChatResponse(
                id=str(uuid.uuid4()),
                content=result,
                model=resolved_model,
                provider=resolved_provider,
            )

        # 无匹配工具 → 降级到通用对话

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
        async with _llm_semaphore:
            result = await llm_adapter.chat(
                messages=messages,
                provider_name=resolved_provider,
                model=resolved_model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                top_p=request.top_p,
            )

        result_content = result.get("content") if isinstance(result, dict) else result
        result_content = result_content or ""
        elapsed = time.time() - start_time
        logger.success(f"[API] POST /chat/completions - Success: elapsed={elapsed:.2f}s, response_len={len(result_content)}")
        return ChatResponse(
            id=str(uuid.uuid4()),
            content=result_content,
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


async def _stream_chat(messages: list[dict], request: ChatRequest, provider: str, model: str):
    chat_id = str(uuid.uuid4())
    full_reply = ""
    try:
        async with _llm_semaphore:
            async for chunk in llm_adapter.chat_stream(
                messages=messages,
                provider_name=provider,
                model=model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                top_p=request.top_p,
            ):
                content = chunk.get("content", "")
                rc = chunk.get("reasoning", "")
                if content:
                    full_reply += content
                data = ChatStreamChunk(id=chat_id, content=content, reasoning_content=rc, model=model, provider=provider)
                yield f"data: {data.model_dump_json()}\n\n"
    except Exception as e:
        logger.error(f"[STREAM] _stream_chat error: {e}")
        yield f"data: {ChatStreamChunk(id=chat_id, content=f'[Error] {str(e)}', model=model, provider=provider).model_dump_json()}\n\n"
    finally:
        done_data = ChatStreamChunk(id=chat_id, content="", model=model, provider=provider, done=True)
        yield f"data: {done_data.model_dump_json()}\n\n"


@router.get("/conversations", response_model=list[ConversationListResponse])
async def list_conversations(agent_id: str | None = None):
    logger.info(f"[API] GET /chat/conversations - Listing conversations, agent_id={agent_id}")
    conv_list = conversation_store.list_conversations(agent_id)
    result = []
    for meta in conv_list:
        conv_id = meta.get("id")
        if not conv_id:
            logger.warning("[API] Skipping conversation with missing id in index")
            continue
        result.append(ConversationListResponse(
            id=conv_id,
            title=meta.get("title", "New Conversation"),
            agent_id=meta.get("agent_id"),
            model=meta.get("model"),
            provider=meta.get("provider"),
            last_message=meta.get("last_message"),
            created_at=meta.get("created_at", ""),
            updated_at=meta.get("updated_at", ""),
        ))
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
    conversation_store.set(conv_id, conv)
    logger.success(f"[API] POST /chat/conversations - Conversation created: id={conv_id}")
    return ConversationResponse(**conv)


@router.get("/conversations/{conv_id}", response_model=ConversationResponse)
async def get_conversation(conv_id: str):
    logger.info(f"[API] GET /chat/conversations/{conv_id} - Fetching conversation")
    conv = conversation_store.get(conv_id)
    if not conv:
        logger.error(f"[API] GET /chat/conversations/{conv_id} - Conversation not found")
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Conversation {conv_id} not found")
    logger.success(f"[API] GET /chat/conversations/{conv_id} - Success: title={conv['title']}, messages={len(conv.get('messages', []))}")
    return ConversationResponse(**conv)


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    logger.info(f"[API] DELETE /chat/conversations/{conv_id} - Deleting conversation")
    conv = conversation_store.get(conv_id)
    if conv:
        conv_title = conv.get("title", "unknown")
        conversation_store.delete(conv_id)
        logger.success(f"[API] DELETE /chat/conversations/{conv_id} - Conversation deleted: title={conv_title}")
    else:
        logger.warning(f"[API] DELETE /chat/conversations/{conv_id} - Conversation not found")
    return {"error": None, "data": {"deleted": True}}


@router.post("/conversations/{conv_id}/messages")
async def add_message(conv_id: str, request: ChatRequest):
    start_time = time.time()
    logger.info(f"[API] POST /chat/conversations/{conv_id}/messages - Adding message")

    conv = conversation_store.get(conv_id)
    if not conv:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Conversation {conv_id} not found")

    last_user_content = ""
    for m in reversed(request.messages):
        if m.role == "user":
            last_user_content = m.content
            break

    _phase_1_save_user_msg(conv, last_user_content, request.file_content, request.file_name, request.file_type)
    _persist_conv(conv_id, conv)

    resolved_provider = request.provider or conv.get("provider") or llm_adapter.default_provider
    resolved_model = request.model or conv.get("model") or llm_adapter.get_provider(resolved_provider).default_model

    system_prompt = _build_system_prompt(conv.get("agent_id"))
    all_messages: list[dict] = [{"role": "system", "content": system_prompt}]

    for m in conv["messages"]:
        msg = {"role": m["role"], "content": m["content"]}
        # 如果 content 是列表（多模态格式），保留原样
        if isinstance(m.get("content"), list):
            msg["content"] = m["content"]
        all_messages.append(msg)

    all_messages = _inject_system_prompt(all_messages)
    agent_id = request.agent_id or conv.get("agent_id")
    all_messages = await _inject_memory(all_messages, agent_id, resolved_provider)

    if request.file_content:
        logger.info(f"[API] 文件内容注入: file_type={request.file_type}, content_length={len(request.file_content)}, is_image={request.file_type == 'image'}")
        all_messages = _inject_file_content(all_messages, request.file_content, request.file_type or "text")

    ctx_mgr = get_context_manager(resolved_provider, resolved_model)
    all_messages = await ctx_mgr.process(all_messages)

    user_query = _get_user_query(all_messages)
    request_type = classify_request(user_query)
    tools = _resolve_tools(user_query, request_type)
    logger.info(f"[API] Intent={request_type.value}, tools={len(tools) if tools else 0}")

    gen_state: dict = {
        "content": "",
        "reasoning": "",
        "aborted": False,
        "started": True,
    }

    if request.stream:
        return await _STREAM_RESPONSE(conv_id, conv, request, all_messages, user_query,
                                       request_type, tools, resolved_provider, resolved_model,
                                       agent_id, gen_state, start_time,
                                       search_results=request.search_results)

    await _NON_STREAM_GENERATE(gen_state, request_type, user_query, all_messages,
                                 resolved_provider, resolved_model, tools, agent_id,
                                 temperature=request.temperature,
                                 max_tokens=request.max_tokens,
                                 top_p=request.top_p,
                                 search_results=request.search_results)

    # 非流式路径：错误时不持久化 [Error] 占位符到对话历史
    persist_state = dict(gen_state)
    if persist_state["aborted"] and persist_state["content"].startswith("[Error]"):
        persist_state["content"] = ""

    _PHASE_3_SAVE_ASSISTANT_MSG(conv, persist_state)
    _persist_conv(conv_id, conv)
    _schedule_memory_update(conv["messages"], conv_id, agent_id, provider_name=resolved_provider)

    elapsed = time.time() - start_time
    logger.success(f"[API] Done: conv={conv_id}, elapsed={elapsed:.2f}s, len={len(gen_state['content'])}, aborted={gen_state['aborted']}")

    return ChatResponse(
        id=str(uuid.uuid4()),
        content=gen_state["content"],
        model=resolved_model,
        provider=resolved_provider,
        tool_calls=tool_calls_data,
        tool_results=tool_results_data,
        usage=result.usage,
        timestamp=_get_timestamp(),
    )


def _phase_1_save_user_msg(conv: dict, content: str, file_content: str | None = None, file_name: str | None = None, file_type: str | None = None) -> None:
    if not content:
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
    if not last or last != entry:
        conv["messages"].append(entry)


def _PHASE_3_SAVE_ASSISTANT_MSG(conv: dict, state: dict) -> None:
    content = state["content"] or "[已中断]"
    reasoning = state["reasoning"] or None
    interrupted = state["aborted"]
    entry: dict = {"role": "assistant", "content": content}
    if reasoning:
        entry["reasoning_content"] = reasoning
    if interrupted:
        entry["interrupted"] = True
    last = conv["messages"][-1] if conv["messages"] else None
    if not last or last.get("content") != content:
        conv["messages"].append(entry)


async def _NON_STREAM_GENERATE(state: dict, request_type: RequestType,
                                 user_query: str, all_messages: list[dict],
                                 provider: str, model: str, tools: list | None,
                                 agent_id: str | None = None,
                                 temperature: float | None = None,
                                 max_tokens: int | None = None,
                                 top_p: float | None = None,
                                 search_results: str | None = None) -> None:
    try:
        if request_type == RequestType.LOCAL_TOOL:
            result = await handle_local_tool_request(user_query)
            if result is None:
                async with _llm_semaphore:
                    raw = await llm_adapter.chat(messages=all_messages, provider_name=provider,
                        model=model, temperature=temperature, max_tokens=max_tokens, top_p=top_p)
                result = raw.get("content") if isinstance(raw, dict) else raw
                if isinstance(raw, dict) and raw.get("reasoning"):
                    state["reasoning"] = raw["reasoning"]
            else:
                result_content = result.get("content") if isinstance(result, dict) else result
                if isinstance(result, dict) and result.get("reasoning"):
                    state["reasoning"] = result["reasoning"]
                result = result_content
            state["content"] = result or ""

        elif request_type == RequestType.TOOL_CALL:
            local_result = await handle_local_tool_request(user_query)
            if local_result is not None:
                local_content = local_result.get("content") if isinstance(local_result, dict) else local_result
                if isinstance(local_result, dict) and local_result.get("reasoning"):
                    state["reasoning"] = local_result["reasoning"]
                state["content"] = local_content or ""
            else:
                tool_results = await execute_tool_chain(user_query, agent_id=agent_id,
                                                         external_search_results=search_results)
                if tool_results:
                    summary_prompt = build_tool_summary(user_query, tool_results)
                    summary_messages = [{"role": "user", "content": summary_prompt}]
                    async with _llm_semaphore:
                        raw = await llm_adapter.chat(messages=summary_messages, provider_name=provider,
                            model=model, temperature=temperature, max_tokens=max_tokens, top_p=top_p)
                else:
                    async with _llm_semaphore:
                        raw = await llm_adapter.chat(messages=all_messages, provider_name=provider,
                            model=model, temperature=temperature, max_tokens=max_tokens, top_p=top_p)
                if isinstance(raw, dict):
                    state["content"] = raw.get("content", "")
                    if raw.get("reasoning"):
                        state["reasoning"] = raw["reasoning"]
                else:
                    state["content"] = raw

        else:
            async with _llm_semaphore:
                raw = await llm_adapter.chat(messages=all_messages, provider_name=provider,
                    model=model, temperature=temperature, max_tokens=max_tokens, top_p=top_p)
            if isinstance(raw, dict):
                state["content"] = raw.get("content", "")
                if raw.get("reasoning"):
                    state["reasoning"] = raw["reasoning"]
            else:
                state["content"] = raw
    except Exception as e:
        logger.error(f"[API] Non-stream error: {e}")
        state["aborted"] = True
        state["content"] = f"[Error] {str(e)}"


async def _STREAM_RESPONSE(conv_id: str, conv: dict, request: ChatRequest,
                            all_messages: list, user_query: str, request_type: RequestType,
                            tools: list | None, provider: str, model: str,
                            agent_id: str | None, state: dict, start_time: float,
                            search_results: str | None = None):
    chat_id = str(uuid.uuid4())

    async def generator():
        try:
            if request_type == RequestType.LOCAL_TOOL:
                result = await handle_local_tool_request(user_query)
                if result is None:
                    async with _llm_semaphore:
                        raw = await llm_adapter.chat(messages=all_messages, provider_name=provider,
                            model=model, temperature=request.temperature or 0.7,
                            max_tokens=request.max_tokens or 4096, top_p=request.top_p or 0.9)
                    result_content = raw.get("content") if isinstance(raw, dict) else raw
                    if isinstance(raw, dict) and raw.get("reasoning"):
                        state["reasoning"] = raw["reasoning"]
                else:
                    result_content = result.get("content") if isinstance(result, dict) else result
                    if isinstance(result, dict) and result.get("reasoning"):
                        state["reasoning"] = result["reasoning"]
                state["content"] = result_content or ""
                yield _sse(chat_id, state["content"], provider, model)

            elif request_type == RequestType.TOOL_CALL:
                local_result = await handle_local_tool_request(user_query)
                if local_result is not None:
                    local_content = local_result.get("content") if isinstance(local_result, dict) else local_result
                    if isinstance(local_result, dict) and local_result.get("reasoning"):
                        state["reasoning"] = local_result["reasoning"]
                    state["content"] = local_content or ""
                    yield _sse(chat_id, state["content"], provider, model)
                else:
                    yield _sse_reasoning(chat_id, "正在查询所需信息…", provider, model)
                    tool_results = await execute_tool_chain(user_query, agent_id=agent_id,
                                                             external_search_results=search_results)
                    if tool_results:
                        summary_prompt = build_tool_summary(user_query, tool_results)
                        summary_messages = [{"role": "user", "content": summary_prompt}]
                    else:
                        summary_messages = all_messages
                    async with _llm_semaphore:
                        async for chunk in llm_adapter.chat_stream(
                            messages=summary_messages, provider_name=provider, model=model,
                            temperature=request.temperature or 0.7,
                            max_tokens=request.max_tokens or 4096, top_p=request.top_p or 0.9,
                        ):
                            content = chunk.get("content", "")
                            rc = chunk.get("reasoning", "")
                            if content:
                                state["content"] += content
                            if rc:
                                state["reasoning"] += rc
                            yield _sse(chat_id, content, provider, model, rc)

            else:
                async with _llm_semaphore:
                    async for chunk in llm_adapter.chat_stream(
                        messages=all_messages, provider_name=provider, model=model,
                        temperature=request.temperature or 0.7,
                        max_tokens=request.max_tokens or 4096, top_p=request.top_p or 0.9,
                    ):
                        content = chunk.get("content", "")
                        rc = chunk.get("reasoning", "")
                        if content:
                            state["content"] += content
                        if rc:
                            state["reasoning"] += rc
                        yield _sse(chat_id, content, provider, model, rc)

        except Exception as e:
            state["aborted"] = True
            logger.error(f"[STREAM] Aborted: conv={conv_id}, error={e}")
            yield _sse(chat_id, f"[Error] {str(e)}", provider, model)

        finally:
            try:
                # 持久化时使用原始内容，不写入错误占位符
                persist_state = dict(state)
                if persist_state["aborted"] and persist_state["content"].startswith("[Error]"):
                    persist_state["content"] = ""
                _PHASE_3_SAVE_ASSISTANT_MSG(conv, persist_state)
                _persist_conv(conv_id, conv)
            except Exception as persist_err:
                logger.error(f"[STREAM] Persist failed: conv={conv_id}, error={persist_err}")
            try:
                yield _sse_done(chat_id, provider, model)
            except Exception as done_err:
                logger.debug(f"[STREAM] Done event send failed (client may have disconnected): {done_err}")
            try:
                _schedule_memory_update(conv["messages"], conv_id, agent_id, provider_name=provider)
            except Exception as schedule_err:
                logger.warning(f"[STREAM] Memory update scheduling failed: {schedule_err}")

    return StreamingResponse(generator(), media_type="text/event-stream",
                           headers={"Cache-Control": "no-cache", "Connection": "keep-alive",
                                   "X-Accel-Buffering": "no"})


def _sse(cid: str, content: str, provider: str, model: str, reasoning: str = "") -> str:
    return f"data: {ChatStreamChunk(id=cid, content=content, reasoning_content=reasoning, model=model, provider=provider).model_dump_json()}\n\n"

def _sse_reasoning(cid: str, reasoning: str, provider: str, model: str) -> str:
    return f"data: {ChatStreamChunk(id=cid, content='', reasoning_content=reasoning, model=model, provider=provider).model_dump_json()}\n\n"

def _sse_done(cid: str, provider: str, model: str) -> str:
    return f"data: {ChatStreamChunk(id=cid, content='', model=model, provider=provider, done=True).model_dump_json()}\n\n"
