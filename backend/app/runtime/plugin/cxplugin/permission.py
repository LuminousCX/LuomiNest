"""CxPlugin 权限守卫 — 进程内沙箱的核心组件。

拦截插件对系统 API 的调用，校验其是否持有相应权限。
配合 CxPluginContext 使用：所有敏感操作（网络/文件/数据库/工具注册等）
在执行前必须先调用 PermissionGuard.check()，未授权则抛出 PermissionError。

设计原则：
- 默认拒绝：未显式声明的权限一律不授予
- 最小权限：仅授予 manifest 声明 + 默认基础权限
- 失败抛错：权限不足时抛 PermissionError，由插件自行捕获或冒泡
"""
from __future__ import annotations

from loguru import logger

from app.models.plugin import CX_DEFAULT_PERMISSIONS, CxPermission


class PermissionGuard:
    """权限守卫 — 拦截插件的系统 API 调用并校验权限。

    每个插件实例对应一个 PermissionGuard，在 loader 实例化插件时创建。
    """

    def __init__(self, plugin_id: str, permissions: set[CxPermission]) -> None:
        self.plugin_id = plugin_id
        # 始终包含默认权限，再合并 manifest 声明的权限
        self._permissions: set[CxPermission] = set(CX_DEFAULT_PERMISSIONS) | set(permissions)

    @classmethod
    def from_manifest_permissions(cls, plugin_id: str, declared: set[CxPermission]) -> PermissionGuard:
        """从 manifest 声明的权限集合构造守卫。"""
        return cls(plugin_id, declared)

    def has(self, required: CxPermission) -> bool:
        """检查是否持有指定权限（非抛错版）。"""
        return required in self._permissions

    def check(self, required: CxPermission) -> bool:
        """校验权限，不足时抛 PermissionError。

        Returns:
            True（权限通过时）

        Raises:
            PermissionError: 插件缺少所需权限
        """
        if required not in self._permissions:
            message = (
                f"Plugin '{self.plugin_id}' lacks required permission: {required.value}. "
                f"Granted: {sorted(p.value for p in self._permissions)}"
            )
            logger.warning(f"[CxPlugin/PermissionGuard] {message}")
            raise PermissionError(message)
        return True

    def check_any(self, required: list[CxPermission]) -> bool:
        """校验是否持有任意一个指定权限（用于 OR 语义）。"""
        for perm in required:
            if perm in self._permissions:
                return True
        message = (
            f"Plugin '{self.plugin_id}' lacks any of required permissions: "
            f"{[p.value for p in required]}. "
            f"Granted: {sorted(p.value for p in self._permissions)}"
        )
        logger.warning(f"[CxPlugin/PermissionGuard] {message}")
        raise PermissionError(message)

    def grant(self, permission: CxPermission) -> None:
        """运行时动态授予权限（仅限管理 API 调用，如用户审批后）。"""
        self._permissions.add(permission)
        logger.info(f"[CxPlugin/PermissionGuard] Granted {permission.value} to {self.plugin_id}")

    def revoke(self, permission: CxPermission) -> None:
        """运行时撤销权限（不可撤销默认权限）。"""
        if permission in CX_DEFAULT_PERMISSIONS:
            logger.warning(
                f"[CxPlugin/PermissionGuard] Cannot revoke default permission "
                f"{permission.value} from {self.plugin_id}"
            )
            return
        self._permissions.discard(permission)
        logger.info(f"[CxPlugin/PermissionGuard] Revoked {permission.value} from {self.plugin_id}")

    def list_granted(self) -> list[str]:
        """列出已授予的权限值（用于 API 响应/调试）。"""
        return sorted(p.value for p in self._permissions)
