"""LuomiNest Agent 记忆访问权限控制（基于 contextvars）。

通过异步上下文变量传递当前 Agent 的记忆访问级别，供 memory_search 工具
在执行时判断是否允许访问、以及访问哪个 Agent 的记忆。

访问级别：
- "none"：无记忆访问权限（联系人 Agent 默认）
- "read_main"：可读主 Agent 记忆（群聊 Agent）
- "read_write"：可读写自身记忆（工作台主 Agent）

设计原则：
- 联系人 Agent（1 对 1 私聊）：memory_access = "none"，不能读写记忆
- 群聊 Agent：memory_access = "read_main"，可主动通过 memory_search 查主 Agent 记忆
- 工作台主 Agent：memory_access = "read_write"，完整记忆读写

品牌化命名：luominest_memory_access。
"""
import contextvars

# 记忆访问级别常量
MEMORY_ACCESS_NONE = "none"
MEMORY_ACCESS_READ_MAIN = "read_main"
MEMORY_ACCESS_READ_WRITE = "read_write"

_VALID_LEVELS = {MEMORY_ACCESS_NONE, MEMORY_ACCESS_READ_MAIN, MEMORY_ACCESS_READ_WRITE}

# 当前异步上下文的记忆访问级别（默认无权限）
_luominest_memory_access: contextvars.ContextVar[str] = contextvars.ContextVar(
    "luominest_memory_access", default=MEMORY_ACCESS_NONE,
)


def get_luominest_memory_access() -> str:
    """读取当前异步上下文的记忆访问级别"""
    return _luominest_memory_access.get()


def set_luominest_memory_access(level: str):
    """设置当前异步上下文的记忆访问级别

    Args:
        level: "none" / "read_main" / "read_write"

    Returns:
        contextvars.Token: 用于 reset_luominest_memory_access 恢复
    """
    if level not in _VALID_LEVELS:
        raise ValueError(f"非法的记忆访问级别: {level}，可选值: {_VALID_LEVELS}")
    return _luominest_memory_access.set(level)


def reset_luominest_memory_access(token) -> None:
    """重置记忆访问级别到之前的状态"""
    _luominest_memory_access.reset(token)
