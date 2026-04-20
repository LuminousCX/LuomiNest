"""
自定义异常模块
Author: LumiNest Team
Date: 2026-04-14
"""


class BusinessException(Exception):
    """业务异常基类"""
    
    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class ConfigError(BusinessException):
    """配置错误"""
    pass


class ValidationError(BusinessException):
    """参数校验错误"""
    pass


class APIError(BusinessException):
    """API调用错误"""
    pass


class APITimeoutError(APIError):
    """API超时错误"""
    pass


class APIUnavailableError(APIError):
    """API不可用错误"""
    pass


class MemoryError(BusinessException):
    """记忆系统错误"""
    pass


class KnowledgeError(BusinessException):
    """知识库错误"""
    pass


class WebParseError(BusinessException):
    """网页解析错误"""
    pass


class PermissionError(BusinessException):
    """权限错误"""
    pass


class UserNotFoundError(BusinessException):
    """用户不存在错误"""
    pass


class AuthenticationError(BusinessException):
    """认证错误"""
    pass
