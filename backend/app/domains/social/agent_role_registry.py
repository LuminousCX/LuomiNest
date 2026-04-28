from dataclasses import dataclass, field
from typing import Any
from loguru import logger


@dataclass
class AgentRoleDefinition:
    role_id: str
    name: str
    description: str
    system_prompt_template: str
    capabilities: list[str] = field(default_factory=list)
    execution_mode: str = "parallel"
    max_concurrent_tasks: int = 3
    timeout_seconds: int = 120
    color: str = "#0d9488"


COORDINATOR_PROMPT = """你是 {name}，LuomiNest 多 Agent 协作系统的中心调度员。

## 你的核心职责
1. 分析用户的需求，判断需要哪些角色参与协作
2. 将复杂任务拆解为可并行/串行执行的子任务
3. 为每个子任务指派最合适的 Agent 角色
4. 收集各 Agent 的执行结果，综合输出最终回复

## 协作策略
- **分工协作**：数据只干数据、计算只干计算、审核只干审核，专人专岗
- **串行+并行混合**：
  - 串行：拆解→执行→审核→输出，流程有序
  - 并行：数据查询+规则预检可以同时跑，提升效率
- **禁止**：不要自己包揽所有工作，必须委派给专业角色

## 可用角色
{available_roles}

## 输出格式
当你需要调度其他 Agent 时，请使用以下 JSON 格式（用 ```json 和 ``` 包裹）：

```json
{{
  "plan": "简要描述执行计划",
  "tasks": [
    {{
      "role_id": "角色ID",
      "description": "子任务描述",
      "input": "传递给该角色的具体输入内容",
      "depends_on": []
    }}
  ],
  "execution_order": "parallel 或 serial",
  "final_synthesis": "你将如何综合各角色结果"
}}
```

如果用户的问题简单，不需要多角色协作，直接回复即可，不需要输出 JSON。

## 规则
- 始终使用中文回复
- 复杂度可控，不要过度拆分简单问题
- 确保每个子任务的输入清晰明确
- depends_on 为空数组表示可并行执行，否则填写依赖的任务序号（从0开始）"""

DATA_AGENT_PROMPT = """你是 {name}，LuomiNest 多 Agent 协作系统的数据专员。

## 你的核心职责
- 数据检索与查询
- 数据分析与统计
- 数据格式化与整理
- 信息验证与交叉比对

## 工作原则
- 只处理数据相关任务，不做计算推理或创意写作
- 输出必须基于事实和数据
- 标注数据来源和可靠性
- 如数据不足，明确说明而非编造

## 规则
- 始终使用中文回复
- 保持客观、准确
- 使用结构化格式呈现数据"""

COMPUTE_AGENT_PROMPT = """你是 {name}，LuomiNest 多 Agent 协作系统的计算专员。

## 你的核心职责
- 数学计算与逻辑推理
- 算法设计与分析
- 代码逻辑验证
- 数值模拟与预测

## 工作原则
- 只处理计算和推理任务，不做数据检索或创意写作
- 展示计算过程和关键步骤
- 标注假设条件和约束
- 提供结果的可信度评估

## 规则
- 始终使用中文回复
- 步骤清晰，逻辑严谨
- 标注单位和量级"""

REVIEW_AGENT_PROMPT = """你是 {name}，LuomiNest 多 Agent 协作系统的审核专员。

## 你的核心职责
- 质量审核与校验
- 逻辑一致性检查
- 合规性审查
- 风险评估与提示

## 工作原则
- 只处理审核相关任务，不做数据检索或计算推理
- 以批判性思维审查内容
- 标注审核标准和依据
- 给出明确的通过/不通过结论及理由

## 规则
- 始终使用中文回复
- 客观公正，不偏不倚
- 具体指出问题和改进建议"""

CREATIVE_AGENT_PROMPT = """你是 {name}，LuomiNest 多 Agent 协作系统的创意专员。

## 你的核心职责
- 创意写作与内容生成
- 方案设计与构思
- 头脑风暴与灵感激发
- 文案优化与润色

## 工作原则
- 只处理创意相关任务，不做数据检索或计算推理
- 追求新颖性和创造性
- 提供多个方案供选择
- 考虑目标受众和使用场景

## 规则
- 始终使用中文回复
- 富有想象力和创造力
- 风格多样，灵活应变"""

BUILTIN_ROLES: dict[str, AgentRoleDefinition] = {
    "coordinator": AgentRoleDefinition(
        role_id="coordinator",
        name="调度员",
        description="中心调度，负责任务拆解、角色分配和结果综合",
        system_prompt_template=COORDINATOR_PROMPT,
        capabilities=["task_decomposition", "role_assignment", "result_synthesis", "planning"],
        execution_mode="serial",
        max_concurrent_tasks=1,
        timeout_seconds=60,
        color="#147ebc",
    ),
    "data-agent": AgentRoleDefinition(
        role_id="data-agent",
        name="数据专员",
        description="数据检索、分析、统计和验证",
        system_prompt_template=DATA_AGENT_PROMPT,
        capabilities=["data_retrieval", "data_analysis", "data_formatting", "fact_checking"],
        execution_mode="parallel",
        max_concurrent_tasks=3,
        timeout_seconds=120,
        color="#22c55e",
    ),
    "compute-agent": AgentRoleDefinition(
        role_id="compute-agent",
        name="计算专员",
        description="数学计算、逻辑推理、算法分析",
        system_prompt_template=COMPUTE_AGENT_PROMPT,
        capabilities=["calculation", "reasoning", "algorithm_design", "simulation"],
        execution_mode="parallel",
        max_concurrent_tasks=3,
        timeout_seconds=120,
        color="#f59e0b",
    ),
    "review-agent": AgentRoleDefinition(
        role_id="review-agent",
        name="审核专员",
        description="质量审核、逻辑校验、合规审查",
        system_prompt_template=REVIEW_AGENT_PROMPT,
        capabilities=["quality_review", "consistency_check", "compliance_audit", "risk_assessment"],
        execution_mode="serial",
        max_concurrent_tasks=1,
        timeout_seconds=90,
        color="#ef4444",
    ),
    "creative-agent": AgentRoleDefinition(
        role_id="creative-agent",
        name="创意专员",
        description="创意写作、方案设计、头脑风暴",
        system_prompt_template=CREATIVE_AGENT_PROMPT,
        capabilities=["creative_writing", "design", "brainstorming", "copywriting"],
        execution_mode="parallel",
        max_concurrent_tasks=2,
        timeout_seconds=120,
        color="#a855f7",
    ),
}


class AgentRoleRegistry:
    _roles: dict[str, AgentRoleDefinition] = {}
    _custom_roles: dict[str, AgentRoleDefinition] = {}
    _initialized: bool = False

    @classmethod
    def _ensure_initialized(cls) -> None:
        if not cls._initialized:
            cls._roles = dict(BUILTIN_ROLES)
            cls._custom_roles = {}
            cls._initialized = True

    @classmethod
    def get_role(cls, role_id: str) -> AgentRoleDefinition | None:
        cls._ensure_initialized()
        role = cls._roles.get(role_id) or cls._custom_roles.get(role_id)
        if not role:
            logger.warning(f"[RoleRegistry] Role not found: {role_id}")
        return role

    @classmethod
    def list_roles(cls) -> list[AgentRoleDefinition]:
        cls._ensure_initialized()
        all_roles = {**cls._roles, **cls._custom_roles}
        return list(all_roles.values())

    @classmethod
    def list_worker_roles(cls) -> list[AgentRoleDefinition]:
        cls._ensure_initialized()
        return [r for r in cls.list_roles() if r.role_id != "coordinator"]

    @classmethod
    def register_role(cls, role: AgentRoleDefinition) -> None:
        cls._ensure_initialized()
        logger.info(f"[RoleRegistry] Registering role: {role.role_id} ({role.name})")
        cls._custom_roles[role.role_id] = role

    @classmethod
    def build_coordinator_prompt(cls, coordinator_name: str = "调度员") -> str:
        cls._ensure_initialized()
        worker_roles = cls.list_worker_roles()
        roles_text = "\n".join(
            f"- **{r.role_id}** ({r.name}): {r.description}，能力: {', '.join(r.capabilities)}"
            for r in worker_roles
        )
        return COORDINATOR_PROMPT.format(
            name=coordinator_name,
            available_roles=roles_text,
        )

    @classmethod
    def build_agent_prompt(cls, role_id: str, agent_name: str) -> str | None:
        cls._ensure_initialized()
        role = cls.get_role(role_id)
        if not role:
            return None
        return role.system_prompt_template.format(name=agent_name)
