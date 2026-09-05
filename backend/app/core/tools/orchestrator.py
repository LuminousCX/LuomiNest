"""LuomiNest 工具编排器。

衔接 LLM function calling 循环与工具注册表：
- get_tools_for_llm：将注册表中的工具转换为 OpenAI function calling 格式
- execute_tool_call：执行 LLM 产生的单个工具调用，返回 tool message
- build_assistant_message_with_tool_calls：构建含 tool_calls 的 assistant 消息（回填上下文）
- build_default_pipeline：根据场景组装中间件管道（Phase 4 新增）
- create_runner：创建带默认管道的 AgentRunner（Phase 4 新增）

设计原则：
1. 编排器不持有工具实例，全部通过 tool_registry 查找，避免双重注册
2. 工具调用结果统一格式化为 tool message，content 为字符串（LLM 可读）
3. max_iterations 限制单次对话的工具调用循环次数，防止无限递归
4. 中间件管道按场景组装（chat/subagent/group），位置驱动执行顺序
"""
import json
from typing import Any

from loguru import logger

from app.core.tools.registry import tool_registry

# ──────────────────────────────────────────────────────────────
# 工具兼容性运行时探测缓存
# ──────────────────────────────────────────────────────────────

_tools_compatibility_cache: dict[str, bool] = {}


def _detect_current_platform() -> str:
    """探测当前运行平台（win/mac/linux）。

    Returns:
        'win'（Windows）/ 'mac'（macOS）/ 'linux'（Linux 及其他）
    """
    import os
    import sys
    if os.name == "nt":
        return "win"
    if sys.platform == "darwin":
        return "mac"
    return "linux"


def _to_llm_function_with_tier(tool) -> dict[str, Any]:
    """按 tier 转换为 OpenAI function 格式（S1b L1 轻量注入）。

    meta tier 工具若无必填参数，仅注入占位参数 schema（~50 token/个），
    完整定义由 read_luominest_tool 按需拉取；有必填参数的 meta 工具
    （如 read_luominest_tool 自身）保留完整 schema 以保证可调用性。
    """
    if tool.tier != "meta":
        return tool.to_openai_function()
    try:
        required = tool.parameters.get("required") or []
    except Exception:
        required = []
    if required:
        return tool.to_openai_function()
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": {"type": "object", "properties": {}},
        },
    }


async def discover_tool_compatibility(provider_name: str, model: str, llm_adapter=None) -> bool:
    """运行时探测模型是否支持工具调用。

    借鉴 airi 的 attemptForToolsCompatibilityDiscovery 设计。

    策略：
    1. 先查缓存
    2. 查 ProviderCapabilities 的 known_unsupported_models
    3. 查 ProviderCapabilities 的 supports_tool_calls
    4. 缓存结果
    """
    cache_key = f"{provider_name}:{model}"
    if cache_key in _tools_compatibility_cache:
        return _tools_compatibility_cache[cache_key]

    # 从能力表检查
    try:
        from app.runtime.provider.llm.capabilities import get_capabilities
        caps = get_capabilities(provider_name, model)
        if model in caps.known_unsupported_models:
            _tools_compatibility_cache[cache_key] = False
            logger.debug(
                f"[ToolCompat] {cache_key}: 在 known_unsupported_models 中，禁用工具调用"
            )
            return False
        if not caps.supports_tool_calls:
            _tools_compatibility_cache[cache_key] = False
            logger.debug(
                f"[ToolCompat] {cache_key}: provider 默认不支持工具调用"
            )
            return False
        # 能力表声明支持，缓存为 True
        _tools_compatibility_cache[cache_key] = True
        return True
    except Exception as e:
        logger.debug(f"[ToolCompat] 能力表查询异常 ({cache_key}): {e}")

    # 默认认为支持
    _tools_compatibility_cache[cache_key] = True
    return True


def invalidate_tool_compatibility_cache(provider_name: str | None = None) -> None:
    """清理工具兼容性缓存。

    Args:
        provider_name: 指定 provider 则只清理该 provider 的缓存，
                       None 则清理全部。
    """
    if provider_name:
        keys_to_remove = [k for k in _tools_compatibility_cache if k.startswith(f"{provider_name}:")]
        for k in keys_to_remove:
            del _tools_compatibility_cache[k]
        logger.debug(f"[ToolCompat] 已清理 {provider_name} 的兼容性缓存 ({len(keys_to_remove)} 条)")
    else:
        _tools_compatibility_cache.clear()
        logger.debug("[ToolCompat] 已清理全部兼容性缓存")


class ToolOrchestrator:
    """工具编排器。

    在 chat_service.stream_response 与 subagent_executor._run_subagent_loop 中被调用，
    负责"LLM 产生 tool_calls → 执行工具 → 回填 tool message → 继续 LLM 调用"的循环编排。
    """

    def __init__(self, max_iterations: int = 10) -> None:
        """
        Args:
            max_iterations: 单次对话/子 Agent 任务的最大工具调用循环次数
        """
        self.max_iterations = max_iterations

    def get_tools_for_llm(
        self,
        provider_name: str | None = None,
        model: str | None = None,
        *,
        scope: str | None = None,
        platform: str | None = None,
    ) -> list[dict[str, Any]]:
        """获取已注册工具的 OpenAI function calling 格式列表（支持 tier/scope/platform 过滤）

        合并两个来源：
        1. tool_registry 中的内置工具（cli、文件操作、delegate_to_subagent 等）
        2. mcp_manager 中已连接服务器的 MCP 工具（命名格式 `{server}__{tool}`）

        Args:
            provider_name: 目标 LLM provider 名称，用于兼容性检查
            model: 目标模型名称，用于兼容性检查
            scope: 场景归属过滤。
                - None：注入 scope='shared' 工具，排除 scope='platform'（工作台/皮套/桌宠场景）
                - 'platform:{instId}'：注入 scope='shared' 子集 + scope='platform' 且匹配该实例的工具
            platform: 运行平台过滤（'win'/'mac'/'linux'）。None 时自动探测当前平台。

        Returns:
            形如 [{"type": "function", "function": {"name", "description", "parameters"}}] 的列表。
            如果模型不支持工具调用，返回空列表。
        """
        # 工具兼容性检查：如果提供了 provider 和 model，先检查是否支持工具调用
        if provider_name and model:
            cache_key = f"{provider_name}:{model}"
            if cache_key in _tools_compatibility_cache and not _tools_compatibility_cache[cache_key]:
                logger.info(
                    f"[ToolOrchestrator] {provider_name}/{model} 不支持工具调用，返回空工具列表"
                )
                return []
            # 同步检查能力表（不 await，保持方法签名兼容）
            try:
                from app.runtime.provider.llm.capabilities import get_capabilities
                caps = get_capabilities(provider_name, model)
                if model in caps.known_unsupported_models or not caps.supports_tool_calls:
                    _tools_compatibility_cache[cache_key] = False
                    logger.info(
                        f"[ToolOrchestrator] {provider_name}/{model} 能力表声明不支持工具调用"
                    )
                    return []
            except Exception:
                # 能力表未收录该 provider/model 属常规情况，跳过检查走默认流程
                logger.debug(f"[ToolOrchestrator] 能力表查询失败，跳过工具兼容性检查: {cache_key}", exc_info=True)

        # 自动探测当前运行平台
        current_platform = platform or _detect_current_platform()

        # 按 scope + platform 过滤 tool_registry 中的工具
        tools: list[dict[str, Any]] = []
        for tool in tool_registry.list_tools():
            # 平台过滤：工具声明的 platform 集合必须包含当前平台
            if current_platform not in tool.platform:
                continue

            # scope 过滤
            tool_scope = tool.scope or "shared"
            if scope is None:
                # 工作台/皮套/桌宠：仅注入 shared 工具，排除 platform 专用
                if tool_scope != "shared":
                    continue
            elif scope.startswith("platform"):
                # 平台域：注入 shared + 该实例的 platform 工具
                if tool_scope != "shared" and tool_scope != scope and tool_scope != "platform":
                    continue
            # 其他自定义 scope：精确匹配
            elif tool_scope != "shared" and tool_scope != scope:
                continue

            tools.append(_to_llm_function_with_tier(tool))

        # 合并 MCP 工具（延迟导入避免循环依赖）
        try:
            from app.core.tools.mcp.manager import mcp_manager
            tools.extend(mcp_manager.get_all_tools_for_llm())
        except Exception as e:
            logger.debug(f"[ToolOrchestrator] MCP 工具合并跳过: {e}")
        return tools

    async def execute_tool_call(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        """执行单个工具调用

        Args:
            tool_call: LLM 产生的工具调用，形如
                {"id": "...", "type": "function",
                 "function": {"name": "...", "arguments": "..."}}

        Returns:
            tool message，形如
                {"role": "tool", "tool_call_id": "...", "name": "...", "content": "..."}
            content 为 LLM 可读的执行结果文本（失败时含错误说明）
        """
        function_info = tool_call.get("function", {})
        tool_name = function_info.get("name", "")
        tool_call_id = tool_call.get("id", "")
        raw_args = function_info.get("arguments", "{}")

        # arguments 可能是 JSON 字符串或 dict
        if isinstance(raw_args, str):
            try:
                arguments = json.loads(raw_args) if raw_args.strip() else {}
            except json.JSONDecodeError as e:
                logger.warning(
                    f"[ToolOrchestrator] 工具参数 JSON 解析失败: "
                    f"name={tool_name}, args={raw_args!r}, error={e}"
                )
                arguments = {}
        else:
            arguments = raw_args or {}

        logger.info(
            f"[ToolOrchestrator] 执行工具: name={tool_name}, "
            f"call_id={tool_call_id}, args_keys={list(arguments.keys())}"
        )

        # 命令安全守卫：CLI 工具前置白名单/黑名单校验
        from app.security.command_guard import validate_tool_command
        guard_result = validate_tool_command(tool_name, arguments)
        if guard_result is not None:
            return {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": tool_name,
                "content": f"[工具执行失败] {guard_result}",
            }

        # MCP 工具路由：工具名含 `__` 前缀（格式 `{server}__{tool}`）
        if "__" in tool_name:
            try:
                from app.core.tools.mcp.manager import mcp_manager
                parsed = mcp_manager.parse_tool_name(tool_name)
                if parsed is not None:
                    server_name, real_tool_name = parsed
                    logger.info(
                        f"[ToolOrchestrator] MCP 工具调用: server={server_name}, "
                        f"tool={real_tool_name}"
                    )
                    result_text = await mcp_manager.call_tool(
                        server_name, real_tool_name, arguments
                    )
                    logger.info(
                        f"[ToolOrchestrator] MCP 工具完成: name={tool_name}, "
                        f"content_len={len(result_text)}"
                    )
                    return {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": tool_name,
                        "content": result_text,
                    }
            except Exception as e:
                logger.warning(
                    f"[ToolOrchestrator] MCP 工具路由失败: name={tool_name}, error={e}"
                )
                # 降级到 tool_registry 查找

        result = await tool_registry.execute(tool_name, arguments)

        # 构造 LLM 可读的 content：成功时输出 output，失败时输出 error
        if result.success:
            content = result.output or "(工具未返回内容)"
        else:
            content = f"[工具执行失败] {result.error or '未知错误'}"

        logger.info(
            f"[ToolOrchestrator] 工具完成: name={tool_name}, "
            f"success={result.success}, content_len={len(content)}"
        )

        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": content,
        }

    @staticmethod
    def build_assistant_message_with_tool_calls(
        content: str,
        tool_calls: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """构建含 tool_calls 的 assistant 消息（用于回填到对话上下文）

        Args:
            content: assistant 的文本内容（可能为空）
            tool_calls: 工具调用列表，形如
                [{"id": "...", "type": "function",
                  "function": {"name": "...", "arguments": "..."}}]

        Returns:
            assistant message，形如
                {"role": "assistant", "content": "...", "tool_calls": [...]}
        """
        return {
            "role": "assistant",
            "content": content or "",
            "tool_calls": tool_calls,
        }

    def build_default_pipeline(self, extra: dict[str, Any]) -> Any:
        """根据场景组装默认中间件管道。

        中间件组装顺序（参考 deer-flow 位置驱动）：
        1. MemoryAccessMiddleware（before_agent 设 contextvar）
        2. ToolFilterMiddleware（before_agent 过滤工具）
        3. SubagentCancelMiddleware（before_model 检查取消，仅 subagent）
        4. LoopGuardMiddleware（after_model 检测循环边界）
        5. SSEEmitMiddleware（after_model/after_tool_call 发射 SSE，仅流式）
        6. ToolExecutionMiddleware（wrap_tool_call 执行工具）
        7. SpecialToolMiddleware（wrap_tool_call 处理特殊工具，仅 chat 流式）
        8. UsageTrackMiddleware（after_agent 记录 usage）

        Args:
            extra: 调用方配置字典，识别以下键：
                - scene: "chat" / "subagent" / "group"（默认 "chat"）
                - is_stream: 是否流式模式（默认 True）
                - max_iterations: 覆盖编排器的 max_iterations（可选）

        Returns:
            MiddlewarePipeline 实例
        """
        from app.core.agents.middleware.builtin import (
            LoopGuardMiddleware,
            MemoryAccessMiddleware,
            SpecialToolMiddleware,
            SSEEmitMiddleware,
            SubagentCancelMiddleware,
            ToolExecutionMiddleware,
            ToolFilterMiddleware,
            UsageTrackMiddleware,
        )
        from app.core.agents.middleware.pipeline import MiddlewarePipeline

        scene = extra.get("scene", "chat")
        is_stream = extra.get("is_stream", True)
        max_iter = extra.get("max_iterations", self.max_iterations)

        middlewares: list[Any] = [
            MemoryAccessMiddleware(),
            ToolFilterMiddleware(),
        ]

        if scene == "subagent":
            middlewares.append(SubagentCancelMiddleware())

        middlewares.append(LoopGuardMiddleware(max_iterations=max_iter))

        if is_stream:
            middlewares.append(SSEEmitMiddleware())

        middlewares.append(ToolExecutionMiddleware())

        if scene == "chat" and is_stream:
            middlewares.append(SpecialToolMiddleware())

        middlewares.append(UsageTrackMiddleware())

        return MiddlewarePipeline(middlewares)

    def create_runner(self, extra: dict[str, Any]) -> Any:
        """创建带默认管道的 AgentRunner。

        Args:
            extra: 调用方配置字典（同 build_default_pipeline，额外支持 execute_fn / hook_registry）

        Returns:
            AgentRunner 实例
        """
        from app.core.agents.middleware.runner import AgentRunner

        pipeline = self.build_default_pipeline(extra)
        max_iter = extra.get("max_iterations", self.max_iterations)
        return AgentRunner(
            pipeline=pipeline,
            max_iterations=max_iter,
            execute_fn=extra.get("execute_fn"),
            hook_registry=extra.get("hook_registry"),
        )


# 全局单例
tool_orchestrator = ToolOrchestrator()
