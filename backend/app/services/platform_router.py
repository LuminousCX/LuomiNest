import asyncio
import json
import time
import traceback
import uuid
from loguru import logger

from app.core.utils import AsyncKeyLocks, extract_llm_text, utc_now
from app.runtime.platform.base import PlatformMessage, PlatformResponse, get_standard_tools_for_platform
from app.runtime.platform.session import (
    MAIN_AGENT_ID,
    create_new_conversation,
    get_or_create_conversation,
)
from app.runtime.platform.main_agent_config import (
    load_luominest_main_agent_config,
    resolve_main_agent_provider_model,
)
from app.runtime.platform.registry import (
    get_adapter,
    get_instance,
    increment_message_count,
    attach_message_handler,
)
from app.runtime.platform.platform_logger import platform_logger
from app.infrastructure.database.conversation_store import conversation_store
from app.services.context_service import context_service
from app.core.context import get_context_manager
from app.runtime.provider.llm.adapter import llm_adapter
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
        self._processing_locks = AsyncKeyLocks()
        self._background_tasks: set[asyncio.Task] = set()

    def _spawn_background_task(self, coro) -> asyncio.Task:
        """启动后台任务并保存引用，防止被 GC 回收。"""
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    async def _get_session_lock(self, session_key: str) -> asyncio.Lock:
        return await self._processing_locks.get(session_key)

    def _resolve_instance_model(self, instance_id: str) -> tuple[str, str, str, float, int]:
        """解析平台实例的模型配置，空值回退到全局主模型配置。

        返回 (provider, model, system_prompt, temperature, max_tokens)。

        2026-08 全局模型统一后：
        - provider/model 回退到全局主模型（resolve_main_agent_provider_model 已委托全局）；
        - temperature/max_tokens 回退到全局生成参数（不再读 main_agent 人设配置）；
        - system_prompt 仍取主 Agent 人设。
        """
        from app.infrastructure.database.facades.model_selection import get_global_generation_defaults

        main_config = load_luominest_main_agent_config()
        main_provider, main_model = resolve_main_agent_provider_model()
        global_temperature, global_max_tokens = get_global_generation_defaults()

        inst = get_instance(instance_id)
        if not inst:
            return (
                main_provider,
                main_model,
                main_config.get("system_prompt", ""),
                float(global_temperature),
                int(global_max_tokens),
            )

        inst_cfg = inst.config.get("model_config", {}) or {}
        provider = inst_cfg.get("provider") or main_provider
        model = inst_cfg.get("model") or main_model
        system_prompt = inst_cfg.get("system_prompt") or main_config.get("system_prompt", "")
        temperature = inst_cfg.get("temperature")
        if temperature is None:
            temperature = float(global_temperature)
        else:
            temperature = float(temperature)
        max_tokens = inst_cfg.get("max_tokens")
        if max_tokens is None:
            max_tokens = int(global_max_tokens)
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
                # /new 命令：为当前平台会话创建新对话（参考 AstrBot 流程）
                if (message.content or "").strip() == "/new":
                    session_id = message.session_id or message.user_id
                    try:
                        await create_new_conversation(instance_id, session_id or "")
                        platform_logger.log(
                            instance_id, "success", "new_conversation_created",
                            f"已为会话 {session_id} 创建新对话",
                            adapter_type=adapter_type,
                            details={"session": session_key, "command": "/new"},
                        )
                        return PlatformResponse(
                            content="[LuomiNest] 已为您开启新对话，之前的上下文已保留在历史记录中。",
                            message_type="text",
                        )
                    except Exception as e:
                        # 服务端日志保留完整异常；对平台用户只返回固定提示，不暴露内部错误
                        logger.error(f"[PlatformRouter] /new command failed: {e}", exc_info=True)
                        return PlatformResponse(
                            content="[LuomiNest] 新建对话失败，请稍后重试",
                            message_type="text",
                        )

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

        provider, model, _system_prompt, temperature, max_tokens = self._resolve_instance_model(instance_id)

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

        # 使用 context_service 的完整系统提示词构建流程（含人设、身份、规则）
        user_text = message.content or ""
        base_system = context_service.build_system_prompt(MAIN_AGENT_ID, user_context=user_text)
        platform_context = self._build_platform_context(message)
        full_system = f"{base_system}\n\n{platform_context}"

        history_messages = self._load_history_messages(conv)
        user_message = self._build_user_message(message, supports_vision)
        messages = [{"role": "system", "content": full_system}] + history_messages + [user_message]

        messages = context_service.inject_timestamp_prompt(messages)
        # 记忆注入（DomainPolicy，§9）：平台域读 owner（优先）+ 该用户 users/{user_key} 记忆
        messages = await context_service.inject_memory(
            messages,
            agent_id=MAIN_AGENT_ID,
            provider_name=provider,
            thread_id=conv_id,
            llm_adapter=llm_adapter,
            domain=conv.get("domain") or f"platform:{instance_id}",
            scene=conv.get("scene") or "platform",
            user_key=conv.get("user_key") or "",
        )

        # 平台对话使用更激进的 70% 压缩阈值
        ctx_mgr = get_context_manager(provider, model, threshold_override=0.70)
        process_result = await ctx_mgr.process(messages, chat_mode="platform")
        messages = process_result["messages"]

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

        # ─── 平台工具注入（tool-opt §4.7 T9）───
        # 双层注入：standard 子集 + 平台专用工具
        platform_adapter = get_adapter(instance_id)
        platform_tools: list[dict] = []
        # 第一层：标准工具子集
        standard_tools = get_standard_tools_for_platform(provider, model)
        platform_tools.extend(standard_tools)
        # 第二层：适配器声明的平台专用工具
        if platform_adapter and hasattr(platform_adapter, 'available_tools'):
            adapter_tools = platform_adapter.available_tools
            platform_tools.extend(adapter_tools)

        use_tools = bool(platform_tools) and llm_adapter.supports_tool_calls(provider, model)

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
                return_raw=True,
                tools=platform_tools if use_tools else None,
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

        # ─── function calling 循环 ───
        max_tool_iterations = 10  # 平台域限制迭代次数（避免无限循环）
        tool_iteration = 0

        while use_tools and tool_iteration < max_tool_iterations:
            tool_calls = self._extract_tool_calls(result)
            if not tool_calls:
                break

            tool_iteration += 1
            logger.info(
                f"[PlatformRouter] Function calling iteration {tool_iteration}: "
                f"{len(tool_calls)} tool call(s)"
            )

            for tc in tool_calls:
                tool_name = tc.get("function", {}).get("name", "")
                tool_args = tc.get("function", {}).get("arguments", {})
                tc_id = tc.get("id", f"call_{tool_iteration}")

                # 解析 arguments（可能是 JSON 字符串）
                if isinstance(tool_args, str):
                    try:
                        tool_args = json.loads(tool_args)
                    except json.JSONDecodeError:
                        tool_args = {}

                # 执行工具
                tool_result = await self._execute_platform_tool(
                    tool_name, tool_args, platform_adapter,
                )

                # 将工具结果追加到消息列表（OpenAI API 格式）
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [tc],
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": tool_result.get("output", tool_result.get("error", "")),
                })

            # 再次调用 LLM（带工具结果）
            try:
                result = await llm_adapter.chat(
                    messages=messages,
                    stream=False,
                    provider_name=provider,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    route_hint=RouteHint.CHAT,
                    return_raw=True,
                    tools=platform_tools,
                )
            except Exception as e:
                logger.error(f"[PlatformRouter] Follow-up LLM call failed: {e}")
                # 回退：使用已积累的内容作为最终响应
                assistant_text = self._extract_assistant_text(result) if result else ""
                usage = self._extract_usage(result) if result else {}
                llm_elapsed = round(time.time() - llm_start, 3)
                self._save_assistant_message(conv, assistant_text, provider, model)
                await self._persist_conv(conv_id, conv)
                increment_message_count(instance_id)
                return PlatformResponse(
                    content=assistant_text or "[LuomiNest] 工具调用后模型响应失败",
                    message_type="text",
                    reply_to=message.message_id,
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

        # 记忆写入（M5=C）：每平台实例独立开关 inst.config["memory_write"]，默认关（§9）；
        # 开启后提炼写入 users/{user_key}/ 用户轨道，不污染主人记忆（§8.5.5）
        memory_write_enabled = bool(inst.config.get("memory_write", False)) if inst else False
        self._spawn_background_task(self._schedule_memory_update(
            messages, conv_id, assistant_text,
            domain=conv.get("domain") or f"platform:{instance_id}",
            user_key=conv.get("user_key") or "",
            memory_write=memory_write_enabled,
        ))

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
        # choices[0].message.content / content 字段提取已收口到 core.utils.extract_llm_text
        return extract_llm_text(result)

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
    def _extract_tool_calls(result) -> list[dict]:
        """从 LLM chat 结果中提取 tool_calls。

        支持 return_raw=True 返回的 dict 格式（含顶层 tool_calls 键）
        以及 OpenAI choices[].message.tool_calls 格式。
        """
        if not isinstance(result, dict):
            return []
        # return_raw=True 格式：顶层 tool_calls 键
        tool_calls = result.get("tool_calls")
        if tool_calls:
            return tool_calls
        # OpenAI choices 格式
        choices = result.get("choices", [])
        if choices:
            first = choices[0]
            if isinstance(first, dict):
                msg = first.get("message", {})
                if isinstance(msg, dict):
                    return msg.get("tool_calls") or []
        return []

    @staticmethod
    async def _execute_platform_tool(
        tool_name: str,
        arguments: dict,
        adapter,
    ) -> dict:
        """执行平台工具调用（standard 子集或平台专用）。

        查找顺序：
        1. 平台专用工具（adapter.execute_platform_tool，名称含 "." 前缀）
        2. tool_registry 中的内置工具（function calling 工具）
        3. internal_tool_registry 中的工作流内部工具
        """
        from app.core.tools.registry import tool_registry
        from app.core.workflow.internal_registry import internal_tool_registry

        # 先尝试平台专用工具（adapter 实现）
        if "." in tool_name and adapter and hasattr(adapter, "execute_platform_tool"):
            try:
                result = await adapter.execute_platform_tool(tool_name, arguments)
                return result
            except Exception as e:
                return {"success": False, "output": "", "error": str(e)}

        # 再尝试 tool_registry（内置 function calling 工具）
        tool = tool_registry.get(tool_name)
        if tool:
            try:
                result = await tool.execute(arguments)
                return {"success": result.success, "output": result.output, "error": result.error}
            except Exception as e:
                return {"success": False, "output": "", "error": str(e)}

        # 再查 internal_tool_registry（工作流内部工具，如 console.execute）
        internal_entry = internal_tool_registry.get(tool_name)
        if internal_entry:
            try:
                wf_result = await internal_tool_registry.execute(tool_name, arguments)
                return {"success": wf_result.success, "output": wf_result.output, "error": wf_result.error}
            except Exception as e:
                return {"success": False, "output": "", "error": str(e)}

        return {"success": False, "output": "", "error": f"工具未找到: {tool_name}"}

    @staticmethod
    async def _persist_conv(conv_id: str, conv: dict) -> None:
        conv["updated_at"] = utc_now()
        await conversation_store.set_async(conv_id, conv)

    @staticmethod
    async def _schedule_memory_update(
        messages: list[dict], thread_id: str, assistant_text: str,
        *, domain: str = "", user_key: str = "", memory_write: bool = False,
    ) -> None:
        try:
            await context_service.schedule_memory_update(
                messages, thread_id, MAIN_AGENT_ID,
                llm_adapter=None,
                domain=domain, user_key=user_key,
                platform_memory_write=memory_write,
            )
        except Exception as e:
            logger.warning(f"[PlatformRouter] Memory update skipped: {e}")


luominest_platform_router = LuomiNestPlatformRouter()


async def route_platform_message(message: PlatformMessage, instance_id: str) -> PlatformResponse | None:
    """平台消息路由入口（供适配器调用）。"""
    return await luominest_platform_router.handle_platform_message(message, instance_id)


def attach_router_to_instances() -> None:
    """将路由器绑定到所有已注册的平台适配器实例。"""
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
