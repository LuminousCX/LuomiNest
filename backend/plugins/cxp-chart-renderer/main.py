"""CxPlugin 绘图渲染器 — LuomiNest 后端插件主入口。

提供数据可视化图表渲染能力：
- 6 个预置图表工具（折线/散点/柱状/直方/饼图/热力图）
- 1 个自由代码执行工具（沙箱安全执行）
- 1 个发现式 meta-tool（列出可用图表类型）

设计原则：
- 工具通过 register_tool 注册到全局 ToolRegistry
- 图片输出支持 base64 内联和文件路径双模式
- 代码执行走沙箱隔离，AST 白名单扫描
"""
from __future__ import annotations

import os
import sys
from typing import Any

# 将插件目录加入 sys.path（与 cxp-pdf-reader 相同的模式）
_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
if _PLUGIN_DIR not in sys.path:
    sys.path.insert(0, _PLUGIN_DIR)

from app.runtime.plugin.cxplugin import CxPluginBase  # noqa: E402
from app.core.tools import ToolBase, ToolResult  # noqa: E402


class CxChartRendererPlugin(CxPluginBase):
    """CxPlugin 绘图渲染器主类。"""

    plugin_name = "CxPlugin 绘图渲染器"
    plugin_version = "1.0.0"
    plugin_description = "数据可视化图表渲染插件"

    async def initialize(self) -> None:
        # 导入并注册所有工具
        from tools.preset_plots import (
            PlotLineTool, PlotScatterTool, PlotBarTool,
            PlotHistogramTool, PlotPieTool, PlotHeatmapTool,
        )
        from tools.code_executor import ExecutePlotCodeTool
        from tools.meta_tool import ListPlotTypesTool

        tools = [
            PlotLineTool().bind_plugin(self),
            PlotScatterTool().bind_plugin(self),
            PlotBarTool().bind_plugin(self),
            PlotHistogramTool().bind_plugin(self),
            PlotPieTool().bind_plugin(self),
            PlotHeatmapTool().bind_plugin(self),
            ExecutePlotCodeTool().bind_plugin(self),
            ListPlotTypesTool().bind_plugin(self),
        ]

        for tool in tools:
            self.context.register_tool(tool)

        self.logger.info(
            f"[CxChartRenderer] Plugin initialized: "
            f"{len(tools)} tools registered"
        )

    async def terminate(self) -> None:
        self.logger.info("[CxChartRenderer] Plugin terminated")
