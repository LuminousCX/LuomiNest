import asyncio
import time
import traceback
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
from app.runtime.platform.registry import get_adapter, get_instance, increment_message_count
from app.runtime.platform.platform_logger import platform_logger
from app.infrastructure.database.conversation_store import conversation_store
from app.services.context_service import context_service
from app.runtime.provider.llm.types import RouteHint


class LuomiNestPlatformRouter:
    """平台消息路由器：将各平台消息路由到主 Agent，共享主 Agent 的记忆和供应商配置。

    设计要点：
    - 所有平台会话使用 MAIN_AGENT_ID 作为 agent_id，共享主 Agent 记忆
    - 每个平台会话（instance_id + session_id）对应独立的 conversation
    - 支持每平台独立模型配置（instance.config["model_config"]），空值回退到主 Agent
    - 支持多模态图片识别（根据模型能力自动判断）
    - 非流式响应（平台消息通常一次性返回）
    - 全链路日志：接收→解析→路由→LLM调用→响应发送，含性能统计
    """

    def __init__(self) -> None:
        self._processing_locks: dict[str, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()
        self._background_tasks: set[asyncio.Task] = set()

    def _spawn_background_task(self, coro) -> asyncio.Task:
        """启动后台任务并保存引用，防止被 GC 回收。"""
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    async def _get_session_lock(self, session_key: str) -> asyncio.Lock:
        if session_key in self._processing_locks:
            return self._processing_locks[session_key]
        async with self._locks_guard:
            if session_key not in self._processing_locks:
                self._processing_locks[session_key] = asyncio.Lock()
            return self._processing_locks[session_key]

    def _resolve_instance_model(self, instance_id: str) -> tuple[str, str, str, float, int]:
        """解析平台实例的模型配置，空值回退到主 Agent 配置。

        返回 (provider, model, system_prompt, temperature, max_tokens)。
        """
        from app.runtime.provider.llm.adapter import llm_adapter

        main_config = load_luominest_main_agent_config()
        main_provider, main_model = resolve_main_agent_provider_model()

        inst = get_instance(instance_id)
        if not inst:
            return (
                main_provider,
                main_model,
                main_config.get("system_prompt", ""),
                float(main_config.get("temperature", 0.7)),
                int(main_config.get("max_tokens", 4096)),
            )

        inst_cfg = inst.config.get("model_config", {}) or {}
        provider = inst_cfg.get("provider") or main_provider
        model = inst_cfg.get("model") or main_model
        system_prompt = inst_cfg.get("system_prompt") or main_config.get("system_prompt", "")
        temperature = inst_cfg.get("temperature")
        if temperature is None:
            temperature = float(main_config.get("temperature", 0.7))
        else:
            temperature = float(temperature)
        max_tokens = inst_cfg.get("max_tokens")
        if max_tokens is None:
            max_tokens = int(main_config.get("max_tokens", 4096))
        else:
            max_tokens = int(max_tokens)

        try:
            provider_inst = llm_adapter.get_provider(provider)
            model = model or provider_inst.default_model
        except Exception:
            provider = main_provider
            model = main_model

        return provider, model, system_prompt, temperature, max_tokens

    async def handle_platform_message(
        self,
        message: PlatformMessage,
        instance_id: str,
    ) -> PlatformResponse | None:
        """处理来自平台的入站消息，路由到主 Agent 并返回响应。"""
        session_key = f"{instance_id}:{message.session_id or message.user_id}"
        lock = await self._get_session_lock(session_key)

        receive_time = time.time()
        inst = get_instance(instance_id)
        adapter_type = inst.adapter_type if inst else message.platform

        platform_logger.log(
            instance_id, "info", "message_received",
            f"收到消息: 来自 {message.sender_name or message.user_id or '未知'}",
            adapter_type=adapter_type,
            details={
                "session": session_key,
                "sender": message.sender_name or message.user_id,
                "is_group": message.is_group,
                "content_length": len(message.content or ""),
                "image_count": len(message.image_urls),
                "message_id": message.message_id,
            },
        )

        async with lock:
            try:
                response = await self._route_to_main_agent(message, instance_id, receive_time)
                if response and response.content:
                    platform_logger.log(
                        instance_id, "success", "message_sent",
                        f"响应已发送: {response.content[:80]}",
                        adapter_type=adapter_type,
                        details={
                            "session": session_key,
                            "response_length": len(response.content),
                            "message_type": response.message_type,
                            "total_elapsed": round(time.time() - receive_time, 3),
                        },
                    )
                return response
            except Exception as e:
                error_tb = traceback.format_exc()
                logger.error(f"[PlatformRouter] Failed to route message from {session_key}: {e}\n{error_tb}")
                platform_logger.log(
                    instance_id, "error", "route_failed",
                    f"消息路由失败: {e}",
                    adapter_type=adapter_type,
                    details={
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "session": session_key,
                        "stack_trace": error_tb[-1000:],
                        "elapsed": round(time.time() - receive_time, 3),
                    },
                )
                return PlatformResponse(
                    content=f"[LuomiNest] 消息处理失败，请稍后重试",
                    message_type="text",
                )

    async def _route_to_main_agent(
        self,
        message: PlatformMessage,
        instance_id: str,
        receive_time: float,
    ) -> PlatformResponse | None:
        from app.runtime.provider.llm.adapter import llm_adapter

        session_id = message.session_id or message.user_id
        inst = get_instance(instance_id)
        adapter_type = inst.adapter_type if inst else message.platform

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
            platform_logger.log(
                instance_id, "error", "conversation_missing",
                f"会话不存在: {conv_id}",
                adapter_type=adapter_type,
                details={"conversation_id": conv_id},
            )
            return None

        provider, model, system_prompt, temperature, max_tokens = self._resolve_instance_model(instance_id)

        try:
            provider_inst = llm_adapter.get_provider(provider)
            supports_vision = provider_inst.supports_multimodal(model)
        except Exception as e:
            supports_vision = False
            platform_logger.log(
                instance_id, "warning", "provider_resolve_failed",
                f"供应商解析失败，回退到默认: {e}",
                adapter_type=adapter_type,
                details={"provider": provider, "model": model, "error": str(e)},
            )

        if message.image_urls and not supports_vision:
            platform_logger.log(
                instance_id, "warning", "vision_unsupported",
                f"用户发送了 {len(message.image_urls)} 张图片，但当前模型 {model} 不支持图片识别",
                adapter_type=adapter_type,
                details={
                    "provider": provider,
                    "model": model,
                    "image_count": len(message.image_urls),
                },
            )

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

        platform_logger.log(
            instance_id, "info", "llm_call_start",
            f"调用 LLM: {provider}/{model}",
            adapter_type=adapter_type,
            details={
                "conversation_id": conv_id,
                "provider": provider,
                "model": model,
                "vision_enabled": supports_vision,
                "history_count": len(history_messages),
                "total_messages": len(messages),
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )

        logger.info(
            f"[PlatformRouter] Routing: platform={message.platform}, "
            f"session={session_id}, provider={provider}, model={model}, "
            f"vision={supports_vision}, images={len(message.image_urls)}, "
            f"history={len(history_messages)}"
        )

        llm_start = time.time()
        try:
            result = await llm_adapter.chat(
                messages=messages,
                stream=False,
                provider_name=provider,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                route_hint=RouteHint.CHAT,
            )
        except Exception as e:
            error_tb = traceback.format_exc()
            llm_elapsed = round(time.time() - llm_start, 3)
            logger.error(f"[PlatformRouter] LLM call failed: {e}\n{error_tb}")
            platform_logger.log(
                instance_id, "error", "llm_call_failed",
                f"LLM 调用失败: {e}",
                adapter_type=adapter_type,
                details={
                    "provider": provider,
                    "model": model,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "llm_elapsed": llm_elapsed,
                    "stack_trace": error_tb[-1000:],
                },
            )
            await self._persist_conv(conv_id, conv)
            return PlatformResponse(
                content=f"[LuomiNest] 模型调用失败：{e}",
                message_type="text",
            )

        llm_elapsed = round(time.time() - llm_start, 3)
        assistant_text = self._extract_assistant_text(result)
        usage = self._extract_usage(result)

        self._save_assistant_message(conv, assistant_text, provider, model)
        await self._persist_conv(conv_id, conv)

        increment_message_count(instance_id)

        platform_logger.log(
            instance_id, "success", "llm_call_success",
            f"LLM 响应成功: {assistant_text[:80]}",
            adapter_type=adapter_type,
            details={
                "conversation_id": conv_id,
                "provider": provider,
                "model": model,
                "llm_elapsed": llm_elapsed,
                "response_length": len(assistant_text),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            },
        )

        platform_logger.log(
            instance_id, "info", "message_routed",
            f"消息已路由: {message.sender_name or session_id} -> 主Agent",
            adapter_type=adapter_type,
            details={
                "conversation_id": conv_id,
                "provider": provider,
                "model": model,
                "total_elapsed": round(time.time() - receive_time, 3),
                "llm_elapsed": llm_elapsed,
            },
        )

        self._spawn_background_task(self._schedule_memory_update(messages, conv_id, assistant_text))

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
    def _extract_usage(result) -> dict:
        """从 LLM 响应中提取 token 用量统计。"""
        if not isinstance(result, dict):
            return {}
        usage = result.get("usage")
        if isinstance(usage, dict):
            return {
                "prompt_tokens": usage.get("prompt_tokens") or usage.get("input_tokens"),
                "completion_tokens": usage.get("completion_tokens") or usage.get("output_tokens"),
                "total_tokens": usage.get("total_tokens"),
            }
        return {}

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
