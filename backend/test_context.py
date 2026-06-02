import sys
sys.path.insert(0, 'app')

from engines.memory import get_memory_engine

engine = get_memory_engine()
context = engine.build_context()
print(context[:3000])  # 打印前3000字符