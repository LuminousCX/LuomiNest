class LuomiNestError(Exception):
    def __init__(self, message: str, code: str = "UNKNOWN_ERROR", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundError(LuomiNestError):
    def __init__(self, message: str = "Resource not found", code: str = "NOT_FOUND"):
        super().__init__(message, code, 404)


class BadRequestError(LuomiNestError):
    """请求参数或操作无效（400）。code 可覆盖为业务错误码。"""

    def __init__(self, message: str = "请求无效", code: str = "BAD_REQUEST"):
        super().__init__(message, code, 400)


class ConflictError(LuomiNestError):
    """资源状态冲突（409），如重复安装、模式锁定等。"""

    def __init__(self, message: str = "资源状态冲突", code: str = "CONFLICT"):
        super().__init__(message, code, 409)


class InternalServerError(LuomiNestError):
    """服务器内部错误（500）。"""

    def __init__(self, message: str = "服务器内部错误", code: str = "INTERNAL_ERROR"):
        super().__init__(message, code, 500)


class ServiceUnavailableError(LuomiNestError):
    """服务暂不可用（503），如调度器未启动、引擎缺失。"""

    def __init__(self, message: str = "服务暂不可用", code: str = "SERVICE_UNAVAILABLE"):
        super().__init__(message, code, 503)


class AuthenticationError(LuomiNestError):
    def __init__(self, message: str = "Authentication failed", code: str = "AUTH_FAILED"):
        super().__init__(message, code, 401)


class AuthorizationError(LuomiNestError):
    def __init__(self, message: str = "Permission denied", code: str = "FORBIDDEN"):
        super().__init__(message, code, 403)


class ValidationError(LuomiNestError):
    def __init__(self, message: str = "Validation failed", code: str = "VALIDATION_ERROR"):
        super().__init__(message, code, 422)


class RateLimitError(LuomiNestError):
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, "RATE_LIMITED", 429)


class ProviderError(LuomiNestError):
    def __init__(self, message: str = "LLM provider error", provider: str = "", code: str = "PROVIDER_ERROR", status_code: int = 502):
        self.provider = provider
        super().__init__(message, code, status_code)


class PluginError(LuomiNestError):
    def __init__(self, message: str = "Plugin error"):
        super().__init__(message, "PLUGIN_ERROR", 500)


class ConversationModeLockedError(LuomiNestError):
    """对话模式锁定（洋葱架构 §6）：已有消息的对话不可变更 chat_mode。

    后端权威锁定：任何对已有消息对话的 chat_mode 修改请求返回 409。
    """

    def __init__(self, message: str = "Conversation mode is locked once messages exist"):
        super().__init__(message, "ERR_CONV_MODE_LOCKED", 409)


# ---------------------------------------------------------------------------
# 语音域异常（voice-model-market.md G8：语音端点统一走错误码体系）
# ---------------------------------------------------------------------------

class VoiceEngineUnavailableError(LuomiNestError):
    """TTS/STT 引擎全部不可用（依赖缺失或初始化失败）。"""

    def __init__(self, message: str = "语音引擎不可用"):
        super().__init__(message, "VOICE_ENGINE_UNAVAILABLE", 503)


class VoiceSynthesisError(LuomiNestError):
    """语音合成失败（引擎抛出异常/超时）。"""

    def __init__(self, message: str = "语音合成失败", engine: str = ""):
        self.engine = engine
        super().__init__(message, "VOICE_SYNTHESIS_FAILED", 500)


class VoiceTranscribeError(LuomiNestError):
    """语音识别失败（引擎抛出异常/超时）。"""

    def __init__(self, message: str = "语音识别失败", engine: str = ""):
        self.engine = engine
        super().__init__(message, "VOICE_TRANSCRIBE_FAILED", 500)


class LangNotSupportedError(LuomiNestError):
    """当前引擎/模型不支持请求的语言（语言感知解析链 L1-L4 判定失败）。

    前端捕获此错误码后弹出消息通知：更换引擎/模型 或 开启翻译管线。
    """

    def __init__(self, message: str = "当前语音引擎不支持该语言", lang: str = "", engine: str = ""):
        self.lang = lang
        self.engine = engine
        super().__init__(message, "LANG_NOT_SUPPORTED", 400)


class VoiceNotFoundError(LuomiNestError):
    """请求的音色不存在于引擎音色列表。"""

    def __init__(self, message: str = "音色不存在", voice: str = ""):
        self.voice = voice
        super().__init__(message, "VOICE_NOT_FOUND", 400)


class VoiceConfigError(LuomiNestError):
    """语音配置校验失败（voice_config 写入时字段非法）。"""

    def __init__(self, message: str = "语音配置无效"):
        super().__init__(message, "VOICE_CONFIG_INVALID", 422)
