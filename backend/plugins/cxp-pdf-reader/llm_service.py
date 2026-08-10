"""CxPlugin PDF 智能阅读器 — LLM 服务封装。

复用主项目已有的 LLM Provider 体系（app.runtime.provider.llm.adapter.llm_adapter），
不在插件内自行实现 OpenAI 调用，避免重复造轮子与凭证管理冲突。

提供三类 LLM 能力：
- summarize_text: 文档总结 + 关键点抽取
- translate_text: 文档翻译
- chat_with_document: 基于文档上下文的问答

设计原则：
- 所有调用走 llm_adapter.chat(return_raw=True)，同时拿到 content 与 usage
- 失败时返回清晰错误结构，不抛异常给上层 API handler
- 长文本自动截断（按字符数），避免超出模型上下文窗口
- 函数名使用 Cx 前缀的项目命名风格（LuminousChenXi 品牌）
"""
from __future__ import annotations

import re
from typing import Any

from loguru import logger

from app.runtime.provider.llm.adapter import llm_adapter

# ──────────────────────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────────────────────

# 单次送入 LLM 的文档字符上限（粗略保护，避免上下文溢出）
MAX_DOC_CHARS_FOR_LLM = 24000

# 默认调用参数
DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 2048


# ──────────────────────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────────────────────

def _truncate_for_llm(text: str, limit: int = MAX_DOC_CHARS_FOR_LLM) -> str:
    """截断文档以适配 LLM 上下文窗口，保留头部内容（通常含摘要/引言）。"""
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n[... 文档已被截断 ...]"


def _get_default_model_name() -> str:
    """获取当前默认 provider 的默认模型名，用于响应回显。"""
    try:
        provider = llm_adapter.get_provider(llm_adapter.default_provider)
        return getattr(provider, "default_model", "") or "unknown"
    except Exception as exc:
        logger.warning(f"[CxPdfReader] get default model failed: {exc}")
        return "unknown"


def _extract_tokens_used(raw_response: dict[str, Any]) -> int:
    """从 llm_adapter.chat(return_raw=True) 返回结构中提取 token 用量。"""
    usage = raw_response.get("usage") or {}
    if not isinstance(usage, dict):
        return 0
    # 优先 total_tokens，其次 prompt+completion
    total = usage.get("total_tokens")
    if isinstance(total, int):
        return total
    prompt = usage.get("prompt_tokens", 0) or 0
    completion = usage.get("completion_tokens", 0) or 0
    return int(prompt) + int(completion)


def _parse_key_points(summary_text: str) -> list[str]:
    """从总结文本中提取关键点列表。

    支持两种格式：
    1. 显式 "关键点:" / "Key Points:" 段落后的项目符号列表
    2. 文本中的项目符号行（- / • / 1. 2. 等）
    """
    if not summary_text:
        return []

    # 尝试定位 "关键点" 段落
    key_section_pattern = re.compile(
        r"(?:关键点|核心要点|key\s*points?|main\s*points?)\s*[:：]?\s*\n?(.*)",
        re.IGNORECASE | re.DOTALL,
    )
    match = key_section_pattern.search(summary_text)
    target_text = match.group(1) if match else summary_text

    # 提取项目符号行
    bullet_pattern = re.compile(r"^\s*(?:[-•*]|\d+[.)、])\s*(.+?)\s*$", re.MULTILINE)
    points = bullet_pattern.findall(target_text)
    # 过滤空与过长项
    cleaned: list[str] = []
    for p in points:
        p = p.strip().strip("。.").strip()
        if p and len(p) <= 500:
            cleaned.append(p)
    return cleaned[:10]  # 最多保留 10 条


# ──────────────────────────────────────────────────────────────
# 对外 LLM 能力
# ──────────────────────────────────────────────────────────────

async def summarize_text(
    text: str,
    max_length: int = 800,
    lang: str = "zh",
) -> dict[str, Any]:
    """生成文档总结与关键点。

    Args:
        text: 已提取的文档文本
        max_length: 总结大致字数上限
        lang: 总结语言代码（zh/en/ja 等）

    Returns:
        成功: {summary, keyPoints, model}
        失败: {error, model}
    """
    if not text or not text.strip():
        return {"error": "文档内容为空，无法生成总结", "model": _get_default_model_name()}

    model = _get_default_model_name()
    truncated = _truncate_for_llm(text)

    lang_label = {"zh": "中文", "en": "English", "ja": "日本語"}.get(lang, lang)
    system_prompt = (
        f"你是 LuomiNest 文档分析助手，请用{lang_label}对给定的文档进行总结。"
        f"总结控制在 {max_length} 字以内，并附上 3-8 条关键点。"
        "输出格式：\n【总结】\n<总结内容>\n\n【关键点】\n- 要点1\n- 要点2\n..."
    )
    user_prompt = f"文档内容如下：\n\n{truncated}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        raw = await llm_adapter.chat(
            messages,
            return_raw=True,
            temperature=DEFAULT_TEMPERATURE,
            max_tokens=DEFAULT_MAX_TOKENS,
        )
    except Exception as exc:
        logger.error(f"[CxPdfReader] summarize_text LLM call failed: {exc}")
        return {"error": f"LLM 调用失败: {exc}", "model": model}

    if not isinstance(raw, dict):
        return {"error": "LLM 返回格式异常", "model": model}

    content = str(raw.get("content") or "").strip()
    if not content:
        return {"error": "LLM 返回空内容", "model": model}

    key_points = _parse_key_points(content)
    return {
        "summary": content,
        "keyPoints": key_points,
        "model": model,
    }


async def translate_text(
    text: str,
    target_lang: str = "zh",
) -> dict[str, Any]:
    """翻译文档文本到目标语言。

    Args:
        text: 待翻译文本
        target_lang: 目标语言代码（zh/en/ja/fr/de 等）

    Returns:
        成功: {translation, targetLang, model}
        失败: {error, model}
    """
    if not text or not text.strip():
        return {"error": "待翻译内容为空", "model": _get_default_model_name()}

    model = _get_default_model_name()
    truncated = _truncate_for_llm(text)

    lang_label = {
        "zh": "中文", "en": "英文", "ja": "日文",
        "fr": "法文", "de": "德文", "ko": "韩文",
        "es": "西班牙文", "ru": "俄文",
    }.get(target_lang, target_lang)

    system_prompt = (
        f"你是 LuomiNest 专业翻译，请将用户提供的文档内容翻译为{lang_label}。"
        "要求：保持原文语义与结构，专业术语统一，不要解释、不要补充原文以外的内容，"
        "直接输出译文。"
    )
    user_prompt = f"原文：\n\n{truncated}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        raw = await llm_adapter.chat(
            messages,
            return_raw=True,
            temperature=DEFAULT_TEMPERATURE,
            max_tokens=DEFAULT_MAX_TOKENS,
        )
    except Exception as exc:
        logger.error(f"[CxPdfReader] translate_text LLM call failed: {exc}")
        return {"error": f"LLM 调用失败: {exc}", "model": model}

    if not isinstance(raw, dict):
        return {"error": "LLM 返回格式异常", "model": model}

    content = str(raw.get("content") or "").strip()
    if not content:
        return {"error": "LLM 返回空内容", "model": model}

    return {
        "translation": content,
        "targetLang": target_lang,
        "model": model,
    }


async def chat_with_document(
    doc_text: str,
    question: str,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """基于文档上下文回答用户问题。

    Args:
        doc_text: 文档全文（将被截断到上下文上限）
        question: 用户问题
        history: 可选的对话历史 [{role, content}, ...]

    Returns:
        成功: {answer, model, tokensUsed}
        失败: {error, model, tokensUsed: 0}
    """
    if not question or not question.strip():
        return {
            "error": "问题不能为空",
            "model": _get_default_model_name(),
            "tokensUsed": 0,
        }

    if not doc_text or not doc_text.strip():
        return {
            "error": "文档内容为空，无法回答",
            "model": _get_default_model_name(),
            "tokensUsed": 0,
        }

    model = _get_default_model_name()
    truncated = _truncate_for_llm(doc_text)

    system_prompt = (
        "你是 LuomiNest 文档问答助手。请仅基于下面提供的文档内容回答用户问题。"
        "如果文档中没有相关信息，请明确告知用户 '文档中未提及相关内容'，"
        "不要编造答案。回答应简洁准确，可适当引用文档原文。"
    )
    context_prompt = f"【文档内容】\n{truncated}\n【文档内容结束】"

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": context_prompt},
    ]

    # 追加历史对话（限制最近 6 轮防止上下文膨胀）
    if history:
        recent = history[-6:]
        for msg in recent:
            role = str(msg.get("role") or "").strip()
            content = str(msg.get("content") or "").strip()
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": question})

    try:
        raw = await llm_adapter.chat(
            messages,
            return_raw=True,
            temperature=DEFAULT_TEMPERATURE,
            max_tokens=DEFAULT_MAX_TOKENS,
        )
    except Exception as exc:
        logger.error(f"[CxPdfReader] chat_with_document LLM call failed: {exc}")
        return {
            "error": f"LLM 调用失败: {exc}",
            "model": model,
            "tokensUsed": 0,
        }

    if not isinstance(raw, dict):
        return {
            "error": "LLM 返回格式异常",
            "model": model,
            "tokensUsed": 0,
        }

    content = str(raw.get("content") or "").strip()
    if not content:
        return {
            "error": "LLM 返回空内容",
            "model": model,
            "tokensUsed": 0,
        }

    tokens_used = _extract_tokens_used(raw)
    return {
        "answer": content,
        "model": model,
        "tokensUsed": tokens_used,
    }
