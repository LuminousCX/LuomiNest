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

        # 天气工具：对接 app/runtime/plugin/skill/builtin/weather.py 的 get_weather
        cls.register(
            SkillDefinition(
                name="get_weather",
                description="获取指定城市的天气信息，包含温度、天气状况、风力、出行建议。当用户明确询问天气、气温、穿什么衣服、是否会下雨时使用。",
                category="utility",
                parameters={
                    "city": {
                        "type": "string",
                        "description": "城市名称，如：北京、上海、广州",
                        "required": True,
                    },
                    "date": {
                        "type": "string",
                        "description": "日期，如：今天、明天、后天、2026-05-06，可选，默认今天",
                        "required": False,
                    },
                },
                is_active=True,
                is_builtin=True,
                handler_name="get_weather",
                tags=["weather", "天气", "utility"],
            ),
            handler=cls._builtin_get_weather,
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

    @classmethod
    async def _builtin_get_weather(cls, **kwargs) -> 'SkillResult':
        """内置天气工具 handler —— 对接 weather_tool.py 的完整 API + 缓存 + 日期解析

        流程：
          1. 提取调用参数中的城市名和日期
          2. 若城市名为空，返回引导用户补充的提示
          3. 若日期为空，默认查询今天
          4. 调用 weather_tool 的天气工具获取数据
          5. 全链路异常捕获，返回友好兜底，绝不暴露技术细节

        参数:
            city: 城市名称（必填，LLM 从用户消息中提取）
            date: 日期（可选，如"明天"、"5.1号"、"下周一"，默认今天）

        返回:
            SkillResult，成功时 data 含 formatted 自然语言回复，
            失败时 error 为友好兜底话术。
        """
        from app.runtime.plugin.skill.base import SkillResult

        city_raw = kwargs.get("city", "")
        date_raw = kwargs.get("date", "")

        # 城市名校验与清洗
        city = city_raw.strip() if city_raw else ""
        # 去掉"市"后缀，如"北京市"→"北京"
        if city.endswith("市") and len(city) > 1:
            city = city[:-1]

        if not city:
            return SkillResult(
                success=False,
                error="请告诉我你想查询哪个城市的天气，比如'北京天气怎么样'。"
            )

        # 日期清洗
        date_str = date_raw.strip() if date_raw else ""

        try:
            # 调用 weather_tool 的核心接口（含日期解析 + 缓存 + 口语化回复）
            from app.utils.weather_tool import _weather_tool
            reply = await _weather_tool.get_reply(city=city, date_str=date_str)
            return SkillResult(success=True, data={"formatted": reply})
        except Exception as e:
            logger.warning(f"[SkillRegistry] _builtin_get_weather 异常: {e}")
            return SkillResult(
                success=False,
                error=f"很抱歉，暂时无法为你获取「{city}」的实时天气数据。"
                      f"你可以打开手机自带的天气APP，或通过搜索引擎输入「{city} 今日天气」快速查询~"
            )
