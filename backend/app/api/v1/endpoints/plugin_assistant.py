"""CxPluginConfigAssistant API — LuomiNest 插件配置 AI 助手对外接口。

提供插件配置的自然语言修改、配置解释、脚手架生成等能力。

设计原则：
- 所有响应统一使用 ApiResponse 格式（含 code/message/data）
- 错误码：0=成功，1xxx=插件错误，3xxx=AI 助手错误
- 路由前缀 /plugins/assistant，挂在 /api/v1/plugins/assistant
"""
from __future__ import annotations

from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel, Field

from app.schemas.avatar import ApiResponse
from app.services.plugin_config_assistant import (
    CxSettingPatch,
    luominest_plugin_config_assistant,
)


router = APIRouter(tags=["plugin-assistant"])


# ---------------------------------------------------------------------------
# 错误码常量
# ---------------------------------------------------------------------------

ERR_PLUGIN_NOT_FOUND = 1001
ERR_ASSISTANT_FAILED = 3001
ERR_ASSISTANT_INVALID = 3002
ERR_SCAFFOLD_EXISTS = 3003


# ---------------------------------------------------------------------------
# 响应辅助
# ---------------------------------------------------------------------------

def _ok(data=None, message: str = "ok") -> ApiResponse:
    return ApiResponse(code=0, message=message, data=data)


def _err(code: int, message: str) -> ApiResponse:
    return ApiResponse(code=code, message=message, data=None)


# ---------------------------------------------------------------------------
# 请求体
# ---------------------------------------------------------------------------


class ConfigSuggestRequest(BaseModel):
    """配置建议请求。"""
    plugin_id: str = Field(..., description="插件 id")
    user_request: str = Field(..., description="用户的自然语言配置请求")


class ConfigApplyRequest(BaseModel):
    """应用配置 patch 请求。"""
    plugin_id: str = Field(..., description="插件 id")
    patches: list[dict] = Field(..., description="patch 列表，每项含 op/key/value/reason")
    skip_invalid: bool = Field(True, description="是否跳过校验失败的 patch")


class PluginIdRequest(BaseModel):
    """仅含 plugin_id 的请求体。"""
    plugin_id: str = Field(..., description="插件 id")


class ScaffoldGenerateRequest(BaseModel):
    """生成脚手架请求。"""
    plugin_id: str = Field(..., description="插件 id（kebab-case）")
    name: str = Field(..., description="插件中文名")
    description: str = Field(..., description="插件描述")
    author: str = Field("LuminousCX", description="作者")
    category: str = Field("tool", description="分类")
    permissions: list[str] | None = Field(None, description="权限列表")
    capabilities: list[str] | None = Field(None, description="能力列表")
    settings_decl: dict | None = Field(None, description="配置项声明，留空则 LLM 生成")


class ScaffoldWriteRequest(BaseModel):
    """写入脚手架请求。"""
    plugin_id: str = Field(..., description="插件 id")
    overwrite: bool = Field(False, description="是否覆盖已存在的目录")


# ---------------------------------------------------------------------------
# 配置查询接口
# ---------------------------------------------------------------------------


@router.get("/plugins/assistant/config/{plugin_id}", response_model=ApiResponse)
async def get_plugin_config(plugin_id: str) -> ApiResponse:
    """获取插件当前配置（合并 manifest 默认值与 KV 存储值）。"""
    try:
        result = luominest_plugin_config_assistant.get_plugin_config(plugin_id)
    except ValueError as e:
        return _err(ERR_PLUGIN_NOT_FOUND, str(e))
    return _ok(data=result)


@router.post("/plugins/assistant/config/reset", response_model=ApiResponse)
async def reset_plugin_config(req: PluginIdRequest) -> ApiResponse:
    """重置插件配置到 manifest 默认值。"""
    try:
        result = luominest_plugin_config_assistant.reset_plugin_config(req.plugin_id)
    except ValueError as e:
        return _err(ERR_PLUGIN_NOT_FOUND, str(e))
    return _ok(data=result, message="Config reset")


# ---------------------------------------------------------------------------
# 配置修改（LLM 建议 + 应用）
# ---------------------------------------------------------------------------


@router.post("/plugins/assistant/suggest", response_model=ApiResponse)
async def suggest_config_change(req: ConfigSuggestRequest) -> ApiResponse:
    """让 LLM 根据自然语言请求生成配置 patch 建议。"""
    try:
        suggestion = await luominest_plugin_config_assistant.suggest_config_change(
            req.plugin_id, req.user_request
        )
    except ValueError as e:
        return _err(ERR_PLUGIN_NOT_FOUND, str(e))
    except RuntimeError as e:
        logger.error(f"[PluginAssistant] suggest failed: {e}")
        return _err(ERR_ASSISTANT_FAILED, str(e))
    return _ok(data=suggestion.to_dict(), message="Suggestion generated")


@router.post("/plugins/assistant/apply", response_model=ApiResponse)
async def apply_config_patches(req: ConfigApplyRequest) -> ApiResponse:
    """应用配置 patch 到插件 KV 存储。"""
    try:
        # 将 dict 转为 CxSettingPatch 列表
        patches = [
            CxSettingPatch(
                op=str(p.get("op", "set")),
                key=str(p.get("key", "")),
                value=p.get("value"),
                reason=str(p.get("reason", "")),
                validation_error=str(p.get("validation_error", "")),
            )
            for p in req.patches
        ]
        result = luominest_plugin_config_assistant.apply_config_patches(
            req.plugin_id, patches, skip_invalid=req.skip_invalid
        )
    except ValueError as e:
        return _err(ERR_ASSISTANT_INVALID, str(e))
    except Exception as e:
        logger.error(f"[PluginAssistant] apply failed: {e}")
        return _err(ERR_ASSISTANT_FAILED, f"应用配置失败: {e}")
    return _ok(data=result, message="Patches applied")


@router.post("/plugins/assistant/explain", response_model=ApiResponse)
async def explain_config(req: PluginIdRequest) -> ApiResponse:
    """用 LLM 解释插件当前配置含义。"""
    try:
        result = await luominest_plugin_config_assistant.explain_config(req.plugin_id)
    except ValueError as e:
        return _err(ERR_PLUGIN_NOT_FOUND, str(e))
    except RuntimeError as e:
        logger.error(f"[PluginAssistant] explain failed: {e}")
        return _err(ERR_ASSISTANT_FAILED, str(e))
    return _ok(data=result)


# ---------------------------------------------------------------------------
# 插件脚手架生成
# ---------------------------------------------------------------------------


@router.post("/plugins/assistant/scaffold/generate", response_model=ApiResponse)
async def generate_scaffold(req: ScaffoldGenerateRequest) -> ApiResponse:
    """根据描述生成新插件脚手架（不写入磁盘）。"""
    try:
        scaffold = await luominest_plugin_config_assistant.generate_scaffold(
            plugin_id=req.plugin_id,
            name=req.name,
            description=req.description,
            author=req.author,
            category=req.category,
            permissions=req.permissions,
            capabilities=req.capabilities,
            settings_decl=req.settings_decl,
        )
    except ValueError as e:
        return _err(ERR_ASSISTANT_INVALID, str(e))
    except Exception as e:
        logger.error(f"[PluginAssistant] generate scaffold failed: {e}")
        return _err(ERR_ASSISTANT_FAILED, f"生成脚手架失败: {e}")
    return _ok(data=scaffold.to_dict(), message="Scaffold generated")


@router.post("/plugins/assistant/scaffold/write", response_model=ApiResponse)
async def write_scaffold(req: ScaffoldWriteRequest) -> ApiResponse:
    """将已生成的脚手架写入 plugins/ 目录。

    需先调用 /scaffold/generate 生成脚手架，本接口根据 plugin_id 从历史记录中读取。
    """
    scaffold_data = luominest_plugin_config_assistant.get_scaffold(req.plugin_id)
    if scaffold_data is None:
        return _err(ERR_ASSISTANT_INVALID, f"未找到脚手架记录: {req.plugin_id}")

    # 重建 CxPluginScaffold 对象
    from app.services.plugin_config_assistant import CxPluginScaffold
    scaffold = CxPluginScaffold(
        plugin_id=scaffold_data["plugin_id"],
        name=scaffold_data["name"],
        description=scaffold_data["description"],
        files=scaffold_data.get("files", {}),
        created_at=scaffold_data.get("created_at", ""),
        notes=scaffold_data.get("notes", []),
    )

    try:
        result = luominest_plugin_config_assistant.write_scaffold_to_disk(
            scaffold, overwrite=req.overwrite
        )
    except ValueError as e:
        msg = str(e)
        if "已存在" in msg:
            return _err(ERR_SCAFFOLD_EXISTS, msg)
        return _err(ERR_ASSISTANT_INVALID, msg)
    except Exception as e:
        logger.error(f"[PluginAssistant] write scaffold failed: {e}")
        return _err(ERR_ASSISTANT_FAILED, f"写入脚手架失败: {e}")
    return _ok(data=result, message="Scaffold written to disk")


@router.get("/plugins/assistant/scaffolds", response_model=ApiResponse)
async def list_scaffolds() -> ApiResponse:
    """列出所有历史脚手架记录。"""
    return _ok(data=luominest_plugin_config_assistant.list_scaffolds())


@router.get("/plugins/assistant/scaffolds/{plugin_id}", response_model=ApiResponse)
async def get_scaffold(plugin_id: str) -> ApiResponse:
    """获取单个历史脚手架详情。"""
    data = luominest_plugin_config_assistant.get_scaffold(plugin_id)
    if data is None:
        return _err(ERR_PLUGIN_NOT_FOUND, f"Scaffold not found: {plugin_id}")
    return _ok(data=data)
