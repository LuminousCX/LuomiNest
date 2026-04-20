"""
常量定义模块
Author: LumiNest Team
Date: 2026-04-14
"""

MAX_RETRY_TIMES = 3
DEFAULT_TIMEOUT = 30
MAX_URLS_PER_CALL = 3
MAX_WORKING_MEMORY = 100
MAX_CONTEXT_LENGTH = 50
MAX_LINE_LENGTH = 120

DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 800

RESPONSE_MODE_EXPERT = "expert"
RESPONSE_MODE_FAST = "fast"
DEFAULT_RESPONSE_MODE = RESPONSE_MODE_FAST

EXPERT_MODE_TEMPERATURE = 0.5
EXPERT_MODE_MAX_TOKENS = 2048
EXPERT_MODE_THINKING_DELAY_MS = 1500

FAST_MODE_TEMPERATURE = 0.8
FAST_MODE_MAX_TOKENS = 512
FAST_MODE_THINKING_DELAY_MS = 300

MEMORY_PATH = "data/memory.json"
KNOWLEDGE_BASE_PATH = "data/knowledge_base.json"
VECTOR_STORE_PATH = "data/vectors.json"
RESPONSE_MODE_PATH = "data/response_mode.json"

LOG_DIR = "logs"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_INTERNAL_ERROR = 500

WELCOME_MESSAGE = """
============================================================
欢迎使用汐汐智能助手！
============================================================

我可以帮你：
  [1] 回答问题 - 问我任何问题，我会尽力回答
  [2] 学习计划 - 为你制定个性化的学习计划
  [3] 记住信息 - 我会记住你的偏好和重要信息
  [4] 提供建议 - 为你提供各种建议和指导

快捷命令：
  /help    - 查看所有可用命令
  /stats   - 查看系统统计信息
  /memory  - 查看记忆状态
  /clear   - 清空对话历史

提示：
  - 直接输入问题即可开始对话
  - 我会记住你的名字、喜好等重要信息
  - 输入 '再见' 或 '退出' 可以结束对话
============================================================
"""
