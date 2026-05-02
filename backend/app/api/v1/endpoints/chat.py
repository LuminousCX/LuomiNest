import asyncio
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
from app.engines.memory.core import (
    get_memory_storage,
    MemoryUpdater,
    MemoryInjector,
)
from app.core.config import settings

router = APIRouter(prefix="/chat", tags=["chat"])

_skill_executor = SkillExecutor()


def _inject_memory_to_messages(
    messages: list[dict], 
    agent_id: str | None, 
    conversation_id: str | None = None,
    user_query: str = "",
) -> list[dict]:
    try:
        storage = get_memory_storage()
        
        # 确保会话之间的记忆隔离：优先使用 conversation_id，其次是 agent_id
        memory_key = conversation_id or agent_id
        
        # 加载记忆
        memory_data = storage.load(memory_key)
        
        # 如果是新对话，初始化工作记忆
        if conversation_id and not memory_data.working_memory.core_goal:
            # 从用户的第一条消息提取核心目标
            for msg in reversed(messages):
                if msg.get("role") == "user" and msg.get("content"):
                    memory_data.working_memory.set_core_goal(msg["content"][:200])
                    break
        
        # 更新工作记忆中的最近对话
        for msg in messages[-3:]:
            if msg.get("role") in ["user", "assistant"] and msg.get("content"):
                memory_data.working_memory.add_conversation(
                    msg["role"], 
                    msg["content"][:500]
                )
        
        # 归档过期记忆
        memory_data.archive_expired_facts()
        
        # 保存更新后的记忆
        if memory_key:
            storage.save(memory_data, memory_key)
        
        injector = MemoryInjector(conversation_id=conversation_id)
        
        profile = memory_data.profile
        logger.info(f"[Memory] Injecting memory for conversation_id={conversation_id}, agent_id={agent_id}")
        logger.info(f"[Memory] Profile: name={profile.name}, occupation={profile.occupation}, location={profile.location}")
        
        result = injector.inject_memory_to_messages(messages, memory_data, user_query=user_query)
        logger.info(f"[Memory] Memory injection completed, messages count: {len(result)}")
        return result
    except Exception as e:
        logger.warning(f"[Memory] Failed to inject memory: {e}")
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


def _build_system_prompt_with_tools(agent_id: str | None) -> str:
    agent_name = "AI助手"
    agent_description = "一个友好、智能的AI助手"
    base_prompt = ""
    
    if agent_id:
        agent = agents_store.get(agent_id)
        if agent:
            agent_name = agent.get("name", agent_name)
            agent_description = agent.get("description", agent_description)
            if agent.get("system_prompt"):
                base_prompt = agent["system_prompt"]

    identity_prompt = f"""【身份设定】
你的名字是「{agent_name}」，{agent_description}。

【核心规则 - 必须严格遵守】

规则1：当用户询问AI身份时（如"你是谁""你叫什么名字"）
- 回答你自己的身份
- 示例："你好！我是{agent_name}，{agent_description}。很高兴为你服务！"
- 绝对禁止反问用户"你是谁"

规则2：当用户询问用户自己的身份时（如"我是谁""你知道我是谁吗""我是谁"）
- 查看<user_memory>中的用户档案
- 如果有档案："你是[姓名]，[职业]，来自[所在地]..."
- 如果没有档案："我还不太了解你呢，你愿意介绍一下自己吗？"

规则3：其他情况
- 正常回答用户的问题
- 不要重复用户的话

"""
    base_prompt = identity_prompt + base_prompt

    available_skills = SkillRegistry.list_skills()
    if not available_skills:
        return base_prompt

    core_rules = """【工具调用核心规则 - 必须严格遵守】

1. 触发必要性：仅当用户明确提出对应需求时，才可以调用对应工具。禁止预判、猜测用户需求，无差别触发工具。
   - 例如：用户说"明天想去北京"，这是出行表达，不是天气查询需求，绝对不允许触发天气工具
   - 只有用户明确说"明天去北京天气怎么样""去北京要带什么衣服"等，才能触发天气工具

2. 前置校验：调用任何工具前，必须先校验请求参数是否合法、功能是否可用。不合法/不可用时，直接使用用户友好的兜底话术，禁止暴露任何内部信息。

3. 结果封装：工具返回的结果，必须转化为通顺自然的口语化中文输出给用户。禁止直接输出接口原始数据、参数、报错代码、JSON格式。

4. 对话优先：永远先回应用户的核心表达，再处理工具调用需求。禁止跳过用户的对话内容，直接执行工具调用。

5. 信息隔离：禁止向用户输出任何工具调用的参数、代码、报错信息、系统内部状态。所有给用户的回复，必须是通顺自然的口语化中文，不得出现任何用户看不懂的技术内容。

"""

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

    tools_section += """## 工具调用格式

当需要使用工具时，请在回复中使用以下XML格式：

<tool_call name="工具名">
{"param1": "value1"}
</tool_call

注意：结束标签是 </tool_call（没有方括号）

如果工具不需要参数，可以使用空对象：
<tool_call name="工具名">
{}
</tool_call

## 工具调用示例

用户：明天去北京，天气怎么样？
助手：<tool_call name="web_search">
{"query": "北京明天天气"}
</tool_call

用户：我明天想去北京
助手：明天去北京呀，提前祝你出行顺利~ 要是需要我帮你查天气、交通攻略、游玩推荐之类的，随时告诉我哦

如果不需要使用工具，直接回复用户即可。
"""

    return core_rules + base_prompt + tools_section


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
        tool_name = call.get("name", "unknown")
        if not isinstance(call.get("arguments"), dict):
            results.append({
                "tool": tool_name,
                "result": "参数格式错误，请检查工具调用格式。",
                "status": "error",
            })
            continue
        try:
            skill_data = SkillRegistry.get_skill(tool_name)
            if not skill_data or not skill_data.get("is_active", True):
                results.append({
                    "tool": tool_name,
                    "result": "该功能暂时不可用，请稍后再试或尝试其他方式。",
                    "status": "error",
                })
                continue

            result = await _skill_executor.execute(
                skill_name=tool_name,
                arguments=call["arguments"],
                agent_id=agent_id,
            )
            results.append({
                "tool": tool_name,
                "result": result,
                "status": "success",
            })
        except Exception as e:
            logger.error(f"[ToolExecutor] Tool execution failed: {tool_name}, error: {e}", exc_info=True)
            error_msg = (
                f"功能执行遇到问题：{str(e)}"
                if settings.DEBUG
                else "功能执行遇到问题，请稍后再试，或尝试用其他方式描述您的需求。"
            )
            results.append({
                "tool": tool_name,
                "result": error_msg,
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

    # 提取用户查询用于记忆检索
    user_query = ""
    for m in reversed(request.messages):
        if m.role == "user":
            user_query = m.content
            break

    messages = _inject_memory_to_messages(
        messages, 
        request.agent_id, 
        conversation_id=None,
        user_query=user_query
    )
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

        thread_id = str(uuid.uuid4())
        conversation_messages = [
            {"role": m.role, "content": m.content} for m in request.messages
        ] + [{"role": "assistant", "content": result}]
        _schedule_memory_update(conversation_messages, thread_id, request.agent_id)

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
    final_answer = ""

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
            tool_result_text = "\n\n".join(
                f"[Tool: {r['tool']}] {r['result']}" for r in tool_results
            )
            messages.append({"role": "assistant", "content": full_content})
            messages.append({"role": "user", "content": f"工具执行结果：\n{tool_result_text}\n\n请基于以上工具结果回答用户的问题。"})

            async for chunk in llm_adapter.chat_stream(
                messages=messages,
                provider_name=provider,
                model=model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                top_p=request.top_p,
            ):
                final_answer += chunk
                chunk_count += 1
                data = ChatStreamChunk(
                    id=chat_id,
                    content=chunk,
                    model=model,
                    provider=provider,
                )
                yield f"data: {data.model_dump_json()}\n\n"
        else:
            final_answer = full_content

        done_data = ChatStreamChunk(
            id=chat_id,
            content="",
            model=model,
            provider=provider,
            done=True,
        )
        yield f"data: {done_data.model_dump_json()}\n\n"

        conversation_messages = [
            {"role": m.role, "content": m.content} for m in request.messages
        ] + [{"role": "assistant", "content": final_answer}]
        _schedule_memory_update(conversation_messages, chat_id, request.agent_id)

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

    # 获取用户的新消息（最后一条用户消息）
    last_user_msg = None
    for m in reversed(request.messages):
        if m.role == "user":
            last_user_msg = m
            break
    
    # 保存用户消息到对话历史
    if last_user_msg:
        msg_entry = {"role": "user", "content": last_user_msg.content}
        if not conv["messages"] or conv["messages"][-1] != msg_entry:
            conv["messages"].append(msg_entry)
            logger.debug(f"[API] POST /chat/conversations/{conv_id}/messages - Added user message")
    
    conv["updated_at"] = datetime.now(timezone.utc).isoformat()

    resolved_provider = request.provider or conv.get("provider") or llm_adapter.default_provider
    resolved_model = request.model or conv.get("model") or llm_adapter.get_provider(resolved_provider).default_model

    # 构建发送给LLM的消息列表
    system_prompt = _build_system_prompt_with_tools(conv.get("agent_id"))
    all_messages = []
    if system_prompt:
        all_messages.append({"role": "system", "content": system_prompt})
    
    # 使用对话历史中的消息（已经包含刚添加的用户消息）
    for m in conv["messages"]:
        all_messages.append({"role": m["role"], "content": m["content"]})

    # 提取用户查询用于记忆检索
    user_query = ""
    if last_user_msg:
        user_query = last_user_msg.content

    all_messages = _inject_memory_to_messages(
        all_messages, 
        conv.get("agent_id"), 
        conversation_id=conv_id,
        user_query=user_query
    )

    if request.stream:
        logger.info(f"[API] POST /chat/conversations/{conv_id}/messages - Starting stream response")

        async def stream_with_save():
            tool_draft = ""
            final_answer = ""
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
                    tool_draft += chunk
                    chunk_count += 1

                tool_calls = _parse_tool_calls(tool_draft)
                if tool_calls:
                    tool_results = await _execute_tool_calls(tool_calls, conv.get("agent_id"))
                    tool_result_text = "\n\n".join(
                        f"[Tool: {r['tool']}] {r['result']}" for r in tool_results
                    )
                    all_messages.append({"role": "assistant", "content": tool_draft})
                    all_messages.append({"role": "user", "content": f"工具执行结果：\n{tool_result_text}\n\n请基于以上工具结果回答用户的问题。"})

                    async for chunk in llm_adapter.chat_stream(
                        messages=all_messages,
                        provider_name=resolved_provider,
                        model=resolved_model,
                        temperature=request.temperature,
                        max_tokens=request.max_tokens,
                        top_p=request.top_p,
                    ):
                        final_answer += chunk
                        chunk_count += 1
                        data = ChatStreamChunk(
                            id=chat_id,
                            content=chunk,
                            model=resolved_model,
                            provider=resolved_provider,
                        )
                        yield f"data: {data.model_dump_json()}\n\n"
                else:
                    final_answer = tool_draft
                    for i in range(0, len(final_answer), 10):
                        chunk = final_answer[i:i+10]
                        data = ChatStreamChunk(
                            id=chat_id,
                            content=chunk,
                            model=resolved_model,
                            provider=resolved_provider,
                        )
                        yield f"data: {data.model_dump_json()}\n\n"

                done_data = ChatStreamChunk(
                    id=chat_id,
                    content="",
                    model=resolved_model,
                    provider=resolved_provider,
                    done=True,
                )
                yield f"data: {done_data.model_dump_json()}\n\n"

                # 检查最后一条消息是否已经是助手回复，避免重复
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

    # 检查最后一条消息是否已经是助手回复，避免重复
    assistant_msg = {"role": "assistant", "content": result}
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
    logger.success(f"[API] POST /chat/conversations/{conv_id}/messages - Success: elapsed={elapsed:.2f}s, response_len={len(result)}")

    return ChatResponse(
        id=str(uuid.uuid4()),
        content=result,
        model=resolved_model,
        provider=resolved_provider,
    )
