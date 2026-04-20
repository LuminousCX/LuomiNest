"""
语义相似度和意图识别优化测试
"""

import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from core.nlp.semantic_similarity import (
    SemanticSimilarityCalculator,
    get_semantic_calculator,
    SynonymDictionary
)
from core.nlp.intent_recognizer_enhanced import (
    EnhancedIntentRecognizer,
    get_intent_recognizer,
    IntentCategory
)


def test_semantic_similarity():
    """测试语义相似度"""
    print("\n" + "="*60)
    print("【测试1: 语义相似度计算】")
    print("="*60)
    
    calc = get_semantic_calculator()
    
    test_cases = [
        ("我很高兴", "我很开心"),
        ("你好", "您好"),
        ("推荐一些电影", "有什么好看的电影"),
        ("我很生气", "我很愤怒"),
        ("怎么学习Python", "如何学习Python"),
        ("再见", "拜拜"),
    ]
    
    for text1, text2 in test_cases:
        result = calc.calculate_similarity(text1, text2)
        print(f"\n文本1: {text1}")
        print(f"文本2: {text2}")
        print(f"相似度: {result.score:.3f}")
        print(f"最佳方法: {result.method}")
        print(f"匹配词: {result.matched_terms[:5]}")
        print(f"置信度: {result.confidence:.3f}")


def test_synonym_dictionary():
    """测试同义词词典"""
    print("\n" + "="*60)
    print("【测试2: 同义词词典】")
    print("="*60)
    
    test_words = ["学习", "开心", "生气", "推荐", "帮助", "编程"]
    
    for word in test_words:
        synonyms = SynonymDictionary.get_synonyms(word)
        related = SynonymDictionary.get_related_words(word)
        print(f"\n词汇: {word}")
        print(f"同义词: {list(synonyms)[:5]}")
        print(f"相关词: {list(related)[:5]}")


def test_intent_recognition():
    """测试意图识别"""
    print("\n" + "="*60)
    print("【测试3: 意图识别】")
    print("="*60)
    
    recognizer = get_intent_recognizer()
    
    test_inputs = [
        "你好，很高兴见到你",
        "现在几点了",
        "今天天气怎么样",
        "我叫小明",
        "我想学习Python编程",
        "推荐一些好看的电影",
        "我很伤心，能安慰我吗",
        "谢谢你的帮助",
        "再见，下次见",
        "帮助",
        "这个是什么意思",
        "为什么天空是蓝色的",
    ]
    
    for user_input in test_inputs:
        result = recognizer.analyze(user_input)
        print(f"\n输入: {user_input}")
        print(f"主要意图: {result.primary_intent.name}")
        print(f"类别: {result.primary_intent.category.value}")
        print(f"置信度: {result.primary_intent.confidence:.3f}")
        print(f"综合分数: {result.primary_intent.combined_score:.3f}")
        print(f"本地功能: {result.primary_intent.local_function}")
        print(f"话题: {result.topic}")
        print(f"情感: {result.sentiment}")


def test_intent_similarity():
    """测试意图相似度匹配"""
    print("\n" + "="*60)
    print("【测试4: 意图相似度匹配】")
    print("="*60)
    
    calc = get_semantic_calculator()
    
    test_cases = [
        ("嗨", ["greeting", "farewell", "gratitude"]),
        ("拜拜", ["greeting", "farewell", "gratitude"]),
        ("多谢", ["greeting", "farewell", "gratitude"]),
        ("我很郁闷", ["emotional_sad", "emotional_happy", "emotional_angry"]),
        ("太棒了", ["emotional_sad", "emotional_happy", "emotional_angry"]),
        ("我很恼火", ["emotional_sad", "emotional_happy", "emotional_angry"]),
    ]
    
    for text, intents in test_cases:
        best_intent, score, matched = calc.find_best_intent(text, intents)
        print(f"\n输入: {text}")
        print(f"候选意图: {intents}")
        print(f"最佳匹配: {best_intent}")
        print(f"匹配分数: {score:.3f}")
        print(f"匹配词: {matched}")


def test_query_expansion():
    """测试查询扩展"""
    print("\n" + "="*60)
    print("【测试5: 查询扩展】")
    print("="*60)
    
    calc = get_semantic_calculator()
    
    queries = [
        "学习编程",
        "推荐电影",
        "天气怎么样",
        "我很开心",
    ]
    
    for query in queries:
        expanded = calc.expand_query(query)
        print(f"\n原始查询: {query}")
        print(f"扩展查询: {expanded[:5]}")


def test_unified_service():
    """测试统一意图分析服务"""
    print("\n" + "="*60)
    print("【测试6: 统一意图分析服务】")
    print("="*60)
    
    from core.nlp.unified_intent_service import get_unified_intent_service
    
    service = get_unified_intent_service()
    
    test_inputs = [
        "你好，我是小明",
        "现在几点了",
        "我想学习Python编程，有什么建议吗",
        "推荐一些好看的电影",
        "我很伤心，今天工作不顺心",
    ]
    
    for user_input in test_inputs:
        result = service.analyze(user_input)
        print(f"\n输入: {user_input}")
        print(f"主要意图: {result.primary_intent.name}")
        print(f"置信度: {result.confidence:.3f}")
        print(f"是否使用API: {result.should_use_api}")
        print(f"话题: {result.topic}")
        print(f"情感: {result.sentiment}")
        print(f"实体: {result.entities}")
        print(f"分析耗时: {result.analysis_time_ms:.2f}ms")


def test_function_mapping():
    """测试功能映射"""
    print("\n" + "="*60)
    print("【测试7: 功能映射】")
    print("="*60)
    
    from core.nlp.intent_function_mapper import IntentFunctionMapper
    from core.nlp.intent_recognizer_enhanced import IntentMatch, IntentCategory
    
    mapper = IntentFunctionMapper()
    
    test_intents = [
        ("get_current_time", "现在几点了"),
        ("introduce_self", "你是谁"),
        ("show_help", "帮助"),
    ]
    
    for intent_name, user_input in test_intents:
        intent = IntentMatch(
            name=intent_name,
            category=IntentCategory.QUERY,
            confidence=0.9,
            priority=5,
            local_function=intent_name
        )
        
        result = mapper.execute_intent(intent, user_input)
        print(f"\n意图: {intent_name}")
        print(f"输入: {user_input}")
        print(f"成功: {result.success}")
        if result.message:
            print(f"结果: {result.message[:100]}...")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "#"*60)
    print("# 语义相似度和意图识别优化测试")
    print("#"*60)
    
    try:
        test_semantic_similarity()
        test_synonym_dictionary()
        test_intent_recognition()
        test_intent_similarity()
        test_query_expansion()
        test_unified_service()
        test_function_mapping()
        
        print("\n" + "#"*60)
        print("# 所有测试完成!")
        print("#"*60)
    except Exception as e:
        print(f"\n测试出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_all_tests()
