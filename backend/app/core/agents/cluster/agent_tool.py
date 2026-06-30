"""LuomiNest Agent 间调用工具（OpenAI 兼容 API 自回调模式）。

参考 综合调查.md §5.1 与 claude-code-src 的 AgentTool 设计：
Agent A 通过 HTTP 回调本服务的 `/chat/completions` 接口，将 `agent_id` 作为 model 参数，
服务端路由到 Agent B 的配置执行其对话流程。

核心机制：
1. 通过 httpx.AsyncClient 调用本服务 REST API（不走外部网络）
2. 递归深度通过 contextvars 跟踪，防止 Agent A→B→A 无限循环
3. 超过 max_depth（默认 3）拒绝调用，返回中文友好提示
4. is_sub_agent 标志让 chat 端点跳过记忆写入，避免污染主 Agent 记忆

品牌化命名：LuomiNestAgentCallTool / _luominest_agent_call_depth。
"""
import contextvars
import json
from typing import Any

import httpx
from loguru import logger

from app.core.config import settings
from app.core.tools.registry import ToolBase, ToolResult


# 递归深度上下文变量：在 chat 端点处理 is_sub_agent 请求时设置，
# 使 agent_tool_call 工具能读取当前深度并 +1 后传递给下一层
_luominest_agent_call_depth: contextvars.ContextVar[int] = contextvars.ContextVar(
    "luominest_agent_call_depth",
    default=0,
)

# 最大递归深度（Agent A→B→C→D 最多 4 层链式调用）
_MAX_AGENT_CALL_DEPTH = 3


def get_luominest_agent_call_depth() -> int:
    """读取当前异步上下文的 Agent 调用深度"""
    return _luominest_agent_call_depth.get()


def set_luominest_agent_call_depth(depth: int):
    """设置当前异步上下文的 Agent 调用深度

    由 chat 端点在处理 is_sub_agent=true 的请求时调用，
    使该请求工具循环中的 agent_tool_call 能读取正确深度。
    """
    return _luominest_agent_call_depth.set(depth)


def reset_luominest_agent_call_depth(token) -> None:
    """重置 Agent 调用深度到之前的状态"""
    _luominest_agent_call_depth.reset(token)


class LuomiNestAgentCallTool(ToolBase):
    """Agent 间调用工具（OpenAI 兼容 API 自回调）

    主 Agent 通过本工具调用同服务内的其他 Agent。
    目标 Agent 拥有独立上下文，执行完成后返回结果摘要。
    """

    @property
    def name(self) -> str:
        return "agent_tool_call"

    @property
    def description(self) -> str:
        return (
            "调用同服务内的其他 Agent 协助完成任务。适用于："
            "1. 需要其他 Agent 专长（如创意、数据、审核）的任务；"
            "2. 需要独立 Agent 视角的二次确认；"
            "3. 多 Agent 协同的特定子任务。"
            "目标 Agent 拥有独立上下文，执行完成后返回结果。"
            "支持递归调用（最大深度 3）。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "目标 Agent 的 ID（必填）",
                },
                "query": {
                    "type": "string",
                    "description": "调用目标 Agent 的查询/任务描述（必填，应清晰具体）",
                },
                "consensus_content": {
                    "type": "string",
                    "description": "共识规范（可选）。传递给目标 Agent 的协同规范，确保多 Agent 协同一致。",
                    "default": "",
                },
            },
            "required": ["agent_id", "query"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        agent_id = arguments.get("agent_id", "").strip()
        if not agent_id:
            return ToolResult.fail("缺少 agent_id 参数")

        query = arguments.get("query", "").strip()
        if not query:
            return ToolResult.fail("缺少 query 参数")

        consensus_content = arguments.get("consensus_content", "") or ""

        # 递归深度守卫：读取当前深度，+1，超限拒绝
        current_depth = _luominest_agent_call_depth.get()
        new_depth = current_depth + 1
        if new_depth > _MAX_AGENT_CALL_DEPTH:
            depth_msg = (
                f"已达到最大 Agent 调用深度 ({_MAX_AGENT_CALL_DEPTH})，"
                f"无法继续递归调用其他 Agent。请直接使用工具完成任务。"
            )
            logger.warning(f"[AgentToolCall] 递归深度超限: {new_depth}/{_MAX_AGENT_CALL_DEPTH}")
            return ToolResult.fail(depth_msg)

        # 构建请求体：consensus_content 拼接到 query 前面作为上下文提示
        if consensus_content:
            full_query = (
                f"【Luminous 共识规范】\n{consensus_content}\n\n"
                f"【任务】\n{query}"
            )
        else:
            full_query = query

        # 流式调用：目标 Agent 需要工具循环能力，stream=True 走 stream_chat 工具循环路径
        request_body = {
            "messages": [{"role": "user", "content": full_query}],
            "stream": True,
            "agent_id": agent_id,
            "is_sub_agent": True,
            "agent_depth": new_depth,
            "disable_tools": ["agent_tool_call", "delegate_to_subagent", "start_collaboration"],
        }

        base_url = settings.APP_SELF_BASE_URL.rstrip("/")
        url = f"{base_url}/api/v1/chat/completions"

        logger.info(
            f"[AgentToolCall] 调用 Agent: target={agent_id}, "
            f"depth={new_depth}/{_MAX_AGENT_CALL_DEPTH}, "
            f"query_len={len(query)}, has_consensus={bool(consensus_content)}"
        )

        try:
            result_content = ""
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", url, json=request_body) as response:
                    if response.status_code != 200:
                        error_bytes = await response.aread()
                        error_detail = ""
                        try:
                            error_data = json.loads(error_bytes)
                            error_detail = error_data.get("detail") or error_data.get("error", {}).get("message", "")
                        except Exception:
                            error_detail = error_bytes.decode("utf-8", errors="ignore")[:200]
                        fail_msg = (
                            f"调用 Agent 失败（HTTP {response.status_code}）："
                            f"{error_detail or '目标 Agent 不可用'}"
                        )
                        logger.error(f"[AgentToolCall] HTTP 错误: {response.status_code}, detail={error_detail}")
                        return ToolResult.fail(fail_msg)

                    # 消费 SSE 流，累积 content 字段
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data = line[6:]
                        if data.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        content = chunk.get("content") or ""
                        if content:
                            result_content += content
                        if chunk.get("done"):
                            break

            if not result_content:
                return ToolResult.fail("目标 Agent 未返回有效内容")

            logger.info(
                f"[AgentToolCall] Agent 调用完成: target={agent_id}, "
                f"result_len={len(result_content)}"
            )
            return ToolResult.ok(
                result_content,
                metadata={
                    "target_agent_id": agent_id,
                    "depth": new_depth,
                    "result_len": len(result_content),
                },
            )

        except httpx.TimeoutException:
            timeout_msg = "调用 Agent 超时（120秒），目标 Agent 可能响应过慢或不可用"
            logger.error(f"[AgentToolCall] 超时: target={agent_id}")
            return ToolResult.fail(timeout_msg)
        except httpx.ConnectError as e:
            connect_msg = f"无法连接到 Agent 服务：{e}"
            logger.error(f"[AgentToolCall] 连接失败: target={agent_id}, error={e}")
            return ToolResult.fail(connect_msg)
        except Exception as e:
            logger.error(f"[AgentToolCall] 异常: target={agent_id}, error={e}", exc_info=True)
            return ToolResult.fail(f"调用 Agent 执行失败：{e}")
