"""命令执行沙盒系统。

提供安全的命令执行环境，支持：
  - 路径白名单与遍历检测
  - 危险命令拦截
  - 输出路径遮蔽（隐藏主机目录结构）
  - 每会话独立工作空间
  - LRU 缓存管理

主要组件：
  - Sandbox: 抽象基类
  - LocalSandbox: 本地沙盒实现
  - SandboxProvider: 线程安全的生命周期管理
  - CommandValidator: 命令安全验证器
  - SandboxMiddleware: FastAPI 中间件

用法::

    from app.security.sandbox import SandboxProvider, get_sandbox

    # 获取 Provider 单例
    provider = SandboxProvider.get_instance()

    # 获取沙盒
    sandbox = provider.acquire("session-123")

    # 执行命令
    result = await sandbox.execute_command("ls -la")
    print(result.stdout)
"""

# 异常体系
from app.security.sandbox.exceptions import (
    SandboxCommandError,
    SandboxError,
    SandboxNotFoundError,
    SandboxPermissionError,
    SandboxRuntimeError,
    SandboxTimeoutError,
)

# 核心类
from app.security.sandbox.sandbox import CommandResult, Sandbox

# 命令验证
from app.security.sandbox.command_validator import CommandValidator

# 本地沙盒
from app.security.sandbox.local_sandbox import LocalSandbox, mask_local_paths_in_output

# Provider
from app.security.sandbox.local_sandbox_provider import LocalSandboxProvider
from app.security.sandbox.sandbox_provider import SandboxProvider

# 中间件与依赖注入
from app.security.sandbox.middleware import (
    SandboxMiddleware,
    get_optional_sandbox,
    get_sandbox,
)

__all__ = [
    # 异常
    "SandboxError",
    "SandboxNotFoundError",
    "SandboxRuntimeError",
    "SandboxCommandError",
    "SandboxPermissionError",
    "SandboxTimeoutError",
    # 核心
    "Sandbox",
    "CommandResult",
    "CommandValidator",
    # 本地沙盒
    "LocalSandbox",
    "mask_local_paths_in_output",
    # Provider
    "LocalSandboxProvider",
    "SandboxProvider",
    # 中间件
    "SandboxMiddleware",
    "get_sandbox",
    "get_optional_sandbox",
]
