import sys
sys.path.insert(0, '.')

from app.engines.memory import get_memory_engine

try:
    engine = get_memory_engine()
    print('Engine created')
    
    data = engine.load_data()
    print('Data loaded successfully')
    
    memory = engine.load_memory()
    print(f'Memory loaded: {len(memory)} chars')
    
    profile = engine.parse_profile()
    print(f'Profile: {profile}')
    
    facts = [f.model_dump() for f in data.facts]
    print(f'Facts: {len(facts)} items')
    
    result = {
        'memory': memory,
        'profile': profile,
        'facts': facts
    }
    print('Endpoint logic works!')
    
except Exception as e:
    print(f'Error: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()