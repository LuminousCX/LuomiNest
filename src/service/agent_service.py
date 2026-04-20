"""Agent 人格管理服务。

核心业务逻辑：
- 预设 Agent 人格的初始化与加载
- 自定义 Agent 的创建、修改、删除
- 基于角色人设生成对话 prompt 模板
- 角色风格的动态切换与生效
- 记忆系统集成：构建 Prompt 时自动注入召回记忆
"""

from __future__ import annotations

from typing import Optional

from src.dao.agent_dao import AgentDao
from src.exceptions import AgentAlreadyExistsError, AgentNotFoundError, ParamError
from src.model.agent import AgentEntity, AgentStatus, AgentType, PresetAgentConfig, ResponseConfig
from src.schema.agent_schema import AgentCreateRequest, AgentUpdateRequest
from src.service.prompt_template import get_prompt_template_service
from src.utils.logger import get_logger
from src.utils.validation_utils import validate_agent_name

logger = get_logger()


class AgentService:
    """Agent 人格管理服务。

    Attributes:
        agent_dao: Agent 数据访问对象。
        _current_agent_id: 当前激活的 Agent ID。
    """

    def __init__(self, agent_dao: AgentDao) -> None:
        self.agent_dao = agent_dao
        self._current_agent_id: Optional[int] = None
        self._init_preset_agents()

    def _init_preset_agents(self) -> None:
        """初始化预设 Agent 人格。"""
        for config in PresetAgentConfig.PRESET_AGENTS:
            existing = self.agent_dao.select_by_name(config["name"])
            if existing is not None:
                logger.debug(f"预设 Agent 已存在，跳过: {config['name']}")
                continue

            response_config = ResponseConfig(**config.get("response_config", {}))
            agent = AgentEntity(
                name=config["name"],
                agent_type=config.get("agent_type", AgentType.PRESET),
                title=config.get("title", ""),
                background=config.get("background", ""),
                personality=config.get("personality", ""),
                speaking_style=config.get("speaking_style", ""),
                constraints=config.get("constraints", ""),
                prompt_template=config.get("prompt_template"),
                response_config=response_config,
            )
            self.agent_dao.insert(agent)
            logger.info(f"预设 Agent 初始化完成: {agent.name}")

        if self._current_agent_id is None:
            all_agents = self.agent_dao.select_all()
            if all_agents:
                self._current_agent_id = all_agents[0].id

    def get_all_agents(self) -> list[AgentEntity]:
        """获取所有活跃的 Agent 人格列表。"""
        return self.agent_dao.select_all()

    def get_preset_agents(self) -> list[AgentEntity]:
        """获取所有预设 Agent 人格。"""
        return self.agent_dao.select_by_type(AgentType.PRESET)

    def get_custom_agents(self) -> list[AgentEntity]:
        """获取所有自定义 Agent 人格。"""
        return self.agent_dao.select_by_type(AgentType.CUSTOM)

    def get_agent_by_id(self, agent_id: int) -> AgentEntity:
        """根据 ID 获取 Agent 人格。"""
        agent = self.agent_dao.select_by_id(agent_id)
        if agent is None:
            raise AgentNotFoundError(agent_id=str(agent_id))
        return agent

    def get_current_agent(self) -> AgentEntity:
        """获取当前激活的 Agent 人格。"""
        if self._current_agent_id is None:
            agents = self.agent_dao.select_all()
            if not agents:
                raise AgentNotFoundError(message="没有任何可用的 Agent 人格")
            self._current_agent_id = agents[0].id

        return self.get_agent_by_id(self._current_agent_id)

    def create_agent(self, request: AgentCreateRequest) -> AgentEntity:
        """创建自定义 Agent 人格。"""
        validate_agent_name(request.name)

        existing = self.agent_dao.select_by_name(request.name)
        if existing is not None:
            raise AgentAlreadyExistsError(agent_name=request.name)

        agent = AgentEntity(
            name=request.name,
            avatar=request.avatar,
            title=request.title,
            background=request.background,
            personality=request.personality,
            speaking_style=request.speaking_style,
            constraints=request.constraints,
            prompt_template=request.prompt_template,
            response_config=request.response_config,
            agent_type=AgentType.CUSTOM,
        )

        result = self.agent_dao.insert(agent)
        logger.info(f"自定义 Agent 创建成功: {agent.name}")
        return result

    def update_agent(self, agent_id: int, request: AgentUpdateRequest) -> AgentEntity:
        """更新 Agent 人格。"""
        self.get_agent_by_id(agent_id)

        update_data: dict = {}
        for field_name in [
            "name", "avatar", "title", "background",
            "personality", "speaking_style", "constraints",
            "prompt_template", "status",
        ]:
            value = getattr(request, field_name, None)
            if value is not None:
                update_data[field_name] = value

        if request.response_config is not None:
            update_data["response_config"] = request.response_config.model_dump()

        if update_data:
            self.agent_dao.update(agent_id, update_data)

        return self.get_agent_by_id(agent_id)

    def delete_agent(self, agent_id: int) -> bool:
        """删除 Agent 人格。"""
        agent = self.get_agent_by_id(agent_id)

        if agent.agent_type == AgentType.PRESET:
            raise ParamError(message="预设 Agent 人格不允许删除，只能禁用")

        self.agent_dao.delete(agent_id)

        if self._current_agent_id == agent_id:
            agents = self.agent_dao.select_all()
            self._current_agent_id = agents[0].id if agents else None

        logger.info(f"Agent 删除成功: {agent.name}")
        return True

    def switch_agent(self, agent_id: int) -> AgentEntity:
        """切换当前激活的 Agent 人格。"""
        agent = self.get_agent_by_id(agent_id)
        self._current_agent_id = agent_id
        logger.info(f"切换当前 Agent: {agent.name}")
        return agent

    def build_system_prompt(
        self,
        agent_id: Optional[int] = None,
        memories: Optional[list[str]] = None,
    ) -> str:
        """构建指定 Agent 的系统 prompt。

        使用 Jinja2 模板引擎渲染，前端只需传递 agent_id。
        支持注入召回的记忆上下文。

        Args:
            agent_id: Agent ID，为空则使用当前角色。
            memories: 召回的记忆内容列表。

        Returns:
            完整的系统 prompt 字符串。
        """
        if agent_id:
            agent = self.get_agent_by_id(agent_id)
        else:
            agent = self.get_current_agent()

        template_service = get_prompt_template_service()
        return agent.build_system_prompt(template_service, memories=memories)
