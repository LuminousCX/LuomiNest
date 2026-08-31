"""图片工具 — 编码、验证、输出策略。"""
import base64
import os
import struct
import uuid
from typing import Any

MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
MAX_IMAGE_DIMENSION = 4096  # 像素


def validate_image(data: bytes) -> dict[str, Any]:
    """验证图片：大小、格式、尺寸。"""
    if len(data) > MAX_IMAGE_SIZE_BYTES:
        return {"valid": False, "error": f"图片超过 10MB 限制（实际 {len(data)/1024/1024:.1f}MB）"}
    if len(data) < 8:
        return {"valid": False, "error": "数据太短，不是有效图片"}

    # 检查 PNG 魔数
    if data[:4] == b"\x89PNG":
        # PNG: 从 IHDR 块读取尺寸
        if len(data) >= 24:
            width = struct.unpack(">I", data[16:20])[0]
            height = struct.unpack(">I", data[20:24])[0]
        else:
            return {"valid": False, "error": "PNG 数据不完整"}
    else:
        # 非 PNG 格式暂不验证尺寸
        width, height = 0, 0

    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
        return {"valid": False, "error": f"图片尺寸 {width}x{height} 超过 {MAX_IMAGE_DIMENSION}x{MAX_IMAGE_DIMENSION} 限制"}

    return {"valid": True, "width": width, "height": height}


def encode_output(
    image_bytes: bytes,
    inline_threshold_kb: int = 50,
    data_dir: str = "",
    fmt: str = "png",
) -> dict[str, Any]:
    """根据大小决定返回方式：base64 内联或文件路径。"""
    size_kb = len(image_bytes) / 1024
    mime = f"image/{fmt}"

    if size_kb <= inline_threshold_kb:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        return {
            "mode": "inline",
            "data": b64,
            "format": fmt,
            "size_kb": round(size_kb, 1),
            "markdown": f"![chart](data:{mime};base64,{b64})",
        }
    else:
        # 保存到插件数据目录
        charts_dir = os.path.join(data_dir, "charts") if data_dir else "/tmp"
        os.makedirs(charts_dir, exist_ok=True)
        file_id = uuid.uuid4().hex
        filename = f"{file_id}.{fmt}"
        filepath = os.path.join(charts_dir, filename)
        with open(filepath, "wb") as f:
            f.write(image_bytes)
        return {
            "mode": "file",
            "path": filepath,
            "file_id": file_id,
            "size_kb": round(size_kb, 1),
            "markdown": f"![chart]({filepath})",
        }
