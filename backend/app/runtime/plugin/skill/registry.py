from loguru import logger
from app.runtime.plugin.skill.base import SkillDefinition, SkillHandler
from app.infrastructure.database.json_store import skills_store


class SkillRegistry:
    _handlers: dict[str, SkillHandler] = {}
    _initialized = False

    @classmethod
    def _ensure_init(cls):
        if cls._initialized:
            return
        cls._initialized = True
        cls._register_builtins()

    @classmethod
    def _register_builtins(cls):
        cls.register(
            SkillDefinition(
                name="search",
                description="搜索知识库获取相关信息。当用户询问需要查找资料、搜索信息或查询知识时使用此工具。",
                category="knowledge",
                parameters={
                    "query": {
                        "type": "string",
                        "description": "搜索查询关键词",
                        "required": True,
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回结果数量，默认5",
                        "required": False,
                    },
                },
                is_active=True,
                is_builtin=True,
                handler_name="search",
                tags=["search", "knowledge", "rag"],
            ),
            handler=cls._builtin_search,
        )

        cls.register(
            SkillDefinition(
                name="web_search",
                description="搜索互联网获取最新信息。当需要查询实时信息、新闻、天气等时使用。",
                category="knowledge",
                parameters={
                    "query": {
                        "type": "string",
                        "description": "搜索查询关键词",
                        "required": True,
                    },
                },
                is_active=True,
                is_builtin=True,
                handler_name="web_search",
                tags=["search", "web", "internet"],
            ),
            handler=cls._builtin_web_search,
        )

        cls.register(
            SkillDefinition(
                name="calculate",
                description="执行数学计算。当需要计算数学表达式、单位换算等时使用。",
                category="utility",
                parameters={
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，如 '2+3*4' 或 'sqrt(16)'",
                        "required": True,
                    },
                },
                is_active=True,
                is_builtin=True,
                handler_name="calculate",
                tags=["math", "calculate", "utility"],
            ),
            handler=cls._builtin_calculate,
        )

        cls.register(
            SkillDefinition(
                name="get_current_time",
                description="获取当前日期和时间信息。",
                category="utility",
                parameters={},
                is_active=True,
                is_builtin=True,
                handler_name="get_current_time",
                tags=["time", "date", "utility"],
            ),
            handler=cls._builtin_get_time,
        )

        cls.register(
            SkillDefinition(
                name="transfer_to_agent",
                description="将对话转交给另一个Agent处理。当当前Agent无法处理或需要其他专业Agent协助时使用。",
                category="agent",
                parameters={
                    "agent_name": {
                        "type": "string",
                        "description": "目标Agent的名称",
                        "required": True,
                    },
                    "task": {
                        "type": "string",
                        "description": "需要转交的任务描述",
                        "required": True,
                    },
                },
                is_active=True,
                is_builtin=True,
                handler_name="transfer_to_agent",
                tags=["agent", "transfer", "handoff"],
            ),
            handler=cls._builtin_transfer_agent,
        )

        logger.success(f"[SkillRegistry] Registered {len(cls._handlers)} builtin skills")

    @classmethod
    def register(cls, skill: SkillDefinition, handler: SkillHandler | None = None):
        cls._ensure_init()
        skill_data = {
            "name": skill.name,
            "description": skill.description,
            "category": skill.category,
            "parameters": skill.parameters,
            "is_active": skill.is_active,
            "is_builtin": skill.is_builtin,
            "handler_name": skill.handler_name,
            "prompt_template": skill.prompt_template,
            "tags": skill.tags,
        }
        skills_store.set(skill.name, skill_data)
        if handler:
            cls._handlers[skill.name] = handler
        logger.debug(f"[SkillRegistry] Registered skill: {skill.name}")

    @classmethod
    def unregister(cls, name: str):
        skills_store.delete(name)
        cls._handlers.pop(name, None)
        logger.debug(f"[SkillRegistry] Unregistered skill: {name}")

    @classmethod
    def get_handler(cls, name: str) -> SkillHandler | None:
        cls._ensure_init()
        return cls._handlers.get(name)

    @classmethod
    def list_skills(cls) -> list[dict]:
        cls._ensure_init()
        return skills_store.values()

    @classmethod
    def get_skill(cls, name: str) -> dict | None:
        cls._ensure_init()
        return skills_store.get(name)

    @classmethod
    def get_openai_tools(cls) -> list[dict]:
        cls._ensure_init()
        tools = []
        for skill_data in skills_store.values():
            if skill_data.get("is_active", True):
                skill = SkillDefinition(
                    name=skill_data["name"],
                    description=skill_data.get("description", ""),
                    parameters=skill_data.get("parameters", {}),
                )
                tools.append(skill.to_openai_tool())
        return tools

    @classmethod
    async def _builtin_search(cls, **kwargs) -> 'SkillResult':
        from app.runtime.plugin.skill.base import SkillResult
        query = kwargs.get("query", "")
        top_k = kwargs.get("top_k", 5)
        try:
            from app.engines.memory.rag.retriever import RAGRetriever
            retriever = RAGRetriever()
            results = await retriever.search(query, top_k=top_k)
            return SkillResult(success=True, data=results)
        except Exception as e:
            return SkillResult(success=False, error=f"Search failed: {e}")

    @classmethod
    async def _builtin_web_search(cls, **kwargs) -> 'SkillResult':
        from app.runtime.plugin.skill.base import SkillResult
        query = kwargs.get("query", "")
        return SkillResult(success=True, data=f"Web search for '{query}' - feature coming soon in LuomiNest")

    @classmethod
    async def _builtin_calculate(cls, **kwargs) -> 'SkillResult':
        from app.runtime.plugin.skill.base import SkillResult
        expression = kwargs.get("expression", "")
        try:
            allowed_names = {
                "abs": abs, "round": round, "min": min, "max": max,
                "sum": sum, "pow": pow, "len": len,
            }
            import math
            for name in dir(math):
                if not name.startswith("_"):
                    allowed_names[name] = getattr(math, name)
            result = eval(expression, {"__builtins__": {}}, allowed_names)
            return SkillResult(success=True, data={"expression": expression, "result": result})
        except Exception as e:
            return SkillResult(success=False, error=f"Calculation error: {e}")

    @classmethod
    async def _builtin_get_time(cls, **kwargs) -> 'SkillResult':
        from app.runtime.plugin.skill.base import SkillResult
        from datetime import datetime
        now = datetime.now()
        weekday_names = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
        return SkillResult(success=True, data={
            "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "weekday": weekday_names[now.weekday()],
            "year": now.year,
            "month": now.month,
            "day": now.day,
            "hour": now.hour,
            "minute": now.minute,
            "second": now.second,
        })

    @classmethod
    async def _builtin_transfer_agent(cls, **kwargs) -> 'SkillResult':
        from app.runtime.plugin.skill.base import SkillResult
        agent_name = kwargs.get("agent_name", "")
        task = kwargs.get("task", "")
        from app.infrastructure.database.json_store import agents_store
        for agent in agents_store.values():
            if agent.get("name") == agent_name:
                return SkillResult(
                    success=True,
                    data={"transferred_to": agent_name, "task": task, "agent_id": agent["id"]},
                    metadata={"transfer": True, "target_agent_id": agent["id"]},
                )
        return SkillResult(success=False, error=f"Agent '{agent_name}' not found")
