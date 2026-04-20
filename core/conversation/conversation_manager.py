from .command_handler import CommandHandler
from .response_generator import ResponseGenerator
from core.nlp.intent_recognizer import IntentRecognizer
from core.nlp.name_extractor import NameExtractor
from core.nlp.keyword_extractor import KeywordExtractor
from core.nlp.unified_intent_analyzer import UnifiedIntentAnalyzer, get_unified_intent_analyzer
from core.nlp.context_manager import ContextManager, get_context_manager
from core.fast_searcher import FastSearcher, SearchResult
from core.safety_filter import safety_filter
from utils.helpers import get_current_date, contains_time_query
from utils.logger import get_logger
import random
import time
import re

logger = get_logger()


class ConversationManager:
    URL_PATTERN = r'https?://[^\s<>"{}|\\^`\[\]]+'

    def __init__(self, memory_manager, knowledge_manager, system_name):
        self.memory_manager = memory_manager
        self.knowledge_manager = knowledge_manager
        self.intent_recognizer = IntentRecognizer()
        self.name_extractor = NameExtractor()
        self.keyword_extractor = KeywordExtractor()
        self.response_generator = ResponseGenerator(system_name)
        self.system_name = system_name
        self.user_name = None

        self.fast_searcher = FastSearcher(knowledge_manager, memory_manager)
        self.command_handler = CommandHandler(memory_manager, self.fast_searcher)

        self.unified_analyzer = get_unified_intent_analyzer()
        self.context_manager = get_context_manager()

    def process_input(self, user_input):
        """处理用户输入（即时响应版）- 增强版"""
        start_time = time.time()

        try:
            is_safe, safety_message = safety_filter.check_content(user_input)
        except Exception as e:
            logger.warning(f"安全检查失败: {e}")
            is_safe, safety_message = True, None

        if not is_safe:
            return safety_message

        if user_input.isdigit() or len(user_input.strip()) < 3:
            suggestions = self._get_input_suggestions()
            if suggestions:
                return suggestions

        if user_input.startswith('/'):
            return self.handle_command(user_input)

        has_url = re.search(self.URL_PATTERN, user_input)
        if has_url:
            print("[THINK] 检测到URL，正在解析...", end='', flush=True)
            return self._stream_api_response_with_thinking(user_input, None)

        facts = self.memory_manager.extract_and_store_facts(user_input)

        analysis_result = self._analyze_user_intent(user_input)

        user_name = self.name_extractor.extract_user_name(user_input)
        if user_name:
            self.user_name = user_name
            self._update_context(user_input, "", "set_name", None, {"user_name": user_name})
            return self.response_generator.generate_response("set_name", user_input, {"user_name": user_name})

        system_name = self.name_extractor.extract_system_name(user_input)
        if system_name:
            self.system_name = system_name
            self.response_generator.update_system_name(system_name)
            return self.response_generator.generate_response("set_system_name", user_input, {"system_name": system_name})

        if analysis_result.primary_intent.name in ["greeting", "farewell", "gratitude"]:
            response = self.response_generator.generate_response(
                analysis_result.primary_intent.name,
                user_input,
                analysis_result.entities
            )
            self._update_context(
                user_input, response,
                analysis_result.primary_intent.name,
                analysis_result.topic,
                analysis_result.entities,
                analysis_result.sentiment
            )
            return response

        if analysis_result.primary_intent.name == "ask_weather":
            print("[THINK] 思考中...", end='', flush=True)
            return self._stream_api_response_with_thinking(user_input, analysis_result)

        if analysis_result.primary_intent.category.name == "EMOTIONAL":
            print("[THINK] 情感分析中...", end='', flush=True)
            return self._stream_api_response_with_thinking(user_input, analysis_result)

        if analysis_result.topic_continuation or analysis_result.primary_intent.category.name == "CONTINUATION":
            print("[THINK] 上下文关联分析中...", end='', flush=True)
            return self._stream_api_response_with_thinking(user_input, analysis_result)

        if analysis_result.primary_intent.category.name == "CLARIFICATION":
            print("[THINK] 深入分析中...", end='', flush=True)
            return self._stream_api_response_with_thinking(user_input, analysis_result)

        search_result = self.fast_searcher.enhanced_search(user_input)

        if search_result.match_type == SearchResult.DIRECT:
            elapsed = (time.time() - start_time) * 1000
            print(f"[FAST] 快速响应 ({elapsed:.1f}ms)")
            self.memory_manager.add_to_working_memory(user_input)
            self.memory_manager.add_to_working_memory(search_result.answer)
            self._update_context(
                user_input, search_result.answer,
                "fast_search",
                analysis_result.topic,
                analysis_result.entities,
                analysis_result.sentiment
            )
            return search_result.answer

        if search_result.match_type == SearchResult.KNOWLEDGE:
            print("[ENHANCE] 知识增强响应中...", end='', flush=True)
            return self._stream_knowledge_enhanced_response(
                user_input, analysis_result, search_result.knowledge_context
            )

        if search_result.match_type == SearchResult.MEMORY:
            elapsed = (time.time() - start_time) * 1000
            print(f"[FAST] 快速响应 ({elapsed:.1f}ms)")
            self.memory_manager.add_to_working_memory(user_input)
            self.memory_manager.add_to_working_memory(search_result.answer)
            self._update_context(
                user_input, search_result.answer,
                "memory_search",
                analysis_result.topic,
                analysis_result.entities,
                analysis_result.sentiment
            )
            return search_result.answer

        print("[THINK] 思考中...", end='', flush=True)

        return self._stream_api_response_with_thinking(user_input, analysis_result)

    def _analyze_user_intent(self, user_input: str):
        """使用联合意图分析器分析用户意图"""
        conversation_history = self.context_manager.get_conversation_history(3)

        memory_results = self.memory_manager.search_memory(user_input, limit=2)
        self.context_manager.set_memory_context(memory_results)

        analysis_result = self.unified_analyzer.analyze(
            user_input=user_input,
            conversation_history=conversation_history,
            memory_results=memory_results,
        )

        return analysis_result

    def _update_context(
        self,
        user_input: str,
        system_response: str,
        intent: str = None,
        topic: str = None,
        entities: dict = None,
        sentiment: str = "neutral"
    ):
        """更新上下文"""
        self.context_manager.add_conversation_turn(
            user_input=user_input,
            system_response=system_response,
            intent=intent,
            topic=topic,
            entities=entities,
            sentiment=sentiment
        )

        if entities:
            self.unified_analyzer.update_entity_cache(entities)

    def _stream_knowledge_enhanced_response(self, user_input, analysis_result, knowledge_context):
        """知识增强的流式 API 响应 - 将知识库匹配结果作为上下文注入 LLM"""
        print('\r' + ' ' * 30 + '\r', end='', flush=True)

        full_response = ""

        enhanced_context = self._build_enhanced_context(user_input, analysis_result)

        memory_results = self.memory_manager.search_memory(user_input, limit=2)

        if enhanced_context:
            memory_results.insert(0, enhanced_context)

        conversation_history = self.context_manager.get_conversation_history(limit=5)

        for chunk in self.knowledge_manager.search_with_knowledge_context(
            user_input, knowledge_context, memory_results, conversation_history
        ):
            full_response += chunk
            print(chunk, end='', flush=True)

        print()

        self.memory_manager.add_memory(user_input, full_response)

        if analysis_result:
            self._update_context(
                user_input, full_response,
                analysis_result.primary_intent.name,
                analysis_result.topic,
                analysis_result.entities,
                analysis_result.sentiment
            )

        return None

    def _stream_api_response_with_thinking(self, user_input, analysis_result=None):
        """带思考过程的流式API响应 - 增强版"""
        print('\r' + ' ' * 20 + '\r', end='', flush=True)

        thinking_steps = [
            "分析中...",
            "搜索中...",
            "生成中..."
        ]

        for step in thinking_steps:
            print(f"\r{step}", end='', flush=True)
            time.sleep(0.02)

        print('\r' + ' ' * 30 + '\r', end='', flush=True)

        full_response = ""

        enhanced_context = self._build_enhanced_context(user_input, analysis_result)

        memory_results = self.memory_manager.search_memory(user_input, limit=2)

        if enhanced_context:
            memory_results.insert(0, enhanced_context)

        conversation_history = self.context_manager.get_conversation_history(limit=5)

        has_url = re.search(self.URL_PATTERN, user_input)
        has_cached_url = self.knowledge_manager.has_cached_url()

        if has_url or has_cached_url:
            if has_url:
                print("[网页解析] 正在解析URL内容...\n")
            else:
                print("[网页解析] 使用缓存的网页内容...\n")
            for chunk in self.knowledge_manager.search_with_url_context(user_input, memory_results, conversation_history):
                full_response += chunk
                print(chunk, end='', flush=True)
        else:
            for chunk in self.knowledge_manager.search_with_api(user_input, memory_results, conversation_history):
                full_response += chunk
                print(chunk, end='', flush=True)

        print()

        self.memory_manager.add_memory(user_input, full_response)

        if analysis_result:
            self._update_context(
                user_input, full_response,
                analysis_result.primary_intent.name,
                analysis_result.topic,
                analysis_result.entities,
                analysis_result.sentiment
            )

        return None

    def _build_enhanced_context(self, user_input: str, analysis_result) -> str:
        """构建增强的上下文提示"""
        if not analysis_result:
            return self.memory_manager.get_context_summary()

        context_parts = []

        if analysis_result.topic:
            context_parts.append(f"【当前话题】{analysis_result.topic}")

        if analysis_result.topic_continuation:
            last_turn = self.context_manager.get_last_turn()
            if last_turn:
                context_parts.append(f"""【对话延续】
用户之前问: {last_turn.user_input[:100]}
系统回答: {last_turn.system_response[:150]}
用户现在说: {user_input}
请理解这是在继续之前的对话，提供相关的新内容。""")

        if analysis_result.primary_intent.category.name == "EMOTIONAL":
            context_parts.append(f"【情感状态】用户当前情绪: {analysis_result.sentiment}")
            context_parts.append("请给予情感支持和理解。")

        if analysis_result.primary_intent.category.name == "CLARIFICATION":
            last_turn = self.context_manager.get_last_turn()
            if last_turn:
                context_parts.append(f"""【追问上下文】
用户之前问: {last_turn.user_input[:100]}
系统回答: {last_turn.system_response[:150]}
用户现在追问: {user_input}
请提供更详细的解释或例子。""")

        if analysis_result.entities:
            entity_info = []
            for key, value in analysis_result.entities.items():
                if isinstance(value, list):
                    entity_info.append(f"{key}: {', '.join(str(v) for v in value[:3])}")
                else:
                    entity_info.append(f"{key}: {value}")
            if entity_info:
                context_parts.append(f"【识别实体】{'; '.join(entity_info[:5])}")

        for ctx_info in analysis_result.context_used[:2]:
            if ctx_info.source == "memory":
                context_parts.append(f"【相关记忆】{ctx_info.content}")

        return "\n".join(context_parts) if context_parts else ""

    def _get_input_suggestions(self) -> str:
        """获取输入建议"""
        suggestions = [
            "如何学习Python？",
            "给我一个学习计划",
            "今天天气怎么样？",
            "你能做什么？",
            "如何提高编程能力？"
        ]

        selected = random.sample(suggestions, min(3, len(suggestions)))

        message = "[提示] 你可以尝试问我：\n"
        for i, suggestion in enumerate(selected, 1):
            message += f"  {i}. {suggestion}\n"

        return message

    def handle_command(self, user_input):
        """处理命令"""
        parts = user_input.split(' ', 1)
        command = parts[0]
        args = parts[1] if len(parts) > 1 else None
        return self.command_handler.handle_command(command, args)

    def get_system_name(self):
        """获取系统名字"""
        return self.system_name

    def get_user_name(self):
        """获取用户名字"""
        return self.user_name

    def update_system_name(self, new_name):
        """更新系统名字"""
        self.system_name = new_name
        self.response_generator.update_system_name(new_name)
