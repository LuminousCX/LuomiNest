"""W6-1 对外 MCP 服务器的单元测试。

覆盖：
- build_luominest_mcp_server：白名单工具构建、schema 透传、未注册工具跳过
- call_tool 端到端：参数按注册表 schema 校验并真正路由到 tool_registry
- 高权限工具不暴露
"""
import pytest


class _FakeTool:
    def __init__(self, name: str, description: str, output: str = "ok") -> None:
        self._name = name
        self._description = description
        self._output = output
        self.received: dict | None = None
        self.tier = "core"
        self.parameters = {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "城市"}},
            "required": ["city"],
        }

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    async def execute(self, arguments: dict) -> object:
        self.received = arguments

        class _R:
            success = True
            output = self._output
            error = ""

        return _R()


@pytest.mark.asyncio
async def test_build_and_call(monkeypatch):
    import app.core.mcp_server.server as srv

    fake = _FakeTool("get_current_time", "查询当前时间")
    reg = type("R", (), {})()
    reg.get = lambda name: fake if name == "get_current_time" else None
    monkeypatch.setattr(srv.tool_registry, "get", reg.get)

    server = srv.build_luominest_mcp_server()
    tools = await server.list_tools()
    assert tools, "至少应暴露白名单中已注册的工具"
    by_name = {t.name for t in tools}
    assert "get_current_time" in by_name
    # schema 透传自注册表
    schema = next(t for t in tools if t.name == "get_current_time").input_schema
    assert schema.get("required") == ["city"]

    result = await server.call_tool("get_current_time", {"city": "北京"})
    assert fake.received == {"city": "北京"}
    assert "ok" in str(result)


@pytest.mark.asyncio
async def test_power_tools_not_exposed(monkeypatch):
    import app.core.mcp_server.server as srv

    assert "cli" not in srv.MCP_EXPOSED_TOOLS
    assert "write_file" not in srv.MCP_EXPOSED_TOOLS
    assert "launch_application" not in srv.MCP_EXPOSED_TOOLS

    reg = type("R", (), {})()
    reg.get = lambda name: None  # 全部未注册
    monkeypatch.setattr(srv.tool_registry, "get", reg.get)
    server = srv.build_luominest_mcp_server()
    assert await server.list_tools() == []
