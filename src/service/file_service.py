"""文件上传解析服务。

提供文件上传、保存、解析、内容注入等功能。
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from src.exceptions import ParamError
from src.utils.file_util import (
    FileUtil,
    FileInfo,
    FileType,
    ParseResult,
    get_file_util,
)
from src.utils.logger import get_logger
from src.utils.string_utils import generate_id

logger = get_logger()

_UPLOAD_DIR_NAME = "uploads"


class FileService:
    """文件上传解析服务。

    Attributes:
        upload_dir: 上传文件保存目录。
    """

    def __init__(self, data_dir: str) -> None:
        """初始化服务。

        Args:
            data_dir: 数据目录路径。
        """
        self.upload_dir = Path(data_dir) / _UPLOAD_DIR_NAME
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"FileService 初始化完成，上传目录: {self.upload_dir}")

    def save_file(self, filename: str, content: bytes) -> FileInfo:
        """保存上传文件。

        Args:
            filename: 原始文件名。
            content: 文件内容字节。

        Returns:
            FileInfo 文件信息对象。

        Raises:
            ParamError: 文件类型不允许或大小超限时抛出。
        """
        file_util = get_file_util()

        if not file_util.is_allowed(filename):
            ext = file_util.get_extension(filename)
            raise ParamError(message=f"不支持的文件类型: {ext}")

        is_valid, error_msg = file_util.check_size(len(content), filename)
        if not is_valid:
            raise ParamError(message=error_msg)

        ext = file_util.get_extension(filename)
        safe_filename = f"{generate_id()}{ext}"
        file_path = self.upload_dir / safe_filename

        with open(file_path, "wb") as f:
            f.write(content)

        logger.info(f"文件保存成功: {file_path}, 原始文件名: {filename}")

        return file_util.create_file_info(filename, content, file_path)

    def parse_file(self, file_id: str) -> ParseResult:
        """解析已上传的文件。

        Args:
            file_id: 文件 ID（不含扩展名）。

        Returns:
            ParseResult 解析结果。

        Raises:
            ParamError: 文件不存在时抛出。
        """
        matching_files = list(self.upload_dir.glob(f"{file_id}.*"))

        if not matching_files:
            raise ParamError(message=f"文件不存在: {file_id}")

        file_path = matching_files[0]
        logger.info(f"开始解析文件: {file_path}")

        return FileUtil.parse_file(file_path)

    def get_file_path(self, file_id: str) -> Optional[Path]:
        """获取文件路径。

        Args:
            file_id: 文件 ID。

        Returns:
            文件路径，不存在返回 None。
        """
        matching_files = list(self.upload_dir.glob(f"{file_id}.*"))
        return matching_files[0] if matching_files else None

    def delete_file(self, file_id: str) -> bool:
        """删除已上传的文件。

        Args:
            file_id: 文件 ID。

        Returns:
            是否删除成功。
        """
        matching_files = list(self.upload_dir.glob(f"{file_id}.*"))

        for file_path in matching_files:
            try:
                file_path.unlink()
                logger.info(f"文件删除成功: {file_path}")
            except Exception as e:
                logger.error(f"文件删除失败: {file_path}, 错误: {e}")
                return False

        return len(matching_files) > 0

    def build_message_for_prompt(
        self,
        file_id: str,
        query: str = "",
    ) -> dict:
        """构建用于注入 prompt 的消息。

        Args:
            file_id: 文件 ID。
            query: 用户查询文本。

        Returns:
            OpenAI 格式消息字典。

        Raises:
            ParamError: 文件不存在时抛出。
        """
        file_path = self.get_file_path(file_id)

        if not file_path:
            raise ParamError(message=f"文件不存在: {file_id}")

        file_util = get_file_util()

        if file_util.is_image(str(file_path)):
            return FileUtil.build_openai_image_message(file_path, query)
        else:
            return FileUtil.build_openai_document_message(file_path, query)

    def list_uploaded_files(self) -> list[FileInfo]:
        """列出所有已上传的文件。

        仅读取文件元信息，不读取文件内容。

        Returns:
            FileInfo 列表。
        """
        files: list[FileInfo] = []

        for file_path in self.upload_dir.iterdir():
            if file_path.is_file():
                try:
                    file_info = FileUtil.create_file_info_from_path(
                        file_path=file_path,
                    )
                    files.append(file_info)
                except Exception as e:
                    logger.warning(f"读取文件信息失败: {file_path}, 错误: {e}")

        return sorted(files, key=lambda x: x.path.stat().st_mtime if x.path else 0, reverse=True)

    def cleanup_old_files(self, max_age_hours: int = 24) -> int:
        """清理过期文件。

        Args:
            max_age_hours: 最大保留时间（小时）。

        Returns:
            删除的文件数量。
        """
        import time

        deleted_count = 0
        cutoff_time = time.time() - (max_age_hours * 3600)

        for file_path in self.upload_dir.iterdir():
            if file_path.is_file():
                try:
                    if file_path.stat().st_mtime < cutoff_time:
                        file_path.unlink()
                        deleted_count += 1
                        logger.debug(f"清理过期文件: {file_path}")
                except Exception as e:
                    logger.warning(f"清理文件失败: {file_path}, 错误: {e}")

        if deleted_count > 0:
            logger.info(f"清理过期文件完成，共删除 {deleted_count} 个文件")

        return deleted_count


_file_service: Optional[FileService] = None
_file_service_lock = threading.Lock()


def get_file_service() -> FileService:
    """获取全局 FileService 实例。"""
    global _file_service
    if _file_service is None:
        with _file_service_lock:
            if _file_service is None:
                from src.config.settings import get_settings
                settings = get_settings()
                _file_service = FileService(settings.data_dir)
    return _file_service
