"""
简单测试脚本 - 验证语义相似度和意图识别优化
"""

import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

print("="*60)
print("语义相似度和意图识别优化测试")
print("="*60)

print("\n[1] 测试导入模块...")
try:
    from core.nlp.semantic_similarity import (
        SemanticSimilarityCalculator,
        get_semantic_calculator,
        SynonymDictionary
    )
    print("  ✓ semantic_similarity 导入成功")
except Exception as e:
    print(f"  ✗ semantic_similarity 导入失败: {e}")
    sys.exit(1)

try:
    from core.nlp.intent_recognizer_enhanced import (
        EnhancedIntentRecognizer,
        get_intent_recognizer,
        IntentCategory
    )
    print("  ✓ intent_recognizer_enhanced 导入成功")
except Exception as e:
    print(f"  ✗ intent_recognizer_enhanced 导入失败: {e}")
    sys.exit(1)

try:
    from core.nlp.intent_function_mapper import (
        IntentFunctionMapper,
        get_intent_function_mapper
    )
    print("  ✓ intent_function_mapper 导入成功")
except Exception as e:
    print(f"  ✗ intent_function_mapper 导入失败: {e}")
    sys.exit(1)

try:
    from core.nlp.unified_intent_service import (
        UnifiedIntentService,
        get_unified_intent_service
    )
    print("  ✓ unified_intent_service 导入成功")
except Exception as e:
    print(f"  ✗ unified_intent_service 导入失败: {e}")
    sys.exit(1)

print("\n[2] 测试语义相似度计算...")
calc = get_semantic_calculator()
test_pairs = [
    ("我很高兴", "我很开心"),
    ("你好", "您好"),
    ("推荐电影", "有什么好看的电影"),
]
for t1, t2 in test_pairs:
    result = calc.calculate_similarity(t1, t2)
    print(f"  '{t1}' vs '{t2}' -> 相似度: {result.score:.3f}")

print("\n[3] 测试同义词词典...")
test_words = ["学习", "开心", "生气"]
for word in test_words:
    synonyms = SynonymDictionary.get_synonyms(word)
    print(f"  '{word}' 的同义词: {list(synonyms)[:3]}")

print("\n[4] 测试意图识别...")
recognizer = get_intent_recognizer()
test_inputs = [
    "你好，很高兴见到你",
    "现在几点了",
    "我叫小明",
    "推荐一些好看的电影",
]
for user_input in test_inputs:
    result = recognizer.analyze(user_input)
    print(f"  '{user_input}' -> 意图: {result.primary_intent.name}, 置信度: {result.primary_intent.confidence:.3f}")

print("\n[5] 测试意图相似度匹配...")
test_cases = [
    ("嗨", ["greeting", "farewell", "gratitude"]),
    ("拜拜", ["greeting", "farewell", "gratitude"]),
]
for text, intents in test_cases:
    best, score, matched = calc.find_best_intent(text, intents)
    print(f"  '{text}' -> 最佳匹配: {best}, 分数: {score:.3f}")

print("\n[6] 测试统一意图分析服务...")
service = get_unified_intent_service()
test_inputs = [
    "你好，我是小明",
    "现在几点了",
]
for user_input in test_inputs:
    result = service.analyze(user_input)
    print(f"  '{user_input}' -> 意图: {result.primary_intent.name}, API: {result.should_use_api}")

print("\n[7] 测试功能映射...")
from core.nlp.intent_recognizer_enhanced import IntentMatch
mapper = get_intent_function_mapper()
intent = IntentMatch(
    name="get_current_time",
    category=IntentCategory.QUERY,
    confidence=0.9,
    priority=5,
    local_function="get_current_time"
)
result = mapper.execute_intent(intent, "现在几点了")
print(f"  'get_current_time' -> 成功: {result.success}")
if result.message:
    print(f"  结果: {result.message[:50]}...")

print("\n" + "="*60)
print("所有测试完成!")
print("="*60)
