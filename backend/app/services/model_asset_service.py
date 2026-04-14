import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model_asset import (
    Model, ModelConfiguration, ModelAnimation, ModelInteraction, ModelVersion,
    ModelStatus, ModelType,
)
from app.schemas.model_asset import (
    ModelCreate, ModelUpdate, ModelResponse, ModelListResponse,
    ConfigurationCreate, ConfigurationUpdate, ConfigurationResponse,
    AnimationCreate, AnimationUpdate, AnimationResponse,
    InteractionCreate, InteractionUpdate, InteractionResponse,
    VersionResponse, ModelParseResult, PreviewRequest, PreviewResponse,
)
from app.engines.render.parsers import registry as parser_registry
from app.services.model_storage import storage_manager, cache_manager


class ModelAssetService:
    async def import_model(
        self,
        db: AsyncSession,
        temp_file_path: Path,
        original_filename: str,
        create_data: ModelCreate,
        user_id: Optional[str] = None,
    ) -> ModelResponse:
        model_id = str(uuid.uuid4())

        file_hash = await self._compute_file_hash(temp_file_path)
        file_size = temp_file_path.stat().st_size

        model_type = ModelType(create_data.model_type.value)
        parse_result = await parser_registry.parse(temp_file_path, model_type)

        saved_path = await storage_manager.save_upload(
            temp_file_path, model_id, original_filename
        )

        try:
            model = Model(
                id=model_id,
                name=create_data.name or parse_result.name or original_filename,
                description=create_data.description,
                model_type=model_type,
                status=ModelStatus.READY,
                file_path=saved_path,
                file_size=file_size,
                file_hash=file_hash,
                original_filename=original_filename,
                version=1,
                metadata_json=parse_result.metadata,
                tags=create_data.tags,
                user_id=user_id,
                is_public=create_data.is_public,
            )

            db.add(model)

            for anim_data in parse_result.animations:
                animation = ModelAnimation(
                    id=str(uuid.uuid4()),
                    model_id=model_id,
                    name=anim_data.get("name", "unnamed"),
                    group=anim_data.get("group"),
                    duration=anim_data.get("duration", 0.0),
                    fps=anim_data.get("fps", 30),
                    loop=anim_data.get("loop", False),
                    trigger_type=anim_data.get("trigger_type", "manual"),
                    metadata_json=anim_data,
                    sort_order=0,
                    is_enabled=True,
                )
                db.add(animation)

            default_config = ModelConfiguration(
                id=str(uuid.uuid4()),
                model_id=model_id,
                config_name="default",
                config_type=model_type.value,
                display_name="默认配置",
                description="自动生成的默认配置",
                properties=self._build_default_properties(model_type, parse_result),
                animation_params=self._build_default_animation_params(model_type, parse_result),
                render_settings=self._build_default_render_settings(model_type),
                physics_settings=self._build_default_physics_settings(model_type, parse_result),
                is_active=True,
                is_default=True,
            )
            db.add(default_config)

            version_info = await storage_manager.create_version(
                model_id, saved_path, 1, "Initial import"
            )
            version = ModelVersion(
                id=str(uuid.uuid4()),
                model_id=model_id,
                version=1,
                file_path=version_info["file_path"],
                file_size=version_info["file_size"],
                file_hash=version_info["file_hash"],
                change_log="Initial import",
                created_by=user_id,
            )
            db.add(version)

            await db.commit()
            await db.refresh(model)

            cache_manager.invalidate_pattern(f"model_list:")
            logger.info(f"Imported model: {model_id} ({model_type.value})")

            return ModelResponse.model_validate(model)
        except Exception as e:
            await db.rollback()
            await storage_manager.delete_model_files(model_id)
            logger.error(f"Failed to import model {model_id}: {e}")
            raise

    async def list_models(
        self,
        db: AsyncSession,
        model_type: Optional[ModelType] = None,
        status: Optional[ModelStatus] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ModelListResponse:
        query = select(Model)

        if model_type:
            query = query.where(Model.model_type == model_type)
        if status:
            query = query.where(Model.status == status)
        if search:
            query = query.where(Model.name.ilike(f"%{search}%"))

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.offset((page - 1) * page_size).limit(page_size).order_by(Model.updated_at.desc())
        result = await db.execute(query)
        models = result.scalars().all()

        return ModelListResponse(
            items=[ModelResponse.model_validate(m) for m in models],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_model(self, db: AsyncSession, model_id: str) -> Optional[ModelResponse]:
        cache_key = f"model:{model_id}"
        cached = cache_manager.get(cache_key)
        if cached:
            return ModelResponse(**cached)

        result = await db.execute(select(Model).where(Model.id == model_id))
        model = result.scalar_one_or_none()
        if model is None:
            return None

        response = ModelResponse.model_validate(model)
        cache_manager.set(cache_key, response.model_dump())
        return response

    async def update_model(
        self, db: AsyncSession, model_id: str, update_data: ModelUpdate
    ) -> Optional[ModelResponse]:
        result = await db.execute(select(Model).where(Model.id == model_id))
        model = result.scalar_one_or_none()
        if model is None:
            return None

        if update_data.name is not None:
            model.name = update_data.name
        if update_data.description is not None:
            model.description = update_data.description
        if update_data.tags is not None:
            model.tags = update_data.tags
        if update_data.is_public is not None:
            model.is_public = update_data.is_public
        if update_data.status is not None:
            model.status = ModelStatus(update_data.status.value)
        model.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(model)

        cache_manager.delete(f"model:{model_id}")
        cache_manager.invalidate_pattern("model_list:")

        return ModelResponse.model_validate(model)

    async def delete_model(self, db: AsyncSession, model_id: str) -> bool:
        result = await db.execute(select(Model).where(Model.id == model_id))
        model = result.scalar_one_or_none()
        if model is None:
            return False

        await db.delete(model)
        await db.commit()

        await storage_manager.delete_model_files(model_id)
        cache_manager.delete(f"model:{model_id}")
        cache_manager.invalidate_pattern("model_list:")

        logger.info(f"Deleted model: {model_id}")
        return True

    async def get_configurations(
        self, db: AsyncSession, model_id: str
    ) -> list[ConfigurationResponse]:
        result = await db.execute(
            select(ModelConfiguration).where(ModelConfiguration.model_id == model_id)
        )
        configs = result.scalars().all()
        return [ConfigurationResponse.model_validate(c) for c in configs]

    async def create_configuration(
        self, db: AsyncSession, model_id: str, data: ConfigurationCreate
    ) -> Optional[ConfigurationResponse]:
        model_result = await db.execute(select(Model).where(Model.id == model_id))
        if model_result.scalar_one_or_none() is None:
            return None

        config = ModelConfiguration(
            id=str(uuid.uuid4()),
            model_id=model_id,
            config_name=data.config_name,
            config_type=data.config_type,
            display_name=data.display_name,
            description=data.description,
            properties=data.properties,
            animation_params=data.animation_params,
            render_settings=data.render_settings,
            physics_settings=data.physics_settings,
            is_default=data.is_default,
        )

        if data.is_default:
            await db.execute(
                update(ModelConfiguration)
                .where(ModelConfiguration.model_id == model_id)
                .values(is_default=False)
            )

        db.add(config)
        await db.commit()
        await db.refresh(config)

        cache_manager.invalidate_pattern(f"model:{model_id}")
        return ConfigurationResponse.model_validate(config)

    async def update_configuration(
        self, db: AsyncSession, config_id: str, data: ConfigurationUpdate
    ) -> Optional[ConfigurationResponse]:
        result = await db.execute(
            select(ModelConfiguration).where(ModelConfiguration.id == config_id)
        )
        config = result.scalar_one_or_none()
        if config is None:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(config, field, value)
        config.updated_at = datetime.utcnow()

        if data.is_default is True:
            await db.execute(
                update(ModelConfiguration)
                .where(ModelConfiguration.model_id == config.model_id)
                .where(ModelConfiguration.id != config_id)
                .values(is_default=False)
            )

        await db.commit()
        await db.refresh(config)

        cache_manager.invalidate_pattern(f"model:{config.model_id}")
        return ConfigurationResponse.model_validate(config)

    async def delete_configuration(self, db: AsyncSession, config_id: str) -> bool:
        result = await db.execute(
            select(ModelConfiguration).where(ModelConfiguration.id == config_id)
        )
        config = result.scalar_one_or_none()
        if config is None:
            return False

        model_id = config.model_id
        await db.delete(config)
        await db.commit()

        cache_manager.invalidate_pattern(f"model:{model_id}")
        return True

    async def get_animations(
        self, db: AsyncSession, model_id: str
    ) -> list[AnimationResponse]:
        result = await db.execute(
            select(ModelAnimation)
            .where(ModelAnimation.model_id == model_id)
            .order_by(ModelAnimation.sort_order, ModelAnimation.name)
        )
        animations = result.scalars().all()
        return [AnimationResponse.model_validate(a) for a in animations]

    async def create_animation(
        self, db: AsyncSession, model_id: str, data: AnimationCreate
    ) -> Optional[AnimationResponse]:
        model_result = await db.execute(select(Model).where(Model.id == model_id))
        if model_result.scalar_one_or_none() is None:
            return None

        animation = ModelAnimation(
            id=str(uuid.uuid4()),
            model_id=model_id,
            name=data.name,
            group=data.group,
            duration=data.duration,
            fps=data.fps,
            loop=data.loop,
            trigger_type=data.trigger_type.value,
            trigger_condition=data.trigger_condition,
            blend_mode=data.blend_mode.value,
            blend_weight=data.blend_weight,
            metadata_json=data.metadata_json,
            sort_order=data.sort_order,
            is_enabled=data.is_enabled,
        )

        db.add(animation)
        await db.commit()
        await db.refresh(animation)

        return AnimationResponse.model_validate(animation)

    async def update_animation(
        self, db: AsyncSession, animation_id: str, data: AnimationUpdate
    ) -> Optional[AnimationResponse]:
        result = await db.execute(
            select(ModelAnimation).where(ModelAnimation.id == animation_id)
        )
        animation = result.scalar_one_or_none()
        if animation is None:
            return None

        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            if hasattr(value, "value"):
                value = value.value
            setattr(animation, field, value)

        await db.commit()
        await db.refresh(animation)

        return AnimationResponse.model_validate(animation)

    async def delete_animation(self, db: AsyncSession, animation_id: str) -> bool:
        result = await db.execute(
            select(ModelAnimation).where(ModelAnimation.id == animation_id)
        )
        animation = result.scalar_one_or_none()
        if animation is None:
            return False

        await db.delete(animation)
        await db.commit()
        return True

    async def get_interactions(
        self, db: AsyncSession, model_id: str
    ) -> list[InteractionResponse]:
        result = await db.execute(
            select(ModelInteraction)
            .where(ModelInteraction.model_id == model_id)
            .order_by(ModelInteraction.priority.desc(), ModelInteraction.name)
        )
        interactions = result.scalars().all()
        return [InteractionResponse.model_validate(i) for i in interactions]

    async def create_interaction(
        self, db: AsyncSession, model_id: str, data: InteractionCreate
    ) -> Optional[InteractionResponse]:
        model_result = await db.execute(select(Model).where(Model.id == model_id))
        if model_result.scalar_one_or_none() is None:
            return None

        interaction = ModelInteraction(
            id=str(uuid.uuid4()),
            model_id=model_id,
            name=data.name,
            interaction_type=data.interaction_type.value,
            trigger_event=data.trigger_event,
            target_parameter=data.target_parameter,
            response_curve=data.response_curve,
            min_value=data.min_value,
            max_value=data.max_value,
            default_value=data.default_value,
            cooldown_ms=data.cooldown_ms,
            priority=data.priority,
            is_enabled=data.is_enabled,
        )

        db.add(interaction)
        await db.commit()
        await db.refresh(interaction)

        return InteractionResponse.model_validate(interaction)

    async def update_interaction(
        self, db: AsyncSession, interaction_id: str, data: InteractionUpdate
    ) -> Optional[InteractionResponse]:
        result = await db.execute(
            select(ModelInteraction).where(ModelInteraction.id == interaction_id)
        )
        interaction = result.scalar_one_or_none()
        if interaction is None:
            return None

        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            if hasattr(value, "value"):
                value = value.value
            setattr(interaction, field, value)

        await db.commit()
        await db.refresh(interaction)

        return InteractionResponse.model_validate(interaction)

    async def delete_interaction(self, db: AsyncSession, interaction_id: str) -> bool:
        result = await db.execute(
            select(ModelInteraction).where(ModelInteraction.id == interaction_id)
        )
        interaction = result.scalar_one_or_none()
        if interaction is None:
            return False

        await db.delete(interaction)
        await db.commit()
        return True

    async def get_versions(
        self, db: AsyncSession, model_id: str
    ) -> list[VersionResponse]:
        result = await db.execute(
            select(ModelVersion)
            .where(ModelVersion.model_id == model_id)
            .order_by(ModelVersion.version.desc())
        )
        versions = result.scalars().all()
        return [VersionResponse.model_validate(v) for v in versions]

    async def create_version(
        self,
        db: AsyncSession,
        model_id: str,
        temp_file_path: Path,
        change_log: str | None = None,
        user_id: str | None = None,
    ) -> Optional[VersionResponse]:
        result = await db.execute(select(Model).where(Model.id == model_id))
        model = result.scalar_one_or_none()
        if model is None:
            return None

        new_version = model.version + 1

        saved_path = await storage_manager.save_upload(
            temp_file_path, model_id, model.original_filename
        )

        version_info = await storage_manager.create_version(
            model_id, saved_path, new_version, change_log
        )

        version = ModelVersion(
            id=str(uuid.uuid4()),
            model_id=model_id,
            version=new_version,
            file_path=version_info["file_path"],
            file_size=version_info["file_size"],
            file_hash=version_info["file_hash"],
            change_log=change_log,
            created_by=user_id,
        )
        db.add(version)

        model.version = new_version
        model.file_path = saved_path
        model.file_size = version_info["file_size"]
        model.file_hash = version_info["file_hash"]
        model.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(version)

        cache_manager.delete(f"model:{model_id}")
        return VersionResponse.model_validate(version)

    async def get_preview(
        self, db: AsyncSession, request: PreviewRequest
    ) -> Optional[PreviewResponse]:
        result = await db.execute(select(Model).where(Model.id == request.model_id))
        model = result.scalar_one_or_none()
        if model is None:
            return None

        render_url = f"/api/v1/models/{request.model_id}/file"
        thumbnail_url = None
        if model.thumbnail_path:
            thumbnail_url = f"/api/v1/models/{request.model_id}/thumbnail"

        config_data = None
        if request.configuration_id:
            config_result = await db.execute(
                select(ModelConfiguration).where(
                    ModelConfiguration.id == request.configuration_id
                )
            )
            config = config_result.scalar_one_or_none()
            if config:
                config_data = {
                    "properties": config.properties,
                    "animation_params": config.animation_params,
                    "render_settings": config.render_settings,
                    "physics_settings": config.physics_settings,
                }

        anim_data = None
        if request.animation_id:
            anim_result = await db.execute(
                select(ModelAnimation).where(ModelAnimation.id == request.animation_id)
            )
            anim = anim_result.scalar_one_or_none()
            if anim:
                anim_data = {
                    "name": anim.name,
                    "duration": anim.duration,
                    "loop": anim.loop,
                    "blend_mode": anim.blend_mode,
                }

        metadata = {
            "model_type": model.model_type.value,
            "configuration": config_data,
            "animation": anim_data,
            "emotion_state": request.emotion_state,
            "viewport": request.viewport,
        }

        return PreviewResponse(
            model_id=request.model_id,
            render_url=render_url,
            thumbnail_url=thumbnail_url,
            metadata=metadata,
        )

    def _build_default_properties(self, model_type: ModelType, parse_result: ModelParseResult) -> dict:
        base = {
            "scale": 1.0,
            "position": {"x": 0, "y": 0, "z": 0},
            "rotation": {"x": 0, "y": 0, "z": 0},
        }

        if model_type == ModelType.LIVE2D:
            base.update({
                "canvas_width": parse_result.metadata.get("canvas_width", 1280),
                "canvas_height": parse_result.metadata.get("canvas_height", 720),
                "background_color": "#00000000",
                "fps": 30,
            })
        elif model_type == ModelType.BLENDER:
            base.update({
                "camera_distance": 3.0,
                "camera_angle": 15.0,
                "ambient_light": 0.5,
                "directional_light": 0.8,
                "shadow_enabled": True,
            })
        elif model_type == ModelType.VAM:
            base.update({
                "render_quality": "high",
                "subsurface_scattering": True,
                "hair_physics": True,
            })
        elif model_type == ModelType.VRM:
            base.update({
                "camera_distance": 2.0,
                "camera_angle": 0.0,
                "ambient_light": 0.6,
                "directional_light": 0.7,
                "first_person_offset": parse_result.metadata.get("look_at_offset"),
            })

        return base

    def _build_default_animation_params(self, model_type: ModelType, parse_result: ModelParseResult) -> dict:
        base = {
            "idle_enabled": True,
            "idle_interval_ms": 5000,
            "blink_enabled": True,
            "blink_interval_ms": 3000,
            "breath_enabled": True,
            "breath_amplitude": 0.02,
        }

        if model_type == ModelType.LIVE2D:
            base.update({
                "lip_sync_enabled": True,
                "lip_sync_gain": 1.0,
                "emotion_blend_speed": 0.1,
                "motion_crossfade_ms": 500,
            })
        elif model_type in (ModelType.BLENDER, ModelType.VRM):
            base.update({
                "transition_blend_ms": 300,
                "ik_enabled": True,
                "look_at_enabled": True,
                "look_at_speed": 5.0,
            })
        elif model_type == ModelType.VAM:
            base.update({
                "morph_speed": 0.1,
                "physics_substeps": 4,
                "collision_enabled": True,
            })

        return base

    def _build_default_render_settings(self, model_type: ModelType) -> dict:
        base = {
            "antialiasing": "msaa_4x",
            "vsync": True,
            "target_fps": 60,
        }

        if model_type == ModelType.LIVE2D:
            base.update({
                "renderer": "canvas2d",
                "texture_filter": "bilinear",
                "opacity": 1.0,
            })
        elif model_type in (ModelType.BLENDER, ModelType.VRM):
            base.update({
                "renderer": "webgl2",
                "tone_mapping": "aces",
                "exposure": 1.0,
                "gamma": 2.2,
            })
        elif model_type == ModelType.VAM:
            base.update({
                "renderer": "webgl2",
                "tone_mapping": "reinhard",
                "ssao_enabled": True,
                "bloom_enabled": False,
            })

        return base

    def _build_default_physics_settings(self, model_type: ModelType, parse_result: ModelParseResult) -> dict:
        base = {
            "enabled": parse_result.metadata.get("physics_enabled", False),
            "gravity": -9.81,
        }

        if model_type == ModelType.LIVE2D:
            base.update({
                "physics_file": None,
                "wind_strength": 0.0,
                "damping": 0.95,
            })
        elif model_type in (ModelType.BLENDER, ModelType.VRM):
            base.update({
                "spring_bone_iterations": 5,
                "collider_radius": 0.02,
                "stiffness": 1.0,
                "drag_force": 0.4,
            })
        elif model_type == ModelType.VAM:
            base.update({
                "soft_body_enabled": True,
                "cloth_simulation": True,
                "substeps": 8,
            })

        return base

    async def _compute_file_hash(self, file_path: Path) -> str:
        import hashlib
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()


model_asset_service = ModelAssetService()
