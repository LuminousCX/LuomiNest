import sys
sys.path.insert(0, '.')

from utils.helpers import is_greeting, is_farewell, is_question, contains_time_query
from utils.logger import logger
from core.nlp.intent_recognizer import IntentRecognizer
from core.memory.memory_store import MemoryStore
from core.safety_filter import safety_filter
from core.conversation.response_generator import ResponseGenerator
from core.conversation.command_handler import CommandHandler

print('Testing helpers...')
assert is_greeting('你好') == True
assert is_farewell('再见') == True
assert is_question('这是什么？') == True
assert contains_time_query('几点了') == True
print('  [OK] helpers tests passed')

print('Testing intent_recognizer...')
recognizer = IntentRecognizer()
assert recognizer.recognize_intent('你好') == 'greeting'
assert recognizer.recognize_intent('再见') == 'farewell'
print('  [OK] intent_recognizer tests passed')

print('Testing safety_filter...')
assert safety_filter.is_safe('你好') == True
assert safety_filter.is_safe('杀人') == False
print('  [OK] safety_filter tests passed')

print('Testing response_generator...')
gen = ResponseGenerator('汐汐')
response = gen.generate_response('greeting', '你好')
assert '汐汐' in response or '你好' in response
print('  [OK] response_generator tests passed')

print('Testing command_handler...')
class MockAdmin:
    is_admin = False
    def check_permission(self, p): return False
    def login(self, p): return p == 'admin123'
    def logout(self): pass

class MockMemory:
    def get_memory_count(self): return 0
    def get_working_memory(self): return []
    def clear_all_memory(self): pass

handler = CommandHandler(MockAdmin(), MockMemory())
assert '/help' in handler.handle_command('/help', None)
assert '未知命令' in handler.handle_command('/unknown', None)
print('  [OK] command_handler tests passed')

print('\nAll tests passed!')
