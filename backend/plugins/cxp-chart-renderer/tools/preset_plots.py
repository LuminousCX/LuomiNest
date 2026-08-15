"""6 个预置图表工具 — 折线/散点/柱状/直方/饼图/热力图。

每个工具继承 _PresetPlotToolBase，共享通用参数和渲染输出逻辑。
工具通过 renderers.chart_renderer.ChartRenderer 渲染，
输出通过 utils.image_utils.encode_output 编码。
"""
from __future__ import annotations

from typing import Any

from app.core.constants.colors import CHART_DEFAULT_SERIES_COLOR
from app.core.tools import ToolBase, ToolResult


class _PresetPlotToolBase(ToolBase):
    """预置图表工具基类 — 共享通用参数和输出逻辑。"""

    tier = "domain"
    scope = "shared"

    def _common_params(self) -> dict[str, Any]:
        return {
            "title": {"type": "string", "description": "图表标题", "default": ""},
            "xlabel": {"type": "string", "description": "X 轴标签", "default": ""},
            "ylabel": {"type": "string", "description": "Y 轴标签", "default": ""},
            "figsize": {
                "type": "array",
                "items": {"type": "number"},
                "description": "画布尺寸 [宽, 高]（英寸）",
                "default": [8, 5],
            },
            "save_format": {
                "type": "string",
                "enum": ["png", "svg"],
                "description": "输出格式",
                "default": "png",
            },
        }

    def bind_plugin(self, plugin: Any) -> "_PresetPlotToolBase":
        self._plugin = plugin
        return self

    async def _render_and_return(
        self, arguments: dict[str, Any], render_func
    ) -> ToolResult:
        """通用渲染 + 输出流程。"""
        import os
        import sys

        # 确保插件目录在 sys.path 中
        plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if plugin_dir not in sys.path:
            sys.path.insert(0, plugin_dir)

        from renderers.chart_renderer import ChartRenderer
        from utils.image_utils import encode_output, validate_image

        figsize = arguments.get("figsize", [8, 5])
        save_format = arguments.get("save_format", "png")
        inline_threshold_kb = int(
            self._plugin.context.get_config("inline_threshold_kb", 50) or 50
        )

        renderer = ChartRenderer(figsize=tuple(figsize))
        try:
            image_bytes = render_func(renderer, arguments)
        except Exception as e:
            return ToolResult.fail(f"图表渲染失败: {e}")

        # 验证图片
        validation = validate_image(image_bytes)
        if not validation.get("valid", True):
            return ToolResult.fail(f"图片验证失败: {validation.get('error', '')}")

        # 编码输出
        output = encode_output(
            image_bytes,
            inline_threshold_kb=inline_threshold_kb,
            data_dir=self._plugin.context.get_data_dir(),
            fmt=save_format,
        )

        return ToolResult.ok(
            output.get("markdown", ""),
            metadata={
                "mode": output.get("mode", ""),
                "size_kb": output.get("size_kb", 0),
            },
        )


# ─── 6 个具体图表工具 ───


class PlotLineTool(_PresetPlotToolBase):
    @property
    def name(self) -> str:
        return "plot_line"

    @property
    def description(self) -> str:
        return (
            "绘制折线图。适用于展示数据随时间或有序类别的变化趋势。"
            "传入 x 和 y 两个等长数值列表。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        params = self._common_params()
        params.update({
            "x": {"type": "array", "items": {"type": "number"}, "description": "X 轴数据（数值列表）"},
            "y": {"type": "array", "items": {"type": "number"}, "description": "Y 轴数据（与 x 等长）"},
            "label": {"type": "string", "description": "图例标签", "default": ""},
            "style": {"type": "string", "enum": ["solid", "dashed", "dotted", "dashdot"], "description": "线型", "default": "solid"},
            "color": {"type": "string", "description": "线条颜色（matplotlib 颜色名或 hex）", "default": CHART_DEFAULT_SERIES_COLOR},
            "marker": {"type": "string", "description": "数据点标记（如 'o', 's', '^'），空则不标记", "default": ""},
            "show_grid": {"type": "boolean", "description": "是否显示网格", "default": True},
        })
        return {"type": "object", "properties": params, "required": ["x", "y"]}

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        x = arguments.get("x", [])
        y = arguments.get("y", [])
        if not x or not y:
            return ToolResult.fail("缺少 x 或 y 数据")
        if len(x) != len(y):
            return ToolResult.fail(f"x 和 y 长度不匹配: {len(x)} vs {len(y)}")
        return await self._render_and_return(arguments, self._render)

    @staticmethod
    def _render(renderer, args):
        return renderer.render_line(
            args["x"], args["y"],
            label=args.get("label", ""),
            style=args.get("style", "solid"),
            color=args.get("color", CHART_DEFAULT_SERIES_COLOR),
            marker=args.get("marker", ""),
            show_grid=args.get("show_grid", True),
            title=args.get("title", ""),
            xlabel=args.get("xlabel", ""),
            ylabel=args.get("ylabel", ""),
        )


class PlotScatterTool(_PresetPlotToolBase):
    @property
    def name(self) -> str:
        return "plot_scatter"

    @property
    def description(self) -> str:
        return "绘制散点图。适用于展示两个变量之间的关系或数据分布。"

    @property
    def parameters(self) -> dict[str, Any]:
        params = self._common_params()
        params.update({
            "x": {"type": "array", "items": {"type": "number"}, "description": "X 轴数据"},
            "y": {"type": "array", "items": {"type": "number"}, "description": "Y 轴数据（与 x 等长）"},
            "color": {"type": "string", "description": "散点颜色", "default": CHART_DEFAULT_SERIES_COLOR},
            "size": {"type": "number", "description": "散点大小", "default": 50},
            "alpha": {"type": "number", "description": "透明度（0-1）", "default": 0.7},
            "show_grid": {"type": "boolean", "description": "是否显示网格", "default": True},
        })
        return {"type": "object", "properties": params, "required": ["x", "y"]}

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        x = arguments.get("x", [])
        y = arguments.get("y", [])
        if not x or not y:
            return ToolResult.fail("缺少 x 或 y 数据")
        return await self._render_and_return(arguments, self._render)

    @staticmethod
    def _render(renderer, args):
        return renderer.render_scatter(
            args["x"], args["y"],
            c=args.get("color", CHART_DEFAULT_SERIES_COLOR),
            s=args.get("size", 50),
            alpha=args.get("alpha", 0.7),
            show_grid=args.get("show_grid", True),
            title=args.get("title", ""),
            xlabel=args.get("xlabel", ""),
            ylabel=args.get("ylabel", ""),
        )


class PlotBarTool(_PresetPlotToolBase):
    @property
    def name(self) -> str:
        return "plot_bar"

    @property
    def description(self) -> str:
        return "绘制柱状图。适用于分类数据的数值比较。"

    @property
    def parameters(self) -> dict[str, Any]:
        params = self._common_params()
        params.update({
            "labels": {"type": "array", "items": {"type": "string"}, "description": "分类标签列表"},
            "values": {"type": "array", "items": {"type": "number"}, "description": "各类别数值"},
            "color": {"type": "string", "description": "柱体颜色", "default": CHART_DEFAULT_SERIES_COLOR},
            "orientation": {"type": "string", "enum": ["vertical", "horizontal"], "description": "方向", "default": "vertical"},
            "show_values": {"type": "boolean", "description": "是否在柱顶显示数值", "default": False},
            "show_grid": {"type": "boolean", "description": "是否显示网格", "default": True},
        })
        return {"type": "object", "properties": params, "required": ["labels", "values"]}

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        if not arguments.get("labels") or not arguments.get("values"):
            return ToolResult.fail("缺少 labels 或 values 数据")
        return await self._render_and_return(arguments, self._render)

    @staticmethod
    def _render(renderer, args):
        return renderer.render_bar(
            args["labels"], args["values"],
            color=args.get("color", CHART_DEFAULT_SERIES_COLOR),
            orientation=args.get("orientation", "vertical"),
            show_values=args.get("show_values", False),
            show_grid=args.get("show_grid", True),
            title=args.get("title", ""),
            xlabel=args.get("xlabel", ""),
            ylabel=args.get("ylabel", ""),
        )


class PlotHistogramTool(_PresetPlotToolBase):
    @property
    def name(self) -> str:
        return "plot_histogram"

    @property
    def description(self) -> str:
        return "绘制直方图。适用于展示数值数据的分布情况。"

    @property
    def parameters(self) -> dict[str, Any]:
        params = self._common_params()
        params.update({
            "data": {"type": "array", "items": {"type": "number"}, "description": "原始数值数据列表"},
            "bins": {"type": "integer", "description": "分箱数量", "default": 10},
            "color": {"type": "string", "description": "柱体颜色", "default": CHART_DEFAULT_SERIES_COLOR},
            "density": {"type": "boolean", "description": "是否归一化为概率密度", "default": False},
            "show_grid": {"type": "boolean", "description": "是否显示网格", "default": True},
        })
        return {"type": "object", "properties": params, "required": ["data"]}

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        if not arguments.get("data"):
            return ToolResult.fail("缺少 data 数据")
        return await self._render_and_return(arguments, self._render)

    @staticmethod
    def _render(renderer, args):
        return renderer.render_histogram(
            args["data"],
            bins=args.get("bins", 10),
            color=args.get("color", CHART_DEFAULT_SERIES_COLOR),
            density=args.get("density", False),
            show_grid=args.get("show_grid", True),
            title=args.get("title", ""),
            xlabel=args.get("xlabel", ""),
            ylabel=args.get("ylabel", ""),
        )


class PlotPieTool(_PresetPlotToolBase):
    @property
    def name(self) -> str:
        return "plot_pie"

    @property
    def description(self) -> str:
        return "绘制饼图。适用于展示各部分占整体的比例。"

    @property
    def parameters(self) -> dict[str, Any]:
        # 饼图不需要 xlabel/ylabel/show_grid
        params = {
            "title": {"type": "string", "description": "图表标题", "default": ""},
            "figsize": {"type": "array", "items": {"type": "number"}, "description": "画布尺寸", "default": [8, 5]},
            "save_format": {"type": "string", "enum": ["png", "svg"], "description": "输出格式", "default": "png"},
            "labels": {"type": "array", "items": {"type": "string"}, "description": "各部分标签"},
            "values": {"type": "array", "items": {"type": "number"}, "description": "各部分数值"},
            "explode": {"type": "array", "items": {"type": "number"}, "description": "各部分偏移量", "default": []},
            "show_percent": {"type": "boolean", "description": "是否显示百分比", "default": True},
            "start_angle": {"type": "number", "description": "起始角度（度）", "default": 90},
        }
        return {"type": "object", "properties": params, "required": ["labels", "values"]}

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        if not arguments.get("labels") or not arguments.get("values"):
            return ToolResult.fail("缺少 labels 或 values 数据")
        return await self._render_and_return(arguments, self._render)

    @staticmethod
    def _render(renderer, args):
        return renderer.render_pie(
            args["labels"], args["values"],
            explode=args.get("explode") or None,
            show_percent=args.get("show_percent", True),
            start_angle=args.get("start_angle", 90),
            title=args.get("title", ""),
        )


class PlotHeatmapTool(_PresetPlotToolBase):
    @property
    def name(self) -> str:
        return "plot_heatmap"

    @property
    def description(self) -> str:
        return "绘制热力图。适用于展示二维数据的数值分布（如相关系数矩阵、混淆矩阵）。"

    @property
    def parameters(self) -> dict[str, Any]:
        params = self._common_params()
        params.update({
            "data": {
                "type": "array",
                "items": {"type": "array", "items": {"type": "number"}},
                "description": "二维数值矩阵（如 [[1,2],[3,4]]）",
            },
            "x_labels": {"type": "array", "items": {"type": "string"}, "description": "X 轴标签", "default": []},
            "y_labels": {"type": "array", "items": {"type": "string"}, "description": "Y 轴标签", "default": []},
            "cmap": {"type": "string", "description": "配色方案（matplotlib colormap 名）", "default": "viridis"},
            "annot": {"type": "boolean", "description": "是否在单元格中显示数值", "default": True},
            "fmt": {"type": "string", "description": "数值格式化（如 '.2f'）", "default": ".2f"},
        })
        return {"type": "object", "properties": params, "required": ["data"]}

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        if not arguments.get("data"):
            return ToolResult.fail("缺少 data 数据")
        return await self._render_and_return(arguments, self._render)

    @staticmethod
    def _render(renderer, args):
        return renderer.render_heatmap(
            args["data"],
            x_labels=args.get("x_labels") or None,
            y_labels=args.get("y_labels") or None,
            cmap=args.get("cmap", "viridis"),
            annot=args.get("annot", True),
            fmt=args.get("fmt", ".2f"),
            title=args.get("title", ""),
            xlabel=args.get("xlabel", ""),
            ylabel=args.get("ylabel", ""),
        )
