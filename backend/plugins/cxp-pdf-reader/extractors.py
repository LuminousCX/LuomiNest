"""CxPlugin PDF 智能阅读器 — 文档解析器。

支持 PDF / DOCX / TXT 三种格式的文本、页码与大纲提取。
所有解析函数采用容错设计：解析失败时返回带 `error` 字段的标准化结构，
不向调用方抛出异常。

设计原则：
- PDF 使用 PyMuPDF (fitz)（按页提取，原生支持书签/大纲提取，性能优于 pdfplumber）
- DOCX 使用 python-docx（按段落提取，通过 page break 与 Heading 样式推导页码与大纲）
- TXT 直接读取（视为单页文档）
- 文件类型通过扩展名检测，不依赖 MIME 嗅探
- 所有路径操作使用 os.path.join，避免跨平台问题
"""
from __future__ import annotations

import os
from typing import Any

from loguru import logger

# ──────────────────────────────────────────────────────────────
# 支持的文件类型常量
# ──────────────────────────────────────────────────────────────

SUPPORTED_FILE_TYPES: tuple[str, ...] = ("pdf", "docx", "txt")

_EXTENSION_MAP: dict[str, str] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "txt",
}


# ──────────────────────────────────────────────────────────────
# 文件类型检测
# ──────────────────────────────────────────────────────────────

def detect_file_type(filename: str) -> str | None:
    """根据文件名扩展名检测文件类型。

    Args:
        filename: 文件名（含扩展名）

    Returns:
        "pdf" | "docx" | "txt" | None（不支持的类型返回 None）
    """
    if not filename:
        return None
    # 仅取最后一段扩展名，避免双扩展名干扰
    _, ext = os.path.splitext(filename.lower())
    return _EXTENSION_MAP.get(ext)


# ──────────────────────────────────────────────────────────────
# 标准化结果结构
# ──────────────────────────────────────────────────────────────

def _empty_result(error: str | None = None) -> dict[str, Any]:
    """构造空结果（用于失败场景）。"""
    result: dict[str, Any] = {
        "text": "",
        "pageCount": 0,
        "outline": [],
        "pages": [],
    }
    if error:
        result["error"] = error
    return result


# ──────────────────────────────────────────────────────────────
# PDF 解析（PyMuPDF / fitz）
# ──────────────────────────────────────────────────────────────

def extract_pdf(file_path: str, max_pages: int | None = None) -> dict[str, Any]:
    """使用 PyMuPDF (fitz) 提取 PDF 文本与大纲。

    PyMuPDF 原生支持书签（outline/TOD）提取，性能优于 pdfplumber，
    同时主项目 pyproject.toml 已声明 `pymupdf` 依赖，无需额外引入。

    Args:
        file_path: PDF 文件绝对路径
        max_pages: 可选的最大页数限制（防止超大文档耗尽内存）

    Returns:
        标准化结构 {text, pageCount, outline, pages}；
        失败时附加 error 字段。
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        logger.error(f"[CxPdfReader] PyMuPDF not installed: {exc}")
        return _empty_result("PDF 解析依赖 PyMuPDF 未安装")

    if not os.path.isfile(file_path):
        return _empty_result(f"文件不存在: {file_path}")

    pages_text: list[str] = []
    outline: list[dict[str, Any]] = []
    page_count = 0
    try:
        doc = fitz.open(file_path)
        try:
            page_count = doc.page_count
            limit = page_count if max_pages is None else min(page_count, max_pages)
            for idx in range(limit):
                page = doc.load_page(idx)
                try:
                    page_text = page.get_text("text") or ""
                except Exception as page_err:
                    # 单页失败不影响整体，记录后继续
                    logger.warning(
                        f"[CxPdfReader] PDF page {idx + 1} extract failed: {page_err}"
                    )
                    page_text = ""
                pages_text.append(page_text)

            # 提取书签大纲：get_toc 返回 [[level, title, page], ...]
            raw_toc = doc.get_toc(simple=True)
            for entry in raw_toc:
                if len(entry) >= 3:
                    level = max(1, int(entry[0]))
                    title = str(entry[1]).strip()
                    page_num = max(1, int(entry[2]))
                    if title:
                        outline.append({
                            "level": level,
                            "title": title,
                            "page": page_num,
                        })
        finally:
            doc.close()
    except Exception as exc:
        logger.error(f"[CxPdfReader] extract_pdf failed: {exc}")
        return _empty_result(f"PDF 解析失败: {exc}")

    full_text = "\n\n".join(pages_text)
    return {
        "text": full_text,
        "pageCount": page_count,
        "outline": outline,
        "pages": pages_text,
    }


# ──────────────────────────────────────────────────────────────
# DOCX 解析（python-docx）
# ──────────────────────────────────────────────────────────────

def extract_docx(file_path: str) -> dict[str, Any]:
    """使用 python-docx 提取 Word 文档文本。

    分页策略：
    - 优先检测 Word 的 page break 元素（w:br w:type="page"）作为分页边界
    - 若无分页符，整体视为单页
    大纲策略：
    - 通过 paragraph.style.name 识别 Heading 1-9 作为大纲条目

    Args:
        file_path: DOCX 文件绝对路径

    Returns:
        标准化结构 {text, pageCount, outline, pages}；
        失败时附加 error 字段。
    """
    try:
        import docx
        from docx.oxml.ns import qn
    except ImportError as exc:
        logger.error(f"[CxPdfReader] python-docx not installed: {exc}")
        return _empty_result("DOCX 解析依赖 python-docx 未安装")

    if not os.path.isfile(file_path):
        return _empty_result(f"文件不存在: {file_path}")

    try:
        document = docx.Document(file_path)
    except Exception as exc:
        logger.error(f"[CxPdfReader] extract_docx open failed: {exc}")
        return _empty_result(f"DOCX 文件打开失败: {exc}")

    pages: list[str] = []
    current_page_chunks: list[str] = []
    outline: list[dict[str, Any]] = []
    current_page_num = 1

    for paragraph in document.paragraphs:
        text = paragraph.text or ""
        style_name = ""
        try:
            style_name = paragraph.style.name if paragraph.style else ""
        except Exception:
            style_name = ""

        # 识别 Heading 样式作为大纲
        if style_name and style_name.lower().startswith("heading"):
            level = _parse_heading_level(style_name)
            if text.strip():
                outline.append({
                    "level": level,
                    "title": text.strip(),
                    "page": current_page_num,
                })

        # 检测 page break 元素：paragraph 内的 run 可能包含 <w:br w:type="page"/>
        has_page_break = _paragraph_has_page_break(paragraph, qn)

        if text.strip():
            current_page_chunks.append(text)

        if has_page_break:
            pages.append("\n".join(current_page_chunks))
            current_page_chunks = []
            current_page_num += 1

    # 收尾：把最后一段内容作为一页
    if current_page_chunks or not pages:
        pages.append("\n".join(current_page_chunks))

    page_count = len(pages)
    full_text = "\n\n".join(pages)

    return {
        "text": full_text,
        "pageCount": page_count,
        "outline": outline,
        "pages": pages,
    }


def _parse_heading_level(style_name: str) -> int:
    """从 'Heading 1' / 'Heading 2' 等样式名解析层级。"""
    parts = style_name.split()
    for part in parts[1:]:
        if part.isdigit():
            return max(1, int(part))
    return 1


def _paragraph_has_page_break(paragraph, qn) -> bool:
    """检测段落中是否包含分页符元素 <w:br w:type="page"/>。

    借鉴 python-docx 社区通用做法，但变量名独立命名以避免与官方示例冲突。
    """
    try:
        for br in paragraph._element.findall(qn("w:r") + "/" + qn("w:br")):
            br_type = br.get(qn("w:type"))
            if br_type == "page":
                return True
    except Exception:
        # XML 解析失败时降级为不分页
        return False
    return False


# ──────────────────────────────────────────────────────────────
# TXT 解析
# ──────────────────────────────────────────────────────────────

def extract_txt(file_path: str) -> dict[str, Any]:
    """读取纯文本文件，视为单页文档。

    尝试 UTF-8 → GBK → Latin-1 顺序解码，提高兼容性。
    """
    if not os.path.isfile(file_path):
        return _empty_result(f"文件不存在: {file_path}")

    text_content: str | None = None
    encoding_tried: list[str] = []
    for encoding in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
        try:
            with open(file_path, encoding=encoding) as fh:
                text_content = fh.read()
            encoding_tried.append(encoding)
            break
        except UnicodeDecodeError:
            encoding_tried.append(f"{encoding}(fail)")
            continue
        except Exception as exc:
            logger.error(f"[CxPdfReader] extract_txt failed ({encoding}): {exc}")
            return _empty_result(f"TXT 文件读取失败: {exc}")

    if text_content is None:
        return _empty_result("TXT 文件解码失败（不支持 UTF-8/GBK/Latin-1）")

    return {
        "text": text_content,
        "pageCount": 1,
        "outline": [],
        "pages": [text_content],
    }


# ──────────────────────────────────────────────────────────────
# 统一入口
# ──────────────────────────────────────────────────────────────

def extract_document(file_path: str, max_pages: int | None = None) -> dict[str, Any]:
    """根据文件类型分发到对应解析器，返回统一结构 + fileType 字段。

    Args:
        file_path: 文档绝对路径
        max_pages: 可选的最大页数限制（仅对 PDF 生效）

    Returns:
        {text, pageCount, outline, pages, fileType} 或失败时 {error, fileType}
    """
    filename = os.path.basename(file_path)
    file_type = detect_file_type(filename)

    if file_type is None:
        logger.warning(f"[CxPdfReader] Unsupported file type: {filename}")
        return {
            **_empty_result(f"不支持的文件类型: {filename}"),
            "fileType": None,
        }

    if file_type == "pdf":
        result = extract_pdf(file_path, max_pages=max_pages)
    elif file_type == "docx":
        result = extract_docx(file_path)
    else:  # txt
        result = extract_txt(file_path)

    result["fileType"] = file_type
    return result
