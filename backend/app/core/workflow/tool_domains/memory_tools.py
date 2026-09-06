"""记忆中枢模块的内部工具处理函数（memory.*）。

从原 register_tools.py 拆出（大文件拆分重构），处理函数体保持原样；
注册顺序与 schema 见 register_tools.register_internal_tools。
"""

import json
from typing import Any

from loguru import logger

from app.core.workflow.models import WorkflowTaskResult
from app.core.workflow.tool_domains.common import _get_emitter, _wf_catch


class _MemoryEngineNotReady(Exception):
    """记忆引擎未初始化"""
    pass


def _require_memory_engine():
    """获取记忆引擎实例，未初始化则抛出异常（由 @_wf_catch 统一捕获）。"""
    from app.engines.memory import get_memory_engine
    engine = get_memory_engine()
    if engine is None:
        raise _MemoryEngineNotReady("Memory engine not initialized")
    return engine


@_wf_catch("memory.search")
async def _memory_search(args: dict[str, Any]) -> WorkflowTaskResult:
    """语义检索记忆中枢（基于向量检索）"""
    query = args.get("query", "")
    top_k = args.get("top_k", 5)

    if not query:
        return WorkflowTaskResult(success=False, error="Missing required parameter: query")

    engine = _require_memory_engine()

    results = await engine.vector_retrieve(query=query, k=top_k)
    results_count = len(results) if isinstance(results, list) else 0
    output = json.dumps(results, ensure_ascii=False, default=str) if results else "未找到相关记忆"

    # 推送工作流事件
    emitter = _get_emitter()
    if emitter:
        await emitter.emit_memory_recalled(
            query=query,
            results_count=results_count,
        )

    return WorkflowTaskResult(
        success=True,
        output=output,
        metadata={"count": results_count},
    )


@_wf_catch("memory.build_context")
async def _memory_build_context(args: dict[str, Any]) -> WorkflowTaskResult:
    """构建记忆上下文（按优先级注入档案/事实/知识/每日记录）"""
    query = args.get("query", "")
    conversation_id = args.get("conversation_id")
    max_chars = args.get("max_chars", 4000)

    engine = _require_memory_engine()

    context = engine.build_context(
        max_chars=max_chars,
        query=query,
        conversation_id=conversation_id,
    )

    return WorkflowTaskResult(
        success=True,
        output=context or "（无可用记忆上下文）",
        metadata={"query": query, "conversation_id": conversation_id},
    )


@_wf_catch("memory.update_knowledge")
async def _memory_update_knowledge(args: dict[str, Any]) -> WorkflowTaskResult:
    """更新知识库内容"""
    content = args.get("content", "")
    if not content:
        return WorkflowTaskResult(success=False, error="Missing required parameter: content")

    engine = _require_memory_engine()
    engine.save_knowledge(content)

    emitter = _get_emitter()
    if emitter:
        await emitter.emit_memory_stored(
            memory_id="knowledge",
            content=content[:200],
            category="knowledge",
        )

    logger.info(f"[Workflow:memory.update_knowledge] content_len={len(content)}")
    return WorkflowTaskResult(
        success=True,
        output=f"已更新知识库（{len(content)} 字符）",
    )


@_wf_catch("memory.update_profile")
async def _memory_update_profile(args: dict[str, Any]) -> WorkflowTaskResult:
    """更新用户画像（通过写入 memory.md 解析 name 和 static_facts）"""
    content = args.get("content", "")
    if not content:
        return WorkflowTaskResult(success=False, error="Missing required parameter: content")

    engine = _require_memory_engine()
    engine.save_memory(content)
    profile = engine.parse_profile()

    logger.info(f"[Workflow:memory.update_profile] name={profile.get('name', '')}")
    return WorkflowTaskResult(
        success=True,
        output=f"已更新用户画像（name={profile.get('name', '未知')}）",
        metadata={"profile": profile},
    )


@_wf_catch("memory.append_daily")
async def _memory_append_daily(args: dict[str, Any]) -> WorkflowTaskResult:
    """追加每日记录"""
    content = args.get("content", "")
    date = args.get("date")
    conversation_id = args.get("conversation_id")

    if not content:
        return WorkflowTaskResult(success=False, error="Missing required parameter: content")

    engine = _require_memory_engine()
    engine.append_daily(content, date, conversation_id=conversation_id)

    logger.info(f"[Workflow:memory.append_daily] date={date or 'today'}, len={len(content)}")
    return WorkflowTaskResult(
        success=True,
        output=f"已追加每日记录（{date or '今天'}）",
    )


@_wf_catch("memory.get_daily")
async def _memory_get_daily(args: dict[str, Any]) -> WorkflowTaskResult:
    """获取每日记录"""
    date = args.get("date")
    conversation_id = args.get("conversation_id")

    engine = _require_memory_engine()
    content = engine.load_daily(date, conversation_id)

    return WorkflowTaskResult(
        success=True,
        output=content or "（无每日记录）",
        metadata={"date": date or "today", "conversation_id": conversation_id},
    )


@_wf_catch("memory.list_dailies")
async def _memory_list_dailies(args: dict[str, Any]) -> WorkflowTaskResult:
    """列出有每日记录的日期"""
    conversation_id = args.get("conversation_id")

    engine = _require_memory_engine()
    dates = engine.list_dailies(conversation_id)

    return WorkflowTaskResult(
        success=True,
        output=json.dumps(dates, ensure_ascii=False),
        metadata={"count": len(dates), "conversation_id": conversation_id},
    )


@_wf_catch("memory.vector_rebuild")
async def _memory_vector_rebuild(args: dict[str, Any]) -> WorkflowTaskResult:
    """重建记忆向量索引"""
    conversation_id = args.get("conversation_id")

    engine = _require_memory_engine()
    count = await engine.vector_rebuild(conversation_id)

    logger.info(f"[Workflow:memory.vector_rebuild] indexed={count}")
    return WorkflowTaskResult(
        success=True,
        output=f"已重建向量索引（{count} 条）",
        metadata={"indexed_count": count},
    )


@_wf_catch("memory.promote_conversation_facts")
async def _memory_promote_conversation_facts(args: dict[str, Any]) -> WorkflowTaskResult:
    """将对话级事实提升为 Agent 级"""
    conversation_id = args.get("conversation_id", "")
    fact_ids = args.get("fact_ids")

    if not conversation_id:
        return WorkflowTaskResult(success=False, error="Missing required parameter: conversation_id")

    engine = _require_memory_engine()
    promoted_count = engine.promote_conversation_facts(conversation_id, fact_ids)

    logger.info(f"[Workflow:memory.promote_conversation_facts] promoted={promoted_count}")
    return WorkflowTaskResult(
        success=True,
        output=f"已提升 {promoted_count} 条对话级事实到 Agent 级",
        metadata={"promoted_count": promoted_count},
    )


@_wf_catch("memory.clear_facts")
async def _memory_clear_facts(args: dict[str, Any]) -> WorkflowTaskResult:
    """清空所有事实"""
    engine = _require_memory_engine()
    engine.clear_facts()

    logger.info("[Workflow:memory.clear_facts] all facts cleared")
    return WorkflowTaskResult(
        success=True,
        output="已清空所有事实",
    )


@_wf_catch("memory.list_facts")
async def _memory_list_facts(args: dict[str, Any]) -> WorkflowTaskResult:
    """列出记忆中枢的事实（支持分类过滤）"""
    category = args.get("category")
    limit = min(args.get("limit", 100), 500)

    engine = _require_memory_engine()
    facts = engine.get_facts(category)
    fact_list = [f.model_dump() for f in facts[:limit]]

    return WorkflowTaskResult(
        success=True,
        output=json.dumps(fact_list, ensure_ascii=False),
        metadata={"count": len(fact_list), "category": category or "all"},
    )


@_wf_catch("memory.create_fact")
async def _memory_create_fact(args: dict[str, Any]) -> WorkflowTaskResult:
    """在记忆中枢创建事实"""
    content = args.get("content", "")
    category = args.get("category", "context")
    confidence = args.get("confidence", 0.8)

    if not content:
        return WorkflowTaskResult(success=False, error="Missing required parameter: content")

    from app.engines.memory.memory_engine import FACT_CATEGORIES, FactItem

    if category not in FACT_CATEGORIES:
        return WorkflowTaskResult(
            success=False,
            error=f"Invalid category. Must be one of: {FACT_CATEGORIES}",
        )

    engine = _require_memory_engine()
    fact = FactItem(
        content=content,
        category=category,
        confidence=confidence,
        source="workflow",
    )
    engine.add_fact(fact)

    emitter = _get_emitter()
    if emitter:
        await emitter.emit_module_action(
            module="memory",
            action="fact_created",
            success=True,
            output=f"已创建事实: {content[:100]}",
            metadata={"fact_id": fact.id, "category": category},
        )

    return WorkflowTaskResult(
        success=True,
        output=f"已创建事实: {content[:100]}",
        metadata={"fact_id": fact.id, "category": category},
    )


@_wf_catch("memory.update_fact")
async def _memory_update_fact(args: dict[str, Any]) -> WorkflowTaskResult:
    """更新记忆中枢的事实"""
    fact_id = args.get("fact_id", "")
    content = args.get("content")
    category = args.get("category")
    confidence = args.get("confidence")

    if not fact_id:
        return WorkflowTaskResult(success=False, error="Missing required parameter: fact_id")

    from app.engines.memory.memory_engine import FACT_CATEGORIES

    if category is not None and category not in FACT_CATEGORIES:
        return WorkflowTaskResult(
            success=False,
            error=f"Invalid category. Must be one of: {FACT_CATEGORIES}",
        )

    engine = _require_memory_engine()
    success = engine.update_fact(fact_id, content, category, confidence)
    if not success:
        return WorkflowTaskResult(success=False, error=f"事实 {fact_id} 不存在")

    emitter = _get_emitter()
    if emitter:
        await emitter.emit_module_action(
            module="memory",
            action="fact_updated",
            success=True,
            output=f"已更新事实: {fact_id}",
            metadata={"fact_id": fact_id},
        )

    return WorkflowTaskResult(
        success=True,
        output=f"已更新事实: {fact_id}",
        metadata={"fact_id": fact_id},
    )


@_wf_catch("memory.delete_fact")
async def _memory_delete_fact(args: dict[str, Any]) -> WorkflowTaskResult:
    """删除记忆中枢的事实"""
    fact_id = args.get("fact_id", "")
    if not fact_id:
        return WorkflowTaskResult(success=False, error="Missing required parameter: fact_id")

    engine = _require_memory_engine()
    success = engine.remove_fact(fact_id)
    if not success:
        return WorkflowTaskResult(success=False, error=f"事实 {fact_id} 不存在")

    emitter = _get_emitter()
    if emitter:
        await emitter.emit_module_action(
            module="memory",
            action="fact_deleted",
            success=True,
            output=f"已删除事实: {fact_id}",
            metadata={"fact_id": fact_id},
        )

    return WorkflowTaskResult(
        success=True,
        output=f"已删除事实: {fact_id}",
        metadata={"fact_id": fact_id},
    )


@_wf_catch("memory.get_summary")
async def _memory_get_summary(args: dict[str, Any]) -> WorkflowTaskResult:
    """获取记忆中枢的摘要"""
    engine = _require_memory_engine()
    content = engine.load_summary()

    return WorkflowTaskResult(
        success=True,
        output=content or "暂无摘要",
        metadata={"length": len(content)},
    )


@_wf_catch("memory.update_summary")
async def _memory_update_summary(args: dict[str, Any]) -> WorkflowTaskResult:
    """更新记忆中枢的摘要"""
    content = args.get("content", "")
    if not content:
        return WorkflowTaskResult(success=False, error="Missing required parameter: content")

    engine = _require_memory_engine()
    engine.save_summary(content)

    emitter = _get_emitter()
    if emitter:
        await emitter.emit_module_action(
            module="memory",
            action="summary_updated",
            success=True,
            output=f"已更新摘要（{len(content)} 字符）",
            metadata={"length": len(content)},
        )

    return WorkflowTaskResult(
        success=True,
        output="已更新记忆摘要",
        metadata={"length": len(content)},
    )


@_wf_catch("memory.get_knowledge")
async def _memory_get_knowledge(args: dict[str, Any]) -> WorkflowTaskResult:
    """获取记忆中枢的知识库"""
    engine = _require_memory_engine()
    content = engine.load_knowledge()

    return WorkflowTaskResult(
        success=True,
        output=content or "暂无知识库内容",
        metadata={"length": len(content)},
    )


@_wf_catch("memory.get_profile")
async def _memory_get_profile(args: dict[str, Any]) -> WorkflowTaskResult:
    """获取用户画像"""
    engine = _require_memory_engine()
    profile = engine.parse_profile()

    return WorkflowTaskResult(
        success=True,
        output=json.dumps(profile, ensure_ascii=False),
        metadata=profile,
    )


@_wf_catch("memory.distill")
async def _memory_distill(args: dict[str, Any]) -> WorkflowTaskResult:
    """蒸馏对话为记忆"""
    messages = args.get("messages", [])
    if not messages:
        return WorkflowTaskResult(success=False, error="Missing required parameter: messages")

    engine = _require_memory_engine()
    result = await engine.distill_conversation(messages)

    emitter = _get_emitter()
    if emitter:
        await emitter.emit_module_action(
            module="memory",
            action="distilled",
            success=True,
            output="对话已蒸馏为记忆" if result else "无需蒸馏",
            metadata={"has_change": bool(result)},
        )

    return WorkflowTaskResult(
        success=True,
        output=result or "对话无需蒸馏",
        metadata={"has_change": bool(result)},
    )
