import asyncio
import time
import uuid
from datetime import datetime, timezone
from loguru import logger

from app.runtime.platform.base import PlatformMessage, PlatformResponse
from app.runtime.platform.session import (
    MAIN_AGENT_ID,
    get_or_create_conversation,
)
from app.runtime.platform.main_agent_config import (
    load_luominest_main_agent_config,
    resolve_main_agent_provider_model,
)
from app.runtime.platform.registry import get_adapter, increment_message_count
from app.runtime.platform.platform_logger import platform_logger
from app.infrastructure.database.conversation_store import conversation_store
from app.services.context_service import context_service


class LuomiNestPlatformRouter:
    """平台消息路由器：将各平台消息路由到主 Agent，共享主 Agent 的记忆和供应商配置。

    设计要点：
    - 所有平台会话使用 MAIN_AGENT_ID 作为 agent_id，共享主 Agent 记忆
    - 每个平台会话（instance_id + session_id）对应独立的 conversation
    - 复用主 Agent 的 provider/model/system_prompt 配置
    - 支持多模态图片识别（根据模型能力自动判断）
    - 非流式响应（平台消息通常一次性返回）
    """

    def __init__(self) -> None:
        self._processing_locks: dict[str, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

    async def _get_session_lock(self, session_key: str) -> asyncio.Lock:
        if session_key in self._processing_locks:
            return self._processing_locks[session_key]
        async with self._locks_guard:
            if session_key not in self._processing_locks:
                self._processing_locks[session_key] = asyncio.Lock()
            return self._processing_locks[session_key]

    async def handle_platform_message(
        self,
        message: PlatformMessage,
        instance_id: str,
    ) -> PlatformResponse | None:
        """处理来自平台的入站消息，路由到主 Agent 并返回响应。"""
        session_key = f"{instance_id}:{message.session_id or message.user_id}"
        lock = await self._get_session_lock(session_key)

        async with lock:
            try:
                return await self._route_to_main_agent(message, instance_id)
            except Exception as e:
                logger.error(f"[PlatformRouter] Failed to route message from {session_key}: {e}")
                platform_logger.log(
                    instance_id, "error", "route_failed",
                    f"消息路由失败: {e}",
                    adapter_type=message.platform,
                    details={"error": str(e), "session": session_key},
                )
                return PlatformResponse(
                    content=f"[LuomiNest] 消息处理失败，请稍后重试",
                    message_type="text",
                )

    async def _route_to_main_agent(
        self,
        message: PlatformMessage,
        instance_id: str,
    ) -> PlatformResponse | None:
        from app.runtime.provider.llm.adapter import llm_adapter

        start_time = time.time()
        session_id = message.session_id or message.user_id

        conv_id = await get_or_create_conversation(
            instance_id=instance_id,
            session_id=session_id,
            platform_name=message.platform,
            sender_name=message.sender_name,
            is_group=message.is_group,
        )

        conv = await conversation_store.get_async(conv_id)
        if not conv:
            logger.error(f"[PlatformRouter] Conversation {conv_id} not found")
            return None

        provider, model = resolve_main_agent_provider_model()
        main_config = load_luominest_main_agent_config()
        system_prompt = main_config.get("system_prompt", "")
        temperature = main_config.get("temperature", 0.7)
        max_tokens = main_config.get("max_tokens", 4096)

        try:
            provider_inst = llm_adapter.get_provider(provider)
            supports_vision = provider_inst.supports_multimodal(model)
        except Exception:
            supports_vision = False

        platform_context = self._build_platform_context(message)
        full_system = self._assemble_system_prompt(system_prompt, platform_context, message)

        history_messages = self._load_history_messages(conv)
        user_message = self._build_user_message(message, supports_vision)
        messages = [{"role": "system", "content": full_system}] + history_messages + [user_message]

        messages = context_service.inject_timestamp_prompt(messages)
        messages = await context_service.inject_memory(
            messages,
            agent_id=MAIN_AGENT_ID,
            provider_name=provider,
            thread_id=conv_id,
            llm_adapter=llm_adapter,
        )

        self._save_user_message(conv, message, user_message)

        logger.info(
            f"[PlatformRouter] Routing: platform={message.platform}, "
            f"session={session_id}, provider={provider}, model={model}, "
            f"vision={supports_vision}, images={len(message.image_urls)}, "
            f"history={len(history_messages)}"
        )

        try:
            result = await llm_adapter.chat(
                messages=messages,
                stream=False,
                provider_name=provider,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as e:
            logger.error(f"[PlatformRouter] LLM call failed: {e}")
            await self._persist_conv(conv_id, conv)
            return PlatformResponse(
                content=f"[LuomiNest] 模型调用失败：{e}",
                message_type="text",
            )

        assistant_text = self._extract_assistant_text(result)
        self._save_assistant_message(conv, assistant_text, provider, model)
        await self._persist_conv(conv_id, conv)

        increment_message_count(instance_id)
        platform_logger.log(
            instance_id, "info", "message_routed",
            f"消息已路由: {message.sender_name or session_id} -> 主Agent",
            adapter_type=message.platform,
            details={
                "conversation_id": conv_id,
                "provider": provider,
                "model": model,
                "elapsed": round(time.time() - start_time, 2),
            },
        )

        asyncio.create_task(self._schedule_memory_update(messages, conv_id, assistant_text))

        return PlatformResponse(
            content=assistant_text,
            message_type="text",
            reply_to=message.message_id,
        )

    @staticmethod
    def _build_platform_context(message: PlatformMessage) -> str:
        scene = "群聊" if message.is_group else "私聊"
        parts = [
            f"<platform_context>",
            f"当前消息来自平台: {message.platform}",
            f"会话场景: {scene}",
        ]
        if message.sender_name:
            parts.append(f"发送者昵称: {message.sender_name}")
        if message.is_group and message.group_id:
            parts.append(f"群组标识: {message.group_id}")
        parts.append("注意：回复内容需符合该平台的交互习惯，保持简洁自然。")
        parts.append("</platform_context>")
        return "\n".join(parts)

    @staticmethod
    def _assemble_system_prompt(base_prompt: str, platform_context: str, message: PlatformMessage) -> str:
        if not base_prompt:
            base_prompt = "你是 LuomiNest 主控智能体，正在通过外部平台与用户交互。"
        return f"{base_prompt}\n\n{platform_context}"

    @staticmethod
    def _load_history_messages(conv: dict) -> list[dict]:
        history: list[dict] = []
        for msg in conv.get("messages", [])[-20:]:
            role = msg.get("role")
            content = msg.get("content")
            if not role or not content:
                continue
            if isinstance(content, list):
                history.append({"role": role, "content": content})
            else:
                history.append({"role": role, "content": str(content)})
        return history

    @staticmethod
    def _build_user_message(message: PlatformMessage, supports_vision: bool) -> dict:
        text = message.content or ""
        if message.sender_name and message.is_group:
            text = f"{message.sender_name}: {text}" if text else message.sender_name

        if message.image_urls and supports_vision:
            content_parts: list[dict] = []
            if text:
                content_parts.append({"type": "text", "text": text})
            else:
                content_parts.append({"type": "text", "text": "请分析这张图片"})
            for url in message.image_urls:
                content_parts.append({"type": "image_url", "image_url": {"url": url}})
            return {"role": "user", "content": content_parts}

        if message.image_urls and not supports_vision:
            hint = f"\n\n[用户发送了 {len(message.image_urls)} 张图片，但当前模型不支持图片识别]"
            return {"role": "user", "content": text + hint if text else hint.strip()}

        return {"role": "user", "content": text}

    @staticmethod
    def _save_user_message(conv: dict, message: PlatformMessage, user_msg: dict) -> None:
        entry: dict = {
            "role": "user",
            "content": user_msg.get("content", message.content),
            "id": str(uuid.uuid4()),
            "platform": {
                "name": message.platform,
                "user_id": message.user_id,
                "sender_name": message.sender_name,
                "is_group": message.is_group,
                "message_id": message.message_id,
            },
        }
        if message.image_urls:
            entry["image_urls"] = message.image_urls
        conv.setdefault("messages", []).append(entry)

    @staticmethod
    def _save_assistant_message(conv: dict, content: str, provider: str, model: str) -> None:
        entry: dict = {
            "role": "assistant",
            "content": content,
            "id": str(uuid.uuid4()),
            "model": model,
            "provider": provider,
        }
        conv.setdefault("messages", []).append(entry)

    @staticmethod
    def _extract_assistant_text(result) -> str:
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            if "content" in result and isinstance(result["content"], str):
                return result["content"]
            if "choices" in result:
                choices = result["choices"]
                if choices and isinstance(choices, list):
                    first = choices[0]
                    if isinstance(first, dict):
                        msg = first.get("message", {})
                        if isinstance(msg, dict) and msg.get("content"):
                            return msg["content"]
        return str(result) if result else ""

    @staticmethod
    async def _persist_conv(conv_id: str, conv: dict) -> None:
        conv["updated_at"] = datetime.now(timezone.utc).isoformat()
        await conversation_store.set_async(conv_id, conv)

    @staticmethod
    async def _schedule_memory_update(messages: list[dict], thread_id: str, assistant_text: str) -> None:
        try:
            await context_service.schedule_memory_update(
                messages, thread_id, MAIN_AGENT_ID,
                llm_adapter=None,
            )
        except Exception as e:
            logger.warning(f"[PlatformRouter] Memory update skipped: {e}")


luominest_platform_router = LuomiNestPlatformRouter()


async def route_platform_message(message: PlatformMessage, instance_id: str) -> PlatformResponse | None:
    """平台消息路由入口（供适配器调用）。"""
    return await luominest_platform_router.handle_platform_message(message, instance_id)


def attach_router_to_instances() -> None:
    """将路由器绑定到所有已注册的平台适配器实例。"""
    from app.runtime.platform.registry import attach_message_handler
    attach_message_handler(route_platform_message)
    logger.success("[PlatformRouter] Router attached to all platform instances")


async def send_platform_response(
    instance_id: str,
    target: str,
    response: PlatformResponse,
) -> bool:
    """通过指定平台实例发送响应消息。"""
    adapter = get_adapter(instance_id)
    if not adapter:
        logger.warning(f"[PlatformRouter] Adapter not found for instance {instance_id}")
        return False
    try:
        return await adapter.send_message(response, target)
    except Exception as e:
        logger.error(f"[PlatformRouter] Failed to send platform response: {e}")
        return False
