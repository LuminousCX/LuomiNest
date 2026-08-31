"""工作流模板 API 端点。

路由前缀: /workflow/templates
对齐 tool-system-optimization.md §4.8.4 M16

提供工作流模板的 CRUD、实例化执行和定时任务绑定接口：
- POST   /workflow/templates                       保存为模板
- GET    /workflow/templates                       模板列表
- GET    /workflow/templates/{template_id}         模板详情
- PUT    /workflow/templates/{template_id}         更新模板
- DELETE /workflow/templates/{template_id}         删除模板
- POST   /workflow/templates/{template_id}/run     实例化执行
- POST   /workflow/templates/{template_id}/schedule 绑定定时任务
"""
from typing import Any

from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel, Field

from app.core.exceptions import LuomiNestError, NotFoundError
from app.core.utils import ok

router = APIRouter(prefix="/workflow/templates", tags=["workflow-templates"])


# ─── Pydantic 请求模型 ───


class SaveAsTemplateRequest(BaseModel):
    """保存为模板请求"""
    name: str = Field(..., description="模板名称")
    description: str = Field("", description="模板描述")
    plan_json: str = Field(..., description="工作流计划 JSON 字符串")
    parameters_schema: str = Field("{}", description="参数 JSON Schema 字符串")
    auto_approve: bool = Field(False, description="是否自动审批")
    created_from: str = Field("user", description="创建来源: user / ai")
    source_session_id: str = Field("", description="来源会话 ID（可选）")


class RunTemplateRequest(BaseModel):
    """实例化执行模板请求"""
    params: dict[str, Any] = Field(default_factory=dict, description="模板参数")
    auto_approve: bool | None = Field(None, description="是否自动审批（None=使用模板默认值）")


class ScheduleTemplateRequest(BaseModel):
    """绑定定时任务请求"""
    schedule: str = Field(..., description="调度表达式: cron / interval / ISO datetime")
    params: dict[str, Any] = Field(default_factory=dict, description="模板参数")
    auto_approve: bool = Field(True, description="定时任务默认免审批")


# ─── 模板服务懒导入 ───


def _get_template_service():
    """懒导入 WorkflowTemplateService 单例"""
    from app.core.workflow.template_service import WorkflowTemplateService
    return WorkflowTemplateService()


# ─── 端点 ───


@router.post("")
async def save_as_template(req: SaveAsTemplateRequest):
    """保存工作流为模板"""
    try:
        service = _get_template_service()
        template = await service.save_template(
            name=req.name,
            description=req.description,
            plan_json=req.plan_json,
            parameters_schema=req.parameters_schema,
            auto_approve=req.auto_approve,
            created_from=req.created_from,
            source_session_id=req.source_session_id,
        )
        return ok(template)
    except LuomiNestError:
        raise
    except Exception as e:
        logger.error("[WorkflowTemplates] Save failed: {}", str(e), exc_info=True)
        raise LuomiNestError(
            "保存模板失败，请稍后重试",
            code="TEMPLATE_SAVE_FAILED",
            status_code=500,
        )


@router.get("")
async def list_templates():
    """列出所有工作流模板"""
    try:
        service = _get_template_service()
        templates = await service.list_templates()
        return ok(templates)
    except LuomiNestError:
        raise
    except Exception as e:
        logger.error("[WorkflowTemplates] List failed: {}", str(e), exc_info=True)
        raise LuomiNestError(
            "获取模板列表失败",
            code="TEMPLATE_LIST_FAILED",
            status_code=500,
        )


@router.get("/{template_id}")
async def get_template(template_id: str):
    """获取工作流模板详情"""
    try:
        service = _get_template_service()
        template = await service.get_template(template_id)
        if template is None:
            raise NotFoundError(f"模板 {template_id} 不存在", code="WORKFLOW_TEMPLATE_NOT_FOUND")
        return ok(template)
    except LuomiNestError:
        raise
    except Exception as e:
        logger.error("[WorkflowTemplates] Get failed: {}", str(e), exc_info=True)
        raise LuomiNestError(
            "获取模板详情失败",
            code="TEMPLATE_GET_FAILED",
            status_code=500,
        )


@router.put("/{template_id}")
async def update_template(template_id: str, req: SaveAsTemplateRequest):
    """更新工作流模板"""
    try:
        service = _get_template_service()
        template = await service.update_template(
            template_id=template_id,
            name=req.name,
            description=req.description,
            plan_json=req.plan_json,
            parameters_schema=req.parameters_schema,
            auto_approve=req.auto_approve,
        )
        if template is None:
            raise NotFoundError(f"模板 {template_id} 不存在", code="WORKFLOW_TEMPLATE_NOT_FOUND")
        return ok(template)
    except LuomiNestError:
        raise
    except Exception as e:
        logger.error("[WorkflowTemplates] Update failed: {}", str(e), exc_info=True)
        raise LuomiNestError(
            "更新模板失败",
            code="TEMPLATE_UPDATE_FAILED",
            status_code=500,
        )


@router.delete("/{template_id}")
async def delete_template(template_id: str):
    """删除工作流模板"""
    try:
        service = _get_template_service()
        success = await service.delete_template(template_id)
        if not success:
            raise NotFoundError(f"模板 {template_id} 不存在", code="WORKFLOW_TEMPLATE_NOT_FOUND")
        return ok({"template_id": template_id})
    except LuomiNestError:
        raise
    except Exception as e:
        logger.error("[WorkflowTemplates] Delete failed: {}", str(e), exc_info=True)
        raise LuomiNestError(
            "删除模板失败",
            code="TEMPLATE_DELETE_FAILED",
            status_code=500,
        )


@router.post("/{template_id}/run")
async def run_template(template_id: str, req: RunTemplateRequest):
    """实例化执行工作流模板

    根据模板创建一个新的工作流会话并执行。
    auto_approve 为 None 时使用模板自身的默认值。
    """
    try:
        service = _get_template_service()
        result = await service.run_template(
            template_id=template_id,
            params=req.params,
            auto_approve=req.auto_approve,
        )
        return ok(result)
    except LuomiNestError:
        raise
    except Exception as e:
        logger.error("[WorkflowTemplates] Run failed: {}", str(e), exc_info=True)
        raise LuomiNestError(
            "执行模板失败，请稍后重试",
            code="TEMPLATE_RUN_FAILED",
            status_code=500,
        )


@router.post("/{template_id}/schedule")
async def schedule_template(template_id: str, req: ScheduleTemplateRequest):
    """绑定定时任务到工作流模板

    创建一个定时任务，按计划自动执行该模板。
    """
    try:
        service = _get_template_service()
        result = await service.schedule_template(
            template_id=template_id,
            schedule=req.schedule,
            params=req.params,
            auto_approve=req.auto_approve,
        )
        return ok(result)
    except LuomiNestError:
        raise
    except Exception as e:
        logger.error("[WorkflowTemplates] Schedule failed: {}", str(e), exc_info=True)
        raise LuomiNestError(
            "绑定定时任务失败",
            code="TEMPLATE_SCHEDULE_FAILED",
            status_code=500,
        )
