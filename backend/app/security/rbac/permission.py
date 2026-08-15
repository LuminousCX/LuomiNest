"""RBAC 权限常量与 FastAPI 依赖注入。

定义系统所有权限点，并提供 require_permission 依赖工厂，
用于在路由层声明式校验当前用户是否拥有指定权限。
"""

from __future__ import annotations

from enum import Enum

from fastapi import Request

from app.core.exceptions import AuthorizationError


class Permission(str, Enum):
    """权限常量。

    格式: "<resource>:<action>"，与角色映射配合使用。
    """

    # 对话
    CHAT_READ = "chat:read"
    CHAT_WRITE = "chat:write"
    CHAT_DELETE = "chat:delete"

    # Agent
    AGENT_READ = "agent:read"
    AGENT_WRITE = "agent:write"
    AGENT_DELETE = "agent:delete"

    # 配置
    CONFIG_READ = "config:read"
    CONFIG_WRITE = "config:write"

    # 记忆
    MEMORY_READ = "memory:read"
    MEMORY_WRITE = "memory:write"

    # 管理
    ADMIN_USERS = "admin:users"
    ADMIN_SYSTEM = "admin:system"


def require_permission(permission: Permission):
    """FastAPI 依赖注入工厂：检查当前用户是否拥有指定权限。

    从 request.state.user 中读取角色列表，结合角色权限映射进行校验。
    无权限时抛出 AuthorizationError（403, FORBIDDEN）。

    Args:
        permission: 要求的目标权限。

    Returns:
        可被 Depends() 消费的异步依赖函数。

    Usage::

        @router.delete("/agents/{agent_id}")
        async def delete_agent(
            agent_id: str,
            _=Depends(require_permission(Permission.AGENT_DELETE)),
        ):
            ...
    """

    async def dependency(request: Request) -> dict:
        # 从 request.state 获取用户信息（由认证中间件设置）
        user_info: dict | None = getattr(request.state, "user", None)

        if user_info is None:
            # local 模式下可能未设置 user 信息，默认放行（向后兼容）
            return {}

        roles: list[str] = user_info.get("roles", [])

        if not roles:
            raise AuthorizationError(f"无权限执行此操作（需要: {permission.value}）")

        # 延迟导入避免循环依赖
        from app.security.rbac.role import Role, has_permission

        for role_str in roles:
            try:
                role = Role(role_str)
            except ValueError:
                # 未知角色跳过
                continue
            if has_permission(role, permission):
                return user_info

        raise AuthorizationError(f"无权限执行此操作（需要: {permission.value}）")

    return dependency
