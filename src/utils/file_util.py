"""文件处理工具类。

提供文件读写、类型判断、安全检查、内容解析等功能。
支持图片（jpg, png, gif, webp）和文档（pdf, txt, md, csv）。
"""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from src.utils.logger import get_logger

logger = get_logger()


class FileType(str, Enum):
    """文件类型枚举。"""

    IMAGE = "image"
    DOCUMENT = "document"
    UNKNOWN = "unknown"


@dataclass
class FileInfo:
    """文件信息。"""

    filename: str
    file_type: FileType
    extension: str
    mime_type: str
    size_bytes: int
    content_hash: str
    path: Optional[Path] = None


@dataclass
class ParseResult:
    """解析结果。"""

    success: bool
    content: str
    error_message: Optional[str] = None
    char_count: int = 0


ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".txt", ".md", ".csv"}
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_DOCUMENT_EXTENSIONS

MAX_IMAGE_SIZE_MB = 10
MAX_DOCUMENT_SIZE_MB = 20
BYTES_PER_MB = 1024 * 1024
MAX_TEXT_LENGTH = 10000


class FileUtil:
    """文件处理工具类。"""

    @staticmethod
    def get_extension(filename: str) -> str:
        """获取文件扩展名（小写，含点号）。"""
        return Path(filename).suffix.lower()

    @staticmethod
    def get_mime_type(filename: str) -> str:
        """获取 MIME 类型。"""
        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".pdf": "application/pdf",
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".csv": "text/csv",
        }
        ext = FileUtil.get_extension(filename)
        return mime_map.get(ext, mimetypes.guess_type(filename)[0] or "application/octet-stream")

    @staticmethod
    def get_file_type(filename: str) -> FileType:
        """判断文件类型。"""
        ext = FileUtil.get_extension(filename)
        if ext in ALLOWED_IMAGE_EXTENSIONS:
            return FileType.IMAGE
        if ext in ALLOWED_DOCUMENT_EXTENSIONS:
            return FileType.DOCUMENT
        return FileType.UNKNOWN

    @staticmethod
    def is_allowed(filename: str) -> bool:
        """检查文件类型是否允许上传。"""
        return FileUtil.get_extension(filename) in ALLOWED_EXTENSIONS

    @staticmethod
    def is_image(filename: str) -> bool:
        """检查是否为图片文件。"""
        return FileUtil.get_extension(filename) in ALLOWED_IMAGE_EXTENSIONS

    @staticmethod
    def is_document(filename: str) -> bool:
        """检查是否为文档文件。"""
        return FileUtil.get_extension(filename) in ALLOWED_DOCUMENT_EXTENSIONS

    @staticmethod
    def check_size(size_bytes: int, filename: str) -> tuple[bool, str]:
        """检查文件大小是否在限制内。"""
        file_type = FileUtil.get_file_type(filename)

        if file_type == FileType.IMAGE:
            max_size = MAX_IMAGE_SIZE_MB
        elif file_type == FileType.DOCUMENT:
            max_size = MAX_DOCUMENT_SIZE_MB
        else:
            return False, f"不支持的文件类型: {FileUtil.get_extension(filename)}"

        size_mb = size_bytes / BYTES_PER_MB
        if size_mb > max_size:
            return False, f"文件大小超过限制: 当前 {size_mb:.2f}MB，最大 {max_size}MB"

        return True, ""

    @staticmethod
    def compute_hash(content: bytes) -> str:
        """计算文件内容的 SHA256 哈希值。"""
        return hashlib.sha256(content).hexdigest()[:16]

    @staticmethod
    def create_file_info(filename: str, content: bytes, path: Optional[Path] = None) -> FileInfo:
        """创建文件信息对象。"""
        return FileInfo(
            filename=filename,
            file_type=FileUtil.get_file_type(filename),
            extension=FileUtil.get_extension(filename),
            mime_type=FileUtil.get_mime_type(filename),
            size_bytes=len(content),
            content_hash=FileUtil.compute_hash(content),
            path=path,
        )

    @staticmethod
    def create_file_info_from_path(file_path: Path) -> FileInfo:
        """从文件路径创建文件信息对象（不读取文件内容）。

        仅获取文件元信息，避免将大文件内容加载到内存。
        content_hash 使用文件路径+大小+修改时间生成伪哈希。
        """
        stat = file_path.stat()
        pseudo_hash = hashlib.sha256(
            f"{file_path.name}:{stat.st_size}:{stat.st_mtime}".encode()
        ).hexdigest()[:16]
        return FileInfo(
            filename=file_path.name,
            file_type=FileUtil.get_file_type(file_path.name),
            extension=FileUtil.get_extension(file_path.name),
            mime_type=FileUtil.get_mime_type(file_path.name),
            size_bytes=stat.st_size,
            content_hash=pseudo_hash,
            path=file_path,
        )

    @staticmethod
    def ensure_dir(path: Path) -> Path:
        """确保目录存在。"""
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def read_json(file_path: Path, default: Any = None) -> Any:
        """读取 JSON 文件。"""
        if not file_path.exists():
            return default
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"读取 JSON 文件失败: {file_path}, 错误: {e}")
            return default

    @staticmethod
    def write_json(file_path: Path, data: Any, indent: int = 2) -> bool:
        """写入 JSON 文件。"""
        FileUtil.ensure_dir(file_path.parent)
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=indent)
            return True
        except (TypeError, OSError) as e:
            logger.error(f"写入 JSON 文件失败: {file_path}, 错误: {e}")
            return False

    @staticmethod
    def backup_file(file_path: Path, backup_suffix: str = ".bak") -> Optional[Path]:
        """备份文件。"""
        if not file_path.exists():
            return None
        backup_path = file_path.with_suffix(file_path.suffix + backup_suffix)
        try:
            shutil.copy2(file_path, backup_path)
            logger.info(f"文件备份成功: {file_path} -> {backup_path}")
            return backup_path
        except OSError as e:
            logger.error(f"文件备份失败: {file_path}, 错误: {e}")
            return None

    @staticmethod
    def parse_image(image_path: Path) -> ParseResult:
        """解析图片文件，返回 base64 编码。"""
        try:
            with open(image_path, "rb") as f:
                content = f.read()

            mime_type = FileUtil.get_mime_type(str(image_path))
            base64_data = base64.b64encode(content).decode("utf-8")
            data_url = f"data:{mime_type};base64,{base64_data}"

            return ParseResult(
                success=True,
                content=data_url,
                char_count=len(base64_data),
            )
        except Exception as e:
            logger.error(f"图片解析失败: {image_path}, 错误: {e}")
            return ParseResult(success=False, content="", error_message=str(e))

    @staticmethod
    def parse_text_file(file_path: Path) -> ParseResult:
        """解析纯文本文件（TXT、MD、CSV）。"""
        try:
            encodings = ["utf-8", "gbk", "gb2312", "latin-1"]
            content = ""

            for encoding in encodings:
                try:
                    with open(file_path, "r", encoding=encoding) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue

            if not content:
                return ParseResult(success=False, content="", error_message="无法识别文件编码")

            truncated = content[:MAX_TEXT_LENGTH]
            if len(content) > MAX_TEXT_LENGTH:
                truncated += f"\n\n... [内容已截断，原文共 {len(content)} 字符]"

            return ParseResult(success=True, content=truncated, char_count=len(truncated))
        except Exception as e:
            logger.error(f"文本文件解析失败: {file_path}, 错误: {e}")
            return ParseResult(success=False, content="", error_message=str(e))

    @staticmethod
    def parse_pdf(file_path: Path) -> ParseResult:
        """解析 PDF 文件。"""
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(str(file_path))
            pages_text: list[str] = []

            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)

            content = "\n\n".join(pages_text)
            truncated = content[:MAX_TEXT_LENGTH]
            if len(content) > MAX_TEXT_LENGTH:
                truncated += f"\n\n... [内容已截断，原文共 {len(content)} 字符]"

            return ParseResult(success=True, content=truncated, char_count=len(truncated))
        except ImportError:
            return ParseResult(success=False, content="", error_message="PyPDF2 库未安装")
        except Exception as e:
            logger.error(f"PDF 解析失败: {file_path}, 错误: {e}")
            return ParseResult(success=False, content="", error_message=str(e))

    @staticmethod
    def parse_file(file_path: Path) -> ParseResult:
        """解析文件，自动识别类型。"""
        ext = FileUtil.get_extension(str(file_path))

        if ext in ALLOWED_IMAGE_EXTENSIONS:
            return FileUtil.parse_image(file_path)
        if ext in {".txt", ".md", ".csv"}:
            return FileUtil.parse_text_file(file_path)
        if ext == ".pdf":
            return FileUtil.parse_pdf(file_path)

        return ParseResult(success=False, content="", error_message=f"不支持的文件类型: {ext}")

    @staticmethod
    def build_openai_image_message(image_path: Path, query: str = "") -> dict:
        """构建 OpenAI 格式的图片消息。"""
        result = FileUtil.parse_image(image_path)

        if not result.success:
            return {"role": "user", "content": f"[图片解析失败: {result.error_message}]"}

        content_parts: list[dict] = []
        if query:
            content_parts.append({"type": "text", "text": query})
        content_parts.append({"type": "image_url", "image_url": {"url": result.content}})

        return {"role": "user", "content": content_parts}

    @staticmethod
    def build_openai_document_message(file_path: Path, query: str = "") -> dict:
        """构建 OpenAI 格式的文档消息。"""
        result = FileUtil.parse_file(file_path)
        filename = file_path.name

        if not result.success:
            return {"role": "user", "content": f"[文档「{filename}」解析失败: {result.error_message}]\n\n{query}"}

        content = f"以下是文件「{filename}」的内容：\n\n{result.content}"
        if query:
            content += f"\n\n用户问题：{query}"

        return {"role": "user", "content": content}


_file_util: Optional[FileUtil] = None


def get_file_util() -> FileUtil:
    """获取全局 FileUtil 实例。"""
    global _file_util
    if _file_util is None:
        _file_util = FileUtil()
    return _file_util
