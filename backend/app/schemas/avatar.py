"""LuomiNest Avatar 多模型驱动协议 schemas.

定义统一的模型驱动协议（emotion_drive JSON Schema），适配 Live2D / VRM /
Pixel / Spine / PNG Tuber 等所有模型类型。

设计原则：
- 与现有 ChatStreamChunk.emotion 字段解耦：emotion_drive 是更高层的封装，
  ChatStreamChunk.emotion 仍只承载 LLM 输出的离散表情 ID，由 chat_service
  通过 EmotionStreamParser 解析得到。
- emotion_drive 协议是可选的实时驱动通道，用于非 chat 来源（如摄像头追踪、
  语音情感分析、AI 自主行为）的模型驱动推送。
- 前端优先消费 chat stream emotion，可选订阅 /avatar/drive WebSocket 获取
  额外模态。
"""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 模型能力声明
# ---------------------------------------------------------------------------

class AvatarCapability(BaseModel):
    """模型能力声明。

    不同模型类型支持的能力不同，前端根据 capabilities 决定调用哪些驱动接口。
    不支持的能力调用会被渲染器静默忽略（no-op）。
    """
    expressions: list[str] = Field(default_factory=list, description="支持的表情 ID 列表")
    motions: list[str] = Field(default_factory=list, description="支持的动作组列表")
    states: list[str] | None = Field(None, description="像素模型支持的状态列表")
    visemes: list[str] | None = Field(None, description="VRM 模型支持的 viseme 列表")
    lip_sync: bool = Field(False, description="是否支持口型同步")
    focus_tracking: bool = Field(False, description="是否支持焦点追踪（鼠标/摄像头）")
    pad_emotion: bool = Field(False, description="是否支持 PAD 连续情感驱动")
    custom_params: list[str] | None = Field(None, description="可直设的参数 ID 列表")


# ---------------------------------------------------------------------------
# 模型绑定（voice + expression_map）
# ---------------------------------------------------------------------------

class AvatarBinding(BaseModel):
    """模型绑定配置：voice / expression_map / default_expression.

    expression_map 把 12 个语义 emotion ID 映射到当前模型的原生表情名。
    前后端共享同一份 manifest，消除历史前后端 binding 不一致问题。
    """
    voice: str = Field("zh-CN-XiaoxiaoNeural", description="TTS 语音 ID")
    voice_lang: str = Field("zh", description="语音语言代码")
    expression_map: dict[str, str] = Field(default_factory=dict, description="emotion → expression 映射")
    default_expression: str = Field("neutral", description="默认表情")


# ---------------------------------------------------------------------------
# 模型清单条目
# ---------------------------------------------------------------------------

AvatarType = Literal["live2d", "vrm", "pixel", "spine", "png"]
AvatarSource = Literal["builtin", "imported"]


class AvatarManifestModel(BaseModel):
    """manifest.json 中单个模型条目。"""
    id: str = Field(..., description="模型唯一 ID（如 builtin-live2d-llny）")
    name: str = Field(..., description="显示名称")
    type: AvatarType = Field(..., description="模型类型")
    version: str = Field("1.0", description="模型版本（如 cubism4 / 1.0）")
    source: AvatarSource = Field("builtin", description="来源：内置或导入")
    path: str = Field(..., description="模型文件相对路径")
    thumbnail: str | None = Field(None, description="缩略图相对路径")
    tags: list[str] = Field(default_factory=list, description="标签列表")
    capabilities: AvatarCapability = Field(default_factory=AvatarCapability)
    binding: AvatarBinding | None = Field(None, description="voice + expression_map 绑定")


class AvatarManifest(BaseModel):
    """完整 manifest 文件结构。"""
    schema_version: str = Field("1.0", description="manifest schema 版本")
    models: list[AvatarManifestModel] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 统一驱动协议（emotion_drive）
# ---------------------------------------------------------------------------

class PadEmotion(BaseModel):
    """PAD 情感模型：Pleasure-Arousal-Dominance 三维连续值。

    每个维度范围 [-1, 1]：
    - Pleasure（愉悦度）：负向情绪 ↔ 正向情绪
    - Arousal（唤醒度）：平静 ↔ 激动
    - Dominance（支配度）：顺从 ↔ 主导
    """
    p: float = Field(0.0, ge=-1.0, le=1.0)
    a: float = Field(0.0, ge=-1.0, le=1.0)
    d: float = Field(0.0, ge=-1.0, le=1.0)


class AvatarDriveData(BaseModel):
    """emotion_drive 数据载荷。

    所有字段可选，渲染器只消费支持的字段。例如像素模型只消费 emotion，忽略
    pad / viseme / params。
    """
    emotion: str | None = Field(None, description="离散表情 ID（来自 SUPPORTED_EMOTION_IDS）")
    pad: PadEmotion | None = Field(None, description="PAD 连续情感值")
    action: str | None = Field(None, description="动作名（如 TapBody / wave）")
    lip_sync: float | None = Field(None, ge=0.0, le=1.0, description="口型开合值 0-1")
    viseme: str | None = Field(None, description="VRM viseme（AA/IH/OU/EE/OH 等）")
    params: dict[str, float] | None = Field(None, description="直设参数（如 ParamAngleX）")


class AvatarDrivePacket(BaseModel):
    """emotion_drive 协议包：通过 /avatar/drive WebSocket 推送。"""
    type: Literal["emotion_drive"] = "emotion_drive"
    timestamp: int = Field(..., description="毫秒级时间戳")
    data: AvatarDriveData


# ---------------------------------------------------------------------------
# WebSocket 控制消息
# ---------------------------------------------------------------------------

class AvatarDriveSubscribe(BaseModel):
    """客户端订阅驱动推送。"""
    type: Literal["subscribe"] = "subscribe"
    model_id: str = Field(..., description="要订阅的模型 ID")


class AvatarDriveUnsubscribe(BaseModel):
    """客户端取消订阅。"""
    type: Literal["unsubscribe"] = "unsubscribe"


# ---------------------------------------------------------------------------
# API 请求/响应
# ---------------------------------------------------------------------------

class AvatarBindingUpdate(BaseModel):
    """更新模型绑定请求体。"""
    voice: str | None = None
    voice_lang: str | None = None
    expression_map: dict[str, str] | None = None
    default_expression: str | None = None


class AvatarEmotionMapRequest(BaseModel):
    """提交 emotion → expression 映射配置请求。"""
    model_id: str
    expression_map: dict[str, str]


class AvatarImportRequest(BaseModel):
    """导入模型元数据（实际上传通过 multipart/form-data）。"""
    name: str
    type: AvatarType
    tags: list[str] = Field(default_factory=list)


class ApiResponse(BaseModel):
    """统一 API 响应格式（含错误码）。

    遵循项目规则：API 响应必须包含错误码。
    """
    code: int = Field(0, description="错误码，0 表示成功")
    message: str = Field("ok", description="错误描述")
    data: Any | None = Field(None, description="业务数据")
