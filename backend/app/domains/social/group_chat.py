import uuid
import time
from datetime import datetime, timezone
from loguru import logger

from app.infrastructure.database.json_store import groups_store, agents_store
from app.runtime.provider.llm.adapter import llm_adapter


class GroupChatManager:
    async def send_group_message(
        self,
        group_id: str,
        sender_id: str,
        sender_type: str,
        content: str,
    ) -> list[dict]:
        group = groups_store.get(group_id)
        if not group:
            return []

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

        if sender_type == "user":
            return await self._trigger_agent_responses(group, content, sender_id)

        return [message]

    async def _trigger_agent_responses(self, group: dict, user_message: str, sender_id: str) -> list[dict]:
        responses = []
        members = group.get("members", [])
        ai_members = [m for m in members if m.get("type") == "agent"]

        for member in ai_members:
            agent = agents_store.get(member["agent_id"])
            if not agent or not agent.get("is_active", True):
                continue

            try:
                system_prompt = self._build_agent_prompt(agent, member, group, user_message)
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ]

                provider = agent.get("provider") or llm_adapter.default_provider
                model = agent.get("model")

                result = await llm_adapter.chat(
                    messages=messages,
                    provider_name=provider,
                    model=model,
                    temperature=0.7,
                    max_tokens=500,
                )

                now = datetime.now(timezone.utc).isoformat()
                response_msg = {
                    "id": str(uuid.uuid4()),
                    "sender_id": agent["id"],
                    "sender_name": agent["name"],
                    "sender_type": "agent",
                    "content": result,
                    "timestamp": now,
                    "role": member.get("role", ""),
                }

                group["messages"].append(response_msg)
                responses.append(response_msg)

            except Exception as e:
                logger.error(f"[GroupChat] Agent {agent.get('name')} failed: {e}")

        groups_store.set(group["id"], group)
        return responses

    @staticmethod
    def _build_agent_prompt(agent: dict, member: dict, group: dict, user_message: str) -> str:
        role = member.get("role", "成员")
        group_name = group.get("name", "")
        group_desc = group.get("description", "")

        other_members = []
        for m in group.get("members", []):
            if m.get("agent_id") != agent["id"]:
                other_a = agents_store.get(m.get("agent_id", ""))
                if other_a:
                    other_members.append(f"{other_a['name']}({m.get('role', '成员')})")

        members_text = "、".join(other_members) if other_members else "无"

        prompt = f"""你是 {agent['name']}，在群组「{group_name}」中的角色是：{role}。

群组描述：{group_desc}

其他群成员：{members_text}

你的个性设定：{agent.get('description', '')}

请以你的角色定位回应群聊中的消息。保持简洁，符合你的角色特征。不要重复其他成员已说过的内容。"""

        if agent.get("system_prompt"):
            prompt += f"\n\n额外指令：{agent['system_prompt']}"

        return prompt
