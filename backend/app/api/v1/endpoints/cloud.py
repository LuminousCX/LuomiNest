"""云路由注入 API 端点（M4）。

桌面端（Electron main）在授权成功与每次令牌续期后，将云端接入信息注入本机后端：
- PUT /cloud/token：注入 {accessToken, cloudBaseUrl, routingMode[, models]} →
  CloudTokenStore（仅内存）；models 为云端从站模型目录（可选，向后兼容：
  旧 payload 不带 models 照常工作，adapter 对空目录不做 model 替换）
- GET /cloud/status：查询注入状态（绝不回显完整令牌，只回传末 4 位用于界面比对）

隐私纪律：cloudBaseUrl 只来自运行时注入；本模块不含任何生产端点/域名/密钥信息。
受全局认证中间件保护（与其它 /api/v1 端点一致，桌面端带本地 Bearer 调用）。
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from app.core.utils import ok
from app.runtime.provider.llm.cloud_store import cloud_token_store

router = APIRouter(prefix="/cloud", tags=["cloud"])


# ── Pydantic 请求模型 ──────────────────────────────────────────────────────────

# 桌面端注入协议字段为 camelCase（accessToken/cloudBaseUrl/routingMode），经 alias 映射
CloudRoutingMode = Literal["off", "all"]


class CloudModelRef(BaseModel):
    """云端从站模型目录条目（GET {cloudBaseUrl}/api/v1/llm/models 的 modelId/displayName 子集）。"""

    model_config = ConfigDict(populate_by_name=True)

    model_id: str = Field(
        ..., min_length=1, alias="modelId",
        description="云端模型 ID（chat 请求的 model 必须精确命中该值）",
    )
    display_name: str = Field(
        "", alias="displayName",
        description="云端模型展示名",
    )


class CloudTokenRequest(BaseModel):
    access_token: str = Field(
        ..., min_length=1, alias="accessToken",
        description="云端访问令牌（轮换期约 30 分钟，勿落盘）",
    )
    cloud_base_url: str = Field(
        ..., min_length=1, alias="cloudBaseUrl",
        description="云端网关根地址（运行时注入，不落盘）",
    )
    routing_mode: CloudRoutingMode = Field(
        "off", alias="routingMode",
        description="路由模式：off=本地；all=chat 类调用走云端",
    )
    models: list[CloudModelRef] | None = Field(
        None,
        description="云端从站模型目录（可选；缺省按空目录处理，旧 payload 向后兼容）",
    )


# ── 端点 ───────────────────────────────────────────────────────────────────────

@router.put("/token")
async def set_cloud_token(req: CloudTokenRequest):
    """注入/覆盖云端令牌（桌面端在授权与每次续期后调用；重启后重新注入）。"""
    models = [m.model_dump(by_alias=True) for m in req.models] if req.models else []
    cloud_token_store.set(req.access_token, req.cloud_base_url, req.routing_mode, models=models)
    logger.info(
        f"[Cloud] Token injected: mode={req.routing_mode}, baseUrl={req.cloud_base_url}, "
        f"token=***{req.access_token[-4:]}, models={len(models)}"
    )
    return ok({"configured": True, "routingMode": req.routing_mode})


@router.get("/status")
async def cloud_status():
    """查询云路由状态（令牌只回传末 4 位，绝不回显完整值）。"""
    snapshot = cloud_token_store.get()
    configured = cloud_token_store.configured
    token = snapshot["accessToken"]
    return ok({
        "configured": configured,
        "routingMode": snapshot["routingMode"],
        "cloudBaseUrl": snapshot["cloudBaseUrl"] if configured else None,
        "tokenTail4": token[-4:] if configured else None,
    })
