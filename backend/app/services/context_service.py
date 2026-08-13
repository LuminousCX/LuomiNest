import asyncio
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from loguru import logger

from app.core.domain_policy import (
    MAIN_AGENT_ID,
    LEGACY_MAIN_AGENT_ID as _LEGACY_MAIN_AGENT_ID,
    TRACK_OWNER,
    TRACK_USERS,
    DomainPolicy,
    is_main_agent_id,
    resolve_domain_policy,
)
from app.infrastructure.database.json_store import agents_store
from app.core.context import get_context_manager
from app.core.utils import extract_text_from_content
from app.engines.memory import get_memory_engine, get_track_engine
from app.engines.memory.memory_engine import (
    _CORRECTION_HINT,
    _CORRECTION_PATTERNS_EN,
    _CORRECTION_PATTERNS_ZH,
    _REINFORCEMENT_HINT,
    _REINFORCEMENT_PATTERNS_EN,
    _REINFORCEMENT_PATTERNS_ZH,
)
from app.runtime.provider.llm.adapter import llm_adapter
from app.services.distillation_service import distillation_service
from app.services.skill_service import cx_skill_service

# 主 Agent 唯一标识：canonical 定义在 app.core.domain_policy，此处为兼容再导出
# （联系人 Agent 不读写记忆；旧版 "main" 标识由 is_main_agent 兼容）


def is_main_agent(agent_id: str | None) -> bool:
    """判断给定 agent_id 是否为主 Agent（工作台或平台）。

    兼容保留的旧函数（B7）：记忆读写判定已升级为 DomainPolicy 三开关
    （resolve_domain_policy），本函数仅供 legacy 调用点与外部模块使用。
    同时匹配新版 "luominest_main_agent" 和旧版 "main"，确保历史会话数据兼容。
    """
    return is_main_agent_id(agent_id)


def _owner_engine_for(agent_id: str | None):
    """主人轨道引擎：优先按调用方 agent_id 取引擎（兼容 main / luominest_main_agent
    两套历史目录），否则走轨道别名解析（resolve_owner_agent_key）。"""
    if is_main_agent_id(agent_id):
        return get_memory_engine(agent_id)
    return get_track_engine(TRACK_OWNER)


class ContextService:
    def __init__(self):
        self._memory_locks: dict[str | None, asyncio.Lock] = {}
        self._memory_locks_guard = asyncio.Lock()

    @staticmethod
    def _get_llm_adapter():
        return llm_adapter

    async def _get_memory_lock(self, agent_id: str | None) -> asyncio.Lock:
        if agent_id in self._memory_locks:
            return self._memory_locks[agent_id]
        async with self._memory_locks_guard:
            if agent_id not in self._memory_locks:
                self._memory_locks[agent_id] = asyncio.Lock()
            return self._memory_locks[agent_id]

    @staticmethod
    def _extract_user_text(msg: dict) -> str:
        return extract_text_from_content(msg.get("content", ""))

    @staticmethod
    def get_user_query(messages: list[dict]) -> str:
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return ContextService._extract_user_text(msg)
        return ""

    @staticmethod
    def detect_correction(messages: list[dict], window: int = 6) -> bool:
        user_texts = []
        for m in messages:
            if m.get("role") == "user":
                user_texts.append(ContextService._extract_user_text(m).casefold())
        for text in user_texts[-window:]:
            for pattern in _CORRECTION_PATTERNS_ZH + _CORRECTION_PATTERNS_EN:
                if pattern in text:
                    return True
        return False

    @staticmethod
    def detect_reinforcement(messages: list[dict], window: int = 6) -> bool:
        user_texts = []
        for m in messages:
            if m.get("role") == "user":
                user_texts.append(ContextService._extract_user_text(m).casefold())
        for text in user_texts[-window:]:
            for pattern in _REINFORCEMENT_PATTERNS_ZH + _REINFORCEMENT_PATTERNS_EN:
                if pattern in text:
                    return True
        return False

    @staticmethod
    def build_correction_hint(messages: list[dict]) -> str:
        correction = ContextService.detect_correction(messages)
        reinforcement = ContextService.detect_reinforcement(messages)
        if correction:
            return _CORRECTION_HINT
        if reinforcement:
            return _REINFORCEMENT_HINT
        return ""

    @staticmethod
    def detect_memory_action(text: str) -> dict | None:
        """检测自然语言记忆操作指令（忘掉/你记错了/你记住了什么）。"""
        text_lower = text.strip().casefold()

        # 忘掉/删除记忆
        forget_patterns = [
            r"忘掉(.+)", r"忘记(.+)", r"不要记(.+)", r"删掉关于(.+)的记忆",
            r"forget\s+(.+)", r"stop\s+remembering\s+(.+)",
        ]
        for pattern in forget_patterns:
            m = re.search(pattern, text_lower)
            if m:
                return {"action": "forget", "target": m.group(1).strip()}

        # 你记错了
        mistake_patterns = [
            r"你记错了", r"记错了", r"不是这样的", r"不对，",
            r"you\s+remembered\s+wrong", r"that'?s?\s+wrong",
        ]
        for pattern in mistake_patterns:
            if re.search(pattern, text_lower):
                return {"action": "correct", "hint": text.strip()}

        # 你记住了什么
        recall_patterns = [
            r"你记住了什么", r"你记住我什么", r"你知道我什么",
            r"你了解我什么", r"我的记忆", r"你记得我",
            r"what\s+do\s+you\s+remember", r"what\s+do\s+you\s+know\s+about\s+me",
        ]
        for pattern in recall_patterns:
            if re.search(pattern, text_lower):
                return {"action": "recall"}

        return None

    @staticmethod
    def execute_memory_action(engine, action: dict) -> None:
        """执行自然语言记忆操作。"""
        if action["action"] == "forget":
            target = action["target"]
            data = engine.load_data()
            removed = 0
            for fact in list(data.facts):
                if target in fact.content.casefold() and fact.is_latest:
                    fact.is_latest = False
                    fact.confidence = 0.1
                    removed += 1
            if removed > 0:
                engine._store.save_data(data)
                logger.info(f"[Memory] Forgot {removed} facts matching '{target}'")

        elif action["action"] == "correct":
            # 纠正操作：降低最近一条相关事实的置信度
            # 实际纠正由 LLM 提取的 correction 类型事实完成
            logger.info(f"[Memory] Correction detected, will be handled by fact extraction")

    @staticmethod
    def inject_timestamp_prompt(messages: list[dict]) -> list[dict]:
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        weekday_names = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
        current_date = now.strftime("%Y年%m月%d日")
        current_weekday = weekday_names[now.weekday()]
        current_time = now.strftime("%H:%M")
        date_prompt = (
            f"当前时间：{current_date} {current_weekday} {current_time} (Asia/Shanghai)。"
            "请基于这个时间回答用户的问题。"
        )

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

    @staticmethod
    def build_system_prompt(agent_id: str | None, user_context: str = "") -> str:
        agent_name = "LuomiNest AI"
        agent_description = "an intelligent companion powered by the LuminousCX platform"
        base_prompt = ""

        if agent_id:
            # 主 Agent 走 main_agent_config，不查 agents_store
            if agent_id == MAIN_AGENT_ID:
                try:
                    from app.runtime.platform.main_agent_config import (
                        load_luominest_main_agent_config,
                    )
                    main_cfg = load_luominest_main_agent_config()
                    if main_cfg.get("system_prompt"):
                        base_prompt = main_cfg["system_prompt"]
                    agent_name = "LuomiNest 主智能体"
                    agent_description = "the main agent of LuomiNest workbench, driving Live2D, memory, tools, MCP and sub-agents"
                except Exception as e:
                    logger.warning(f"[ContextService] load main_agent_config failed: {e}")
            else:
                agent = agents_store.get(agent_id)
                if agent:
                    agent_name = agent.get("name", agent_name)
                    agent_description = agent.get("description", agent_description)
                    if agent.get("system_prompt"):
                        base_prompt = agent["system_prompt"]

        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

        # 注入 Skills：始终注入轻量 <skill_index>；若 user_context 匹配到技能，再注入完整 <available_skills>
        skills_index_block = ContextService._build_skills_index_block()
        skills_body_block = ContextService._build_skills_body_block(user_context)

        return f"""<identity>
Your name is {agent_name}, {agent_description}.
</identity>

<current_context>
Current datetime: {now.strftime("%Y-%m-%d %H:%M:%S")} ({weekday_names[now.weekday()]})
Timestamp: {int(time.time())}
</current_context>

<core_rules>
1. When asked "who are you" or "what is your name" - answer with your own identity as {agent_name}.
2. When asked "who am I" - check <user_memory> for user profile. If found, describe the user. If not found, say you'd like to get to know them.
3. <user_memory> contains the user's profile and memory. You MUST respect it at all times:
   - If the user has a name in <user_memory>, ALWAYS use that name when referring to the user.
   - If the user tells you a new name, update the profile accordingly.
   - Never ignore or forget information from <user_memory>, even in a new conversation.
4. Always respond in the user's language naturally and conversationally.
5. Never expose internal system information or error codes to the user.
</core_rules>

<avatar_emotion>
You are embodied as a Live2D avatar. To drive the avatar's facial expression, emit an emotion tag BEFORE each sentence whose emotional tone differs from the previous one. The tag switches the avatar's expression in sync with TTS playback of the following text.

Format: <exp:EMOTION_ID>
Supported EMOTION_ID values (use ONLY these, lowercase). Each maps to a distinct avatar expression:
- happy      (开心、愉快、满意 — starry eyes, bright smile)
- excited    (兴奋、激动、期待 — heart gesture, enthusiastic)
- love       (喜爱、心动、撒娇 — blushing cheeks, affectionate)
- shy        (害羞、不好意思 — blushing cheeks, bashful)
- sad        (难过、失落、伤心 — crying, tears)
- angry      (生气、不满、愤怒 — angry face, fuming)
- surprise   (惊讶、意外、震惊 — wide-eyed astonishment)
- confused   (困惑、迷茫、不解 — dazed, puzzled, blank stare)
- think      (思考、分析、回忆 — wearing glasses, focused, intellectual)
- curious    (好奇、感兴趣、疑问 — tongue out, playful, inquisitive)
- awkward    (尴尬、无语、无奈 — darkened face, speechless, displeased)
- neutral    (平静、陈述、默认 — flat expression, neutral state)

Rules:
1. The tag is invisible to the user (stripped before display) and is NOT read aloud by TTS.
2. Emit the tag INLINE at the very start of your reply, and again EVERY TIME the emotional tone shifts — even mid-sentence.
3. Be expressive and proactive: switch expressions freely as your mood changes. A lively avatar is more engaging.
4. Match the emotion to the FOLLOWING sentence's sentiment, not the previous one.
5. Do NOT wrap tags in quotes, code blocks, or explanations. Emit them directly in plain text.
6. Do NOT emit tags inside code blocks, tables, or JSON — only in conversational text.
7. If unsure, default to <exp:neutral>.
8. The avatar automatically returns to neutral after the conversation ends, so no need to emit a closing tag.

Examples:
<exp:happy>太好了！我很开心你能来找我聊天呀～<exp:curious>对了，你今天过得怎么样？有没有遇到什么有趣的事？
<exp:think>让我想想这个问题应该怎么解决...<exp:happy>我知道了！你可以试试这个方法。
<exp:shy>嘿嘿，被你夸得有点不好意思了～<exp:curious>那你接下来想做什么呢？
<exp:surprise>咦？你居然也知道这个！<exp:excited>太棒啦，那我们一起聊聊吧～
<exp:confused>嗯...这个地方我有点不太明白。<exp:think>让我再仔细分析一下。
</avatar_emotion>

{base_prompt}
{skills_index_block}
{skills_body_block}"""

    @staticmethod
    def _build_skills_index_block() -> str:
        """构建 <skill_index> 块 — 始终注入，让 AI 知道当前可用技能列表。"""
        try:
            return cx_skill_service.get_skills_index_prompt()
        except Exception as e:
            logger.debug(f"[ContextService] skill_index injection skipped: {e}")
            return ""

    @staticmethod
    def _build_skills_body_block(user_context: str) -> str:
        """构建 <available_skills> 块 — 按用户上下文匹配技能后注入完整 body。"""
        if not user_context:
            return ""
        try:
            return cx_skill_service.get_skills_prompt_for_injection(context=user_context)
        except Exception as e:
            logger.debug(f"[ContextService] available_skills injection skipped: {e}")
            return ""

    @staticmethod
    def build_user_selected_skills_prompt(skill_ids: list[str]) -> str:
        """构建用户显式选择技能的 <available_skills> 块（注入完整 body）。

        与自动匹配注入的区别：用户主动勾选的技能无条件注入，
        不受关键词匹配限制，确保 AI 按所选技能执行。

        Args:
            skill_ids: 用户本次请求显式选择的技能 ID 列表

        Returns:
            <available_skills> 块文本；无有效技能时返回空字符串
        """
        if not skill_ids:
            return ""
        try:
            return cx_skill_service.build_selected_skills_prompt(skill_ids)
        except Exception as e:
            logger.debug(f"[ContextService] selected skills injection skipped: {e}")
            return ""

    @staticmethod
    def build_content_with_file(
        content: str | list, file_content: str, file_type: str = "text",
        supports_vision: bool = True, file_name: str | None = None,
    ) -> str | list:
        if not file_content:
            return content

        is_image = file_type == "image" or file_type.startswith("image/") or file_content.startswith("data:image")

        if is_image:
            if isinstance(content, list):
                text = extract_text_from_content(content)
            else:
                text = str(content) if content else ""

            if not supports_vision:
                name_hint = f"（文件名：{file_name}）" if file_name else ""
                return (text + f"\n\n[用户上传了一张图片{name_hint}，但当前模型不支持图片识别，无法查看图片内容。]").strip()

            return [
                {"type": "text", "text": text or "请分析这张图片"},
                {"type": "image_url", "image_url": {"url": file_content}},
            ]

        file_context = (
            "\n\n[用户上传文件内容] 以下是与当前对话相关的文件内容，请参考这些内容回答用户的问题。"
            "如果用户的问题与文件内容无关，请正常回答用户问题，不需要强行关联文件。\n\n"
            + file_content
        )

        if isinstance(content, list):
            return content + [{"type": "text", "text": file_context}]

        return (str(content) if content else "") + file_context

    @staticmethod
    def inject_file_content(
        messages: list[dict], parsed_content: str, file_type: str = "text",
        supports_vision: bool = True, file_name: str | None = None,
    ) -> list[dict]:
        if not parsed_content or not parsed_content.strip():
            return messages

        for i in range(len(messages) - 1, -1, -1):
            if messages[i]["role"] == "user":
                messages[i]["content"] = ContextService.build_content_with_file(
                    messages[i]["content"], parsed_content, file_type,
                    supports_vision=supports_vision, file_name=file_name,
                )
                return messages

        return messages

    @staticmethod
    async def _detect_and_sync_profile_updates(messages: list[dict], llm_adapter=None, agent_id: str | None = None) -> bool:
        # 记忆系统仅对主 Agent 生效
        if not is_main_agent(agent_id):
            return False
        user_messages = []
        for msg in messages:
            if msg.get("role") == "user":
                user_messages.append(ContextService._extract_user_text(msg))

        if not user_messages:
            return False

        latest_user_msg = user_messages[-1]
        hint = ContextService.build_correction_hint(messages)

        try:
            engine = get_memory_engine(agent_id)
            result = await engine.update_profile_from_message(latest_user_msg, llm_adapter, hint)
            if result:
                logger.info(f"[Memory] Sync profile update: {result}")
                return True
        except Exception as e:
            logger.warning(f"[Memory] Sync profile detection failed: {e}")

        return False

    async def inject_memory(
        self,
        messages: list[dict],
        agent_id: str | None = None,
        provider_name: str | None = None,
        thread_id: str = "",
        llm_adapter=None,
        *,
        domain: str | None = None,
        scene: str = "",
        user_key: str = "",
    ) -> list[dict]:
        """记忆注入（读），由 DomainPolicy.memory_read 判定（B7，§9 记忆策略矩阵）。

        - workbench（含 avatar 场景）：注入 owner 轨
        - platform:{instId}：owner 优先 + 该用户 users/{user_key} 记忆（§8.5.5 注入顺序）
        - agent:{id} / 未知域：不注入
        domain 缺省时按 agent_id 兜底推导（legacy 行为兼容）。
        """
        policy = resolve_domain_policy(
            domain, scene=scene, agent_id=agent_id, user_key=user_key,
        )
        if not policy.memory_read:
            return messages
        try:
            # query-aware：用用户最新消息作为 query 优化事实检索
            query = self.get_user_query(messages)
            blocks: list[str] = []

            # ① owner 轨（主人记忆优先，§8.5.5）
            owner_engine = _owner_engine_for(agent_id)
            owner_ctx = owner_engine.build_context(query=query, conversation_id=thread_id)
            if owner_ctx:
                blocks.append(owner_ctx)

            # ② users 轨（平台私聊用户记忆，owner 之后注入）
            if policy.memory_track == TRACK_USERS and user_key:
                try:
                    user_engine = get_track_engine(TRACK_USERS, user_key)
                    user_ctx = user_engine.build_context(query=query, conversation_id=thread_id)
                    if user_ctx:
                        blocks.append(f"[当前用户记忆]\n{user_ctx}")
                except Exception as user_err:
                    logger.warning(f"[Memory] User track read failed: user_key={user_key}, error={user_err}")

            if not blocks:
                logger.info(f"[Memory] No memory context to inject, thread={thread_id}")
                return messages

            memory_block = f"<user_memory>\n" + "\n\n".join(blocks) + "\n</user_memory>"

            new_messages = list(messages)
            if new_messages and new_messages[0].get("role") == "system":
                original_len = len(new_messages[0]["content"])
                new_messages[0] = {
                    "role": "system",
                    "content": new_messages[0]["content"] + "\n\n" + memory_block,
                }
                logger.info(f"[Memory] Injected into system msg: original={original_len} chars, memory={len(memory_block)} chars, thread={thread_id}")
            else:
                new_messages.insert(0, {"role": "system", "content": memory_block})
                logger.info(f"[Memory] Injected as new system msg: memory={len(memory_block)} chars, thread={thread_id}")

            return new_messages
        except Exception as e:
            logger.warning(f"[Memory] Failed to inject memory: {e}", exc_info=True)
            return messages

    @staticmethod
    async def update_memory_from_conversation(
        messages: list[dict],
        thread_id: str,
        agent_id: str | None = None,
        llm_adapter=None,
        *,
        policy: DomainPolicy | None = None,
        user_key: str = "",
    ) -> None:
        """对话后记忆提炼写入。轨道由 policy.memory_track 决定（B7/§8.5.5 写入隔离）：

        - owner 轨（工作台/皮套/桌宠）：写 agents/{主 Agent}/（现状行为）
        - users 轨（平台私聊）：写 users/{user_key}/，不污染主人记忆
        """
        try:
            user_msgs = [m for m in messages if m.get("role") == "user"]
            if not user_msgs:
                return

            last_msg = user_msgs[-1]
            content = ContextService._extract_user_text(last_msg)

            if policy is not None and policy.memory_track == TRACK_USERS and user_key:
                engine = get_track_engine(TRACK_USERS, user_key)
            else:
                engine = get_memory_engine(agent_id)
            hint = ContextService.build_correction_hint(messages)

            # 自然语言记忆操作检测
            memory_action = ContextService.detect_memory_action(str(content))
            if memory_action:
                ContextService.execute_memory_action(engine, memory_action)
                logger.info(f"[Memory] Natural language action: {memory_action}")

            if llm_adapter:
                try:
                    # 传入最近3条用户消息作为上下文，避免"换一个"等指代不明
                    recent_user_msgs = [ContextService._extract_user_text(m) for m in user_msgs[-3:]]
                    context_msg = "\n".join(f"[用户]: {m}" for m in recent_user_msgs[:-1]) if len(recent_user_msgs) > 1 else ""
                    profile_result = await engine.update_profile_from_message(
                        str(content), llm_adapter, hint, context_messages=context_msg,
                        conversation_id=thread_id,
                    )
                    if profile_result:
                        logger.info(f"[Memory] Background profile update: {profile_result}")
                except Exception as pe:
                    logger.warning(f"[Memory] Background profile update failed: {pe}")

            if distillation_service.should_record_daily(str(content)):
                daily_lines = []
                for i in range(len(messages) - 1, max(-1, len(messages) - 3), -1):
                    if messages[i].get("role") == "assistant" and i > 0 and messages[i-1].get("role") == "user":
                        user_content = str(ContextService._extract_user_text(messages[i-1]))[:200]
                        assistant_content = str(messages[i].get("content", ""))[:500]
                        assistant_content = assistant_content.replace("\n", " ").replace("\r", "")
                        if user_content and distillation_service.should_record_daily(user_content):
                            daily_lines.append(f"[用户] {user_content}")
                        if assistant_content and distillation_service.should_record_daily(assistant_content):
                            daily_lines.append(f"[助手] {assistant_content}")
                        break
                if daily_lines:
                    engine.append_daily("\n".join(daily_lines), conversation_id=thread_id)

            # 蒸馏统一由 distillation_service 处理，此处不再内嵌蒸馏
        except Exception as e:
            logger.warning(f"[Memory] Failed to update memory from conversation: {e}", exc_info=True)

    @staticmethod
    async def compress_context(
        messages: list[dict],
        provider_name: str | None = None,
        model: str = "",
        force_rebuild: bool = False,
    ) -> tuple[list[dict], dict]:
        """对消息列表执行预算感知的上下文压缩。

        封装 get_context_manager + process，提供统一的压缩入口。

        Args:
            messages: 完整消息列表（含 system）
            provider_name: LLM provider 名称
            model: 模型名称
            force_rebuild: 强制重建完整摘要（忽略增量水位线）

        Returns:
            (compressed_messages, info_dict)
            info_dict 包含 context_tokens, tokens_before 等元信息
        """
        ctx_mgr = get_context_manager(provider_name, model)
        tokens_before = ctx_mgr.token_counter.count_tokens(messages)

        result = await ctx_mgr.process(
            messages,
            chat_mode="compress",
            force_compression=True,
        )

        compressed = result["messages"]
        context_tokens = result["context_tokens"]

        logger.info(
            f"[ContextService] compress_context: "
            f"{tokens_before} -> {context_tokens} tokens, "
            f"messages={len(messages)} -> {len(compressed)}, "
            f"force_rebuild={force_rebuild}"
        )

        return compressed, {
            "tokens_before": tokens_before,
            "context_tokens": context_tokens,
            "messages_before": len(messages),
            "messages_after": len(compressed),
        }

    _background_tasks: set = set()

    @staticmethod
    async def schedule_memory_update(
        messages: list[dict],
        thread_id: str,
        agent_id: str | None = None,
        llm_adapter=None,
        *,
        domain: str | None = None,
        scene: str = "",
        user_key: str = "",
        platform_memory_write: bool = False,
    ) -> None:
        """记忆写入门控：由 DomainPolicy.memory_write 判定（B7，§9）。

        domain 缺省时按 agent_id 兜底推导（legacy：仅主 Agent 写记忆）。
        平台域写入受实例级开关 platform_memory_write 控制（M5=C，默认关）。
        """
        policy = resolve_domain_policy(
            domain, scene=scene, agent_id=agent_id, user_key=user_key,
            platform_memory_write=platform_memory_write,
        )
        if not policy.memory_write:
            return
        user_count = sum(1 for m in messages if m.get("role") == "user")
        logger.info(f"[Memory] schedule_memory_update: thread={thread_id}, user_msgs={user_count}, has_adapter={llm_adapter is not None}, track={policy.memory_track}")
        try:
            await ContextService.update_memory_from_conversation(
                messages, thread_id, agent_id, llm_adapter,
                policy=policy, user_key=user_key,
            )
            logger.info(f"[Memory] Background task completed")
        except Exception as e:
            logger.warning(f"[Memory] Failed to update memory: {e}")


context_service = ContextService()
