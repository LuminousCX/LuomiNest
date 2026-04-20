"""LuomiNest 统一异常体系。

定义项目中所有自定义异常，形成层次化的异常体系，
便于全局异常捕获、错误码管理和前端错误展示。
"""

from __future__ import annotations

from enum import IntEnum
from typing import Any


class ErrorCode(IntEnum):
    """业务错误码枚举。

    错误码规则：
        - 1xxxx: 通用错误
        - 2xxxx: 参数错误
        - 3xxxx: Agent 相关错误
        - 4xxxx: 模型调用错误
        - 5xxxx: 数据持久化错误
        - 6xxxx: 安全相关错误
        - 7xxxx: 记忆系统错误
    """

    SUCCESS = 0
    UNKNOWN_ERROR = 10000
    INTERNAL_ERROR = 10001
    SERVICE_UNAVAILABLE = 10002

    PARAM_ERROR = 20000
    PARAM_MISSING = 20001
    PARAM_TYPE_ERROR = 20002
    PARAM_RANGE_ERROR = 20003

    AGENT_NOT_FOUND = 30000
    AGENT_ALREADY_EXISTS = 30001
    AGENT_CREATE_FAILED = 30002
    AGENT_UPDATE_FAILED = 30003
    AGENT_DELETE_FAILED = 30004

    MODEL_CALL_FAILED = 40000
    MODEL_TIMEOUT = 40001
    MODEL_RATE_LIMIT = 40002
    MODEL_AUTH_FAILED = 40003
    MODEL_RESPONSE_PARSE_FAILED = 40004

    DAO_ERROR = 50000
    DAO_RECORD_NOT_FOUND = 50001
    DAO_DUPLICATE_KEY = 50002
    DAO_CONNECTION_FAILED = 50003

    CONTENT_BLOCKED = 60000
    CONTENT_SENSITIVE = 60001

    MEMORY_NOT_FOUND = 70000
    MEMORY_STORE_FAILED = 70001
    MEMORY_RECALL_FAILED = 70002
    MEMORY_EMBEDDING_FAILED = 70003
    MEMORY_AGENT_MISMATCH = 70004
    MEMORY_EXPIRED = 70005


class AppException(Exception):
    """所有自定义业务异常的基类。

    Attributes:
        code: 错误码。
        message: 错误信息。
        detail: 额外错误详情。
    """

    def __init__(
        self,
        code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
        message: str = "",
        detail: Any = None,
    ) -> None:
        self.code = code
        self.message = message or code.name
        self.detail = detail
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """将异常转换为字典格式，便于 API 响应序列化。"""
        result: dict[str, Any] = {
            "code": self.code.value,
            "message": self.message,
        }
        if self.detail is not None:
            result["detail"] = self.detail
        return result

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(code={self.code.value}, message={self.message!r})"


class BusinessException(AppException):
    """通用业务异常。"""

    def __init__(
        self,
        message: str = "业务处理异常",
        code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
        detail: Any = None,
    ) -> None:
        super().__init__(code=code, message=message, detail=detail)


class ParamError(AppException):
    """参数校验错误。"""

    def __init__(
        self,
        message: str = "参数错误",
        code: ErrorCode = ErrorCode.PARAM_ERROR,
        detail: Any = None,
    ) -> None:
        super().__init__(code=code, message=message, detail=detail)


class AgentNotFoundError(AppException):
    """Agent 角色未找到。"""

    def __init__(
        self,
        message: str = "Agent 角色不存在",
        agent_id: str | None = None,
    ) -> None:
        detail = {"agent_id": agent_id} if agent_id else None
        super().__init__(
            code=ErrorCode.AGENT_NOT_FOUND,
            message=message,
            detail=detail,
        )


class AgentAlreadyExistsError(AppException):
    """Agent 角色已存在。"""

    def __init__(
        self,
        message: str = "Agent 角色已存在",
        agent_name: str | None = None,
    ) -> None:
        detail = {"agent_name": agent_name} if agent_name else None
        super().__init__(
            code=ErrorCode.AGENT_ALREADY_EXISTS,
            message=message,
            detail=detail,
        )


class ModelCallError(AppException):
    """大模型调用异常。"""

    def __init__(
        self,
        message: str = "模型调用失败",
        code: ErrorCode = ErrorCode.MODEL_CALL_FAILED,
        detail: Any = None,
    ) -> None:
        super().__init__(code=code, message=message, detail=detail)


class ModelTimeoutError(ModelCallError):
    """模型调用超时。"""

    def __init__(self, message: str = "模型调用超时", detail: Any = None) -> None:
        super().__init__(
            message=message,
            code=ErrorCode.MODEL_TIMEOUT,
            detail=detail,
        )


class ModelRateLimitError(ModelCallError):
    """模型调用限流。"""

    def __init__(self, message: str = "模型调用频率超限", detail: Any = None) -> None:
        super().__init__(
            message=message,
            code=ErrorCode.MODEL_RATE_LIMIT,
            detail=detail,
        )


class DaoError(AppException):
    """数据持久化异常。"""

    def __init__(
        self,
        message: str = "数据操作失败",
        code: ErrorCode = ErrorCode.DAO_ERROR,
        detail: Any = None,
    ) -> None:
        super().__init__(code=code, message=message, detail=detail)


class RecordNotFoundError(DaoError):
    """记录未找到。"""

    def __init__(self, message: str = "记录不存在", detail: Any = None) -> None:
        super().__init__(
            message=message,
            code=ErrorCode.DAO_RECORD_NOT_FOUND,
            detail=detail,
        )


class ContentBlockedError(AppException):
    """内容被安全过滤拦截。"""

    def __init__(
        self,
        message: str = "内容不符合安全规范",
        detail: Any = None,
    ) -> None:
        super().__init__(
            code=ErrorCode.CONTENT_BLOCKED,
            message=message,
            detail=detail,
        )


class MemoryNotFoundError(AppException):
    """记忆未找到。"""

    def __init__(
        self,
        message: str = "记忆不存在",
        memory_id: int | None = None,
    ) -> None:
        detail = {"memory_id": memory_id} if memory_id else None
        super().__init__(
            code=ErrorCode.MEMORY_NOT_FOUND,
            message=message,
            detail=detail,
        )


class MemoryStoreError(AppException):
    """记忆存储失败。"""

    def __init__(
        self,
        message: str = "记忆存储失败",
        detail: Any = None,
    ) -> None:
        super().__init__(
            code=ErrorCode.MEMORY_STORE_FAILED,
            message=message,
            detail=detail,
        )


class MemoryRecallError(AppException):
    """记忆召回失败。"""

    def __init__(
        self,
        message: str = "记忆召回失败",
        detail: Any = None,
    ) -> None:
        super().__init__(
            code=ErrorCode.MEMORY_RECALL_FAILED,
            message=message,
            detail=detail,
        )


class MemoryEmbeddingError(AppException):
    """向量嵌入失败。"""

    def __init__(
        self,
        message: str = "向量嵌入生成失败",
        detail: Any = None,
    ) -> None:
        super().__init__(
            code=ErrorCode.MEMORY_EMBEDDING_FAILED,
            message=message,
            detail=detail,
        )
