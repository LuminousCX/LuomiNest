"""CxPlugin 与 CxSkill 管理 API — LuomiNest 双轨扩展系统对外接口。

设计原则：
- 所有响应统一使用 ApiResponse 格式（含 code/message/data），遵循项目规则
- 错误码：0=成功，1xxx=插件错误，2xxx=技能错误，3xxx=AI 自创建错误
- 路由前缀 /plugins 与 /skills，挂在 /api/v1/plugins 与 /api/v1/skills
- 操作类接口返回最新的插件/技能状态，便于前端同步 UI
"""
from __future__ import annotations

from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel, Field

from app.runtime.plugin.cxplugin.lifecycle import luominest_plugin_lifecycle
from app.runtime.plugin.cxplugin.registry import luominest_plugin_registry
from app.schemas.avatar import ApiResponse
from app.services.skill_service import luominest_skill_service
from app.services.skill_improvement_service import luominest_skill_improvement_service


router = APIRouter(tags=["plugins"])


# ---------------------------------------------------------------------------
# 错误码常量
# ---------------------------------------------------------------------------

ERR_PLUGIN_NOT_FOUND = 1001
ERR_PLUGIN_OP_FAILED = 1002
ERR_SKILL_NOT_FOUND = 2001
ERR_SKILL_OP_FAILED = 2002
ERR_SKILL_INVALID = 2003        # skill_id 或 SKILL.md 内容校验失败
ERR_SKILL_EXISTS = 2004         # skill 已存在且 overwrite=False
ERR_SKILL_IMPROVE_FAILED = 2005 # 技能自改进操作失败


# ---------------------------------------------------------------------------
# 响应辅助
# ---------------------------------------------------------------------------

def _ok(data=None, message: str = "ok") -> ApiResponse:
    return ApiResponse(code=0, message=message, data=data)


def _err(code: int, message: str) -> ApiResponse:
    return ApiResponse(code=code, message=message, data=None)


def _plugin_to_dict(metadata) -> dict:
    """将 CxPluginMetadata 序列化为 API 响应字典。"""
    return {
        **metadata.manifest.to_dict(),
        "status": metadata.status.value,
        "loaded_at": metadata.loaded_at,
        "error_message": metadata.error_message,
        "reserved": metadata.reserved,
        "is_active": metadata.is_active,
    }


# ---------------------------------------------------------------------------
# 插件管理接口
# ---------------------------------------------------------------------------

@router.get("/plugins", response_model=ApiResponse)
async def list_plugins(active_only: bool = False) -> ApiResponse:
    """列出所有已加载的插件。"""
    plugins = luominest_plugin_registry.list_plugins(active_only=active_only)
    return _ok(data=[_plugin_to_dict(m) for m in plugins])


@router.get("/plugins/stats", response_model=ApiResponse)
async def plugins_stats() -> ApiResponse:
    """返回插件系统统计信息。"""
    plugins = luominest_plugin_registry.list_plugins()
    disabled = luominest_plugin_lifecycle.get_disabled_plugins()
    return _ok(data={
        "total": len(plugins),
        "active": sum(1 for p in plugins if p.is_active),
        "disabled": len(disabled),
        "disabled_ids": disabled,
    })


@router.get("/plugins/{plugin_id}", response_model=ApiResponse)
async def get_plugin(plugin_id: str) -> ApiResponse:
    """获取单个插件详情。"""
    meta = luominest_plugin_registry.get_plugin(plugin_id)
    if meta is None:
        return _err(ERR_PLUGIN_NOT_FOUND, f"Plugin not found: {plugin_id}")
    return _ok(data=_plugin_to_dict(meta))


@router.post("/plugins/{plugin_id}/enable", response_model=ApiResponse)
async def enable_plugin(plugin_id: str) -> ApiResponse:
    """启用插件。"""
    meta = luominest_plugin_registry.get_plugin(plugin_id)
    if meta is None:
        return _err(ERR_PLUGIN_NOT_FOUND, f"Plugin not found: {plugin_id}")
    ok = await luominest_plugin_lifecycle.enable_plugin(plugin_id)
    if not ok:
        return _err(ERR_PLUGIN_OP_FAILED, f"Failed to enable plugin: {plugin_id}")
    meta = luominest_plugin_registry.get_plugin(plugin_id)
    return _ok(data=_plugin_to_dict(meta), message="Plugin enabled")


@router.post("/plugins/{plugin_id}/disable", response_model=ApiResponse)
async def disable_plugin(plugin_id: str) -> ApiResponse:
    """禁用插件（不卸载，仅标记为禁用状态）。"""
    meta = luominest_plugin_registry.get_plugin(plugin_id)
    if meta is None:
        return _err(ERR_PLUGIN_NOT_FOUND, f"Plugin not found: {plugin_id}")
    ok = await luominest_plugin_lifecycle.disable_plugin(plugin_id)
    if not ok:
        return _err(ERR_PLUGIN_OP_FAILED, f"Failed to disable plugin: {plugin_id}")
    meta = luominest_plugin_registry.get_plugin(plugin_id)
    return _ok(data=_plugin_to_dict(meta), message="Plugin disabled")


@router.post("/plugins/{plugin_id}/reload", response_model=ApiResponse)
async def reload_plugin(plugin_id: str) -> ApiResponse:
    """重载单个插件（卸载后重新加载）。"""
    meta = luominest_plugin_registry.get_plugin(plugin_id)
    if meta is None:
        return _err(ERR_PLUGIN_NOT_FOUND, f"Plugin not found: {plugin_id}")
    ok = await luominest_plugin_lifecycle.reload_plugin(plugin_id)
    if not ok:
        return _err(ERR_PLUGIN_OP_FAILED, f"Failed to reload plugin: {plugin_id}")
    meta = luominest_plugin_registry.get_plugin(plugin_id)
    return _ok(data=_plugin_to_dict(meta) if meta else None, message="Plugin reloaded")


@router.post("/plugins/{plugin_id}/unload", response_model=ApiResponse)
async def unload_plugin(plugin_id: str) -> ApiResponse:
    """卸载插件（从注册表移除，不删除文件）。"""
    meta = luominest_plugin_registry.get_plugin(plugin_id)
    if meta is None:
        return _err(ERR_PLUGIN_NOT_FOUND, f"Plugin not found: {plugin_id}")
    ok = await luominest_plugin_lifecycle.unload_plugin(plugin_id)
    if not ok:
        return _err(ERR_PLUGIN_OP_FAILED, f"Failed to unload plugin: {plugin_id}")
    return _ok(message="Plugin unloaded")


@router.post("/plugins/reload-all", response_model=ApiResponse)
async def reload_all_plugins() -> ApiResponse:
    """重载所有插件。"""
    count = await luominest_plugin_lifecycle.reload_all()
    logger.info(f"[PluginAPI] Reloaded all plugins: {count} loaded")
    return _ok(data={"loaded_count": count}, message="All plugins reloaded")


# ---------------------------------------------------------------------------
# 技能管理接口
# ---------------------------------------------------------------------------

@router.get("/skills", response_model=ApiResponse)
async def list_skills(active_only: bool = False) -> ApiResponse:
    """列出所有已加载的技能。"""
    return _ok(data=luominest_skill_service.list_skills(active_only=active_only))


@router.get("/skills/stats", response_model=ApiResponse)
async def skills_stats() -> ApiResponse:
    """返回技能系统统计信息。"""
    return _ok(data=luominest_skill_service.get_stats())


@router.get("/skills/{skill_id}", response_model=ApiResponse)
async def get_skill(skill_id: str) -> ApiResponse:
    """获取单个技能详情（含 body 全文）。"""
    data = luominest_skill_service.get_skill(skill_id)
    if data is None:
        return _err(ERR_SKILL_NOT_FOUND, f"Skill not found: {skill_id}")
    return _ok(data=data)


@router.post("/skills/{skill_id}/enable", response_model=ApiResponse)
async def enable_skill(skill_id: str) -> ApiResponse:
    """启用技能。"""
    ok = luominest_skill_service.enable_skill(skill_id)
    if not ok:
        return _err(ERR_SKILL_NOT_FOUND, f"Skill not found: {skill_id}")
    return _ok(data=luominest_skill_service.get_skill(skill_id), message="Skill enabled")


@router.post("/skills/{skill_id}/disable", response_model=ApiResponse)
async def disable_skill(skill_id: str) -> ApiResponse:
    """禁用技能（不卸载，仅标记为禁用状态，不参与 Prompt 注入）。"""
    ok = luominest_skill_service.disable_skill(skill_id)
    if not ok:
        return _err(ERR_SKILL_NOT_FOUND, f"Skill not found: {skill_id}")
    return _ok(data=luominest_skill_service.get_skill(skill_id), message="Skill disabled")


@router.post("/skills/{skill_id}/reload", response_model=ApiResponse)
async def reload_skill(skill_id: str) -> ApiResponse:
    """重载单个技能（用于 SKILL.md 修改后热更新）。"""
    ok = await luominest_skill_service.reload_skill(skill_id)
    if not ok:
        return _err(ERR_SKILL_OP_FAILED, f"Failed to reload skill: {skill_id}")
    return _ok(data=luominest_skill_service.get_skill(skill_id), message="Skill reloaded")


@router.post("/skills/reload-all", response_model=ApiResponse)
async def reload_all_skills() -> ApiResponse:
    """重载所有技能。"""
    count = await luominest_skill_service.reload_all()
    return _ok(data={"loaded_count": count}, message="All skills reloaded")


# ---------------------------------------------------------------------------
# 技能写入/删除/原文读取（供 skill-creator 元技能与前端编辑器调用）
# ---------------------------------------------------------------------------


class SkillWriteRequest(BaseModel):
    """写入 SKILL.md 的请求体。"""
    skill_id: str = Field(..., description="技能 id（kebab-case，与目录名一致）")
    content: str = Field(..., description="SKILL.md 完整文本（含 frontmatter + body）")
    overwrite: bool = Field(True, description="已存在时是否覆盖，默认 True")


class SkillIdRequest(BaseModel):
    """仅含 skill_id 的请求体。"""
    skill_id: str = Field(..., description="技能 id")


@router.get("/skills/{skill_id}/raw", response_model=ApiResponse)
async def get_skill_raw(skill_id: str) -> ApiResponse:
    """获取 SKILL.md 原始文本内容（供前端编辑器加载）。"""
    content = await luominest_skill_service.get_skill_raw_content(skill_id)
    if content is None:
        return _err(ERR_SKILL_NOT_FOUND, f"Skill not found or no source file: {skill_id}")
    return _ok(data={"skill_id": skill_id, "content": content})


@router.post("/skills/write", response_model=ApiResponse)
async def write_skill(req: SkillWriteRequest) -> ApiResponse:
    """写入（创建或更新）SKILL.md，写后立即加载。

    供 skill-creator 元技能、前端编辑器、AI 自主扩展调用。
    """
    try:
        result = await luominest_skill_service.write_skill(
            req.skill_id, req.content, overwrite=req.overwrite
        )
    except ValueError as e:
        msg = str(e)
        if "已存在" in msg:
            return _err(ERR_SKILL_EXISTS, msg)
        return _err(ERR_SKILL_INVALID, msg)
    except Exception as e:
        logger.error(f"[PluginAPI] write_skill failed: {e}")
        return _err(ERR_SKILL_OP_FAILED, f"写入技能失败: {e}")

    # 返回最新技能详情（若加载成功）
    detail = luominest_skill_service.get_skill(req.skill_id)
    return _ok(
        data={**result, "skill": detail},
        message="Skill created" if result.get("created") else "Skill updated",
    )


@router.post("/skills/validate", response_model=ApiResponse)
async def validate_skill_content(req: SkillWriteRequest) -> ApiResponse:
    """仅校验 SKILL.md 内容合法性，不写入磁盘。"""
    try:
        frontmatter = luominest_skill_service.validate_skill_md_content(
            req.content, req.skill_id
        )
    except ValueError as e:
        return _err(ERR_SKILL_INVALID, str(e))
    return _ok(data={"valid": True, "frontmatter": frontmatter}, message="Skill content is valid")


@router.post("/skills/delete", response_model=ApiResponse)
async def delete_skill(req: SkillIdRequest) -> ApiResponse:
    """删除技能（含目录与注册表条目）。"""
    try:
        result = await luominest_skill_service.delete_skill(req.skill_id)
    except ValueError as e:
        return _err(ERR_SKILL_INVALID, str(e))
    except Exception as e:
        logger.error(f"[PluginAPI] delete_skill failed: {e}")
        return _err(ERR_SKILL_OP_FAILED, f"删除技能失败: {e}")
    if not result.get("deleted"):
        return _err(ERR_SKILL_NOT_FOUND, f"Skill not found: {req.skill_id}")
    return _ok(data=result, message="Skill deleted")


# ---------------------------------------------------------------------------
# 技能自改进接口（使用统计 + LLM 建议 + auto_improve）
# ---------------------------------------------------------------------------


class SkillFeedbackRequest(BaseModel):
    """技能反馈请求体。"""
    skill_id: str = Field(..., description="技能 id")
    kind: str = Field(..., description="反馈类型: positive / negative")
    comment: str = Field("", description="可选反馈说明")


class SkillSuggestionRequest(BaseModel):
    """生成改进建议请求体。"""
    skill_id: str = Field(..., description="技能 id")
    force: bool = Field(False, description="是否强制生成（忽略已有未应用建议）")


class SuggestionActionRequest(BaseModel):
    """建议操作请求体。"""
    suggestion_id: str = Field(..., description="建议 id")


class AutoImproveConfigRequest(BaseModel):
    """auto_improve 配置请求体。"""
    enabled: bool = Field(..., description="是否启用自动改进")
    threshold: float = Field(0.7, ge=0.0, le=1.0, description="自动应用置信度阈值")


@router.get("/skills/improvement/dashboard", response_model=ApiResponse)
async def get_improvement_dashboard() -> ApiResponse:
    """获取技能自改进仪表盘数据。"""
    return _ok(data=luominest_skill_improvement_service.get_dashboard())


@router.get("/skills/improvement/usage", response_model=ApiResponse)
async def list_skill_usage_stats() -> ApiResponse:
    """列出所有技能的使用统计。"""
    stats = luominest_skill_improvement_service.list_usage_stats()
    return _ok(data=[s.to_dict() for s in stats])


@router.get("/skills/improvement/usage/{skill_id}", response_model=ApiResponse)
async def get_skill_usage_stats(skill_id: str) -> ApiResponse:
    """获取单个技能的使用统计。"""
    stats = luominest_skill_improvement_service.get_usage_stats(skill_id)
    if stats is None:
        return _err(ERR_SKILL_NOT_FOUND, f"No usage stats for: {skill_id}")
    return _ok(data=stats.to_dict())


@router.post("/skills/improvement/feedback", response_model=ApiResponse)
async def submit_skill_feedback(req: SkillFeedbackRequest) -> ApiResponse:
    """提交技能反馈（赞/踩）。"""
    try:
        stats = luominest_skill_improvement_service.track_feedback(
            req.skill_id, req.kind, req.comment
        )
    except ValueError as e:
        return _err(ERR_SKILL_INVALID, str(e))
    except Exception as e:
        logger.error(f"[PluginAPI] submit_skill_feedback failed: {e}")
        return _err(ERR_SKILL_IMPROVE_FAILED, f"提交反馈失败: {e}")
    return _ok(data=stats.to_dict(), message="Feedback recorded")


@router.get("/skills/improvement/suggestions", response_model=ApiResponse)
async def list_suggestions(
    skill_id: str | None = None,
    applied: bool | None = None,
) -> ApiResponse:
    """列出改进建议。

    Args:
        skill_id: 按技能过滤
        applied: True=仅已应用，False=仅未应用，None=全部
    """
    applied_only = applied is True
    unapplied_only = applied is False
    suggs = luominest_skill_improvement_service.list_suggestions(
        skill_id=skill_id,
        applied_only=applied_only,
        unapplied_only=unapplied_only,
    )
    return _ok(data=suggs)


@router.post("/skills/improvement/suggest", response_model=ApiResponse)
async def generate_suggestion(req: SkillSuggestionRequest) -> ApiResponse:
    """异步调用 LLM 生成技能改进建议。

    若已有未应用的建议且 force=False，直接返回该建议。
    """
    try:
        suggestion = await luominest_skill_improvement_service.generate_suggestion(
            req.skill_id, force=req.force
        )
    except Exception as e:
        logger.error(f"[PluginAPI] generate_suggestion failed: {e}")
        return _err(ERR_SKILL_IMPROVE_FAILED, f"生成建议失败: {e}")

    if suggestion is None:
        return _err(ERR_SKILL_IMPROVE_FAILED, "生成建议失败（LLM 调用或解析失败）")
    return _ok(data=suggestion, message="Suggestion generated")


@router.post("/skills/improvement/apply", response_model=ApiResponse)
async def apply_suggestion(req: SuggestionActionRequest) -> ApiResponse:
    """应用一条改进建议到 SKILL.md（含备份）。"""
    try:
        result = await luominest_skill_improvement_service.apply_suggestion(
            req.suggestion_id, auto=False
        )
    except ValueError as e:
        return _err(ERR_SKILL_INVALID, str(e))
    except Exception as e:
        logger.error(f"[PluginAPI] apply_suggestion failed: {e}")
        return _err(ERR_SKILL_IMPROVE_FAILED, f"应用建议失败: {e}")
    return _ok(data=result, message="Suggestion applied")


@router.post("/skills/improvement/dismiss", response_model=ApiResponse)
async def dismiss_suggestion(req: SuggestionActionRequest) -> ApiResponse:
    """忽略（删除）一条改进建议。"""
    ok = luominest_skill_improvement_service.dismiss_suggestion(req.suggestion_id)
    if not ok:
        return _err(ERR_SKILL_NOT_FOUND, f"Suggestion not found: {req.suggestion_id}")
    return _ok(message="Suggestion dismissed")


@router.get("/skills/improvement/auto-config", response_model=ApiResponse)
async def get_auto_improve_config() -> ApiResponse:
    """获取 auto_improve 配置。"""
    return _ok(data={
        "enabled": luominest_skill_improvement_service.is_auto_improve_enabled(),
        "threshold": luominest_skill_improvement_service.get_auto_improve_threshold(),
    })


@router.post("/skills/improvement/auto-config", response_model=ApiResponse)
async def set_auto_improve_config(req: AutoImproveConfigRequest) -> ApiResponse:
    """配置 auto_improve 开关与阈值。"""
    try:
        luominest_skill_improvement_service.set_auto_improve(req.enabled)
        luominest_skill_improvement_service.set_auto_improve_threshold(req.threshold)
    except ValueError as e:
        return _err(ERR_SKILL_INVALID, str(e))
    return _ok(data={
        "enabled": luominest_skill_improvement_service.is_auto_improve_enabled(),
        "threshold": luominest_skill_improvement_service.get_auto_improve_threshold(),
    }, message="auto_improve config updated")
