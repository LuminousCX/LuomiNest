import asyncio
import hashlib
import json
import time
import traceback
import uuid
from dataclasses import replace
from typing import Any
from loguru import logger

from app.core.utils import AsyncKeyLocks, extract_llm_text, utc_now
from app.core.domain_policy import platform_user_key
from app.runtime.platform.group_config import safe_get_group_config
from app.runtime.platform.base import (
    HIGH_RISK_PLATFORM_TOOLS,
    HIGH_RISK_TOOL_BLOCKED_MESSAGE,
    PLATFORM_TOOLS_RISK_ENABLED_KEY,
    PlatformMessage,
    PlatformResponse,
    filter_tools_by_risk,
)
from app.runtime.platform.infrastructure.dedup import MessageDeduplicator
from app.runtime.platform.infrastructure.message_batch import TextBatchAggregator
from app.runtime.platform.segmenter import SegmentParams, segment_reply_plan
from app.runtime.platform.briefings import get_platform_briefing
from app.runtime.platform.session import (
    MAIN_AGENT_ID,
    get_or_create_conversation,
)
from app.runtime.platform.commands import (
    CommandContext,
    dispatch_platform_command,
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
from app.infrastructure.database.config_store import luominest_config_store
from app.services.context_service import context_service
from app.core.agents.middleware.base import AgentContext
from app.core.tags.definitions import (
    TASK_DISPATCH_DETECTED_KEY,
    TASK_DISPATCH_RESULTS_KEY,
)
from app.core.tags.parser import TagStreamParser
from app.core.context import get_context_manager
from app.core.tools.orchestrator import tool_orchestrator
from app.runtime.provider.llm.adapter import llm_adapter
from app.runtime.provider.llm.types import RouteHint

# 批聚合并关（接线债：TextBatchAggregator，审查报告 03 §P1-1 / 接线债清单）。
# 存放在 inst.config，与其他实例级开关（memory_write / platform_tools_risk_enabled）同风格。
# 默认关闭：同步响应契约下开启会给所有文本消息引入一个窗口期的固定延迟，
# 且拉长 qq_onebot 这类内联 emit 适配器的读循环阻塞时间（报告 P2-1 队头阻塞面）。
MESSAGE_BATCH_ENABLED_KEY = "message_batch_enabled"

# ── G0-C/G0-D 常量（2026-10-25 拍板⑪⑫，赛博生命升格计划书 §6.1）──────────
# 私聊/未配置群的历史注入条数（原 20 条冲刷扩容至 100；AstrBot 佐证：其默认
# 不限条数 + 按 token 压缩，插件生态常开 100+）
PLATFORM_HISTORY_LIMIT_DEFAULT = 100
# 快脑会话实际注入条数：快脑吃「滚动摘要 + 近 50 条」，慢脑 dispatch 吃全量
FAST_BRAIN_RECENT_MESSAGES = 50
# 滚动摘要低频维护触发阈值：会话消息距上次摘要新增 ≥N 条时重新生成
ROLLING_SUMMARY_TRIGGER = 40
# 滚动摘要存储命名空间（config_items 键 platform.summaries.{conv_id}）。
# 独立于 conv 对象存储：后台摘要写与热路径会话写并发时互不覆盖（append-only 键）。
SUMMARY_NAMESPACE = "platform.summaries."

# 滚动摘要生成提示词（拍板⑪：纯事实性压缩，与 G1 reflection 的认知性升华相邻不合并）
_ROLLING_SUMMARY_SYSTEM_PROMPT = (
    "你是对话记录归档员。把既有摘要与新增消息合并为一份更新的事实性滚动摘要：\n"
    "- 只记录事实：谁说了什么、决定了什么、发生了什么、提到的实体/关系/数字/时间；\n"
    "- 不要评价、不要建议、不要总结感受（那是另一条认知管线的职责）；\n"
    "- 保留人名、时间、数字等关键信息；冲突信息以更新后的为准；\n"
    "- 控制在 500 字以内，直接输出摘要正文，不要任何前后缀。"
)


class LuomiNestPlatformRouter:
    """平台消息路由器：将各平台消息路由到主 Agent，共享主 Agent 的记忆和供应商配置。

    设计要点：
    - 所有平台会话使用 MAIN_AGENT_ID 作为 agent_id，共享主 Agent 记忆
    - 每个平台会话（instance_id + session_id）对应独立的 conversation
    - 支持每平台独立模型配置（instance.config["model_config"]），空值回退到主 Agent
    - 支持多模态图片识别（根据模型能力自动判断）
    - 非流式响应（平台消息通常一次性返回）
    - 全链路日志：接收→解析→路由→LLM调用→响应发送，含性能统计
    - 入口统一消息去重（P1-1：MessageDeduplicator，TTL+LRU 有界缓存），
      拦截平台级重推（微信系 5s 无响应重推 / QQ 官方事件重发 /
      Discord Resume 重放 / telegram 重启 offset 归零重拉 pending）
    - 可选批聚合（TextBatchAggregator，inst.config["message_batch_enabled"]，默认关），
      合并同一发送者窗口期内的连续短文本，防碎片消息各自触发独立回复
    """

    def __init__(self) -> None:
        self._processing_locks = AsyncKeyLocks()
        self._background_tasks: set[asyncio.Task] = set()
        # 去重缓存有界：LRU 2000 条 + TTL 300s，超限淘汰最久未访问条目
        # （微信系重推窗口 5s、QQ 官方重发分钟级，300s 覆盖；telegram
        # 重启重拉 pending 也在同一进程内被此缓存兜住）
        self._deduplicator = MessageDeduplicator(max_size=2000, ttl=300.0)
        self._batch_aggregator = TextBatchAggregator(aggregation_window=1.5)

    def _spawn_background_task(self, coro) -> asyncio.Task:
        """启动后台任务并保存引用，防止被 GC 回收。"""
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    async def _get_session_lock(self, session_key: str) -> asyncio.Lock:
        return await self._processing_locks.get(session_key)

    @staticmethod
    def _get_instance_config(inst) -> dict:
        """稳妥读取实例配置 dict（兼容 PlatformInstance 对象与 dict 两种形态）。"""
        if inst is None:
            return {}
        if isinstance(inst, dict):
            cfg = inst.get("config")
        else:
            cfg = getattr(inst, "config", None)
        return cfg if isinstance(cfg, dict) else {}

    def _is_platform_risk_enabled(self, instance_id: str) -> bool:
        """读取实例级高风险平台工具开关（W3-3：platform_tools_risk_enabled，默认关）。

        开关存放在 inst.config（单一配置源），注入面与执行面共用同一读取逻辑，
        防止两处判定不一致。
        """
        if not instance_id:
            return False
        inst = get_instance(instance_id)
        return bool(self._get_instance_config(inst).get(PLATFORM_TOOLS_RISK_ENABLED_KEY, False))

    def _resolve_instance_model(self, instance_id: str) -> tuple[str, str, str, float, int]:
        """解析平台实例生效的模型配置。

        返回 (provider, model, system_prompt, temperature, max_tokens)。

        全局模型统一后：
        - provider/model/temperature/max_tokens 一律取全局主模型与全局生成参数
          （设置→模型设置），平台实例不再支持模型级覆盖；
        - system_prompt 仍支持实例级覆盖（平台人格），未设置时取主 Agent 人设。
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
        system_prompt = inst_cfg.get("system_prompt") or main_config.get("system_prompt", "")

        return (
            main_provider,
            main_model,
            system_prompt,
            float(global_temperature),
            int(global_max_tokens),
        )

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

        # ─── P1-1 平台级消息去重（审查报告 03-平台对接链路 §4 P1-1）───
        # 按（实例 + 平台消息唯一键）判重，重复推送直接丢弃并记平台日志。
        # 与 wechat_personal 适配器内的自消息回显过滤互补：那是双 bot 死循环
        # 防护，这里收口平台 at-least-once 语义下的重复投递。
        # message_id 为空的适配器不参与去重（无法构造可靠键，保持原语义）。
        dedup_key = self._build_dedup_key(message, instance_id)
        if dedup_key and self._deduplicator.check_and_mark(dedup_key):
            platform_logger.log(
                instance_id, "info", "duplicate_dropped",
                f"重复消息已丢弃: {message.message_id}",
                adapter_type=adapter_type,
                details={
                    "session": session_key,
                    "message_id": message.message_id,
                    "sender": message.sender_name or message.user_id,
                },
            )
            return None

        # ─── 批聚合（接线债：TextBatchAggregator，默认关闭）───
        # 在会话锁之前执行：等待窗口期间不占锁，不影响其他会话/消息正常流转。
        message = await self._maybe_aggregate(message, instance_id, adapter_type)
        if message is None:
            # 本条已并入其他并发调用的聚合批次，由窗口到期者统一回复一次
            return None

        async with lock:
            main_config = load_luominest_main_agent_config()
            agent_name = str(main_config.get("name") or "主Agent").strip()
            try:
                # ─── 命令短路（2026-10-12 拍板：命令制；命中命令不进 LLM）───
                # /help /new /memory 等，/new 是唯一的开新会话入口；
                # 非命令文本走正常 LLM 路由（parse 失败返回 None）
                command_response = await dispatch_platform_command(CommandContext(
                    message=message,
                    instance_id=instance_id,
                    session_id=message.session_id or message.user_id or "",
                    agent_name=agent_name,
                ))
                if command_response is not None:
                    return command_response

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
                content=f"[{agent_name}] 消息处理失败，请稍后重试",
                message_type="text",
            )

    @staticmethod
    def _build_dedup_key(message: PlatformMessage, instance_id: str) -> str:
        """构造去重键：实例 + 消息唯一键 + 内容指纹。

        - 主键为 instance_id + message_id：平台重推（微信 5s 无响应重推、
          QQ 官方事件重发、Discord Resume 重放、telegram offset 归零重拉）
          携带同一 message_id 与同一载荷，命中即去重。
        - 附加 content + image_urls 指纹：个别适配器的 message_id 是弱回退值
          （minecraft 截图 ss_{秒级时间戳}、home_assistant time_fired），
          同秒两条不同消息会撞 id；载荷指纹保证只有「同 id 且同载荷」才判重，
          真重推载荷必然一致，不受影响。
        - message_id 为空返回空串，调用方跳过去重（保持原语义）。
        """
        message_id = (message.message_id or "").strip()
        if not message_id:
            return ""
        payload = "\x00".join([message.content or "", *message.image_urls])
        payload_fp = hashlib.sha1(payload.encode("utf-8", "ignore")).hexdigest()[:16]
        return f"{instance_id}:{message_id}:{payload_fp}"

    async def _maybe_aggregate(
        self,
        message: PlatformMessage,
        instance_id: str,
        adapter_type: str,
    ) -> PlatformMessage | None:
        """批聚合（接线债：TextBatchAggregator，默认关闭）。

        将同一发送者在窗口期内的连续短文本合并为一条消息统一处理，
        防止用户快速分段发送时各自触发独立回复。

        返回值语义：
        - PlatformMessage（content 已替换为聚合文本）：由本次调用负责路由，
          走正常返回值路径由适配器 send_message 回包；
        - None：本条已被并入其他并发调用正在处理的批次，本次不回复。

        并发模型（同步响应契约下无需后台定时器）：
        - 每个进入聚合的调用先 add_message 占位/追加，首个片段的调用方
          sleep 一个窗口后 flush 统一处理；并发片段的调用方同样 sleep 后
          flush 落空（缓冲已被取走）→ 返回 None 退出。一个批次恰好一次回复。
        - 等待发生在会话锁之前，不占锁；聚合键按（实例+会话+发送者）隔离，
          群里不同成员的消息不会互相合并，也不会与 /new 等命令冲突
          （命令与图片消息不参与聚合）。

        默认关闭（取舍见 MESSAGE_BATCH_ENABLED_KEY 注释）：同步响应契约下
        开启会给所有文本消息增加约一个窗口期（1.5s）的固定延迟，并拉长
        qq_onebot 这类内联 emit 适配器的读循环阻塞时间（报告 P2-1 队头
        阻塞面），是否开启交由实例配置 message_batch_enabled 决定。
        """
        inst = get_instance(instance_id)
        if not bool(self._get_instance_config(inst).get(MESSAGE_BATCH_ENABLED_KEY, False)):
            return message

        text = (message.content or "").strip()
        # 命令与图片消息不参与聚合：命令需即时短路（/new），图片走多模态分支
        if not text or text.startswith("/") or message.image_urls:
            return message

        agg_key = f"{instance_id}:{message.session_id or message.user_id}:{message.user_id}"
        merged = self._batch_aggregator.add_message(agg_key, text)
        if merged is None:
            # 首个片段：等一个窗口让后续片段汇入，再统一取走缓冲
            await asyncio.sleep(self._batch_aggregator.aggregation_window)
            merged = self._batch_aggregator.flush(agg_key)
        if not (merged or "").strip():
            # 缓冲已被其他并发调用取走（或为空）：本条无需再回复
            return None

        if merged != text:
            platform_logger.log(
                instance_id, "info", "messages_aggregated",
                f"窗口期内合并连续短消息（聚合后 {len(merged)} 字）",
                adapter_type=adapter_type,
                details={
                    "session": f"{instance_id}:{message.session_id or message.user_id}",
                    "sender": message.sender_name or message.user_id,
                    "merged_length": len(merged),
                },
            )
        # 不改传入对象：浅拷贝替换 content，原始 PlatformMessage 归适配器所有
        return replace(message, content=merged)

    async def _route_to_main_agent(
        self,
        message: PlatformMessage,
        instance_id: str,
        receive_time: float,
    ) -> PlatformResponse | None:
        session_id = message.session_id or message.user_id
        inst = get_instance(instance_id)
        adapter_type = inst.adapter_type if inst else message.platform

        # P0-1 定时任务闭环：标记平台会话来源，使 create_scheduled_task 等工具
        # 执行时能记录结果投递目标（群里建的提醒回该群）；contextvar 随请求任务隔离
        try:
            from app.core.tools.builtin.scheduler_tool import set_platform_task_origin
            set_platform_task_origin(
                instance_id=instance_id,
                session_id=session_id or "",
                is_group=message.is_group,
                platform=message.platform,
            )
        except Exception as e:
            logger.warning(f"[PlatformRouter] 设置平台任务来源上下文失败: {e}")

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

        # 统一人键（分册10 §16.1）：群成员轨与私聊轨归一为同一把键
        # {platform}_{sender_id}——同一人在群聊和私聊共享一处记忆；
        # 私聊沿用 conv.user_key（同为 {platform}_{uid} 格式），无 sender_id
        # 的群消息维持现状（不建轨）。旧三段键存量由
        # scripts/migrate_member_tracks.py 幂等并入统一人键。
        member_user_key = ""
        if message.is_group and (message.user_id or "").strip():
            member_user_key = platform_user_key(message.platform, message.user_id)
        effective_user_key = conv.get("user_key") or member_user_key
        # 在场其他成员（近期群消息去重，不含当前说话者）→ 群友画像块
        group_members = self._collect_group_members(conv, message, instance_id)

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
        # G0-B：传 provider/model——快脑会话自动切换为合同风格提示块（W2 分册 10 §18）
        user_text = message.content or ""
        base_system = context_service.build_system_prompt(
            MAIN_AGENT_ID,
            user_context=user_text,
            include_avatar_emotion=False,
            provider=provider,
            model=model,
        )
        # W3-3/平台 briefing：风险开关提前计算（工具注入面与本 briefing 共用同一判定）
        risk_enabled = self._is_platform_risk_enabled(instance_id)
        _adapter_for_briefing = get_adapter(instance_id)
        _adapter_tool_names = [
            t.get("function", {}).get("name", "")
            for t in filter_tools_by_risk(
                getattr(_adapter_for_briefing, "available_tools", []) or [],
                risk_enabled,
            )
            if isinstance(t, dict)
        ]
        platform_context = self._build_platform_context(
            message,
            risk_enabled=risk_enabled,
            tool_names=[n for n in _adapter_tool_names if n],
        )
        full_system = f"{base_system}\n\n{platform_context}"

        # ── G0-C 三层上下文（拍板⑪）：快脑吃「摘要+近 50」，慢脑吃「摘要+全量」──
        group_id_val = message.group_id or (message.session_id if message.is_group else "")
        group_cfg: dict = {}
        if message.is_group and (group_id_val or "").strip():
            group_cfg = safe_get_group_config(instance_id, group_id_val)
        is_fast_brain = context_service.is_fast_brain_model(provider, model)
        context_limit = (
            int(group_cfg.get("context_limit") or PLATFORM_HISTORY_LIMIT_DEFAULT)
            if message.is_group else PLATFORM_HISTORY_LIMIT_DEFAULT
        )
        effective_limit = (
            min(context_limit, FAST_BRAIN_RECENT_MESSAGES) if is_fast_brain else context_limit
        )
        # 滚动摘要注入（低频维护，独立存储键；读取失败静默跳过不断流）
        try:
            _summary_entry = await luominest_config_store.get_async(f"{SUMMARY_NAMESPACE}{conv_id}")
            _rolling_summary = str(_summary_entry.get("summary") or "") if isinstance(_summary_entry, dict) else ""
        except Exception as e:
            _rolling_summary = ""
            logger.debug(f"[PlatformRouter] 滚动摘要读取失败（跳过注入）: {e}")
        if _rolling_summary:
            full_system += (
                f"\n\n[会话滚动摘要 · 事实性压缩]\n{_rolling_summary}\n"
                f"（以上是更早对话的摘要，与近期消息共同构成完整上下文）"
            )

        history_messages = self._load_history_messages(conv, limit=effective_limit)
        user_message = self._build_user_message(message, supports_vision)
        messages = [{"role": "system", "content": full_system}] + history_messages + [user_message]

        messages = context_service.inject_timestamp_prompt(messages)
        # 记忆注入（DomainPolicy，§9）：平台域读 owner（优先）+ 群组画像(若群聊) + 说话成员用户轨
        # （私聊 = conv.user_key；群聊 = 粉丝成员轨 + 群聊专属记忆，防隐私泄露）+ 在场成员群友画像块
        messages = await context_service.inject_memory(
            messages,
            agent_id=MAIN_AGENT_ID,
            provider_name=provider,
            thread_id=conv_id,
            llm_adapter=llm_adapter,
            domain=conv.get("domain") or f"platform:{instance_id}",
            scene=conv.get("scene") or "platform",
            user_key=effective_user_key,
            group_id=group_id_val,
            group_members=group_members,
        )

        # 平台对话使用更激进的 70% 压缩阈值
        ctx_mgr = get_context_manager(provider, model, threshold_override=0.70)
        process_result = await ctx_mgr.process(messages, chat_mode="platform")
        messages = process_result["messages"]

        # 快脑合同四段式改写最后一跳 user 消息（W2 分册 10 §18.1；chat_service 同款，
        # G0-B：is_fast_brain_ctx 判定自此覆盖平台路径）
        if is_fast_brain:
            messages = context_service.inject_fast_brain_protocol(
                messages,
                agent_id=MAIN_AGENT_ID,
                session_mode="group_chat" if message.is_group else "private_chat",
                is_owner=False,
                speaker_name=message.sender_name,
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

        # ─── 平台工具注入（G0-A 拍板⑨：工具面全量放开，三级注入照常生效）───
        # 第一层：全量注册表三级注入（常驻/召回层完整 schema + 长尾摘要；
        # W7 高权限裁剪与能力表检查在 orchestrator 内照常生效）
        platform_adapter = get_adapter(instance_id)
        schemas, tool_digest = tool_orchestrator.get_tools_for_llm_tiered(
            provider, model, scope=None, query=user_text,
        )
        platform_tools: list[dict] = list(schemas)
        # 第二层：适配器声明的平台专用工具
        # 风险闸门（W3-3，默认关闭）：risk_enabled 已在上方构建平台 briefing 时计算，
        # 两处共用同一判定（inst.config["platform_tools_risk_enabled"]）——双闸保留
        if platform_adapter and hasattr(platform_adapter, 'available_tools'):
            adapter_tools = platform_adapter.available_tools
            platform_tools.extend(filter_tools_by_risk(adapter_tools, risk_enabled))

        use_tools = bool(platform_tools) and llm_adapter.supports_tool_calls(provider, model)

        # 长尾工具摘要块进 system（快脑会话由 ToolFilterMiddleware 整块剥除，W3 口径）
        if tool_digest and use_tools and messages and messages[0].get("role") == "system":
            messages[0]["content"] = (
                messages[0]["content"]
                + "\n\n<tool_index>\n以下工具未注入完整参数定义（节省 token）。"
                "使用其中某个工具前，先调用 tool_explore(tool_name='工具名') 获取完整定义，"
                "探索到的工具即可直接调用：\n"
                + tool_digest
                + "\n</tool_index>"
            )

        llm_start = time.time()
        try:
            # ── G0-A 平台管道收敛（拍板⑧）：scene="platform" 非流式独立挂载组 ──
            # MemoryAccess/ToolFilter/ContextTrim/LoopGuard/PermissionGate/Dispatch/
            # ToolExecution/UsageTrack 全在位；工具循环由 AgentRunner.run_non_stream
            # 承载（原自建 function-calling 循环已删，与 chat 非流式同构）。
            # execute_fn 用平台执行器：适配器专用工具/内部工具三层查找 + 高风险执行侧
            # 兜底闸门（_execute_platform_tool）不可绕开。
            async def platform_execute_fn(tool_call: dict) -> dict:
                func_info = tool_call.get("function", {})
                tool_name = func_info.get("name", "")
                raw_args = func_info.get("arguments", {})
                if isinstance(raw_args, str):
                    try:
                        arguments = json.loads(raw_args) if raw_args.strip() else {}
                    except json.JSONDecodeError:
                        arguments = {}
                else:
                    arguments = raw_args or {}
                tool_result = await self._execute_platform_tool(
                    tool_name, arguments, platform_adapter,
                    instance_id=instance_id,
                )
                content = (
                    tool_result.get("output")
                    or tool_result.get("error")
                    or "{}"
                )
                if not str(content).strip():
                    content = "{}"
                out: dict[str, Any] = {
                    "role": "tool",
                    "tool_call_id": tool_call.get("id", ""),
                    "name": tool_name,
                    "content": str(content),
                }
                if tool_result.get("metadata"):
                    out["metadata"] = tool_result["metadata"]
                return out

            runner = tool_orchestrator.create_runner({
                "scene": "platform",
                "is_stream": False,
                "max_iterations": 10,
                "execute_fn": platform_execute_fn,
            })
            agent_ctx = AgentContext(
                messages=messages,
                tools=platform_tools if use_tools else None,
                route_hint=RouteHint.CHAT,
                state={"provider": provider, "model": model, "chat_id": conv_id},
                extra={
                    "scene": "platform",
                    "is_stream": False,
                    "agent_id": MAIN_AGENT_ID,
                    # dispatch 结果回填目标会话（DispatchMiddleware._backfill_result 惯例）
                    "conv_id": conv_id,
                    "supports_vision": supports_vision,
                    # G0-C：慢脑派发可见「滚动摘要 + 近期消息全量」（中间件侧裁剪 8000 字）
                    "dispatch_context": await self._build_dispatch_context(conv_id, context_limit),
                },
            )

            async def llm_call_fn(call_ctx: AgentContext):
                extra_kwargs: dict = {}
                # G0-B Ollama 快脑补丁（拍板⑩）：关思考模式——快脑为快速响应存在
                if provider == "ollama" and is_fast_brain:
                    extra_kwargs["think"] = False
                result = await llm_adapter.chat(
                    messages=call_ctx.messages,
                    tools=call_ctx.tools,
                    stream=False,
                    provider_name=provider,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    route_hint=RouteHint.CHAT,
                    return_raw=True,
                    **extra_kwargs,
                )
                # 标签协议覆盖平台域（G0）：剥五族合同标签 + dispatch 挂点写入
                return self._normalize_platform_llm_result(call_ctx, result)

            result_state = await runner.run_non_stream(agent_ctx, llm_call_fn)
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
            agent_name = str(load_luominest_main_agent_config().get("name") or "主Agent").strip()
            return PlatformResponse(
                content=f"[{agent_name}] 模型调用失败：{e}",
                message_type="text",
            )

        llm_elapsed = round(time.time() - llm_start, 3)
        assistant_text = str(result_state.get("content") or "").strip()
        usage = result_state.get("usage") or {}

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
        # 开启后提炼写入 users/{track_user_key}/ 用户轨（私聊 = conv.user_key；
        # 群聊 = 说话成员轨，关于某群友的事实写进该群友的轨道而非丢弃，§8.5.10），
        # 不污染主人记忆（§8.5.5）
        memory_write_enabled = bool(inst.config.get("memory_write", False)) if inst else False
        # per-group 记忆开关（platform.groups.*）：群聊在实例开关之上再取与
        if memory_write_enabled and message.is_group and (group_id_val or "").strip():
            memory_write_enabled = bool(
                safe_get_group_config(instance_id, group_id_val).get("memory_enabled", True)
            )
        self._spawn_background_task(self._schedule_memory_update(
            messages, conv_id, assistant_text,
            domain=conv.get("domain") or f"platform:{instance_id}",
            user_key=effective_user_key,
            group_id=group_id_val,
            memory_write=memory_write_enabled,
        ))

        # ── G0-C 滚动摘要低频维护（后台；拍板⑪：慢脑维护，新增 ≥N 条触发）───
        self._spawn_background_task(self._maybe_update_rolling_summary(
            conv_id, provider, model,
        ))

        # ── G0-A 派发结果回投 + G0-D 分段发送（拍板⑧⑫）──────────────────
        # 非流式管道没有 SSE：DispatchMiddleware 把 done 结果登记在
        # ctx.state[TASK_DISPATCH_RESULTS_KEY]，此处经适配器补发到平台会话。
        dispatch_results = [
            dr for dr in (result_state.get(TASK_DISPATCH_RESULTS_KEY) or [])
            if isinstance(dr, dict) and str(dr.get("result") or "").strip()
        ]

        seg_params: SegmentParams | None = None
        send_target = ""
        if message.is_group and (group_id_val or "").strip():
            send_target = group_id_val or message.session_id or message.user_id or ""
            if bool(group_cfg.get("segment_enabled", True)):
                seg_params = self._build_segment_params(group_cfg)

        if seg_params is not None and send_target and (assistant_text or dispatch_results):
            # 分段模式：主回复与派发结果都由后台任务按计划延迟逐段发送，
            # 返回 None 让适配器跳过同步回包（延迟不阻塞适配器读循环）
            if assistant_text:
                self._spawn_background_task(self._send_platform_text(
                    instance_id, send_target, assistant_text,
                    reply_to=message.message_id, params=seg_params,
                ))
            for dr in dispatch_results:
                title = str(dr.get("task") or "")[:40] or "任务"
                self._spawn_background_task(self._send_platform_text(
                    instance_id, send_target,
                    f"[派发任务]《{title}》执行完成：\n{dr.get('result')}",
                    reply_to=message.message_id, params=seg_params,
                ))
            return None

        # 非分段路径：主回复走同步回包；派发结果单条补发
        for dr in dispatch_results:
            title = str(dr.get("task") or "")[:40] or "任务"
            fallback_target = message.session_id or message.user_id or ""
            if fallback_target:
                self._spawn_background_task(self._send_platform_text(
                    instance_id, fallback_target,
                    f"[派发任务]《{title}》执行完成：\n{dr.get('result')}",
                    reply_to=message.message_id,
                ))

        if not assistant_text:
            # 全部输出为标签/派发垫话缺失等净化后为空：不回空消息
            return None

        return PlatformResponse(
            content=assistant_text,
            message_type="text",
            reply_to=message.message_id,
        )

    @staticmethod
    def _collect_group_members(
        conv: dict,
        message: PlatformMessage,
        instance_id: str,
        *,
        max_members: int = 10,
    ) -> list[dict]:
        """从会话近期群消息收集在场成员（不含当前说话者）→ 群友画像条目。

        消息 platform.user_id 为发送者标识（各群聊 adapter 均已填充），
        platform.sender_name 为昵称；按「人」去重（同一 sender_id 保留最近
        昵称），最近发言的成员优先（超出 max_members 时截断）。
        """
        if not message.is_group:
            return []
        members: list[dict] = []
        seen: set[str] = set()
        speaker_id = (message.user_id or "").strip()
        for msg in reversed(conv.get("messages", [])):
            meta = msg.get("platform") or {}
            if not meta.get("is_group"):
                continue
            sender_id = str(meta.get("user_id", "") or "").strip()
            if not sender_id or sender_id == speaker_id or sender_id in seen:
                continue
            seen.add(sender_id)
            members.append({
                "sender_id": sender_id,
                "sender_name": str(meta.get("sender_name", "") or ""),
                "user_key": platform_user_key(message.platform, sender_id),
            })
            if len(members) >= max_members:
                break
        return members

    @staticmethod
    def _build_platform_context(
        message: PlatformMessage,
        risk_enabled: bool = False,
        tool_names: list[str] | None = None,
    ) -> str:
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
        # 平台 briefing（2026-09-21）：只注入当前平台的能力边界、不具备的能力
        # （反幻觉）与风险约束——system 上下文按平台隔离，防跨平台紊乱
        briefing = get_platform_briefing(
            message.platform,
            risk_enabled=risk_enabled,
            tool_names=tool_names,
        )
        if briefing:
            parts.append(briefing)
        return "\n".join(parts)

    @staticmethod
    def _assemble_system_prompt(base_prompt: str, platform_context: str, message: PlatformMessage) -> str:
        if not base_prompt:
            base_prompt = "你是 LuomiNest 主控智能体，正在通过外部平台与用户交互。"
        return f"{base_prompt}\n\n{platform_context}"

    @staticmethod
    def _load_history_messages(conv: dict, limit: int | None = None) -> list[dict]:
        """加载历史消息（G0-C 拍板⑪：条数可配，默认 100——原 20 条冲刷已扩容）。

        limit 为注入条数上限；快脑会话由调用方传入 min(context_limit, 50)，
        慢脑/默认吃全量。非法/缺省回退 PLATFORM_HISTORY_LIMIT_DEFAULT。
        """
        keep = int(limit) if (limit is not None and int(limit) > 0) else PLATFORM_HISTORY_LIMIT_DEFAULT
        history: list[dict] = []
        for msg in conv.get("messages", [])[-keep:]:
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

    async def _execute_platform_tool(
        self,
        tool_name: str,
        arguments: dict,
        adapter,
        instance_id: str = "",
    ) -> dict:
        """执行平台工具调用（standard 子集或平台专用）。

        查找顺序：
        1. 平台专用工具（adapter.execute_platform_tool，名称含 "." 前缀）
        2. tool_registry 中的内置工具（function calling 工具）
        3. internal_tool_registry 中的工作流内部工具

        高风险闸门（W3-3 执行侧兜底）：工具名命中 HIGH_RISK_PLATFORM_TOOLS
        且实例未开启 platform_tools_risk_enabled 时，直接拒绝执行。
        注入面（filter_tools_by_risk）与执行面在此双闸，防两处不同步
        （如工具注入后实例开关被关闭、或模型幻觉拼出未注入的工具名）。
        """
        # 兼容处理被 LLM 转义的工具名（如 mc__navigate -> mc.navigate）
        normalized_name = tool_name.replace("__", ".") if ("__" in tool_name and "." not in tool_name) else tool_name

        # 高风险平台操作执行侧兜底（W3-3，默认拒绝）
        if (
            normalized_name in HIGH_RISK_PLATFORM_TOOLS
            and not self._is_platform_risk_enabled(instance_id)
        ):
            platform_logger.log(
                instance_id or "unknown", "warning", "high_risk_tool_blocked",
                f"已拦截高风险平台工具调用: {normalized_name}（实例未开启风险开关）",
                details={"tool_name": normalized_name},
            )
            return {"success": False, "output": "", "error": HIGH_RISK_TOOL_BLOCKED_MESSAGE}

        from app.core.tools.registry import tool_registry
        from app.core.workflow.internal_registry import internal_tool_registry

        # 先尝试平台专用工具（adapter 实现）
        if "." in normalized_name and adapter and hasattr(adapter, "execute_platform_tool"):
            try:
                result = await adapter.execute_platform_tool(normalized_name, arguments)
                return result
            except Exception as e:
                return {"success": False, "output": "", "error": str(e)}

        # 再尝试 tool_registry（内置 function calling 工具）
        tool = tool_registry.get(tool_name)
        if tool:
            try:
                result = await tool.execute(arguments)
                return {
                    "success": result.success,
                    "output": result.output,
                    "error": result.error,
                    "metadata": result.metadata,
                }
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

    # ── G0 新增辅助（平台管道收敛 / 三层上下文 / 分段发送）─────────────

    @staticmethod
    def _normalize_platform_llm_result(ctx: AgentContext, result) -> Any:
        """标签协议覆盖平台域（G0，计划书 §6 G0 行）：content 过五类合同标签
        解析器剥离（QQ 等文本渠道不渲染表情/皮套标签），dispatch 标签写入挂点
        供 DispatchMiddleware 消费。解析器任何异常都放行原文（绝不中断路由）。"""
        try:
            if not isinstance(result, dict):
                return result
            content = result.get("content")
            if not (isinstance(content, str) and content):
                return result
            parser = TagStreamParser()
            clean, events = parser.feed(content)
            tail, tail_events = parser.flush()
            events = list(events) + list(tail_events)
            clean_text = (clean + tail).strip()
            # dispatch 挂点（多轮工具循环每轮都会解析，游标消费防重复）
            for ev in events:
                if getattr(ev, "kind", "") == "dispatch" and isinstance(getattr(ev, "value", None), dict):
                    ctx.state.setdefault(TASK_DISPATCH_DETECTED_KEY, []).append(ev.value)
            result["content"] = clean_text
            return result
        except Exception as e:
            logger.debug(f"[PlatformRouter] 标签解析跳过（放行原文）: {e}")
            return result

    @staticmethod
    def _build_segment_params(group_cfg: dict) -> SegmentParams:
        """群配置 → 分段参数（G0-D；字段缺省回退 AstrBot 实测口径）。"""
        try:
            return SegmentParams(
                max_chars=int(group_cfg.get("segment_max_chars") or 150),
                delay_mode=str(group_cfg.get("segment_delay_mode") or "log"),
                log_base=float(group_cfg.get("segment_log_base") or 2.6),
                delay_min=float(group_cfg.get("segment_delay_min") or 1.5),
                delay_max=float(group_cfg.get("segment_delay_max") or 3.5),
                think_base=float(group_cfg.get("segment_think_base") or 1.2),
                think_jitter=float(group_cfg.get("segment_think_jitter") or 2.0),
            )
        except (TypeError, ValueError):
            return SegmentParams()

    async def _send_platform_text(
        self,
        instance_id: str,
        target: str,
        text: str,
        *,
        reply_to: str | None = None,
        params: SegmentParams | None = None,
    ) -> None:
        """经适配器发送文本（G0-D：params 非空时按分段计划延迟逐段发送）。

        思考延迟/段间延迟都在本协程内 sleep——调用方必须以后台任务运行，
        绝不占用适配器读循环（P2-1 队头阻塞教训）。
        """
        text = (text or "").strip()
        if not text or not (target or "").strip():
            return
        adapter = get_adapter(instance_id)
        if adapter is None:
            logger.warning(f"[PlatformRouter] 分段发送跳过：实例 {instance_id} 无适配器")
            return
        plan = segment_reply_plan(text, params) if params is not None else [(text, 0.0)]
        sent = 0
        for seg, delay in plan:
            if delay > 0:
                await asyncio.sleep(delay)
            try:
                ok = await adapter.send_message(
                    PlatformResponse(content=seg, message_type="text", reply_to=reply_to),
                    target,
                )
                if ok:
                    sent += 1
            except Exception as e:
                logger.warning(f"[PlatformRouter] 分段发送失败（段 {sent + 1}/{len(plan)}）: {e}")
        platform_logger.log(
            instance_id, "success", "segmented_sent",
            f"分段发送完成: {sent}/{len(plan)} 段",
            details={"target": target, "total_chars": len(text)},
        )

    async def _build_dispatch_context(self, conv_id: str, limit: int) -> str:
        """G0-C：慢脑派发附加上下文 = 滚动摘要 + 最近 limit 条全量。

        经 ctx.extra["dispatch_context"] 传入派发中间件（_context_snapshot 优先
        消费，8000 字符裁剪在中间件侧）；构建失败回退空串（最小快照兜底）。
        """
        try:
            parts: list[str] = []
            summary_entry = await luominest_config_store.get_async(f"{SUMMARY_NAMESPACE}{conv_id}")
            if isinstance(summary_entry, dict) and str(summary_entry.get("summary") or "").strip():
                parts.append(f"[会话滚动摘要（事实性压缩）]\n{str(summary_entry['summary']).strip()}")
            conv = await conversation_store.get_async(conv_id)
            lines: list[str] = []
            for msg in (conv or {}).get("messages", [])[-int(limit):]:
                role = msg.get("role")
                content = msg.get("content")
                if not role or not content:
                    continue
                text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
                lines.append(f"{role}: {text}")
            if lines:
                parts.append("[近期消息全量]\n" + "\n".join(lines))
            return "\n\n".join(parts)
        except Exception as e:
            logger.debug(f"[PlatformRouter] dispatch_context 构建失败（回退最小快照）: {e}")
            return ""

    async def _maybe_update_rolling_summary(
        self, conv_id: str, session_provider: str, session_model: str,
    ) -> None:
        """G0-C 滚动摘要低频维护（拍板⑪）：慢脑维护，新增 ≥N 条触发。

        摘要 = 纯事实性压缩（谁说了什么/决定了什么/关键实体与数字），与 G1
        reflection 的认知性升华相邻不合并。存储于 config_items 独立键
        （platform.summaries.{conv_id}），不写回 conv 对象——后台写与热路径
        会话写并发时互不覆盖。
        """
        try:
            conv = await conversation_store.get_async(conv_id)
            messages = (conv or {}).get("messages") or []
            key = f"{SUMMARY_NAMESPACE}{conv_id}"
            entry = await luominest_config_store.get_async(key)
            if not isinstance(entry, dict):
                entry = {}
            upto = int(entry.get("upto_count") or 0)
            if len(messages) - upto < ROLLING_SUMMARY_TRIGGER:
                return
            prev_summary = str(entry.get("summary") or "")
            incremental: list[str] = []
            for msg in messages[upto:]:
                role = msg.get("role")
                content = msg.get("content")
                if not role or not content:
                    continue
                text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
                incremental.append(f"{role}: {text}")
            if not incremental:
                return

            # 慢脑优先（拍板⑪），未配置慢脑回退会话模型
            provider, model = session_provider, session_model
            try:
                from app.core.agents.middleware.dispatch import resolve_slow_brain
                slow = resolve_slow_brain()
                if slow and slow.get("provider"):
                    provider = slow["provider"]
                    model = slow.get("model") or model
            except Exception as e:
                logger.debug(f"[PlatformRouter] 慢脑解析失败，摘要回退会话模型: {e}")

            result = await llm_adapter.chat(
                messages=[
                    {"role": "system", "content": _ROLLING_SUMMARY_SYSTEM_PROMPT},
                    {"role": "user", "content": (
                        f"[既有摘要]\n{prev_summary or '（无）'}\n\n"
                        f"[新增消息]\n" + "\n".join(incremental[-120:])
                    )},
                ],
                stream=False,
                provider_name=provider,
                model=model,
                temperature=0.2,
                max_tokens=800,
                route_hint=RouteHint.CHAT,
            )
            new_summary = extract_llm_text(result).strip() if result else ""
            if not new_summary:
                return
            await luominest_config_store.set_async(key, {
                "summary": new_summary,
                "upto_count": len(messages),
                "updated_at": utc_now(),
            })
            logger.info(
                f"[PlatformRouter] 滚动摘要已更新: conv={conv_id}, "
                f"upto={len(messages)}, chars={len(new_summary)}"
            )
        except Exception as e:
            logger.warning(f"[PlatformRouter] 滚动摘要维护失败（静默跳过）: {e}")

    @staticmethod
    async def _persist_conv(conv_id: str, conv: dict) -> None:
        conv["updated_at"] = utc_now()
        await conversation_store.set_async(conv_id, conv)

    @staticmethod
    async def _schedule_memory_update(
        messages: list[dict], thread_id: str, assistant_text: str,
        *, domain: str = "", user_key: str = "", group_id: str = "", memory_write: bool = False,
    ) -> None:
        try:
            await context_service.schedule_memory_update(
                messages, thread_id, MAIN_AGENT_ID,
                llm_adapter=llm_adapter,
                domain=domain, user_key=user_key, group_id=group_id,
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
