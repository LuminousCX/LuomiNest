"""
快速搜索器 - 优化版
配合智能记忆管理器使用
"""

import asyncio
import time
from typing import List, Dict, Any, Optional, Tuple, Callable
from concurrent.futures import ThreadPoolExecutor
import threading
import re
from datetime import datetime
from core.predictive_cache import predictive_cache


class SearchResult:
    """搜索结果封装，携带匹配类型和上下文信息"""

    DIRECT = "direct"
    KNOWLEDGE = "knowledge"
    MEMORY = "memory"
    NONE = "none"

    def __init__(self, answer: Optional[str] = None, match_type: str = NONE,
                 knowledge_context: Optional[str] = None, score: float = 0.0):
        self.answer = answer
        self.match_type = match_type
        self.knowledge_context = knowledge_context
        self.score = score

    @property
    def found(self) -> bool:
        return self.match_type != self.NONE

    @property
    def needs_enhancement(self) -> bool:
        return self.match_type == self.KNOWLEDGE


DIRECT_ANSWER_KEYS = {
    '你是谁', '你叫什么', '你好', '你是', '你能做什么',
    '今天', '时间', '几点', '今天天气', '天气如何', '天气怎么样', '天气',
}


class FastSearcher:
    """快速搜索器 - 优化版"""

    STOP_WORDS = {
        '的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
        '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
        '自己', '这', '那', '他', '她', '它', '给', '吗', '还', '什么', '呢', '啊', '吧'
    }

    GENERIC_WORDS = {'计划', '建议', '推荐', '方法', '方式', '功能', '问题', '内容', '东西'}

    TOPIC_KEYWORDS = {
        '旅游', '旅行', '学习', '美食', '电影', '音乐', '游戏', '工作', '生活',
        '健康', '编程', '读书', '运动', '购物', '投资', '理财'
    }

    RECALL_PATTERNS = [
        '还记得', '记得吗', '记不记得', '之前', '刚才', '上次', '以前',
        '说过', '问过', '聊过', '讨论过', '提到过', '上次说', '上次问',
        '我上次', '上次我', '之前说', '之前问', '之前聊',
        '最次', '这回', '那回', '上回', '前次', '往次',
        '那一次', '这一次', '上一次', '前一次',
    ]

    ENHANCEMENT_INDICATORS = {
        '如何', '怎么', '怎样', '为什么', '原因', '区别', '对比', '比较',
        '建议', '推荐', '方法', '方案', '攻略', '指南', '教程', '技巧',
        '最好', '最优', '注意', '需要', '应该', '可以', '适合',
        '优缺点', '利弊', '好坏', '评价', '评测', '怎么样',
    }

    def __init__(self, knowledge_manager, memory_manager):
        """初始化快速搜索器"""
        self.knowledge_manager = knowledge_manager
        self.memory_manager = memory_manager

        self._preload_data()

        self.executor = ThreadPoolExecutor(max_workers=3)

        self.search_cache = {}
        self.cache_lock = threading.Lock()

        self.hot_queries = {
            '你是谁': '我是汐汐，一个智能助手。',
            '你叫什么': '我叫汐汐。',
            '你好': '你好！很高兴见到你。',
            '你是': '我是汐汐，一个智能助手。',
            '你能做什么': '我可以回答问题、提供建议、陪你聊天。',
            '今天天气': self._get_weather_unavailable,
            '天气如何': self._get_weather_unavailable,
            '天气怎么样': self._get_weather_unavailable,
            '天气': self._get_weather_unavailable,
            '今天': self._get_date_answer,
            '时间': self._get_time_answer,
            '几点': self._get_time_answer,
        }

        self._sorted_hot_keys = sorted(self.hot_queries.keys(), key=len, reverse=True)

        string_only_queries = {k: v for k, v in self.hot_queries.items() if not callable(v)}
        predictive_cache.preload_common_queries(string_only_queries)

    def _preload_data(self):
        """预加载所有数据到内存"""
        print("[LOAD] 预加载数据中...")
        start = time.time()

        self.knowledge_base = self.knowledge_manager.local_rag.knowledge_base
        self.keyword_index = self.knowledge_manager.local_rag.keyword_index

        self.vectors_cache = self.knowledge_manager.vector_rag.vectors_cache
        self.texts_cache = self.knowledge_manager.vector_rag.texts_cache

        try:
            if hasattr(self.memory_manager, 'long_term_memories'):
                self.memory_data = self.memory_manager.long_term_memories
                print("   - 使用智能记忆系统")
            else:
                self.memory_data = self.memory_manager.memory_store.memories
                print("   - 使用传统记忆系统")
        except Exception as e:
            print(f"[WARNING] 加载记忆失败: {e}")
            self.memory_data = []

        print(f"[OK] 数据预加载完成 ({time.time()-start:.2f}s)")
        print(f"   - 知识库: {len(self.knowledge_base)} 条")
        print(f"   - 向量库: {len(self.vectors_cache)} 条")
        print(f"   - 记忆: {len(self.memory_data)} 条")

    def _get_date_answer(self) -> str:
        now = datetime.now()
        weekdays = ['一', '二', '三', '四', '五', '六', '日']
        return f"今天是{now.year}年{now.month}月{now.day}日，星期{weekdays[now.weekday()]}"

    def _get_time_answer(self) -> str:
        now = datetime.now()
        return f"现在是{now.hour}点{now.minute}分"

    def _get_weather_unavailable(self) -> str:
        return "抱歉，我暂时无法获取实时天气信息。建议你使用手机天气应用或网站查看最新的天气情况。"

    def _needs_enhancement(self, query: str) -> bool:
        """判断查询是否需要 LLM 增强（即使知识库有匹配）"""
        query_lower = query.lower().strip()

        if any(indicator in query_lower for indicator in self.ENHANCEMENT_INDICATORS):
            return True

        if self._is_vague_intent(query):
            return True

        if len(query_lower) >= 6:
            return True

        return False

    def _is_vague_intent(self, query: str) -> bool:
        """判断是否为模糊意图（应该调用API而不是返回缓存）"""
        query_lower = query.lower().strip()

        if len(query_lower) < 3:
            return True

        clear_keywords = ['计划', '建议', '推荐', '方法', '方案', '攻略', '指南', '教程']
        if any(kw in query_lower for kw in clear_keywords):
            return False

        vague_patterns = [
            '我好想', '我好像', '我想', '我要', '我需要', '我想要',
            '能不能', '可以吗', '怎么样', '如何', '为什么',
            '帮我', '给我', '告诉我', '请问', '帮我',
        ]

        for pattern in vague_patterns:
            if query_lower.startswith(pattern):
                return True

        emotion_patterns = ['好想', '好像', '想去', '想做', '想学', '想看', '想玩']
        for pattern in emotion_patterns:
            if pattern in query_lower:
                if not any(kw in query_lower for kw in clear_keywords):
                    return True

        return False

    def fast_search(self, query: str) -> Tuple[Optional[str], bool]:
        """快速搜索（兼容旧接口）"""
        result = self.enhanced_search(query)
        return result.answer, result.found

    def enhanced_search(self, query: str) -> SearchResult:
        """
        增强搜索 - 返回携带匹配类型的搜索结果

        搜索优先级：
        1. 热点查询（你是谁、几点等）→ 直接回答
        2. 记忆搜索（仅当用户明确要求回忆时）→ 直接回答
        3. 知识库搜索 → 判断是否需要 LLM 增强
        """
        cached_result = predictive_cache.get(query)
        if cached_result:
            return SearchResult(answer=cached_result, match_type=SearchResult.DIRECT)

        for key in self._sorted_hot_keys:
            answer = self.hot_queries[key]
            if key in query:
                if callable(answer):
                    result = answer()
                    predictive_cache.set(query, result)
                    return SearchResult(answer=result, match_type=SearchResult.DIRECT)
                predictive_cache.set(query, answer)
                return SearchResult(answer=answer, match_type=SearchResult.DIRECT)

        if self._is_recall_query(query):
            memory_result = self._search_memory(query)
            if memory_result:
                predictive_cache.set(query, memory_result)
                return SearchResult(answer=memory_result, match_type=SearchResult.MEMORY)

        kb_answer, kb_score = self._fast_keyword_search_with_score(query)
        if kb_answer:
            predictive_cache.set(query, kb_answer)

            if self._needs_enhancement(query):
                return SearchResult(
                    answer=kb_answer,
                    match_type=SearchResult.KNOWLEDGE,
                    knowledge_context=kb_answer,
                    score=kb_score,
                )

            return SearchResult(answer=kb_answer, match_type=SearchResult.DIRECT)

        return SearchResult(match_type=SearchResult.NONE)

    def _is_recall_query(self, query: str) -> bool:
        """判断是否为回忆查询"""
        return any(pattern in query for pattern in self.RECALL_PATTERNS)

    def _extract_topics(self, query: str) -> List[str]:
        """提取查询主题"""
        query_lower = query.lower()
        topics = []

        for topic in self.TOPIC_KEYWORDS:
            if topic in query_lower:
                topics.append(topic)

        return topics

    def _search_memory(self, query: str) -> Optional[str]:
        """搜索记忆 - 仅在用户明确要求回忆时调用，返回最新的匹配记忆"""
        query_lower = query.lower()
        recall_topics = self._extract_topics(query_lower)

        try:
            if hasattr(self.memory_manager, 'long_term_memories'):
                self.memory_data = self.memory_manager.long_term_memories
            else:
                self.memory_data = self.memory_manager.memory_store.memories
        except Exception as e:
            self.memory_data = []

        if not self.memory_data:
            return None

        matched_memories = []

        for memory in self.memory_data:
            if isinstance(memory, dict):
                user_input = memory.get('user_input', '')
                system_response = memory.get('system_response', '')
                memory_topics = set(memory.get('topics', []))

                is_match, matched_topic = self._is_memory_match(recall_topics, query_lower, user_input, memory_topics)

                if is_match:
                    timestamp = self._parse_timestamp(memory.get('timestamp', ''))
                    matched_memories.append({
                        'user_input': user_input,
                        'system_response': system_response,
                        'topic': matched_topic,
                        'timestamp': timestamp,
                        'importance': memory.get('importance', 0.5)
                    })

        if not matched_memories:
            return None

        matched_memories.sort(key=lambda x: (x['timestamp'], x['importance']), reverse=True)

        latest = matched_memories[0]
        return self._format_memory_response(latest)

    def _is_memory_match(self, recall_topics: List[str], query_lower: str, user_input: str, memory_topics: set) -> Tuple[bool, Optional[str]]:
        """判断记忆是否匹配"""
        if recall_topics:
            for topic in recall_topics:
                if topic in memory_topics or topic in user_input.lower():
                    return True, topic
        else:
            query_keywords = self._extract_keywords(query_lower)
            keyword_matches = sum(1 for kw in query_keywords if kw in user_input.lower())
            if keyword_matches > 0:
                return True, "相关"
        return False, None

    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """解析时间戳"""
        try:
            return datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.min
        except:
            return datetime.min

    def _format_memory_response(self, memory: Dict[str, Any]) -> str:
        """格式化记忆响应"""
        user_q = memory['user_input']
        response = memory['system_response']
        topic = memory['topic']

        if topic and topic != "相关":
            return f"记得！最近一次你问过关于{topic}的问题（\"{user_q[:20]}...\"）。\n\n{response}"
        else:
            return f"记得！最近一次你问过（\"{user_q[:20]}...\"）。\n\n{response}"

    def _fast_keyword_search(self, query: str) -> Optional[str]:
        """快速关键词搜索"""
        result, _ = self._fast_keyword_search_with_score(query)
        return result

    def _fast_keyword_search_with_score(self, query: str) -> Tuple[Optional[str], float]:
        """快速关键词搜索（带匹配分数）"""
        keywords = self._extract_keywords(query)
        if not keywords:
            return None, 0.0

        candidate_indices = self._get_candidate_indices(keywords)
        if not candidate_indices:
            return None, 0.0

        best_answer, best_score = self._find_best_answer(candidate_indices, keywords)
        if best_score == 0 or best_answer is None:
            return None, 0.0

        if not self._validate_answer_relevance(query, best_answer):
            return None, 0.0

        normalized_score = best_score / len(keywords) if keywords else 0.0
        return best_answer, normalized_score

    def _get_candidate_indices(self, keywords: List[str]) -> set:
        """获取候选索引"""
        candidate_indices = set()
        for keyword in keywords:
            if keyword in self.keyword_index:
                candidate_indices.update(self.keyword_index[keyword])
        return candidate_indices

    def _find_best_answer(self, candidate_indices: set, keywords: List[str]) -> Tuple[Optional[str], int]:
        """找到最佳答案"""
        best_score = 0
        best_answer = None

        for idx in candidate_indices:
            if idx < len(self.knowledge_base):
                item = self.knowledge_base[idx]
                question = item.get('question', '')
                answer = item.get('answer', '')

                score = sum(1 for k in keywords if k in question)
                if score > best_score and len(answer) > 10:
                    best_score = score
                    best_answer = answer

        return best_answer, best_score

    def _validate_answer_relevance(self, query: str, answer: str) -> bool:
        """验证答案相关性"""
        query_keywords = set(self._extract_keywords(query))
        if not query_keywords:
            return True

        return True

    def _extract_keywords(self, text: str) -> List[str]:
        """快速提取关键词"""
        text = re.sub(r'[，。！？；："\'（）【】]', ' ', text.lower())
        words = text.split()
        return [w for w in words if w not in self.STOP_WORDS and len(w) > 1]

    def clear_cache(self):
        """清空缓存"""
        with self.cache_lock:
            self.search_cache.clear()

    def parallel_search(self, query: str) -> Tuple[Optional[str], bool]:
        """并行搜索（异步版本）"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            results = loop.run_until_complete(self._async_parallel_search(query))

            for result in results:
                if result:
                    return result, True

            return None, False
        finally:
            loop.close()

    async def _async_parallel_search(self, query: str) -> List[Optional[str]]:
        """异步并行搜索"""
        tasks = [
            self._async_search_knowledge(query),
            self._async_search_memory(query),
            self._async_search_vectors(query)
        ]

        results = await asyncio.gather(*tasks)
        return results

    async def _async_search_knowledge(self, query: str) -> Optional[str]:
        """异步搜索知识库"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._fast_keyword_search,
            query
        )

    async def _async_search_memory(self, query: str) -> Optional[str]:
        """异步搜索记忆"""
        for memory in self.memory_data:
            if query in str(memory):
                return str(memory)
        return None

    async def _async_search_vectors(self, query: str) -> Optional[str]:
        """异步搜索向量库"""
        if not self.vectors_cache:
            return None

        query_vector = self.knowledge_manager._generate_simple_vector(query)

        best_score = 0
        best_text = None

        for i, vector in enumerate(self.vectors_cache[:100]):
            if len(vector) == len(query_vector):
                score = sum(a * b for a, b in zip(query_vector, vector))
                if score > best_score:
                    best_score = score
                    best_text = self.texts_cache[i]

        return best_text if best_score > 0.1 else None
