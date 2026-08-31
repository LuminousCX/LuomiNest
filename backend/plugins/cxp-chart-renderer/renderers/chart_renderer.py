"""图表渲染引擎 — matplotlib Agg 后端封装。

所有预置图表工具的底层渲染器。强制使用非交互式后端，
直接输出图片 bytes，不尝试显示窗口。
"""
import io
from typing import Any

import matplotlib
matplotlib.use("Agg")  # 必须在 import pyplot 之前
import matplotlib.pyplot as plt
import numpy as np

from app.core.constants.colors import CHART_DEFAULT_SERIES_COLOR

# 所有方法需要从 kwargs 中提取的样式参数
_STYLE_KEYS = {"title", "xlabel", "ylabel", "figsize", "save_format"}


class ChartRenderer:
    """图表渲染器。"""

    def __init__(self, figsize: tuple[float, float] = (8, 5)):
        self.figsize = figsize

    def render_line(self, x, y, **kwargs) -> bytes:
        fig, ax = plt.subplots(figsize=self.figsize)
        style_map = {"solid": "-", "dashed": "--", "dotted": ":", "dashdot": "-."}
        linestyle = style_map.get(kwargs.pop("style", "solid"), "-")
        label = kwargs.pop("label", None) or None
        marker = kwargs.pop("marker", None) or None
        color = kwargs.pop("color", CHART_DEFAULT_SERIES_COLOR)
        show_grid = kwargs.pop("show_grid", True)
        self._pop_style(kwargs)
        ax.plot(x, y, linestyle=linestyle, color=color, label=label, marker=marker)
        self._apply_style(ax, kwargs, show_grid)
        if label:
            ax.legend()
        return self._save(fig)

    def render_scatter(self, x, y, **kwargs) -> bytes:
        fig, ax = plt.subplots(figsize=self.figsize)
        show_grid = kwargs.pop("show_grid", True)
        color = kwargs.pop("color", CHART_DEFAULT_SERIES_COLOR)
        size = kwargs.pop("size", 50)
        alpha = kwargs.pop("alpha", 0.7)
        self._pop_style(kwargs)
        ax.scatter(x, y, c=color, s=size, alpha=alpha)
        self._apply_style(ax, kwargs, show_grid)
        return self._save(fig)

    def render_bar(self, labels, values, **kwargs) -> bytes:
        fig, ax = plt.subplots(figsize=self.figsize)
        orientation = kwargs.pop("orientation", "vertical")
        show_values = kwargs.pop("show_values", False)
        show_grid = kwargs.pop("show_grid", True)
        color = kwargs.pop("color", CHART_DEFAULT_SERIES_COLOR)
        self._pop_style(kwargs)
        if orientation == "horizontal":
            bars = ax.barh(labels, values, color=color)
        else:
            bars = ax.bar(labels, values, color=color)
        if show_values:
            for bar in bars:
                if orientation == "horizontal":
                    height = bar.get_width()
                    ax.text(height, bar.get_y() + bar.get_height() / 2,
                            f"{height:g}", ha="left", va="center", fontsize=8)
                else:
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width() / 2, height,
                            f"{height:g}", ha="center", va="bottom", fontsize=8)
        self._apply_style(ax, kwargs, show_grid)
        return self._save(fig)

    def render_histogram(self, data, **kwargs) -> bytes:
        fig, ax = plt.subplots(figsize=self.figsize)
        show_grid = kwargs.pop("show_grid", True)
        color = kwargs.pop("color", CHART_DEFAULT_SERIES_COLOR)
        bins = kwargs.pop("bins", 10)
        density = kwargs.pop("density", False)
        self._pop_style(kwargs)
        ax.hist(data, bins=bins, color=color, density=density, edgecolor="white", alpha=0.8)
        self._apply_style(ax, kwargs, show_grid)
        return self._save(fig)

    def render_pie(self, labels, values, **kwargs) -> bytes:
        fig, ax = plt.subplots(figsize=self.figsize)
        explode = kwargs.pop("explode", None) or None
        show_percent = kwargs.pop("show_percent", True)
        start_angle = kwargs.pop("start_angle", 90)
        title = kwargs.pop("title", "")
        # 清理剩余样式键
        self._pop_style(kwargs)
        autopct = "%1.1f%%" if show_percent else None
        ax.pie(values, labels=labels, explode=explode, autopct=autopct, startangle=start_angle)
        if title:
            ax.set_title(title)
        return self._save(fig)

    def render_heatmap(self, data, **kwargs) -> bytes:
        fig, ax = plt.subplots(figsize=self.figsize)
        arr = np.array(data)
        cmap = kwargs.pop("cmap", "viridis")
        annot = kwargs.pop("annot", True)
        fmt = kwargs.pop("fmt", ".2f")
        x_labels = kwargs.pop("x_labels", None) or None
        y_labels = kwargs.pop("y_labels", None) or None
        show_grid = kwargs.pop("show_grid", False)
        self._pop_style(kwargs)
        im = ax.imshow(arr, cmap=cmap, aspect="auto")
        if annot:
            for i in range(arr.shape[0]):
                for j in range(arr.shape[1]):
                    val = arr[i, j]
                    text_color = "white" if val > (arr.max() + arr.min()) / 2 else "black"
                    ax.text(j, i, f"{val:{fmt}}", ha="center", va="center",
                            color=text_color, fontsize=8)
        if x_labels:
            ax.set_xticks(range(len(x_labels)))
            ax.set_xticklabels(x_labels, rotation=45, ha="right")
        if y_labels:
            ax.set_yticks(range(len(y_labels)))
            ax.set_yticklabels(y_labels)
        fig.colorbar(im, ax=ax, shrink=0.8)
        self._apply_style(ax, kwargs, show_grid)
        return self._save(fig)

    def _pop_style(self, kwargs: dict) -> dict:
        """提取并移除样式参数，返回样式字典。"""
        style = {}
        for key in list(kwargs.keys()):
            if key in _STYLE_KEYS:
                style[key] = kwargs.pop(key)
        return style

    def _apply_style(self, ax, kwargs, show_grid=True):
        """应用通用样式（标题、标签、网格）。"""
        title = kwargs.pop("title", "") if "title" in kwargs else ""
        xlabel = kwargs.pop("xlabel", "") if "xlabel" in kwargs else ""
        ylabel = kwargs.pop("ylabel", "") if "ylabel" in kwargs else ""
        if title:
            ax.set_title(title)
        if xlabel:
            ax.set_xlabel(xlabel)
        if ylabel:
            ax.set_ylabel(ylabel)
        if show_grid:
            ax.grid(True, alpha=0.3)

    def _save(self, fig, fmt="png") -> bytes:
        buf = io.BytesIO()
        fig.savefig(buf, format=fmt, dpi=100, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        buf.seek(0)
        return buf.read()
