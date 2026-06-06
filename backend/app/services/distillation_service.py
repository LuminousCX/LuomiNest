import asyncio
import hashlib
from datetime import datetime, timezone
from loguru import logger

from app.engines.memory import get_memory_engine
from app.engines.memory.prompts import _DISTILL_PROMPT_ROUND, _MERGE_SUMMARY_PROMPT


class DistillationService:
    """
    5轮滚动合并蒸馏服务

    核心流程:
    1. 每5轮(用户+AI) → 蒸馏最近5轮
    2. 新蒸馏结果 + 旧摘要 → LLM合并
    3. 合并产物覆盖写入 SUMMARY

    触发条件（满足任一即触发）：
    - Turn-count: full_turns >= 5 且有未蒸馏的新轮次
    - 对话结束: final_distill 兜底蒸馏剩余轮次
    """

    DROPLET_THRESHOLD = 5

    # 记录每个对话上次蒸馏时的轮次数，防止重复蒸馏
    _last_distilled_turns: dict[str, int] = {}

    STOP_WORDS = {
        '好', '嗯', '哦', '行', 'ok', 'OK', '好的', '嗯嗯', '嗯嗯嗯',
        '知道了', '明白', '收到', '呵呵', '哈哈', '对的',
        '是的', '没错', '可以', '👌', '👍', '👌🏻',
        '好滴', '好哒', '好呢', '好呀', '好哦',
        'okk', 'okok', 'ok啦', '好啦', '好咯',
        '嗯嗯好', '好的呢', '好的呀',
    }

    FORCE_ALLOW_KEYWORDS = {'什么', '怎么', '为什么', '谁', '哪', '哪', '?', '？'}

    PUNCTUATION = set('，。！？、；：""''（）(){}[]【】<>《》·…—–—_一')
    EMOJI_RANGES = [
        (0x1F600, 0x1F64F),  # 表情符号
        (0x1F300, 0x1F5FF),  # 杂项符号
        (0x1F680, 0x1F6FF),  # 交通工具
        (0x2600, 0x26FF),    # 杂项符号
        (0x2700, 0x27BF),    # 装饰符号
    ]

    def __init__(self):
        pass

    @staticmethod
    def reset_distill_state(conversation_id: str) -> None:
        """重置指定对话的蒸馏状态，使下次maybe_distill能重新触发"""
        DistillationService._last_distilled_turns.pop(conversation_id, None)

    @staticmethod
    def _is_emoji(char: str) -> bool:
        """判断字符是否为表情符号"""
        code = ord(char)
        for start, end in DistillationService.EMOJI_RANGES:
            if start <= code <= end:
                return True
        return False

    @staticmethod
    def should_record_daily(content: str) -> bool:
        """多信号打分器判断是否记录每日对话
        
        四个零成本信号综合判断：
        1. 去标点后 ≤1 字 → 噪音
        2. 命中黑名单（含变体） → 噪音
        3. 纯表情/纯标点 → 噪音
        4. 含"什么/怎么/为什么/谁/哪/?/？" → 强制放行
        """
        stripped = content.strip()
        
        # 空内容直接返回 False
        if not stripped:
            return False
        
        # 信号1：去标点后 ≤1 字 → 噪音
        content_without_punc = ''.join(c for c in stripped if c not in DistillationService.PUNCTUATION)
        if len(content_without_punc) <= 1:
            return False
        
        # 信号2：命中黑名单（含变体） → 噪音
        if stripped in DistillationService.STOP_WORDS:
            return False
        
        # 信号3：纯表情/纯标点 → 噪音
        has_meaningful_char = False
        for char in content_without_punc:
            if not DistillationService._is_emoji(char):
                has_meaningful_char = True
                break
        if not has_meaningful_char:
            return False
        
        # 信号4：含疑问词 → 强制放行
        for keyword in DistillationService.FORCE_ALLOW_KEYWORDS:
            if keyword in stripped:
                return True
        
        # 默认：长度≥2且不在黑名单的内容都记录
        return len(stripped) >= 2

    @staticmethod
    def count_full_turns(messages: list) -> int:
        """统计完整轮次（用户+AI）"""
        turns = 0
        i = 0
        while i < len(messages):
            if messages[i].get("role") == "user":
                if i + 1 < len(messages) and messages[i + 1].get("role") == "assistant":
                    turns += 1
                    i += 2
                else:
                    i += 1
            else:
                i += 1
        return turns

    @staticmethod
    def get_last_n_turns(messages: list, n: int) -> list:
        """获取最近n轮对话（用户+AI对）"""
        result = []
        i = len(messages) - 1
        
        while i >= 0 and n > 0:
            if messages[i].get("role") == "assistant":
                if i - 1 >= 0 and messages[i - 1].get("role") == "user":
                    result.insert(0, messages[i - 1])
                    result.insert(1, messages[i])
                    n -= 1
                    i -= 2
                else:
                    i -= 1
            else:
                i -= 1
        
        return result

    @staticmethod
    def _generate_summary_hash(agent_id: str, conversation_id: str) -> str:
        """生成摘要的唯一哈希值"""
        return hashlib.md5(f"{agent_id}:{conversation_id}".encode()).hexdigest()

    @staticmethod
    async def maybe_distill(agent_id: str, conversation_id: str, messages: list, llm_adapter=None) -> bool:
        """检查是否有未蒸馏的新轮次，有则触发蒸馏合并。

        触发条件：full_turns >= DROPLET_THRESHOLD 且有未蒸馏的增量轮次。
        通过 _last_distilled_turns 记录上次蒸馏时的轮次数，避免重复蒸馏。
        """
        full_turns = DistillationService.count_full_turns(messages)

        if full_turns < DistillationService.DROPLET_THRESHOLD:
            logger.info(f"[Distill] Skip: {full_turns} turns < {DistillationService.DROPLET_THRESHOLD}")
            return False

        last_distilled = DistillationService._last_distilled_turns.get(conversation_id, 0)
        if full_turns <= last_distilled:
            logger.info(f"[Distill] Skip: {full_turns} turns, last distilled at {last_distilled}")
            return False

        new_turns = full_turns - last_distilled
        logger.info(f"[Distill] Triggered: {full_turns} turns ({new_turns} new since last distill)")
        success = await DistillationService.distill_and_merge(agent_id, conversation_id, messages, llm_adapter)

        if success:
            DistillationService._last_distilled_turns[conversation_id] = full_turns
        return success

    @staticmethod
    async def distill_rounds(messages: list, llm_adapter=None) -> str | None:
        """蒸馏最近5轮 → 新观察"""
        if llm_adapter is None:
            try:
                from app.runtime.provider.llm.adapter import llm_adapter as default_adapter
                llm_adapter = default_adapter
            except Exception as e:
                logger.warning(f"[Distill] No LLM adapter available: {e}")
                return None

        last_5_turns = DistillationService.get_last_n_turns(messages, 5)
        if not last_5_turns:
            logger.warning("[Distill] No messages to distill")
            return None

        conv_summary = ""
        for msg in last_5_turns:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if isinstance(content, str) and content:
                conv_summary += f"[{role}] {content[:300]}\n"

        prompt = _DISTILL_PROMPT_ROUND.format(messages=conv_summary.strip())

        try:
            result = await llm_adapter.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
            )
            response_text = (
                result.strip() if isinstance(result, str) else str(result).strip()
            )
            logger.info(f"[Distill] Round distillation result: {response_text[:200]}")
            return response_text

        except Exception as e:
            logger.warning(f"[Distill] Round distillation failed: {e}")
            return None

    @staticmethod
    async def merge_summaries(old_summary: str, new_obs: str, llm_adapter=None) -> str | None:
        """旧摘要 + 新观察 → 统一摘要"""
        if llm_adapter is None:
            try:
                from app.runtime.provider.llm.adapter import llm_adapter as default_adapter
                llm_adapter = default_adapter
            except Exception as e:
                logger.warning(f"[Distill] No LLM adapter available: {e}")
                return None

        prompt = _MERGE_SUMMARY_PROMPT.format(
            old_summary=old_summary,
            new_summary=new_obs,
        )

        try:
            result = await llm_adapter.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=800,
            )
            response_text = (
                result.strip() if isinstance(result, str) else str(result).strip()
            )
            logger.info(f"[Distill] Merge result: {response_text[:200]}")
            return response_text

        except Exception as e:
            logger.warning(f"[Distill] Summary merge failed: {e}")
            return None

    @staticmethod
    async def distill_and_merge(agent_id: str, conversation_id: str, messages: list, llm_adapter=None) -> bool:
        """执行蒸馏并合并，返回是否成功"""
        try:
            new_observation = await DistillationService.distill_rounds(messages, llm_adapter)
            if not new_observation:
                logger.warning("[Distill] No new observation from distillation")
                return False

            engine = get_memory_engine(agent_id)

            # 对话级摘要：独立合并
            conv_summary = engine.load_summary() if conversation_id else ""
            if conversation_id:
                from app.engines.memory.memory_engine import get_conversation_store
                conv_store = get_conversation_store(agent_id, conversation_id)
                conv_data = conv_store.load_data()
                from app.engines.memory.models import summaries_to_markdown
                conv_summary = summaries_to_markdown(conv_data)

            if conv_summary and conv_summary.strip():
                logger.info("[Distill] Merging with existing conversation summary")
                merged_conv = await DistillationService.merge_summaries(conv_summary, new_observation, llm_adapter)
                if merged_conv:
                    engine.save_summary(merged_conv, conversation_id=conversation_id)
                else:
                    logger.warning("[Distill] Conversation merge failed, keeping original")

            # Agent级摘要：独立合并
            agent_summary = engine.load_summary()
            if agent_summary and agent_summary.strip():
                logger.info("[Distill] Merging with existing agent summary")
                merged_agent = await DistillationService.merge_summaries(agent_summary, new_observation, llm_adapter)
                if merged_agent:
                    engine.save_summary(merged_agent)
                else:
                    logger.warning("[Distill] Agent merge failed, keeping original")
            else:
                engine.save_summary(new_observation)

            return True

        except Exception as e:
            logger.error(f"[Distill] distill_and_merge failed: {e}")
            return False

    @staticmethod
    async def final_distill(agent_id: str, conversation_id: str, messages: list, llm_adapter=None):
        """对话结束触发最终蒸馏，兜底处理未蒸馏的剩余轮次"""
        full_turns = DistillationService.count_full_turns(messages)

        if full_turns < 2:
            logger.info(f"[Distill] Skip final: {full_turns} < 2 turns")
            return

        last_distilled = DistillationService._last_distilled_turns.get(conversation_id, 0)
        if full_turns <= last_distilled:
            logger.info(f"[Distill] Skip final: already distilled at {last_distilled} turns")
            return

        logger.info(f"[Distill] Final distill triggered: {full_turns} turns ({full_turns - last_distilled} unprocessed)")

        # 只蒸馏未处理的增量轮次
        unprocessed_turns = DistillationService.get_last_n_turns(messages, full_turns - last_distilled)
        new_observation = await DistillationService.distill_rounds(unprocessed_turns if unprocessed_turns else messages, llm_adapter)
        if new_observation:
            engine = get_memory_engine(agent_id)

            # 对话级摘要：独立合并
            conv_summary = ""
            if conversation_id:
                from app.engines.memory.memory_engine import get_conversation_store
                conv_store = get_conversation_store(agent_id, conversation_id)
                conv_data = conv_store.load_data()
                from app.engines.memory.models import summaries_to_markdown
                conv_summary = summaries_to_markdown(conv_data)

            if conv_summary and conv_summary.strip():
                merged_conv = await DistillationService.merge_summaries(conv_summary, new_observation, llm_adapter)
                if merged_conv:
                    engine.save_summary(merged_conv, conversation_id=conversation_id)
                else:
                    logger.warning("[Distill] Final conversation merge failed")
            elif conversation_id:
                engine.save_summary(new_observation, conversation_id=conversation_id)

            # Agent级摘要：独立合并
            agent_summary = engine.load_summary()
            if agent_summary and agent_summary.strip():
                merged_agent = await DistillationService.merge_summaries(agent_summary, new_observation, llm_adapter)
                if merged_agent:
                    engine.save_summary(merged_agent)
                else:
                    logger.warning("[Distill] Final agent merge failed")
            else:
                engine.save_summary(new_observation)

        DistillationService._last_distilled_turns.pop(conversation_id, None)


distillation_service = DistillationService()