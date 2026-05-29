import asyncio
import json
import re
import uuid
import time
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from loguru import logger

from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatStreamChunk,
    ConversationCreate,
    ConversationResponse,
    ConversationListResponse,
    ConversationSearchResult,
    TrashListItemResponse,
    BatchIdsRequest,
)
from app.runtime.provider.llm.adapter import llm_adapter
from app.infrastructure.database.conversation_store import conversation_store
from app.core.context import get_context_manager
from app.services.context_service import context_service
from app.services.suggestion_service import suggestion_service
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])

_memory_locks: dict[str | None, asyncio.Lock] = {}
_memory_locks_guard = asyncio.Lock()
_llm_semaphore = asyncio.Semaphore(1)

_tools_cache: dict[str, list[dict]] = {}
_tools_cache_ts: dict[str, float] = {}
TOOLS_CACHE_TTL = 300  # 5 minutes
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

# 推荐问题异步任务跟踪：每个对话只保留最新的推荐生成任务
_pending_suggestion_tasks: dict[str, asyncio.Task] = {}

SUGGESTED_QUESTIONS_PROMPT = """基于以下对话内容，生成3个用户可能想问的后续问题。

要求：
1. 问题要具体、有针对性，与对话内容紧密相关
2. 问题要简洁明了，每个不超过30个字
3. 问题应该引导用户深入探讨对话中的话题
4. 只返回问题列表，每行一个，不要编号，不要其他内容

对话内容：
{conversation}"""


async def _generate_suggested_questions(
    messages: list[dict],
    agent_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> list[str]:
    """调用 LLM 生成推荐问题，永不持久化"""
    try:
        # 构建对话摘要（取最近的消息，避免过长）
        recent_messages = messages[-6:]  # 最近6条消息
        conversation_text = ""
        for msg in recent_messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if isinstance(content, list):
                # 多模态消息，只取文本部分
                text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
                content = " ".join(text_parts)
            if role == "user":
                conversation_text += f"用户: {content}\n"
            elif role == "assistant":
                # 截断过长的助手回复
                if len(content) > 500:
                    content = content[:500] + "..."
                conversation_text += f"助手: {content}\n"

        if not conversation_text.strip():
            return []

        prompt = SUGGESTED_QUESTIONS_PROMPT.format(conversation=conversation_text)

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

        # 解析 LLM 返回的问题列表
        questions: list[str] = []
        for line in text.strip().split("\n"):
            line = line.strip()
            # 去掉可能的编号前缀（1. 2. 1) 2) 等）
            line = re.sub(r'^[\d]+[.、)\]]\s*', '', line)
            if line and len(line) <= 50:
                questions.append(line)

        return questions[:3]  # 最多3个

    except Exception as e:
        logger.warning(f"[SuggestedQuestions] Failed to generate: {e}")
        return []


async def _generate_suggestions_for_conv(
    conv_id: str,
    messages: list[dict],
    agent_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> list[str]:
    """为指定对话生成推荐问题，带任务取消机制"""
    # 取消该对话之前未完成的推荐生成任务
    old_task = _pending_suggestion_tasks.get(conv_id)
    if old_task and not old_task.done():
        old_task.cancel()
        logger.debug(f"[SuggestedQuestions] Cancelled previous task for conv={conv_id}")

    # 创建新任务
    task = asyncio.create_task(
        _generate_suggested_questions(messages, agent_id, provider, model)
    )
    _pending_suggestion_tasks[conv_id] = task

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
        if _pending_suggestion_tasks.get(conv_id) is task:
            del _pending_suggestion_tasks[conv_id]


def _get_user_query(messages: list[dict]) -> str:
    """Extract the last user message content from the message list."""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
                return " ".join(parts)
    return ""
LOOP_DETECTION_MAX_HISTORY = 20
LOOP_DETECTION_HARD_LIMIT = 5


def _get_timestamp() -> float:
    return time.time()

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


async def _inject_memory(messages: list[dict], agent_id: str | None = None, provider_name: str | None = None, thread_id: str = "") -> list[dict]:
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
            goal = memory_data.working_memory.get_core_goal_for(thread_id) if thread_id else memory_data.working_memory.core_goal
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

        user_query = _get_user_query(messages)
        injector = MemoryInjector()
        return injector.inject_memory_to_messages(messages, memory_data, user_query, thread_id)
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
                from app.domains.mcp_tools.gateway import MCPGateway
                result = await MCPGateway.call_tool(server_name, actual_tool_name, arguments)
                result_str = json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result
                return {
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "result": _truncate_tool_result(result_str),
                    "status": "success",
                }
            except Exception as e:
                logger.error(f"[ToolExec] MCP tool error: {tool_name}, error: {e}")
                return {
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "result": f"Tool execution error: {type(e).__name__}: {str(e)[:200]}. Continue with available context, or choose an alternative tool.",
                    "status": "error",
                }

    try:
        result = await execute_single_tool(tool_name, arguments, agent_id=agent_id)
        result_str = process_tool_result(result, tool_name)
        return {
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "result": _truncate_tool_result(result_str),
            "status": "success",
        }
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

        raw = await llm_adapter.chat(
            messages=current_messages,
            tools=tools,
            provider_name=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            return_raw=True,
        )

        # Convert dict response to LLMResponse
        if isinstance(raw, dict):
            llm_response = LLMResponse(
                content=raw.get("content", ""),
                tool_calls=raw.get("tool_calls"),
                finish_reason="stop",
            )
        else:
            llm_response = LLMResponse(content=str(raw), finish_reason="stop")

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
                raw2 = await llm_adapter.chat(
                    messages=current_messages,
                    tools=None,
                    provider_name=provider,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    return_raw=True,
                )
                if isinstance(raw2, dict):
                    llm_response = LLMResponse(
                        content=raw2.get("content", ""),
                        tool_calls=raw2.get("tool_calls"),
                        finish_reason="stop",
                    )
                else:
                    llm_response = LLMResponse(content=str(raw2), finish_reason="stop")
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
    raw_final = await llm_adapter.chat(
        messages=current_messages,
        tools=None,
        provider_name=provider,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        return_raw=True,
    )
    if isinstance(raw_final, dict):
        final_response = LLMResponse(
            content=raw_final.get("content", ""),
            tool_calls=raw_final.get("tool_calls"),
            finish_reason="stop",
        )
    else:
        final_response = LLMResponse(content=str(raw_final), finish_reason="stop")
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
    request_ts = request.timestamp or time.time()
    logger.info(
        f"[API] POST /chat/completions - "
        f"provider={resolved_provider}, model={resolved_model}, "
        f"stream={request.stream}, ts={request_ts}"
    )

    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    messages = context_service.inject_timestamp_prompt(messages)
    messages = await context_service.inject_memory(messages, request.agent_id, resolved_provider)

    ctx_mgr = get_context_manager(resolved_provider, resolved_model)
    messages = await ctx_mgr.process(messages)

    if request.stream:
        logger.info("[API] POST /chat/completions - Starting stream response")
        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            _chat_service.stream_chat(messages, request, resolved_provider, resolved_model),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    gen_state: dict = {"content": "", "reasoning": "", "aborted": False, "started": True}
    await _chat_service.non_stream_generate(
        gen_state, messages,
        resolved_provider, resolved_model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        top_p=request.top_p,
    )

    if gen_state["aborted"]:
        raise Exception(gen_state["content"].removeprefix("[Error] "))

    result_content = gen_state["content"] or ""
    elapsed = time.time() - start_time
    logger.success(
        f"[API] POST /chat/completions - "
        f"Success: elapsed={elapsed:.2f}s, response_len={len(result_content)}"
    )
    return ChatResponse(
        id=str(uuid.uuid4()),
        content=result_content,
        model=resolved_model,
        provider=resolved_provider,
    )


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


@router.get("/conversations/search", response_model=list[ConversationSearchResult])
async def search_conversations(keyword: str, agent_id: str | None = None):
    req_id = str(uuid.uuid4())[:8]
    logger.info(
        f"[API] GET /chat/conversations/search - "
        f"req_id={req_id}, keyword_len={len(keyword)}, "
        f"agent_id={'***' if agent_id else None}"
    )
    results = conversation_store.search_conversations(keyword, agent_id)
    response = [
        ConversationSearchResult(
            id=r["id"],
            title=r["title"],
            snippet=r["snippet"],
            updated_at=r["updated_at"],
        )
        for r in results
    ]
    logger.success(
        f"[API] GET /chat/conversations/search - req_id={req_id}, found {len(response)} results"
    )
    return response


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(request: ConversationCreate):
    logger.info(
        f"[API] POST /chat/conversations - "
        f"Creating conversation: title={request.title}, agent_id={request.agent_id}"
    )
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
    logger.success(
        f"[API] GET /chat/conversations/{conv_id} - "
        f"Success: title={conv['title']}, messages={len(conv.get('messages', []))}"
    )
    return ConversationResponse(**conv)


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    logger.info(f"[API] DELETE /chat/conversations/{conv_id} - Moving to trash")
    conversation_store.soft_delete(conv_id)
    logger.success(f"[API] DELETE /chat/conversations/{conv_id} - Moved to trash")
    return {"error": None, "data": {"deleted": True}}


class TruncateMessagesRequest(BaseModel):
    keep_count: int = Field(..., ge=0)


class DeleteMessageRequest(BaseModel):
    message_id: str


@router.patch("/conversations/{conv_id}/messages")
async def truncate_messages(conv_id: str, request: TruncateMessagesRequest):
    logger.info(
        f"[API] PATCH /chat/conversations/{conv_id}/messages - "
        f"Truncating to {request.keep_count}"
    )
    conv = conversation_store.get(conv_id)
    if not conv:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Conversation {conv_id} not found")
    conv["messages"] = conv["messages"][:request.keep_count]
    _chat_service.persist_conv(conv_id, conv)

    agent_id = conv.get("agent_id")
    try:
        from app.engines.memory.core.storage import get_memory_storage
        storage = get_memory_storage()
        storage.clear_thread(conv_id, agent_id)
        logger.info(f"[Memory] Cleared thread memory for conv={conv_id}")
    except Exception as e:
        logger.warning(f"[Memory] Failed to clear thread memory: {e}")

    logger.success(
        f"[API] PATCH /chat/conversations/{conv_id}/messages - "
        f"Truncated to {request.keep_count} messages"
    )
    return {"error": None, "data": {"truncated": True, "keep_count": request.keep_count}}


@router.delete("/conversations/{conv_id}/messages/{message_id}")
async def delete_message(conv_id: str, message_id: str):
    logger.info(
        f"[API] DELETE /chat/conversations/{conv_id}/messages/{message_id} - Deleting message"
    )
    conv = conversation_store.get(conv_id)
    if not conv:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Conversation {conv_id} not found")
    original_len = len(conv["messages"])
    conv["messages"] = [m for m in conv["messages"] if m.get("id") != message_id]
    if len(conv["messages"]) == original_len:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Message {message_id} not found in conversation {conv_id}")
    _chat_service.persist_conv(conv_id, conv)
    logger.success(
        f"[API] DELETE /chat/conversations/{conv_id}/messages/{message_id} - Message deleted"
    )
    return {"error": None, "data": {"deleted": True}}


class TruncateMessagesRequest(BaseModel):
    keep_count: int = Field(..., ge=0)


class DeleteMessageRequest(BaseModel):
    message_id: str


@router.patch("/conversations/{conv_id}/messages")
async def truncate_messages(conv_id: str, request: TruncateMessagesRequest):
    logger.info(f"[API] PATCH /chat/conversations/{conv_id}/messages - Truncating to {request.keep_count}")
    conv = conversation_store.get(conv_id)
    if not conv:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Conversation {conv_id} not found")
    conv["messages"] = conv["messages"][:request.keep_count]
    _persist_conv(conv_id, conv)

    # Also clear thread-isolated working memory for this conversation
    agent_id = conv.get("agent_id")
    try:
        storage = get_memory_storage()
        storage.clear_thread(conv_id, agent_id)
        logger.info(f"[Memory] Cleared thread memory for conv={conv_id}")
    except Exception as e:
        logger.warning(f"[Memory] Failed to clear thread memory: {e}")

    logger.success(f"[API] PATCH /chat/conversations/{conv_id}/messages - Truncated to {request.keep_count} messages")
    return {"error": None, "data": {"truncated": True, "keep_count": request.keep_count}}


@router.delete("/conversations/{conv_id}/messages/{message_id}")
async def delete_message(conv_id: str, message_id: str):
    logger.info(f"[API] DELETE /chat/conversations/{conv_id}/messages/{message_id} - Deleting message")
    conv = conversation_store.get(conv_id)
    if not conv:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Conversation {conv_id} not found")
    original_len = len(conv["messages"])
    conv["messages"] = [m for m in conv["messages"] if m.get("id") != message_id]
    if len(conv["messages"]) == original_len:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(f"Message {message_id} not found in conversation {conv_id}")
    _persist_conv(conv_id, conv)
    logger.success(f"[API] DELETE /chat/conversations/{conv_id}/messages/{message_id} - Message deleted")
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

    _chat_service.save_user_message(
        conv, last_user_content, request.file_content, request.file_name, request.file_type,
    )
    _chat_service.persist_conv(conv_id, conv)

    resolved_provider = (
        request.provider or conv.get("provider") or llm_adapter.default_provider
    )
    resolved_model = (
        request.model or conv.get("model")
        or llm_adapter.get_provider(resolved_provider).default_model
    )

    system_prompt = context_service.build_system_prompt(conv.get("agent_id"))
    all_messages: list[dict] = [{"role": "system", "content": system_prompt}]

    for m in conv["messages"]:
        msg = {"role": m["role"], "content": m["content"]}
        if isinstance(m.get("content"), list):
            msg["content"] = m["content"]
        all_messages.append(msg)

    all_messages = context_service.inject_timestamp_prompt(all_messages)
    agent_id = request.agent_id or conv.get("agent_id")
    all_messages = await context_service.inject_memory(
        all_messages, agent_id, resolved_provider, conv_id,
    )

    if request.file_content:
        logger.info(
            f"[API] 文件内容注入: file_type={request.file_type}, "
            f"content_length={len(request.file_content)}, "
            f"is_image={request.file_type == 'image'}"
        )
        all_messages = context_service.inject_file_content(
            all_messages, request.file_content, request.file_type or "text",
        )

    ctx_mgr = get_context_manager(resolved_provider, resolved_model)
    all_messages = await ctx_mgr.process(all_messages)

    gen_state: dict = {
        "content": "",
        "reasoning": "",
        "aborted": False,
        "started": True,
    }

    if request.stream:
        return await _chat_service.stream_response(
            conv_id, conv, request, all_messages,
            resolved_provider, resolved_model,
            agent_id, gen_state, start_time,
        )

    await _chat_service.non_stream_generate(
        gen_state, all_messages,
        resolved_provider, resolved_model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        top_p=request.top_p,
    )

    persist_state = dict(gen_state)
    if persist_state["aborted"] and persist_state["content"].startswith("[Error]"):
        persist_state["content"] = ""

    _chat_service.save_assistant_message(conv, persist_state)
    _chat_service.persist_conv(conv_id, conv)
    context_service.schedule_memory_update(
        [dict(m) for m in conv["messages"]], conv_id, agent_id,
    )

    elapsed = time.time() - start_time
    logger.success(
        f"[API] Done: conv={conv_id}, elapsed={elapsed:.2f}s, "
        f"len={len(gen_state['content'])}, aborted={gen_state['aborted']}"
    )

    return ChatResponse(
        id=str(uuid.uuid4()),
        content=gen_state["content"],
        model=resolved_model,
        provider=resolved_provider,
    )


# ── 回收站 ──────────────────────────────────────────────────

@router.get("/trash", response_model=list[TrashListItemResponse])
async def list_trash(agent_id: str | None = None):
    logger.info(f"[API] GET /chat/trash - Listing trash, agent_id={agent_id}")
    items = conversation_store.list_trash(agent_id)
    result = []
    for meta in items:
        result.append(TrashListItemResponse(
            id=meta["id"],
            title=meta.get("title", "New Conversation"),
            agent_id=meta.get("agent_id"),
            model=meta.get("model"),
            provider=meta.get("provider"),
            last_message=meta.get("last_message"),
            created_at=meta.get("created_at", ""),
            updated_at=meta.get("updated_at", ""),
            deleted_at=meta.get("deleted_at", ""),
        ))
    logger.success(f"[API] GET /chat/trash - Success: returned {len(result)} items")
    return result


@router.post("/trash/{conv_id}/restore")
async def restore_conversation(conv_id: str):
    logger.info(f"[API] POST /chat/trash/{conv_id}/restore - Restoring conversation")
    conversation_store.restore(conv_id)
    logger.success(f"[API] POST /chat/trash/{conv_id}/restore - Restored")
    return {"error": None, "data": {"restored": True}}


@router.delete("/trash/{conv_id}")
async def permanent_delete_conversation(conv_id: str):
    logger.info(f"[API] DELETE /chat/trash/{conv_id} - Permanent deleting conversation")
    conversation_store.permanent_delete(conv_id)
    logger.success(f"[API] DELETE /chat/trash/{conv_id} - Permanently deleted")
    return {"error": None, "data": {"deleted": True}}


@router.delete("/trash")
async def empty_trash(agent_id: str | None = None):
    logger.info(f"[API] DELETE /chat/trash - Emptying trash, agent_id={agent_id}")
    count = conversation_store.empty_trash(agent_id)
    logger.success(f"[API] DELETE /chat/trash - Emptied {count} items")
    return {"error": None, "data": {"deleted_count": count}}


@router.post("/trash/batch-restore")
async def batch_restore(request: BatchIdsRequest):
    logger.info(f"[API] POST /chat/trash/batch-restore - Restoring {len(request.ids)} items")
    count = conversation_store.batch_restore(request.ids)
    logger.success(f"[API] POST /chat/trash/batch-restore - Restored {count} items")
    return {"error": None, "data": {"restored_count": count}}


@router.post("/trash/batch-delete")
async def batch_permanent_delete(request: BatchIdsRequest):
    logger.info(f"[API] POST /chat/trash/batch-delete - Deleting {len(request.ids)} items")
    count = conversation_store.batch_permanent_delete(request.ids)
    logger.success(f"[API] POST /chat/trash/batch-delete - Deleted {count} items")
    return {"error": None, "data": {"deleted_count": count}}


@router.post("/conversations/batch-delete")
async def batch_soft_delete(request: BatchIdsRequest):
    logger.info(f"[API] POST /chat/conversations/batch-delete - Moving {len(request.ids)} to trash")
    count = conversation_store.batch_soft_delete(request.ids)
    logger.success(f"[API] POST /chat/conversations/batch-delete - Moved {count} to trash")
    return {"error": None, "data": {"deleted_count": count}}


# ── TTS 语音合成 ──────────────────────────────────────────────

class TTSRequest(BaseModel):
    text: str = Field(..., max_length=2000)
    voice: str = Field(default="default")


@router.post("/tts/synthesize")
async def tts_synthesize(request: TTSRequest):
    if not request.text.strip():
        return JSONResponse({"error": "text is required"}, status_code=400)

    try:
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
                            all_messages: list, provider: str, model: str,
                            agent_id: str | None, state: dict, start_time: float):
    chat_id = str(uuid.uuid4())

    async def generator():
        suggested_questions: list[str] = []
        try:
            async with _llm_semaphore:
                async for chunk in llm_adapter.chat_stream(
                    messages=all_messages, provider_name=provider, model=model,
                    temperature=request.temperature or 0.7,
                    max_tokens=request.max_tokens or 4096, top_p=request.top_p or 0.9,
                ):
                    content = chunk.data.get("content", "")
                    rc = chunk.data.get("reasoning", "")
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
                persist_state = dict(state)
                if persist_state["aborted"] and persist_state["content"].startswith("[Error]"):
                    persist_state["content"] = ""
                _PHASE_3_SAVE_ASSISTANT_MSG(conv, persist_state)
                _persist_conv(conv_id, conv)
            except Exception as persist_err:
                logger.error(f"[STREAM] Persist failed: conv={conv_id}, error={persist_err}")

            # 异步生成推荐问题（不持久化，只在 SSE 中推送）
            if not state["aborted"] and state["content"]:
                try:
                    suggested_questions = await _generate_suggestions_for_conv(
                        conv_id=conv_id,
                        messages=[dict(m) for m in conv["messages"]],
                        agent_id=agent_id,
                        provider=provider,
                        model=model,
                    )
                except Exception as sq_err:
                    logger.warning(f"[STREAM] Suggested questions failed: conv={conv_id}, error={sq_err}")

            try:
                yield _sse_done(chat_id, provider, model, suggested_questions or None)
            except Exception as done_err:
                logger.debug(f"[STREAM] Done event send failed (client may have disconnected): {done_err}")
            try:
                _schedule_memory_update([dict(m) for m in conv["messages"]], conv_id, agent_id)
            except Exception as schedule_err:
                logger.warning(f"[STREAM] Memory update scheduling failed: {schedule_err}")

    return StreamingResponse(generator(), media_type="text/event-stream",
                           headers={"Cache-Control": "no-cache", "Connection": "keep-alive",
                                   "X-Accel-Buffering": "no"})


def _sse(cid: str, content: str, provider: str, model: str, reasoning: str = "") -> str:
    return f"data: {ChatStreamChunk(id=cid, content=content, reasoning_content=reasoning, model=model, provider=provider).model_dump_json()}\n\n"

def _sse_done(cid: str, provider: str, model: str, suggested_questions: list[str] | None = None) -> str:
    return f"data: {ChatStreamChunk(id=cid, content='', model=model, provider=provider, done=True, suggested_questions=suggested_questions).model_dump_json()}\n\n"
