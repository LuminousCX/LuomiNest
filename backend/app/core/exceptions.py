class LuomiNestError(Exception):
    def __init__(self, message: str, code: str = "UNKNOWN_ERROR", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundError(LuomiNestError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, "NOT_FOUND", 404)


class AuthenticationError(LuomiNestError):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, "AUTH_FAILED", 401)


class AuthorizationError(LuomiNestError):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(message, "FORBIDDEN", 403)


class ValidationError(LuomiNestError):
    def __init__(self, message: str = "Validation failed"):
        super().__init__(message, "VALIDATION_ERROR", 422)


class RateLimitError(LuomiNestError):
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, "RATE_LIMITED", 429)


class ProviderError(LuomiNestError):
    def __init__(self, message: str = "LLM provider error", provider: str = ""):
        self.provider = provider
        super().__init__(message, "PROVIDER_ERROR", 502)


class PluginError(LuomiNestError):
    def __init__(self, message: str = "Plugin error"):
        super().__init__(message, "PLUGIN_ERROR", 500)


def register_exception_handlers(app: FastAPI) -> None:
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.exception_handler(LuomiNestError)
    async def luominest_error_handler(request: Request, exc: LuomiNestError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )
