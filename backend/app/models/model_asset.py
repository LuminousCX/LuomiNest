import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean, DateTime, ForeignKey, JSON, Enum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class ModelType(str, PyEnum):
    LIVE2D = "live2d"
    BLENDER = "blender"
    VAM = "vam"
    VRM = "vrm"


class ModelStatus(str, PyEnum):
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"
    ARCHIVED = "archived"


class Model(Base):
    __tablename__ = "models"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_type: Mapped[ModelType] = mapped_column(Enum(ModelType), nullable=False)
    status: Mapped[ModelStatus] = mapped_column(Enum(ModelStatus), default=ModelStatus.UPLOADING)

    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)

    thumbnail_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)

    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    configurations: Mapped[list["ModelConfiguration"]] = relationship(
        back_populates="model", cascade="all, delete-orphan"
    )
    animations: Mapped[list["ModelAnimation"]] = relationship(
        back_populates="model", cascade="all, delete-orphan"
    )
    interactions: Mapped[list["ModelInteraction"]] = relationship(
        back_populates="model", cascade="all, delete-orphan"
    )
    versions: Mapped[list["ModelVersion"]] = relationship(
        back_populates="model", cascade="all, delete-orphan"
    )


class ModelConfiguration(Base):
    __tablename__ = "model_configurations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    model_id: Mapped[str] = mapped_column(String(36), ForeignKey("models.id", ondelete="CASCADE"), nullable=False)

    config_name: Mapped[str] = mapped_column(String(255), nullable=False)
    config_type: Mapped[str] = mapped_column(String(50), nullable=False)

    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    properties: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    animation_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    render_settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    physics_settings: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    model: Mapped["Model"] = relationship(back_populates="configurations")


class ModelAnimation(Base):
    __tablename__ = "model_animations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    model_id: Mapped[str] = mapped_column(String(36), ForeignKey("models.id", ondelete="CASCADE"), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    group: Mapped[str | None] = mapped_column(String(100), nullable=True)
    duration: Mapped[float] = mapped_column(Float, default=0.0)
    fps: Mapped[int] = mapped_column(Integer, default=30)
    loop: Mapped[bool] = mapped_column(Boolean, default=False)

    trigger_type: Mapped[str] = mapped_column(String(50), default="manual")
    trigger_condition: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    blend_mode: Mapped[str] = mapped_column(String(30), default="override")
    blend_weight: Mapped[float] = mapped_column(Float, default=1.0)

    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    model: Mapped["Model"] = relationship(back_populates="animations")


class ModelInteraction(Base):
    __tablename__ = "model_interactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    model_id: Mapped[str] = mapped_column(String(36), ForeignKey("models.id", ondelete="CASCADE"), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    interaction_type: Mapped[str] = mapped_column(String(50), nullable=False)

    trigger_event: Mapped[str] = mapped_column(String(100), nullable=False)
    target_parameter: Mapped[str] = mapped_column(String(255), nullable=False)
    response_curve: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    min_value: Mapped[float] = mapped_column(Float, default=0.0)
    max_value: Mapped[float] = mapped_column(Float, default=1.0)
    default_value: Mapped[float] = mapped_column(Float, default=0.0)

    cooldown_ms: Mapped[int] = mapped_column(Integer, default=0)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    model: Mapped["Model"] = relationship(back_populates="interactions")


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    model_id: Mapped[str] = mapped_column(String(36), ForeignKey("models.id", ondelete="CASCADE"), nullable=False)

    version: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    change_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    configuration_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    model: Mapped["Model"] = relationship(back_populates="versions")
