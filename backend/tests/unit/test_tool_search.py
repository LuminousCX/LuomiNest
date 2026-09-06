"""工具检索（S1b）与对话模式配置回归测试。

覆盖：
- score_tool_match 轻量评分（拉丁词/CJK 加权）
- ToolRegistry.search：召回、meta tier 排除、top_k 截断、空 query
- InternalToolRegistry.search / get_schemas_for
- chat_mode：仅 normal/standard 两模式（ULTRA 已移除）、白名单含 meta 工具
- WorkflowSubmitRequest：legacy ultra 入参归一为 standard
"""

from app.core.chat_mode import CHAT_MODE_TOOL_CONFIGS, ChatMode
from app.core.tools.registry import ToolBase, ToolRegistry, ToolResult, score_tool_match
from app.core.workflow.internal_registry import InternalToolRegistry
from app.core.workflow.models import WorkflowMode


class _FakeTool(ToolBase):
    def __init__(
        self,
        name: str,
        description: str,
        tier: str = "domain",
    ) -> None:
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


# ────────────────────────── score_tool_match ──────────────────────────

def test_score_latin_name_beats_description():
    assert score_tool_match("memory search", "memory_search", "search user memory facts") >= 3
    # 命中 name（+3+3）应高于仅命中 description（+1+1）
    name_hit = score_tool_match("memory search", "memory_search", "irrelevant")
    desc_hit = score_tool_match("memory search", "other_tool", "search user memory facts")
    assert name_hit > desc_hit


def test_score_cjk_run_in_description():
    score = score_tool_match("搜索记忆", "other_tool", "按关键词搜索记忆事实")
    assert score > 0


def test_score_empty_query_is_zero():
    assert score_tool_match("", "anything", "desc") == 0
    assert score_tool_match("   ", "anything", "desc") == 0


# ────────────────────────── ToolRegistry.search ──────────────────────────

def _make_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(_FakeTool("memory_search", "按关键词搜索记忆事实与向量"))
    registry.register(_FakeTool("create_scheduled_task", "创建定时任务，支持 cron 表达式"))
    registry.register(_FakeTool("browser_screenshot", "截取当前浏览器页面截图"))
    registry.register(_FakeTool("cli", "执行命令行命令"))
    registry.register(_FakeTool("list_luominest_tools", "列出全部工具", tier="meta"))
    return registry


def test_registry_search_recalls_by_cjk():
    registry = _make_registry()
    names = [t.name for t in registry.search("帮我搜索记忆", top_k=5)]
    assert "memory_search" in names
    assert "create_scheduled_task" not in names[:1]  # 相关性排序首位应是记忆工具


def test_registry_search_excludes_meta_tier():
    registry = _make_registry()
    names = [t.name for t in registry.search("列出全部工具 tools", top_k=10)]
    assert "list_luominest_tools" not in names


def test_registry_search_top_k_and_empty():
    registry = _make_registry()
    assert len(registry.search("task 任务", top_k=1)) == 1
    assert registry.search("", top_k=5) == []
    assert registry.search("zzz_no_match_keyword", top_k=5) == []


# ────────────────────────── InternalToolRegistry ──────────────────────────

async def test_internal_registry_search_and_schemas():
    registry = InternalToolRegistry()
    await registry.register(
        name="memory.search", module="memory", description="搜索记忆事实",
        handler=lambda args: None, parameters_schema={"type": "object", "properties": {"query": {"type": "string"}}},
    )
    await registry.register(
        name="tool.read", module="meta", description="读取工具定义",
        handler=lambda args: None, parameters_schema={"type": "object", "properties": {}},
    )
    hits = registry.search("搜索记忆", top_k=5)
    assert [t.name for t in hits] == ["memory.search"]  # meta 模块不参与召回
    schemas = registry.get_schemas_for({"memory.search", "missing.tool"})
    assert len(schemas) == 1
    assert schemas[0]["parameters"]["properties"]


# ────────────────────────── chat_mode 回归 ──────────────────────────

def test_chat_mode_only_normal_and_standard():
    assert set(CHAT_MODE_TOOL_CONFIGS.keys()) == {ChatMode.NORMAL, ChatMode.STANDARD}
    assert ChatMode.NORMAL.value == "normal"
    assert ChatMode.STANDARD.value == "standard"
    # 防止 ULTRA 以任何形式回流
    assert not hasattr(ChatMode, "ULTRA")


def test_normal_whitelist_contains_meta_tools():
    whitelist = CHAT_MODE_TOOL_CONFIGS[ChatMode.NORMAL]["whitelist"]
    assert "list_luominest_tools" in whitelist
    assert "read_luominest_tool" in whitelist
    assert CHAT_MODE_TOOL_CONFIGS[ChatMode.NORMAL]["is_workflow"] is False
    assert CHAT_MODE_TOOL_CONFIGS[ChatMode.STANDARD]["is_workflow"] is True
    # 浏览器工具瘦身后 STANDARD 不再有排除集
    assert "exclude_tools" not in CHAT_MODE_TOOL_CONFIGS[ChatMode.STANDARD]


def test_workflow_mode_only_standard():
    assert not hasattr(WorkflowMode, "ULTRA")
    assert WorkflowMode.STANDARD.value == "standard"


# ────────────────────────── workflow 入参归一 ──────────────────────────

def test_workflow_submit_request_normalizes_legacy_ultra():
    from app.api.v1.endpoints.workflow import WorkflowSubmitRequest

    req = WorkflowSubmitRequest(message="test", mode="ultra")
    assert req.mode == WorkflowMode.STANDARD
    req2 = WorkflowSubmitRequest(message="test", mode="standard")
    assert req2.mode == WorkflowMode.STANDARD
