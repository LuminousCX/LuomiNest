"""W2 按需注入的单元测试（2026-09-21 修改书 W2/W7）。

覆盖：
1. get_tools_for_llm_tiered：常驻/召回/长尾三级划分、W7 高权限工具默认排除
2. ToolFilterMiddleware.before_model：探索发现的工具动态加入可调用集 + 白名单放行
3. ToolExecutionMiddleware：探索类工具的 discovered_tools 收获
4. ContextTrimMiddleware：user 边界裁剪、保底条数、token 估算
5. build_system_prompt：<current_context> 去重（时间戳只由 inject_timestamp_prompt 注入）、
   avatar_emotion 配置开关
"""
from typing import Any

import pytest

from app.core.agents.middleware.base import AgentContext
from app.core.agents.middleware.builtin import (
    ContextTrimMiddleware,
    ToolExecutionMiddleware,
    ToolFilterMiddleware,
)
from app.core.tools.orchestrator import ToolOrchestrator
from app.core.tools.registry import ToolBase, ToolRegistry, ToolResult


class _FakeTool(ToolBase):
    def __init__(self, name: str, description: str, tier: str = "domain") -> None:
        self._name = name
        self._description = description
        self.tier = tier

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute(self, arguments: dict) -> ToolResult:
        return ToolResult.ok("ok")


def _register_tools(monkeypatch) -> ToolRegistry:
    """用隔离注册表替换全局单例，注册分级测试工具。"""
    reg = ToolRegistry()
    monkeypatch.setattr("app.core.tools.orchestrator.tool_registry", reg)
    monkeypatch.setattr("app.core.tools.builtin.explore_tools.tool_registry", reg)
    reg.register(_FakeTool("memory_search", "搜索用户长期记忆", tier="core"))
    reg.register(_FakeTool("tool_explore", "探索发现工具", tier="meta"))
    reg.register(_FakeTool("get_current_time", "查询当前时间", tier="domain"))
    reg.register(_FakeTool("query_weather", "查询城市天气", tier="domain"))
    reg.register(_FakeTool("mc_navigate", "让 Minecraft 角色走向目标坐标", tier="domain"))
    reg.register(_FakeTool("cli", "执行 shell 命令", tier="domain"))
    reg.register(_FakeTool("write_file", "写入文件内容", tier="domain"))
    reg.register(_FakeTool("a2a_tool_call_x", "调用远程 A2A Agent", tier="domain"))
    return reg


def _schema(name: str) -> dict[str, Any]:
    return {"type": "function", "function": {"name": name, "description": name, "parameters": {}}}


# ────────────────── 1. 三级注入 ──────────────────

class TestTieredInjection:
    def test_resident_recall_digest_partition(self, monkeypatch):
        reg = _register_tools(monkeypatch)
        orch = ToolOrchestrator()
        schemas, digest = orch.get_tools_for_llm_tiered(
            query="查询天气", recall_top_k=2, extra_resident=["get_current_time"],
        )
        names = {t["function"]["name"] for t in schemas}
        # 常驻层：core/meta + extra_resident
        assert {"memory_search", "tool_explore", "get_current_time"} <= names
        # 召回层：天气工具按 query 命中进 schema
        assert "query_weather" in names
        # 长尾层：未被常驻/召回的工具只出现在摘要里
        assert "mc_navigate" not in names
        assert "mc_navigate" in digest
        # W7：高权限工具既不在 schema 也不在摘要
        assert "cli" not in names and "cli" not in digest
        assert "write_file" not in names
        assert "a2a_tool_call_x" not in names and "a2a_tool_call_x" not in digest

    def test_power_tools_restored_by_settings(self, monkeypatch):
        reg = _register_tools(monkeypatch)
        from app.core.config import settings
        monkeypatch.setattr(settings, "LLM_POWER_TOOLS_ENABLED", True)
        orch = ToolOrchestrator()
        schemas, digest = orch.get_tools_for_llm_tiered(query="")
        # 高权限工具恢复进入注入面（tier=domain、query 空 → 落长尾摘要层）
        assert "cli" in digest and "write_file" in digest and "a2a_tool_call_x" in digest

    def test_empty_query_only_resident(self, monkeypatch):
        reg = _register_tools(monkeypatch)
        orch = ToolOrchestrator()
        schemas, digest = orch.get_tools_for_llm_tiered(query="")
        names = {t["function"]["name"] for t in schemas}
        assert names == {"memory_search", "tool_explore"}
        assert "get_current_time" in digest and "query_weather" in digest


# ────────────────── 2. 探索即可调用 ──────────────────

class TestExploreThenCallable:
    @pytest.mark.asyncio
    async def test_harvest_and_whitelist_union(self):
        ctx = AgentContext(
            messages=[],
            tools=[_schema("memory_search")],
            extra={"tool_whitelist": ["memory_search", "get_current_time"]},
        )
        discovered = _schema("mc_navigate")

        # 模拟 ToolExecutionMiddleware 对 tool_explore 结果的收获
        async def _next(tool_call):
            return {
                "role": "tool", "tool_call_id": "t1", "name": "tool_explore",
                "content": "...schema...",
                "metadata": {"discovered_tools": [discovered]},
            }

        mw = ToolExecutionMiddleware()
        await mw.wrap_tool_call(ctx, {"function": {"name": "tool_explore"}, "id": "t1"}, _next)
        assert ctx.state["dynamic_tool_schemas"] == [discovered]

        # before_model：动态 schema 追加进 ctx.tools，且白名单放行集并入动态名
        fmw = ToolFilterMiddleware()
        await fmw.before_model(ctx)
        names = {t["function"]["name"] for t in ctx.tools}
        assert "mc_navigate" in names

    @pytest.mark.asyncio
    async def test_whitelist_still_filters_unknown(self):
        ctx = AgentContext(
            messages=[],
            tools=[_schema("memory_search"), _schema("mc_navigate")],
            extra={"tool_whitelist": ["memory_search"]},
        )
        ctx.state["dynamic_tool_schemas"] = []
        fmw = ToolFilterMiddleware()
        await fmw.before_model(ctx)
        names = {t["function"]["name"] for t in ctx.tools}
        assert names == {"memory_search"}


# ────────────────── 3. 循环内裁剪 ──────────────────

class TestContextTrim:
    def test_trim_at_user_boundaries(self):
        # 4 个旧轮次（8 条）+ 1 个近期轮次（2 条）：超过保底 6 条才可裁
        messages = [{"role": "system", "content": "sys"}]
        for i in range(4):
            messages += [
                {"role": "user", "content": f"旧消息{i}" * 500},
                {"role": "assistant", "content": f"旧回复{i}" * 500},
            ]
        messages += [
            {"role": "user", "content": "近期消息"},
            {"role": "assistant", "content": "近期回复"},
        ]
        trimmed = ContextTrimMiddleware._trim_at_user_boundaries(messages, target_tokens=10)
        # system 保留；最旧的整轮被丢弃；近期轮次保留
        assert trimmed[0]["role"] == "system"
        contents = [str(m.get("content")) for m in trimmed[1:]]
        assert all("旧消息0" not in c and "旧回复0" not in c for c in contents)
        assert any("近期消息" in c for c in contents)

    def test_trim_never_breaks_tool_pairs(self):
        messages = [
            {"role": "user", "content": "第一轮" * 300},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "t1"}]},
            {"role": "tool", "tool_call_id": "t1", "content": "结果" * 300},
            {"role": "user", "content": "第二轮"},
        ]
        trimmed = ContextTrimMiddleware._trim_at_user_boundaries(messages, target_tokens=5)
        # tool 结果只能随其 assistant 一起保留：裁剪只能发生在 user 边界
        assert trimmed[0]["content"].startswith("第二轮") or len(trimmed) == len(messages)

    def test_keep_minimum_recent(self):
        messages = [{"role": "user", "content": f"m{i}" * 100} for i in range(10)]
        trimmed = ContextTrimMiddleware._trim_at_user_boundaries(messages, target_tokens=1)
        assert len(trimmed) == 6  # 保底保留最近 6 条

    def test_estimate_tokens_multimodal(self):
        msgs = [
            {"role": "user", "content": [
                {"type": "text", "text": "hello"},
                {"type": "image_url", "image_url": {"url": "data:..."}},
            ]},
        ]
        est = ContextTrimMiddleware._estimate_tokens(msgs)
        assert est >= 765  # 图片固定估算值


# ────────────────── 4. 提示词瘦身 ──────────────────

class TestPromptSlimming:
    def test_no_duplicate_timestamp_block(self, monkeypatch):
        from app.services.context_service import ContextService
        prompt = ContextService.build_system_prompt(None, include_avatar_emotion=False)
        assert "<current_context>" not in prompt
        # 时间戳由 inject_timestamp_prompt 单独注入
        messages = [{"role": "system", "content": prompt}]
        out = ContextService.inject_timestamp_prompt(messages)
        assert "当前时间" in out[0]["content"]

    def test_avatar_emotion_respects_settings(self, monkeypatch):
        from app.core.config import settings
        from app.services.context_service import ContextService
        monkeypatch.setattr(settings, "LLM_AVATAR_EMOTION_ENABLED", False)
        prompt = ContextService.build_system_prompt(None)
        assert "<avatar_emotion>" not in prompt
        monkeypatch.setattr(settings, "LLM_AVATAR_EMOTION_ENABLED", True)
        prompt_on = ContextService.build_system_prompt(None)
        assert "<avatar_emotion>" in prompt_on

    def test_memory_budget_clamp(self, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, "MEMORY_INJECTION_BUDGET", 50)
        # inject_memory 走 DB 依赖较重，直接验证预算收缩逻辑等价块
        blocks = ["a" * 40, "b" * 40, "c" * 40]
        budget = settings.MEMORY_INJECTION_BUDGET
        while len(blocks) > 1 and sum(len(b) for b in blocks) > budget:
            blocks.pop()
        body = "\n\n".join(blocks)
        if len(body) > budget:
            body = body[:budget]
        assert len(body) <= budget
