"""沙盒异常体系 — 所有沙盒相关错误的基类与子类。"""


class SandboxError(Exception):
    """沙盒错误基类。

    Attributes:
        message: 人类可读的错误描述。
        details: 可选的附加信息字典。
    """

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({detail_str})"
        return self.message


class SandboxNotFoundError(SandboxError):
    """沙盒实例未找到。"""

    def __init__(self, message: str = "Sandbox not found", sandbox_id: str | None = None):
        details = {"sandbox_id": sandbox_id} if sandbox_id else None
        super().__init__(message, details)
        self.sandbox_id = sandbox_id


class SandboxRuntimeError(SandboxError):
    """运行时错误（配置缺失、环境不可用等）。"""

    pass


class SandboxCommandError(SandboxError):
    """命令执行错误。

    Attributes:
        command: 导致错误的命令字符串。
        exit_code: 进程退出码。
    """

    def __init__(
        self,
        message: str,
        command: str | None = None,
        exit_code: int | None = None,
    ):
        details: dict = {}
        if command is not None:
            details["command"] = command[:100] + "..." if len(command) > 100 else command
        if exit_code is not None:
            details["exit_code"] = exit_code
        super().__init__(message, details or None)
        self.command = command
        self.exit_code = exit_code


class SandboxPermissionError(SandboxError):
    """权限错误（路径越界、操作被拒等）。

    Attributes:
        path: 触发错误的路径。
        operation: 尝试执行的操作。
    """

    def __init__(
        self,
        message: str,
        path: str | None = None,
        operation: str | None = None,
    ):
        details: dict = {}
        if path is not None:
            details["path"] = path
        if operation is not None:
            details["operation"] = operation
        super().__init__(message, details or None)
        self.path = path
        self.operation = operation


class SandboxTimeoutError(SandboxError):
    """命令执行超时。"""

    def __init__(self, message: str = "Command execution timed out", timeout: int | None = None):
        details = {"timeout": timeout} if timeout is not None else None
        super().__init__(message, details)
        self.timeout = timeout
