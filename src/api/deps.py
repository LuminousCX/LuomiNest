"""依赖注入与服务初始化。

提供 FastAPI 的依赖注入机制，统一管理所有 Service 实例。
"""

from __future__ import annotations

import threading
from typing import Optional

from src.config.settings import get_settings
from src.dao.agent_dao import AgentDao
from src.dao.conversation_dao import ConversationDao
from src.dao.database import DatabaseManager
from src.service.agent_service import AgentService
from src.service.chat_service import ChatService
from src.service.file_service import FileService
from src.service.memory_service import MemoryService
from src.utils.logger import get_logger

logger = get_logger()

_services: Optional[dict] = None
_services_lock = threading.Lock()


def init_services() -> dict:
    """初始化所有服务实例。

    按照依赖顺序创建 DAO 和 Service：
    1. 加载配置
    2. 创建 DatabaseManager
    3. 创建 DAO 实例
    4. 创建 Service 实例

    Returns:
        包含所有服务实例的字典。
    """
    global _services
    if _services is not None:
        return _services

    with _services_lock:
        if _services is not None:
            return _services

        settings = get_settings()

        db_manager = DatabaseManager(db_path=settings.db_sqlite_path)

        agent_dao = AgentDao(db_manager=db_manager)
        conversation_dao = ConversationDao(db_manager=db_manager)

        agent_service = AgentService(agent_dao=agent_dao)
        memory_service = MemoryService(db_manager=db_manager)
        chat_service = ChatService(
            conversation_dao=conversation_dao,
            agent_service=agent_service,
        )
        file_service = FileService(data_dir=settings.data_dir)

        _services = {
            "db_manager": db_manager,
            "agent_dao": agent_dao,
            "conversation_dao": conversation_dao,
            "agent_service": agent_service,
            "chat_service": chat_service,
            "file_service": file_service,
            "memory_service": memory_service,
        }

        logger.info("所有服务初始化完成")
        return _services


def get_services() -> dict:
    """获取已初始化的服务实例字典。"""
    if _services is None:
        return init_services()
    return _services


def reset_services() -> None:
    """重置所有服务实例（主要用于测试）。"""
    global _services
    _services = None
