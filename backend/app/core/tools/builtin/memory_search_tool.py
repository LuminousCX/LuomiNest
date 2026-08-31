"""LuomiNest 记忆主动搜索工具。

供群聊 Agent 主动深挖主 Agent 的记忆。基于 contextvars 权限控制：
- "none"：拒绝访问（联系人 Agent 默认）
- "read_main"：可读主 Agent 记忆（群聊 Agent）
- "read_write"：可读写自身记忆（工作台主 Agent，记忆即主 Agent 记忆）

设计原则（参考 综合调查.md §5 群聊改造）：
- 群聊 Agent 不做被动记忆注入（避免上下文膨胀），改为主动工具调用
- 仅查询主 Agent 记忆，不写入
- 联系人 Agent 无权限，工具返回友好提示

品牌化命名：LuomiNestMemorySearchTool。
"""
from typing import Any

from loguru import logger

from app.core.agents.memory_access import (
    get_luominest_memory_access,
    MEMORY_ACCESS_NONE,
)
from app.core.tools.registry import ToolBase, ToolResult


class LuomiNestMemorySearchTool(ToolBase):
    """主动搜索主 Agent 记忆的工具

    群聊 Agent 可通过本工具查询主 Agent 的长期记忆，获取用户偏好、历史事实等。
    权限由当前异步上下文的 memory_access contextvar 决定。
    """

    @property
    def name(self) -> str:
        return "memory_search"

    @property
    def description(self) -> str:
        return (
            "搜索主 Agent 的长期记忆，获取用户偏好、历史事实、过往对话要点等。"
            "适用于：1. 需要了解用户习惯和偏好的场景；"
            "2. 需要引用过往对话事实的场景；"
            "3. 需要个性化回应时深挖用户信息。"
            "返回与查询最相关的记忆条目（含内容、分类、置信度）。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询（应清晰描述想查找的记忆内容，如「用户喜欢的编程语言」「用户的饮食习惯」）",
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回结果数量（默认 5，最大 10）",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        query = arguments.get("query", "").strip()
        if not query:
            return ToolResult.fail("缺少 query 参数")

        top_k = arguments.get("top_k", 5)
        try:
            top_k = int(top_k)
        except (TypeError, ValueError):
            top_k = 5
        top_k = max(1, min(top_k, 10))

        # 权限检查：读取当前异步上下文的记忆访问级别
        access_level = get_luominest_memory_access()
        if access_level == MEMORY_ACCESS_NONE:
            return ToolResult.fail(
                "当前 Agent 无记忆访问权限。联系人 Agent 不可查询记忆，"
                "仅群聊 Agent 可查主 Agent 记忆。"
            )

        # 延迟导入避免循环依赖
        try:
            from app.engines.memory import get_memory_engine
            from app.services.context_service import MAIN_AGENT_ID
        except Exception as e:
            logger.error(f"[MemorySearch] 导入记忆引擎失败: {e}")
            return ToolResult.fail(f"记忆引擎不可用: {e}")

        try:
            engine = get_memory_engine(MAIN_AGENT_ID)
        except Exception as e:
            logger.error(f"[MemorySearch] 获取主 Agent 记忆引擎失败: {e}")
            return ToolResult.fail(f"记忆引擎初始化失败: {e}")

        # 向量语义召回
        try:
            scored_facts = await engine.vector_retrieve(query=query, k=top_k)
        except Exception as e:
            logger.error(f"[MemorySearch] 向量召回失败: {e}", exc_info=True)
            return ToolResult.fail(f"记忆搜索失败: {e}")

        if not scored_facts:
            return ToolResult.ok(
                "未找到相关记忆。",
                metadata={"query": query, "result_count": 0},
            )

        # 反查 fact 内容（仅有效事实：is_latest 且未过期，向量索引过期条目兜底过滤）
        try:
            from datetime import datetime, timezone

            memory_data = engine.load_data()
            valid_facts = []
            for f in memory_data.facts:
                if not f.is_latest:
                    continue
                if f.expires_at:
                    try:
                        exp_time = datetime.fromisoformat(f.expires_at.replace("Z", "+00:00"))
                        if exp_time <= datetime.now(timezone.utc):
                            continue
                    except (ValueError, TypeError):
                        pass
                valid_facts.append(f)
            fact_map = {f.id: f for f in valid_facts}
        except Exception as e:
            logger.error(f"[MemorySearch] 加载记忆数据失败: {e}", exc_info=True)
            return ToolResult.fail(f"记忆数据加载失败: {e}")

        # 格式化结果
        result_lines: list[str] = []
        matched_count = 0
        for scored in scored_facts:
            fact = fact_map.get(scored.fact_id)
            if not fact:
                continue
            matched_count += 1
            result_lines.append(
                f"[{matched_count}] (分类: {fact.category}, 置信度: {fact.confidence:.2f}, "
                f"相似度: {scored.score:.2f})\n{fact.content}"
            )

        if not result_lines:
            return ToolResult.ok(
                "找到记忆条目但无法解析内容。",
                metadata={"query": query, "result_count": 0},
            )

        result_text = f"查询「{query}」找到 {matched_count} 条相关记忆：\n\n" + "\n\n".join(result_lines)
        logger.info(
            f"[MemorySearch] 查询成功: query_len={len(query)}, "
            f"matched={matched_count}, access={access_level}"
        )
        return ToolResult.ok(
            result_text,
            metadata={"query": query, "result_count": matched_count},
        )
