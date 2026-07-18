"""LuomiNest Agent 中间件链系统。

自研轻量中间件（参考 deer-flow 钩子分类 + airi 观察者模式，不引入 LangChain），
统一 4 处重复的工具调用循环（stream_chat / stream_response / subagent / group_chat）。

模块组成：
- base.py: AgentContext + AgentMiddleware 基类 + HookRegistry 观察者模式注册表
- pipeline.py: MiddlewarePipeline（按顺序执行钩子）
- builtin.py: 8 个内置中间件
- runner.py: AgentRunner（统一工具调用循环编排器）

10 个钩子点（6 原有 + 4 新增）：
- before_agent / before_model：正序（0→N）
- on_before_message_composed / on_after_message_composed：正序，链式传递 messages
- after_model / after_tool_call / after_agent：反序（N→0）
- on_stream_token：正序，流式 token 通知
- on_chat_turn_complete：正序，回合完成通知
- wrap_tool_call：洋葱式（idx=0 最外层，idx=N 调 execute_fn）

HookRegistry 提供运行时动态注册/取消回调能力，与中间件管道并行工作。
"""
