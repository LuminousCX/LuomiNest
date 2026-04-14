from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_db
from app.core.config import settings
from app.models.model_asset import Model as ModelORM, ModelType, ModelStatus
from app.schemas.model_asset import (
    ModelCreate, ModelUpdate, ModelResponse, ModelListResponse,
    ConfigurationCreate, ConfigurationUpdate, ConfigurationResponse,
    AnimationCreate, AnimationUpdate, AnimationResponse,
    InteractionCreate, InteractionUpdate, InteractionResponse,
    VersionResponse, PreviewRequest, PreviewResponse,
)
from app.services.model_asset_service import model_asset_service
from app.services.model_storage import storage_manager, cache_manager

router = APIRouter(prefix="/models", tags=["models"])


@router.post("", response_model=ModelResponse, status_code=201)
async def import_model(
    file: UploadFile = File(...),
    name: str = Form(...),
    model_type: str = Form(...),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    is_public: bool = Form(False),
    db: AsyncSession = Depends(get_db),
):
    try:
        model_type_enum = ModelType(model_type)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid model_type: {model_type}. Must be one of: {', '.join(mt.value for mt in ModelType)}")

    suffix = Path(file.filename or "unknown").suffix.lower()
    if suffix and suffix not in settings.MODEL_ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=422, detail=f"File extension '{suffix}' not allowed. Allowed: {', '.join(settings.MODEL_ALLOWED_EXTENSIONS)}")

    temp_path = await storage_manager.create_temp_upload_path(suffix=suffix)
    try:
        content = await file.read()
        max_size = settings.MODEL_MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if len(content) > max_size:
            raise HTTPException(status_code=413, detail=f"File too large. Max size: {settings.MODEL_MAX_UPLOAD_SIZE_MB}MB")

        temp_path.write_bytes(content)

        create_data = ModelCreate(
            name=name,
            description=description,
            model_type=model_type_enum,
            tags=tags.split(",") if tags else None,
            is_public=is_public,
        )

        result = await model_asset_service.import_model(
            db=db,
            temp_file_path=temp_path,
            original_filename=file.filename or "unknown",
            create_data=create_data,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            temp_path.unlink()


@router.get("", response_model=ModelListResponse)
async def list_models(
    model_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    mt = ModelType(model_type) if model_type else None
    ms = ModelStatus(status) if status else None
    return await model_asset_service.list_models(
        db=db, model_type=mt, status=ms, search=search, page=page, page_size=page_size
    )


@router.get("/{model_id}", response_model=ModelResponse)
async def get_model(model_id: str, db: AsyncSession = Depends(get_db)):
    result = await model_asset_service.get_model(db=db, model_id=model_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return result


@router.patch("/{model_id}", response_model=ModelResponse)
async def update_model(
    model_id: str, data: ModelUpdate, db: AsyncSession = Depends(get_db)
):
    result = await model_asset_service.update_model(db=db, model_id=model_id, update_data=data)
    if result is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return result


@router.delete("/{model_id}", status_code=204)
async def delete_model(model_id: str, db: AsyncSession = Depends(get_db)):
    success = await model_asset_service.delete_model(db=db, model_id=model_id)
    if not success:
        raise HTTPException(status_code=404, detail="Model not found")


@router.get("/{model_id}/file")
async def get_model_file(model_id: str, db: AsyncSession = Depends(get_db)):
    from fastapi.responses import FileResponse

    result = await db.execute(select(ModelORM).where(ModelORM.id == model_id))
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")

    file_path = Path(model.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Model file not found")

    return FileResponse(
        path=str(file_path),
        filename=model.original_filename,
        media_type="application/octet-stream",
    )


@router.get("/{model_id}/thumbnail")
async def get_model_thumbnail(model_id: str, db: AsyncSession = Depends(get_db)):
    from fastapi.responses import FileResponse

    model = await model_asset_service.get_model(db=db, model_id=model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")

    thumb_path = storage_manager.get_thumbnail_path(model_id)
    if not thumb_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")

    return FileResponse(
        path=str(thumb_path),
        media_type="image/png",
    )


@router.post("/{model_id}/thumbnail", response_model=ModelResponse)
async def upload_thumbnail(
    model_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    image_data = await file.read()
    thumb_path = await storage_manager.save_thumbnail(image_data, model_id)

    result = await db.execute(select(ModelORM).where(ModelORM.id == model_id))
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")

    model.thumbnail_path = thumb_path
    await db.commit()
    await db.refresh(model)

    cache_manager.delete(f"model:{model_id}")
    return ModelResponse.model_validate(model)


@router.get("/{model_id}/versions", response_model=list[VersionResponse])
async def get_model_versions(model_id: str, db: AsyncSession = Depends(get_db)):
    return await model_asset_service.get_versions(db=db, model_id=model_id)


@router.post("/{model_id}/versions", response_model=VersionResponse, status_code=201)
async def create_model_version(
    model_id: str,
    file: UploadFile = File(...),
    change_log: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    temp_path = await storage_manager.create_temp_upload_path(
        suffix=Path(file.filename or "unknown").suffix
    )
    try:
        content = await file.read()
        temp_path.write_bytes(content)

        result = await model_asset_service.create_version(
            db=db,
            model_id=model_id,
            temp_file_path=temp_path,
            change_log=change_log,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Model not found")
        return result
    finally:
        if temp_path.exists():
            temp_path.unlink()


@router.post("/{model_id}/preview", response_model=PreviewResponse)
async def get_model_preview(
    model_id: str, request: PreviewRequest, db: AsyncSession = Depends(get_db)
):
    request.model_id = model_id
    result = await model_asset_service.get_preview(db=db, request=request)
    if result is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return result


# ── Configuration endpoints ──

@router.get("/{model_id}/configurations", response_model=list[ConfigurationResponse])
async def get_configurations(model_id: str, db: AsyncSession = Depends(get_db)):
    return await model_asset_service.get_configurations(db=db, model_id=model_id)


@router.post("/{model_id}/configurations", response_model=ConfigurationResponse, status_code=201)
async def create_configuration(
    model_id: str, data: ConfigurationCreate, db: AsyncSession = Depends(get_db)
):
    result = await model_asset_service.create_configuration(db=db, model_id=model_id, data=data)
    if result is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return result


@router.patch("/configurations/{config_id}", response_model=ConfigurationResponse)
async def update_configuration(
    config_id: str, data: ConfigurationUpdate, db: AsyncSession = Depends(get_db)
):
    result = await model_asset_service.update_configuration(db=db, config_id=config_id, data=data)
    if result is None:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return result


@router.delete("/configurations/{config_id}", status_code=204)
async def delete_configuration(config_id: str, db: AsyncSession = Depends(get_db)):
    success = await model_asset_service.delete_configuration(db=db, config_id=config_id)
    if not success:
        raise HTTPException(status_code=404, detail="Configuration not found")


# ── Animation endpoints ──

@router.get("/{model_id}/animations", response_model=list[AnimationResponse])
async def get_animations(model_id: str, db: AsyncSession = Depends(get_db)):
    return await model_asset_service.get_animations(db=db, model_id=model_id)


@router.post("/{model_id}/animations", response_model=AnimationResponse, status_code=201)
async def create_animation(
    model_id: str, data: AnimationCreate, db: AsyncSession = Depends(get_db)
):
    result = await model_asset_service.create_animation(db=db, model_id=model_id, data=data)
    if result is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return result


@router.patch("/animations/{animation_id}", response_model=AnimationResponse)
async def update_animation(
    animation_id: str, data: AnimationUpdate, db: AsyncSession = Depends(get_db)
):
    result = await model_asset_service.update_animation(db=db, animation_id=animation_id, data=data)
    if result is None:
        raise HTTPException(status_code=404, detail="Animation not found")
    return result


@router.delete("/animations/{animation_id}", status_code=204)
async def delete_animation(animation_id: str, db: AsyncSession = Depends(get_db)):
    success = await model_asset_service.delete_animation(db=db, animation_id=animation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Animation not found")


# ── Interaction endpoints ──

@router.get("/{model_id}/interactions", response_model=list[InteractionResponse])
async def get_interactions(model_id: str, db: AsyncSession = Depends(get_db)):
    return await model_asset_service.get_interactions(db=db, model_id=model_id)


@router.post("/{model_id}/interactions", response_model=InteractionResponse, status_code=201)
async def create_interaction(
    model_id: str, data: InteractionCreate, db: AsyncSession = Depends(get_db)
):
    result = await model_asset_service.create_interaction(db=db, model_id=model_id, data=data)
    if result is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return result


@router.patch("/interactions/{interaction_id}", response_model=InteractionResponse)
async def update_interaction(
    interaction_id: str, data: InteractionUpdate, db: AsyncSession = Depends(get_db)
):
    result = await model_asset_service.update_interaction(db=db, interaction_id=interaction_id, data=data)
    if result is None:
        raise HTTPException(status_code=404, detail="Interaction not found")
    return result


@router.delete("/interactions/{interaction_id}", status_code=204)
async def delete_interaction(interaction_id: str, db: AsyncSession = Depends(get_db)):
    success = await model_asset_service.delete_interaction(db=db, interaction_id=interaction_id)
    if not success:
        raise HTTPException(status_code=404, detail="Interaction not found")
