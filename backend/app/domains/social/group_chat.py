import json
import uuid
from collections.abc import AsyncIterator
from loguru import logger

from app.core.tools import tool_registry
from app.core.tools.orchestrator import tool_orchestrator
from app.core.utils import utc_now, to_camel_case
from app.domains.social.agent_orchestrator import resolve_provider, resolve_model
from app.infrastructure.database.json_store import groups_store, agents_store
from app.runtime.provider.llm.adapter import llm_adapter
from app.runtime.provider.llm.types import RouteHint
from app.services.avatar_manager import EmotionStreamParser, strip_emotion_tags


# 群聊 Agent 可用工具白名单（仅只读 + memory_search，禁止写操作/子 Agent/集群调用）
GROUP_CHAT_TOOL_WHITELIST = frozenset({
    "memory_search",
    "read_file",
    "list_files",
    "search_files",
})


class GroupChatManager:
    async def send_group_message_stream(
        self,
        group_id: str,
        sender_id: str,
        sender_type: str,
        content: str,
    ) -> AsyncIterator[dict]:
        """向群组发送消息并以 SSE 事件流形式返回响应（串行时间线 + 流式 + 工具循环）。

        群聊语义（参考 综合调查.md §5 群聊改造）：
        - 多个 Agent 串行响应（一个说完，另一个再获取上下文接话）
        - 每个 Agent 流式输出（agent_message_delta 逐 token 推送）
        - 可用工具白名单（memory_search 主动查主 Agent 记忆 + 只读文件工具）
        - 不支持子 Agent / 集群调用 / 协作模式

        事件类型：user_message, agents_start, agent_message_start, agent_message_delta,
                  agent_message_end, agent_error, agents_done, info, error
        """
        group = groups_store.get(group_id)
        if not group:
            yield {"type": "error", "data": {"message": f"Group {group_id} not found"}}
            return

        now = utc_now()
        message = {
            "id": str(uuid.uuid4()),
            "sender_id": sender_id,
            "sender_type": sender_type,
            "content": content,
            "timestamp": now,
        }

        if "messages" not in group:
            group["messages"] = []
        group["messages"].append(message)
        group["updated_at"] = now
        groups_store.set(group_id, group)

        yield {
            "type": "user_message",
            "data": to_camel_case(message),
        }

        if sender_type != "user":
            return

        members = group.get("members", [])
        ai_members = [m for m in members if m.get("type") == "agent"]

        if not ai_members:
            yield {
                "type": "info",
                "data": {"message": "群组中没有 AI 成员，请先添加 Agent"},
            }
            return

        yield {
            "type": "agents_start",
            "data": to_camel_case({
                "agent_count": len(ai_members),
                "agent_names": [m.get("name", "Agent") for m in ai_members],
            }),
        }

        recent_context = self._build_recent_context(group)

        for member in ai_members:
            persist_msg: dict | None = None
            try:
                async for event in self._respond_as_agent_stream(
                    group, member, content, recent_context,
                ):
                    yield event
                    if event["type"] in ("agent_message_end", "agent_error"):
                        persist_msg = event["data"]

                if persist_msg:
                    fresh_group = groups_store.get(group_id)
                    if fresh_group:
                        if "messages" not in fresh_group:
                            fresh_group["messages"] = []
                        fresh_group["messages"].append(persist_msg)
                        fresh_group["updated_at"] = utc_now()
                        groups_store.set(group_id, fresh_group)
                        # 更新 recent_context，让下一个 Agent 能看到本轮回复
                        recent_context = self._build_recent_context(fresh_group)

            except Exception as e:
                logger.error(f"[GroupChat] Agent {member.get('name')} 响应异常: {e}", exc_info=True)
                now_err = utc_now()
                error_msg = {
                    "id": str(uuid.uuid4()),
                    "sender_id": member.get("agent_id", "agent"),
                    "sender_name": member.get("name", "Agent"),
                    "sender_type": "agent",
                    "content": f"[响应失败: {str(e)[:100]}]",
                    "timestamp": now_err,
                    "role": member.get("role", ""),
                }
                yield {
                    "type": "agent_error",
                    "data": to_camel_case(error_msg),
                }

        yield {"type": "agents_done", "data": {}}

    async def _respond_as_agent_stream(
        self,
        group: dict,
        member: dict,
        user_message: str,
        recent_context: str,
    ) -> AsyncIterator[dict]:
        """单个 Agent 的流式响应（带工具循环）。

        群聊 Agent 响应流程：
        1. yield agent_message_start（通知前端 Agent 开始响应）
        2. 设置 memory_access = read_main（允许查主 Agent 记忆）
        3. 工具循环：LLM 流式输出 → 收集 tool_calls → 执行工具 → 继续下一轮
        4. yield agent_message_delta（逐 token 内容）
        5. yield agent_message_end（最终完整内容，供持久化）
        """
        agent = agents_store.get(member.get("agent_id", ""))
        if not agent or not agent.get("is_active", True):
            now = utc_now()
            yield {
                "type": "agent_error",
                "data": to_camel_case({
                    "id": str(uuid.uuid4()),
                    "sender_id": member.get("agent_id", "agent"),
                    "sender_name": member.get("name", "Agent"),
                    "sender_type": "agent",
                    "content": f"[Agent {member.get('name', '未知')} 不可用或未激活]",
                    "timestamp": now,
                    "role": member.get("role", ""),
                }),
            }
            return

        provider_name = resolve_provider(agent)
        if not provider_name:
            now = utc_now()
            yield {
                "type": "agent_error",
                "data": to_camel_case({
                    "id": str(uuid.uuid4()),
                    "sender_id": agent["id"],
                    "sender_name": agent["name"],
                    "sender_type": "agent",
                    "content": "[无可用 LLM Provider]",
                    "timestamp": now,
                    "role": member.get("role", ""),
                }),
            }
            return

        model = resolve_model(agent, provider_name)

        message_id = str(uuid.uuid4())
        start_time = utc_now()

        yield {
            "type": "agent_message_start",
            "data": to_camel_case({
                "id": message_id,
                "sender_id": agent["id"],
                "sender_name": agent["name"],
                "sender_type": "agent",
                "content": "",
                "timestamp": start_time,
                "role": member.get("role", ""),
            }),
        }

        # 记忆访问权限由 MemoryAccessMiddleware 通过 ctx.extra["memory_access"] 处理

        parser = EmotionStreamParser()

        try:
            from app.core.agents.middleware.base import AgentContext
            from app.core.agents.memory_access import MEMORY_ACCESS_READ_MAIN

            system_prompt = self._build_agent_prompt(agent, member, group)
            working_messages: list[dict] = [
                {"role": "system", "content": system_prompt},
            ]
            if recent_context:
                working_messages.append({
                    "role": "system",
                    "content": f"近期对话上下文:\n{recent_context}",
                })
            working_messages.append({"role": "user", "content": user_message})

            # 工具配置：白名单过滤
            available_tools = self._get_group_chat_tools()
            use_tools = bool(available_tools) and llm_adapter.supports_tool_calls(provider_name, model)
            if available_tools and not use_tools:
                logger.info(
                    f"[GroupChat] Agent {agent['name']}: Provider {provider_name}/{model} "
                    f"不支持工具调用，纯对话模式"
                )

            ctx = AgentContext(
                messages=working_messages,
                tools=available_tools if use_tools else None,
                route_hint=RouteHint.CHAT,
                state={"chat_id": message_id, "provider": provider_name, "model": model},
                extra={
                    "scene": "chat",
                    "is_stream": True,
                    "memory_access": MEMORY_ACCESS_READ_MAIN,
                    "agent_id": agent.get("id"),
                },
            )

            # llm_call_fn：流式调用 LLM，content 经 EmotionStreamParser 清洗
            async def llm_call_fn(ctx):
                async for chunk in llm_adapter.chat_stream(
                    messages=ctx.messages,
                    tools=ctx.tools,
                    provider_name=provider_name,
                    model=model,
                    temperature=0.7,
                    max_tokens=500,
                    route_hint=RouteHint.CHAT,
                ):
                    if chunk.type == "content":
                        raw_content = chunk.data.get("content", "")
                        clean_content, _emotion = parser.feed(raw_content)
                        chunk.data["content"] = clean_content
                    yield chunk

            runner = tool_orchestrator.create_runner({"scene": "chat", "is_stream": True})

            async for sse_str in runner.run_stream(ctx, llm_call_fn):
                chunk_data = json.loads(sse_str[len("data: "):-2])
                content = chunk_data.get("content", "")
                # 跳过错误内容（aborted 时 runner 会 yield "[Error]..." content）
                if content and not ctx.state.get("aborted"):
                    yield {
                        "type": "agent_message_delta",
                        "data": to_camel_case({
                            "id": message_id,
                            "content": content,
                        }),
                    }

            # 流式结束后：检查是否异常终止
            if ctx.state.get("aborted"):
                error_content = ctx.state.get("content", "")
                err_time = utc_now()
                yield {
                    "type": "agent_error",
                    "data": to_camel_case({
                        "id": message_id,
                        "sender_id": agent["id"],
                        "sender_name": agent["name"],
                        "sender_type": "agent",
                        "content": f"[响应中断: {error_content[:100]}]" if error_content else "[响应中断]",
                        "timestamp": err_time,
                        "role": member.get("role", ""),
                    }),
                }
                return

            # 最终内容（兜底过滤情绪标签）
            full_content = ctx.state.get("content", "")
            final_content = strip_emotion_tags(full_content) if full_content else "[无响应内容]"

            end_time = utc_now()
            yield {
                "type": "agent_message_end",
                "data": to_camel_case({
                    "id": message_id,
                    "sender_id": agent["id"],
                    "sender_name": agent["name"],
                    "sender_type": "agent",
                    "content": final_content,
                    "timestamp": end_time,
                    "role": member.get("role", ""),
                }),
            }

        except Exception as e:
            logger.error(f"[GroupChat] Agent {agent.get('name', '未知')} 流式响应异常: {e}", exc_info=True)
            err_time = utc_now()
            yield {
                "type": "agent_error",
                "data": to_camel_case({
                    "id": message_id,
                    "sender_id": agent.get("id", "agent"),
                    "sender_name": agent.get("name", "Agent"),
                    "sender_type": "agent",
                    "content": f"[响应失败: {str(e)[:100]}]",
                    "timestamp": err_time,
                    "role": member.get("role", ""),
                }),
            }

    def _get_group_chat_tools(self) -> list[dict]:
        """获取群聊可用工具列表（白名单过滤）"""
        if not tool_registry.list_names():
            return []
        all_tools = tool_orchestrator.get_tools_for_llm()
        return [
            t for t in all_tools
            if t.get("function", {}).get("name") in GROUP_CHAT_TOOL_WHITELIST
        ]

    @staticmethod
    def _build_recent_context(group: dict, max_messages: int = 10) -> str:
        """构建近期对话上下文（兼容 camelCase 与 snake_case 消息格式）"""
        messages = group.get("messages", [])
        if not messages:
            return ""
        recent = messages[-max_messages:]
        context_lines = []
        for msg in recent:
            sender_type = msg.get("sender_type") or msg.get("senderType") or "user"
            sender_name = msg.get("sender_name") or msg.get("senderName")
            if not sender_name:
                sender_name = "用户" if sender_type == "user" else "Agent"
            content = msg.get("content", "")
            context_lines.append(f"{sender_name}: {content}")
        return "\n".join(context_lines)

    @staticmethod
    def _build_agent_prompt(agent: dict, member: dict, group: dict) -> str:
        role = member.get("role", "成员")
        group_name = group.get("name", "")
        group_desc = group.get("description", "")
        member_count = len(group.get("members", []))

        other_members = []
        for m in group.get("members", []):
            if m.get("agent_id") != agent["id"]:
                other_a = agents_store.get(m.get("agent_id", ""))
                if other_a:
                    other_members.append(f"{other_a['name']}({m.get('role', '成员')})")

        members_text = "、".join(other_members) if other_members else "无"

        prompt = f"""你是 {agent['name']}，这是 LuomiNest AI 群聊环境。你在群组「{group_name}」中的角色是：{role}。

## 群聊环境信息
- 群组名称：{group_name}
- 群组描述：{group_desc}
- 群组人数：{member_count}
- 其他群成员：{members_text}

## 你的身份
- 名称：{agent['name']}
- 角色定位：{role}
- 个性描述：{agent.get('description', '通用AI助手')}

## 行为准则
1. 以你的角色定位回应群聊中的消息
2. 保持简洁，符合你的角色特征
3. 不要重复其他成员已说过的内容
4. 与其他 Agent 协作配合，发挥各自专长
5. 如需了解用户偏好或历史信息，可调用 memory_search 工具查询主 Agent 记忆
6. 始终使用中文回复"""

        if agent.get("system_prompt"):
            prompt += f"\n\n额外指令：{agent['system_prompt']}"

        return prompt
