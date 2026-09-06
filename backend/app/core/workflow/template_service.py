"""工作流模板服务 — CRUD + 实例化执行。

提供模板的完整生命周期管理：
- save_as_template: 创建模板
- list_templates / get_template: 查询
- update_template: 更新字段
- delete_template: 删除
- instantiate: 加载模板 -> 渲染参数 -> 创建工作流会话 -> 提交执行

持久化走 get_async_session 异步会话模式（与 workflow_persistence.py 对齐）。
"""
import json
import uuid
from typing import Any

from loguru import logger
from sqlalchemy import delete, select

from app.core.utils import utc_now
from app.core.workflow.template_renderer import render_plan
from app.infrastructure.database.models.workflow_template import WorkflowTemplateORM
from app.infrastructure.database.repositories.base import BaseRepository
from app.infrastructure.database.session import get_async_session


def _orm_to_dict(orm: WorkflowTemplateORM) -> dict[str, Any]:
    """将 ORM 对象转为字典。"""
    return {
        "template_id": orm.template_id,
        "name": orm.name,
        "description": orm.description,
        "plan_json": orm.plan_json,
        "parameters_schema": orm.parameters_schema,
        "auto_approve": orm.auto_approve,
        "created_from": orm.created_from,
        "source_session_id": orm.source_session_id,
        "created_at": orm.created_at,
        "updated_at": orm.updated_at,
    }


async def save_as_template(
    name: str,
    description: str = "",
    plan_json: str | dict = "{}",
    parameters_schema: str | dict = "{}",
    auto_approve: int = 0,
    created_from: str = "user",
    source_session_id: str = "",
) -> str:
    """创建并保存工作流模板。

    Args:
        name: 模板名称
        description: 模板描述
        plan_json: JSON 序列化的执行计划（字符串或字典）
        parameters_schema: 参数 Schema（字符串或字典）
        auto_approve: 1=免审批直接执行
        created_from: 创建来源 'user' / 'ai'
        source_session_id: 来源会话 ID

    Returns:
        template_id: 生成的模板 ID（前缀 wft_ + uuid hex 前 12 位）
    """
    template_id = f"wft_{uuid.uuid4().hex[:12]}"
    now = utc_now()

    # 确保 plan_json 和 parameters_schema 是字符串
    if isinstance(plan_json, dict):
        plan_json = json.dumps(plan_json, ensure_ascii=False)
    if isinstance(parameters_schema, dict):
        parameters_schema = json.dumps(parameters_schema, ensure_ascii=False)

    await BaseRepository.upsert_async(
        WorkflowTemplateORM,
        index_elements=["template_id"],
        values={
            "template_id": template_id,
            "name": name,
            "description": description,
            "plan_json": plan_json,
            "parameters_schema": parameters_schema,
            "auto_approve": auto_approve,
            "created_from": created_from,
            "source_session_id": source_session_id,
            "created_at": now,
            "updated_at": now,
        },
        update_set={
            "name": name,
            "description": description,
            "plan_json": plan_json,
            "parameters_schema": parameters_schema,
            "auto_approve": auto_approve,
            "updated_at": now,
        },
    )

    logger.info(f"[TemplateService] Template saved: {template_id} ({name})")
    return template_id


async def list_templates() -> list[dict[str, Any]]:
    """列出所有模板（按 updated_at 降序）。"""
    async with get_async_session() as db:
        result = await db.execute(
            select(WorkflowTemplateORM)
            .order_by(WorkflowTemplateORM.updated_at.desc())
        )
        templates = result.scalars().all()
        return [_orm_to_dict(t) for t in templates]


async def get_template(template_id: str) -> dict[str, Any] | None:
    """获取单个模板详情。

    Returns:
        模板字典，不存在时返回 None。
    """
    async with get_async_session() as db:
        result = await db.execute(
            select(WorkflowTemplateORM)
            .where(WorkflowTemplateORM.template_id == template_id)
        )
        orm = result.scalar_one_or_none()
        return _orm_to_dict(orm) if orm else None


async def update_template(
    template_id: str,
    updates: dict[str, Any],
) -> bool:
    """更新模板字段。

    Args:
        template_id: 模板 ID
        updates: 要更新的字段键值对（仅允许模型中定义的字段）

    Returns:
        True 表示更新成功，False 表示模板不存在。
    """
    # 过滤非法字段（主键和时间字段不可随意修改）
    allowed_fields = {
        "name", "description", "plan_json", "parameters_schema",
        "auto_approve", "created_from", "source_session_id",
    }
    filtered = {}
    for key, value in updates.items():
        if key in allowed_fields:
            # 字典类型自动序列化
            if key in ("plan_json", "parameters_schema") and isinstance(value, dict):
                value = json.dumps(value, ensure_ascii=False)
            filtered[key] = value

    if not filtered:
        logger.warning(f"[TemplateService] No valid fields to update for {template_id}")
        return False

    filtered["updated_at"] = utc_now()

    async with get_async_session() as db:
        result = await db.execute(
            select(WorkflowTemplateORM)
            .where(WorkflowTemplateORM.template_id == template_id)
        )
        orm = result.scalar_one_or_none()
        if not orm:
            logger.warning(f"[TemplateService] Template not found: {template_id}")
            return False

        for key, value in filtered.items():
            setattr(orm, key, value)

    logger.info(f"[TemplateService] Template updated: {template_id} fields={list(filtered.keys())}")
    return True


async def delete_template(template_id: str) -> bool:
    """删除模板。

    Returns:
        True 表示删除成功，False 表示模板不存在。
    """
    async with get_async_session() as db:
        result = await db.execute(
            select(WorkflowTemplateORM)
            .where(WorkflowTemplateORM.template_id == template_id)
        )
        orm = result.scalar_one_or_none()
        if not orm:
            logger.warning(f"[TemplateService] Template not found for deletion: {template_id}")
            return False

        await db.execute(
            delete(WorkflowTemplateORM)
            .where(WorkflowTemplateORM.template_id == template_id)
        )

    logger.info(f"[TemplateService] Template deleted: {template_id}")
    return True


async def instantiate(
    template_id: str,
    params: dict[str, Any] | None = None,
    auto_approve: bool | None = None,
) -> str:
    """实例化模板：加载 -> 渲染参数 -> 创建工作流会话 -> 提交执行。

    Args:
        template_id: 模板 ID
        params: 参数键值对，用于替换 {{param}} 占位符
        auto_approve: 覆盖模板的 auto_approve 设置（None 表示使用模板默认值）

    Returns:
        session_id: 创建的工作流会话 ID

    Raises:
        ValueError: 模板不存在或渲染失败
    """
    from app.core.workflow.engine import workflow_engine
    from app.core.workflow.models import WorkflowMode

    # 1. 加载模板
    template = await get_template(template_id)
    if not template:
        raise ValueError(f"模板不存在: {template_id}")

    plan_json_str = template.get("plan_json", "{}")
    if params is None:
        params = {}

    # 2. 渲染参数
    try:
        rendered_plan = render_plan(plan_json_str, params)
    except ValueError as e:
        raise ValueError(f"模板渲染失败: {e}")

    logger.info(
        f"[TemplateService] Template {template_id} rendered: "
        f"task_count={len(rendered_plan.get('tasks', []))}"
    )

    # 3. 确定是否跳过确认
    should_skip = auto_approve if auto_approve is not None else bool(template.get("auto_approve", 0))

    # 4. 构造用户消息并提交到工作流引擎
    # 将渲染后的计划序列化为结构化消息，引擎会识别并直接执行
    user_message = (
        f"[模板实例化] {template.get('name', template_id)}\n\n"
        f"{json.dumps(rendered_plan, ensure_ascii=False, indent=2)}"
    )

    session = await workflow_engine.submit(
        user_message=user_message,
        mode=WorkflowMode.STANDARD,
        skip_confirmation=should_skip,
    )

    logger.info(
        f"[TemplateService] Template {template_id} instantiated: "
        f"session_id={session.session_id}, phase={session.phase.value}"
    )
    return session.session_id


class WorkflowTemplateService:
    """工作流模板服务（类封装，供 API 端点和内部工具调用）。

    包装模块级函数，提供统一的方法名接口。
    """

    async def save_template(self, **kwargs) -> dict[str, Any]:
        """保存模板，返回模板字典（含 template_id）。"""
        template_id = await save_as_template(**kwargs)
        result = await get_template(template_id)
        return result or {"template_id": template_id}

    async def list_templates(self) -> list[dict[str, Any]]:
        return await list_templates()

    async def get_template(self, template_id: str) -> dict[str, Any] | None:
        return await get_template(template_id)

    async def update_template(self, template_id: str, **kwargs) -> bool:
        return await update_template(template_id, kwargs)

    async def delete_template(self, template_id: str) -> bool:
        return await delete_template(template_id)

    async def run_template(
        self,
        template_id: str,
        params: dict[str, Any] | None = None,
        auto_approve: bool | None = None,
    ) -> dict[str, Any]:
        """实例化并执行模板，返回 {session_id}。"""
        session_id = await instantiate(template_id, params, auto_approve)
        return {"session_id": session_id}

    async def schedule_template(
        self,
        template_id: str,
        schedule: str,
        params: dict[str, Any] | None = None,
        auto_approve: bool = True,
    ) -> dict[str, Any]:
        """绑定定时任务到模板。

        创建定时任务，触发时执行模板实例化。
        """
        from app.core.scheduler.manager import luominest_scheduler

        # 构造定时任务 payload
        payload = {
            "instruction": f"[模板定时执行] {template_id}",
            "template_id": template_id,
            "params": params or {},
            "auto_approve": auto_approve,
        }

        task_id = await luominest_scheduler.add_task(
            name=f"模板定时: {template_id}",
            schedule=schedule,
            payload=payload,
        )

        return {"task_id": task_id, "template_id": template_id}
