import asyncio
import json
import re
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from loguru import logger

from app.infrastructure.database.json_store import groups_store, agents_store
from app.runtime.provider.llm.adapter import llm_adapter
from app.domains.social.agent_role_registry import AgentRoleRegistry


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CollaborationPhase(str, Enum):
    ANALYZING = "analyzing"
    DISPATCHING = "dispatching"
    EXECUTING = "executing"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SubTask:
    task_id: str
    role_id: str
    agent_id: str | None
    description: str
    input_content: str
    depends_on: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: str | None = None
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


@dataclass
class CollaborationSession:
    session_id: str
    group_id: str
    user_message: str
    phase: CollaborationPhase = CollaborationPhase.ANALYZING
    plan: str | None = None
    sub_tasks: list[SubTask] = field(default_factory=list)
    final_result: str | None = None
    coordinator_response: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None


class MCPInterface:
    async def call_tool(self, server_name: str, tool_name: str, arguments: dict) -> Any:
        logger.info(f"[MCPInterface] Reserved: call_tool({server_name}, {tool_name})")
        raise NotImplementedError("MCP tool calling is reserved for future implementation")

    async def list_tools(self, server_name: str) -> list[dict]:
        logger.info(f"[MCPInterface] Reserved: list_tools({server_name})")
        return []


class MemoryInterface:
    async def store(self, agent_id: str, content: str, metadata: dict | None = None) -> str:
        logger.info(f"[MemoryInterface] Reserved: store({agent_id})")
        raise NotImplementedError("Memory storage is reserved for future implementation")

    async def recall(self, agent_id: str, query: str, top_k: int = 5) -> list[dict]:
        logger.info(f"[MemoryInterface] Reserved: recall({agent_id})")
        return []

    async def update_profile(self, agent_id: str, updates: dict) -> None:
        logger.info(f"[MemoryInterface] Reserved: update_profile({agent_id})")
        raise NotImplementedError("Memory profile update is reserved for future implementation")


class SkillInterface:
    async def execute(self, skill_name: str, arguments: dict, agent_id: str | None = None) -> Any:
        logger.info(f"[SkillInterface] Reserved: execute({skill_name})")
        raise NotImplementedError("Skill execution is reserved for future implementation")

    async def list_skills(self) -> list[dict]:
        logger.info("[SkillInterface] Reserved: list_skills()")
        return []


class ToolCallingInterface:
    async def call(self, tool_name: str, arguments: dict, agent_id: str | None = None) -> Any:
        logger.info(f"[ToolCallingInterface] Reserved: call({tool_name})")
        raise NotImplementedError("Tool calling is reserved for future implementation")

    async def list_available_tools(self, agent_id: str | None = None) -> list[dict]:
        logger.info(f"[ToolCallingInterface] Reserved: list_available_tools({agent_id})")
        return []


mcp_interface = MCPInterface()
memory_interface = MemoryInterface()
skill_interface = SkillInterface()
tool_calling_interface = ToolCallingInterface()


def _extract_json_plan(text: str) -> dict | None:
    patterns = [
        r'```json\s*([\s\S]*?)\s*```',
        r'```\s*([\s\S]*?)\s*```',
        r'(\{[\s\S]*"tasks"[\s\S]*\})',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            try:
                parsed = json.loads(match.strip())
                if isinstance(parsed, dict) and "tasks" in parsed:
                    return parsed
            except json.JSONDecodeError:
                continue
    return None


def _find_agent_for_role(group: dict, role_id: str) -> dict | None:
    members = group.get("members", [])
    normalized_role = role_id.lower().strip()
    role_tokens = set(re.split(r'[-_\s]+', normalized_role))
    for member in members:
        if member.get("type") != "agent":
            continue
        member_role = member.get("role", "").lower().strip()
        if normalized_role == member_role:
            agent = agents_store.get(member.get("agent_id", ""))
            if agent and agent.get("is_active", True):
                return agent
        member_tokens = set(re.split(r'[-_\s]+', member_role))
        if role_tokens & member_tokens:
            agent = agents_store.get(member.get("agent_id", ""))
            if agent and agent.get("is_active", True):
                return agent
    return None


def _find_coordinator_agent(group: dict) -> dict | None:
    members = group.get("members", [])
    for member in members:
        if member.get("type") != "agent":
            continue
        member_role = member.get("role", "").lower()
        if "调度" in member_role or "协调" in member_role or "coordinator" in member_role:
            agent = agents_store.get(member.get("agent_id", ""))
            if agent and agent.get("is_active", True):
                return agent
    ai_members = [m for m in members if m.get("type") == "agent"]
    if ai_members:
        first_member = ai_members[0]
        agent = agents_store.get(first_member.get("agent_id", ""))
        if agent and agent.get("is_active", True):
            return agent
    return None


class AgentOrchestrator:
    """多 Agent 协作编排器，负责任务分析、子任务调度、执行和结果综合。"""

    def __init__(self):
        self._active_sessions: dict[str, CollaborationSession] = {}
        self._save_locks: dict[str, asyncio.Lock] = {}

    def _resolve_provider(self, agent: dict) -> str:
        agent_provider = agent.get("provider", "")
        if agent_provider and agent_provider in llm_adapter.providers:
            return agent_provider
        if llm_adapter.default_provider in llm_adapter.providers:
            return llm_adapter.default_provider
        for provider_key in llm_adapter.providers:
            return provider_key
        return ""

    def _resolve_model(self, agent: dict, provider_name: str) -> str:
        agent_model = agent.get("model", "")
        if agent_model:
            return agent_model
        provider = llm_adapter.providers.get(provider_name)
        if provider:
            return provider.default_model
        return ""

    async def orchestrate(
        self,
        group_id: str,
        user_message: str,
        sender_id: str = "user",
    ) -> CollaborationSession:
        """执行一次完整的多 Agent 协作流程（非流式）。

        Args:
            group_id: 目标群组 ID
            user_message: 用户发送的消息内容
            sender_id: 发送者 ID，默认为 "user"

        Returns:
            CollaborationSession: 包含协作全过程的会话对象
        """
        group = groups_store.get(group_id)
        if not group:
            raise ValueError(f"Group {group_id} not found")

        session = CollaborationSession(
            session_id=str(uuid.uuid4()),
            group_id=group_id,
            user_message=user_message,
        )
        self._active_sessions[session.session_id] = session

        try:
            coordinator = _find_coordinator_agent(group)
            if not coordinator:
                session.phase = CollaborationPhase.FAILED
                session.final_result = "群组中没有可用的 Agent，请先添加 Agent 到群组"
                return session

            session.phase = CollaborationPhase.ANALYZING
            plan = await self._analyze_with_coordinator(coordinator, group, user_message, session)

            if not plan:
                session.phase = CollaborationPhase.COMPLETED
                session.final_result = session.coordinator_response or "无法处理该请求"
                await self._save_messages(group, session)
                return session

            session.plan = plan.get("plan", "")
            session.phase = CollaborationPhase.DISPATCHING

            sub_tasks = self._create_sub_tasks(plan, group, session)
            if not sub_tasks:
                session.phase = CollaborationPhase.COMPLETED
                session.final_result = session.coordinator_response or "无法创建子任务"
                await self._save_messages(group, session)
                return session

            session.sub_tasks = sub_tasks
            session.phase = CollaborationPhase.EXECUTING

            await self._execute_sub_tasks(sub_tasks, group, session)

            session.phase = CollaborationPhase.SYNTHESIZING
            final_result = await self._synthesize_results(coordinator, group, session)
            session.final_result = final_result
            session.phase = CollaborationPhase.COMPLETED
            session.completed_at = datetime.now(timezone.utc).isoformat()

            await self._save_messages(group, session)

        except Exception as e:
            logger.error(f"[Orchestrator] Session {session.session_id} failed: {e}")
            session.phase = CollaborationPhase.FAILED
            session.final_result = f"协作过程出错: {str(e)}"
            session.completed_at = datetime.now(timezone.utc).isoformat()

        return session

    async def orchestrate_stream(
        self,
        group_id: str,
        user_message: str,
        sender_id: str = "user",
    ) -> AsyncIterator[dict]:
        """执行一次多 Agent 协作流程（流式），逐步 yield 事件。

        Args:
            group_id: 目标群组 ID
            user_message: 用户发送的消息内容
            sender_id: 发送者 ID，默认为 "user"

        Returns:
            AsyncIterator[dict]: 事件流，包含 session_start、phase_change、task_started 等事件
        """
        group = groups_store.get(group_id)
        if not group:
            yield {"type": "error", "data": {"message": f"Group {group_id} not found"}}
            return

        session = CollaborationSession(
            session_id=str(uuid.uuid4()),
            group_id=group_id,
            user_message=user_message,
        )
        self._active_sessions[session.session_id] = session

        try:
            yield {
                "type": "session_start",
                "data": {
                    "session_id": session.session_id,
                    "phase": "analyzing",
                },
            }

            coordinator = _find_coordinator_agent(group)
            if not coordinator:
                yield {
                    "type": "error",
                    "data": {"message": "群组中没有可用的 Agent，请先添加 Agent 到群组"},
                }
                return

            yield {
                "type": "phase_change",
                "data": {
                    "phase": "analyzing",
                    "agent_id": coordinator["id"],
                    "agent_name": coordinator["name"],
                    "message": f"{coordinator['name']} 正在分析任务...",
                },
            }

            plan = await self._analyze_with_coordinator(coordinator, group, user_message, session)

            if not plan:
                session.phase = CollaborationPhase.COMPLETED
                session.final_result = session.coordinator_response or "无法处理该请求"
                yield {
                    "type": "direct_response",
                    "data": {
                        "agent_id": coordinator["id"],
                        "agent_name": coordinator["name"],
                        "content": session.coordinator_response,
                    },
                }
                yield {"type": "session_end", "data": {"session_id": session.session_id}}
                await self._save_messages(group, session)
                return

            session.plan = plan.get("plan", "")
            yield {
                "type": "plan_created",
                "data": {
                    "plan": session.plan,
                    "task_count": len(plan.get("tasks", [])),
                    "execution_order": plan.get("execution_order", "parallel"),
                },
            }

            sub_tasks = self._create_sub_tasks(plan, group, session)
            if not sub_tasks:
                session.phase = CollaborationPhase.COMPLETED
                session.final_result = session.coordinator_response or "无法创建子任务"
                yield {
                    "type": "direct_response",
                    "data": {
                        "agent_id": coordinator["id"],
                        "agent_name": coordinator["name"],
                        "content": session.final_result,
                    },
                }
                yield {"type": "session_end", "data": {"session_id": session.session_id}}
                await self._save_messages(group, session)
                return

            session.sub_tasks = sub_tasks
            session.phase = CollaborationPhase.EXECUTING

            yield {
                "type": "phase_change",
                "data": {
                    "phase": "executing",
                    "message": "正在执行子任务...",
                },
            }

            completed_ids: set[str] = set()
            max_iterations = len(sub_tasks) + 1
            iteration = 0

            while len(completed_ids) < len(sub_tasks) and iteration < max_iterations:
                iteration += 1
                ready = self._resolve_ready_tasks(sub_tasks, completed_ids)

                if not ready:
                    stuck = [t for t in sub_tasks if t.task_id not in completed_ids and t.status != TaskStatus.FAILED]
                    if stuck:
                        for t in stuck:
                            t.status = TaskStatus.FAILED
                            t.error = "Unresolvable dependency"
                            t.completed_at = datetime.now(timezone.utc).isoformat()
                            completed_ids.add(t.task_id)
                    break

                for task in ready:
                    async for event in self._execute_single_task_stream(task, group, session):
                        yield event

                for t in ready:
                    completed_ids.add(t.task_id)

            session.phase = CollaborationPhase.SYNTHESIZING
            yield {
                "type": "phase_change",
                "data": {
                    "phase": "synthesizing",
                    "agent_id": coordinator["id"],
                    "agent_name": coordinator["name"],
                    "message": f"{coordinator['name']} 正在综合结果...",
                },
            }

            final_result = await self._synthesize_results(coordinator, group, session)
            session.final_result = final_result
            session.phase = CollaborationPhase.COMPLETED
            session.completed_at = datetime.now(timezone.utc).isoformat()

            yield {
                "type": "final_result",
                "data": {
                    "content": final_result,
                    "agent_id": coordinator["id"],
                    "agent_name": coordinator["name"],
                },
            }

            yield {"type": "session_end", "data": {"session_id": session.session_id}}
            await self._save_messages(group, session)

        except Exception as e:
            logger.error(f"[Orchestrator] Stream session {session.session_id} failed: {e}")
            session.phase = CollaborationPhase.FAILED
            session.final_result = f"协作过程出错: {str(e)}"
            yield {
                "type": "error",
                "data": {"message": str(e)},
            }

    async def _analyze_with_coordinator(
        self,
        coordinator: dict,
        group: dict,
        user_message: str,
        session: CollaborationSession,
    ) -> dict | None:
        coordinator_prompt = AgentRoleRegistry.build_coordinator_prompt(coordinator["name"])

        group_context = self._build_group_context(group)
        messages = [
            {"role": "system", "content": coordinator_prompt},
            {"role": "user", "content": f"群组上下文:\n{group_context}\n\n用户消息: {user_message}"},
        ]

        provider = self._resolve_provider(coordinator)
        model = self._resolve_model(coordinator, provider)

        logger.info(f"[Orchestrator] Coordinator calling LLM: provider={provider}, model={model}")

        result = await llm_adapter.chat(
            messages=messages,
            provider_name=provider,
            model=model,
            temperature=0.3,
            max_tokens=1500,
        )

        response_content = result.content if hasattr(result, "content") else str(result)
        session.coordinator_response = response_content

        plan = _extract_json_plan(response_content)
        if plan:
            logger.info(f"[Orchestrator] Coordinator created plan with {len(plan.get('tasks', []))} tasks")
        else:
            logger.info("[Orchestrator] Coordinator responded directly without task plan")

        return plan

    def _build_group_context(self, group: dict) -> str:
        members_info = []
        for m in group.get("members", []):
            if m.get("type") == "agent":
                agent = agents_store.get(m.get("agent_id", ""))
                if agent:
                    members_info.append(f"- {agent['name']} (角色: {m.get('role', '成员')}, 描述: {agent.get('description', '')})")
        members_text = "\n".join(members_info) if members_info else "暂无成员"
        return f"群组: {group.get('name', '')}\n描述: {group.get('description', '')}\n成员:\n{members_text}"

    def _create_sub_tasks(
        self,
        plan: dict,
        group: dict,
        session: CollaborationSession,
    ) -> list[SubTask]:
        tasks = plan.get("tasks", [])
        sub_tasks = []

        for i, task_def in enumerate(tasks):
            role_id = task_def.get("role_id", "")
            description = task_def.get("description", "")
            input_content = task_def.get("input", "")
            depends_on = task_def.get("depends_on", [])

            role = AgentRoleRegistry.get_role(role_id)
            if not role:
                logger.warning(f"[Orchestrator] Unknown role: {role_id}, skipping task")
                continue

            agent = _find_agent_for_role(group, role_id)

            sub_task = SubTask(
                task_id=f"task_{i}",
                role_id=role_id,
                agent_id=agent["id"] if agent else None,
                description=description,
                input_content=input_content,
                depends_on=depends_on,
            )
            sub_tasks.append(sub_task)

        return sub_tasks

    def _resolve_ready_tasks(self, sub_tasks: list[SubTask], completed_ids: set[str]) -> list[SubTask]:
        return [
            t for t in sub_tasks
            if t.task_id not in completed_ids
            and t.status not in (TaskStatus.RUNNING, TaskStatus.COMPLETED, TaskStatus.FAILED)
            and all(dep in completed_ids for dep in t.depends_on)
        ]

    async def _execute_sub_tasks(
        self,
        sub_tasks: list[SubTask],
        group: dict,
        session: CollaborationSession,
    ) -> None:
        completed_ids: set[str] = set()
        max_iterations = len(sub_tasks) + 1
        iteration = 0

        while len(completed_ids) < len(sub_tasks) and iteration < max_iterations:
            iteration += 1
            ready = self._resolve_ready_tasks(sub_tasks, completed_ids)

            if not ready:
                stuck = [t for t in sub_tasks if t.task_id not in completed_ids and t.status != TaskStatus.FAILED]
                if stuck:
                    for t in stuck:
                        t.status = TaskStatus.FAILED
                        t.error = "Unresolvable dependency"
                        t.completed_at = datetime.now(timezone.utc).isoformat()
                        completed_ids.add(t.task_id)
                break

            if len(ready) == 1:
                await self._execute_single_task(ready[0], group, session)
            else:
                results = await asyncio.gather(*[
                    self._execute_single_task(t, group, session)
                    for t in ready
                ], return_exceptions=True)
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"[Orchestrator] Task {ready[i].task_id} gather error: {result}")

            for t in ready:
                completed_ids.add(t.task_id)

    async def _execute_single_task(
        self,
        task: SubTask,
        group: dict,
        session: CollaborationSession,
    ) -> None:
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc).isoformat()

        try:
            agent = None
            if task.agent_id:
                agent = agents_store.get(task.agent_id)

            if not agent:
                coordinator = _find_coordinator_agent(group)
                for m in group.get("members", []):
                    if m.get("type") == "agent" and m.get("agent_id") != (coordinator["id"] if coordinator else ""):
                        a = agents_store.get(m.get("agent_id", ""))
                        if a and a.get("is_active", True):
                            agent = a
                            break

            if not agent:
                task.status = TaskStatus.FAILED
                task.error = f"No available agent for role {task.role_id}"
                return

            role = AgentRoleRegistry.get_role(task.role_id)
            role_prompt = ""
            if role:
                role_prompt = AgentRoleRegistry.build_agent_prompt(task.role_id, agent["name"]) or ""

            member_info = None
            for m in group.get("members", []):
                if m.get("agent_id") == agent["id"]:
                    member_info = m
                    break

            system_prompt = self._build_worker_prompt(agent, member_info, group, role_prompt)

            context_parts = [f"用户原始需求: {session.user_message}"]
            if session.plan:
                context_parts.append(f"执行计划: {session.plan}")
            context_parts.append(f"你的具体任务: {task.description}")
            context_parts.append(f"任务输入: {task.input_content}")

            for dep_id in task.depends_on:
                dep_task = next((t for t in session.sub_tasks if t.task_id == dep_id), None)
                if dep_task and dep_task.result:
                    context_parts.append(f"前置任务 {dep_id} 的结果: {dep_task.result}")

            context = "\n\n".join(context_parts)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context},
            ]

            provider = self._resolve_provider(agent)
            model = self._resolve_model(agent, provider)

            logger.info(f"[Orchestrator] Task {task.task_id} calling LLM: agent={agent['name']}, provider={provider}, model={model}")

            result = await llm_adapter.chat(
                messages=messages,
                provider_name=provider,
                model=model,
                temperature=0.5,
                max_tokens=800,
            )

            task.result = result.content if hasattr(result, "content") else str(result)
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc).isoformat()

        except Exception as e:
            logger.error(f"[Orchestrator] Task {task.task_id} failed: {e}")
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now(timezone.utc).isoformat()

    async def _execute_single_task_stream(
        self,
        task: SubTask,
        group: dict,
        session: CollaborationSession,
    ) -> AsyncIterator[dict]:
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc).isoformat()

        yield {
            "type": "task_started",
            "data": {
                "task_id": task.task_id,
                "role_id": task.role_id,
                "description": task.description,
                "agent_id": task.agent_id,
            },
        }

        try:
            agent = None
            if task.agent_id:
                agent = agents_store.get(task.agent_id)

            if not agent:
                for m in group.get("members", []):
                    if m.get("type") == "agent":
                        a = agents_store.get(m.get("agent_id", ""))
                        if a and a.get("is_active", True):
                            agent = a
                            break

            if not agent:
                task.status = TaskStatus.FAILED
                task.error = f"No available agent for role {task.role_id}"
                yield {
                    "type": "task_failed",
                    "data": {
                        "task_id": task.task_id,
                        "error": task.error,
                    },
                }
                return

            agent_name = agent.get("name", "Agent")
            yield {
                "type": "task_agent_assigned",
                "data": {
                    "task_id": task.task_id,
                    "agent_id": agent["id"],
                    "agent_name": agent_name,
                },
            }

            role = AgentRoleRegistry.get_role(task.role_id)
            role_prompt = ""
            if role:
                role_prompt = AgentRoleRegistry.build_agent_prompt(task.role_id, agent_name) or ""

            member_info = None
            for m in group.get("members", []):
                if m.get("agent_id") == agent["id"]:
                    member_info = m
                    break

            system_prompt = self._build_worker_prompt(agent, member_info, group, role_prompt)

            context_parts = [f"用户原始需求: {session.user_message}"]
            if session.plan:
                context_parts.append(f"执行计划: {session.plan}")
            context_parts.append(f"你的具体任务: {task.description}")
            context_parts.append(f"任务输入: {task.input_content}")

            for dep_id in task.depends_on:
                dep_task = next((t for t in session.sub_tasks if t.task_id == dep_id), None)
                if dep_task and dep_task.result:
                    context_parts.append(f"前置任务 {dep_id} 的结果: {dep_task.result}")

            context = "\n\n".join(context_parts)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context},
            ]

            provider = self._resolve_provider(agent)
            model = self._resolve_model(agent, provider)

            logger.info(f"[Orchestrator] Stream task {task.task_id}: agent={agent_name}, provider={provider}, model={model}")

            result = await llm_adapter.chat(
                messages=messages,
                provider_name=provider,
                model=model,
                temperature=0.5,
                max_tokens=800,
            )

            task.result = result.content if hasattr(result, "content") else str(result)
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc).isoformat()

            yield {
                "type": "task_completed",
                "data": {
                    "task_id": task.task_id,
                    "role_id": task.role_id,
                    "agent_id": agent["id"],
                    "agent_name": agent_name,
                    "result": task.result,
                },
            }

        except Exception as e:
            logger.error(f"[Orchestrator] Task {task.task_id} failed: {e}")
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now(timezone.utc).isoformat()
            yield {
                "type": "task_failed",
                "data": {
                    "task_id": task.task_id,
                    "error": str(e),
                },
            }

    async def _synthesize_results(
        self,
        coordinator: dict,
        group: dict,
        session: CollaborationSession,
    ) -> str:
        completed_tasks = [t for t in session.sub_tasks if t.status == TaskStatus.COMPLETED]
        failed_tasks = [t for t in session.sub_tasks if t.status == TaskStatus.FAILED]

        if not completed_tasks and not failed_tasks:
            return session.coordinator_response or "协作未能产生有效结果"

        results_text = ""
        for task in completed_tasks:
            agent = agents_store.get(task.agent_id) if task.agent_id else None
            agent_name = agent["name"] if agent else "Unknown Agent"
            results_text += f"\n### {agent_name} ({task.role_id}) - {task.description}\n{task.result}\n"

        if failed_tasks:
            results_text += "\n### 失败的任务\n"
            for task in failed_tasks:
                results_text += f"- {task.description}: {task.error}\n"

        synthesis_prompt = f"""你是 {coordinator['name']}，LuomiNest 协作调度员。

用户原始需求: {session.user_message}

执行计划: {session.plan or '无'}

各 Agent 的执行结果:
{results_text}

请综合以上各角色的执行结果，给出一个完整、连贯、对用户友好的最终回复。
要求：
1. 整合各角色的关键发现和结论
2. 去除重复内容
3. 保持逻辑清晰
4. 如有失败的任务，说明影响和替代方案
5. 使用中文回复"""

        messages = [
            {"role": "system", "content": synthesis_prompt},
            {"role": "user", "content": "请综合以上结果，给出最终回复。"},
        ]

        provider = self._resolve_provider(coordinator)
        model = self._resolve_model(coordinator, provider)

        result = await llm_adapter.chat(
            messages=messages,
            provider_name=provider,
            model=model,
            temperature=0.3,
            max_tokens=1200,
        )

        return result.content if hasattr(result, "content") else str(result)

    def _build_worker_prompt(
        self,
        agent: dict,
        member: dict | None,
        group: dict,
        role_prompt: str,
    ) -> str:
        role = member.get("role", "成员") if member else "成员"
        group_name = group.get("name", "")

        prompt = f"""你是 {agent['name']}，这是 LuomiNest AI 群聊环境。你在群组「{group_name}」中的角色是：{role}。

{agent.get('description', '')}

{role_prompt}"""

        if agent.get("system_prompt"):
            prompt += f"\n\n额外指令：{agent['system_prompt']}"

        return prompt

    async def _save_messages(self, group: dict, session: CollaborationSession) -> None:
        group_id = group.get("id", "")
        if group_id not in self._save_locks:
            self._save_locks[group_id] = asyncio.Lock()
        async with self._save_locks[group_id]:
            fresh_group = groups_store.get(group_id)
            if not fresh_group:
                logger.warning(f"[Orchestrator] Group {group_id} not found when saving messages")
                return

            if "messages" not in fresh_group:
                fresh_group["messages"] = []

            now = datetime.now(timezone.utc).isoformat()

            user_msg = {
                "id": str(uuid.uuid4()),
                "sender_id": "user",
                "sender_type": "user",
                "content": session.user_message,
                "timestamp": now,
            }
            fresh_group["messages"].append(user_msg)

            if session.phase == CollaborationPhase.COMPLETED and session.sub_tasks:
                for task in session.sub_tasks:
                    if task.status == TaskStatus.COMPLETED and task.result:
                        agent = agents_store.get(task.agent_id) if task.agent_id else None
                        agent_name = agent["name"] if agent else "Agent"
                        member = None
                        for m in fresh_group.get("members", []):
                            if m.get("agent_id") == task.agent_id:
                                member = m
                                break

                        task_msg = {
                            "id": str(uuid.uuid4()),
                            "sender_id": task.agent_id or "agent",
                            "sender_name": agent_name,
                            "sender_type": "agent",
                            "content": task.result,
                            "timestamp": now,
                            "role": member.get("role", "") if member else task.role_id,
                            "collaboration": {
                                "session_id": session.session_id,
                                "task_id": task.task_id,
                                "task_description": task.description,
                            },
                        }
                        fresh_group["messages"].append(task_msg)

                if session.final_result:
                    coordinator = _find_coordinator_agent(fresh_group)
                    coordinator_name = coordinator["name"] if coordinator else "调度员"
                    synthesis_msg = {
                        "id": str(uuid.uuid4()),
                        "sender_id": coordinator["id"] if coordinator else "coordinator",
                        "sender_name": coordinator_name,
                        "sender_type": "agent",
                        "content": session.final_result,
                        "timestamp": now,
                        "role": "调度员",
                        "collaboration": {
                            "session_id": session.session_id,
                            "type": "synthesis",
                        },
                    }
                    fresh_group["messages"].append(synthesis_msg)

            elif session.coordinator_response:
                coordinator = _find_coordinator_agent(fresh_group)
                coordinator_name = coordinator["name"] if coordinator else "Agent"
                direct_msg = {
                    "id": str(uuid.uuid4()),
                    "sender_id": coordinator["id"] if coordinator else "agent",
                    "sender_name": coordinator_name,
                    "sender_type": "agent",
                    "content": session.coordinator_response,
                    "timestamp": now,
                    "role": "调度员",
                }
                fresh_group["messages"].append(direct_msg)

            elif session.final_result:
                error_msg = {
                    "id": str(uuid.uuid4()),
                    "sender_id": "system",
                    "sender_name": "系统",
                    "sender_type": "agent",
                    "content": session.final_result,
                    "timestamp": now,
                    "role": "系统",
                }
                fresh_group["messages"].append(error_msg)

            fresh_group["updated_at"] = now
            groups_store.set(fresh_group["id"], fresh_group)

    def get_session(self, session_id: str) -> CollaborationSession | None:
        """获取指定 ID 的协作会话。

        Args:
            session_id: 会话 ID

        Returns:
            CollaborationSession | None: 会话对象，不存在则返回 None
        """
        return self._active_sessions.get(session_id)


agent_orchestrator = AgentOrchestrator()
