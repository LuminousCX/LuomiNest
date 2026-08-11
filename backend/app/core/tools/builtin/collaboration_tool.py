"""LuomiNest 工作台多 Agent 协作工具。

主 Agent 通过本工具启动多 Agent 协作流程。触发后：
1. 创建临时 group（不持久化），成员 = 指定 Agent 或所有可用 Agent
2. 若未提供 consensus_content，调度员自动生成简短共识规范
3. 调用 agent_orchestrator.orchestrate_stream 执行协作
4. 将协作事件通过 subagent_event 通道转发到前端 SSE
5. 返回最终综合结果

设计原则（参考 综合调查.md §5.3 与 deer-flow 的协作模式）：
- 主 Agent 自动触发，前端零改动（复用 subagent_event UI）
- 临时 group 以 "temp_" 前缀标识，orchestrator 跳过持久化
- consensus_content 注入工人系统提示词，确保多 Agent 协同一致

品牌化命名：LuomiNestStartCollaborationTool。
"""
import uuid
from typing import Any

from loguru import logger

from app.core.tools.registry import ToolBase, ToolResult
from app.infrastructure.database.json_store import agents_store


class LuomiNestStartCollaborationTool(ToolBase):
    """启动多 Agent 协作工具

    主 Agent 通过本工具将复杂任务分派给多个 Agent 协同完成。
    调度员自动分析任务、分配子任务、综合结果。
    """

    @property
    def name(self) -> str:
        return "start_collaboration"

    @property
    def description(self) -> str:
        return (
            "启动多 Agent 协作流程，将复杂任务分派给多个 Agent 协同完成。适用于："
            "1. 需要多角色协作的复杂任务（如策划、分析、审核）；"
            "2. 需要多视角综合的决策任务；"
            "3. 单个 Agent 难以独立完成的大型任务。"
            "调度员会自动分析任务、分配子任务、综合结果。"
            "可选指定参与的 Agent 列表和共识规范。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "需要多 Agent 协作完成的任务描述（必填，应清晰完整）",
                },
                "agent_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "参与协作的 Agent ID 列表（可选）。为空时使用所有可用 Agent。",
                    "default": [],
                },
                "consensus_content": {
                    "type": "string",
                    "description": "共识规范（可选）。确保多 Agent 协同一致的规范。为空时调度员自动生成。",
                    "default": "",
                },
            },
            "required": ["task"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        task = arguments.get("task", "").strip()
        if not task:
            return ToolResult.fail("缺少 task 参数")

        agent_ids = arguments.get("agent_ids", []) or []
        consensus_content = arguments.get("consensus_content", "") or ""

        # 延迟导入避免循环依赖（agents_store 已在模块级导入）
        try:
            from app.domains.social.agent_orchestrator import agent_orchestrator
            from app.core.tools.builtin.subagent_tool import emit_luominest_subagent_event
        except Exception as e:
            logger.error(f"[StartCollaboration] 导入依赖失败: {e}")
            return ToolResult.fail(f"协作组件不可用: {e}")

        # 1. 构建临时 group（不持久化）
        temp_group = await self._build_temp_group(agent_ids)
        if not temp_group.get("members"):
            return ToolResult.fail("没有可用的 Agent 参与协作，请先创建 Agent")

        # 2. 自动生成 consensus_content（若未提供）
        if not consensus_content:
            try:
                consensus_content = await self._generate_consensus(task)
                logger.info(f"[StartCollaboration] 自动生成共识规范: len={len(consensus_content)}")
            except Exception as e:
                logger.warning(f"[StartCollaboration] 共识规范生成失败，使用空值: {e}")
                consensus_content = ""

        logger.info(
            f"[StartCollaboration] 启动协作: task_len={len(task)}, "
            f"members={len(temp_group['members'])}, "
            f"has_consensus={bool(consensus_content)}"
        )

        # 3. 调用 orchestrator 并转发事件到 SSE
        final_result = ""
        try:
            async for event in agent_orchestrator.orchestrate_stream(
                group_id=temp_group["id"],
                user_message=task,
                sender_id="luominest_main_agent",
                consensus_content=consensus_content or None,
                group=temp_group,
            ):
                # 转发协作事件到前端 SSE（复用 subagent_event 通道）
                try:
                    await emit_luominest_subagent_event({
                        "type": "collaboration",
                        "event": event,
                    })
                except Exception as ev_err:
                    logger.debug(f"[StartCollaboration] 事件转发失败: {ev_err}")

                event_type = event.get("type", "")
                if event_type in ("final_result", "direct_response"):
                    final_result = event.get("data", {}).get("content", "")
                elif event_type == "error":
                    error_msg = event.get("data", {}).get("message", "协作过程出错")
                    return ToolResult.fail(error_msg)

        except Exception as e:
            logger.error(f"[StartCollaboration] 协作执行异常: {e}", exc_info=True)
            return ToolResult.fail(f"协作执行失败: {e}")

        if not final_result:
            return ToolResult.fail("协作完成但未产生有效结果")

        logger.info(f"[StartCollaboration] 协作完成: result_len={len(final_result)}")
        return ToolResult.ok(
            final_result,
            metadata={
                "task_len": len(task),
                "members": len(temp_group["members"]),
                "result_len": len(final_result),
            },
        )

    async def _build_temp_group(self, agent_ids: list[str]) -> dict:
        """构建临时协作 group（不持久化到 groups_store）"""
        group_id = f"temp_{uuid.uuid4().hex[:8]}"
        members: list[dict] = []

        if agent_ids:
            for aid in agent_ids:
                agent = agents_store.get(aid)
                if agent and agent.get("is_active", True):
                    members.append({
                        "agent_id": aid,
                        "name": agent.get("name", "Agent"),
                        "type": "agent",
                        "role": "成员",
                        "is_active": True,
                    })
        else:
            all_agents = await agents_store.all_async()
            for agent in all_agents:
                if agent.get("is_active", True):
                    members.append({
                        "agent_id": agent.get("id", ""),
                        "name": agent.get("name", "Agent"),
                        "type": "agent",
                        "role": "成员",
                        "is_active": True,
                    })

        # 第一个成员作为调度员
        if members:
            members[0]["role"] = "调度员"

        return {
            "id": group_id,
            "name": "工作台协作",
            "description": "主 Agent 触发的临时多 Agent 协作",
            "type": "collaboration",
            "members": members,
            "member_count": len(members),
            "messages": [],
        }

    async def _generate_consensus(self, task: str) -> str:
        """调度员自动生成简短共识规范"""
        from app.runtime.provider.llm.adapter import llm_adapter

        messages = [
            {
                "role": "system",
                "content": (
                    "你是 LuomiNest 协作调度员。根据任务生成简短的共识规范（2-3 句话），"
                    "确保多 Agent 协同时目标一致、分工明确、风格统一。"
                    "直接输出规范内容，不要多余解释。"
                ),
            },
            {"role": "user", "content": f"任务：{task}\n\n请生成共识规范："},
        ]
        result = await llm_adapter.chat(
            messages=messages,
            temperature=0.3,
            max_tokens=200,
        )
        return (result.content if hasattr(result, "content") else str(result)).strip()
