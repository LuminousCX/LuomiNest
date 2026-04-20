"""记忆插件抽象基类与实现。

提供插件化的记忆集成接口：
- MemoryPlugin: 抽象基类，定义对话前检索、对话后存储的钩子
- SQLiteMemoryPlugin: 基于 MemoryService 的具体实现

使用方式：
    plugin = SQLiteMemoryPlugin(memory_service)
    memories = plugin.before_chat(agent_id, user_msg)
    plugin.after_chat(agent_id, user_msg, assistant_msg)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.service.memory_service import MemoryService
from src.utils.logger import get_logger

logger = get_logger()


class MemoryPlugin(ABC):
    """记忆插件抽象基类。

    定义对话前检索、对话后存储的钩子接口，
    实现无侵入的记忆系统集成。
    """

    @abstractmethod
    def before_chat(
        self,
        agent_id: int,
        user_msg: str,
        top_k: int = 10,
    ) -> list[dict]:
        """对话前检索记忆。

        Args:
            agent_id: Agent ID。
            user_msg: 用户消息。
            top_k: 召回数量。

        Returns:
            召回的记忆内容字典列表。
        """

    @abstractmethod
    async def after_chat(
        self,
        agent_id: int,
        user_msg: str,
        assistant_msg: str,
    ) -> None:
        """对话后存储记忆。

        Args:
            agent_id: Agent ID。
            user_msg: 用户消息。
            assistant_msg: 助手回复。
        """

    @abstractmethod
    def clear_memories(self, agent_id: int) -> tuple[int, int]:
        """清空指定 Agent 的所有记忆。"""


class SQLiteMemoryPlugin(MemoryPlugin):
    """基于 MemoryService 的记忆插件实现。

    使用 SQLite + FTS5 + 向量存储的本地记忆系统。

    Attributes:
        memory_service: 记忆服务实例。
    """

    def __init__(self, memory_service: MemoryService) -> None:
        self.memory_service = memory_service

    def before_chat(
        self,
        agent_id: int,
        user_msg: str,
        top_k: int = 10,
    ) -> list[dict]:
        """对话前检索记忆。"""
        try:
            memories = self.memory_service.retrieve(
                agent_id=agent_id,
                query=user_msg,
                top_k=top_k,
            )
            logger.debug(
                f"对话前记忆检索: agent_id={agent_id}, "
                f"召回 {len(memories)} 条记忆"
            )
            return memories
        except Exception as e:
            logger.warning(f"对话前记忆检索失败: {e}")
            return []

    async def after_chat(
        self,
        agent_id: int,
        user_msg: str,
        assistant_msg: str,
    ) -> None:
        """对话后存储记忆。"""
        try:
            await self.memory_service.memorize(
                agent_id=agent_id,
                user_msg=user_msg,
                assistant_msg=assistant_msg,
            )
            logger.debug(f"对话后记忆存储: agent_id={agent_id}")
        except Exception as e:
            logger.warning(f"对话后记忆存储失败: {e}")

    def clear_memories(self, agent_id: int) -> tuple[int, int]:
        """清空指定 Agent 的所有记忆。"""
        return self.memory_service.clear(agent_id)
