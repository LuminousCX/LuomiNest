"""LuomiNest Agent 中间件链系统。

自研轻量中间件（参考 deer-flow 钩子分类，不引入 LangChain），
统一 4 处重复的工具调用循环（stream_chat / stream_response / subagent / group_chat）。

模块组成：
- base.py: AgentContext + AgentMiddleware 基类
- pipeline.py: MiddlewarePipeline（按顺序执行钩子）
- builtin.py: 8 个内置中间件
- runner.py: AgentRunner（统一工具调用循环编排器）

钩子执行顺序（列表位置驱动）：
- before_agent / before_model：正序（0→N）
- after_model / after_tool_call / after_agent：反序（N→0）
- wrap_tool_call：洋葱式（idx=0 最外层，idx=N 调 execute_fn）
"""
