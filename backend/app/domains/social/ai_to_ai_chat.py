import uuid
import time
from datetime import datetime, timezone
from loguru import logger

from app.infrastructure.database.json_store import agents_store
from app.runtime.provider.llm.adapter import llm_adapter


class AIToAIChat:
    @staticmethod
    async def converse(
        agent_a_id: str,
        agent_b_id: str,
        topic: str,
        rounds: int = 3,
    ) -> list[dict]:
        agent_a = agents_store.get(agent_a_id)
        agent_b = agents_store.get(agent_b_id)
        if not agent_a or not agent_b:
            return []

        messages_log = []
        current_speaker = agent_a
        current_listener = agent_b
        conversation = []

        conversation.append({"role": "user", "content": f"话题：{topic}"})

        for round_num in range(rounds):
            try:
                system_prompt = f"""你是 {current_speaker['name']}。{current_speaker.get('description', '')}

你正在和 {current_listener['name']} 讨论：{topic}

{current_listener['name']}的简介：{current_listener.get('description', '')}

请简洁地表达你的观点，回应对方。"""

                conv_messages = [{"role": "system", "content": system_prompt}] + conversation[-6:]

                provider = current_speaker.get("provider") or llm_adapter.default_provider
                model = current_speaker.get("model")

                result = await llm_adapter.chat(
                    messages=conv_messages,
                    provider_name=provider,
                    model=model,
                    temperature=0.8,
                    max_tokens=300,
                )

                response_content = result.content if hasattr(result, 'content') else str(result)

                now = datetime.now(timezone.utc).isoformat()
                messages_log.append({
                    "id": str(uuid.uuid4()),
                    "sender_id": current_speaker["id"],
                    "sender_name": current_speaker["name"],
                    "content": response_content,
                    "timestamp": now,
                    "round": round_num + 1,
                })

                conversation.append({"role": "assistant", "content": response_content})
                conversation.append({"role": "user", "content": f"[{current_listener['name']}的回应]"})

                current_speaker, current_listener = current_listener, current_speaker

            except Exception as e:
                logger.error(f"[AIToAI] Round {round_num + 1} failed: {e}")
                break

        return messages_log
