"""LuomiNest RBAC — 基于角色的访问控制。

角色（Role）→ 权限（Permission）映射 + FastAPI 依赖注入工厂。

Usage::

    from app.security.rbac import Permission, require_permission

    @router.delete("/agents/{agent_id}")
    async def delete_agent(
        agent_id: str,
        _=Depends(require_permission(Permission.AGENT_DELETE)),
    ):
        ...

路由守卫读取 ``request.state.user["roles"]``（由认证中间件写入），
local 单用户模式下未设置 user 信息时默认放行（向后兼容）。
"""
from app.security.rbac.permission import Permission, require_permission
from app.security.rbac.role import (
    ROLE_PERMISSIONS,
    Role,
    get_role_permissions,
    has_permission,
)

__all__ = [
    "Permission",
    "require_permission",
    "Role",
    "ROLE_PERMISSIONS",
    "get_role_permissions",
    "has_permission",
]
