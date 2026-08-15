"""LuomiNest Avatar REST API endpoints.

提供模型清单查询、绑定更新、模型导入/删除等接口。

设计原则：
- 所有响应统一使用 ApiResponse 格式（含 code/message/data），遵循项目规则
- 错误码：0=成功，1xxx=客户端错误，2xxx=服务端错误
- 路由前缀 /avatar，挂在 /api/v1/avatar
"""
from __future__ import annotations

import time
from fastapi import APIRouter, UploadFile, File, Form, Query
from loguru import logger

from app.schemas.avatar import (
    AvatarManifest,
    AvatarManifestModel,
    AvatarBinding,
    AvatarBindingUpdate,
    AvatarEmotionMapRequest,
    AvatarImportRequest,
    AvatarType,
    ApiResponse,
)
from app.services.avatar_manifest import (
    avatar_manifest_manager,
    get_avatar_manifest_manager,
)


router = APIRouter(prefix="/avatar", tags=["avatar"])


# ---------------------------------------------------------------------------
# 错误码常量
# ---------------------------------------------------------------------------

ERR_MODEL_NOT_FOUND = 1001
ERR_MODEL_EXISTS = 1002
ERR_INVALID_TYPE = 1003
ERR_IMPORT_FAILED = 1004
ERR_DELETE_FAILED = 1005
ERR_BINDING_NOT_FOUND = 1006


def _ok(data=None, message: str = "ok") -> ApiResponse:
    return ApiResponse(code=0, message=message, data=data)


def _err(code: int, message: str) -> ApiResponse:
    return ApiResponse(code=code, message=message, data=None)


# ---------------------------------------------------------------------------
# Manifest 查询
# ---------------------------------------------------------------------------

@router.get("/manifest", response_model=ApiResponse)
async def get_manifest() -> ApiResponse:
    """获取完整 manifest（builtin + imported）。"""
    manifest = await avatar_manifest_manager.get_full_manifest()
    return _ok(data=manifest.model_dump())


@router.get("/models", response_model=ApiResponse)
async def list_models(
    type: AvatarType | None = Query(None, description="按类型过滤"),
    source: str | None = Query(None, description="按来源过滤（builtin/imported）"),
) -> ApiResponse:
    """列出所有模型，支持按 type/source 过滤。"""
    models = await avatar_manifest_manager.list_models(type_filter=type, source_filter=source)
    return _ok(data=[m.model_dump() for m in models])


@router.get("/models/{model_id}", response_model=ApiResponse)
async def get_model(model_id: str) -> ApiResponse:
    """获取单个模型详情。"""
    model = await avatar_manifest_manager.get_model(model_id)
    if not model:
        return _err(ERR_MODEL_NOT_FOUND, f"Model not found: {model_id}")
    return _ok(data=model.model_dump())


@router.get("/models/{model_id}/capabilities", response_model=ApiResponse)
async def get_capabilities(model_id: str) -> ApiResponse:
    """查询模型能力（表情/动作/viseme 等）。"""
    model = await avatar_manifest_manager.get_model(model_id)
    if not model:
        return _err(ERR_MODEL_NOT_FOUND, f"Model not found: {model_id}")
    return _ok(data=model.capabilities.model_dump())


@router.get("/models/{model_id}/binding", response_model=ApiResponse)
async def get_binding(model_id: str) -> ApiResponse:
    """获取模型绑定（voice + expression_map）。"""
    binding = await avatar_manifest_manager.get_binding(model_id)
    if not binding:
        return _err(ERR_BINDING_NOT_FOUND, f"Binding not found for model: {model_id}")
    return _ok(data=binding.model_dump())


# ---------------------------------------------------------------------------
# Binding 更新
# ---------------------------------------------------------------------------

@router.put("/models/{model_id}/binding", response_model=ApiResponse)
async def update_binding(model_id: str, update: AvatarBindingUpdate) -> ApiResponse:
    """更新模型绑定配置。

    builtin 模型通过 override 保留（不修改原 manifest 文件），
    imported 模型直接修改持久化文件。
    """
    # 先检查模型存在
    model = await avatar_manifest_manager.get_model(model_id)
    if not model:
        return _err(ERR_MODEL_NOT_FOUND, f"Model not found: {model_id}")

    updated = await avatar_manifest_manager.update_binding(model_id, update)
    if not updated:
        return _err(ERR_BINDING_NOT_FOUND, f"Failed to update binding for: {model_id}")
    return _ok(data=updated.model_dump(), message="Binding updated")


@router.post("/emotion-map", response_model=ApiResponse)
async def set_emotion_map(req: AvatarEmotionMapRequest) -> ApiResponse:
    """提交 emotion → expression 映射配置。

    等价于 update_binding 的 expression_map 字段，提供独立端点便于前端调用。
    """
    model = await avatar_manifest_manager.get_model(req.model_id)
    if not model:
        return _err(ERR_MODEL_NOT_FOUND, f"Model not found: {req.model_id}")

    update = AvatarBindingUpdate(expression_map=req.expression_map)
    updated = await avatar_manifest_manager.update_binding(req.model_id, update)
    if not updated:
        return _err(ERR_BINDING_NOT_FOUND, f"Failed to set emotion map for: {req.model_id}")
    return _ok(data=updated.model_dump(), message="Emotion map updated")


# ---------------------------------------------------------------------------
# 模型导入/删除
# ---------------------------------------------------------------------------

@router.post("/import", response_model=ApiResponse)
async def import_model(
    name: str = Form(..., description="模型显示名称"),
    type: AvatarType = Form(..., description="模型类型"),
    tags: str = Form("", description="标签（逗号分隔）"),
    file: UploadFile = File(..., description="模型文件（zip 或单文件）"),
) -> ApiResponse:
    """导入用户模型文件。

    实际文件落盘由前端 Electron 处理（通过 luominest-avatar:// 协议提供），
    后端只接收元数据并登记到 imported-manifest.json。
    此端点接收 multipart 上传，落盘到 userData/avatar/{type}/ 并追加 manifest 条目。

    注意：Electron 桌面端通常通过 IPC 直接管理文件，不走 HTTP；此端点主要为
    Web 模式（未来）和后端独立运行场景提供。
    """
    if not name or not type:
        return _err(ERR_INVALID_TYPE, "name and type are required")

    try:
        # 生成模型 ID
        safe_name = "".join(c for c in name if c.isalnum() or c in "-_").lower() or "imported"
        model_id = f"imported-{type}-{safe_name}-{int(time.time())}"
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

        # 读取文件内容并落盘（简化版：仅记录元数据，实际文件处理由前端完成）
        # 这里只生成 manifest 条目，文件由调用方自行上传
        content = await file.read()
        if not content:
            return _err(ERR_IMPORT_FAILED, "Empty file")

        # 构造 manifest 条目（path 由前端 IPC 上报后通过单独 API 更新）
        model = AvatarManifestModel(
            id=model_id,
            name=name,
            type=type,
            version="1.0",
            source="imported",
            path=f"{type}/{safe_name}/",  # 占位路径，前端 IPC 上报后修正
            thumbnail=None,
            tags=tag_list,
            capabilities={},  # 由前端扫描后上报
            binding=None,
        )

        ok = await avatar_manifest_manager.add_imported_model(model)
        if not ok:
            return _err(ERR_MODEL_EXISTS, f"Model ID conflict: {model_id}")

        logger.info(f"[AvatarAPI] Model imported: {model_id} ({type}, {len(content)} bytes)")
        return _ok(data=model.model_dump(), message="Model imported")

    except Exception as e:
        logger.error(f"[AvatarAPI] Import failed: {e}", exc_info=True)
        return _err(ERR_IMPORT_FAILED, f"Import failed: {e}")


@router.delete("/models/{model_id}", response_model=ApiResponse)
async def delete_model(model_id: str) -> ApiResponse:
    """删除导入的模型（builtin 不可删）。"""
    # 检查模型存在
    model = await avatar_manifest_manager.get_model(model_id)
    if not model:
        return _err(ERR_MODEL_NOT_FOUND, f"Model not found: {model_id}")

    if model.source == "builtin":
        return _err(ERR_DELETE_FAILED, "Cannot delete builtin model")

    ok = await avatar_manifest_manager.delete_model(model_id)
    if not ok:
        return _err(ERR_DELETE_FAILED, f"Failed to delete: {model_id}")
    return _ok(message="Model deleted")


# ---------------------------------------------------------------------------
# 供 avatar_manager.py 同步回退使用的辅助函数
# ---------------------------------------------------------------------------

def _sync_get_binding_fallback(model_id: str) -> AvatarBinding | None:
    """同步版 get_avatar_binding 回退。

    用于 chat_service 等不能 await 的场景。从内存中读取已初始化的 manifest。
    若 manifest 未初始化（lifespan 未完成），返回 None（chat_service 会跳过 binding）。
    """
    mgr = get_avatar_manifest_manager()
    if not mgr._initialized:  # noqa: SLF001
        return None
    # 同步遍历内存 manifest
    for m in list(mgr._builtin_manifest.models) + list(mgr._imported_manifest.models):  # noqa: SLF001
        if m.id == model_id:
            if m.id in mgr._binding_overrides:  # noqa: SLF001
                return mgr._binding_overrides[m.id]  # noqa: SLF001
            return m.binding
    return None
