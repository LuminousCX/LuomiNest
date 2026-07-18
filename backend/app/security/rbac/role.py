"""RBAC 角色定义与权限映射。

定义系统角色及其对应的权限集合，供 require_permission 依赖注入使用。
"""

from __future__ import annotations

from enum import Enum

from app.security.rbac.permission import Permission


class Role(str, Enum):
    """系统角色。

    - OWNER:  拥有者，具备全部权限（含管理类）。
    - USER:   普通用户，具备日常读写权限，无管理权限。
    - VIEWER: 只读用户，仅具备读取权限。
    """

    OWNER = "owner"
    USER = "user"
    VIEWER = "viewer"


# 角色 → 权限映射
ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.OWNER: set(Permission),
    Role.USER: {
        Permission.CHAT_READ,
        Permission.CHAT_WRITE,
        Permission.CHAT_DELETE,
        Permission.AGENT_READ,
        Permission.AGENT_WRITE,
        Permission.CONFIG_READ,
        Permission.CONFIG_WRITE,
        Permission.MEMORY_READ,
        Permission.MEMORY_WRITE,
    },
    Role.VIEWER: {
        Permission.CHAT_READ,
        Permission.AGENT_READ,
        Permission.CONFIG_READ,
        Permission.MEMORY_READ,
    },
}


def has_permission(role: Role, permission: Permission) -> bool:
    """检查角色是否拥有指定权限。

    Args:
        role: 待检查的角色。
        permission: 目标权限。

    Returns:
        True 表示拥有，False 表示无权限。
    """
    return permission in ROLE_PERMISSIONS.get(role, set())


def get_role_permissions(role: Role) -> list[Permission]:
    """获取角色的所有权限列表。

    Args:
        role: 目标角色。

    Returns:
        该角色拥有的权限列表（无序）。
    """
    return list(ROLE_PERMISSIONS.get(role, set()))
