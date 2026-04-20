"""
NLP 模块 - 自然语言处理组件
"""

from .intent_recognizer import IntentRecognizer
from .context_resolver import ContextResolver, get_context_resolver
from .name_extractor import NameExtractor
from .keyword_extractor import KeywordExtractor
from .unified_intent_analyzer import UnifiedIntentAnalyzer, get_unified_intent_analyzer
from .context_manager import ContextManager, get_context_manager
from .enhanced_intent_analyzer import (
    EnhancedIntentAnalyzer,
    get_enhanced_intent_analyzer,
    SemanticCalculator,
    TimeDecayCalculator,
    SentimentAnalyzer,
    TopicAnalyzer,
    IntentCombiner,
    SentimentIntensity,
    TopicRelation,
)

from .semantic_similarity import (
    SemanticSimilarityCalculator,
    get_semantic_calculator,
    SynonymDictionary,
    SemanticVectorGenerator,
    TFIDFCalculator,
    SimilarityResult,
)

from .intent_recognizer_enhanced import (
    EnhancedIntentRecognizer,
    get_intent_recognizer,
    IntentMatch,
    IntentAnalysisResult,
    IntentCategory,
    IntentPriority,
    IntentPatternRegistry,
)

from .intent_function_mapper import (
    IntentFunctionMapper,
    get_intent_function_mapper,
    LocalFunctionRegistry,
    FunctionResult,
)

from .unified_intent_service import (
    UnifiedIntentService,
    get_unified_intent_service,
    UnifiedAnalysisResult,
)

__all__ = [
    'IntentRecognizer',
    'ContextResolver',
    'get_context_resolver',
    'NameExtractor',
    'KeywordExtractor',
    'UnifiedIntentAnalyzer',
    'get_unified_intent_analyzer',
    'ContextManager',
    'get_context_manager',
    'EnhancedIntentAnalyzer',
    'get_enhanced_intent_analyzer',
    'SemanticCalculator',
    'TimeDecayCalculator',
    'SentimentAnalyzer',
    'TopicAnalyzer',
    'IntentCombiner',
    'SentimentIntensity',
    'TopicRelation',
    'SemanticSimilarityCalculator',
    'get_semantic_calculator',
    'SynonymDictionary',
    'SemanticVectorGenerator',
    'TFIDFCalculator',
    'SimilarityResult',
    'EnhancedIntentRecognizer',
    'get_intent_recognizer',
    'IntentMatch',
    'IntentAnalysisResult',
    'IntentCategory',
    'IntentPriority',
    'IntentPatternRegistry',
    'IntentFunctionMapper',
    'get_intent_function_mapper',
    'LocalFunctionRegistry',
    'FunctionResult',
    'UnifiedIntentService',
    'get_unified_intent_service',
    'UnifiedAnalysisResult',
]
