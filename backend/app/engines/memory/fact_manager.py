import re
from datetime import datetime
from loguru import logger

from app.core.utils import utc_now_dt

from .models import MemoryData, FactItem, ArchivedFact
from .store import MemoryStore

# 中文停用词（用于关键词提取时过滤无意义词）
_STOP_WORDS = frozenset({
    "的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一",
    "个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有",
    "看", "好", "自己", "这", "他", "她", "它", "那", "被", "把", "还", "让",
    "吗", "呢", "吧", "啊", "嗯", "哦", "对", "么", "什么", "怎么", "为什么",
    "比较", "可以", "可能", "应该", "因为", "所以", "但是", "而且", "或者",
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "i", "me", "my", "you", "your", "he", "him", "his", "she", "her",
    "it", "its", "we", "us", "our", "they", "them", "their",
    "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
    "not", "no", "so", "if", "than", "too", "very", "just", "about",
})

# 常用中文双字词优先整体成词（排在单字匹配之前）。
# 旧版逐字切分把"咖啡"拆成"咖"+"啡"，既放大词集合规模（三层相似度
# 循环的集合运算量），也让 Jaccard 在词序置换的句子上失真。
_BI_GRAM_WORDS = (
    "咖啡", "牛奶", "喝茶", "茶叶", "早餐", "午餐", "晚餐",
    "工作", "职业", "公司", "学校", "专业", "学业", "毕业", "同事", "老板",
    "学习", "研究", "阅读", "书籍", "音乐", "电影", "游戏", "画画",
    "运动", "健身", "跑步", "游泳", "旅行", "旅游", "度假", "周末",
    "电脑", "手机", "键盘", "鼠标", "显示器", "软件", "硬件", "系统",
    "编程", "代码", "程序", "项目", "工具", "插件", "数据", "模型",
    "喜欢", "讨厌", "偏好", "希望", "计划", "目标", "习惯", "想法",
    "名字", "姓名", "生日", "地址", "电话", "邮箱", "头像", "昵称",
    "宠物", "家人", "父母", "朋友", "同学",
    "健康", "睡眠", "饮食", "体重", "医院", "医生",
    "英语", "日语", "韩语", "中文", "语言",
    "城市", "国家", "搬家", "居住",
    "知乎", "哔哩", "微信", "微博",
)

# 分词正则：双字词优先 → 英文单词 → 单个汉字
_TOKEN_RE = re.compile("|".join(_BI_GRAM_WORDS) + "|[a-zA-Z]+|[\u4e00-\u9fff]")


def _extract_content_words(text: str) -> set[str]:
    """从文本中提取有意义的关键词集合（用于语义相似度计算）。

    常用双字词优先整体成词（"咖啡"→"咖啡" 而非 "咖"+"啡"），
    未收录词仍按单字切分；英文按单词切分并过滤停用词。
    """
    words = set()
    for token in _TOKEN_RE.findall(text):
        token_lower = token.lower()
        if token_lower in _STOP_WORDS:
            continue
        if len(token_lower) < 2 and not re.match(r"[\u4e00-\u9fff]", token):
            continue
        words.add(token_lower)
    return words


class FactManager:
    """事实生命周期管理：CRUD、去重、合并、纠正、矛盾处理、时间衰减。

    合并决策表（_reconcile_conflicts 单入口）：

    | 条件                                  | 动作                          |
    |---------------------------------------|-------------------------------|
    | 精确/语义相似 + 矛盾（correction 或正反词） | 旧版归档(is_latest=False)，新版替代 |
    | 相似 + 新版置信度更高                 | 旧版归档，原地更新内容         |
    | 相似 + 新版置信度不高于旧版           | 丢弃新版（保留旧版）           |
    | 不相似                                | 追加新事实                    |

    矛盾检测见 _is_contradiction；归档版本存 ArchivedFact.history。
    """

    MAX_FACTS = 100

    def __init__(self, store: MemoryStore):
        self._store = store

    def get_facts(self, category: str | None = None, include_expired: bool = False) -> list[FactItem]:
        data = self._store.load_data()
        facts = data.facts
        if not include_expired:
            facts = self._filter_valid_facts(facts)
        if category:
            facts = [f for f in facts if f.category == category]
        return facts

    def _filter_valid_facts(self, facts: list[FactItem]) -> list[FactItem]:
        """过滤出未过期的有效事实（is_latest=True 且未过期）。"""
        now = utc_now_dt()
        valid = []
        for fact in facts:
            if not fact.is_latest:
                continue
            if fact.expires_at:
                try:
                    # 使用 datetime.fromisoformat 解析 ISO 8601 格式
                    # 支持 "2025-01-15" 和 "2025-01-15T00:00:00" 格式
                    exp_time = datetime.fromisoformat(fact.expires_at.replace("Z", "+00:00"))
                    if exp_time <= now:
                        continue
                except (ValueError, TypeError):
                    pass
            valid.append(fact)
        return valid

    def cleanup_expired_facts(self) -> int:
        """清理已过期的事实，返回清理数量。"""
        removed = 0

        def op(data: MemoryData) -> None:
            nonlocal removed
            original_count = len(data.facts)
            now = utc_now_dt()
            remaining = []
            for fact in data.facts:
                if not fact.is_latest:
                    remaining.append(fact)
                    continue
                if fact.expires_at:
                    try:
                        exp_time = datetime.fromisoformat(fact.expires_at.replace("Z", "+00:00"))
                        if exp_time <= now:
                            logger.info(f"[Memory] Fact expired and removed: {fact.content[:50]}")
                            continue
                    except (ValueError, TypeError):
                        pass
                remaining.append(fact)
            data.facts = remaining
            removed = original_count - len(remaining)

        self._store.mutate(op)
        return removed

    def add_fact(self, fact: FactItem) -> None:
        def op(data: MemoryData) -> None:
            self._merge_fact(data, fact)
            self._trim_facts(data)
        self._store.mutate(op)

    def remove_fact(self, fact_id: str) -> bool:
        removed = False

        def op(data: MemoryData) -> None:
            nonlocal removed
            before = len(data.facts)
            data.facts = [f for f in data.facts if f.id != fact_id]
            removed = len(data.facts) < before

        self._store.mutate(op)
        return removed

    def update_fact(
        self,
        fact_id: str,
        content: str | None = None,
        category: str | None = None,
        confidence: float | None = None,
    ) -> bool:
        updated = False

        def op(data: MemoryData) -> None:
            nonlocal updated
            for fact in data.facts:
                if fact.id == fact_id:
                    if content is not None:
                        fact.content = content
                    if category is not None:
                        fact.category = category
                    if confidence is not None:
                        fact.confidence = confidence
                    updated = True
                    break

        self._store.mutate(op)
        return updated

    def clear_facts(self) -> None:
        def op(data: MemoryData) -> None:
            data.facts = []
        self._store.mutate(op)

    def merge_facts(self, data: MemoryData, facts: list[FactItem]) -> None:
        """将新事实列表合并到已有数据中，处理纠正、矛盾和时间衰减。"""
        for fact in facts:
            if fact.category == "correction" and fact.source_error:
                self._apply_correction(data, fact)
            self._merge_fact(data, fact)
        self._cleanup_expired(data)
        self._trim_facts(data)

    def _cleanup_expired(self, data: MemoryData) -> None:
        """删除已过期的（is_latest 且 expires_at 早于当前时间）事实。"""
        now = utc_now_dt()
        remaining = []
        for fact in data.facts:
            if not fact.is_latest:
                remaining.append(fact)
                continue
            if fact.expires_at:
                try:
                    exp_time = datetime.fromisoformat(fact.expires_at.replace("Z", "+00:00"))
                    if exp_time <= now:
                        logger.info(f"[Memory] Fact expired: {fact.content[:50]}")
                        continue
                except (ValueError, TypeError):
                    pass
            remaining.append(fact)
        data.facts = remaining

    def deprecate_old_name_facts(self, data: MemoryData, old_name: str, new_name: str) -> None:
        """名字变更时，降低包含旧名字的身份类事实的置信度。"""
        old_name_lower = old_name.strip().casefold()
        for fact in data.facts:
            if fact.confidence < 0.9:
                continue
            fact_lower = fact.content.strip().casefold()
            if old_name_lower not in fact_lower:
                continue
            if any(kw in fact_lower for kw in ("名字", "叫", "名为")):
                fact.confidence = min(fact.confidence, 0.3)

    def _merge_fact(self, data: MemoryData, fact: FactItem) -> None:
        """合并单条事实：存在相似则进入矛盾/更新决策，否则追加。"""
        existing = self._find_similar_fact(data, fact)
        if existing:
            self._reconcile_conflicts(data, existing, fact)
        else:
            data.facts.append(fact)

    def _reconcile_conflicts(self, data: MemoryData, existing: FactItem, fact: FactItem) -> None:
        """合并决策单入口（见类顶部决策表）：矛盾替代 / 高置信度更新 / 丢弃。

        归档旧版本到 history，保证版本可追溯。
        """
        if self._is_contradiction(existing, fact):
            # 矛盾检测到：归档旧版本，新事实替代
            existing.history.append(ArchivedFact(
                content=existing.content,
                category=existing.category,
                confidence=existing.confidence,
                reason="conflict",
            ))
            existing.is_latest = False
            fact.supersedes_id = existing.id
            fact.is_latest = True
            # 继承旧版本的history
            fact.history = existing.history.copy()
            data.facts.append(fact)
            logger.info(f"[Memory] Contradiction detected, new fact supersedes old: {existing.content[:30]} -> {fact.content[:30]}")
        elif fact.confidence > existing.confidence:
            # 更高置信度：归档旧版本，更新内容
            existing.history.append(ArchivedFact(
                content=existing.content,
                category=existing.category,
                confidence=existing.confidence,
                reason="superseded",
            ))
            existing.content = fact.content
            existing.confidence = fact.confidence
            existing.category = fact.category
            existing.source_error = fact.source_error
            existing.expires_at = fact.expires_at
            if fact.source_conversation_id:
                existing.source_conversation_id = fact.source_conversation_id
            if fact.source_message:
                existing.source_message = fact.source_message

    @staticmethod
    def _is_contradiction(existing: FactItem, new_fact: FactItem) -> bool:
        """检测新旧事实是否矛盾（同类别但内容相斥）。"""
        if existing.category != new_fact.category:
            return False
        # correction 类别始终视为矛盾（替代旧信息）
        if new_fact.category == "correction":
            return True
        # 相同类别的关键词矛盾检测
        contradiction_indicators = [
            # 工作/状态变化
            (["在...工作", "就职于", "是...的"], ["离开", "辞职", "quit", "left", "不再"]),
            (["住在", "位于", "在..."], ["搬到", "moved to", "relocated"]),
            # 喜好矛盾
            (["喜欢", "爱", "偏好", "prefer", "love"], ["讨厌", "不喜欢", "反感", "dislike", "hate"]),
            # 使用矛盾
            (["使用", "用", "用...技术", "用...工具"], ["不用", "不再用", "停止使用", "stop using"]),
            # 状态矛盾
            (["是", "在"], ["不是", "不在", "不再"]),
        ]
        existing_lower = existing.content.lower()
        new_lower = new_fact.content.lower()
        for positive_kw, negative_kw in contradiction_indicators:
            has_positive_old = any(kw in existing_lower for kw in positive_kw)
            has_negative_new = any(kw in new_lower for kw in negative_kw)
            has_positive_new = any(kw in new_lower for kw in positive_kw)
            has_negative_old = any(kw in existing_lower for kw in negative_kw)
            if has_positive_old and has_negative_new:
                return True
            if has_positive_new and has_negative_old:
                return True
        return False

    def _trim_facts(self, data: MemoryData) -> None:
        """事实数超上限时归档：按置信度保留前 MAX_FACTS，被挤出的最新事实
        以 [记忆整理] 行追加到 daily（不再静默丢弃）。
        """
        if len(data.facts) <= self.MAX_FACTS:
            return
        data.facts.sort(key=lambda f: f.confidence, reverse=True)
        evicted = data.facts[self.MAX_FACTS:]
        data.facts = data.facts[: self.MAX_FACTS]
        for fact in evicted:
            if not fact.is_latest:
                continue
            try:
                self._store.append_daily(
                    f"[记忆整理] 已归档事实（超出 {self.MAX_FACTS} 条上限）：{fact.content[:80]}"
                )
            except Exception as e:
                logger.warning(f"[Memory] trim archive to daily failed: {e}")

    @staticmethod
    def _find_similar_fact(data: MemoryData, fact: FactItem) -> FactItem | None:
        """查找语义相似或矛盾的事实：先精确匹配，再关键词子集匹配，最后同类别矛盾匹配。

        性能：存量事实的分词结果在循环外预计算一次，供第 2/3 阶段复用
        （旧版每层循环重复分词，100 存量 × 50 新增实测 130ms，主因即此）。
        """
        normalized = fact.content.strip().casefold()
        latest = [f for f in data.facts if f.is_latest]
        # 1. 精确匹配
        for existing in latest:
            if existing.content.strip().casefold() == normalized:
                return existing
        # 2. 关键词子集匹配：如果新事实的核心词全部出现在已有事实中（或反之），视为相似
        content_words = _extract_content_words(normalized)
        if not content_words:
            return None
        existing_words = [(f, _extract_content_words(f.content.strip().casefold())) for f in latest]
        for existing, fact_words in existing_words:
            if not fact_words:
                continue
            # 至少需要 2 个非停用词重叠才有比较意义
            common = content_words & fact_words
            if len(common) < 2:
                continue
            # 计算 Jaccard 相似度
            overlap = len(common) / max(len(content_words | fact_words), 1)
            if overlap >= 0.8:
                return existing
        # 3. 同类别矛盾匹配：同 category 且共享至少1个核心词，且包含矛盾关键词对
        for existing, fact_words in existing_words:
            if not fact_words:
                continue
            common = content_words & fact_words
            if not common:
                continue
            if FactManager._is_contradiction(existing, fact):
                return existing
        return None

    @staticmethod
    def _apply_correction(data: MemoryData, correction_fact: FactItem) -> None:
        error_text = correction_fact.source_error.strip().casefold()
        if not error_text:
            return
        for fact in data.facts:
            if error_text in fact.content.casefold():
                fact.confidence = min(fact.confidence, 0.3)

    def apply_supersedes(self, data: MemoryData, supersedes_text: str, new_content: str) -> None:
        """LLM 标记的矛盾处理：归档被替代的事实，标记为非最新。"""
        if not supersedes_text:
            return
        supersedes_lower = supersedes_text.strip().casefold()
        for fact in data.facts:
            if not fact.is_latest:
                continue
            if supersedes_lower in fact.content.casefold() and fact.content.strip().casefold() != new_content.strip().casefold():
                fact.history.append(ArchivedFact(
                    content=fact.content,
                    category=fact.category,
                    confidence=fact.confidence,
                    reason="conflict",
                ))
                fact.is_latest = False
                fact.confidence = min(fact.confidence, 0.3)
                logger.info(f"[Memory] LLM supersedes: '{new_content[:30]}' replaces '{fact.content[:30]}'")
