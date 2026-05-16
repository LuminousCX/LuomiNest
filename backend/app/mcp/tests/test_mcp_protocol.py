"""
MCP Server 协议兼容性验证脚本（手动模拟 stdio）

直接调用各 Server 的 handle_request 函数，模拟完整的 MCP 协议交互：
initialize → tools/list → tools/call

不依赖 subprocess，适用于 Windows 沙箱环境。

用法：
  python -m app.mcp.tests.test_mcp_protocol
"""

import sys
import os
import json
import asyncio
import time


def simulate_client(handle_fn, server_name: str, icon: str, extra_async_handler=None):
    """模拟一个 MCP 客户端与 Server 通信

    通过直接调用 handle_fn 发送 JSON-RPC 请求，无需子进程。

    参数:
        handle_fn: Server 的请求处理函数
        server_name: 服务器名称
        icon: 图标（emoji）
        extra_async_handler: 异步回调（用于天气查询等需要 await 的调用）
    """
    next_id = 1
    results = []
    start = time.time()

    def _send(method, params=None, expect_content=True):
        nonlocal next_id
        request = {
            "jsonrpc": "2.0",
            "id": next_id,
            "method": method,
            "params": params or {},
        }
        next_id += 1

        response_str = handle_fn(request)
        if response_str is None:
            return None

        # 处理异步标记（天气查询返回 ("ASYNC_WEATHER", id, args) 元组）
        if isinstance(response_str, tuple) and response_str[0] == "ASYNC_WEATHER":
            return {"_async": True, "_id": response_str[1], "_args": response_str[2]}

        response = json.loads(response_str)

        if "error" in response:
            return response

        if expect_content and "result" not in response:
            raise AssertionError(f"{method} 缺少 result: {response}")

        return response

    try:
        # ===== 1. initialize 握手 =====
        print(f"\n  [1/4] {server_name} initialize 握手...")
        resp = _send("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        })
        assert resp["result"]["protocolVersion"] == "2024-11-05"
        assert "tools" in resp["result"]["capabilities"]
        svr_info = resp["result"]["serverInfo"]
        print(f"     协议版本: {resp['result']['protocolVersion']}")
        print(f"     服务名称: {svr_info['name']} v{svr_info['version']}")
        results.append("PASS")

        # ===== 2. 初始化完成通知 =====
        resp = _send("notifications/initialized", expect_content=False)
        assert resp is None
        results.append("PASS")

        # ===== 3. tools/list =====
        print(f"\n  [2/4] {server_name} tools/list 查询工具列表...")
        resp = _send("tools/list")
        tools = resp["result"]["tools"]
        assert len(tools) >= 1
        tool_names = [t["name"] for t in tools]
        print(f"     工具数量: {len(tools)}")
        print(f"     工具列表: {tool_names}")

        for tool in tools:
            assert "name" in tool, f"工具缺少 name"
            assert "description" in tool, f"工具缺少 description"
            assert "inputSchema" in tool, f"工具缺少 inputSchema"
            assert tool["inputSchema"]["type"] == "object"
            print(f"       - {tool['name']}: {tool['description'][:50]}...")

        results.append("PASS")

        # ===== 4. tools/call =====
        print(f"\n  [3/4] {server_name} tools/call 调用工具...")
        first_tool = tools[0]
        call_args = {}

        # 如果工具需要参数，提供默认值
        if "properties" in first_tool["inputSchema"]:
            for prop_name, prop_info in first_tool["inputSchema"]["properties"].items():
                if prop_name == "city":
                    call_args["city"] = "北京"
                elif prop_name == "date":
                    call_args["date"] = "今天"

        resp = _send("tools/call", {
            "name": first_tool["name"],
            "arguments": call_args,
        })

        # 处理异步响应（天气查询返回 {"_async": True} 标记）
        if isinstance(resp, dict) and resp.get("_async"):
            async def _do_async():
                return await extra_async_handler(resp["_id"], resp["_args"])
            resp = asyncio.run(_do_async())
            resp = json.loads(resp)

        content = resp["result"]["content"]
        assert len(content) >= 1
        assert content[0]["type"] == "text"
        assert content[0]["text"]
        print(f"     返回内容: {content[0]['text'][:100]}...")
        results.append("PASS")

        # ===== 5. 错误处理：未知工具 =====
        print(f"\n  [4/4] {server_name} 错误处理: 调用未知工具 unknown_tool_xyz...")
        resp = _send("tools/call", {
            "name": "unknown_tool_xyz",
            "arguments": {},
        }, expect_content=False)
        assert "error" in resp, f"未知工具应返回 error"
        assert resp["error"]["code"] == -32601
        print(f"     错误码: {resp['error']['code']}, 消息: {resp['error']['message']}")
        results.append("PASS")

    except Exception as e:
        print(f"\n     {icon} 失败: {e}")
        results.append(f"FAIL: {e}")
        import traceback
        traceback.print_exc()

    elapsed = time.time() - start
    all_pass = all(r == "PASS" for r in results)
    pass_count = results.count("PASS")
    total_count = len(results)
    status_msg = "全部通过" if all_pass else f"{pass_count}/{total_count} 通过"
    print(f"\n     {server_name} 耗时: {elapsed:.3f}s, 结果: {status_msg}")

    return all_pass


def test_time():
    """测试时间 MCP Server"""
    from app.mcp.servers.time_server import handle_request
    return simulate_client(handle_request, "时间", "(time)")


def test_weather():
    """测试天气 MCP Server（需要网络连接 Open-Meteo API）"""
    from app.mcp.servers.weather_server import (
        handle_request,
        _handle_weather_call,
    )
    return simulate_client(handle_request, "天气", "(weather)", _handle_weather_call)


def main():
    print("=" * 70)
    print("  LuomiNest MCP Server 协议兼容性验证")
    print("  MCP 协议: 2024-11-05 | JSON-RPC 2.0 | stdio")
    print("=" * 70)

    # 运行测试
    time_ok = test_time()
    weather_ok = test_weather()

    # 汇总
    print()
    print("=" * 70)
    print("  最终结果")
    print("=" * 70)
    print(f"  时间 MCP Server:    {'PASS' if time_ok else 'FAIL'}")
    print(f"  天气 MCP Server:    {'PASS' if weather_ok else 'FAIL'}")

    if time_ok and weather_ok:
        print()
        print("  全部 MCP Server 测试通过!")
        print("  这些 Server 现在可被任何兼容 MCP 的客户端加载使用。")
    else:
        print()
        print("  部分测试未通过，请检查失败项。")

    print("=" * 70)


if __name__ == "__main__":
    main()
