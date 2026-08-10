"""CxPlugin PDF 智能阅读器 — LuomiNest 后端插件主入口。

提供 PDF / Word / TXT 文档的提取、AI 总结、AI 翻译、文档问答、大纲查询、
全文搜索、单页文本获取等能力。所有能力通过 admin_api 权限的 HTTP 路由暴露。

路由前缀: /api/v1/plugins/cxp-pdf-reader/

设计原则：
- 文件存储走 context.get_data_dir()，不使用硬编码路径
- 提取结果持久化为 JSON 文件，避免 KV store 承载大文本
- LLM 调用复用主项目 llm_adapter，不重复实现 OpenAI 客户端
- 所有响应使用 ApiResponse 统一格式（含 code/message/data 三字段）
- 错误码集中定义在常量模块，便于前后端对齐
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from typing import Any

# 将插件目录加入 sys.path，使 sibling 模块（extractors / llm_service）可被导入。
# CxPlugin loader 使用 importlib.util.spec_from_file_location 加载 main.py，
# 不会自动将插件目录注入 sys.path，因此需要在此显式添加。
_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
if _PLUGIN_DIR not in sys.path:
    sys.path.insert(0, _PLUGIN_DIR)

from datetime import UTC  # noqa: E402

import extractors as _extractors  # noqa: E402
import llm_service as _llm_service  # noqa: E402
from fastapi import UploadFile  # noqa: E402
from loguru import logger  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from app.runtime.plugin.cxplugin import CxPluginBase  # noqa: E402
from app.schemas.avatar import ApiResponse  # noqa: E402

# ──────────────────────────────────────────────────────────────
# 错误码常量
# ──────────────────────────────────────────────────────────────

CODE_OK = 0
CODE_UNSUPPORTED_TYPE = 1101
CODE_FILE_TOO_LARGE = 1102
CODE_PARSE_FAILED = 1103
CODE_FILE_NOT_FOUND = 1104
CODE_LLM_FAILED = 1105
CODE_PAGE_OUT_OF_RANGE = 1106
CODE_BAD_REQUEST = 1107

PLUGIN_VERSION = "1.0.0"
PLUGIN_ID = "cxp-pdf-reader"

# 文本预览长度
TEXT_PREVIEW_LENGTH = 500


# ──────────────────────────────────────────────────────────────
# 请求体模型
# ──────────────────────────────────────────────────────────────

class SummarizeRequest(BaseModel):
    file_id: str = Field(..., description="已提取文档的 fileId")
    max_length: int = Field(800, description="总结大致字数上限")


class TranslateRequest(BaseModel):
    file_id: str = Field(..., description="已提取文档的 fileId")
    target_lang: str = Field("zh", description="目标语言代码")
    page_range: list[int] | None = Field(None, description="可选 [start, end] 页码范围")


class ChatRequest(BaseModel):
    file_id: str = Field(..., description="已提取文档的 fileId")
    question: str = Field(..., description="用户问题")
    history: list[dict[str, Any]] | None = Field(None, description="对话历史")


class SearchRequest(BaseModel):
    file_id: str = Field(..., description="已提取文档的 fileId")
    query: str = Field(..., description="搜索关键词")
    max_results: int = Field(50, description="最大返回结果数")


class PageTextRequest(BaseModel):
    file_id: str = Field(..., description="已提取文档的 fileId")
    page_num: int = Field(..., description="页码（从 1 开始）")


# ──────────────────────────────────────────────────────────────
# 模块级插件实例引用（在 initialize 时注入）
# ──────────────────────────────────────────────────────────────

_plugin_instance: CxPdfReaderPlugin | None = None


def _get_plugin() -> CxPdfReaderPlugin:
    """获取当前插件实例。"""
    if _plugin_instance is None:
        raise RuntimeError("CxPdfReaderPlugin not initialized")
    return _plugin_instance


def _get_data_dir() -> str:
    """获取插件数据目录。"""
    return _get_plugin().context.get_data_dir()


def _get_max_file_size_mb() -> int:
    """读取配置的最大文件大小（MB）。"""
    return int(_get_plugin().context.get_config("max_file_size_mb", 50) or 50)


def _get_max_pages() -> int:
    """读取配置的单次最大提取页数。"""
    return int(_get_plugin().context.get_config("max_pages_per_extract", 30) or 30)


def _get_default_summary_lang() -> str:
    """读取配置的默认总结语言。"""
    return str(_get_plugin().context.get_config("default_summary_lang", "zh") or "zh")


def _get_default_translate_target() -> str:
    """读取配置的默认翻译目标语言。"""
    return str(_get_plugin().context.get_config("default_translate_target", "zh") or "zh")


# ──────────────────────────────────────────────────────────────
# 持久化辅助
# ──────────────────────────────────────────────────────────────

def _extracted_dir() -> str:
    """提取结果 JSON 存储目录。"""
    path = os.path.join(_get_data_dir(), "extracted")
    os.makedirs(path, exist_ok=True)
    return path


def _uploads_dir() -> str:
    """原始上传文件存储目录。"""
    path = os.path.join(_get_data_dir(), "uploads")
    os.makedirs(path, exist_ok=True)
    return path


def _save_extracted(file_id: str, payload: dict[str, Any]) -> str:
    """将提取结果保存为 JSON 文件，返回文件路径。"""
    path = os.path.join(_extracted_dir(), f"{file_id}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return path


def _load_extracted(file_id: str) -> dict[str, Any] | None:
    """根据 fileId 加载提取结果，不存在返回 None。"""
    path = os.path.join(_extracted_dir(), f"{file_id}.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        logger.warning(f"[CxPdfReader] load extracted failed: fileId={file_id}, error={exc}")
        return None


def _make_preview(text: str, length: int = TEXT_PREVIEW_LENGTH) -> str:
    """生成文本预览（截断 + 省略号）。"""
    if not text:
        return ""
    if len(text) <= length:
        return text
    return text[:length] + "..."


def _build_search_snippet(page_text: str, pos: int, query_len: int) -> str:
    """构造搜索结果片段（前后各取 50 字符上下文）。"""
    start = max(0, pos - 50)
    end = min(len(page_text), pos + query_len + 50)
    snippet = page_text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(page_text):
        snippet = snippet + "..."
    return snippet


def _now_iso() -> str:
    """当前 UTC 时间的 ISO 字符串。"""
    from datetime import datetime
    return datetime.now(UTC).isoformat()


# ──────────────────────────────────────────────────────────────
# 路由处理器
# ──────────────────────────────────────────────────────────────

async def handle_extract(file: UploadFile) -> ApiResponse:
    """POST /extract — 上传文件并提取文本。"""
    original_name = file.filename or "unknown"
    file_type = _extractors.detect_file_type(original_name)
    if file_type is None:
        return ApiResponse(
            code=CODE_UNSUPPORTED_TYPE,
            message=f"不支持的文件类型: {original_name}",
            data={"fileName": original_name},
        )

    try:
        content = await file.read()
    except Exception as exc:
        logger.error(f"[CxPdfReader] read upload failed: {exc}")
        return ApiResponse(
            code=CODE_PARSE_FAILED,
            message=f"读取上传文件失败: {exc}",
            data=None,
        )

    file_size_mb = len(content) / (1024 * 1024)
    if file_size_mb > _get_max_file_size_mb():
        return ApiResponse(
            code=CODE_FILE_TOO_LARGE,
            message=f"文件过大: {file_size_mb:.2f}MB > 上限 {_get_max_file_size_mb()}MB",
            data={"sizeMb": round(file_size_mb, 2), "limitMb": _get_max_file_size_mb()},
        )

    # 保存原始文件到 data/uploads/{fileId}/{originalName}
    file_id = uuid.uuid4().hex
    upload_dir = os.path.join(_uploads_dir(), file_id)
    os.makedirs(upload_dir, exist_ok=True)
    saved_path = os.path.join(upload_dir, original_name)
    try:
        with open(saved_path, "wb") as fh:
            fh.write(content)
    except Exception as exc:
        logger.error(f"[CxPdfReader] save upload failed: {exc}")
        return ApiResponse(
            code=CODE_PARSE_FAILED,
            message=f"保存上传文件失败: {exc}",
            data=None,
        )

    # 调用解析器
    extraction = _extractors.extract_document(saved_path, max_pages=_get_max_pages())
    if extraction.get("error"):
        return ApiResponse(
            code=CODE_PARSE_FAILED,
            message=extraction["error"],
            data={"fileId": file_id, "fileName": original_name},
        )

    # 持久化提取结果
    extracted_payload = {
        "fileId": file_id,
        "fileName": original_name,
        "fileType": extraction.get("fileType") or file_type,
        "pageCount": extraction.get("pageCount", 0),
        "outline": extraction.get("outline", []),
        "pages": extraction.get("pages", []),
        "text": extraction.get("text", ""),
        "originalPath": saved_path,
        "extractedAt": _now_iso(),
    }
    _save_extracted(file_id, extracted_payload)

    logger.info(
        f"[CxPdfReader] extract success: fileId={file_id}, name={original_name}, "
        f"pages={extracted_payload['pageCount']}, chars={len(extracted_payload['text'])}"
    )

    return ApiResponse(
        code=CODE_OK,
        data={
            "fileId": file_id,
            "fileName": original_name,
            "fileType": extracted_payload["fileType"],
            "pageCount": extracted_payload["pageCount"],
            "outline": extracted_payload["outline"],
            "textPreview": _make_preview(extracted_payload["text"]),
            "extractedAt": extracted_payload["extractedAt"],
        },
    )


async def handle_summarize(body: SummarizeRequest) -> ApiResponse:
    """POST /summarize — AI 总结。"""
    extracted = _load_extracted(body.file_id)
    if not extracted:
        return ApiResponse(
            code=CODE_FILE_NOT_FOUND,
            message=f"fileId 不存在: {body.file_id}",
            data={"fileId": body.file_id},
        )

    result = await _llm_service.summarize_text(
        text=extracted.get("text", ""),
        max_length=body.max_length,
        lang=_get_default_summary_lang(),
    )

    if result.get("error"):
        return ApiResponse(
            code=CODE_LLM_FAILED,
            message=result["error"],
            data={"fileId": body.file_id, "model": result.get("model", "")},
        )

    return ApiResponse(
        code=CODE_OK,
        data={
            "summary": result.get("summary", ""),
            "keyPoints": result.get("keyPoints", []),
            "model": result.get("model", ""),
        },
    )


async def handle_translate(body: TranslateRequest) -> ApiResponse:
    """POST /translate — AI 翻译。"""
    extracted = _load_extracted(body.file_id)
    if not extracted:
        return ApiResponse(
            code=CODE_FILE_NOT_FOUND,
            message=f"fileId 不存在: {body.file_id}",
            data={"fileId": body.file_id},
        )

    # 处理 page_range：可选地只翻译指定页码范围
    text_to_translate = extracted.get("text", "")
    pages = extracted.get("pages", []) or []
    if body.page_range and len(body.page_range) == 2 and pages:
        start_page, end_page = body.page_range
        start_page = max(1, start_page)
        end_page = min(len(pages), end_page)
        if start_page <= end_page:
            text_to_translate = "\n\n".join(pages[start_page - 1:end_page])

    result = await _llm_service.translate_text(
        text=text_to_translate,
        target_lang=body.target_lang or _get_default_translate_target(),
    )

    if result.get("error"):
        return ApiResponse(
            code=CODE_LLM_FAILED,
            message=result["error"],
            data={"fileId": body.file_id, "model": result.get("model", "")},
        )

    return ApiResponse(
        code=CODE_OK,
        data={
            "translation": result.get("translation", ""),
            "targetLang": result.get("targetLang", body.target_lang),
            "model": result.get("model", ""),
        },
    )


async def handle_chat(body: ChatRequest) -> ApiResponse:
    """POST /chat — 文档问答。"""
    extracted = _load_extracted(body.file_id)
    if not extracted:
        return ApiResponse(
            code=CODE_FILE_NOT_FOUND,
            message=f"fileId 不存在: {body.file_id}",
            data={"fileId": body.file_id},
        )

    result = await _llm_service.chat_with_document(
        doc_text=extracted.get("text", ""),
        question=body.question,
        history=body.history,
    )

    if result.get("error"):
        return ApiResponse(
            code=CODE_LLM_FAILED,
            message=result["error"],
            data={
                "fileId": body.file_id,
                "model": result.get("model", ""),
                "tokensUsed": result.get("tokensUsed", 0),
            },
        )

    return ApiResponse(
        code=CODE_OK,
        data={
            "answer": result.get("answer", ""),
            "model": result.get("model", ""),
            "tokensUsed": result.get("tokensUsed", 0),
        },
    )


async def handle_outline(file_id: str) -> ApiResponse:
    """GET /outline/{fileId} — 获取大纲。"""
    extracted = _load_extracted(file_id)
    if not extracted:
        return ApiResponse(
            code=CODE_FILE_NOT_FOUND,
            message=f"fileId 不存在: {file_id}",
            data={"fileId": file_id},
        )
    return ApiResponse(
        code=CODE_OK,
        data={"outline": extracted.get("outline", [])},
    )


async def handle_search(body: SearchRequest) -> ApiResponse:
    """POST /search — 全文搜索。"""
    extracted = _load_extracted(body.file_id)
    if not extracted:
        return ApiResponse(
            code=CODE_FILE_NOT_FOUND,
            message=f"fileId 不存在: {body.file_id}",
            data={"fileId": body.file_id},
        )

    query = body.query or ""
    if not query.strip():
        return ApiResponse(
            code=CODE_BAD_REQUEST,
            message="搜索关键词不能为空",
            data={"fileId": body.file_id},
        )

    pages = extracted.get("pages", []) or []
    max_results = max(1, body.max_results)
    matches: list[dict[str, Any]] = []
    query_len = len(query)

    for page_idx, page_text in enumerate(pages):
        if not page_text:
            continue
        start = 0
        while True:
            pos = page_text.find(query, start)
            if pos == -1:
                break
            matches.append({
                "page": page_idx + 1,
                "text": _build_search_snippet(page_text, pos, query_len),
                "position": pos,
            })
            start = pos + 1
            if len(matches) >= max_results:
                break
        if len(matches) >= max_results:
            break

    return ApiResponse(
        code=CODE_OK,
        data={
            "matches": matches,
            "total": len(matches),
        },
    )


async def handle_page_text(body: PageTextRequest) -> ApiResponse:
    """POST /page-text — 获取单页文本。"""
    extracted = _load_extracted(body.file_id)
    if not extracted:
        return ApiResponse(
            code=CODE_FILE_NOT_FOUND,
            message=f"fileId 不存在: {body.file_id}",
            data={"fileId": body.file_id},
        )

    pages = extracted.get("pages", []) or []
    page_num = body.page_num
    if page_num < 1 or page_num > len(pages):
        return ApiResponse(
            code=CODE_PAGE_OUT_OF_RANGE,
            message=f"页码超出范围: {page_num}, 总页数 {len(pages)}",
            data={"fileId": body.file_id, "pageNum": page_num, "pageCount": len(pages)},
        )

    return ApiResponse(
        code=CODE_OK,
        data={
            "text": pages[page_num - 1],
            "pageNum": page_num,
        },
    )


async def handle_health() -> ApiResponse:
    """GET /health — 健康检查。"""
    return ApiResponse(
        code=CODE_OK,
        data={
            "status": "ok",
            "version": PLUGIN_VERSION,
            "plugin": PLUGIN_ID,
        },
    )


# ──────────────────────────────────────────────────────────────
# 插件主类
# ──────────────────────────────────────────────────────────────

class CxPdfReaderPlugin(CxPluginBase):
    """CxPlugin PDF 智能阅读器主类。

    在 initialize 阶段通过 context.register_api_route 注册 8 条 HTTP 路由，
    所有路由需 admin_api 权限（已在 manifest.permissions 中声明）。
    """

    plugin_name = "CxPlugin PDF 智能阅读器"
    plugin_version = PLUGIN_VERSION
    plugin_description = "PDF/Word/TXT 文档阅读与 AI 总结/翻译/问答插件"
    plugin_author = "LuminousCX"

    async def initialize(self) -> None:
        global _plugin_instance
        _plugin_instance = self

        # 注册 8 条 API 路由（均挂载到 /api/v1/plugins/cxp-pdf-reader/ 前缀下）
        self.context.register_api_route("extract", handle_extract, methods=["POST"])
        self.context.register_api_route("summarize", handle_summarize, methods=["POST"])
        self.context.register_api_route("translate", handle_translate, methods=["POST"])
        self.context.register_api_route("chat", handle_chat, methods=["POST"])
        self.context.register_api_route("outline/{file_id}", handle_outline, methods=["GET"])
        self.context.register_api_route("search", handle_search, methods=["POST"])
        self.context.register_api_route("page-text", handle_page_text, methods=["POST"])
        self.context.register_api_route("health", handle_health, methods=["GET"])

        self.logger.info(
            f"[CxPdfReader] Plugin initialized: version={PLUGIN_VERSION}, "
            f"data_dir={self.context.get_data_dir()}"
        )

    async def terminate(self) -> None:
        self.logger.info("[CxPdfReader] Plugin terminated")
