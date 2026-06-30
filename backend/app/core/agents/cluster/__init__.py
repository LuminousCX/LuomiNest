"""LuomiNest Agent 集群调用工具集。

提供三种 Agent 集群互相调用模式（参考 综合调查.md §5）：
- agent_tool：OpenAI 兼容 API 自回调（同服务内 Agent 间调用）
- a2a_tool：python-a2a 协议跨服务调用
- sub_agent：子 Agent 委派（位于 app/core/agents/subagent_executor.py）

品牌化命名：所有类/函数使用 LuomiNest/Luminous 前缀，防止侵权。
"""
