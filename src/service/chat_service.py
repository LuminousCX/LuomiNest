"""对话交互与大模型调用服务。

核心业务逻辑：
- 基于当前 Agent 角色拼接系统 prompt（使用 Jinja2 模板）
- 支持专家模式/快速模式切换
- 对话上下文记忆与管理
- 大模型 API 调用封装（流式/非流式）
- 多模态消息支持（图片、文档）
- Token 用量统计
- 异步消息持久化（先响应后存储）
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator, Optional

from src.dao.conversation_dao import ConversationDao
from src.model.agent import AgentEntity
from src.model.conversation import (
    ConversationEntity,
    MessageEntity,
    MessageRole,
    ResponseMode,
)
from src.schema.chat_schema import ChatRequest, ChatResponse, MultimodalChatRequest
from src.service.agent_service import AgentService
from src.service.prompt_template import get_prompt_template_service
from src.utils.logger import get_logger
from src.utils.model_util import ModelResponse, ResponseMode as ModelResponseMode, get_model_util
from src.utils.string_utils import generate_id
from src.utils.token_utils import estimate_tokens, get_token_budget

logger = get_logger()

_MAX_CONTEXT_MESSAGES = 50


class ChatService:
    """对话交互服务。

    Attributes:
        conversation_dao: 对话数据访问对象。
        agent_service: Agent 角色管理服务。
    """

    def __init__(
        self,
        conversation_dao: ConversationDao,
        agent_service: AgentService,
    ) -> None:
        """初始化服务。

        Args:
            conversation_dao: 对话数据访问对象。
            agent_service: Agent 角色管理服务。
        """
        self.conversation_dao = conversation_dao
        self.agent_service = agent_service

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """非流式对话。

        优化：用户消息存储与 LLM 调用并行执行，
        助手消息存储在响应返回后异步完成。
        """
        conversation = self._get_or_create_conversation(
            conversation_id=request.conversation_id,
            agent_id=request.agent_id,
            mode=request.mode,
        )
        agent = self._get_agent(request.agent_id)

        user_tokens = estimate_tokens(request.content)
        user_message = MessageEntity(
            role=MessageRole.USER,
            content=request.content,
            tokens=user_tokens,
        )

        system_prompt = self._build_system_prompt(agent)
        openai_messages = self._build_openai_messages(
            system_prompt, conversation, user_message
        )

        model_util = get_model_util()
        mode = self._convert_mode(request.mode)

        user_msg_task = asyncio.create_task(
            asyncio.to_thread(self.conversation_dao.add_message, conversation.id, user_message)
        )
        response = await model_util.chat(
            messages=openai_messages,
            mode=mode,
        )
        await user_msg_task

        assistant_message = MessageEntity(
            role=MessageRole.ASSISTANT,
            content=response.content,
            tokens=response.completion_tokens,
        )
        asyncio.create_task(
            asyncio.to_thread(self.conversation_dao.add_message, conversation.id, assistant_message)
        )

        get_token_budget().consume(response.total_tokens)

        return ChatResponse(
            conversation_id=conversation.id,
            message_id=assistant_message.id,
            content=response.content,
            tokens=response.completion_tokens,
            total_tokens=conversation.total_tokens + user_tokens + response.completion_tokens,
            mode=request.mode,
        )

    async def multimodal_chat(self, request: MultimodalChatRequest) -> ChatResponse:
        """多模态对话。

        优化：助手消息存储在响应返回后异步完成。
        """
        conversation = self._get_or_create_conversation(
            conversation_id=request.conversation_id,
            agent_id=request.agent_id,
            mode=request.mode,
        )
        agent = self._get_agent(request.agent_id)

        system_prompt = self._build_system_prompt(agent)

        openai_messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]

        if request.multimodal_messages:
            openai_messages.extend(request.multimodal_messages)

        if request.content:
            openai_messages.append({"role": "user", "content": request.content})

        model_util = get_model_util()
        mode = self._convert_mode(request.mode)

        response = await model_util.chat(
            messages=openai_messages,
            mode=mode,
        )

        user_tokens = estimate_tokens(request.content)
        user_message = MessageEntity(
            role=MessageRole.USER,
            content=request.content or "[多模态消息]",
            tokens=user_tokens,
        )
        asyncio.create_task(
            asyncio.to_thread(self.conversation_dao.add_message, conversation.id, user_message)
        )

        assistant_message = MessageEntity(
            role=MessageRole.ASSISTANT,
            content=response.content,
            tokens=response.completion_tokens,
        )
        asyncio.create_task(
            asyncio.to_thread(self.conversation_dao.add_message, conversation.id, assistant_message)
        )

        get_token_budget().consume(response.total_tokens)

        return ChatResponse(
            conversation_id=conversation.id,
            message_id=assistant_message.id,
            content=response.content,
            tokens=response.completion_tokens,
            total_tokens=conversation.total_tokens + user_tokens + response.completion_tokens,
            mode=request.mode,
        )

    async def chat_stream(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """流式对话。

        Args:
            request: 对话请求。

        Yields:
            流式输出的文本片段。
        """
        conversation = self._get_or_create_conversation(
            conversation_id=request.conversation_id,
            agent_id=request.agent_id,
            mode=request.mode,
        )
        agent = self._get_agent(request.agent_id)

        user_tokens = estimate_tokens(request.content)
        user_message = MessageEntity(
            role=MessageRole.USER,
            content=request.content,
            tokens=user_tokens,
        )
        self.conversation_dao.add_message(conversation.id, user_message)

        system_prompt = self._build_system_prompt(agent)
        openai_messages = self._build_openai_messages(
            system_prompt, conversation, user_message
        )

        model_util = get_model_util()
        mode = self._convert_mode(request.mode)

        full_content: list[str] = []

        async for chunk in model_util.chat_stream(
            messages=openai_messages,
            mode=mode,
        ):
            if chunk.content:
                full_content.append(chunk.content)
                yield chunk.content

        assistant_content = "".join(full_content)
        completion_tokens = estimate_tokens(assistant_content)

        assistant_message = MessageEntity(
            role=MessageRole.ASSISTANT,
            content=assistant_content,
            tokens=completion_tokens,
        )
        asyncio.create_task(
            asyncio.to_thread(self.conversation_dao.add_message, conversation.id, assistant_message)
        )
        get_token_budget().consume(user_tokens + completion_tokens)

    def _get_agent(self, agent_id: Optional[int] = None) -> AgentEntity:
        """获取 Agent 实体。

        Args:
            agent_id: Agent ID，为空则使用当前角色。

        Returns:
            Agent 实体。
        """
        if agent_id:
            return self.agent_service.get_agent_by_id(agent_id)
        return self.agent_service.get_current_agent()

    def _build_system_prompt(self, agent: AgentEntity) -> str:
        """构建系统 prompt。

        Args:
            agent: Agent 实体。

        Returns:
            完整的系统 prompt 字符串。
        """
        template_service = get_prompt_template_service()
        return agent.build_system_prompt(template_service)

    def _convert_mode(self, mode: ResponseMode) -> ModelResponseMode:
        """转换模式枚举类型。

        Args:
            mode: 对话模式。

        Returns:
            模型调用模式。
        """
        if mode == ResponseMode.EXPERT:
            return ModelResponseMode.EXPERT
        return ModelResponseMode.FAST

    def _get_or_create_conversation(
        self,
        conversation_id: Optional[str] = None,
        agent_id: Optional[int] = None,
        mode: ResponseMode = ResponseMode.FAST,
    ) -> ConversationEntity:
        """获取已有会话或创建新会话。

        Args:
            conversation_id: 会话 ID。
            agent_id: Agent ID。
            mode: 对话模式。

        Returns:
            对话会话实体。
        """
        if conversation_id:
            conversation = self.conversation_dao.select_conversation_by_id(
                conversation_id
            )
            if conversation:
                return conversation

        resolved_agent_id = agent_id or self.agent_service.get_current_agent().id
        conversation = ConversationEntity(
            agent_id=str(resolved_agent_id),
            mode=mode,
        )
        self.conversation_dao.insert_conversation(conversation)
        return conversation

    def _build_openai_messages(
        self,
        system_prompt: str,
        conversation: ConversationEntity,
        current_user_message: MessageEntity,
    ) -> list[dict[str, str]]:
        """构建 OpenAI API 所需的消息列表。

        Args:
            system_prompt: 系统提示词。
            conversation: 对话会话。
            current_user_message: 当前用户消息。

        Returns:
            OpenAI 格式消息列表。
        """
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]

        history = conversation.messages[-_MAX_CONTEXT_MESSAGES:]
        for msg in history:
            if msg.id != current_user_message.id:
                messages.append(msg.to_openai_format())

        messages.append(current_user_message.to_openai_format())
        return messages

    def switch_mode(self, conversation_id: str, mode: ResponseMode) -> bool:
        """切换对话模式。

        Args:
            conversation_id: 会话 ID。
            mode: 目标模式。

        Returns:
            是否切换成功。
        """
        self.conversation_dao.update_conversation_mode(
            conversation_id, mode.value
        )
        logger.info(f"对话模式切换: conversation_id={conversation_id}, mode={mode.value}")
        return True

    def get_conversation_history(
        self, conversation_id: str
    ) -> Optional[ConversationEntity]:
        """获取对话历史记录。

        Args:
            conversation_id: 会话 ID。

        Returns:
            对话会话实体。
        """
        return self.conversation_dao.select_conversation_by_id(conversation_id)

    def get_conversation_list(
        self, agent_id: Optional[str] = None, limit: int = 50
    ) -> list[ConversationEntity]:
        """获取对话列表。

        Args:
            agent_id: Agent ID 过滤。
            limit: 返回数量限制。

        Returns:
            对话会话列表。
        """
        if agent_id:
            return self.conversation_dao.select_conversations_by_agent(agent_id, limit)
        return self.conversation_dao.select_all_conversations(limit)

    def delete_conversation(self, conversation_id: str) -> bool:
        """删除对话会话。

        Args:
            conversation_id: 会话 ID。

        Returns:
            是否删除成功。
        """
        return self.conversation_dao.delete_conversation(conversation_id)

    def get_token_usage(self) -> dict:
        """获取 Token 用量统计。

        Returns:
            Token 用量字典。
        """
        return get_token_budget().to_dict()

    async def test_model_connection(self) -> bool:
        """测试模型连接是否正常。

        Returns:
            连接是否成功。
        """
        model_util = get_model_util()
        return await model_util.test_connection()
