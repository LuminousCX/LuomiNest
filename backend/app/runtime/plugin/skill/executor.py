from loguru import logger
from app.runtime.plugin.skill.base import SkillResult
from app.runtime.plugin.skill.registry import SkillRegistry


class SkillExecutor:
    async def execute(self, skill_name: str, arguments: dict, agent_id: str | None = None) -> str:
        logger.info(f"[SkillExecutor] Executing skill: {skill_name}, args={arguments}")

        handler = SkillRegistry.get_handler(skill_name)
        if handler:
            try:
                result = await handler(**arguments)
                if isinstance(result, SkillResult):
                    return result.to_text()
                return str(result)
            except Exception as e:
                logger.error(f"[SkillExecutor] Handler error for {skill_name}: {e}")
                return f"Skill execution error: {e}"

        skill_data = SkillRegistry.get_skill(skill_name)
        if skill_data and skill_data.get("prompt_template"):
            try:
                rendered = skill_data["prompt_template"].format(**arguments)
                return rendered
            except Exception as e:
                logger.error(f"[SkillExecutor] Template render error for {skill_name}: {e}")
                return f"Template error: {e}"

        if skill_data and skill_data.get("handler_name") == "mcp_tool":
            try:
                from app.domains.mcp_tools.tool_executor import MCPToolExecutor
                mcp_executor = MCPToolExecutor()
                result = await mcp_executor.execute(
                    server_name=arguments.get("_mcp_server", ""),
                    tool_name=skill_name,
                    arguments=arguments,
                )
                return str(result)
            except Exception as e:
                logger.error(f"[SkillExecutor] MCP tool error for {skill_name}: {e}")
                return f"MCP tool error: {e}"

        logger.warning(f"[SkillExecutor] No handler found for skill: {skill_name}")
        return f"Skill '{skill_name}' is registered but has no executable handler. Description: {skill_data.get('description', 'N/A') if skill_data else 'Unknown skill'}"
