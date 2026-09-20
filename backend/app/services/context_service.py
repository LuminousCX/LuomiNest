import asyncio
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from loguru import logger

from app.core.domain_policy import (
    MAIN_AGENT_ID,
    KIND_PLATFORM,
    LEGACY_MAIN_AGENT_ID as _LEGACY_MAIN_AGENT_ID,
    TRACK_OWNER,
    TRACK_USERS,
    TRACK_GROUPS,
    DomainPolicy,
    is_main_agent_id,
    resolve_domain_policy,
)
from app.infrastructure.database.json_store import agents_store
from app.core.context import get_context_manager
from app.core.utils import AsyncKeyLocks, extract_text_from_content
from app.engines.memory import get_memory_engine, get_track_engine
from app.engines.memory.memory_engine import (
    _CORRECTION_HINT,
    _CORRECTION_PATTERNS_EN,
    _CORRECTION_PATTERNS_ZH,
    _REINFORCEMENT_HINT,
    _REINFORCEMENT_PATTERNS_EN,
    _REINFORCEMENT_PATTERNS_ZH,
    build_group_members_block,
)
from app.runtime.provider.llm.adapter import llm_adapter
from app.services.distillation_service import distillation_service
from app.services.skill_service import luominest_skill_service

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
    """owner 轨引擎：子 Agent 读各自 owner:{agent_id}（记忆中枢可选页），
    主 Agent / 缺省读主人轨（resolve_owner_agent_key 别名过渡）。

    A 方案：agent:{id} 域由 NONE_POLICY 改为 owner 轨读写，读侧随之
    从「fallback 主人轨」改为「各自 Agent 轨」，否则切换查看永远为空。
    """
    if agent_id and not is_main_agent_id(agent_id):
        return get_memory_engine(agent_id)
    return get_track_engine(TRACK_OWNER)


class ContextService:
    def __init__(self):
        self._memory_locks = AsyncKeyLocks()

    @staticmethod
    def _get_llm_adapter():
        return llm_adapter

    async def _get_memory_lock(self, agent_id: str | None) -> asyncio.Lock:
        return await self._memory_locks.get(agent_id)

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
    def detect_correction(messages: list[dict], window: int = 2) -> bool:
        user_texts = []
        for m in messages:
            if m.get("role") == "user":
                user_texts.append(ContextService._extract_user_text(m).casefold())
        for text in user_texts[-window:]:
            for pattern in _CORRECTION_PATTERNS_ZH + _CORRECTION_PATTERNS_EN:
                if pattern in text:
                    logger.info(f"[Memory] Correction hint triggered by pattern={pattern!r} in text={text!r}")
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
    async def execute_memory_action(engine, action: dict) -> None:
        """执行自然语言记忆操作。"""
        if action["action"] == "forget":
            target = action["target"]

            def _apply_forget(data) -> int:
                removed = 0
                for fact in list(data.facts):
                    if target in fact.content.casefold() and fact.is_latest:
                        fact.is_latest = False
                        fact.confidence = 0.1
                        removed += 1
                return removed

            # 引擎写锁 + store 原子 mutate：forget 与蒸馏/CRUD 并发时不相互覆盖
            async with engine.write_lock:
                removed = await asyncio.to_thread(engine.forget_facts, _apply_forget)
            if removed > 0:
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
                    agent_name = str(main_cfg.get("name") or "主Agent").strip()
                    agent_description = "the main agent of the workbench and integrated platforms, driving Live2D, memory, tools, and sub-agents"
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
1. 当被问"你是谁"或"你叫什么名字"时，用你自己的身份回答，即 {agent_name}。
2. 当被问"我是谁"时，查看 <user_memory> 中的用户档案。找到则描述该用户；未找到则说你希望进一步了解对方。
3. <user_memory> 包含用户的档案与记忆，你必须时刻遵守：
   - 如果 <user_memory> 中有用户的名字，提及该用户时始终使用这个名字。
   - 如果用户告诉你一个新名字，相应地更新档案。
   - 即使开启新对话，也绝不可忽略或遗忘 <user_memory> 中的信息。
4. 始终用用户的语言自然、口语化地回复。
5. 绝不对用户暴露内部系统信息或错误码。
6. 内部思考与规则复述一律使用中文；回复语言跟随用户。
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
            return luominest_skill_service.get_skills_index_prompt()
        except Exception as e:
            logger.debug(f"[ContextService] skill_index injection skipped: {e}")
            return ""

    @staticmethod
    def _build_skills_body_block(user_context: str) -> str:
        """构建 <available_skills> 块 — 按用户上下文匹配技能后注入完整 body。"""
        if not user_context:
            return ""
        try:
            return luominest_skill_service.get_skills_prompt_for_injection(context=user_context)
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
            return luominest_skill_service.build_selected_skills_prompt(skill_ids)
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
        group_id: str = "",
        group_members: list[dict] | None = None,
        platform_name: str = "",
    ) -> list[dict]:
        """记忆注入（读），由 DomainPolicy.memory_read 判定（B7，§9 记忆策略矩阵）。

        - workbench（含 avatar 场景）：注入 owner 轨
        - platform:{instId}：owner 优先 + 群组画像(若群聊) + 说话成员 users/{track_user_key} 记忆
          （私聊 = conversation.user_key；群聊 = 粉丝成员轨 + 群聊专属记忆，防隐私泄露）
        - agent:{id}：读写各自 owner:{agent_id} 记忆（A 方案，记忆中枢可选页）
        domain 缺省时按 agent_id 兜底推导（legacy 行为兼容）。

        Args:
            group_members: 群聊在场成员条目（不含说话成员），每项
                {"sender_id", "sender_name", "user_key"}；平台域会据此叠加
                「群友画像块」（每人 top 事实摘要，读不受写开关限制）。
                私聊/工作台不传，行为与旧版完全一致。
        """
        inferred_platform = platform_name or (user_key.split("_")[0] if "_" in user_key else "")
        policy = resolve_domain_policy(
            domain, scene=scene, agent_id=agent_id, user_key=user_key, group_id=group_id,
            platform_name=inferred_platform,
        )
        if not policy.memory_read:
            return messages
        # 用户轨键以 policy 解析结果为准（群聊成员轨由 DomainPolicy 归一）
        track_key = policy.track_user_key or user_key
        is_group = bool(policy.group_track_key or group_id or group_members or (domain and "group" in domain))
        allowed_scopes = {"global", "group"} if is_group else {"global", "group", "private"}

        try:
            # query-aware：用用户最新消息作为 query 优化事实检索
            query = self.get_user_query(messages)
            blocks: list[str] = []

            # ① owner 轨（主人记忆优先，§8.5.5）
            # build_context 的同步组装含 SQLite 读，放 to_thread 执行避免阻塞事件循环
            owner_engine = _owner_engine_for(agent_id)
            owner_ctx = await asyncio.to_thread(
                owner_engine.build_context_sync,
                query=query,
                conversation_id=thread_id,
                allowed_scopes=allowed_scopes,
            )
            if owner_ctx:
                blocks.append(owner_ctx)

            # ② groups 轨（群聊场景下的粉丝群公共画像/群设定与梗）
            if is_group and policy.group_track_key:
                try:
                    group_engine = get_track_engine(TRACK_GROUPS, policy.group_track_key)
                    group_ctx = await asyncio.to_thread(
                        group_engine.build_context_sync,
                        query=query,
                        conversation_id=thread_id,
                        allowed_scopes={"global", "group"},
                    )
                    if group_ctx:
                        blocks.append(f"[群聊画像 · 群体设定]\n{group_ctx}")
                except Exception as group_err:
                    logger.warning(f"[Memory] Group track read failed: group_key={policy.group_track_key}, error={group_err}")

            # ③ users 轨（平台私聊用户 / 群聊说话成员记忆，群聊中私密事实已被严格过滤）
            if policy.memory_track == TRACK_USERS and track_key:
                try:
                    user_engine = get_track_engine(TRACK_USERS, track_key)
                    user_ctx = await asyncio.to_thread(
                        user_engine.build_context_sync,
                        query=query,
                        conversation_id=thread_id,
                        allowed_scopes=allowed_scopes,
                    )
                    if user_ctx:
                        blocks.append(f"[当前用户记忆]\n{user_ctx}")
                except Exception as user_err:
                    logger.warning(f"[Memory] User track read failed: user_key={track_key}, error={user_err}")

            # ④ 群友画像块（§8.5.10 本期实现）：在场成员轨 top 事实摘要。
            # 读不受 platform_memory_write 开关限制（平台域读语义一致，写闸门在写侧）
            if group_members and policy.kind == KIND_PLATFORM:
                member_block = await asyncio.to_thread(
                    build_group_members_block,
                    group_members,
                    exclude_keys={track_key} if track_key else None,
                )
                if member_block:
                    blocks.append(f"[群友画像]\n{member_block}")

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
        group_id: str = "",
    ) -> None:
        """对话后记忆提炼写入。轨道由 policy.memory_track 决定（B7/§8.5.5 写入隔离）：

        - owner 轨（工作台/皮套/桌宠）：写 agents/{主 Agent}/（现状行为）
        - users 轨（平台私聊/群聊成员）：写 users/{user_key}/，不污染主人记忆
        - groups 轨（群聊设定/群梗/公共事件）：当在群聊中时，公共事件同步记录至 groups/{group_key}/
        """
        try:
            user_msgs = [m for m in messages if m.get("role") == "user"]
            if not user_msgs:
                return

            last_msg = user_msgs[-1]
            content = ContextService._extract_user_text(last_msg)

            is_group = bool((policy and policy.group_track_key) or group_id or (policy and policy.domain and "group" in policy.domain))
            effective_group_id = (policy.group_track_key if policy else "") or group_id
            default_scope = "group" if is_group else ("private" if (policy and policy.memory_track == TRACK_USERS) else "global")

            if policy is not None and policy.memory_track == TRACK_USERS and user_key:
                engine = get_track_engine(TRACK_USERS, user_key)
            else:
                engine = get_memory_engine(agent_id)
            hint = ContextService.build_correction_hint(messages)

            # 自然语言记忆操作检测
            memory_action = ContextService.detect_memory_action(str(content))
            if memory_action:
                await ContextService.execute_memory_action(engine, memory_action)
                logger.info(f"[Memory] Natural language action: {memory_action}")

            if llm_adapter:
                try:
                    # 传入最近3条用户消息作为上下文，避免"换一个"等指代不明
                    recent_user_msgs = [ContextService._extract_user_text(m) for m in user_msgs[-3:]]
                    context_msg = "\n".join(f"[用户]: {m}" for m in recent_user_msgs[:-1]) if len(recent_user_msgs) > 1 else ""
                    profile_result = await engine.update_profile_from_message(
                        str(content), llm_adapter, hint, context_messages=context_msg,
                        conversation_id=thread_id,
                        default_scope=default_scope,
                        group_id=effective_group_id,
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
                    await asyncio.to_thread(
                        engine.append_daily, "\n".join(daily_lines), conversation_id=thread_id
                    )
                    # 若在群聊中，且群标识存在，群每日记录也同步追加一份群轨迹
                    if is_group and effective_group_id:
                        try:
                            group_engine = get_track_engine(TRACK_GROUPS, effective_group_id)
                            await asyncio.to_thread(
                                group_engine.append_daily, "\n".join(daily_lines), conversation_id=thread_id
                            )
                        except Exception as ge:
                            logger.warning(f"[Memory] Group daily record failed: {ge}")

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
        group_id: str = "",
        platform_memory_write: bool = False,
    ) -> None:
        """记忆写入门控：由 DomainPolicy.memory_write 判定（B7，§9）。

        domain 缺省时按 agent_id 兜底推导（legacy：仅主 Agent 写记忆）。
        平台域写入受实例级开关 platform_memory_write 控制（M5=C，默认关）。
        """
        policy = resolve_domain_policy(
            domain, scene=scene, agent_id=agent_id, user_key=user_key, group_id=group_id,
            platform_memory_write=platform_memory_write,
        )
        if not policy.memory_write:
            return
        user_count = sum(1 for m in messages if m.get("role") == "user")
        logger.info(f"[Memory] schedule_memory_update: thread={thread_id}, user_msgs={user_count}, has_adapter={llm_adapter is not None}, track={policy.memory_track}")
        try:
            await ContextService.update_memory_from_conversation(
                messages, thread_id, agent_id, llm_adapter,
                policy=policy, user_key=user_key, group_id=group_id,
            )
            logger.info(f"[Memory] Background task completed")
        except Exception as e:
            logger.warning(f"[Memory] Failed to update memory: {e}")


context_service = ContextService()
