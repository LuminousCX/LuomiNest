"""文件上传解析 API 路由。

提供文件上传、解析、删除等接口。
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field
from typing_extensions import Annotated

from src.schema.common_schema import ApiResponse
from src.service.file_service import FileService, get_file_service
from src.utils.file_util import FileType
from src.utils.logger import get_logger

logger = get_logger()

router = APIRouter(prefix="/file", tags=["文件上传解析"])


class UploadResponse(BaseModel):
    """上传响应。"""

    file_id: str = Field(description="文件ID")
    filename: str = Field(description="原始文件名")
    file_type: FileType = Field(description="文件类型")
    mime_type: str = Field(description="MIME类型")
    size_bytes: int = Field(description="文件大小（字节）")
    content_hash: str = Field(description="内容哈希")


class ParseResponse(BaseModel):
    """解析响应。"""

    file_id: str = Field(description="文件ID")
    success: bool = Field(description="是否成功")
    content: str = Field(description="解析内容预览")
    char_count: int = Field(description="字符数")
    error_message: Optional[str] = Field(default=None, description="错误信息")


class BuildMessageRequest(BaseModel):
    """构建消息请求。"""

    file_id: str = Field(description="文件ID")
    query: str = Field(default="", description="用户查询文本")


def get_service() -> FileService:
    """获取 FileService 实例（依赖注入）。"""
    return get_file_service()


async def _do_upload(
    service: FileService, file: UploadFile, allowed_category: Optional[FileType] = None
) -> ApiResponse[UploadResponse]:
    """文件上传内部实现。

    Args:
        service: 文件服务。
        file: 上传文件。
        allowed_category: 限定文件类别（IMAGE 或 DOCUMENT），None 表示不限。
    """
    content = await file.read()
    filename = file.filename or "unknown"

    file_info = service.save_file(filename, content)

    if allowed_category is not None and file_info.file_type != allowed_category:
        service.delete_file(file_info.path.stem if file_info.path else "")
        return ApiResponse.error(
            code=40001,
            message=f"文件类型不匹配，仅允许 {allowed_category.value} 类型",
        )

    logger.info(f"文件上传成功: {filename} -> {file_info.path}")

    return ApiResponse.success(
        data=UploadResponse(
            file_id=file_info.path.stem if file_info.path else "",
            filename=file_info.filename,
            file_type=file_info.file_type,
            mime_type=file_info.mime_type,
            size_bytes=file_info.size_bytes,
            content_hash=file_info.content_hash,
        ),
        message="文件上传成功",
    )


@router.post("/upload", summary="上传文件")
async def upload_file(
    service: Annotated[FileService, Depends(get_service)],
    file: UploadFile = File(...),
) -> ApiResponse[UploadResponse]:
    """上传文件（图片或文档）。

    支持的文件类型：
    - 图片：jpg, jpeg, png, gif, webp（最大 10MB）
    - 文档：pdf, txt, md, csv（最大 20MB）

    Returns:
        文件 ID 和基本信息。
    """
    return await _do_upload(service, file)


@router.post("/upload/image", summary="上传图片")
async def upload_image(
    service: Annotated[FileService, Depends(get_service)],
    file: UploadFile = File(...),
) -> ApiResponse[UploadResponse]:
    """上传图片文件。

    仅支持图片格式：jpg, jpeg, png, gif, webp
    最大文件大小：10MB

    Returns:
        图片文件 ID 和基本信息。
    """
    return await _do_upload(service, file, allowed_category=FileType.IMAGE)


@router.post("/upload/document", summary="上传文档")
async def upload_document(
    service: Annotated[FileService, Depends(get_service)],
    file: UploadFile = File(...),
) -> ApiResponse[UploadResponse]:
    """上传文档文件。

    支持的文档格式：pdf, txt, md, csv
    最大文件大小：20MB

    Returns:
        文档文件 ID 和基本信息。
    """
    return await _do_upload(service, file, allowed_category=FileType.DOCUMENT)


@router.get("/parse/{file_id}", summary="解析文件")
async def parse_file(
    file_id: str,
    service: Annotated[FileService, Depends(get_service)],
) -> ApiResponse[ParseResponse]:
    """解析已上传的文件，返回文本内容。

    Args:
        file_id: 上传文件返回的 file_id。

    Returns:
        解析后的文本内容。
    """
    result = service.parse_file(file_id)

    return ApiResponse.success(
        data=ParseResponse(
            file_id=file_id,
            success=result.success,
            content=result.content[:500] if result.success else "",
            char_count=result.char_count,
            error_message=result.error_message,
        ),
    )


@router.post("/build-message", summary="构建对话消息")
async def build_message(
    request: BuildMessageRequest,
    service: Annotated[FileService, Depends(get_service)],
) -> ApiResponse[dict]:
    """构建用于注入 prompt 的对话消息。

    将文件内容转换为 OpenAI 格式的消息，可直接用于对话。

    Args:
        request: 构建消息请求。

    Returns:
        OpenAI 格式的消息字典。
    """
    message = service.build_message_for_prompt(
        file_id=request.file_id,
        query=request.query,
    )

    return ApiResponse.success(
        data={
            "file_id": request.file_id,
            "message": message,
        },
    )


@router.delete("/{file_id}", summary="删除文件")
async def delete_file(
    file_id: str,
    service: Annotated[FileService, Depends(get_service)],
) -> ApiResponse[None]:
    """删除已上传的文件。

    Args:
        file_id: 文件 ID。

    Returns:
        删除结果。
    """
    success = service.delete_file(file_id)

    if success:
        return ApiResponse.success(message="文件删除成功")
    else:
        return ApiResponse.error(code=50001, message="文件不存在或删除失败")


@router.get("/list", summary="列出已上传文件")
async def list_files(
    service: Annotated[FileService, Depends(get_service)],
) -> ApiResponse[list[dict]]:
    """列出所有已上传的文件。

    Returns:
        文件信息列表。
    """
    files = service.list_uploaded_files()

    return ApiResponse.success(
        data=[
            {
                "file_id": f.path.stem if f.path else "",
                "filename": f.filename,
                "file_type": f.file_type.value,
                "mime_type": f.mime_type,
                "size_bytes": f.size_bytes,
            }
            for f in files
        ],
    )


@router.post("/cleanup", summary="清理过期文件")
async def cleanup_files(
    service: Annotated[FileService, Depends(get_service)],
    max_age_hours: int = 24,
) -> ApiResponse[dict]:
    """清理过期的上传文件。

    Args:
        max_age_hours: 最大保留时间（小时），默认 24 小时。

    Returns:
        删除的文件数量。
    """
    deleted_count = service.cleanup_old_files(max_age_hours)

    return ApiResponse.success(
        data={"deleted_count": deleted_count},
        message=f"清理完成，删除 {deleted_count} 个过期文件",
    )
