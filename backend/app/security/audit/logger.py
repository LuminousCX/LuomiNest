"""审计日志记录器。

提供线程安全的 AuditLogger 单例，负责将系统关键操作写入 audit_logs 表。
对 details 中的敏感字段自动脱敏（复用 LogSanitizer）。
"""

from __future__ import annotations

import re
import threading
from typing import ClassVar

from loguru import logger

from app.infrastructure.database.models.audit_log import AuditLog
from app.infrastructure.database.session import get_async_session
from app.runtime.platform.infrastructure.sanitizer import LogSanitizer

# 敏感字段键名模式：包含这些关键词的键值会被脱敏
_SENSITIVE_KEY_PATTERN = re.compile(
    r"(password|api_key|apikey|secret|token|credential|auth)",
    re.IGNORECASE,
)


def _sanitize_details(details: dict | None) -> dict | None:
    """对 details 字典中的敏感字段值进行脱敏。

    遍历所有键，若键名包含敏感关键词，则将值替换为 "***"。
    对字符串值同时执行 LogSanitizer 文本脱敏。
    """
    if not details:
        return details

    sanitizer = LogSanitizer.get_instance()
    sanitized: dict = {}

    for key, value in details.items():
        if _SENSITIVE_KEY_PATTERN.search(key):
            sanitized[key] = "***"
        elif isinstance(value, str):
            sanitized[key] = sanitizer.sanitize(value)
        else:
            sanitized[key] = value

    return sanitized


class AuditLogger:
    """线程安全的审计日志记录器（单例）。

    所有审计日志写入通过本类统一入口，确保格式一致、敏感信息脱敏。
    """

    _instance: ClassVar[AuditLogger | None] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    @classmethod
    def get_instance(cls) -> AuditLogger:
        """获取全局单例。"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    async def log(
        self,
        action: str,
        user_id: str | None = None,
        resource: str | None = None,
        resource_id: str | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
        success: bool = True,
    ) -> None:
        """记录一条审计日志。

        Args:
            action: 动作标识，如 "user.login"、"agent.create"。
            user_id: 操作者用户 ID，None 表示系统操作。
            resource: 资源类型，如 "user"、"agent"。
            resource_id: 资源 ID。
            details: 操作详情，敏感字段会自动脱敏。
            ip_address: 请求来源 IP。
            success: 操作是否成功。
        """
        safe_details = _sanitize_details(details)

        try:
            async with get_async_session() as db:
                record = AuditLog(
                    action=action,
                    user_id=user_id,
                    resource=resource,
                    resource_id=resource_id,
                    details=safe_details,
                    ip_address=ip_address,
                    success=success,
                )
                db.add(record)
        except Exception as exc:
            # 审计日志写入失败不应影响主流程，仅记录警告
            logger.warning(f"[AuditLogger] 写入审计日志失败: {exc}")

    async def log_login(
        self, user_id: str, ip_address: str, success: bool
    ) -> None:
        """记录登录事件。"""
        await self.log(
            action="user.login",
            user_id=user_id,
            resource="user",
            resource_id=user_id,
            ip_address=ip_address,
            success=success,
        )

    async def log_api_key_change(
        self, user_id: str, provider_id: str, action: str
    ) -> None:
        """记录 API Key 变更。"""
        await self.log(
            action=f"provider.{action}",
            user_id=user_id,
            resource="provider",
            resource_id=provider_id,
            details={"provider_id": provider_id, "action": action},
        )

    async def log_agent_change(
        self, user_id: str, agent_id: str, action: str
    ) -> None:
        """记录 Agent 变更。"""
        await self.log(
            action=f"agent.{action}",
            user_id=user_id,
            resource="agent",
            resource_id=agent_id,
            details={"agent_id": agent_id, "action": action},
        )

    async def log_conversation_delete(
        self, user_id: str, conversation_id: str
    ) -> None:
        """记录对话删除。"""
        await self.log(
            action="conversation.delete",
            user_id=user_id,
            resource="conversation",
            resource_id=conversation_id,
        )

    async def log_config_change(self, user_id: str, config_key: str) -> None:
        """记录配置变更。"""
        await self.log(
            action="config.update",
            user_id=user_id,
            resource="config",
            details={"config_key": config_key},
        )

    async def log_command_execute(
        self, user_id: str, command: str, success: bool
    ) -> None:
        """记录命令执行。"""
        await self.log(
            action="command.execute",
            user_id=user_id,
            resource="command",
            details={"command": command},
            success=success,
        )


# 模块级便捷函数
def get_audit_logger() -> AuditLogger:
    """获取审计日志记录器单例。"""
    return AuditLogger.get_instance()
