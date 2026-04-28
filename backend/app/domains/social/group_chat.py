import asyncio
import uuid
import json
from datetime import datetime, timezone
from typing import AsyncIterator
from loguru import logger

from app.infrastructure.database.json_store import groups_store, agents_store
from app.runtime.provider.llm.adapter import llm_adapter


def to_camel_case(data: dict) -> dict:
    out = {}
    for k, v in data.items():
        parts = k.split("_")
        camel = parts[0] + "".join(p.capitalize() for p in parts[1:])
        if isinstance(v, dict):
            v = to_camel_case(v)
        elif isinstance(v, list):
            v = [to_camel_case(i) if isinstance(i, dict) else i for i in v]
        out[camel] = v
    return out


class GroupChatManager:
    async def send_group_message_stream(
        self,
        group_id: str,
        sender_id: str,
        sender_type: str,
        content: str,
    ) -> AsyncIterator[dict]:
        group = groups_store.get(group_id)
        if not group:
            yield {"type": "error", "data": {"message": f"Group {group_id} not found"}}
            return

        now = datetime.now(timezone.utc).isoformat()
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

        tasks = []
        for member in ai_members:
            tasks.append(self._respond_as_agent(group, member, content, recent_context))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            member = ai_members[i]
            if isinstance(result, Exception):
                now = datetime.now(timezone.utc).isoformat()
                error_msg = {
                    "id": str(uuid.uuid4()),
                    "sender_id": member.get("agent_id", "agent"),
                    "sender_name": member.get("name", "Agent"),
                    "sender_type": "agent",
                    "content": f"[响应失败: {str(result)[:100]}]",
                    "timestamp": now,
                    "role": member.get("role", ""),
                }
                yield {
                    "type": "agent_error",
                    "data": to_camel_case(error_msg),
                }
            else:
                yield {
                    "type": "agent_message",
                    "data": to_camel_case(result),
                }

        group = groups_store.get(group_id)
        if group:
            for result in results:
                if not isinstance(result, Exception) and result:
                    if "messages" not in group:
                        group["messages"] = []
                    group["messages"].append(result)
            group["updated_at"] = datetime.now(timezone.utc).isoformat()
            groups_store.set(group_id, group)

        yield {"type": "agents_done", "data": {}}

    async def _respond_as_agent(
        self,
        group: dict,
        member: dict,
        user_message: str,
        recent_context: str,
    ) -> dict:
        agent = agents_store.get(member.get("agent_id", ""))
        if not agent or not agent.get("is_active", True):
            raise ValueError(f"Agent {member.get('agent_id')} not found or inactive")

        provider_name = self._resolve_provider(agent)
        if not provider_name:
            raise ValueError(f"No available provider for agent {agent.get('name')}")

        model = self._resolve_model(agent, provider_name)

        system_prompt = self._build_agent_prompt(agent, member, group)
        messages = [
            {"role": "system", "content": system_prompt},
        ]

        if recent_context:
            messages.append({"role": "system", "content": f"近期对话上下文:\n{recent_context}"})

        messages.append({"role": "user", "content": user_message})

        logger.info(f"[GroupChat] Calling LLM for agent {agent['name']}: provider={provider_name}, model={model}")

        result = await llm_adapter.chat(
            messages=messages,
            provider_name=provider_name,
            model=model,
            temperature=0.7,
            max_tokens=500,
        )

        response_content = result.content if hasattr(result, "content") else str(result)

        now = datetime.now(timezone.utc).isoformat()
        return {
            "id": str(uuid.uuid4()),
            "sender_id": agent["id"],
            "sender_name": agent["name"],
            "sender_type": "agent",
            "content": response_content,
            "timestamp": now,
            "role": member.get("role", ""),
        }

    def _resolve_provider(self, agent: dict) -> str:
        agent_provider = agent.get("provider", "")
        if agent_provider and agent_provider in llm_adapter.providers:
            return agent_provider
        if llm_adapter.default_provider in llm_adapter.providers:
            return llm_adapter.default_provider
        for provider_key in llm_adapter.providers:
            return provider_key
        return ""

    def _resolve_model(self, agent: dict, provider_name: str) -> str:
        agent_model = agent.get("model", "")
        if agent_model:
            return agent_model
        provider = llm_adapter.providers.get(provider_name)
        if provider:
            return provider.default_model
        return ""

    @staticmethod
    def _build_recent_context(group: dict, max_messages: int = 10) -> str:
        messages = group.get("messages", [])
        if not messages:
            return ""
        recent = messages[-max_messages:]
        context_lines = []
        for msg in recent:
            sender_type = msg.get("sender_type", "user")
            sender_name = msg.get("sender_name", "用户" if sender_type == "user" else "Agent")
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
5. 始终使用中文回复"""

        if agent.get("system_prompt"):
            prompt += f"\n\n额外指令：{agent['system_prompt']}"

        return prompt
