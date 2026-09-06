"""Phase 4 单元测试: 中间件管道（MiddlewarePipeline）。

验证：
1. before_agent / before_model 正序执行（0→N）
2. after_model / after_agent 反序执行（N→0）
3. wrap_tool_call 洋葱式执行（外层先进入后退出）
4. 中间件中断（raise 异常时后续不执行）
5. ctx 在中间件间正确传递
6. 空中间件列表不报错

运行方式：python tests/unit/test_middleware_pipeline.py
"""
import os
import sys
import asyncio

sys.path.insert(0, r"D:/Projects/My_Projects/LuomiNest/backend")
os.environ.setdefault("DATA_DIR", "/tmp/luominest_test_middleware")
os.environ.setdefault("SECRET_KEY", "test-key-not-for-production-use")

from app.core.agents.middleware.base import AgentContext, AgentMiddleware
from app.core.agents.middleware.pipeline import MiddlewarePipeline
from app.runtime.provider.llm.types import RouteHint

passed = 0
failed = 0


def check(name: str, cond: bool, detail: str = ""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name}" + (f" ({detail})" if detail else ""))


# ──────────────────────────────────────────────────────────────
# 测试用中间件：记录执行顺序
# ──────────────────────────────────────────────────────────────


class OrderRecordMiddleware(AgentMiddleware):
    """记录每个钩子的执行顺序到 ctx.state["order_log"]。"""

    def __init__(self, name: str):
        self.name = name

    def _log(self, ctx: AgentContext, hook: str) -> None:
        ctx.state.setdefault("order_log", []).append(f"{self.name}.{hook}")

    async def before_agent(self, ctx: AgentContext) -> None:
        self._log(ctx, "before_agent")

    async def before_model(self, ctx: AgentContext) -> None:
        self._log(ctx, "before_model")

    async def after_model(self, ctx, response) -> None:
        self._log(ctx, "after_model")

    async def after_tool_call(self, ctx, tool_call, result) -> None:
        self._log(ctx, "after_tool_call")

    async def after_agent(self, ctx: AgentContext) -> None:
        self._log(ctx, "after_agent")

    async def wrap_tool_call(self, ctx, tool_call, next_fn):
        self._log(ctx, "wrap_enter")
        result = await next_fn(tool_call)
        self._log(ctx, "wrap_exit")
        return result


class AbortMiddleware(AgentMiddleware):
    """在 before_model 抛出异常，测试中断行为。"""

    def __init__(self, name: str):
        self.name = name

    async def before_model(self, ctx: AgentContext) -> None:
        ctx.state.setdefault("order_log", []).append(f"{self.name}.before_model")
        raise RuntimeError(f"{self.name} aborted")


class FailToolMiddleware(AgentMiddleware):
    """在 wrap_tool_call 抛出异常，测试洋葱中断。"""

    def __init__(self, name: str):
        self.name = name

    async def wrap_tool_call(self, ctx, tool_call, next_fn):
        ctx.state.setdefault("order_log", []).append(f"{self.name}.wrap_enter")
        raise RuntimeError(f"{self.name} tool failed")


def make_ctx() -> AgentContext:
    """创建测试用 AgentContext。"""
    return AgentContext(
        messages=[{"role": "user", "content": "hello"}],
        tools=[],
        route_hint=RouteHint.CHAT,
        state={"order_log": []},
    )


# ════════════════════════════════════════════════════
# 1. before_agent / before_model 正序执行
# ════════════════════════════════════════════════════
print("\n=== 1. before_agent / before_model 正序执行 ===")

async def test_before_order():
    ctx = make_ctx()
    pipeline = MiddlewarePipeline([
        OrderRecordMiddleware("A"),
        OrderRecordMiddleware("B"),
        OrderRecordMiddleware("C"),
    ])
    await pipeline.run_before_agent(ctx)
    await pipeline.run_before_model(ctx)
    log = ctx.state["order_log"]
    check("before_agent 正序 A→B→C",
          log[0:3] == ["A.before_agent", "B.before_agent", "C.before_agent"],
          f"got={log[0:3]}")
    check("before_model 正序 A→B→C",
          log[3:6] == ["A.before_model", "B.before_model", "C.before_model"],
          f"got={log[3:6]}")

asyncio.run(test_before_order())


# ════════════════════════════════════════════════════
# 2. after_model / after_agent 反序执行
# ════════════════════════════════════════════════════
print("\n=== 2. after_model / after_agent 反序执行 ===")

async def test_after_order():
    ctx = make_ctx()
    pipeline = MiddlewarePipeline([
        OrderRecordMiddleware("A"),
        OrderRecordMiddleware("B"),
        OrderRecordMiddleware("C"),
    ])
    await pipeline.run_after_model(ctx, None)
    await pipeline.run_after_agent(ctx)
    log = ctx.state["order_log"]
    check("after_model 反序 C→B→A",
          log[0:3] == ["C.after_model", "B.after_model", "A.after_model"],
          f"got={log[0:3]}")
    check("after_agent 反序 C→B→A",
          log[3:6] == ["C.after_agent", "B.after_agent", "A.after_agent"],
          f"got={log[3:6]}")

asyncio.run(test_after_order())


# ════════════════════════════════════════════════════
# 3. wrap_tool_call 洋葱式执行（外层先进入后退出）
# ════════════════════════════════════════════════════
print("\n=== 3. wrap_tool_call 洋葱式执行 ===")

async def test_wrap_onion():
    ctx = make_ctx()
    pipeline = MiddlewarePipeline([
        OrderRecordMiddleware("A"),  # idx=0 最外层
        OrderRecordMiddleware("B"),  # idx=1
        OrderRecordMiddleware("C"),  # idx=2 最内层
    ])

    execute_called = []

    async def execute_fn(tool_call):
        execute_called.append("execute")
        return {"role": "tool", "content": "result"}

    result = await pipeline.run_tool_call(ctx, {"id": "tc1"}, execute_fn)
    log = ctx.state["order_log"]

    # 期望：A.enter → B.enter → C.enter → execute → C.exit → B.exit → A.exit
    expected = [
        "A.wrap_enter", "B.wrap_enter", "C.wrap_enter",
        "C.wrap_exit", "B.wrap_exit", "A.wrap_exit",
    ]
    check("洋葱式外层先进入后退出",
          log == expected, f"got={log}")
    check("execute_fn 被调用一次", len(execute_called) == 1, f"got={execute_called}")
    check("返回工具结果", result == {"role": "tool", "content": "result"})

asyncio.run(test_wrap_onion())


# ════════════════════════════════════════════════════
# 4. 中间件中断（before_model 异常）
# ════════════════════════════════════════════════════
print("\n=== 4. 中间件中断（before_model 异常） ===")

async def test_before_interrupt():
    ctx = make_ctx()
    pipeline = MiddlewarePipeline([
        OrderRecordMiddleware("A"),
        AbortMiddleware("B"),
        OrderRecordMiddleware("C"),
    ])
    interrupted = False
    try:
        await pipeline.run_before_model(ctx)
    except RuntimeError as e:
        interrupted = True
        check("异常被抛出", "B aborted" in str(e))
    log = ctx.state["order_log"]
    check("A.before_model 执行", "A.before_model" in log)
    check("B.before_model 执行（抛异常前记录）", "B.before_model" in log)
    check("C.before_model 未执行（被 B 中断）", "C.before_model" not in log)
    check("异常标志为 True", interrupted)

asyncio.run(test_before_interrupt())


# ════════════════════════════════════════════════════
# 5. wrap_tool_call 中断（内层异常传播）
# ════════════════════════════════════════════════════
print("\n=== 5. wrap_tool_call 中断（内层异常传播） ===")

async def test_wrap_interrupt():
    ctx = make_ctx()
    pipeline = MiddlewarePipeline([
        OrderRecordMiddleware("A"),
        FailToolMiddleware("B"),
        OrderRecordMiddleware("C"),
    ])

    async def execute_fn(tool_call):
        return {"role": "tool", "content": "should not reach"}

    interrupted = False
    try:
        await pipeline.run_tool_call(ctx, {"id": "tc1"}, execute_fn)
    except RuntimeError as e:
        interrupted = True
        check("工具异常被抛出", "B tool failed" in str(e))
    log = ctx.state["order_log"]
    check("A.wrap_enter 执行", "A.wrap_enter" in log)
    check("B.wrap_enter 执行（抛异常前记录）", "B.wrap_enter" in log)
    check("C.wrap_enter 未执行（被 B 中断）", "C.wrap_enter" not in log)
    check("A.wrap_exit 未执行（异常未捕获）", "A.wrap_exit" not in log)
    check("异常标志为 True", interrupted)

asyncio.run(test_wrap_interrupt())


# ════════════════════════════════════════════════════
# 6. ctx 在中间件间正确传递
# ════════════════════════════════════════════════════
print("\n=== 6. ctx 在中间件间正确传递 ===")

class MutateCtxMiddleware(AgentMiddleware):
    """修改 ctx.state 验证传递。"""

    def __init__(self, key: str, value: str):
        self.key = key
        self.value = value

    async def before_agent(self, ctx: AgentContext) -> None:
        ctx.state[self.key] = self.value

    async def wrap_tool_call(self, ctx, tool_call, next_fn):
        ctx.state[f"{self.key}_wrap"] = self.value
        return await next_fn(tool_call)

async def test_ctx_passing():
    ctx = make_ctx()
    pipeline = MiddlewarePipeline([
        MutateCtxMiddleware("k1", "v1"),
        MutateCtxMiddleware("k2", "v2"),
    ])
    await pipeline.run_before_agent(ctx)

    async def execute_fn(tool_call):
        return {"role": "tool", "content": "ok"}

    await pipeline.run_tool_call(ctx, {"id": "tc1"}, execute_fn)

    check("before_agent 写入 k1", ctx.state.get("k1") == "v1")
    check("before_agent 写入 k2", ctx.state.get("k2") == "v2")
    check("wrap_tool_call 写入 k1_wrap", ctx.state.get("k1_wrap") == "v1")
    check("wrap_tool_call 写入 k2_wrap", ctx.state.get("k2_wrap") == "v2")
    check("原始 messages 仍存在", len(ctx.messages) == 1)

asyncio.run(test_ctx_passing())


# ════════════════════════════════════════════════════
# 7. 空中间件列表不报错
# ════════════════════════════════════════════════════
print("\n=== 7. 空中间件列表不报错 ===")

async def test_empty_pipeline():
    ctx = make_ctx()
    pipeline = MiddlewarePipeline([])

    await pipeline.run_before_agent(ctx)
    await pipeline.run_before_model(ctx)
    await pipeline.run_after_model(ctx, None)
    await pipeline.run_after_agent(ctx)

    async def execute_fn(tool_call):
        return {"role": "tool", "content": "direct"}

    result = await pipeline.run_tool_call(ctx, {"id": "tc1"}, execute_fn)
    check("空管道 before_agent 不报错", True)
    check("空管道 before_model 不报错", True)
    check("空管道 after_model 不报错", True)
    check("空管道 after_agent 不报错", True)
    check("空管道 run_tool_call 直接调 execute_fn",
          result == {"role": "tool", "content": "direct"})

asyncio.run(test_empty_pipeline())


# ════════════════════════════════════════════════════
# 8. after_tool_call 反序执行
# ════════════════════════════════════════════════════
print("\n=== 8. after_tool_call 反序执行 ===")

async def test_after_tool_call_order():
    ctx = make_ctx()
    pipeline = MiddlewarePipeline([
        OrderRecordMiddleware("A"),
        OrderRecordMiddleware("B"),
        OrderRecordMiddleware("C"),
    ])
    await pipeline.run_after_tool_call(ctx, {"id": "tc1"}, {"role": "tool", "content": "ok"})
    log = ctx.state["order_log"]
    check("after_tool_call 反序 C→B→A",
          log == ["C.after_tool_call", "B.after_tool_call", "A.after_tool_call"],
          f"got={log}")

asyncio.run(test_after_tool_call_order())


# ════════════════════════════════════════════════════
# 结果汇总
# ════════════════════════════════════════════════════
print(f"\n{'=' * 60}")
print(f"test_middleware_pipeline 结果: {passed} passed, {failed} failed")
print(f"{'=' * 60}")
sys.exit(0 if failed == 0 else 1)
