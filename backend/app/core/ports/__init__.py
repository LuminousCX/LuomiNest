"""LuomiNest 核心端口包（六边形架构）。

汇集内层核心向外部世界暴露的 Port 契约：
内层只定义接口与调用入口，具体实现由外层（接入层/基础设施）提供，
可通过各端口的 register 函数注入；未注入时使用端口内置的兜底实现
（兜底实现对依赖采用延迟导入，保证本包不顶层依赖任何外层模块）。

端口清单：
- browser_automation: 浏览器自动化执行端口（WS 传输由接入层注入）
- subagent_delegation: 子 Agent 委派端口（兜底延迟导入 subagent_executor 单例）
- task_scheduling: 任务调度执行端口（兜底延迟导入 luominest_scheduler 单例）

依赖方向：外层 → 本包；本包 ↛ 外层（顶层导入禁止）。
"""
