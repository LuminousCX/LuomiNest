from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ModelType(str, Enum):
    LIVE2D = "live2d"
    BLENDER = "blender"
    VAM = "vam"
    VRM = "vrm"


class ModelStatus(str, Enum):
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"
    ARCHIVED = "archived"


class TriggerType(str, Enum):
    MANUAL = "manual"
    AUTO = "auto"
    EVENT = "event"
    IDLE = "idle"
    EMOTION = "emotion"


class BlendMode(str, Enum):
    OVERRIDE = "override"
    ADD = "add"
    MIX = "mix"


class InteractionType(str, Enum):
    TAP = "tap"
    DRAG = "drag"
    PINCH = "pinch"
    HOVER = "hover"
    VOICE = "voice"
    MOTION = "motion"


class ModelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    model_type: ModelType
    tags: list[str] | None = None
    is_public: bool = False


class ModelUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    tags: list[str] | None = None
    is_public: bool | None = None
    status: ModelStatus | None = None


class ModelResponse(BaseModel):
    id: str
    name: str
    description: str | None
    model_type: ModelType
    status: ModelStatus
    file_size: int
    file_hash: str | None
    original_filename: str
    thumbnail_path: str | None
    version: int
    metadata_json: dict | None
    tags: list[str] | None
    user_id: str | None
    is_public: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ModelListResponse(BaseModel):
    items: list[ModelResponse]
    total: int
    page: int
    page_size: int


class Live2DMetadata(BaseModel):
    version: int | None = None
    model_name: str | None = None
    texture_count: int = 0
    expression_count: int = 0
    motion_groups: list[str] = Field(default_factory=list)
    physics_enabled: bool = False
    canvas_width: int = 0
    canvas_height: int = 0


class BlenderMetadata(BaseModel):
    blender_version: str | None = None
    object_count: int = 0
    mesh_count: int = 0
    material_count: int = 0
    animation_count: int = 0
    armature_count: int = 0
    vertex_count: int = 0
    face_count: int = 0
    has_shape_keys: bool = False
    has_uv_maps: bool = False


class VAMMetadata(BaseModel):
    vam_version: str | None = None
    author: str | None = None
    category: str | None = None
    clothing_items: int = 0
    morph_count: int = 0
    texture_resolution: str | None = None
    plugin_dependencies: list[str] = Field(default_factory=list)


class ConfigurationCreate(BaseModel):
    config_name: str = Field(..., min_length=1, max_length=255)
    config_type: str = Field(..., min_length=1, max_length=50)
    display_name: str | None = None
    description: str | None = None
    properties: dict | None = None
    animation_params: dict | None = None
    render_settings: dict | None = None
    physics_settings: dict | None = None
    is_default: bool = False


class ConfigurationUpdate(BaseModel):
    config_name: str | None = Field(None, min_length=1, max_length=255)
    display_name: str | None = None
    description: str | None = None
    properties: dict | None = None
    animation_params: dict | None = None
    render_settings: dict | None = None
    physics_settings: dict | None = None
    is_active: bool | None = None
    is_default: bool | None = None


class ConfigurationResponse(BaseModel):
    id: str
    model_id: str
    config_name: str
    config_type: str
    display_name: str | None
    description: str | None
    properties: dict | None
    animation_params: dict | None
    render_settings: dict | None
    physics_settings: dict | None
    is_active: bool
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AnimationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    group: str | None = None
    duration: float = 0.0
    fps: int = 30
    loop: bool = False
    trigger_type: TriggerType = TriggerType.MANUAL
    trigger_condition: dict | None = None
    blend_mode: BlendMode = BlendMode.OVERRIDE
    blend_weight: float = Field(1.0, ge=0.0, le=1.0)
    metadata_json: dict | None = None
    sort_order: int = 0
    is_enabled: bool = True


class AnimationUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    group: str | None = None
    duration: float | None = None
    fps: int | None = None
    loop: bool | None = None
    trigger_type: TriggerType | None = None
    trigger_condition: dict | None = None
    blend_mode: BlendMode | None = None
    blend_weight: float | None = Field(None, ge=0.0, le=1.0)
    metadata_json: dict | None = None
    sort_order: int | None = None
    is_enabled: bool | None = None


class AnimationResponse(BaseModel):
    id: str
    model_id: str
    name: str
    group: str | None
    duration: float
    fps: int
    loop: bool
    trigger_type: str
    trigger_condition: dict | None
    blend_mode: str
    blend_weight: float
    metadata_json: dict | None
    sort_order: int
    is_enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class InteractionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    interaction_type: InteractionType
    trigger_event: str = Field(..., min_length=1, max_length=100)
    target_parameter: str = Field(..., min_length=1, max_length=255)
    response_curve: dict | None = None
    min_value: float = 0.0
    max_value: float = 1.0
    default_value: float = 0.0
    cooldown_ms: int = 0
    priority: int = 0
    is_enabled: bool = True


class InteractionUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    interaction_type: InteractionType | None = None
    trigger_event: str | None = None
    target_parameter: str | None = None
    response_curve: dict | None = None
    min_value: float | None = None
    max_value: float | None = None
    default_value: float | None = None
    cooldown_ms: int | None = None
    priority: int | None = None
    is_enabled: bool | None = None


class InteractionResponse(BaseModel):
    id: str
    model_id: str
    name: str
    interaction_type: str
    trigger_event: str
    target_parameter: str
    response_curve: dict | None
    min_value: float
    max_value: float
    default_value: float
    cooldown_ms: int
    priority: int
    is_enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class VersionResponse(BaseModel):
    id: str
    model_id: str
    version: int
    file_path: str
    file_size: int
    file_hash: str
    change_log: str | None
    configuration_snapshot: dict | None
    created_at: datetime
    created_by: str | None

    model_config = {"from_attributes": True}


class ModelParseResult(BaseModel):
    model_type: ModelType
    name: str | None = None
    metadata: dict
    animations: list[dict] = Field(default_factory=list)
    parameters: list[dict] = Field(default_factory=list)
    expressions: list[dict] = Field(default_factory=list)
    physics_groups: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PreviewRequest(BaseModel):
    model_id: str
    configuration_id: str | None = None
    animation_id: str | None = None
    emotion_state: dict | None = None
    viewport: dict | None = None


class PreviewResponse(BaseModel):
    model_id: str
    render_url: str
    thumbnail_url: str | None = None
    metadata: dict | None = None
