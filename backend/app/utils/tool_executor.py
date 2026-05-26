"""
工具执行引擎 —— 批量执行工具调用并返回处理后的结果

功能：
  接收工具名+参数列表，批量执行并处理结果（过滤/聚合/精简），
  返回结构化的工具执行结果供 LLM 总结使用。

设计原则：
  1. 所有异常捕获，单个工具失败不影响其他工具
  2. 所有工具执行后统一做结果精简处理
  3. 支持本地工具和外部 API 工具混合调用
  4. 异步执行，天然支持并发（但按序执行以保障顺序一致性）
"""

from loguru import logger
from app.runtime.plugin.skill.executor import SkillExecutor
from app.utils.tool_result_processor import process_tool_result
from app.utils.tool_parameter_extractor import ToolParameterExtractor
from app.utils.intent_gateway import is_weather_query
from app.utils.time_tool import TimeTool
from app.utils.weather_tool import _weather_tool
from app.utils.local_handler import _extract_city
from app.utils.web_search_tool import search_web


_time_tool_instance = TimeTool(timezone="Asia/Shanghai")
_extractor = ToolParameterExtractor()


async def execute_tool_by_name(tool_name: str, args: dict, **kwargs) -> str:
    """Tool Loop 专用：按工具名+参数执行单个工具，返回结果文本

    与 execute_single_tool 的区别：
      - 返回纯文本字符串（不是 dict）
      - 参数由 LLM 生成（不是正则提取）
      - 自动处理工具不存在的情况
    """
    try:
        if tool_name == "delegate_task":
            task_description = args.get("task_description", "").strip()
            if task_description:
                try:
                    from app.core.agent.tool_loop import delegate_sub_task
                    result = await delegate_sub_task(
                        task_description=task_description,
                        provider_name=kwargs.get("provider_name", ""),
                        model=kwargs.get("model", ""),
                    )
                    return result if result else "子代理未返回结果"
                except Exception as e:
                    logger.warning(f"[ToolExecutor] delegate_task 异常: {e}")
                    return "子代理执行失败"
            return "任务描述为空"

        if tool_name == "get_weather":
            city = args.get("city", "")
            date_str = args.get("date", args.get("date_str", ""))
            if city:
                try:
                    raw = await _weather_tool.get_reply(city, date_str)
                    return process_tool_result(tool_name, raw)
                except Exception as e:
                    logger.warning(f"[ToolExecutor] 天气工具异常: {e}")
                    return f"获取天气信息失败: {e}"

        if tool_name == "get_current_time":
            try:
                raw = _time_tool_instance.get_reply(query_type="date", user_message="")
                return process_tool_result(tool_name, raw)
            except Exception as e:
                logger.warning(f"[ToolExecutor] 时间工具异常: {e}")
                return f"获取时间信息失败: {e}"

        if tool_name == "web_search":
            query = args.get("query", "")
            if query:
                raw = await search_web(query)
                return process_tool_result(tool_name, raw)
            return "搜索查询为空"

        if tool_name == "calculate":
            expression = args.get("expression", "")
            if expression:
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
                    return f"{expression} = {result}"
                except Exception as e:
                    return f"计算错误: {e}"
            return "计算表达式为空"

        if tool_name == "search":
            query = args.get("query", "")
            if query:
                try:
                    from app.runtime.plugin.skill.executor import SkillExecutor
                    executor = SkillExecutor()
                    raw = await executor.execute(tool_name, args)
                    return process_tool_result(tool_name, raw)
                except Exception as e:
                    return f"知识库搜索失败: {e}"
            return "搜索查询为空"

        executor = SkillExecutor()
        raw = await executor.execute(tool_name, args)
        processed = process_tool_result(tool_name, raw)
        return processed

    except Exception as e:
        logger.warning(f"[ToolExecutor] execute_tool_by_name({tool_name}) 异常: {e}")
        return f"工具 '{tool_name}' 执行出错: {e}"


async def execute_tool_chain(
    user_query: str,
    agent_id: str | None = None,
    external_search_results: str | None = None,
) -> list[dict]:
    """根据用户查询匹配工具并批量执行

    完整流程：
      1. 用 get_matched_tools 匹配场景和工具列表
      2. 对每个工具用 ToolParameterExtractor 提取参数
      3. 对每个工具调用 execute_single_tool 执行
      4. 对每个结果用 process_tool_result 精简
      5. 返回结构化结果列表

    参数:
        user_query: 用户原始提问
        agent_id: 代理 ID（用于上下文隔离）

    返回:
        [{"tool_name": "...", "args": {...}, "result": "...", "success": bool}]

    用法:
        results = await execute_tool_chain("北京明天天气怎么样")
        if results:
            print(results[0]["result"])  # 精简后的天气文本
    """
    from app.utils.tool_lazy_loader import get_matched_tools

    results: list[dict] = []

    # 1. 获取匹配的工具列表
    tools = get_matched_tools(user_query)
    if not tools:
        return results

    # 2. 提取工具名集合
    tool_names: set[str] = set()
    for tool_def in tools:
        fn = tool_def.get("function", {})
        name = fn.get("name", "")
        if name:
            tool_names.add(name)

    # 3. 如果同时有时间工具和搜索工具，先执行时间工具获取当前日期
    #    用于优化搜索查询词（如5月问软考→搜索"下半年"）
    current_date_info: str | None = None
    if "get_current_time" in tool_names and "web_search" in tool_names:
        try:
            time_args = _extractor.extract("get_current_time", user_query)
            time_result = _time_tool_instance.get_reply(
                query_type="date",
                user_message=user_query,
            )
            if time_result:
                current_date_info = time_result
                logger.info(f"[ToolExecutor] 跨工具联动: 获取当前日期 → {current_date_info[:50]}")
        except Exception as e:
            logger.debug(f"[ToolExecutor] 跨工具联动时间获取失败: {e}")

    # 4. 对每个工具提取参数并执行
    executor = SkillExecutor()
    for tool_name in sorted(tool_names):
        args = _extractor.extract(tool_name, user_query)

        # 如果是搜索工具且有外部搜索结果，直接使用
        if tool_name == "web_search" and external_search_results:
            processed = process_tool_result(tool_name, external_search_results)
            logger.info(f"[ToolExecutor] web_search (外部浏览器结果) → {len(processed)} 字符")
            results.append({
                "tool_name": tool_name,
                "args": args,
                "result": processed,
                "success": True,
            })
            continue

        result = await execute_single_tool(tool_name, args, executor, agent_id, user_query)
        results.append(result)

    return results


async def execute_single_tool(
    tool_name: str,
    args: dict,
    executor: SkillExecutor | None = None,
    agent_id: str | None = None,
    user_query: str = "",
) -> dict:
    """执行单个工具并返回处理结果

    参数:
        tool_name: 工具名称
        args: 从用户查询中提取的参数
        executor: SkillExecutor 实例（可选，复用避免重复创建）
        agent_id: 代理 ID
        user_query: 用户原始提问（用于本地工具的上下文感知）

    返回:
        {"tool_name": "...", "args": {...}, "result": "...", "success": bool}
    """
    if executor is None:
        executor = SkillExecutor()

    try:
        # ---------- 天气工具：优先走本地快速路径 ----------
        if tool_name == "get_weather" and "city" in args:
            city = args.get("city", "")
            date_str = args.get("date_str", "")
            try:
                raw = await _weather_tool.get_reply(city, date_str)
            except Exception as e:
                logger.warning(f"[ToolExecutor] 天气快速路径异常，降级到通用执行: {e}")
                raw = await executor.execute(tool_name, args, agent_id=agent_id)
            processed = process_tool_result(tool_name, raw)
            logger.info(f"[ToolExecutor] get_weather → {len(processed)} 字符")
            return {
                "tool_name": tool_name,
                "args": args,
                "result": processed,
                "success": True,
            }

        # ---------- 时间工具：优先走本地快速路径 ----------
        if tool_name == "get_current_time":
            try:
                date_str = args.get("date_str", "")
                if date_str:
                    raw = _time_tool_instance.get_reply_with_context(
                        query_type="date_offset",
                        user_message=user_query,
                        agent_type="通用",
                    )
                else:
                    raw = _time_tool_instance.get_reply(
                        query_type="date",
                        user_message=user_query,
                    )
            except Exception as e:
                logger.warning(f"[ToolExecutor] 时间快速路径异常，降级到通用执行: {e}")
                raw = await executor.execute(tool_name, args, agent_id=agent_id)
            processed = process_tool_result(tool_name, raw)
            logger.info(f"[ToolExecutor] get_current_time → {len(processed)} 字符")
            return {
                "tool_name": tool_name,
                "args": args,
                "result": processed,
                "success": True,
            }

        # ---------- 搜索工具：走 DuckDuckGo 搜索 ----------
        if tool_name == "web_search":
            query = args.get("query", user_query)
            raw = await search_web(query)
            processed = process_tool_result(tool_name, raw)
            logger.info(f"[ToolExecutor] web_search → {len(processed)} 字符")
            return {
                "tool_name": tool_name,
                "args": args,
                "result": processed,
                "success": True,
            }

        # ---------- 通用路径：走 SkillExecutor ----------
        raw = await executor.execute(tool_name, args, agent_id=agent_id)
        processed = process_tool_result(tool_name, raw)
        logger.info(f"[ToolExecutor] {tool_name} → 原始 {len(raw)} 字符 → 精简 {len(processed)} 字符")
        return {
            "tool_name": tool_name,
            "args": args,
            "result": processed,
            "success": True,
        }

    except Exception as e:
        logger.warning(f"[ToolExecutor] {tool_name} 执行异常: {e}")
        return {
            "tool_name": tool_name,
            "args": args,
            "result": f"工具执行出错: {e}",
            "success": False,
        }


def build_tool_summary(user_query: str, tool_results: list[dict]) -> str:
    """构建发给 LLM 的工具结果总结提示词

    将工具执行结果组织成自然语言提示，让 LLM 进行总结回答。

    参数:
        user_query: 用户原始提问
        tool_results: execute_tool_chain 返回的结构化结果列表

    返回:
        可发送给 LLM 的提示词文本
    """
    if not tool_results:
        return user_query

    success_results = [r for r in tool_results if r["success"]]
    failed_results = [r for r in tool_results if not r["success"]]

    parts = [f"用户问：{user_query}"]

    if success_results:
        parts.append("\n已获取到以下信息：")
        for r in success_results:
            result_text = r["result"]
            if len(result_text) > 300:
                result_text = result_text[:300] + "…"
            parts.append(f"- [{r['tool_name']}] {result_text}")

    if failed_results:
        parts.append("\n以下工具执行失败：")
        for r in failed_results:
            parts.append(f"- {r['tool_name']}: {r['result']}")

    parts.append("\n请根据以上信息，用自然、友好的语言总结回答用户的问题。")
    parts.append("如果信息不足或工具失败，告诉用户暂时无法获取完整信息。")
    parts.append("注意区分「报名时间」和「考试时间」，用户问的是考试/事件日期时，不要用报名时间代替。")
    parts.append("如果搜索结果中的日期已经过去，请说明该日期已过，并尝试告知下一次的时间（如有信息）。")

    return "\n".join(parts)