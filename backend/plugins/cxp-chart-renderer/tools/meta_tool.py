"""list_plot_types — 发现式 meta-tool。

供 LLM 按需查询可用图表类型和参数说明。
tier=meta，仅在 LLM 主动发现时注入。
"""
from __future__ import annotations

import json
from typing import Any

from app.core.tools import ToolBase, ToolResult


# 可用图表类型清单
_PLOT_TYPES = [
    {
        "name": "plot_line",
        "description": "折线图 — 展示数据随时间/有序类别的变化趋势",
        "params": "x, y, label?, style?, color?, marker?",
    },
    {
        "name": "plot_scatter",
        "description": "散点图 — 展示两个变量之间的关系",
        "params": "x, y, color?, size?, alpha?",
    },
    {
        "name": "plot_bar",
        "description": "柱状图 — 分类数据的数值比较",
        "params": "labels, values, color?, orientation?, show_values?",
    },
    {
        "name": "plot_histogram",
        "description": "直方图 — 数值数据的分布情况",
        "params": "data, bins?, color?, density?",
    },
    {
        "name": "plot_pie",
        "description": "饼图 — 各部分占整体的比例",
        "params": "labels, values, explode?, show_percent?",
    },
    {
        "name": "plot_heatmap",
        "description": "热力图 — 二维数据的数值分布",
        "params": "data, x_labels?, y_labels?, cmap?, annot?",
    },
    {
        "name": "execute_plot_code",
        "description": "自由代码执行 — 复杂/定制可视化（沙箱安全执行）",
        "params": "code, retry?",
    },
]


class ListPlotTypesTool(ToolBase):
    """列出所有可用图表类型和参数说明。"""

    tier = "meta"
    scope = "shared"

    @property
    def name(self) -> str:
        return "list_plot_types"

    @property
    def description(self) -> str:
        return (
            "列出所有可用的图表渲染工具及其参数说明。"
            "当不确定该用哪个图表类型时调用此工具。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    def bind_plugin(self, plugin: Any) -> "ListPlotTypesTool":
        self._plugin = plugin
        return self

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        return ToolResult.ok(
            json.dumps(_PLOT_TYPES, ensure_ascii=False, indent=2),
            metadata={"tool_count": len(_PLOT_TYPES)},
        )
